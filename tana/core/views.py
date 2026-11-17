from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def healthz(request: HttpRequest) -> HttpResponse:
    """200 se l'app risponde e raggiunge il database. Nessuna autenticazione, nessun dato.

    Usato dal healthcheck del servizio `web` e da `docker compose up --wait` (unit systemd).
    """
    connection.ensure_connection()
    return HttpResponse("ok", content_type="text/plain")


# --- PWA (D-22): installabile, senza uso offline --------------------------------------


def manifest(request: HttpRequest) -> HttpResponse:
    """Manifest con le icone da `{% static %}` (nomi con hash: niente cache vecchie su iOS)."""
    return render(request, "pwa/manifest.webmanifest", content_type="application/manifest+json")


def service_worker(request: HttpRequest) -> HttpResponse:
    """Service worker alla radice (ambito: tutto il sito). Va sempre in rete; senza rete mostra
    la pagina di avviso, nient'altro in cache."""
    risposta = render(request, "pwa/sw.js", content_type="application/javascript")
    risposta["Cache-Control"] = "no-cache"
    return risposta


def senza_rete(request: HttpRequest) -> HttpResponse:
    return render(request, "pwa/senza_rete.html")
