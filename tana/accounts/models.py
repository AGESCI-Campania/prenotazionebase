"""Utente di Tana: si identifica con l'email (richiedenti e account di gestione via Sestante).

AUTH_USER_MODEL = "accounts.User": non modificabile dopo la prima migrazione.
I ruoli (Pattuglia, Amministratore, Responsabile, Redazione, Segreteria) arrivano in F1/F3
come nomine separate, con il flag `da_sso` per i ruoli globali di Sestante (D-28).
"""

from typing import Any, ClassVar

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
