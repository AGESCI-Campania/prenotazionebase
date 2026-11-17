"""Servizi dei listini: scelta della versione applicabile (D-09)."""

import datetime

from .models import Listino, VersioneListino


def versione_applicabile(
    listino: Listino, *, data_richiesta: datetime.date, primo_giorno: datetime.date
) -> VersioneListino | None:
    """Versione di `listino` da applicare a un soggiorno (D-09).

    Tra le versioni già pubblicate alla data della richiesta, quella in vigore il primo giorno
    del soggiorno; vale per tutto il soggiorno. None se nessuna versione è applicabile.
    """
    return (
        VersioneListino.objects.filter(
            listino=listino, pubblicata_il__lte=data_richiesta, valida_dal__lte=primo_giorno
        )
        .order_by("-valida_dal")
        .first()
    )
