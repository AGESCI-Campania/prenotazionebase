"""Collegamento delle prenotazioni importate da SuperSaaS agli account (§7.2): quando un utente
conferma un'email, o accede con email verificate, le prenotazioni con quel referente diventano sue."""

from typing import Any

from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed, user_logged_in

from .importazione import collega_a_utente


def email_confermata(request: Any, email_address: EmailAddress, **kwargs: Any) -> None:
    collega_a_utente(email_address.user, email_address.email)


def accesso(request: Any, user: Any, **kwargs: Any) -> None:
    for indirizzo in EmailAddress.objects.filter(user=user, verified=True):
        collega_a_utente(user, indirizzo.email)


email_confirmed.connect(email_confermata)
user_logged_in.connect(accesso)
