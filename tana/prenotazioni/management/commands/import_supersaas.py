"""manage.py import_supersaas — import una tantum dai calendari SuperSaaS (§7).

    import_supersaas --accantonamento prenotazioni.csv --tende campotende.csv --dry-run --report revisione.xlsx
    import_supersaas --accantonamento prenotazioni.csv --tende campotende.csv --apply --decisioni revisione.xlsx

Con le stesse opzioni in entrambi i passi (comprese --amministratori "Nome Cognome,email").

Senza --apply non scrive nulla nel database. I CSV e il file di revisione contengono dati
personali: fuori dal repo, da cancellare dopo l'import.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError, CommandParser

from tana.prenotazioni import importazione


class Command(BaseCommand):
    help = "Importa le prenotazioni dai due calendari SuperSaaS (prima --dry-run, poi --apply)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--accantonamento", type=Path, required=True, help="CSV del calendario prenotazioni"
        )
        parser.add_argument(
            "--tende", type=Path, required=True, help="CSV del calendario campotende"
        )
        modo = parser.add_mutually_exclusive_group(required=True)
        modo.add_argument(
            "--dry-run", action="store_true", help="Solo proposte: scrive il file di revisione"
        )
        modo.add_argument("--apply", action="store_true", help="Importa usando le decisioni")
        parser.add_argument(
            "--report", type=Path, help="File di revisione da creare (con --dry-run)"
        )
        parser.add_argument(
            "--amministratori",
            default="",
            help="Nomi o email (separati da virgola) con cui l'amministratore ha inserito righe "
            "per conto dei gruppi: quelle righe sono proposte senza referente",
        )
        parser.add_argument(
            "--decisioni", type=Path, help="File di revisione corretto (con --apply)"
        )

    def handle(self, *args, **opzioni) -> None:
        for percorso in (opzioni["accantonamento"], opzioni["tende"]):
            if not percorso.is_file():
                raise CommandError(f"File non trovato: {percorso}")
        try:
            proposte = importazione.proposte(
                opzioni["accantonamento"],
                opzioni["tende"],
                amministratori=opzioni["amministratori"].split(","),
            )
            if opzioni["dry_run"]:
                self._prova(proposte, opzioni["report"])
            else:
                self._applica(proposte, opzioni["decisioni"])
        except importazione.ErroreImport as errore:
            raise CommandError(str(errore)) from errore

    def _prova(self, proposte: list[importazione.Proposta], report: Path | None) -> None:
        if report is None:
            raise CommandError("Con --dry-run serve --report <file.xlsx>.")
        importazione.scrivi_revisione(proposte, report)
        righe = sum(len(p.righe) for p in proposte)
        self.stdout.write(
            f"{righe} righe lette, {len(proposte)} prenotazioni proposte "
            f"({sum(p.unione for p in proposte)} congiunte, "
            f"{sum(p.azione == 'SCARTA' for p in proposte)} da scartare, "
            f"{sum(bool(p.anomalie) for p in proposte)} con anomalie). "
            f"Nessuna scrittura nel database. Revisione: {report}"
        )

    def _applica(self, proposte: list[importazione.Proposta], decisioni: Path | None) -> None:
        if decisioni is None or not decisioni.is_file():
            raise CommandError("Con --apply serve --decisioni <file di revisione corretto>.")
        esito = importazione.applica(proposte, importazione.leggi_decisioni(decisioni))
        self.stdout.write(
            self.style.SUCCESS(
                f"Importate {len(esito.importate)} prenotazioni; scartate {len(esito.scartate)}: "
                + (", ".join(esito.scartate) or "nessuna")
            )
        )
