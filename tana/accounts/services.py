"""Ruoli di gestione: nomine e gruppi Django collegati (§6, P-12, D-28)."""

from typing import Any

from django.contrib.auth.models import Group
from django.db import transaction

from .models import Nomina, Ruolo, User

# Claim `groups` di Sestante → ruolo globale di Tana (D-28); gli altri gruppi si ignorano
RUOLI_DA_SESTANTE = {
    "admin-multipiattaforma": Ruolo.AMMINISTRATORE,
    "segreteria": Ruolo.SEGRETERIA,
}


def gruppo(ruolo: str) -> Group:
    """Gruppo Django del ruolo (stesso nome dell'etichetta)."""
    gruppo, _ = Group.objects.get_or_create(name=Ruolo(ruolo).label)
    return gruppo


def ruoli_attivi(utente: User) -> set[str]:
    if not utente.is_authenticated:
        return set()
    return set(utente.nomine.filter(attiva=True).values_list("ruolo", flat=True))


def allinea_gruppi(utente: User) -> None:
    """L'utente è nei gruppi dei ruoli con almeno una nomina attiva, e solo in quelli.

    Nell'admin Django entra solo il superutente tecnico (`is_staff`): strutture e categorie si
    modificano nell'editor del sito e nella gestione.
    """
    attivi = ruoli_attivi(utente)
    for ruolo in Ruolo:
        if ruolo in attivi:
            utente.groups.add(gruppo(ruolo))
        else:
            utente.groups.remove(gruppo(ruolo))
    staff = utente.is_superuser
    if utente.is_staff != staff:
        utente.is_staff = staff
        utente.save(update_fields=["is_staff"])


@transaction.atomic
def nomina(utente: User, ruolo: str, *, assegnata_da: Any = None) -> Nomina:
    """Assegna un ruolo locale (lo fa la segreteria, P-12)."""
    esistente = utente.nomine.filter(ruolo=ruolo, da_sso=False, attiva=True).first()
    risultato = esistente or Nomina.objects.create(
        utente=utente, ruolo=ruolo, assegnata_da=assegnata_da
    )
    allinea_gruppi(utente)
    return risultato


@transaction.atomic
def revoca(utente: User, ruolo: str) -> None:
    """Revoca un ruolo locale; le nomine da Sestante le gestisce solo il login SSO."""
    utente.nomine.filter(ruolo=ruolo, da_sso=False, attiva=True).update(attiva=False)
    allinea_gruppi(utente)


@transaction.atomic
def allinea_ruoli_globali(utente: User, groups: list[str]) -> None:
    """Ruoli globali dal claim `groups` di Sestante, ricalcolati a ogni login SSO (D-28).

    Crea le nomine `da_sso` mancanti e revoca quelle non più nel claim; le nomine locali non si
    toccano mai.
    """
    attesi = {RUOLI_DA_SESTANTE[g] for g in groups if g in RUOLI_DA_SESTANTE}
    nomine_sso = utente.nomine.filter(da_sso=True, attiva=True)
    nomine_sso.exclude(ruolo__in=attesi).update(attiva=False)
    presenti = set(nomine_sso.values_list("ruolo", flat=True))
    for ruolo in attesi - presenti:
        Nomina.objects.create(utente=utente, ruolo=ruolo, da_sso=True)
    allinea_gruppi(utente)
