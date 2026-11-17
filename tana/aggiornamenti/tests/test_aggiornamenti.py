import json

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from tana.aggiornamenti import services
from tana.aggiornamenti.models import ReleaseGitHub, RichiestaAggiornamento, StatoRichiesta

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def cartella(tmp_path, settings, monkeypatch):
    settings.AGGIORNAMENTI_DIR = tmp_path
    monkeypatch.setattr(services, "versione_installata", lambda: "0.1.0")
    return tmp_path


def release(versione="v0.2.0"):
    r = ReleaseGitHub.corrente()
    r.versione = versione
    r.save()
    return r


def test_confronto_versioni():
    assert services.e_successiva("v0.2.0", "0.1.0")
    assert not services.e_successiva("v0.1.0", "0.1.0")
    assert not services.tag_valido("0.2.0") and services.tag_valido("v1.10.3")


def test_richiesta_scrive_il_file(cartella, admin):
    release()
    richiesta = services.crea_richiesta(admin, "v0.2.0")
    dati = json.loads((cartella / "richiesta.json").read_text())
    assert dati["id"] == richiesta.pk and dati["versione"] == "v0.2.0"
    with pytest.raises(services.RichiestaInCorso):
        services.crea_richiesta(admin, "v0.2.0")
    services.annulla_richiesta(admin)
    assert not (cartella / "richiesta.json").exists()


def test_solo_l_ultima_release_successiva(admin):
    release("v0.1.0")
    with pytest.raises(ValidationError):
        services.crea_richiesta(admin, "v0.1.0")
    with pytest.raises(ValidationError):
        services.crea_richiesta(admin, "v0.3.0")  # non è l'ultima nota


def test_stato_dal_server(cartella, admin):
    release()
    richiesta = services.crea_richiesta(admin, "v0.2.0")
    (cartella / "richiesta.json").rename(cartella / "in-corso.json")
    assert services.sincronizza_storico().stato == StatoRichiesta.IN_CORSO
    with pytest.raises(services.RichiestaInCorso):
        services.annulla_richiesta(admin)
    (cartella / "stato.json").write_text(json.dumps({"id": richiesta.pk, "fase": "build", "messaggio": "Costruzione", "percentuale": 45, "esito": None, "log": ["riga"]}))
    richiesta = services.sincronizza_storico()
    assert (richiesta.fase, richiesta.percentuale) == ("build", 45)
    (cartella / "stato.json").write_text(json.dumps({"id": richiesta.pk, "fase": "fine", "messaggio": "Fatto", "percentuale": 100, "esito": "completato", "aggiornato_at": "2026-11-17T12:00:00+01:00"}))
    richiesta = services.sincronizza_storico()
    assert richiesta.stato == StatoRichiesta.COMPLETATO and richiesta.completato_il is not None


def test_pagina_solo_amministrazione_e_riautenticazione(admin, pattuglia):
    release()
    c = Client()
    c.force_login(pattuglia)
    assert c.get(reverse("gestione:aggiornamenti")).status_code == 403
    c.force_login(admin)  # force_login: nessun accesso recente registrato da allauth
    pagina = c.get(reverse("gestione:aggiornamenti")).content.decode()
    assert "Aggiorna a v0.2.0" in pagina and "conferma la tua identità" in pagina
    c.post(reverse("gestione:aggiornamenti"), {"azione": "aggiorna", "versione": "v0.2.0"})
    assert not RichiestaAggiornamento.objects.exists()


def test_richiesta_con_accesso_recente(admin, monkeypatch, cartella):
    release()
    monkeypatch.setattr(services, "autenticazione_recente", lambda request: True)
    c = Client()
    c.force_login(admin)
    c.post(reverse("gestione:aggiornamenti"), {"azione": "aggiorna", "versione": "v0.2.0"})
    assert RichiestaAggiornamento.objects.get().stato == StatoRichiesta.IN_ATTESA
    assert (cartella / "richiesta.json").exists()


def test_pagina_raggiungibile_in_manutenzione(admin):
    call_command("manutenzione", "attiva")
    c = Client()
    c.force_login(admin)
    assert c.get(reverse("gestione:aggiornamenti")).status_code == 200
    assert c.get(reverse("gestione:cruscotto")).status_code == 503


def test_controllo_della_release(monkeypatch):
    class Risposta:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"tag_name": "v0.3.0", "name": "Tana 0.3.0", "body": "Novità", "published_at": "2026-11-17T10:00:00Z", "html_url": "https://github.com/x"}).encode()

    monkeypatch.setattr(services.urllib.request, "urlopen", lambda req, timeout: Risposta())
    r = services.controlla_ultima_release()
    assert r.versione == "v0.3.0" and not r.errore and services.aggiornamento_disponibile()

    def guasto(req, timeout):
        raise OSError("rete assente")

    monkeypatch.setattr(services.urllib.request, "urlopen", guasto)
    assert services.controlla_ultima_release().errore == "rete assente"
