"""Messaggi e telefoni tra gruppi (D-16).

Un gruppo scrive sempre alla gestione della base; a un altro gruppo solo se le due prenotazioni
attive condividono almeno un giorno (compresi i giorni di cambio) o c'è una domanda di consenso
tra loro. Il telefono dell'altro referente si vede solo se lui lo autorizza.
"""

from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, OuterRef, Q, QuerySet, Subquery
from django.utils import timezone

from tana.accounts import permessi
from tana.core.services import registra_evento

from . import notifiche
from .models import (
    STATI_ATTIVI,
    Contatto,
    Conversazione,
    Messaggio,
    Prenotazione,
    RichiestaConsenso,
    RichiestaTelefono,
)

StatoTelefono = RichiestaTelefono.StatoRichiesta


def gruppi_vicini(prenotazione: Prenotazione) -> QuerySet[Prenotazione]:
    """Altre prenotazioni attive con cui il gruppo può scrivere."""
    if prenotazione.stato not in STATI_ATTIVI:
        return Prenotazione.objects.none()
    giorni_in_comune = Q(arrivo__lte=prenotazione.partenza, partenza__gte=prenotazione.arrivo)
    consensi = RichiestaConsenso.objects.filter(
        Q(richiesta=prenotazione) | Q(prenotazione_esistente=prenotazione)
    )
    legate = set(consensi.values_list("richiesta_id", flat=True)) | set(
        consensi.values_list("prenotazione_esistente_id", flat=True)
    )
    return (
        Prenotazione.objects.filter(stato__in=STATI_ATTIVI)
        .filter(giorni_in_comune | Q(pk__in=legate))
        .exclude(pk=prenotazione.pk)
        .order_by("arrivo")
    )


def con_gestione(prenotazione: Prenotazione) -> Conversazione:
    conversazione, _ = Conversazione.objects.get_or_create(prenotazione=prenotazione, con=None)
    return conversazione


def tra_gruppi(prenotazione: Prenotazione, altra: Prenotazione) -> Conversazione:
    if not gruppi_vicini(prenotazione).filter(pk=altra.pk).exists():
        raise PermissionDenied("Puoi scrivere solo ai gruppi presenti negli stessi giorni.")
    prima, seconda = sorted((prenotazione, altra), key=lambda p: p.pk)
    conversazione, _ = Conversazione.objects.get_or_create(prenotazione=prima, con=seconda)
    return conversazione


def parti(conversazione: Conversazione) -> list[Prenotazione | None]:
    """Le due parti: prenotazioni, oppure None per la gestione."""
    return [conversazione.prenotazione, conversazione.con]


def puo_scrivere(utente: Any, conversazione: Conversazione, da: Prenotazione | None) -> bool:
    if da is None:
        return conversazione.con is None and permessi.e_pattuglia(utente)
    return da in parti(conversazione) and permessi.e_titolare(utente, da)


def conversazioni(prenotazione: Prenotazione) -> QuerySet[Conversazione]:
    return Conversazione.objects.filter(Q(prenotazione=prenotazione) | Q(con=prenotazione))


@transaction.atomic
def invia(
    conversazione: Conversazione, *, utente: Any, testo: str, da: Prenotazione | None
) -> Messaggio:
    """Nuovo messaggio da `da` (None: dalla gestione), con email all'altra parte."""
    if not puo_scrivere(utente, conversazione, da):
        raise PermissionDenied("Non puoi scrivere in questa conversazione.")
    testo = testo.strip()
    if not testo:
        raise ValidationError({"testo": "Scrivi il messaggio."})
    messaggio = Messaggio.objects.create(
        conversazione=conversazione, da_prenotazione=da, mittente=utente, testo=testo
    )
    altra = conversazione.con if da == conversazione.prenotazione else conversazione.prenotazione
    if conversazione.con is None:
        # Con la gestione: email al gruppo se scrive la gestione, alla gestione se scrive il gruppo
        notifiche.notifica(
            conversazione.prenotazione,
            "messaggio",
            al_richiedente=da is None,
            alla_gestione=da is not None,
            messaggio=messaggio,
            mittente=_nome(da),
        )
    elif altra is not None:
        notifiche.notifica(
            altra, "messaggio", alla_gestione=False, messaggio=messaggio, mittente=_nome(da)
        )
    return messaggio


def _nome(prenotazione: Prenotazione | None) -> str:
    if prenotazione is None:
        return "la gestione della base"
    return prenotazione.gruppo or f"la prenotazione {prenotazione.numero}"


def segna_letti(conversazione: Conversazione, *, lettore: Prenotazione | None) -> int:
    """Messaggi dell'altra parte letti da `lettore` (None: la gestione)."""
    messaggi = conversazione.messaggi.filter(letto=False)
    if lettore is None:
        messaggi = messaggi.exclude(da_prenotazione=None)
    else:
        messaggi = messaggi.exclude(da_prenotazione=lettore)
    return messaggi.update(letto=True)


def senza_risposta() -> QuerySet[Conversazione]:
    """Conversazioni con la gestione il cui ultimo messaggio è di un gruppo (per la Pattuglia)."""
    ultimo = Messaggio.objects.filter(conversazione=OuterRef("pk")).order_by("-inviato_il", "-pk")
    return (
        Conversazione.objects.filter(con=None)
        .annotate(
            ultimo_da=Subquery(ultimo.values("da_prenotazione")[:1]),
            ultimo_il=Max("messaggi__inviato_il"),
        )
        .filter(ultimo_da__isnull=False)
        .order_by("ultimo_il")
    )


# --- Telefoni ---------------------------------------------------------------------------


@transaction.atomic
def chiedi_telefono(da: Prenotazione, a: Prenotazione, *, utente: Any) -> RichiestaTelefono:
    if not permessi.e_titolare(utente, da):
        raise PermissionDenied("Non puoi chiedere contatti per questa prenotazione.")
    if not gruppi_vicini(da).filter(pk=a.pk).exists():
        raise PermissionDenied(
            "Puoi chiedere il telefono solo ai gruppi presenti negli stessi giorni."
        )
    richiesta, creata = RichiestaTelefono.objects.get_or_create(da=da, a=a)
    if creata:
        registra_evento(da, "telefono chiesto", utente=utente, dopo={"a": a.numero})
        notifiche.notifica(a, "telefono_richiesto", richiesta_telefono=richiesta, da=_nome(da))
    return richiesta


@transaction.atomic
def rispondi_telefono(
    richiesta: RichiestaTelefono, *, utente: Any, autorizza: bool
) -> RichiestaTelefono:
    if not permessi.e_titolare(utente, richiesta.a):
        raise PermissionDenied("Solo il referente interessato può autorizzare.")
    if richiesta.stato != StatoTelefono.IN_ATTESA:
        raise ValidationError("Hai già risposto a questa richiesta.")
    richiesta.stato = StatoTelefono.AUTORIZZATA if autorizza else StatoTelefono.NEGATA
    richiesta.risposta_il = timezone.now()
    richiesta.save()
    registra_evento(
        richiesta.a,
        f"telefono {richiesta.get_stato_display()}",
        utente=utente,
        dopo={"a": richiesta.da.numero},
    )
    notifiche.notifica(
        richiesta.da, "telefono_risposta", richiesta_telefono=richiesta, da=_nome(richiesta.a)
    )
    return richiesta


def telefoni_visibili(prenotazione: Prenotazione) -> list[tuple[Prenotazione, Contatto]]:
    """Referenti degli altri gruppi che hanno autorizzato a mostrare il telefono."""
    risultato = []
    for richiesta in prenotazione.telefoni_chiesti.filter(
        stato=StatoTelefono.AUTORIZZATA, a__stato__in=STATI_ATTIVI
    ).select_related("a__contatto"):
        if richiesta.a.contatto:
            risultato.append((richiesta.a, richiesta.a.contatto))
    return risultato
