"""Aiuti per la rete dietro il reverse proxy."""

from django.http import HttpRequest


def ip_client_dietro_proxy(request: HttpRequest) -> str:
    """IP del client dietro Caddy → nginx interno.

    nginx aggiunge a X-Forwarded-For l'indirizzo da cui riceve (Caddy): il client è quindi il
    penultimo valore. REMOTE_ADDR sarebbe sempre l'nginx interno.
    """
    valori = [
        v.strip() for v in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if v.strip()
    ]
    if len(valori) >= 2:
        return valori[-2]
    if valori:
        return valori[-1]
    return request.META.get("REMOTE_ADDR", "")
