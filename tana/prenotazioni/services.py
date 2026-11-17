"""Servizi delle prenotazioni: numerazione e occupazioni delle aree (D-05).

Le occupazioni si derivano sempre da qui: viste, comandi e import non le scrivono a mano.
"""

import datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.backends.postgresql.psycopg_any import DateRange
from django.utils import timezone

from tana.base.models import Area

from .models import STATI_ATTIVI, BloccoTecnico, ContatoreNumeri, Occupazione, Prenotazione

VINCOLO_NON_SOVRAPPOSIZIONE = "occupazioni_non_sovrapposte"


class DateOccupate(ValidationError):
    """Le date chieste si sovrappongono a un'occupazione attiva della stessa area."""

    def __init__(self) -> None:
        super().__init__("Le date scelte si sovrappongono a un'altra prenotazione o a un blocco.")


@transaction.atomic
def assegna_numero(anno: int) -> str:
    """Prossimo numero `AAAA-NNN` per `anno`; i numeri non si riusano mai."""
    contatore, _ = ContatoreNumeri.objects.select_for_update().get_or_create(anno=anno)
    contatore.ultimo += 1
    contatore.save(update_fields=["ultimo"])
    return f"{anno}-{contatore.ultimo:03d}"


def crea_prenotazione(**campi: Any) -> Prenotazione:
    """Crea una prenotazione con il numero dell'anno corrente. Le presenze si aggiungono dopo,
    seguite da `sincronizza_occupazioni`."""
    with transaction.atomic():
        numero = assegna_numero(timezone.localdate().year)
        return Prenotazione.objects.create(numero=numero, **campi)


def _salva_occupazioni(operazione: Any) -> None:
    # Traduce la violazione dell'exclusion constraint in un errore per l'utente
    try:
        with transaction.atomic():
            operazione()
    except IntegrityError as errore:
        nome = getattr(getattr(errore.__cause__, "diag", None), "constraint_name", "")
        if nome == VINCOLO_NON_SOVRAPPOSIZIONE:
            raise DateOccupate from errore
        raise


def occupazioni_attese(prenotazione: Prenotazione) -> dict[int, str]:
    """Aree che la prenotazione occupa, con il tipo di occupazione.

    Ogni area con persone occupa `[arrivo, partenza)`; l'esclusiva concessa (solo
    accantonamento, D-03) occupa anche l'area tende senza persone. Le attività in giornata non
    occupano aree (P-05).
    """
    if prenotazione.partenza <= prenotazione.arrivo:
        return {}
    attese: dict[int, str] = {
        p.area_id: Occupazione.Tipo.PRENOTAZIONE for p in prenotazione.presenze.all()
    }
    if prenotazione.esclusiva_concessa:
        tende = Area.objects.get(codice=Area.TENDE)
        if tende.pk in attese:
            raise ValidationError("L'esclusiva si concede solo a chi prenota l'accantonamento.")
        attese[tende.pk] = Occupazione.Tipo.ESCLUSIVA
    return attese


def sincronizza_occupazioni(prenotazione: Prenotazione) -> None:
    """Allinea le occupazioni a presenze, date, esclusiva e stato della prenotazione.

    Solleva `DateOccupate` se le date non sono libere (vincolo del database).
    """
    attese = occupazioni_attese(prenotazione)
    periodo = DateRange(prenotazione.arrivo, prenotazione.partenza, "[)")
    attiva = prenotazione.stato in STATI_ATTIVI

    def operazione() -> None:
        prenotazione.occupazioni.exclude(area_id__in=attese).delete()
        for area_id, tipo in attese.items():
            Occupazione.objects.update_or_create(
                prenotazione=prenotazione,
                area_id=area_id,
                defaults={"tipo": tipo, "periodo": periodo, "attiva": attiva},
            )

    _salva_occupazioni(operazione)


def crea_blocco(
    *, area: Area, dal: datetime.date, al: datetime.date, motivo: str, utente: Any = None
) -> BloccoTecnico:
    """Blocca un'area dal giorno `dal` al giorno `al` inclusi.

    Solleva `DateOccupate` se il periodo non è libero.
    """
    if al < dal:
        raise ValidationError({"al": "L'ultimo giorno non può precedere il primo."})
    risultato: list[BloccoTecnico] = []

    def operazione() -> None:
        blocco = BloccoTecnico.objects.create(
            area=area, dal=dal, al=al, motivo=motivo, creato_da=utente
        )
        Occupazione.objects.create(
            tipo=Occupazione.Tipo.BLOCCO,
            area=area,
            periodo=DateRange(dal, al + datetime.timedelta(days=1), "[)"),
            blocco=blocco,
        )
        risultato.append(blocco)

    _salva_occupazioni(operazione)
    return risultato[0]
