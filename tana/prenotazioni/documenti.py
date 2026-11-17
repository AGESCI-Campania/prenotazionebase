"""Documenti PDF della prenotazione (D-19): preventivo, conferma, consuntivo con ricevuta.

Si generano al momento (cambiano con la prenotazione); il regolamento invece ha il suo PDF per
versione (`tana.sito.regolamento`).
"""

from typing import Any

from django.utils import timezone

from tana.base.models import Configurazione
from tana.core.pdf import genera

from . import contributo
from .models import Prenotazione

TIPI = {
    "preventivo": "Preventivo",
    "conferma": "Conferma di prenotazione",
    "consuntivo": "Consuntivo e ricevuta",
}


def disponibili(prenotazione: Prenotazione) -> list[str]:
    """Documenti che hanno senso nello stato della prenotazione."""
    tipi = ["preventivo"]
    if prenotazione.stato in ("CONFERMATA", "SVOLTA", "CHIUSA"):
        tipi.append("conferma")
    if prenotazione.righe_importo.filter(fase=contributo.Fase.CONSUNTIVO).exists():
        tipi.append("consuntivo")
    return tipi


def nome_file(prenotazione: Prenotazione, tipo: str) -> str:
    return f"{tipo}-{prenotazione.numero}.pdf"


def pdf(prenotazione: Prenotazione, tipo: str) -> bytes:
    if tipo not in TIPI:
        raise ValueError(tipo)
    conf = Configurazione.corrente()
    contesto: dict[str, Any] = {
        "p": prenotazione,
        "titolo": TIPI[tipo],
        "conf": conf,
        "causale": conf.causale(prenotazione.numero, prenotazione.gruppo),
        "oggi": timezone.localdate(),
        "presenze": prenotazione.presenze.select_related("area").order_by("area__ordine"),
        "attivita": prenotazione.attivita_giornaliere.order_by("data"),
        "preventivo": contributo.riepilogo(prenotazione),
        "consuntivo": contributo.riepilogo(prenotazione, contributo.Fase.CONSUNTIVO),
        "pagamenti": prenotazione.pagamenti.filter(stato="VERIFICATO").order_by("data", "pk"),
        "acconto_versato": contributo.acconto_versato(prenotazione),
        "saldo": contributo.saldo(prenotazione),
        "versato": contributo.totale_versato(prenotazione),
    }
    totale = contesto["consuntivo"].totale
    contesto["da_versare"] = None if totale is None else max(totale - contesto["versato"], 0)
    return genera(f"pdf/{tipo}.html", contesto)
