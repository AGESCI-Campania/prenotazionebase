"""Utente di Tana: si identifica con l'email (richiedenti e account di gestione via Sestante).

AUTH_USER_MODEL = "accounts.User": non modificabile dopo la prima migrazione.
I ruoli di gestione sono nomine (§6, P-12): ogni ruolo è anche un gruppo Django con lo stesso
nome, così i permessi (es. le notifiche di gestione) si assegnano ai ruoli dall'admin. Le nomine
`da_sso` sono i ruoli globali di Sestante, ricalcolati a ogni login SSO (D-28).
"""

from typing import Any, ClassVar

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra: Any) -> User:
        if not email:
            raise ValueError("L'email è obbligatoria.")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra: Any) -> User:
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra: Any) -> User:
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    username = None  # type: ignore[assignment]
    email = models.EmailField("email", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects: ClassVar[UserManager] = UserManager()  # type: ignore[assignment]

    class Meta:
        verbose_name = "utente"
        verbose_name_plural = "utenti"

    def __str__(self) -> str:
        return self.email


class Ruolo(models.TextChoices):
    PATTUGLIA = "PATTUGLIA", "Pattuglia"
    AMMINISTRATORE = "AMMINISTRATORE", "Amministratore"
    RESPONSABILE = "RESPONSABILE", "Responsabile della base"
    REDAZIONE = "REDAZIONE", "Redazione"
    SEGRETERIA = "SEGRETERIA", "Segreteria regionale"


class Nomina(models.Model):
    """Ruolo di gestione di un utente. Più persone possono avere lo stesso ruolo (diarchia)."""

    utente = models.ForeignKey(User, on_delete=models.CASCADE, related_name="nomine")
    ruolo = models.CharField(max_length=20, choices=Ruolo.choices)
    da_sso = models.BooleanField(
        "da Sestante", default=False, help_text="Ruolo globale dal claim groups di Sestante."
    )
    attiva = models.BooleanField(default=True)
    assegnata_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    assegnata_il = models.DateTimeField(auto_now_add=True)
    aggiornata_il = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "nomina"
        verbose_name_plural = "nomine"
        ordering = ("utente", "ruolo")
        constraints = (
            # Una sola nomina attiva per ruolo e origine (locale o Sestante)
            models.UniqueConstraint(
                fields=("utente", "ruolo", "da_sso"),
                condition=models.Q(attiva=True),
                name="nomina_attiva_unica",
            ),
        )

    def __str__(self) -> str:
        origine = " (Sestante)" if self.da_sso else ""
        return f"{self.utente}: {self.get_ruolo_display()}{origine}"
