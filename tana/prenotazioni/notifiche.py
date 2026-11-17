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


def notifica(prenotazione: Prenotazione, evento: str, **contesto: Any) -> None:
    """Prepara le email di `evento` e le invia dopo il commit della transazione."""
    descrizione = EVENTI[evento]
    messaggi = []
    for per_gestione, attivo, destinatari in (
        (False, descrizione.al_richiedente, destinatari_richiedente(prenotazione)),
        (True, descrizione.alla_gestione, destinatari_gestione()),
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
        "causale": conf.causale_bonifico.format(
            numero=prenotazione.numero, gruppo=prenotazione.gruppo
        ),
        "base_url": settings.BASE_URL,
        **extra,
    }
