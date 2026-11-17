"""Listini paralleli con versioni (D-08, D-09) e categorie "Associazione o ente" (D-10).

Importi in centesimi interi. Una versione già usata da una prenotazione è immutabile: non si
modificano né lei né le sue voci (si pubblica una nuova versione).
"""

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models


class VersioneInUso(ValidationError):
    """Modifica di una versione di listino già applicata a una prenotazione."""

    def __init__(self) -> None:
        super().__init__(
            "Questa versione del listino è già usata da una prenotazione e non si può modificare: "
            "pubblica una nuova versione."
        )


class Listino(models.Model):
    class Tipo(models.TextChoices):
        ASSOCIATIVO = "ASSOCIATIVO", "associativo"
        EXTRA = "EXTRA", "extra associativo"
        AGEVOLATO = "AGEVOLATO", "agevolato"
        GRATUITO = "GRATUITO", "gratuito"

    tipo = models.CharField(max_length=20, choices=Tipo.choices, unique=True)
    nome = models.CharField(max_length=100)

    class Meta:
        verbose_name = "listino"
        verbose_name_plural = "listini"
        ordering = ("pk",)

    def __str__(self) -> str:
        return self.nome


class VersioneListino(models.Model):
    """Versione di un listino (D-09): si applica, tra quelle già pubblicate alla data della
    richiesta, quella in vigore il primo giorno del soggiorno."""

    listino = models.ForeignKey(Listino, on_delete=models.PROTECT, related_name="versioni")
    nome = models.CharField(max_length=50, help_text="Es. 2022/2023.")
    pubblicata_il = models.DateField("pubblicata il")
    valida_dal = models.DateField("valida dal")
    note = models.TextField(blank=True)

    class Meta:
        verbose_name = "versione di listino"
        verbose_name_plural = "versioni di listino"
        ordering = ("listino", "-valida_dal")
        constraints = (
            models.UniqueConstraint(
                fields=("listino", "valida_dal"), name="versione_listino_unica_per_data"
            ),
        )

    def __str__(self) -> str:
        return f"{self.listino} {self.nome}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.in_uso():
            raise VersioneInUso
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        if self.in_uso():
            raise VersioneInUso
        return super().delete(*args, **kwargs)

    def in_uso(self) -> bool:
        if not self.pk:
            return False
        return self.prenotazioni.exists()


class Attivita(models.TextChoices):
    """Tipi di attività prenotabili (D-07)."""

    CAMPO = "CAMPO", "campo"
    BIVACCO = "BIVACCO", "bivacco"
    USCITA_CUCINA = "USCITA_CUCINA", "uscita con uso cucina"
    USCITA_AREA_VERDE = "USCITA_AREA_VERDE", "uscita area verde"
    GIORNATA_OSPITI = "GIORNATA_OSPITI", "giornata genitori e ospiti"


# Attività in giornata: non occupano un'area in esclusiva (P-05)
ATTIVITA_IN_GIORNATA = (
    Attivita.USCITA_CUCINA,
    Attivita.USCITA_AREA_VERDE,
    Attivita.GIORNATA_OSPITI,
)


class VoceListino(models.Model):
    """Voce di una versione: attività × area × stagione, con unità e importo (D-08).

    L'unità decide il conteggio: a giorni (arrivo e partenza inclusi) o a notti (D-04).
    """

    class Stagione(models.TextChoices):
        NESSUNA = "NESSUNA", "tutto l'anno"
        ESTIVA = "ESTIVA", "estiva"
        INVERNALE = "INVERNALE", "invernale"

    class Unita(models.TextChoices):
        PERSONA_GIORNO = "PERSONA_GIORNO", "persona/giorno"
        PERSONA_NOTTE = "PERSONA_NOTTE", "persona/notte"
        FORFAIT = "FORFAIT", "forfait"

    versione = models.ForeignKey(VersioneListino, on_delete=models.CASCADE, related_name="voci")
    attivita = models.CharField("attività", max_length=20, choices=Attivita.choices)
    area = models.ForeignKey(
        "base.Area",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Vuota per le attività in giornata.",
    )
    stagione = models.CharField(max_length=10, choices=Stagione.choices, default=Stagione.NESSUNA)
    unita = models.CharField("unità", max_length=20, choices=Unita.choices)
    importo_centesimi = models.PositiveIntegerField("importo (centesimi)")
    descrizione = models.CharField(
        max_length=200, blank=True, help_text="Nome della voce, es. «Pernotto extra associativo»."
    )

    class Meta:
        verbose_name = "voce di listino"
        verbose_name_plural = "voci di listino"
        ordering = ("versione", "attivita", "area", "stagione")
        constraints = (
            models.UniqueConstraint(
                fields=("versione", "attivita", "area", "stagione"),
                nulls_distinct=False,
                name="voce_listino_unica",
            ),
        )

    def __str__(self) -> str:
        return self.descrizione or self.get_attivita_display()

    def save(self, *args: Any, **kwargs: Any) -> None:
        self._verifica_versione_modificabile()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        self._verifica_versione_modificabile()
        return super().delete(*args, **kwargs)

    def clean(self) -> None:
        in_giornata = self.attivita in ATTIVITA_IN_GIORNATA
        if in_giornata and self.area_id is not None:
            raise ValidationError({"area": "Le attività in giornata non hanno un'area."})
        if not in_giornata and self.area_id is None:
            raise ValidationError({"area": "Indica l'area del campo o del bivacco."})
        # Il conteggio (giorni o notti) dipende dall'unità: uguale in tutte le stagioni
        altre = VoceListino.objects.filter(
            versione_id=self.versione_id, attivita=self.attivita, area=self.area
        ).exclude(pk=self.pk)
        if altre.exclude(unita=self.unita).exists():
            raise ValidationError({"unita": "Usa la stessa unità delle altre stagioni."})

    def _verifica_versione_modificabile(self) -> None:
        versioni = {self.versione_id}
        if self.pk:
            # Anche lo spostamento di una voce da una versione in uso
            versioni |= set(
                VoceListino.objects.filter(pk=self.pk).values_list("versione_id", flat=True)
            )
        if VersioneListino.objects.filter(pk__in=versioni, prenotazioni__isnull=False).exists():
            raise VersioneInUso


class Categoria(models.Model):
    """Categoria "Associazione o ente" (D-10): obbligatoria su ogni prenotazione."""

    codice = models.SlugField(max_length=30, unique=True)
    nome = models.CharField(max_length=150)
    prioritaria = models.BooleanField(default=False, help_text="Priorità del regolamento (D-11).")
    listino_default = models.ForeignKey(
        Listino, on_delete=models.PROTECT, related_name="+", verbose_name="listino di default"
    )
    richiede_specifica = models.BooleanField(
        default=False, help_text="Il richiedente deve specificare l'associazione o l'ente."
    )
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "categoria"
        verbose_name_plural = "categorie"
        ordering = ("ordine", "nome")

    def __str__(self) -> str:
        return self.nome
