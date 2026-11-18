"""MFA obbligatoria per il superutente di emergenza (P-13): finché non configura il TOTP può
solo attivarlo o uscire. Chi è entrato con Sestante in questa sessione è esente (D-28)."""

from collections.abc import Callable

from allauth.mfa.models import Authenticator
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse

from .adapters import mfa_obbligatoria, sessione_da_sestante

# sw.js e manifest: il browser li chiede da solo, un redirect darebbe solo errori in console
PERCORSI_LIBERI = ("/accounts/", "/healthz/", "/static/", "/sw.js", "/manifest.webmanifest")


class MFAObbligatoriaMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        utente = request.user
        if (
            utente.is_authenticated
            and mfa_obbligatoria(utente)
            and not request.path.startswith(PERCORSI_LIBERI)
            and not sessione_da_sestante(request)
            and not Authenticator.objects.filter(user=utente, type=Authenticator.Type.TOTP).exists()
        ):
            return HttpResponseRedirect(reverse("mfa_activate_totp"))
        return self.get_response(request)
