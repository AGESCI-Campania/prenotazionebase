import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from tana.accounts.models import User
from tana.listini.models import Categoria
from tana.prenotazioni import flusso
from tana.prenotazioni.models import Messaggio, Pagamento, Prenotazione, Stato

from .utils import richiesta, tra

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _dati(dati):
    pass


@pytest.fixture
def cliente(richiedente):
    """Client del richiedente, separato da `client` (usato per gli altri utenti)."""
    c = Client()
    c.force_login(richiedente)
    return c


def data(giorni):
    return tra(giorni).isoformat()


PASSO_1 = {
    "gruppo": "Avellino 1",
    "unita": ["EG", "RS"],
    "referente_nome": "Mario Rossi",
    "referente_email": "mario@example.org",
    "referente_telefono": "3331234567",
    "capo_nome": "Lucia Verdi",
    "capo_telefono": "3339876543",
}


def passo_1(cliente, **extra):
    dati = {**PASSO_1, "categoria": Categoria.objects.get(codice="gruppo-agesci").pk, **extra}
    return cliente.post(reverse("prenotazioni:nuova"), dati)


# --- Pagine pubbliche -------------------------------------------------------------------


def test_pagine_pubbliche(client, richiedente, contatto):
    richiesta(richiedente, contatto)
    calendario = client.get(reverse("disponibilita"), {"mese": f"{tra(10):%Y-%m}"})
    assert calendario.status_code == 200
    html = calendario.content.decode()
    assert "tana-occupato" in html and "Avellino 1" not in html  # niente nomi (D-17)
    assert client.get(reverse("disponibilita"), {"mese": "non-valido"}).status_code == 200
    listino = client.get(reverse("listino")).content.decode()
    assert "Campo estivo in accantonamento" in listino and "8,00 €" in listino
    assert "Pernotto extra associativo" in listino


def test_area_personale_solo_con_login(client):
    risposta = client.get(reverse("prenotazioni:elenco"))
    assert risposta.status_code == 302 and "/accounts/login/" in risposta["Location"]


# --- Nuova richiesta --------------------------------------------------------------------


def test_richiesta_in_tre_passi(
    cliente, richiedente, mailoutbox, django_capture_on_commit_callbacks
):
    risposta = passo_1(cliente)
    assert risposta["Location"] == reverse("prenotazioni:nuova_passo", kwargs={"passo": 2})
    soggiorno = {
        "tipo": "CONGIUNTA",
        "arrivo": data(30),
        "partenza": data(35),
        "persone_acc": 20,
        "persone_tende": 12,
        "ospiti_data": data(32),
        "ospiti_persone": 40,
    }
    anteprima = cliente.post(reverse("prenotazioni:anteprima"), soggiorno).content.decode()
    assert "Totale stimato" in anteprima and "Accantonamento libera" in anteprima
    risposta = cliente.post(reverse("prenotazioni:nuova_passo", kwargs={"passo": 2}), soggiorno)
    assert risposta["Location"] == reverse("prenotazioni:nuova_passo", kwargs={"passo": 3})
    riepilogo = cliente.get(risposta["Location"]).content.decode()
    assert "Lucia Verdi" in riepilogo and "Totale stimato" in riepilogo
    # Senza accettare il regolamento non si invia
    assert cliente.post(risposta["Location"], {}).status_code == 200
    with django_capture_on_commit_callbacks(execute=True):
        risposta = cliente.post(
            risposta["Location"], {"accetto": "on", "note": "Arriviamo alle 16"}
        )
    prenotazione = Prenotazione.objects.get()
    assert risposta["Location"] == reverse("prenotazioni:dettaglio", args=[prenotazione.numero])
    assert prenotazione.richiedente == richiedente
    assert prenotazione.stato == Stato.RICHIESTA
    assert prenotazione.unita == ["EG", "RS"]
    assert prenotazione.capo_responsabile.nome == "Lucia Verdi"
    assert prenotazione.contatto.telefono == "3331234567"
    assert {p.area.codice: p.persone_previste for p in prenotazione.presenze.all()} == {
        "ACC": 20,
        "TENDE": 12,
    }
    assert prenotazione.attivita_giornaliere.get().persone_previste == 40
    assert len(mailoutbox) == 2
    assert reverse("prenotazioni:dettaglio", args=[prenotazione.numero]) in mailoutbox[0].body
    # La sessione del modulo si svuota
    assert cliente.get(reverse("prenotazioni:nuova_passo", kwargs={"passo": 3})).status_code == 302


@pytest.mark.parametrize(
    ("soggiorno", "errore"),
    [
        (
            {"tipo": "TENDE", "arrivo": data(30), "partenza": data(30), "persone_tende": 5},
            "partenza",
        ),
        ({"tipo": "ACC", "arrivo": data(30), "partenza": data(33)}, "persone_acc"),
        ({"tipo": "BIVACCO", "arrivo": data(30), "persone_acc": 10}, "area_bivacco"),
        ({"tipo": "USCITA", "arrivo": data(30), "persone_uscita": 10}, "tipo_uscita"),
        (
            {
                "tipo": "CONGIUNTA",
                "arrivo": data(30),
                "partenza": data(33),
                "persone_acc": 5,
                "persone_tende": 5,
                "esclusiva_richiesta": "on",
            },
            "esclusiva_richiesta",
        ),
    ],
)
def test_errori_del_soggiorno(cliente, soggiorno, errore):
    passo_1(cliente)
    risposta = cliente.post(reverse("prenotazioni:nuova_passo", kwargs={"passo": 2}), soggiorno)
    assert risposta.status_code == 200
    assert errore in risposta.context["form"].errors


def test_bivacco_e_uscita(cliente):
    passo_1(cliente)
    url = reverse("prenotazioni:nuova_passo", kwargs={"passo": 2})
    cliente.post(
        url, {"tipo": "BIVACCO", "arrivo": data(30), "area_bivacco": "ACC", "persone_acc": 15}
    )
    cliente.post(reverse("prenotazioni:nuova_passo", kwargs={"passo": 3}), {"accetto": "on"})
    bivacco = Prenotazione.objects.get()
    assert (bivacco.partenza - bivacco.arrivo).days == 1
    passo_1(cliente)
    cliente.post(
        url,
        {
            "tipo": "USCITA",
            "arrivo": data(40),
            "tipo_uscita": "USCITA_AREA_VERDE",
            "persone_uscita": 25,
        },
    )
    cliente.post(reverse("prenotazioni:nuova_passo", kwargs={"passo": 3}), {"accetto": "on"})
    uscita = Prenotazione.objects.exclude(pk=bivacco.pk).get()
    assert uscita.arrivo == uscita.partenza and not uscita.presenze.exists()


def test_specifica_obbligatoria(cliente):
    risposta = passo_1(cliente, categoria=Categoria.objects.get(codice="altro").pk)
    assert "specifica_categoria" in risposta.context["form"].errors


def test_passi_in_ordine(cliente):
    assert cliente.get(reverse("prenotazioni:nuova_passo", kwargs={"passo": 3})).status_code == 302


def test_date_occupate_non_si_inviano(cliente, richiedente, contatto):
    richiesta(richiedente, contatto, arrivo=30, partenza=35)
    passo_1(cliente)
    cliente.post(
        reverse("prenotazioni:nuova_passo", kwargs={"passo": 2}),
        {"tipo": "ACC", "arrivo": data(32), "partenza": data(34), "persone_acc": 10},
    )
    url = reverse("prenotazioni:nuova_passo", kwargs={"passo": 3})
    assert "Accantonamento occupata" in cliente.get(url).content.decode()
    risposta = cliente.post(url, {"accetto": "on"})
    assert risposta.status_code == 200
    assert Prenotazione.objects.count() == 1


# --- Area personale ---------------------------------------------------------------------


def test_dettaglio_solo_del_titolare(cliente, client, richiedente, contatto):
    prenotazione = richiesta(richiedente, contatto)
    url = reverse("prenotazioni:dettaglio", args=[prenotazione.numero])
    pagina = cliente.get(url).content.decode()
    assert prenotazione.numero in pagina and "Le date sono riservate a te" in pagina
    assert prenotazione.numero in cliente.get(reverse("prenotazioni:elenco")).content.decode()
    altro = User.objects.create_user("altro@example.org")
    client.force_login(altro)
    assert client.get(url).status_code == 404


def test_ricevuta_dall_area_personale(
    cliente, client, richiedente, contatto, admin, pattuglia, settings
):
    prenotazione = richiesta(richiedente, contatto)
    flusso.approva(prenotazione, utente=admin)
    pagina = cliente.get(
        reverse("prenotazioni:dettaglio", args=[prenotazione.numero])
    ).content.decode()
    assert "IBAN <b>IT00X0000</b>" in pagina
    assert f"Acconto prenotazione {prenotazione.numero} - Avellino 1" in pagina
    url = reverse("prenotazioni:carica_ricevuta", args=[prenotazione.numero])
    errata = SimpleUploadedFile("ricevuta.exe", b"MZ")
    cliente.post(url, {"ricevuta": errata})
    assert not Pagamento.objects.exists()
    cliente.post(url, {"ricevuta": SimpleUploadedFile("bonifico.pdf", b"%PDF-1.4")})
    pagamento = Pagamento.objects.get()
    download = reverse("prenotazioni:ricevuta", args=[prenotazione.numero, pagamento.pk])
    risposta = cliente.get(download)
    assert risposta.status_code == 200 and b"".join(risposta.streaming_content) == b"%PDF-1.4"
    # Altri utenti: 404; Pattuglia: sì; in produzione la serve nginx
    client.force_login(User.objects.create_user("altro@example.org"))
    assert client.get(download).status_code == 404
    client.force_login(pattuglia)
    settings.PRIVATI_X_ACCEL = True
    risposta = client.get(download)
    assert risposta["X-Accel-Redirect"] == f"/protetti/{pagamento.ricevuta.name}"
    assert risposta["Content-Type"] == "application/pdf"
    assert risposta.content == b""


def test_annulla_dall_area_personale(cliente, richiedente, contatto):
    prenotazione = richiesta(richiedente, contatto)
    cliente.post(
        reverse("prenotazioni:annulla", args=[prenotazione.numero]), {"motivo": "Campo spostato"}
    )
    prenotazione.refresh_from_db()
    assert prenotazione.stato == Stato.ANNULLATA
    assert (
        cliente.get(reverse("prenotazioni:annulla", args=[prenotazione.numero])).status_code == 405
    )


def test_messaggi_dall_area_personale(cliente, richiedente, contatto):
    prenotazione = richiesta(richiedente, contatto)
    altro = User.objects.create_user("altro@example.org")
    vicino = richiesta(altro, contatto, arrivo=15, partenza=18, gruppo="Salerno 3")
    url = reverse("prenotazioni:scrivi", args=[prenotazione.numero])
    cliente.post(url, {"con": "gestione", "testo": "Domanda per la Pattuglia"})
    cliente.post(url, {"con": vicino.numero, "testo": "Ciao Salerno 3"})
    assert Messaggio.objects.count() == 2
    pagina = cliente.get(
        reverse("prenotazioni:dettaglio", args=[prenotazione.numero]), {"con": vicino.numero}
    ).content.decode()
    assert "Ciao Salerno 3" in pagina and "Domanda per la Pattuglia" not in pagina
    lontano = richiesta(altro, contatto, arrivo=40, partenza=42)
    cliente.post(url, {"con": lontano.numero, "testo": "Non dovrei poter scrivere"})
    assert Messaggio.objects.count() == 2


def test_consenso_dall_area_personale(cliente, client, richiedente, contatto):
    soggiorno = richiesta(richiedente, contatto)
    altro = User.objects.create_user("altro@example.org")
    uscita = richiesta(
        altro,
        contatto,
        arrivo=12,
        partenza=12,
        presenze={},
        attivita=[(tra(12), "USCITA_CUCINA", 20)],
    )
    domanda = uscita.consensi_chiesti.get()
    assert (
        "Altri gruppi chiedono il tuo consenso"
        in cliente.get(reverse("prenotazioni:elenco")).content.decode()
    )
    client.force_login(altro)
    url = reverse("prenotazioni:rispondi_consenso", args=[domanda.pk])
    assert client.post(url, {"concesso": "1"}).status_code == 404
    risposta = cliente.post(url, {"concesso": "1"})
    assert risposta["Location"] == reverse("prenotazioni:dettaglio", args=[soggiorno.numero])
    domanda.refresh_from_db()
    assert domanda.stato == "CONCESSO"


def test_telefono_dall_area_personale(cliente, client, richiedente, contatto):
    prenotazione = richiesta(richiedente, contatto)
    altro = User.objects.create_user("altro@example.org")
    vicino = richiesta(altro, contatto, arrivo=15, partenza=18)
    client.force_login(altro)
    client.post(reverse("prenotazioni:chiedi_telefono", args=[vicino.numero, prenotazione.numero]))
    domanda = vicino.telefoni_chiesti.get()
    pagina = cliente.get(
        reverse("prenotazioni:dettaglio", args=[prenotazione.numero])
    ).content.decode()
    assert "chiede di vedere il tuo telefono" in pagina
    cliente.post(reverse("prenotazioni:rispondi_telefono", args=[domanda.pk]), {"autorizza": "1"})
    pagina = client.get(reverse("prenotazioni:dettaglio", args=[vicino.numero])).content.decode()
    assert "tel:3331234567" in pagina
