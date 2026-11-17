"""Consenso del gruppo presente (D-06, P-05).

Un'attività in giornata in un giorno in cui un'altra prenotazione attiva ha il gruppo in base
(compresi i giorni di arrivo e di partenza) o un'altra attività in giornata chiede il consenso a
chi ha prenotato prima. Termine: `consenso_giorni` dalla domanda, non oltre la fine della
vigilia; se la domanda arriva la vigilia o il giorno stesso, le 8:00 del giorno dell'attività.
Senza risposta il consenso è negato;
la richiesta resta all'amministrazione, che la rifiuta (non c'è rifiuto automatico).
"""

import datetime
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from tana.accounts import permessi
from tana.base.models import Configurazione
from tana.core.services import registra_evento

from . import notifiche
from .models import STATI_ATTIVI, Prenotazione, RichiestaConsenso, Stato

StatoConsenso = RichiestaConsenso.StatoConsenso
ORA_DEL_GIORNO_STESSO = datetime.time(8, 0)


def presenti(data: datetime.date, *, escludi: Prenotazione | None = None) -> QuerySet[Prenotazione]:
    """Prenotazioni attive con il gruppo in base il giorno `data`."""
    soggiorni = Q(presenze__isnull=False, arrivo__lte=data, partenza__gte=data)
    giornate = Q(attivita_giornaliere__data=data)
    risultato = Prenotazione.objects.filter(stato__in=STATI_ATTIVI).filter(soggiorni | giornate)
    if escludi is not None:
        risultato = risultato.exclude(pk=escludi.pk)
    return risultato.distinct()


def termine(data: datetime.date, adesso: datetime.datetime | None = None) -> datetime.datetime:
    """Scadenza della risposta per un'attività del giorno `data`."""
    adesso = adesso or timezone.now()
    giorni = Configurazione.corrente().consenso_giorni
    inizio_giorno = timezone.make_aware(datetime.datetime.combine(data, datetime.time.min))
    inizio_vigilia = inizio_giorno - datetime.timedelta(days=1)
    if adesso < inizio_vigilia:
        scadenza = min(adesso + datetime.timedelta(days=giorni), inizio_giorno)
    else:
        scadenza = timezone.make_aware(datetime.datetime.combine(data, ORA_DEL_GIORNO_STESSO))
    if scadenza <= adesso:
        raise ValidationError(
            {"attivita": "È troppo tardi per chiedere il consenso al gruppo già presente."}
        )
    return scadenza


def chiedi_consensi(prenotazione: Prenotazione) -> list[RichiestaConsenso]:
    """Domande di consenso per le attività in giornata della richiesta: alla creazione e dopo
    una modifica delle date (solo a chi ha prenotato prima e non è già stato interpellato)."""
    adesso = timezone.now()
    scadenze: dict[int, datetime.datetime] = {}
    esistenti: dict[int, Prenotazione] = {}
    gia_chiesti = set(
        prenotazione.consensi_chiesti.values_list("prenotazione_esistente", flat=True)
    )
    for attivita in prenotazione.attivita_giornaliere.all():
        prima = presenti(attivita.data, escludi=prenotazione).filter(
            creata_il__lt=prenotazione.creata_il
        )
        for presente in prima.exclude(pk__in=gia_chiesti):
            scadenza = termine(attivita.data, adesso)
            scadenze[presente.pk] = min(scadenze.get(presente.pk, scadenza), scadenza)
            esistenti[presente.pk] = presente
    domande = []
    for pk, esistente in esistenti.items():
        domanda = RichiestaConsenso.objects.create(
            richiesta=prenotazione, prenotazione_esistente=esistente, scadenza=scadenze[pk]
        )
        domande.append(domanda)
        registra_evento(prenotazione, "consenso chiesto", dopo={"a": esistente.numero})
        notifiche.notifica(esistente, "consenso_richiesto", domanda=domanda)
    return domande


def puo_rispondere(utente: Any, domanda: RichiestaConsenso) -> bool:
    """Risponde il titolare della prenotazione esistente; se non ha un titolare (prioritarie
    inserite dalla gestione) risponde l'amministrazione."""
    esistente = domanda.prenotazione_esistente
    if esistente.richiedente_id is None:
        return permessi.e_amministrazione(utente)
    return permessi.e_titolare(utente, esistente)


@transaction.atomic
def rispondi(domanda: RichiestaConsenso, *, utente: Any, concesso: bool) -> RichiestaConsenso:
    if not puo_rispondere(utente, domanda):
        raise PermissionDenied("Solo il gruppo già presente può rispondere.")
    domanda = RichiestaConsenso.objects.select_for_update().get(pk=domanda.pk)
    if domanda.stato != StatoConsenso.IN_ATTESA or domanda.richiesta.stato != Stato.RICHIESTA:
        raise ValidationError("Questa richiesta di consenso non attende più una risposta.")
    if domanda.scadenza <= timezone.now():
        raise ValidationError("Il termine per rispondere è scaduto.")
    domanda.stato = StatoConsenso.CONCESSO if concesso else StatoConsenso.NEGATO
    domanda.risposta_il, domanda.risposto_da = timezone.now(), utente
    domanda.save()
    _esito(domanda, utente)
    return domanda


def _esito(domanda: RichiestaConsenso, utente: Any) -> None:
    for prenotazione in (domanda.richiesta, domanda.prenotazione_esistente):
        registra_evento(
            prenotazione,
            f"consenso {domanda.get_stato_display()}",
            utente=utente,
            dopo={
                "richiesta": domanda.richiesta.numero,
                "esistente": domanda.prenotazione_esistente.numero,
            },
        )
    notifiche.notifica(domanda.richiesta, "consenso_risposta", domanda=domanda)


def scadi_consensi() -> int:
    """Domande senza risposta entro il termine → consenso negato (servizio scheduler)."""
    scadute = 0
    candidate = RichiestaConsenso.objects.filter(
        stato=StatoConsenso.IN_ATTESA, scadenza__lte=timezone.now()
    ).values_list("pk", flat=True)
    for pk in candidate:
        with transaction.atomic():
            domanda = RichiestaConsenso.objects.select_for_update().get(pk=pk)
            if domanda.stato != StatoConsenso.IN_ATTESA:
                continue
            domanda.stato = StatoConsenso.SCADUTO
            domanda.save(update_fields=["stato"])
            if domanda.richiesta.stato == Stato.RICHIESTA:
                _esito(domanda, None)
            scadute += 1
    return scadute


def mancanti(prenotazione: Prenotazione) -> QuerySet[RichiestaConsenso]:
    """Consensi non (ancora) concessi da prenotazioni ancora attive: bloccano l'approvazione."""
    return prenotazione.consensi_chiesti.exclude(stato=StatoConsenso.CONCESSO).filter(
        prenotazione_esistente__stato__in=STATI_ATTIVI
    )


def da_rispondere(utente: Any) -> QuerySet[RichiestaConsenso]:
    """Domande in attesa a cui l'utente deve rispondere come titolare."""
    return RichiestaConsenso.objects.filter(
        stato=StatoConsenso.IN_ATTESA,
        richiesta__stato=Stato.RICHIESTA,
        prenotazione_esistente__richiedente=utente,
    ).select_related("richiesta", "prenotazione_esistente")
