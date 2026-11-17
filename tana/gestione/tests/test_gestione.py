import csv
import datetime
import io

import pytest
from django.core.files.base import ContentFile
from django.test import Client
from django.urls import reverse
from openpyxl import load_workbook

from tana.accounts.models import Nomina, Ruolo, User
from tana.base.models import Area, Configurazione
from tana.gestione import statistiche
from tana.listini.models import Categoria, VersioneListino
from tana.prenotazioni import contributo, flusso
from tana.prenotazioni.models import BloccoTecnico, Pagamento, Prenotazione, Stato
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
    # Configurazione solo all'amministrazione, ruoli solo alla segreteria
    assert cliente_di(pattuglia).get(reverse("gestione:configurazione")).status_code == 403
    assert cliente_di(admin).get(reverse("gestione:utenti")).status_code == 403
    assert cliente_di(segreteria).get(reverse("gestione:utenti")).status_code == 200
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
    c.post(reverse("gestione:utenti"), {"email": "nessuno@example.org", "ruolo": Ruolo.PATTUGLIA})
    assert Nomina.objects.filter(attiva=True).count() == 1  # solo quella della segreteria


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
