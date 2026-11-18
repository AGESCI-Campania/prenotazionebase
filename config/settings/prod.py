"""Produzione: dietro Caddy (agesci-campania-web-frontend) e l'nginx interno, solo HTTP.

Regole: docs/INTEGRAZIONE.md del repo agesci-campania-web-frontend (§ 2.4–2.5).
"""

from pathlib import Path

from tana.core.log import configurazione as configurazione_logging

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

# Ricevute e allegati privati: li serve l'nginx interno dopo il controllo in Django (P-14)
PRIVATI_X_ACCEL = True

# Dietro due proxy (Caddy → nginx) l'IP del client è il penultimo di X-Forwarded-For
AXES_CLIENT_IP_CALLABLE = "tana.core.rete.ip_client_dietro_proxy"

LOG_DIR = Path(env.str("LOG_DIR", default=str(BASE_DIR / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = configurazione_logging(LOG_DIR)
