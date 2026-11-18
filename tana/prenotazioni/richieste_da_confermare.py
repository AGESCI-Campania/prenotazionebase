"""Richieste senza account con la verifica dell'email (D-33).

Chi non ha fatto l'accesso compila la richiesta come tutti; all'invio i dati restano qui e il
referente riceve un link. Al clic (pagina con un pulsante: i controlli antivirus della posta
aprono i link da soli) nasce la prenotazione con lo stesso flusso di sempre, sull'account con
quell'email, creato se manca: l'email è verificata dal clic.
"""

import datetime
import secrets
from typing import Any

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from tana.accounts.models import User

from .models import RichiestaDaConfermare
from .notifiche import PREFISSO_OGGETTO

VALIDITA = datetime.timedelta(hours=24)
MASSIMO_PER_EMAIL = 3  # richieste non confermate per email nelle 24 ore (abusi)


def crea(email: str, dati: dict[str, Any]) -> RichiestaDaConfermare:
    """Salva la richiesta e manda il link di conferma (dopo il commit)."""
    recenti = RichiestaDaConfermare.objects.filter(
        email__iexact=email,
        confermata_il__isnull=True,
        creata_il__gte=timezone.now() - VALIDITA,
    )
    if recenti.count() >= MASSIMO_PER_EMAIL:
        raise ValidationError(
            "Ci sono già altre richieste da confermare per questo indirizzo: controlla la tua "
            "email (anche nella posta indesiderata) e usa uno dei link ricevuti."
        )
    richiesta = RichiestaDaConfermare.objects.create(
        token=secrets.token_urlsafe(32), email=email, dati=dati
    )
    link = settings.BASE_URL.rstrip("/") + reverse(
        "prenotazioni:conferma_richiesta", kwargs={"token": richiesta.token}
    )
    messaggio = EmailMessage(
        PREFISSO_OGGETTO + "Conferma la tua richiesta di prenotazione",
        render_to_string(
            "prenotazioni/email/conferma_richiesta.txt",
            {
                "link": link,
                "ore": int(VALIDITA.total_seconds() // 3600),
                "base_url": settings.BASE_URL,
            },
        ),
        to=[email],
        reply_to=[settings.EMAIL_REPLY_TO],
    )
    transaction.on_commit(messaggio.send)
    return richiesta


def valida(token: str) -> RichiestaDaConfermare | None:
    """La richiesta del link, se esiste, non è scaduta e non è già stata confermata."""
    return RichiestaDaConfermare.objects.filter(
        token=token, confermata_il__isnull=True, creata_il__gte=timezone.now() - VALIDITA
    ).first()


def account(email: str) -> User:
    """L'account con quell'email, creato se manca, con l'email verificata."""
    utente = User.objects.filter(email__iexact=email).first()
    if utente is None:
        utente = User.objects.create_user(email)  # senza password: «Password dimenticata?»
    indirizzo, _ = EmailAddress.objects.get_or_create(
        user=utente, email__iexact=email, defaults={"email": email}
    )
    if not indirizzo.verified:
        indirizzo.verified = True
        indirizzo.primary = not EmailAddress.objects.filter(user=utente, primary=True).exists()
        indirizzo.save()
    return utente


def accesso_automatico(utente: User) -> bool:
    """Accesso con il solo link solo per gli account dei gruppi: chi ha un ruolo (o è il
    superutente) entra con SSO o password e verifica in due passaggi."""
    return not (utente.is_superuser or utente.nomine.filter(attiva=True).exists())


def pulisci() -> int:
    """Scadenza dello scheduler: via le richieste più vecchie della validità (dati minimi)."""
    eliminate, _ = RichiestaDaConfermare.objects.filter(
        creata_il__lt=timezone.now() - VALIDITA
    ).delete()
    return eliminate
