"""Backend di autenticazione con password: rifiutano gli account di gestione (P-13).

Valgono per ogni form con password (allauth, admin, login dell'editor del sito). Il login con
Sestante non passa da `authenticate` e le sessioni già aperte non si toccano (`get_user`).
"""

from typing import Any

from allauth.account.auth_backends import AuthenticationBackend as AllauthBackend
from django.contrib.auth.backends import ModelBackend

from . import permessi


def _senza_gestione(utente: Any) -> Any:
    return None if utente is not None and permessi.solo_sso(utente) else utente


class TanaModelBackend(ModelBackend):
    def authenticate(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        return _senza_gestione(super().authenticate(request, *args, **kwargs))


class TanaAllauthBackend(AllauthBackend):
    def authenticate(self, request: Any, **credentials: Any) -> Any:  # type: ignore[override]
        return _senza_gestione(super().authenticate(request, **credentials))
