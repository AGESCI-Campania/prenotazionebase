"""Permessi di Tana (§6): unica fonte di verità per viste, servizi, PDF ed export."""

from typing import Any

from .models import Ruolo
from .services import ruoli_attivi

# Il responsabile della base ha gli stessi permessi dell'amministratore (§6)
AMMINISTRAZIONE = frozenset({Ruolo.AMMINISTRATORE, Ruolo.RESPONSABILE})
# "Tutto il ruolo Pattuglia (e quindi anche amministratore e responsabile)" (D-26)
PATTUGLIA = AMMINISTRAZIONE | {Ruolo.PATTUGLIA}

PERMESSO_NOTIFICHE = "prenotazioni.ricevi_notifiche_gestione"


def _ha(utente: Any, ruoli: frozenset[str]) -> bool:
    if not getattr(utente, "is_authenticated", False) or not utente.is_active:
        return False
    return utente.is_superuser or bool(ruoli_attivi(utente) & ruoli)


def e_amministrazione(utente: Any) -> bool:
    """Approvare e rifiutare, decisioni discrezionali, blocchi tecnici, listini, configurazione."""
    return _ha(utente, AMMINISTRAZIONE)


def e_pattuglia(utente: Any) -> bool:
    """Verificare acconti, registrare pagamenti, consuntivi, messaggi, arrivi e partenze."""
    return _ha(utente, PATTUGLIA)


def vede_tutte_le_prenotazioni(utente: Any) -> bool:
    """La segreteria vede tutto in sola lettura."""
    return _ha(utente, PATTUGLIA | {Ruolo.SEGRETERIA})


def assegna_ruoli(utente: Any) -> bool:
    return _ha(utente, frozenset({Ruolo.SEGRETERIA}))


def solo_sso(utente: Any) -> bool:
    """Chi ha un ruolo di gestione entra solo con Sestante, mai con la password (P-13).

    Unica eccezione il superutente tecnico di emergenza, che ha la MFA TOTP obbligatoria.
    """
    return not utente.is_superuser and bool(ruoli_attivi(utente))


def e_titolare(utente: Any, prenotazione: Any) -> bool:
    return (
        getattr(utente, "is_authenticated", False)
        and prenotazione.richiedente_id is not None
        and prenotazione.richiedente_id == utente.pk
    )


def vede_info_interne(utente: Any) -> bool:
    """Info interne del sito (D-18, D-20): gruppi con una prenotazione confermata e gestione."""
    if vede_tutte_le_prenotazioni(utente) or _ha(utente, frozenset({Ruolo.REDAZIONE})):
        return True
    if not getattr(utente, "is_authenticated", False) or not utente.is_active:
        return False
    from tana.prenotazioni.models import Prenotazione, Stato

    return Prenotazione.objects.filter(richiedente=utente, stato=Stato.CONFERMATA).exists()
