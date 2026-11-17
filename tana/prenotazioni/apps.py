from django.apps import AppConfig


class PrenotazioniConfig(AppConfig):
    name = "tana.prenotazioni"
    label = "prenotazioni"
    verbose_name = "Prenotazioni"

    def ready(self) -> None:
        from . import signals  # noqa: F401
