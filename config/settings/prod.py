"""Produzione: dietro Caddy (agesci-campania-web-frontend) e l'nginx interno, solo HTTP.

Regole: docs/INTEGRAZIONE.md del repo agesci-campania-web-frontend (§ 2.4–2.5).
"""

from pathlib import Path

from django.utils.csp import CSP

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env

DEBUG = env.bool("DJANGO_DEBUG", default=False)

# Caddy → nginx interno: lo schema originale arriva in X-Forwarded-Proto
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "SAMEORIGIN"  # l'anteprima di Wagtail usa un iframe dello stesso sito
SILENCED_SYSTEM_CHECKS = ["security.W019"]  # SAMEORIGIN voluto, vedi sopra

# Il healthcheck chiama /healthz/ in HTTP dentro il container: niente redirect HTTPS lì
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]

# Il tema 3.0.0a3 carica Bootstrap 6 da jsDelivr e i font da Google Fonts (base.html del tema)
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.UNSAFE_INLINE, "https://cdn.jsdelivr.net"],
    "style-src": [
        CSP.SELF,
        CSP.UNSAFE_INLINE,
        "https://cdn.jsdelivr.net",
        "https://fonts.googleapis.com",
    ],
    "img-src": [CSP.SELF, "data:", "https:"],
    "font-src": [CSP.SELF, "data:", "https://fonts.gstatic.com", "https://cdn.jsdelivr.net"],
    "connect-src": [CSP.SELF],
    "frame-src": [CSP.SELF, "https://www.google.com", "https://www.openstreetmap.org"],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF, "https://auth.agescicampania.net"],
    "frame-ancestors": [CSP.SELF],
}

# Ricevute e allegati privati: li serve l'nginx interno dopo il controllo in Django (P-14)
PRIVATI_X_ACCEL = True

# Dietro due proxy (Caddy → nginx) l'IP del client è il penultimo di X-Forwarded-For
AXES_CLIENT_IP_CALLABLE = "tana.core.rete.ip_client_dietro_proxy"

LOG_DIR = Path(env.str("LOG_DIR", default=str(BASE_DIR / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"semplice": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
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
            "filename": str(LOG_DIR / "tana.log"),
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
        "django.request": {"handlers": ["mail_admins"], "level": "ERROR", "propagate": True}
    },
}
