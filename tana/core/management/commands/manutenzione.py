"""manage.py manutenzione attiva|disattiva|stato [--messaggio TESTO]

Usato da scripts/aggiorna.sh: l'ultima riga stampata da `stato` è "attiva" o "disattiva".
"""

from django.core.management.base import BaseCommand, CommandParser

from tana.core.models import Manutenzione


class Command(BaseCommand):
    help = "Attiva, disattiva o mostra la manutenzione del sito."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("azione", choices=["attiva", "disattiva", "stato"])
        parser.add_argument("--messaggio", default="", help="Testo mostrato nella pagina 503.")

    def handle(self, *args, azione: str, messaggio: str, **options) -> None:
        stato = Manutenzione.corrente()
        if azione == "attiva":
            stato.attiva = True
            stato.messaggio = messaggio
            stato.save()
        elif azione == "disattiva":
            stato.attiva = False
            stato.messaggio = ""
            stato.save()
        self.stdout.write("attiva" if stato.attiva else "disattiva")
