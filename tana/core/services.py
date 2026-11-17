"""Servizi trasversali: storico degli eventi e delle decisioni discrezionali (P-03)."""

from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from .models import EventoStorico


def registra_evento(
    oggetto: models.Model,
    azione: str,
    *,
    utente: Any = None,
    deciso_da: str = "",
    motivazione: str = "",
    prima: dict[str, Any] | None = None,
    dopo: dict[str, Any] | None = None,
) -> EventoStorico:
    """Scrive una voce dello storico per `oggetto`."""
    return EventoStorico.objects.create(
        content_type=ContentType.objects.get_for_model(oggetto),
        object_id=str(oggetto.pk),
        azione=azione,
        utente=utente,
        deciso_da=deciso_da.strip(),
        motivazione=motivazione.strip(),
        dati_prima=prima,
        dati_dopo=dopo,
    )


def registra_decisione(
    oggetto: models.Model,
    azione: str,
    *,
    utente: Any,
    deciso_da: str,
    motivazione: str,
    **dati: Any,
) -> EventoStorico:
    """Come `registra_evento`, ma per le decisioni discrezionali (D-14): "deciso da" e
    motivazione sono obbligatori (P-03)."""
    errori = {}
    if not deciso_da.strip():
        errori["deciso_da"] = "Indica chi ha preso la decisione."
    if not motivazione.strip():
        errori["motivazione"] = "Indica la motivazione della decisione."
    if errori:
        raise ValidationError(errori)
    return registra_evento(
        oggetto, azione, utente=utente, deciso_da=deciso_da, motivazione=motivazione, **dati
    )


def storico(oggetto: models.Model) -> models.QuerySet[EventoStorico]:
    """Eventi di `oggetto`, dal più recente."""
    return EventoStorico.objects.filter(
        content_type=ContentType.objects.get_for_model(oggetto), object_id=str(oggetto.pk)
    )
