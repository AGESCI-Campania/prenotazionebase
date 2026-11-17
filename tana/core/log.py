"""Logging di produzione: file, console ed email agli amministratori senza i 503."""

import logging
from pathlib import Path
from typing import Any


def non_manutenzione(record: logging.LogRecord) -> bool:
    """Scarta le risposte 503: le dà solo la pagina di manutenzione, voluta durante gli
    aggiornamenti; senza filtro ogni richiesta (es. il service worker) manda una email."""
    return getattr(record, "status_code", None) != 503


def configurazione(cartella: Path) -> dict[str, Any]:
    """LOGGING di produzione.

    Il logger `django` va ridefinito: la configurazione di default di Django gli lascia un
    proprio `mail_admins` senza il filtro dei 503, e gli errori di `django.request` vi
    risalgono (email doppie, e quelle della manutenzione comunque inviate).
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "semplice": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}
        },
        "filters": {
            "non_manutenzione": {
                "()": "django.utils.log.CallbackFilter",
                "callback": "ext://tana.core.log.non_manutenzione",
            }
        },
        "handlers": {
            "console": {"class": "logging.StreamHandler", "formatter": "semplice"},
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(cartella / "tana.log"),
                "maxBytes": 5 * 1024 * 1024,
                "backupCount": 5,
                "formatter": "semplice",
            },
            "mail_admins": {
                "class": "django.utils.log.AdminEmailHandler",
                "level": "ERROR",
                "filters": ["non_manutenzione"],
            },
        },
        "root": {"handlers": ["console", "file"], "level": "INFO"},
        "loggers": {
            # Solo verso root (console e file): niente gestori di default
            "django": {"handlers": [], "level": "INFO", "propagate": True},
            "django.request": {"handlers": ["mail_admins"], "level": "ERROR", "propagate": True},
        },
    }
