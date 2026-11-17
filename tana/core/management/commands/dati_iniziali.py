"""manage.py dati_iniziali — dati di partenza, idempotente (lanciato da scripts/installa.sh).

F0: nessun dato ancora. In F1 crea aree, strutture, categorie, listini 2022/2023 e la
configurazione (§3, §5.3, D-10, D-12); in F6 l'albero delle pagine del sito (D-30).
Mai sovrascrivere dati già modificati dalla gestione: solo get_or_create.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea i dati iniziali di Tana se mancano (idempotente)."

    def handle(self, *args, **options) -> None:
        self.stdout.write("Nessun dato iniziale da creare in questa versione.")
