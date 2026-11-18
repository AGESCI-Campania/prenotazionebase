import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import authenticate
from django.urls import reverse

from tana.accounts.models import Ruolo, User
from tana.accounts.services import nomina

pytestmark = pytest.mark.django_db

PASSWORD = "UnaPasswordLunga!42"
MESSAGGIO = "entra con «SSO AGESCI Campania»"


def utente_con_password(email, ruolo=None):
    utente = User.objects.create_user(email, PASSWORD)
    EmailAddress.objects.create(user=utente, email=email, verified=True, primary=True)
    if ruolo:
        nomina(utente, ruolo)
    return utente


def accedi(client, email, password=PASSWORD):
    return client.post(reverse("account_login"), {"login": email, "password": password})


@pytest.mark.parametrize("ruolo", [Ruolo.PATTUGLIA, Ruolo.AMMINISTRATORE, Ruolo.REDAZIONE])
def test_gestione_mai_con_password(client, ruolo):
    utente_con_password("capo@example.org", ruolo)
    risposta = accedi(client, "capo@example.org")
    assert risposta.status_code == 200 and MESSAGGIO in risposta.content.decode()
    assert "_auth_user_id" not in client.session
    # Anche fuori da allauth (admin, login dell'editor del sito)
    assert authenticate(None, username="capo@example.org", password=PASSWORD) is None
    assert authenticate(None, email="capo@example.org", password=PASSWORD) is None


def test_password_sbagliata_non_rivela_il_ruolo(client):
    utente_con_password("capo@example.org", Ruolo.PATTUGLIA)
    risposta = accedi(client, "capo@example.org", "sbagliata")
    assert MESSAGGIO not in risposta.content.decode()


def test_richiedente_e_superutente_con_password(client):
    utente_con_password("gruppo@example.org")
    assert accedi(client, "gruppo@example.org").status_code == 302
    assert "_auth_user_id" in client.session
    User.objects.create_superuser("tecnico@example.org", PASSWORD)
    assert authenticate(None, username="tecnico@example.org", password=PASSWORD) is not None


def test_sessione_sestante_resta_valida(client):
    # Il login SSO non passa da authenticate: la sessione aperta col backend resta valida
    utente = utente_con_password("capo@example.org", Ruolo.PATTUGLIA)
    client.force_login(utente, backend="tana.accounts.backends.TanaAllauthBackend")
    assert client.get(reverse("gestione:cruscotto")).status_code == 200


def test_ruolo_revocato_torna_la_password(client):
    from tana.accounts.services import revoca

    utente = utente_con_password("capo@example.org", Ruolo.PATTUGLIA)
    revoca(utente, Ruolo.PATTUGLIA)
    assert accedi(client, "capo@example.org").status_code == 302
