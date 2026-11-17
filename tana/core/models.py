"""Modelli trasversali di Tana."""

from django.db import models


class Manutenzione(models.Model):
    """Stato di manutenzione del sito (singleton, pk=1).

    Lo attivano e disattivano `scripts/aggiorna.sh` (comando `manage.py manutenzione`) e, in
    futuro, la pagina di configurazione. Con la manutenzione attiva il sito risponde 503, tranne
    `/healthz/` (serve agli script per sapere se i servizi sono pronti) e i superutenti.
    """

    attiva = models.BooleanField(default=False)
    messaggio = models.CharField(max_length=300, blank=True)
    aggiornata_il = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "manutenzione"
        verbose_name_plural = "manutenzione"

    def __str__(self) -> str:
        return "attiva" if self.attiva else "disattiva"

    @classmethod
    def corrente(cls) -> Manutenzione:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
