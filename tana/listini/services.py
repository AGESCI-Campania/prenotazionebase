"""Servizi dei listini: scelta della versione applicabile (D-09)."""

import datetime

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Listino, VersioneListino, VoceListino


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


def listini_in_vigore(
    oggi: datetime.date,
) -> list[tuple[Listino, VersioneListino | None, VersioneListino | None]]:
    """Per ogni listino: la versione in vigore oggi e quella successiva già pubblicata (D-09:
    il nuovo listino si comunica in anticipo)."""
    risultato = []
    for listino in Listino.objects.all():
        pubblicate = listino.versioni.filter(pubblicata_il__lte=oggi)
        corrente = pubblicate.filter(valida_dal__lte=oggi).order_by("-valida_dal").first()
        prossima = pubblicate.filter(valida_dal__gt=oggi).order_by("valida_dal").first()
        risultato.append((listino, corrente, prossima))
    return risultato


@transaction.atomic
def nuova_versione(
    listino: Listino,
    *,
    nome: str,
    pubblicata_il: datetime.date,
    valida_dal: datetime.date,
    copia_da: VersioneListino | None = None,
    note: str = "",
) -> VersioneListino:
    """Nuova versione di un listino (D-09), con le voci copiate da una versione esistente da
    modificare prima dell'uso (le versioni usate non si toccano più)."""
    if valida_dal < pubblicata_il:
        raise ValidationError({"valida_dal": "La validità non può precedere la pubblicazione."})
    versione = VersioneListino.objects.create(
        listino=listino, nome=nome, pubblicata_il=pubblicata_il, valida_dal=valida_dal, note=note
    )
    if copia_da is not None:
        for voce in copia_da.voci.all():
            VoceListino.objects.create(
                versione=versione,
                attivita=voce.attivita,
                area=voce.area,
                stagione=voce.stagione,
                unita=voce.unita,
                importo_centesimi=voce.importo_centesimi,
                descrizione=voce.descrizione,
            )
    return versione
