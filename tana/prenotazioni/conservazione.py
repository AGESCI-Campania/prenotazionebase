"""Conservazione dei dati personali (D-18): dopo `anni_conservazione` (10) dalla fine dell'anno
di partenza i dati personali delle prenotazioni si anonimizzano; restano numero, categoria,
gruppo, date, presenze, importi e pagamenti (statistiche e contabilità).
"""

import datetime

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from tana.base.models import Configurazione
from tana.core.services import registra_evento

from .models import Contatto, Conversazione, Prenotazione

ANONIMO = "anonimizzato"


def da_anonimizzare(oggi: datetime.date | None = None) -> QuerySet[Prenotazione]:
    """Prenotazioni con la partenza in un anno chiuso da più di `anni_conservazione` anni."""
    oggi = oggi or timezone.localdate()
    anni = Configurazione.corrente().anni_conservazione
    # Partenza nel 2016, 10 anni: si anonimizza dal 1/1/2027 (dopo il 31/12/2026)
    ultimo_anno = oggi.year - anni - 1
    return Prenotazione.objects.filter(
        anonimizzata_il__isnull=True, partenza__year__lte=ultimo_anno
    )


def _anonimizza_contatto(contatto: Contatto | None) -> None:
    if contatto is None:
        return
    # Un contatto condiviso con prenotazioni ancora da conservare resta com'è
    if contatto.prenotazioni.filter(anonimizzata_il__isnull=True).exists():
        return
    if contatto.prenotazioni_come_capo.filter(anonimizzata_il__isnull=True).exists():
        return
    contatto.nome, contatto.email, contatto.telefono = ANONIMO, "", ""
    contatto.save()


@transaction.atomic
def anonimizza(prenotazione: Prenotazione) -> None:
    contatti = [prenotazione.contatto, prenotazione.capo_responsabile]
    for pagamento in prenotazione.pagamenti.exclude(ricevuta=""):
        pagamento.ricevuta.delete(save=True)
    Conversazione.objects.filter(prenotazione=prenotazione).delete()
    Conversazione.objects.filter(con=prenotazione).delete()
    prenotazione.telefoni_chiesti.all().delete()
    prenotazione.telefoni_richiesti.all().delete()
    prenotazione.richiedente = None
    prenotazione.note = ""
    prenotazione.anonimizzata_il = timezone.now()
    prenotazione.save()
    for contatto in contatti:
        _anonimizza_contatto(contatto)
    registra_evento(prenotazione, "dati personali anonimizzati (D-18)")


def anonimizza_scadute() -> int:
    """Servizio scheduler: anonimizza le prenotazioni oltre il periodo di conservazione."""
    quante = 0
    for prenotazione in da_anonimizzare():
        anonimizza(prenotazione)
        quante += 1
    return quante
