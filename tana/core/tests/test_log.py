import logging
import logging.config

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils.log import DEFAULT_LOGGING, configure_logging, log_response

from tana.core.log import configurazione, non_manutenzione


def _record(status_code: int) -> logging.LogRecord:
    record = logging.makeLogRecord({"msg": "Errore", "levelno": logging.ERROR})
    record.status_code = status_code
    return record


def test_niente_email_per_la_manutenzione():
    assert not non_manutenzione(_record(503))
    assert non_manutenzione(_record(500))
    assert non_manutenzione(logging.makeLogRecord({"msg": "Eccezione"}))


def test_filtro_risolto_da_dictconfig():
    filtro = {
        "()": "django.utils.log.CallbackFilter",
        "callback": "ext://tana.core.log.non_manutenzione",
    }
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"f": filtro},
            "handlers": {"h": {"class": "logging.NullHandler", "filters": ["f"]}},
            "loggers": {"tana.test_log": {"handlers": ["h"], "propagate": False}},
        }
    )
    gestore = logging.getLogger("tana.test_log").handlers[0]
    assert not gestore.filter(_record(503))
    assert gestore.filter(_record(500))


@pytest.fixture
def logging_di_produzione(settings, tmp_path):
    # Come Django all'avvio: prima la configurazione di default, poi LOGGING
    settings.ADMINS = ["admin@example.org"]
    logging.config.dictConfig(DEFAULT_LOGGING)
    logging.config.dictConfig(configurazione(tmp_path))
    yield
    configure_logging(settings.LOGGING_CONFIG, settings.LOGGING)


@pytest.mark.parametrize(("stato", "email"), [(503, 0), (500, 1)])
def test_email_agli_amministratori(logging_di_produzione, mailoutbox, stato, email):
    request = RequestFactory().get("/manifest.webmanifest")
    log_response("Errore: %s", request.path, response=HttpResponse(status=stato), request=request)
    assert len(mailoutbox) == email  # 503 mai, 500 una sola volta (non doppia)
