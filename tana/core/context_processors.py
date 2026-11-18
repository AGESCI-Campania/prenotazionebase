from django.conf import settings
from django.http import HttpRequest


def manuale(request: HttpRequest) -> dict[str, str]:
    """Link al manuale d'uso nel footer e nel menu della gestione."""
    return {"manuale_url": settings.MANUALE_URL}
