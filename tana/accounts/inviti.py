"""Inviti su Sestante per gli account pre-registrati (P-12, contratto SSO di Sestante § 10).

Chi assegna un ruolo a una persona senza account Sestante le fa creare l'account con un invito:
Tana lo chiede a Sestante con il token dell'account di servizio `svc-tana` e manda alla persona
il link. L'account creato vale solo per Tana (lo decide Sestante dal token). Al primo login SSO
il collegamento per email (D-28) lo aggancia all'account pre-registrato, con i ruoli.
"""

import contextlib
import json
import logging
import secrets
import urllib.error
import urllib.request
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import InvitoSestante, User

log = logging.getLogger("tana.inviti")

FLUSSO = "sestante-iscrizione-invito"
DURATA = timedelta(days=7)
# Sotto questo margine si manda un invito nuovo invece di rimandare lo stesso link
MARGINE = timedelta(days=1)
TIMEOUT = 10
PREFISSO_OGGETTO = "[Base Aiello] "


class ErroreSestante(Exception):
    """Sestante non raggiungibile o richiesta rifiutata (dettagli nel log, mai il token)."""


def attivi() -> bool:
    return bool(settings.SESTANTE_INVITI_TOKEN)


def url_sestante() -> str:
    """URL pubblico di Sestante (mai l'alias Docker), ricavato dall'issuer del provider."""
    parti = urlsplit(settings.SOCIAL_SESTANTE_SERVER_URL)
    return f"{parti.scheme}://{parti.netloc}"


def link(invito: InvitoSestante) -> str:
    return f"{url_sestante()}/if/flow/{FLUSSO}/?itoken={invito.uuid}"


def da_invitare(utente: User) -> bool:
    """Chi non è mai entrato con Sestante (con un account Sestante si collega da solo)."""
    return not SocialAccount.objects.filter(user=utente, provider="sestante").exists()


def _chiama(metodo: str, percorso: str, dati: dict[str, Any] | None = None) -> Any:
    richiesta = urllib.request.Request(
        f"{url_sestante()}/api/v3/{percorso}",
        data=json.dumps(dati).encode() if dati is not None else None,
        method=metodo,
        headers={
            "Authorization": f"Bearer {settings.SESTANTE_INVITI_TOKEN}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(richiesta, timeout=TIMEOUT) as risposta:
            corpo = risposta.read()
    except urllib.error.HTTPError as errore:
        log.warning(
            "Sestante: %s %s → HTTP %s %s",
            metodo,
            percorso,
            errore.code,
            errore.read()[:500].decode(errors="replace"),
        )
        raise ErroreSestante(f"Sestante ha risposto con l'errore {errore.code}.") from None
    except (urllib.error.URLError, TimeoutError) as errore:
        log.warning("Sestante: %s %s non riuscita: %s", metodo, percorso, errore)
        raise ErroreSestante("Sestante non è raggiungibile.") from None
    return json.loads(corpo) if corpo else None


def _crea_su_sestante(utente: User, richiesto_da: User) -> tuple[str, Any]:
    flusso = _chiama("GET", f"flows/instances/{FLUSSO}/")["pk"]
    scadenza = timezone.now() + DURATA
    dati: dict[str, Any] = {"email": utente.email, "username": utente.email}
    if nome := utente.get_full_name():
        dati["name"] = nome
    dati["attributes.invito"] = {"piattaforma": "tana", "richiesto_da": richiesto_da.email}
    risposta = _chiama(
        "POST",
        "stages/invitation/invitations/",
        {
            "name": f"tana-{secrets.token_hex(8)}",
            "flow": flusso,
            "single_use": False,
            "expires": scadenza.isoformat(),
            "fixed_data": dati,
        },
    )
    return risposta["pk"], scadenza


def invita(utente: User, *, richiesto_da: User) -> InvitoSestante:
    """Manda alla persona il link per creare l'account Sestante: lo stesso se l'invito è ancora
    valido, altrimenti uno nuovo (il vecchio si revoca). Solleva ErroreSestante."""
    adesso = timezone.now()
    invito = InvitoSestante.objects.filter(utente=utente).first()
    if invito is None or invito.scade_il - adesso < MARGINE:
        uuid, scadenza = _crea_su_sestante(utente, richiesto_da)
        if invito is not None:
            _revoca_su_sestante(invito)
        invito, _ = InvitoSestante.objects.update_or_create(
            utente=utente,
            defaults={"uuid": uuid, "scade_il": scadenza, "inviato_il": adesso},
        )
    invito.inviato_da = richiesto_da
    invito.inviato_il = adesso
    invito.save(update_fields=["inviato_da", "inviato_il"])
    _manda_email(invito)
    return invito


def _revoca_su_sestante(invito: InvitoSestante) -> None:
    # Già scaduto o cancellato su Sestante: niente da revocare. Gli altri errori sono nel log;
    # l'invito resta comunque limitato a Tana e scade da solo
    with contextlib.suppress(ErroreSestante):
        _chiama("DELETE", f"stages/invitation/invitations/{invito.uuid}/")


def revoca(utente: User) -> None:
    """Revoca l'invito ancora aperto (es. tolto l'ultimo ruolo prima dell'iscrizione)."""
    invito = InvitoSestante.objects.filter(utente=utente).first()
    if invito is not None:
        _revoca_su_sestante(invito)
        invito.delete()


def _manda_email(invito: InvitoSestante) -> None:
    utente = invito.utente
    ruoli = ", ".join(
        n.get_ruolo_display() for n in utente.nomine.filter(attiva=True).order_by("ruolo")
    )
    messaggio = EmailMessage(
        PREFISSO_OGGETTO + "Il tuo accesso alla gestione di Tana",
        render_to_string(
            "accounts/email/invito_sestante.txt",
            {
                "link": link(invito),
                "scadenza": timezone.localtime(invito.scade_il),
                "ruoli": ruoli,
                "richiesto_da": invito.inviato_da,
                "accesso": settings.BASE_URL + reverse("account_login"),
                "base_url": settings.BASE_URL,
            },
        ),
        to=[utente.email],
        reply_to=[settings.EMAIL_REPLY_TO],
    )
    transaction.on_commit(messaggio.send)
