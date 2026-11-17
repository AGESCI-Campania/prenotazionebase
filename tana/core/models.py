"""Modelli trasversali di Tana."""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
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


class EventoStorico(models.Model):
    """Voce dello storico (P-03): chi ha operato e, per le decisioni discrezionali, chi ha
    deciso e perché. Si scrive solo tramite `tana.core.services`."""

    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.PROTECT, verbose_name="tipo di oggetto"
    )
    object_id = models.CharField("id dell'oggetto", max_length=64)
    oggetto = GenericForeignKey("content_type", "object_id")
    azione = models.CharField(max_length=100)
    utente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Chi ha operato nell'app.",
    )
    deciso_da = models.CharField(
        "deciso da", max_length=200, blank=True, help_text="Chi ha preso la decisione (P-03)."
    )
    motivazione = models.TextField(blank=True)
    dati_prima = models.JSONField("dati prima", null=True, blank=True)
    dati_dopo = models.JSONField("dati dopo", null=True, blank=True)
    creato_il = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "evento dello storico"
        verbose_name_plural = "storico"
        ordering = ("-creato_il", "-pk")
        indexes = (models.Index(fields=("content_type", "object_id")),)

    def __str__(self) -> str:
        return f"{self.azione} ({self.creato_il:%d/%m/%Y %H:%M})"
