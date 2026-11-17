"""manage.py scheduler — processo del servizio `scheduler` del compose (P-07, P-11).

Ogni SCHEDULER_INTERVALLO secondi esegue le scadenze periodiche e aggiorna il file di battito
SCHEDULER_BATTITO, controllato dal healthcheck del servizio. Niente Celery né cron sull'host.

Scadenze (sempre servizi di dominio):
- richieste approvate senza ricevuta entro il termine → SCADUTA (D-13);
- prenotazioni confermate con la partenza passata → SVOLTA (§4);
- F4: richieste di consenso senza risposta entro il termine → negate (D-06);
- F5: anonimizzazione dei dati personali dopo 10 anni (D-18).
"""

import logging
import signal
import time
from collections.abc import Callable

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.db import close_old_connections

from tana.prenotazioni.flusso import scadi_acconti, segna_svolte

log = logging.getLogger("tana.scheduler")

# Elenco delle scadenze: funzioni senza argomenti, idempotenti
SCADENZE: list[Callable[[], object]] = [scadi_acconti, segna_svolte]


def esegui_scadenze() -> None:
    for scadenza in SCADENZE:
        try:
            scadenza()
        except Exception:  # una scadenza che fallisce non deve fermare le altre
            log.exception("Scadenza %s non riuscita", getattr(scadenza, "__name__", scadenza))


class Command(BaseCommand):
    help = "Esegue periodicamente le scadenze automatiche di Tana."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--una-volta", action="store_true", help="Un solo giro, poi esce.")

    def handle(self, *args, una_volta: bool, **options) -> None:
        fermati = False

        def _stop(*_: object) -> None:
            nonlocal fermati
            fermati = True

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)
        intervallo = settings.SCHEDULER_INTERVALLO
        log.info("Scheduler avviato (intervallo %ss).", intervallo)
        while not fermati:
            close_old_connections()
            esegui_scadenze()
            settings.SCHEDULER_BATTITO.touch()
            if una_volta:
                break
            for _ in range(intervallo):
                if fermati:
                    break
                time.sleep(1)
        log.info("Scheduler fermato.")
