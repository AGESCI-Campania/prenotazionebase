"""Adapter di allauth per il login unico Sestante e la MFA (D-28, contratto INTEGRAZIONE-SSO.md).

Implementazione di riferimento: Plancia (`apps/accounts/adapters.py`), con il criterio della
MFA del contratto § 6 punto 4: conta il metodo di autenticazione della sessione corrente, mai
l'esistenza di un account Sestante collegato.
"""

from typing import Any

from allauth.core import context as allauth_context
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.mfa.adapter import DefaultMFAAdapter
from allauth.mfa.models import Authenticator
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse

from .avatar import allinea_avatar, estrai_picture
from .models import User
from .services import allinea_ruoli_globali

PROVIDER_SESTANTE = "sestante"


def sessione_da_sestante(request: Any) -> bool:
    """True se nella sessione corrente l'utente si è autenticato con Sestante."""
    session = getattr(request, "session", None)
    if session is None:
        return False
    return any(
        m.get("method") == "socialaccount" and m.get("provider") == PROVIDER_SESTANTE
        for m in session.get("account_authentication_methods", [])
    )


def mfa_obbligatoria(utente: Any) -> bool:
    """Il superutente tecnico di emergenza ha la MFA TOTP obbligatoria (P-13)."""
    return bool(getattr(utente, "is_superuser", False))


def _groups(extra_data: dict) -> list[str]:
    # allauth ≥ 65.11: extra_data = {"userinfo": {...}, "id_token": {...}}
    dati = extra_data.get("userinfo") or extra_data.get("id_token") or extra_data
    groups = dati.get("groups") or []
    return [g for g in groups if isinstance(g, str)]


def _rifiuta(request: Any, messaggio: str) -> None:
    """Interrompe il login SSO senza creare account parziali (contratto § 6 punto 6)."""
    messages.error(request, messaggio)
    raise ImmediateHttpResponse(HttpResponseRedirect(reverse("account_login")))


class TanaSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Sestante: provisioning automatico, collegamento per email, ruoli globali dal claim
    `groups` e immagine del profilo dal claim `picture` a ogni login. Altri provider (se mai aggiunti): solo collegamento."""

    def is_auto_signup_allowed(self, request: Any, sociallogin: Any) -> bool:
        return sociallogin.account.provider == PROVIDER_SESTANTE

    def pre_social_login(self, request: Any, sociallogin: Any) -> None:
        if sociallogin.account.provider != PROVIDER_SESTANTE:
            return
        email = sociallogin.email_addresses[0].email if sociallogin.email_addresses else None
        if not email:
            _rifiuta(
                request,
                "Il tuo account SSO AGESCI Campania non ha un indirizzo email: chiedi alla "
                "Segreteria regionale di aggiungerlo.",
            )
        # Prima di ogni salvataggio dell'account: il data-URI dell'immagine non va in extra_data
        sociallogin.picture_sestante = estrai_picture(sociallogin.account.extra_data)
        # Sestante verifica le email dei suoi utenti: niente nuova conferma
        for indirizzo in sociallogin.email_addresses:
            indirizzo.verified = True
        if not sociallogin.is_existing:
            utenti = list(User.objects.filter(email__iexact=email)[:2])
            if len(utenti) > 1:
                _rifiuta(
                    request,
                    f"Più account di Tana usano l'indirizzo {email}: contatta la Segreteria "
                    "regionale per unificarli.",
                )
            if utenti:
                sociallogin.connect(request, utenti[0])
        if sociallogin.is_existing:
            allinea_ruoli_globali(sociallogin.user, _groups(sociallogin.account.extra_data))
            allinea_avatar(sociallogin.user, sociallogin.picture_sestante)

    def save_user(self, request: Any, sociallogin: Any, form: Any = None) -> Any:
        da_sestante = sociallogin.account.provider == PROVIDER_SESTANTE
        if da_sestante and not hasattr(sociallogin, "picture_sestante"):
            sociallogin.picture_sestante = estrai_picture(sociallogin.account.extra_data)
        utente = super().save_user(request, sociallogin, form=form)
        if da_sestante:
            allinea_ruoli_globali(utente, _groups(sociallogin.account.extra_data))
            allinea_avatar(utente, sociallogin.picture_sestante)
        return utente


class TanaMFAAdapter(DefaultMFAAdapter):
    def is_mfa_enabled(self, user: Any, types: Any = None) -> bool:
        # Durante il login con Sestante la MFA l'ha già chiesta l'IdP: niente secondo codice.
        # Solo nella pipeline di login (utente non ancora autenticato nella sessione).
        request = allauth_context.request
        if (
            request is not None
            and not request.user.is_authenticated
            and sessione_da_sestante(request)
        ):
            return False
        return super().is_mfa_enabled(user, types=types)

    def can_delete_authenticator(self, authenticator: Any) -> bool:
        # Il TOTP obbligatorio non si rimuove; i codici di recupero sì (si rigenerano)
        if mfa_obbligatoria(authenticator.user):
            return authenticator.type != Authenticator.Type.TOTP
        return super().can_delete_authenticator(authenticator)
