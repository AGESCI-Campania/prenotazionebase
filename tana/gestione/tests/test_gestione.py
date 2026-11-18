import csv
import datetime
import io

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.test import Client
from django.urls import reverse
from openpyxl import load_workbook

from tana.accounts.models import Nomina, Ruolo, User
from tana.accounts.services import nomina
from tana.base.models import Area, Configurazione
from tana.gestione import statistiche
from tana.listini.models import Categoria, VersioneListino
from tana.prenotazioni import contributo, flusso
from tana.prenotazioni.models import BloccoTecnico, Contatto, Pagamento, Prenotazione, Stato
from tana.prenotazioni.services import sincronizza_occupazioni
from tana.prenotazioni.tests.utils import EURO, richiesta, tra, utente_con

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _dati(dati):
    pass


def cliente_di(utente):
    c = Client()
    c.force_login(utente)
    return c


@pytest.fixture
def segreteria():
    return utente_con(Ruolo.SEGRETERIA, "segreteria@example.org")


@pytest.fixture
def prenotazione(richiedente, contatto):
    return richiesta(richiedente, contatto, arrivo=10, partenza=15)


def azione(cliente, p, nome, **dati):
    return cliente.post(reverse("gestione:azione", args=[p.numero, nome]), dati)


# --- Accessi ----------------------------------------------------------------------------


def test_accessi(client, richiedente, pattuglia, admin, segreteria):
    url = reverse("gestione:cruscotto")
    assert client.get(url).status_code == 302
    assert cliente_di(richiedente).get(url).status_code == 403
    for utente in (pattuglia, admin, segreteria):
        assert cliente_di(utente).get(url).status_code == 200
    # Configurazione solo all'amministrazione; ruoli alla segreteria e (in parte) all'amministrazione
    assert cliente_di(pattuglia).get(reverse("gestione:configurazione")).status_code == 403
    assert cliente_di(admin).get(reverse("gestione:utenti")).status_code == 200
    assert cliente_di(pattuglia).get(reverse("gestione:utenti")).status_code == 403
    assert cliente_di(segreteria).get(reverse("gestione:utenti")).status_code == 200
    # Arrivi e partenze solo alla Pattuglia (e all'amministrazione): niente voce alla segreteria
    arrivi = reverse("gestione:arrivi")
    assert cliente_di(segreteria).get(arrivi).status_code == 403
    assert arrivi not in cliente_di(segreteria).get(url).content.decode()
    assert arrivi in cliente_di(pattuglia).get(url).content.decode()
    # Voce «Gestione» nel menu solo a chi la vede
    assert "Gestione" in cliente_di(pattuglia).get(reverse("listino")).content.decode()
    assert ">Gestione<" not in cliente_di(richiedente).get(reverse("listino")).content.decode()


def test_arrivi_solo_prenotazioni_approvate(prenotazione, admin):
    c = cliente_di(admin)
    assert (
        "Avellino 1" not in c.get(reverse("gestione:arrivi"), {"periodo": "mese"}).content.decode()
    )
    flusso.approva(prenotazione, utente=admin)
    assert "Avellino 1" in c.get(reverse("gestione:arrivi"), {"periodo": "mese"}).content.decode()


def test_tutte_le_pagine(prenotazione, admin):
    c = cliente_di(admin)
    for nome in (
        "cruscotto",
        "calendario",
        "arrivi",
        "blocchi",
        "listini",
        "configurazione",
        "statistiche",
        "export",
        "nuova",
    ):
        assert c.get(reverse(f"gestione:{nome}")).status_code == 200, nome
    for elenco in ("da_approvare", "acconti", "consensi", "consuntivi", "messaggi", "tutte"):
        risposta = c.get(reverse("gestione:elenco"), {"elenco": elenco, "q": "Avellino"})
        assert risposta.status_code == 200, elenco
    assert (
        prenotazione.numero
        in c.get(reverse("gestione:elenco"), {"elenco": "da_approvare"}).content.decode()
    )
    pagina = c.get(reverse("gestione:scheda", args=[prenotazione.numero])).content.decode()
    assert "Approvazione" in pagina and "Storico" in pagina
    versione = VersioneListino.objects.first()
    assert c.get(reverse("gestione:versione", args=[versione.pk])).status_code == 200
    assert (
        "Avellino 1"
        in c.get(reverse("gestione:calendario"), {"mese": f"{tra(10):%Y-%m}"}).content.decode()
    )


# --- Azioni dalla scheda ----------------------------------------------------------------


def test_approvazione_e_acconto_dalla_scheda(email, prenotazione, admin, pattuglia, segreteria):
    # La segreteria vede ma non approva
    azione(cliente_di(segreteria), prenotazione, "approva")
    prenotazione.refresh_from_db()
    assert prenotazione.stato == Stato.RICHIESTA
    with email.cattura(execute=True):
        azione(
            cliente_di(admin),
            prenotazione,
            "approva",
            acconto="100,50",
            deciso_da="Pattuglia",
            motivazione="Accordo con il gruppo",
        )
    prenotazione.refresh_from_db()
    assert prenotazione.stato == Stato.APPROVATA and prenotazione.acconto_centesimi == 10050
    flusso.carica_ricevuta(
        prenotazione,
        utente=prenotazione.richiedente,
        ricevuta=ContentFile(b"%PDF", name="r.pdf"),
    )
    pagamento = Pagamento.objects.get()
    azione(cliente_di(pattuglia), prenotazione, "verifica", pagamento=pagamento.pk)
    prenotazione.refresh_from_db()
    assert prenotazione.stato == Stato.CONFERMATA


def test_rifiuto_dalla_scheda(prenotazione, admin):
    c = cliente_di(admin)
    azione(c, prenotazione, "rifiuta", deciso_da="", motivazione="")
    prenotazione.refresh_from_db()
    assert prenotazione.stato == Stato.RICHIESTA
    azione(c, prenotazione, "rifiuta", deciso_da="Pattuglia", motivazione="Base chiusa")
    prenotazione.refresh_from_db()
    assert prenotazione.stato == Stato.RIFIUTATA


def test_modifica_voci_e_messaggi_dalla_scheda(email, prenotazione, admin, pattuglia):
    c = cliente_di(admin)
    azione(
        c,
        prenotazione,
        "modifica",
        arrivo=tra(11).isoformat(),
        partenza=tra(16).isoformat(),
        persone_acc=20,
        motivo="",
    )
    prenotazione.refresh_from_db()
    assert prenotazione.arrivo == tra(11)
    azione(
        c,
        prenotazione,
        "voce",
        fase="PREVENTIVO",
        descrizione="Sovrapprezzo esclusiva",
        quantita=1,
        prezzo="50",
        deciso_da="",
        motivazione="",
    )
    assert prenotazione.righe_importo.filter(
        descrizione="Sovrapprezzo esclusiva", importo_centesimi=50 * EURO
    ).exists()
    azione(
        c,
        prenotazione,
        "quota",
        fase="PREVENTIVO",
        totale="0",
        deciso_da="Responsabile",
        motivazione="Ospiti",
    )
    assert contributo.riepilogo(prenotazione).totale == 0
    with email.cattura(execute=True):
        azione(cliente_di(pattuglia), prenotazione, "rispondi", testo="Benvenuti!")
    assert email.inviate[-1].body.count("Benvenuti!") == 1
    azione(cliente_di(pattuglia), prenotazione, "orari", arrivo="12:30", partenza="")
    prenotazione.refresh_from_db()
    assert prenotazione.orario_arrivo_concordato == datetime.time(12, 30)
    assert (
        cliente_di(admin)
        .post(reverse("gestione:azione", args=[prenotazione.numero, "inesistente"]))
        .status_code
        == 404
    )


def test_consuntivo_e_chiusura(email, prenotazione, admin, pattuglia):
    flusso.approva(prenotazione, utente=admin)
    flusso.registra_pagamento(
        prenotazione,
        utente=pattuglia,
        tipo="ACCONTO",
        importo_centesimi=prenotazione.acconto_centesimi,
        data=tra(0),
    )
    Prenotazione.objects.filter(pk=prenotazione.pk).update(stato=Stato.SVOLTA)
    c = cliente_di(pattuglia)
    url = reverse("gestione:consuntivo", args=[prenotazione.numero])
    assert c.get(url).status_code == 200
    assert not prenotazione.righe_importo.filter(fase="CONSUNTIVO").exists()  # la GET non scrive
    c.post(url, {"area_ACC": 26})
    consuntivo = contributo.riepilogo(prenotazione, contributo.Fase.CONSUNTIVO)
    assert consuntivo.righe[0].persone == 26
    with email.cattura(execute=True):
        c.post(reverse("gestione:chiudi", args=[prenotazione.numero]))
    prenotazione.refresh_from_db()
    assert prenotazione.stato == Stato.CHIUSA
    assert "Saldo" in email.inviate[0].body


def test_prenotazione_per_la_gestione(admin):
    c = cliente_di(admin)
    dati = {
        "categoria": Categoria.objects.get(codice="foca-regionale").pk,
        "gruppo": "CFT regionale",
        "arrivo": tra(500).isoformat(),
        "partenza": tra(505).isoformat(),
        "persone_acc": 40,
        "deciso_da": "Pattuglia e IRO",
        "motivazione": "Date del CFT",
    }
    c.post(reverse("gestione:nuova"), dati)
    p = Prenotazione.objects.get()
    assert p.richiedente is None and p.categoria_prioritaria_concessa  # oltre l'orizzonte


# --- Configurazione ---------------------------------------------------------------------


def test_blocchi_e_configurazione(admin):
    c = cliente_di(admin)
    c.post(
        reverse("gestione:blocchi"),
        {
            "area": Area.objects.get(codice="ACC").pk,
            "dal": tra(20).isoformat(),
            "al": tra(21).isoformat(),
            "motivo": "Potatura",
        },
    )
    blocco = BloccoTecnico.objects.get()
    c.post(reverse("gestione:blocchi"), {"elimina": blocco.pk})
    assert not BloccoTecnico.objects.exists()
    risposta = c.get(reverse("gestione:configurazione"))
    pagina = risposta.content.decode()
    assert 'class="menu-item selected" type="button" role="option" data-bs-value="11"' in pagina
    assert '<span class="form-adorn-text" aria-hidden="true">%</span>' in pagina
    form = risposta.context["form"]
    dati = {k: v for k, v in form.initial.items() if v is not None}
    dati.update(iban="IT60X0542811101000000123456", acconto_percentuale=40, inverno_al_mese=4)
    c.post(reverse("gestione:configurazione"), dati)
    assert Configurazione.corrente().acconto_percentuale == 40
    assert Configurazione.corrente().inverno_al_mese == 4


def test_versioni_di_listino(admin, prenotazione):
    c = cliente_di(admin)
    corrente = VersioneListino.objects.get(listino__tipo="ASSOCIATIVO")
    c.post(
        reverse("gestione:listini"),
        {
            "listino": corrente.listino_id,
            "nome": "2028",
            "pubblicata_il": tra(0).isoformat(),
            "valida_dal": tra(60).isoformat(),
            "copia_da": corrente.pk,
        },
    )
    nuova = VersioneListino.objects.get(nome="2028")
    assert nuova.voci.count() == corrente.voci.count()
    pagina = c.get(reverse("gestione:versione", args=[corrente.pk]))
    assert pagina.context["in_uso"]  # usata dalla prenotazione


def test_ruoli_dalla_segreteria(segreteria):
    utente = User.objects.create_user("capo@example.org")
    c = cliente_di(segreteria)
    c.post(reverse("gestione:utenti"), {"email": "CAPO@example.org", "ruolo": Ruolo.PATTUGLIA})
    nomina_ = Nomina.objects.get(utente=utente)
    assert nomina_.assegnata_da == segreteria
    c.post(reverse("gestione:utenti"), {"revoca": nomina_.pk})
    assert not Nomina.objects.filter(utente=utente, attiva=True).exists()
    # Email sconosciuta: account pre-registrato senza password, con il ruolo già assegnato
    risposta = c.post(
        reverse("gestione:utenti"), {"email": "Nuovo@Example.org", "ruolo": Ruolo.REDAZIONE}
    )
    assert risposta.status_code == 302
    nuovo = User.objects.get(email__iexact="nuovo@example.org")
    assert not nuovo.has_usable_password()
    assert Nomina.objects.get(utente=nuovo, attiva=True).ruolo == Ruolo.REDAZIONE
    # Più ruoli: una sola riga per l'utente
    nomina(utente, Ruolo.PATTUGLIA)
    nomina(utente, Ruolo.REDAZIONE)
    pagina = c.get(reverse("gestione:utenti")).content.decode()
    assert pagina.count("<td>capo@example.org ") == 1
    assert "Pattuglia" in pagina and "Redazione" in pagina
    # Mai entrati con Sestante: capo, nuovo e (nel test) la segreteria
    assert pagina.count("in attesa del primo accesso con Sestante") == 3


# --- Report -----------------------------------------------------------------------------


@pytest.fixture
def anno_svolto(richiedente, contatto, admin, pattuglia):
    """Una prenotazione svolta e una del Comune nel 2027, con pagamenti."""
    p = richiesta(richiedente, contatto, arrivo=10, partenza=15)
    comune = richiesta(
        admin,
        None,
        arrivo=30,
        partenza=38,
        categoria="comune",
        da_gestione=True,
        deciso_da="P",
        motivazione="Comodato",
    )
    for q, giorni in (
        (p, (datetime.date(2027, 7, 19), datetime.date(2027, 7, 24))),
        (comune, (datetime.date(2027, 8, 1), datetime.date(2027, 8, 9))),
    ):
        Prenotazione.objects.filter(pk=q.pk).update(arrivo=giorni[0], partenza=giorni[1])
        q.refresh_from_db()
        sincronizza_occupazioni(q)
        contributo.aggiorna_preventivo(q)
        Prenotazione.objects.filter(pk=q.pk).update(stato=Stato.SVOLTA)
    Pagamento.objects.create(
        prenotazione=p, tipo="ACCONTO", importo_centesimi=672 * EURO, data=datetime.date(2027, 5, 2)
    )
    return p, comune


def test_statistiche(anno_svolto, admin):
    s = statistiche.calcola(2027)
    righe = {r.categoria.codice: r for r in s.categorie}
    agesci = righe["gruppo-agesci"]
    assert agesci.prenotazioni == 1 and agesci.presenze == {"Accantonamento": 28 * 6}
    assert agesci.importi == 1344 * EURO and agesci.incassi == 672 * EURO
    assert s.giorni_comune == 9  # oltre la settimana del comodato
    notti_per_mese = {m: n for m, n, _ in s.occupazione["Accantonamento"]}
    assert notti_per_mese["lug"] == 5 and notti_per_mese["ago"] == 8
    pagina = cliente_di(admin).get(reverse("gestione:statistiche"), {"anno": 2027}).content.decode()
    assert "oltre la settimana annua" in pagina and "1.344,00 €" in pagina


def test_grafici_delle_statistiche(anno_svolto, admin):
    svolta, _ = anno_svolto
    svolta.presenze.update(persone_effettive=20)
    s = statistiche.calcola(2027)
    mensili = {m: (p, e) for m, p, e in s.presenze_mensili}
    # 19-24 luglio (6 giorni) con 28 previste e 20 effettive; Comune 1-9 agosto senza consuntivo
    assert mensili["lug"] == (28 * 6, 20 * 6)
    assert mensili["ago"] == (28 * 9, 0)
    pagina = cliente_di(admin).get(reverse("gestione:statistiche"), {"anno": 2027}).content.decode()
    assert pagina.count('<svg class="tana-grafico"') == 3  # presenze + una per area
    assert "lug · previste: 168" in pagina and "lug · effettive: 120" in pagina
    assert "ago · occupazione: 26%" in pagina  # 8 notti su 31


def test_export(anno_svolto, admin):
    c = cliente_di(admin)
    risposta = c.get(
        reverse("gestione:export"),
        {"dal": "2027-01-01", "al": "2027-12-31", "contenuto": "prenotazioni", "formato": "xlsx"},
    )
    assert risposta["Content-Disposition"].endswith('.xlsx"')
    foglio = load_workbook(io.BytesIO(risposta.content)).active
    righe = list(foglio.iter_rows(values_only=True))
    assert righe[0][0] == "Numero" and len(righe) == 3
    assert righe[1][8] == 1344  # preventivo in euro
    risposta = c.get(
        reverse("gestione:export"),
        {"dal": "2027-01-01", "al": "2027-12-31", "contenuto": "incassi", "formato": "csv"},
    )
    testo = risposta.content.decode("utf-8-sig")
    (intestazione, riga) = list(csv.reader(io.StringIO(testo), delimiter=";"))
    assert riga[0] == "02/05/2027" and riga[-1] == "672,00"


def test_menu_a_sezioni(prenotazione, admin, pattuglia):
    pagina = cliente_di(admin).get(reverse("gestione:statistiche")).content.decode()
    assert pagina.count('name="tana-menu"') == 3
    assert pagina.count('name="tana-menu" open') == 1
    assert 'name="tana-menu" open>\n        <summary class="tana-sidebar__sezione">Report' in pagina
    elenco = reverse("gestione:elenco") + "?elenco=da_approvare"
    pagina = cliente_di(pattuglia).get(elenco).content.decode()
    assert pagina.count('name="tana-menu"') == 2  # niente Configurazione per la Pattuglia
    assert f'active" href="{elenco}"' in pagina


def test_link_al_manuale(admin, client):
    # Nel footer per tutti, anche senza accesso, e nel menu della gestione
    url = settings.MANUALE_URL
    assert f'href="{url}"' in client.get(reverse("listino")).content.decode()
    pagina = cliente_di(admin).get(reverse("gestione:statistiche")).content.decode()
    assert pagina.count(f'href="{url}"') == 2


def test_correzione_di_una_versione(prenotazione, admin):
    c = cliente_di(admin)
    usata = prenotazione.versione_listino
    nuova = VersioneListino.objects.create(
        listino=usata.listino,
        nome="2099",
        pubblicata_il=datetime.date(2099, 9, 1),
        valida_dal=datetime.date(2099, 1, 1),
    )
    url = reverse("gestione:versione", args=[nuova.pk])
    dati = {"azione": "dati", "nome": "2100", "pubblicata_il": "2099-09-01"}
    # Validità prima della pubblicazione: rifiutata
    c.post(url, {**dati, "valida_dal": "2099-01-01"})
    nuova.refresh_from_db()
    assert nuova.nome == "2099"
    assert c.post(url, {**dati, "valida_dal": "2100-01-01"}).status_code == 302
    nuova.refresh_from_db()
    assert (nuova.nome, nuova.valida_dal) == ("2100", datetime.date(2100, 1, 1))
    c.post(url, {"azione": "elimina"})
    assert not VersioneListino.objects.filter(pk=nuova.pk).exists()
    # Una versione usata non si corregge né si elimina
    url = reverse("gestione:versione", args=[usata.pk])
    assert "Salva nome e date" not in c.get(url).content.decode()
    c.post(url, {**dati, "valida_dal": "2100-01-01"})
    c.post(url, {"azione": "elimina"})
    usata.refresh_from_db()
    assert usata.nome != "2100"


def test_modalita_demo_dalla_configurazione(admin, pattuglia, richiedente, contatto):
    url = reverse("gestione:demo")
    c = cliente_di(admin)
    assert cliente_di(pattuglia).post(url, {"azione": "attiva"}).status_code == 403
    c.post(url, {"azione": "attiva"})
    assert Configurazione.corrente().modalita_demo
    assert "Modalità demo:" in c.get(reverse("gestione:cruscotto")).content.decode()
    pagina = cliente_di(richiedente).get(reverse("prenotazioni:nuova")).content.decode()
    assert "versione di prova" in pagina
    richiesta(pattuglia, contatto)
    # Senza conferma non si cancella niente
    c.post(url, {"azione": "termina"})
    assert Prenotazione.objects.exists()
    c.post(url, {"azione": "termina", "conferma": "1"})
    assert not Prenotazione.objects.exists()
    assert not Configurazione.corrente().modalita_demo
    # Con prenotazioni la demo non è attivabile: il riquadro non c'è (il contatto di prima
    # è stato cancellato con la demo)
    richiesta(richiedente, Contatto.objects.create(nome="Referente", email="r@example.org"))
    assert "Modalità demo" not in c.get(reverse("gestione:configurazione")).content.decode()


def test_link_nel_messaggio_di_blocco(richiedente):
    Configurazione.objects.filter(pk=1).update(
        prenotazioni_bloccate=True, messaggio_blocco="Dettagli su https://example.org/avviso"
    )
    pagina = cliente_di(richiedente).get(reverse("prenotazioni:nuova")).content.decode()
    assert '<a href="https://example.org/avviso"' in pagina


def test_categorie(prenotazione, admin, pattuglia):
    url = reverse("gestione:categorie")
    assert cliente_di(pattuglia).get(url).status_code == 403
    c = cliente_di(admin)
    listino = prenotazione.categoria.listino_default
    risposta = c.post(
        url, {"nome": "Scuola", "codice": "scuola", "listino_default": listino.pk, "ordine": 9}
    )
    assert risposta.status_code == 302
    nuova = Categoria.objects.get(codice="scuola")
    scheda = reverse("gestione:categoria", args=[nuova.pk])
    # Il codice non cambia dopo la creazione
    dati = {"nome": "Scuole", "codice": "altro", "listino_default": listino.pk, "ordine": 9}
    assert c.post(scheda, dati).status_code == 302
    nuova.refresh_from_db()
    assert (nuova.nome, nuova.codice) == ("Scuole", "scuola")
    assert "Categorie" in c.get(url).content.decode()
    c.post(scheda, {"elimina": "1"})
    assert not Categoria.objects.filter(pk=nuova.pk).exists()
    # Una categoria usata non si elimina
    usata = reverse("gestione:categoria", args=[prenotazione.categoria.pk])
    c.post(usata, {"elimina": "1"})
    assert Categoria.objects.filter(pk=prenotazione.categoria.pk).exists()


def test_moduli_con_le_prenotazioni_bloccate(admin, richiedente):
    Configurazione.objects.filter(pk=1).update(
        prenotazioni_bloccate=True, messaggio_blocco="Prenotazioni chiuse per prova."
    )
    pagina = cliente_di(richiedente).get(reverse("prenotazioni:nuova")).content.decode()
    assert "Prenotazioni chiuse per prova." in pagina
    assert "<form" not in pagina.split("<h1>", 1)[1].split("</main>", 1)[0]
    pagina = cliente_di(admin).get(reverse("gestione:nuova")).content.decode()
    assert "Prenotazioni chiuse per prova." in pagina
    assert 'name="motivazione"' not in pagina
    pagina = cliente_di(admin).get(reverse("gestione:configurazione")).content.decode()
    assert pagina.index('name="prenotazioni_bloccate"') < pagina.index("Stagione invernale")
