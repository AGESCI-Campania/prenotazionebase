import logging
import logging.config

from tana.core.log import non_manutenzione


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
