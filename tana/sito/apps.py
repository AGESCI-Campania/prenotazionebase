from django.apps import AppConfig


class SitoConfig(AppConfig):
    name = "tana.sito"
    label = "sito"
    verbose_name = "Sito della base"

    def ready(self) -> None:
        from . import signals  # noqa: F401
