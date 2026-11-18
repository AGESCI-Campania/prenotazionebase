import uuid

import pytest
from allauth.account.models import EmailAddress
from allauth.account.utils import has_verified_email
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.mfa.models import Authenticator
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory
from django.utils import timezone

from tana.accounts import permessi
from tana.accounts.adapters import (
    TanaMFAAdapter,
    TanaSocialAccountAdapter,
    sessione_da_sestante,
)
from tana.accounts.models import InvitoSestante, Nomina, Ruolo, User
from tana.accounts.services import (
    allinea_ruoli_globali,
    nomina,
    nomina_per_email,
    revoca,
    ruoli_attivi,
)

pytestmark = pytest.mark.django_db

SESSIONE_SESTANTE = [{"method": "socialaccount", "provider": "sestante", "uid": "x", "at": 1}]
PROVIDER_SESTANTE = {
    "openid_connect": {
        "APPS": [
            {
                "provider_id": "sestante",
                "name": "SSO AGESCI Campania",
                "client_id": "id",
                "secret": "segreto",
                "settings": {"server_url": "https://auth.agescicampania.net/application/o/tana"},
            }
        ]
    }
}


@pytest.fixture
def sestante(settings):
    settings.SOCIALACCOUNT_PROVIDERS = PROVIDER_SESTANTE


@pytest.fixture
def utente(db):
    return User.objects.create_user("capo@example.org")


def gruppi(utente):
    return set(utente.groups.values_list("name", flat=True))


def test_nomina_e_revoca_allineano_i_gruppi(utente):
    nomina(utente, Ruolo.PATTUGLIA)
    nomina(utente, Ruolo.PATTUGLIA)  # idempotente
    assert gruppi(utente) == {"Pattuglia"}
    assert Nomina.objects.filter(utente=utente, attiva=True).count() == 1
    revoca(utente, Ruolo.PATTUGLIA)
    assert gruppi(utente) == set()
    assert ruoli_attivi(utente) == set()


def test_ruoli_globali_da_sestante(utente):
    nomina(utente, Ruolo.PATTUGLIA)
    allinea_ruoli_globali(utente, ["segreteria", "authentik Admins", "admin-multipiattaforma"])
    assert ruoli_attivi(utente) == {Ruolo.PATTUGLIA, Ruolo.SEGRETERIA, Ruolo.AMMINISTRATORE}
    # Tolto un gruppo in Sestante: si revoca solo quel ruolo globale
    allinea_ruoli_globali(utente, ["segreteria"])
    assert ruoli_attivi(utente) == {Ruolo.PATTUGLIA, Ruolo.SEGRETERIA}
    allinea_ruoli_globali(utente, [])
    assert ruoli_attivi(utente) == {Ruolo.PATTUGLIA}
    assert gruppi(utente) == {"Pattuglia"}


def test_ruolo_locale_e_globale_insieme(utente):
    nomina(utente, Ruolo.AMMINISTRATORE)
    allinea_ruoli_globali(utente, ["admin-multipiattaforma"])
    allinea_ruoli_globali(utente, [])
    # La nomina locale resta: l'utente è ancora amministratore
    assert ruoli_attivi(utente) == {Ruolo.AMMINISTRATORE}


@pytest.mark.parametrize(
    ("ruolo", "amministrazione", "pattuglia", "vede_tutto", "assegna"),
    [
        (Ruolo.AMMINISTRATORE, True, True, True, True),
        (Ruolo.RESPONSABILE, True, True, True, True),
        (Ruolo.PATTUGLIA, False, True, True, False),
        (Ruolo.SEGRETERIA, False, False, True, True),
        (Ruolo.REDAZIONE, False, False, False, False),
    ],
)
def test_permessi_dei_ruoli(utente, ruolo, amministrazione, pattuglia, vede_tutto, assegna):
    nomina(utente, ruolo)
    assert permessi.e_amministrazione(utente) is amministrazione
    assert permessi.e_pattuglia(utente) is pattuglia
    assert permessi.vede_tutte_le_prenotazioni(utente) is vede_tutto
    assert permessi.assegna_ruoli(utente) is assegna


def test_richiedente_senza_permessi_di_gestione(utente):
    assert not permessi.e_pattuglia(utente)
    utente.is_active = False
    nomina(utente, Ruolo.AMMINISTRATORE)
    assert not permessi.e_amministrazione(utente)


# --- Login Sestante ---------------------------------------------------------------------


def richiesta(metodi=None):
    request = RequestFactory().get("/accounts/oidc/sestante/login/callback/")
    request.session = SessionStore()
    if metodi is not None:
        request.session["account_authentication_methods"] = metodi
    request._messages = FallbackStorage(request)
    return request


def social_login(email, groups=(), uid="sub-1"):
    account = SocialAccount(
        provider="sestante",
        uid=uid,
        extra_data={"userinfo": {"email": email, "groups": list(groups)}, "id_token": {}},
    )
    indirizzi = [EmailAddress(email=email, verified=False, primary=True)] if email else []
    return SocialLogin(user=User(email=email or ""), account=account, email_addresses=indirizzi)


def test_solo_sestante_fa_auto_signup():
    adapter = TanaSocialAccountAdapter()
    assert adapter.is_auto_signup_allowed(richiesta(), social_login("a@example.org"))
    altro = social_login("a@example.org")
    altro.account.provider = "google"
    assert not adapter.is_auto_signup_allowed(richiesta(), altro)


def test_utente_esistente_collegato_per_email(utente, sestante):
    sociallogin = social_login("CAPO@example.org", groups=["segreteria"])
    TanaSocialAccountAdapter().pre_social_login(richiesta(), sociallogin)
    assert sociallogin.is_existing and sociallogin.user == utente
    assert SocialAccount.objects.get(user=utente).provider == "sestante"
    assert all(e.verified for e in sociallogin.email_addresses)
    assert ruoli_attivi(utente) == {Ruolo.SEGRETERIA}


def test_account_pre_registrato_collegato_al_primo_login(db, sestante):
    n, creato = nomina_per_email("Pre@Example.org", Ruolo.PATTUGLIA)
    assert creato and not n.utente.has_usable_password()
    assert nomina_per_email("pre@example.org", Ruolo.REDAZIONE)[1] is False
    sociallogin = social_login("pre@example.org", groups=["segreteria"])
    TanaSocialAccountAdapter().pre_social_login(richiesta(), sociallogin)
    assert sociallogin.is_existing and sociallogin.user == n.utente
    assert User.objects.count() == 1
    # Email verificata da Sestante: Tana non chiede un'altra verifica
    assert has_verified_email(n.utente)
    assert EmailAddress.objects.get(user=n.utente).primary
    assert ruoli_attivi(n.utente) == {Ruolo.PATTUGLIA, Ruolo.REDAZIONE, Ruolo.SEGRETERIA}


def test_email_non_verificata_diventa_verificata(utente, sestante):
    # Es. account collegato prima della correzione, o richiedente con l'email da confermare
    EmailAddress.objects.create(user=utente, email="capo@example.org", verified=False, primary=True)
    TanaSocialAccountAdapter().pre_social_login(richiesta(), social_login("Capo@Example.org"))
    assert EmailAddress.objects.get(user=utente).verified
    assert EmailAddress.objects.filter(user=utente).count() == 1


def test_invito_cancellato_al_primo_login(utente, sestante):
    InvitoSestante.objects.create(
        utente=utente, uuid=uuid.uuid4(), scade_il=timezone.now(), inviato_il=timezone.now()
    )
    TanaSocialAccountAdapter().pre_social_login(richiesta(), social_login("capo@example.org"))
    assert not InvitoSestante.objects.exists()


def test_nuovo_utente_con_i_ruoli_globali(db, sestante):
    sociallogin = social_login("nuovo@example.org", groups=["admin-multipiattaforma"])
    adapter = TanaSocialAccountAdapter()
    request = richiesta()
    adapter.pre_social_login(request, sociallogin)
    assert not sociallogin.is_existing
    utente = adapter.save_user(request, sociallogin)
    assert ruoli_attivi(utente) == {Ruolo.AMMINISTRATORE}
    assert not utente.has_usable_password()


@pytest.mark.parametrize("email", [None, "doppio@example.org"])
def test_login_rifiutato_senza_account_parziali(db, email):
    if email:
        User.objects.create_user("doppio@example.org")
        User.objects.create_user("Doppio@Example.org")
    numero_utenti = User.objects.count()
    with pytest.raises(ImmediateHttpResponse) as uscita:
        TanaSocialAccountAdapter().pre_social_login(richiesta(), social_login(email))
    assert uscita.value.response["Location"] == "/accounts/login/"
    assert User.objects.count() == numero_utenti
    assert not SocialAccount.objects.exists()


# --- MFA --------------------------------------------------------------------------------


def test_criterio_della_sessione():
    assert sessione_da_sestante(richiesta(SESSIONE_SESTANTE))
    assert not sessione_da_sestante(richiesta([{"method": "password", "at": 1}]))
    assert not sessione_da_sestante(richiesta())


@pytest.fixture
def superutente(db):
    return User.objects.create_superuser("emergenza@example.org", "password-lunga-1")


def test_superutente_deve_attivare_il_totp(client, superutente):
    client.force_login(superutente)
    risposta = client.get("/django-admin/")
    assert risposta.status_code == 302
    assert risposta["Location"] == "/accounts/2fa/totp/activate/"
    # La pagina di attivazione è raggiungibile (allauth chiede prima la password)
    attivazione = client.get("/accounts/2fa/totp/activate/")
    assert attivazione["Location"].startswith("/accounts/reauthenticate/")


def test_superutente_con_totp_entra(client, superutente):
    Authenticator.objects.create(user=superutente, type=Authenticator.Type.TOTP, data={})
    client.force_login(superutente)
    assert client.get("/django-admin/").status_code == 200


def test_sessione_sestante_esente(client, superutente):
    client.force_login(superutente)
    sessione = client.session
    sessione["account_authentication_methods"] = SESSIONE_SESTANTE
    sessione.save()
    assert client.get("/django-admin/").status_code == 200


def test_richiedente_senza_mfa_obbligatoria(client, utente):
    client.force_login(utente)
    assert client.get("/django-admin/").status_code == 302  # login admin, non MFA
    assert "totp" not in client.get("/django-admin/")["Location"]


def test_totp_del_superutente_non_si_elimina(superutente, utente):
    adapter = TanaMFAAdapter()
    totp = Authenticator.objects.create(user=superutente, type=Authenticator.Type.TOTP, data={})
    codici = Authenticator(user=superutente, type=Authenticator.Type.RECOVERY_CODES)
    assert not adapter.can_delete_authenticator(totp)
    assert adapter.can_delete_authenticator(codici)
    assert adapter.can_delete_authenticator(
        Authenticator(user=utente, type=Authenticator.Type.TOTP)
    )


def test_pulsante_sso_nella_pagina_di_login(client, settings):
    assert "SSO AGESCI Campania" not in client.get("/accounts/login/").content.decode()
    settings.SOCIALACCOUNT_PROVIDERS = PROVIDER_SESTANTE
    assert "SSO AGESCI Campania" in client.get("/accounts/login/").content.decode()


def test_indirizzo_di_sestante_senza_barra_finale(monkeypatch):
    """Con la "/" finale allauth chiede …/tana//.well-known/… e Sestante risponde 404 (500 in Tana)."""
    import importlib

    import config.settings.base as base

    monkeypatch.setenv("SOCIAL_SESTANTE_CLIENT_ID", "id")
    monkeypatch.setenv(
        "SOCIAL_SESTANTE_SERVER_URL", "https://auth.agescicampania.net/application/o/tana/"
    )
    try:
        importlib.reload(base)
        app = base.SOCIALACCOUNT_PROVIDERS["openid_connect"]["APPS"][0]
        assert app["settings"]["server_url"] == "https://auth.agescicampania.net/application/o/tana"
    finally:
        monkeypatch.undo()
        importlib.reload(base)
