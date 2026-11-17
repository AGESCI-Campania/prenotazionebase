"""Filtri di logging."""

import logging


def non_manutenzione(record: logging.LogRecord) -> bool:
    """Scarta le risposte 503: le dà solo la pagina di manutenzione, voluta durante gli
    aggiornamenti; senza filtro ogni richiesta (es. il service worker) manda una email."""
    return getattr(record, "status_code", None) != 503
