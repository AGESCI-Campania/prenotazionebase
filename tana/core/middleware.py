"""Middleware di manutenzione: pagina statica 503 durante gli aggiornamenti."""

from collections.abc import Callable

from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string

PERCORSI_LIBERI = ("/healthz/", "/static/")


class ManutenzioneMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not request.path.startswith(PERCORSI_LIBERI):
            from tana.core.models import Manutenzione

            try:
                stato = Manutenzione.objects.filter(pk=1).only("attiva", "messaggio").first()
            except DatabaseError:
                stato = None  # tabella non ancora creata (prima migrazione): nessun blocco
            utente = getattr(request, "user", None)
            if stato and stato.attiva and not (utente and utente.is_superuser):
                html = render_to_string("core/manutenzione.html", {"messaggio": stato.messaggio})
                risposta = HttpResponse(html, status=503)
                risposta["Retry-After"] = "120"
                return risposta
        return self.get_response(request)
