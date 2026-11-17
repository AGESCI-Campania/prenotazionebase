"""Notifiche email delle prenotazioni (D-19): a ogni cambio di stato, al richiedente e alla
gestione.

La gestione è la casella della base (EMAIL_REPLY_TO) più gli utenti con il permesso
`prenotazioni.ricevi_notifiche_gestione`, assegnabile ai ruoli dall'admin. Le email partono solo
a transazione confermata.
"""

import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse

from tana.accounts.models import User
from tana.accounts.permessi import PERMESSO_NOTIFICHE
from tana.base.models import Configurazione

from . import contributo
from .models import Prenotazione

log = logging.getLogger("tana.notifiche")

PREFISSO_OGGETTO = "[Base Aiello] "


@dataclass(frozen=True)
class Evento:
    oggetto: str
    al_richiedente: bool = True
    alla_gestione: bool = True


EVENTI = {
    "richiesta_inviata": Evento("Richiesta di prenotazione {numero} ricevuta"),
    "approvata": Evento("Prenotazione {numero} approvata"),
    "rifiutata": Evento("Richiesta di prenotazione {numero} non accolta"),
    "annullata": Evento("Prenotazione {numero} annullata"),
    "ricevuta_caricata": Evento("Ricevuta dell'acconto {numero} da verificare", False, True),
    "ricevuta_respinta": Evento("Ricevuta dell'acconto {numero} da ricaricare"),
    "confermata": Evento("Prenotazione {numero} confermata"),
    "scaduta": Evento("Prenotazione {numero} scaduta"),
    "svolta": Evento("Grazie per il soggiorno alla base ({numero})"),
    "chiusa": Evento("Consuntivo della prenotazione {numero}"),
    "consenso_richiesto": Evento("Richiesta di consenso per la prenotazione {numero}"),
    "consenso_risposta": Evento("Risposta alla richiesta di consenso ({numero})"),
    "messaggio": Evento("Nuovo messaggio sulla prenotazione {numero}"),
    "modificata": Evento("Prenotazione {numero} modificata"),
    "orari": Evento("Orari concordati per la prenotazione {numero}"),
    "pagamento": Evento("Pagamento registrato per la prenotazione {numero}"),
    "telefono_richiesto": Evento("Richiesta del tuo telefono ({numero})", True, False),
    "telefono_risposta": Evento("Risposta alla richiesta del telefono ({numero})", True, False),
}


def destinatari_richiedente(prenotazione: Prenotazione) -> list[str]:
    indirizzi = []
    if prenotazione.contatto and prenotazione.contatto.email:
        indirizzi.append(prenotazione.contatto.email)
    if prenotazione.richiedente and prenotazione.richiedente.email:
        indirizzi.append(prenotazione.richiedente.email)
    return _unici(indirizzi)


def destinatari_gestione() -> list[str]:
    # Permesso dai gruppi dei ruoli o assegnato all'utente; i superutenti non contano
    app, codice = PERMESSO_NOTIFICHE.split(".")
    permesso = Permission.objects.get(content_type__app_label=app, codename=codice)
    utenti = User.objects.filter(
        Q(groups__permissions=permesso) | Q(user_permissions=permesso), is_active=True
    ).distinct()
    indirizzi = [settings.EMAIL_REPLY_TO, *utenti.values_list("email", flat=True)]
    return _unici([i for i in indirizzi if i])


def _unici(indirizzi: list[str]) -> list[str]:
    visti: dict[str, str] = {}
    for indirizzo in indirizzi:
        visti.setdefault(indirizzo.lower(), indirizzo)
    return list(visti.values())


def notifica(
    prenotazione: Prenotazione,
    evento: str,
    *,
    al_richiedente: bool | None = None,
    alla_gestione: bool | None = None,
    **contesto: Any,
) -> None:
    """Prepara le email di `evento` e le invia dopo il commit della transazione.

    `al_richiedente` e `alla_gestione` sostituiscono i destinatari di default dell'evento.
    """
    descrizione = EVENTI[evento]
    if al_richiedente is None:
        al_richiedente = descrizione.al_richiedente
    if alla_gestione is None:
        alla_gestione = descrizione.alla_gestione
    messaggi = []
    for per_gestione, attivo, destinatari in (
        (False, al_richiedente, destinatari_richiedente(prenotazione)),
        (True, alla_gestione, destinatari_gestione()),
    ):
        if not attivo or not destinatari:
            continue
        corpo = render_to_string(
            f"prenotazioni/email/{evento}.txt",
            _contesto(prenotazione, per_gestione=per_gestione, **contesto),
        )
        messaggi.append(
            EmailMessage(
                PREFISSO_OGGETTO + descrizione.oggetto.format(numero=prenotazione.numero),
                corpo,
                to=destinatari,
                reply_to=[settings.EMAIL_REPLY_TO],
            )
        )
    transaction.on_commit(lambda: _invia(messaggi))


def _invia(messaggi: list[EmailMessage]) -> None:
    for messaggio in messaggi:
        try:
            messaggio.send()
        except Exception:  # un SMTP non raggiungibile non annulla il cambio di stato
            log.exception("Email non inviata: %s", messaggio.subject)


def _contesto(prenotazione: Prenotazione, **extra: Any) -> dict[str, Any]:
    conf = Configurazione.corrente()
    preventivo = contributo.riepilogo(prenotazione, contributo.Fase.PREVENTIVO)
    return {
        "p": prenotazione,
        "presenze": prenotazione.presenze.select_related("area").order_by("area__ordine"),
        "attivita": prenotazione.attivita_giornaliere.order_by("data"),
        "preventivo": preventivo,
        "conf": conf,
        "causale": conf.causale(prenotazione.numero, prenotazione.gruppo),
        "base_url": settings.BASE_URL,
        "link": settings.BASE_URL.rstrip("/")
        + reverse("prenotazioni:dettaglio", kwargs={"numero": prenotazione.numero}),
        **extra,
    }
