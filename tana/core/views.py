from django.db import connection
from django.http import HttpRequest, HttpResponse


def healthz(request: HttpRequest) -> HttpResponse:
    """200 se l'app risponde e raggiunge il database. Nessuna autenticazione, nessun dato.

    Usato dal healthcheck del servizio `web` e da `docker compose up --wait` (unit systemd).
    """
    connection.ensure_connection()
    return HttpResponse("ok", content_type="text/plain")
