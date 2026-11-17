"""Sviluppo: Django sull'host, PostgreSQL in Docker (docker-compose.dev.yml)."""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = ["*"]
# Email in console; con EMAIL_MAILPIT=true a Mailpit (docker-compose.dev.yml, UI su :8025)
if env.bool("EMAIL_MAILPIT", default=False):
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {"host": "localhost", "port": 1025, "use_tls": False},
        }
    }
else:
    MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}
ACCOUNT_EMAIL_VERIFICATION = "optional"
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
