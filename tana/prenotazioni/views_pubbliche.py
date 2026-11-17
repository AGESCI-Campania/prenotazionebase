"""Pagine pubbliche: calendario della disponibilità (D-17, mockup 1)."""

import datetime

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from . import disponibilita as servizio

MESI = [
    "",
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
]


def _mese(valore: str | None) -> datetime.date:
    """Primo giorno del mese da `?mese=AAAA-MM` (di default il mese corrente)."""
    try:
        anno, mese = (int(x) for x in (valore or "").split("-"))
        return datetime.date(anno, mese, 1)
    except ValueError:
        return timezone.localdate().replace(day=1)


def disponibilita(request: HttpRequest) -> HttpResponse:
    primo = _mese(request.GET.get("mese"))
    precedente = (primo - datetime.timedelta(days=1)).replace(day=1)
    successivo = (primo + datetime.timedelta(days=32)).replace(day=1)
    return render(
        request,
        "prenotazioni/disponibilita.html",
        {
            "sezione": "disponibilita",
            "settimane": servizio.calendario_mese(primo.year, primo.month),
            "titolo_mese": f"{MESI[primo.month]} {primo.year}",
            "precedente": f"{precedente:%Y-%m}",
            "successivo": f"{successivo:%Y-%m}",
            "giorni": ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"],
            "oggi": timezone.localdate(),
        },
    )
