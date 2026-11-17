import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.urls import reverse

from tana.base.models import Area, Configurazione
from tana.core.models import EventoStorico
from tana.prenotazioni import demo, flusso
from tana.prenotazioni.models import (
    ContatoreNumeri,
    Contatto,
    Occupazione,
    Pagamento,
    Prenotazione,
)
from tana.prenotazioni.services import crea_blocco

from .utils import richiesta, tra

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _dati(dati):
    pass


def in_demo():
    return Configurazione.corrente().modalita_demo


def test_si_attiva_solo_senza_prenotazioni(admin, pattuglia, richiedente, contatto):
    with pytest.raises(PermissionDenied):
        demo.attiva(utente=pattuglia)
    richiesta(richiedente, contatto)
    with pytest.raises(ValidationError):
        demo.attiva(utente=admin)
    assert not in_demo()


def test_in_demo_prenota_solo_la_gestione(admin, pattuglia, richiedente, contatto):
    demo.attiva(utente=admin)
    with pytest.raises(ValidationError, match="prova del sistema"):
        richiesta(richiedente, contatto)
    assert richiesta(pattuglia, contatto).pk


def test_email_ai_richiedenti_solo_verso_utenti_con_un_ruolo(email, admin, pattuglia):
    demo.attiva(utente=admin)
    # Referente esterno (es. importato): nessuna email al richiedente
    esterno = Contatto.objects.create(nome="Gruppo vero", email="gruppo@example.org")
    email(richiesta, pattuglia, esterno)
    destinatari = [i for m in email.inviate for i in m.to]
    assert "gruppo@example.org" not in destinatari
    assert all(m.subject.startswith("[DEMO] ") for m in email.inviate)
    # Chi prova con il proprio indirizzo riceve l'email del richiedente
    email.inviate.clear()
    proprio = Contatto.objects.create(nome="Prova", email="PATTUGLIA@example.org")
    email(richiesta, pattuglia, proprio, arrivo=20, partenza=22)
    assert any("pattuglia@example.org" in [i.lower() for i in m.to] for m in email.inviate)


def test_al_termine_si_cancella_tutto(
    admin, pattuglia, contatto, django_capture_on_commit_callbacks
):
    demo.attiva(utente=admin)
    blocco = crea_blocco(area=_area(), dal=tra(60), al=tra(61), motivo="Lavori")
    p = richiesta(pattuglia, contatto)
    flusso.approva(p, utente=admin)
    flusso.carica_ricevuta(p, utente=pattuglia, ricevuta=ContentFile(b"x", name="r.pdf"))
    ricevuta = Pagamento.objects.get().ricevuta.name
    with pytest.raises(PermissionDenied):
        demo.termina(utente=pattuglia)
    with django_capture_on_commit_callbacks(execute=True):
        assert demo.termina(utente=admin) == 1
    assert not Prenotazione.objects.exists()
    assert not Pagamento.objects.exists() and not Contatto.objects.exists()
    assert not ContatoreNumeri.objects.exists()
    assert not storages["privato"].exists(ricevuta)
    assert not EventoStorico.objects.filter(content_type__app_label="prenotazioni").exists()
    # Le date bloccate restano
    assert Occupazione.objects.filter(blocco=blocco).exists()
    assert not in_demo()
    assert EventoStorico.objects.filter(azione="modalità demo terminata").exists()


def _area():
    return Area.objects.get(codice="ACC")


def test_in_demo_registrazione_chiusa_tranne_sestante(admin, client, settings):
    from tana.accounts.adapters import TanaSocialAccountAdapter
    from tana.accounts.models import User
    from tana.accounts.tests.test_ruoli_sso import PROVIDER_SESTANTE, richiesta, social_login

    settings.SOCIALACCOUNT_PROVIDERS = PROVIDER_SESTANTE
    pagina = client.get(reverse("account_signup")).content.decode()
    # Fuori dalla demo: modulo aperto, con il pulsante SSO prima del modulo
    assert pagina.index("Accedi con SSO AGESCI Campania") < pagina.index('name="password1"')
    demo.attiva(utente=admin)
    pagina = client.get(reverse("account_signup")).content.decode()
    assert "Le registrazioni non sono ancora aperte" in pagina and "password1" not in pagina
    assert "Accedi con SSO AGESCI Campania" in pagina and "oppure con email" not in pagina
    dati = {
        "email": "nuovo@example.org",
        "password1": "una-Password-lunga1",
        "password2": "una-Password-lunga1",
    }
    client.post(reverse("account_signup"), dati)
    assert not User.objects.filter(email="nuovo@example.org").exists()
    # Il primo accesso con Sestante crea comunque l'account
    adapter = TanaSocialAccountAdapter()
    assert adapter.is_open_for_signup(richiesta(), social_login("capo@example.org"))
