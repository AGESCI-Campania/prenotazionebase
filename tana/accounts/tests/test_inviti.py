import datetime
import io
import json
import logging
import urllib.error
import uuid

import pytest
from allauth.socialaccount.models import SocialAccount
from django.test import Client
from django.urls import reverse
from django.utils import formats, timezone

from tana.accounts import inviti, permessi, services
from tana.accounts.models import InvitoSestante, Nomina, Ruolo, User
from tana.accounts.services import nomina

pytestmark = pytest.mark.django_db

TOKEN = "token-segreto-di-prova"
URL = reverse("gestione:utenti")


class SestanteFinto:
    """Sostituisce le chiamate HTTP a Sestante e le registra."""

    def __init__(self):
        self.chiamate = []
        self.errore = None

    def __call__(self, metodo, percorso, dati=None):
        self.chiamate.append((metodo, percorso, dati))
        if self.errore:
            raise inviti.ErroreSestante(self.errore)
        if metodo == "GET":
            return {"pk": "flusso-pk"}
        if metodo == "POST":
            return {"pk": str(uuid.uuid4())}
        return None

    def di(self, metodo):
        return [c for c in self.chiamate if c[0] == metodo]


@pytest.fixture
def sestante(settings, monkeypatch, dati_iniziali):
    settings.SESTANTE_INVITI_TOKEN = TOKEN
    finto = SestanteFinto()
    monkeypatch.setattr(inviti, "_chiama", finto)
    return finto


def con_ruolo(ruolo, email):
    utente = User.objects.create_user(email)
    nomina(utente, ruolo)
    return utente


def cliente_di(utente):
    c = Client()
    c.force_login(utente)
    return c


@pytest.fixture
def segreteria(db):
    return con_ruolo(Ruolo.SEGRETERIA, "segreteria@example.org")


@pytest.fixture
def responsabile(db):
    return con_ruolo(Ruolo.RESPONSABILE, "responsabile@example.org")


def test_ruolo_a_email_nuova_manda_l_invito(
    sestante, responsabile, django_capture_on_commit_callbacks, mailoutbox, caplog
):
    with (
        django_capture_on_commit_callbacks(execute=True),
        caplog.at_level(logging.INFO, logger="tana.inviti"),
    ):
        risposta = cliente_di(responsabile).post(
            URL, {"email": "Nuovo@Example.org", "ruolo": Ruolo.PATTUGLIA}, follow=True
        )
    utente = User.objects.get(email__iexact="nuovo@example.org")
    # Data con il mese in minuscolo, come nel resto di Tana
    scadenza = timezone.localtime(timezone.now() + inviti.DURATA)
    assert f"{scadenza.day} {formats.date_format(scadenza, 'F').lower()} " in (
        risposta.content.decode()
    )
    _, percorso, dati = sestante.di("POST")[0]
    assert percorso == "stages/invitation/invitations/"
    assert dati["flow"] == "flusso-pk" and dati["single_use"] is False
    # Solo le chiavi ammesse dal contratto, username uguale all'email
    assert set(dati["fixed_data"]) == {"email", "username", "attributes.invito"}
    assert dati["fixed_data"]["username"] == dati["fixed_data"]["email"] == utente.email
    assert dati["fixed_data"]["attributes.invito"]["richiesto_da"] == responsabile.email
    scadenza = datetime.datetime.fromisoformat(dati["expires"])
    assert timezone.now() + datetime.timedelta(days=6) < scadenza
    assert scadenza <= timezone.now() + inviti.DURATA
    invito = InvitoSestante.objects.get(utente=utente)
    assert invito.inviato_da == responsabile
    [email] = mailoutbox
    assert email.to == [utente.email]
    assert f"/if/flow/sestante-iscrizione-invito/?itoken={invito.uuid}" in email.body
    assert "Pattuglia" in email.body and TOKEN not in email.body
    assert formats.date_format(scadenza, "F").lower() in email.body
    assert f"Invito Sestante: email inviata a {utente.email}" in caplog.text
    pagina = cliente_di(responsabile).get(URL).content.decode()
    assert "Rimanda l&#x27;invito" in pagina or "Rimanda l'invito" in pagina


def test_rimanda_stesso_link_o_nuovo_invito(
    sestante, segreteria, django_capture_on_commit_callbacks, mailoutbox
):
    utente = con_ruolo(Ruolo.PATTUGLIA, "capo@example.org")
    c = cliente_di(segreteria)
    with django_capture_on_commit_callbacks(execute=True):
        c.post(URL, {"invita": utente.pk})
    primo = InvitoSestante.objects.get(utente=utente).uuid
    # Subito dopo (doppio clic): niente di nuovo
    with django_capture_on_commit_callbacks(execute=True):
        c.post(URL, {"invita": utente.pk})
    assert len(sestante.di("POST")) == 1 and len(mailoutbox) == 1
    # Più tardi, ancora valido: stessa email con lo stesso link, nessun invito nuovo
    InvitoSestante.objects.filter(utente=utente).update(
        inviato_il=timezone.now() - inviti.RIPETIZIONE
    )
    with django_capture_on_commit_callbacks(execute=True):
        c.post(URL, {"invita": utente.pk})
    assert len(sestante.di("POST")) == 1 and len(mailoutbox) == 2
    assert InvitoSestante.objects.get(utente=utente).uuid == primo
    # Quasi scaduto: invito nuovo e revoca del vecchio
    InvitoSestante.objects.filter(utente=utente).update(
        scade_il=timezone.now(), inviato_il=timezone.now() - inviti.RIPETIZIONE
    )
    c.post(URL, {"invita": utente.pk})
    assert len(sestante.di("POST")) == 2
    assert sestante.di("DELETE")[0][1] == f"stages/invitation/invitations/{primo}/"
    assert InvitoSestante.objects.get(utente=utente).uuid != primo


def test_revoca_dell_ultimo_ruolo_revoca_l_invito(sestante, segreteria):
    utente = con_ruolo(Ruolo.PATTUGLIA, "capo@example.org")
    nomina(utente, Ruolo.REDAZIONE)
    c = cliente_di(segreteria)
    c.post(URL, {"invita": utente.pk})
    for ruolo in (Ruolo.REDAZIONE, Ruolo.PATTUGLIA):
        c.post(URL, {"revoca": Nomina.objects.get(utente=utente, ruolo=ruolo, attiva=True).pk})
        # Con un ruolo ancora attivo l'invito resta
        assert InvitoSestante.objects.filter(utente=utente).exists() is (ruolo == Ruolo.REDAZIONE)
    assert len(sestante.di("DELETE")) == 1


def test_errore_di_sestante(sestante, segreteria):
    sestante.errore = "Sestante non è raggiungibile."
    risposta = cliente_di(segreteria).post(
        URL, {"email": "capo@example.org", "ruolo": Ruolo.PATTUGLIA}, follow=True
    )
    # Ruolo e pre-registrazione restano, l'invito no
    utente = User.objects.get(email="capo@example.org")
    assert utente.nomine.filter(attiva=True).exists()
    assert not InvitoSestante.objects.exists()
    assert "Rimanda l" in risposta.content.decode()
    assert "non è partito" in risposta.content.decode()


def test_senza_token_nessun_invito(settings, segreteria, dati_iniziali, monkeypatch):
    settings.SESTANTE_INVITI_TOKEN = ""
    monkeypatch.setattr(inviti, "_chiama", lambda *a, **k: pytest.fail("chiamata a Sestante"))
    risposta = cliente_di(segreteria).post(
        URL, {"email": "capo@example.org", "ruolo": Ruolo.PATTUGLIA}, follow=True
    )
    assert "farselo creare dalla segreteria regionale" in risposta.content.decode()
    assert not InvitoSestante.objects.exists()


def test_chi_ha_gia_sestante_non_si_invita(sestante, segreteria):
    utente = User.objects.create_user("capo@example.org")
    SocialAccount.objects.create(user=utente, provider="sestante", uid="sub-1")
    cliente_di(segreteria).post(URL, {"email": "capo@example.org", "ruolo": Ruolo.PATTUGLIA})
    assert utente.nomine.filter(attiva=True).exists()
    assert sestante.chiamate == []


def test_responsabile_solo_pattuglia_e_redazione(sestante, responsabile):
    assert permessi.ruoli_assegnabili(responsabile) == {Ruolo.PATTUGLIA, Ruolo.REDAZIONE}
    c = cliente_di(responsabile)
    for ruolo in (Ruolo.AMMINISTRATORE, Ruolo.RESPONSABILE, Ruolo.SEGRETERIA):
        c.post(URL, {"email": "altro@example.org", "ruolo": ruolo})
    assert not User.objects.filter(email="altro@example.org").exists()
    # Non revoca ruoli che non può assegnare (nemmeno il proprio)
    assert c.post(URL, {"revoca": responsabile.nomine.get().pk}).status_code == 404
    pagina = c.get(URL).content.decode()
    assert 'value="AMMINISTRATORE"' not in pagina and 'value="PATTUGLIA"' in pagina


def test_chiamata_http(settings, monkeypatch, caplog):
    settings.SESTANTE_INVITI_TOKEN = TOKEN
    settings.SOCIAL_SESTANTE_SERVER_URL = "https://auth.agescicampania.net/application/o/tana"
    richieste = []

    class Risposta(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def urlopen(richiesta, timeout):
        richieste.append(richiesta)
        if richiesta.get_method() == "DELETE":
            raise urllib.error.HTTPError(
                richiesta.full_url, 403, "Forbidden", {}, io.BytesIO(b'{"detail": "no"}')
            )
        return Risposta(json.dumps({"pk": "x"}).encode())

    monkeypatch.setattr(inviti.urllib.request, "urlopen", urlopen)
    assert inviti._chiama("GET", "flows/instances/sestante-iscrizione-invito/") == {"pk": "x"}
    # URL pubblico (mai l'alias Docker) e token nell'header
    assert richieste[0].full_url == (
        "https://auth.agescicampania.net/api/v3/flows/instances/sestante-iscrizione-invito/"
    )
    assert richieste[0].get_header("Authorization") == f"Bearer {TOKEN}"
    with (
        caplog.at_level(logging.WARNING, logger="tana.inviti"),
        pytest.raises(inviti.ErroreSestante, match="403"),
    ):
        inviti._chiama("DELETE", "stages/invitation/invitations/x/")
    assert "403" in caplog.text and TOKEN not in caplog.text


@pytest.mark.django_db(transaction=True)
def test_doppio_clic_un_solo_invito(settings, monkeypatch, mailoutbox):
    """Due richieste contemporanee (doppio clic su «Assegna»): un utente, un ruolo, un invito su
    Sestante e una sola email."""
    import threading
    import time

    from django.db import connection

    settings.SESTANTE_INVITI_TOKEN = TOKEN
    finto = SestanteFinto()

    def lento(metodo, percorso, dati=None):
        if metodo == "POST":
            time.sleep(0.5)  # Sestante che ci mette un po' a rispondere
        return finto(metodo, percorso, dati)

    monkeypatch.setattr(inviti, "_chiama", lento)
    richiedente = con_ruolo(Ruolo.SEGRETERIA, "segreteria@example.org")
    errori = []

    def assegna():
        try:
            n, _ = services.nomina_per_email("capo@example.org", Ruolo.PATTUGLIA)
            inviti.invita(n.utente, richiesto_da=richiedente)
        except Exception as errore:  # noqa: BLE001
            errori.append(errore)
        finally:
            connection.close()

    fili = [threading.Thread(target=assegna) for _ in range(2)]
    for filo in fili:
        filo.start()
    for filo in fili:
        filo.join()
    assert errori == []
    assert User.objects.filter(email="capo@example.org").count() == 1
    assert Nomina.objects.filter(utente__email="capo@example.org", attiva=True).count() == 1
    assert len(finto.di("POST")) == 1
    assert InvitoSestante.objects.count() == 1
    assert len(mailoutbox) == 1
