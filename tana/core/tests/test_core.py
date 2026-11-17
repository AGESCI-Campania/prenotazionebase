import pytest
from django.core.management import call_command
from django.test import RequestFactory

from tana.core.models import Manutenzione
from tana.core.rete import ip_client_dietro_proxy

pytestmark = pytest.mark.django_db


def test_healthz_risponde_ok(client):
    risposta = client.get("/healthz/")
    assert risposta.status_code == 200
    assert risposta.content == b"ok"


def test_comando_manutenzione_attiva_e_disattiva(capsys):
    call_command("manutenzione", "attiva", "--messaggio", "Aggiornamento in corso")
    assert Manutenzione.corrente().attiva
    assert capsys.readouterr().out.strip().splitlines()[-1] == "attiva"
    call_command("manutenzione", "disattiva")
    assert not Manutenzione.corrente().attiva
    call_command("manutenzione", "stato")
    assert capsys.readouterr().out.strip().splitlines()[-1] == "disattiva"


def test_manutenzione_blocca_il_sito_ma_non_healthz(client):
    call_command("manutenzione", "attiva", "--messaggio", "Torniamo presto")
    risposta = client.get("/")
    assert risposta.status_code == 503
    assert "Torniamo presto" in risposta.content.decode()
    assert client.get("/healthz/").status_code == 200


def test_manutenzione_non_blocca_i_superutenti(client, django_user_model):
    admin = django_user_model.objects.create_superuser("admin@example.org", "password-lunga-1")
    client.force_login(admin)
    call_command("manutenzione", "attiva")
    assert client.get("/healthz/").status_code == 200
    assert client.get("/").status_code != 503


def test_scheduler_un_giro_aggiorna_il_battito(tmp_path, settings):
    settings.SCHEDULER_BATTITO = tmp_path / "battito"
    call_command("scheduler", "--una-volta")
    assert settings.SCHEDULER_BATTITO.exists()


@pytest.mark.parametrize(
    ("xff", "atteso"),
    [("203.0.113.7, 172.18.0.5", "203.0.113.7"), ("203.0.113.7", "203.0.113.7"), ("", "10.0.0.1")],
)
def test_ip_client_dietro_proxy(xff, atteso):
    richiesta = RequestFactory().get("/", HTTP_X_FORWARDED_FOR=xff, REMOTE_ADDR="10.0.0.1")
    assert ip_client_dietro_proxy(richiesta) == atteso
