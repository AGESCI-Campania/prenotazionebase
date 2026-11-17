"""Aggiornamento del server dal web (P-20), sul modello di Plancia 3.0."""

from django.conf import settings
from django.db import models


class ReleaseGitHub(models.Model):
    """Ultima release pubblicata su GitHub (singleton, pk=1)."""

    versione = models.CharField(max_length=40, blank=True, help_text="Tag, es. v1.2.0.")
    nome = models.CharField(max_length=200, blank=True)
    note = models.TextField(blank=True, help_text="Note della release (markdown).")
    pubblicata_il = models.DateTimeField(null=True, blank=True)
    url = models.URLField(max_length=500, blank=True)
    controllata_il = models.DateTimeField(null=True, blank=True)
    errore = models.CharField(max_length=500, blank=True)

    class Meta:
        verbose_name = "ultima release"
        verbose_name_plural = "ultima release"

    def __str__(self) -> str:
        return self.versione or "nessuna release"

    @classmethod
    def corrente(cls) -> ReleaseGitHub:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class StatoRichiesta(models.TextChoices):
    IN_ATTESA = "IN_ATTESA", "in attesa"
    IN_CORSO = "IN_CORSO", "in corso"
    COMPLETATO = "COMPLETATO", "completato"
    FALLITO = "FALLITO", "non riuscito"
    ANNULLATO = "ANNULLATO", "annullato"


STATI_APERTI = (StatoRichiesta.IN_ATTESA, StatoRichiesta.IN_CORSO)


class RichiestaAggiornamento(models.Model):
    """Storico delle richieste di aggiornamento fatte dal web."""

    versione = models.CharField(max_length=40)
    versione_partenza = models.CharField(max_length=40, blank=True)
    richiesta_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    richiesta_da_email = models.CharField(max_length=254, blank=True)
    richiesta_il = models.DateTimeField(auto_now_add=True)
    stato = models.CharField(
        max_length=20, choices=StatoRichiesta.choices, default=StatoRichiesta.IN_ATTESA
    )
    fase = models.CharField(max_length=40, blank=True)
    messaggio = models.CharField(max_length=500, blank=True)
    percentuale = models.PositiveSmallIntegerField(null=True, blank=True)
    log = models.TextField(blank=True)
    completato_il = models.DateTimeField(null=True, blank=True)
    aggiornato_il = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "richiesta di aggiornamento"
        verbose_name_plural = "richieste di aggiornamento"
        ordering = ("-richiesta_il",)

    def __str__(self) -> str:
        return f"{self.versione} ({self.get_stato_display()})"

    @property
    def aperta(self) -> bool:
        return self.stato in STATI_APERTI
