"""Richieste senza account con la conferma dell'email (D-33)."""

import datetime
import re

import pytest
from allauth.account.models import EmailAddress
from django.urls import reverse

from tana.accounts.models import Ruolo, User
from tana.base.models import Configurazione
from tana.prenotazioni import demo, richieste_da_confermare
from tana.prenotazioni.models import Prenotazione, RichiestaDaConfermare, Stato
from tana.prenotazioni.tests.test_area_richiedente import data, passo_1

from .utils import utente_con

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _dati(dati):
    pass


def non_sono_un_robot(client) -> str:
    """Risolve la sfida ALTCHA come farebbe il widget nel browser."""
    from altcha import Challenge, Payload, solve_challenge

    sfida = Challenge.from_dict(client.get(reverse("prenotazioni:sfida")).json())
    soluzione = solve_challenge(sfida)
    assert soluzione is not None
    return Payload(sfida, soluzione).to_base64()


def compila(client, email="mario@example.org", robot=False):
    """I tre passi da anonimo, fino all'invio (che manda il link)."""
    passo_1(client, referente_email=email)
    soggiorno = {"tipo": "ACC", "arrivo": data(30), "partenza": data(33), "persone_acc": 20}
    client.post(reverse("prenotazioni:nuova_passo", kwargs={"passo": 2}), soggiorno)
    invio = {"accetto": "on"} if robot else {"accetto": "on", "altcha": non_sono_un_robot(client)}
    return client.post(reverse("prenotazioni:nuova_passo", kwargs={"passo": 3}), invio)


def link(email) -> str:
    trovato = re.search(r"https?://\S+/prenotazioni/conferma/\S+/", email.body)
    assert trovato
    return trovato[0]


def test_richiesta_confermata_con_il_link(client, mailoutbox, django_capture_on_commit_callbacks):
    assert client.get(reverse("prenotazioni:nuova")).status_code == 200  # niente login
    with django_capture_on_commit_callbacks(execute=True):
        risposta = compila(client)
    assert "Controlla la tua email" in risposta.content.decode()
    assert not Prenotazione.objects.exists()  # le date non sono ancora riservate
    (email,) = mailoutbox
    assert email.to == ["mario@example.org"] and "Conferma la richiesta" in email.body
    percorso = link(email).split("://", 1)[1].split("/", 1)[1]
    # Aprire il link non conferma (i controlli della posta aprono i link da soli)
    pagina = client.get("/" + percorso).content.decode()
    assert "Conferma la richiesta" in pagina and not Prenotazione.objects.exists()
    with django_capture_on_commit_callbacks(execute=True):
        risposta = client.post("/" + percorso)
    prenotazione = Prenotazione.objects.get()
    utente = User.objects.get(email="mario@example.org")
    assert prenotazione.richiedente == utente and prenotazione.stato == Stato.RICHIESTA
    assert not utente.has_usable_password()
    assert EmailAddress.objects.get(user=utente).verified
    assert risposta["Location"] == reverse("prenotazioni:dettaglio", args=[prenotazione.numero])
    assert client.get(risposta["Location"]).status_code == 200  # accesso fatto
    # Il link vale una volta sola
    client.logout()
    client.post("/" + percorso)
    assert Prenotazione.objects.count() == 1
    assert "non è valido" in client.get("/" + percorso).content.decode()


def test_account_esistente_con_ruolo_senza_accesso_automatico(
    client, mailoutbox, django_capture_on_commit_callbacks
):
    capo = utente_con(Ruolo.PATTUGLIA, "capo@example.org")
    with django_capture_on_commit_callbacks(execute=True):
        compila(client, email="Capo@example.org")
    risposta = client.post(link(mailoutbox[0]).split(":8000", 1)[-1].split("testserver", 1)[-1])
    assert Prenotazione.objects.get().richiedente == capo
    assert risposta["Location"] == reverse("account_login")  # entra con SSO o password


def test_link_scaduto_e_pulizia(client, mailoutbox, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        compila(client)
    RichiestaDaConfermare.objects.update(
        creata_il=datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=25)
    )
    richiesta = RichiestaDaConfermare.objects.get()
    assert richieste_da_confermare.valida(richiesta.token) is None
    assert richieste_da_confermare.pulisci() == 1


def test_massimo_tre_richieste_da_confermare(client):
    for _ in range(3):
        richieste_da_confermare.crea("mario@example.org", {"1": {}, "2": {}, "note": ""})
    risposta = compila(client)
    assert risposta.status_code == 302 and RichiestaDaConfermare.objects.count() == 3


def test_in_demo_niente_richieste_e_link_per_prenotare_davvero(client):
    admin = utente_con(Ruolo.AMMINISTRATORE, "admin@example.org")
    demo.attiva(utente=admin)
    Configurazione.objects.filter(pk=1).update(
        link_prenotazioni_vere="https://www.baseaiello.agescicampania.net/prenotazioni"
    )
    pagina = client.get(reverse("prenotazioni:nuova")).content.decode()
    assert "le prenotazioni inserite qui non sono valide" in pagina
    assert 'href="https://www.baseaiello.agescicampania.net/prenotazioni"' in pagina
    assert "versione di prova" in client.get(reverse("account_signup")).content.decode()


def test_senza_non_sono_un_robot_niente_email(
    client, mailoutbox, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        risposta = compila(client, robot=True)
    assert risposta.status_code == 302 and not mailoutbox
    assert not RichiestaDaConfermare.objects.exists()
    # Una soluzione vale una volta sola
    soluzione = non_sono_un_robot(client)
    from tana.prenotazioni import verifica_umana

    assert verifica_umana.verifica(soluzione) and not verifica_umana.verifica(soluzione)
    assert not verifica_umana.verifica("non-valida")
