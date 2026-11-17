"""Disponibilità delle aree (D-05, D-17): calendario pubblico e controllo delle date nel modulo.

Una notte `d` è quella tra il giorno `d` e il giorno dopo: un'occupazione `[arrivo, partenza)`
occupa le notti da arrivo a partenza − 1. Nel calendario ogni giorno ha due metà: la notte
precedente e quella successiva, così arrivi e partenze sono mezze giornate.
"""

import calendar
import datetime
from dataclasses import dataclass, field

from django.db.backends.postgresql.psycopg_any import DateRange

from tana.base.models import Area

from .models import Occupazione

LIBERO = "libero"
OCCUPATO = "occupato"
NON_DISPONIBILE = "non_disponibile"  # prioritarie concesse, esclusive, blocchi tecnici

ETICHETTE = {
    LIBERO: "libero",
    OCCUPATO: "occupato",
    NON_DISPONIBILE: "non disponibile",
}


def _stato(occupazione: Occupazione) -> str:
    if occupazione.tipo != Occupazione.Tipo.PRENOTAZIONE:
        return NON_DISPONIBILE
    prenotazione = occupazione.prenotazione
    if (
        prenotazione
        and prenotazione.categoria.prioritaria
        and prenotazione.categoria_prioritaria_concessa
    ):
        return NON_DISPONIBILE
    return OCCUPATO


def notti(dal: datetime.date, al: datetime.date) -> dict[int, dict[datetime.date, str]]:
    """Stato di ogni notte in `[dal, al)` per area (pk), dalle sole occupazioni attive."""
    stati: dict[int, dict[datetime.date, str]] = {}
    occupazioni = Occupazione.objects.filter(
        attiva=True, periodo__overlap=DateRange(dal, al, "[)")
    ).select_related("prenotazione__categoria")
    for occupazione in occupazioni:
        stato = _stato(occupazione)
        per_area = stati.setdefault(occupazione.area_id, {})
        giorno = max(occupazione.periodo.lower, dal)
        while giorno < min(occupazione.periodo.upper, al):
            # Non disponibile prevale su occupato (es. esclusiva sopra una prenotazione)
            if per_area.get(giorno) != NON_DISPONIBILE:
                per_area[giorno] = stato
            giorno += datetime.timedelta(days=1)
    return stati


@dataclass
class GiornoCalendario:
    data: datetime.date
    nel_mese: bool
    # Per area: (notte precedente, notte successiva)
    aree: list[tuple[Area, str, str]] = field(default_factory=list)


def calendario_mese(anno: int, mese: int) -> list[list[GiornoCalendario]]:
    """Settimane del mese (da lunedì) con lo stato delle due metà di ogni giorno per area."""
    settimane = calendar.Calendar(firstweekday=0).monthdatescalendar(anno, mese)
    primo, ultimo = settimane[0][0], settimane[-1][-1]
    aree = list(Area.objects.all())
    stati = notti(primo - datetime.timedelta(days=1), ultimo + datetime.timedelta(days=1))
    risultato = []
    for settimana in settimane:
        riga = []
        for giorno in settimana:
            elemento = GiornoCalendario(data=giorno, nel_mese=giorno.month == mese)
            for area in aree:
                per_area = stati.get(area.pk, {})
                elemento.aree.append(
                    (
                        area,
                        per_area.get(giorno - datetime.timedelta(days=1), LIBERO),
                        per_area.get(giorno, LIBERO),
                    )
                )
            riga.append(elemento)
        risultato.append(riga)
    return risultato


@dataclass
class EsitoDate:
    """Disponibilità di un periodo richiesto, per il modulo di richiesta."""

    libere: dict[str, bool]  # codice area → libera per tutte le notti
    arrivo_con_partenza: list[str] = field(default_factory=list)  # aree con un gruppo che parte
    partenza_con_arrivo: list[str] = field(default_factory=list)  # aree con un gruppo che arriva

    @property
    def tutte_libere(self) -> bool:
        return all(self.libere.values())


def verifica_date(arrivo: datetime.date, partenza: datetime.date, codici: list[str]) -> EsitoDate:
    """Le aree sono libere per `[arrivo, partenza)`? E chi c'è nei giorni di cambio (D-04)?"""
    aree = {a.codice: a for a in Area.objects.filter(codice__in=codici)}
    stati = notti(arrivo - datetime.timedelta(days=1), partenza + datetime.timedelta(days=1))
    esito = EsitoDate(libere={})
    for codice, area in aree.items():
        per_area = stati.get(area.pk, {})
        giorno, libera = arrivo, True
        while giorno < partenza:
            libera = libera and giorno not in per_area
            giorno += datetime.timedelta(days=1)
        esito.libere[codice] = libera
        if arrivo - datetime.timedelta(days=1) in per_area:
            esito.arrivo_con_partenza.append(area.nome)
        if partenza in per_area:
            esito.partenza_con_arrivo.append(area.nome)
    return esito
