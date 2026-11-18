"""La base: aree prenotabili, strutture e configurazione generale (§3, D-12)."""

import datetime

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.models import Orderable


class Area(models.Model):
    """Area prenotabile da un solo gruppo alla volta (D-02)."""

    ACCANTONAMENTO = "ACC"
    TENDE = "TENDE"

    codice = models.CharField(max_length=10, unique=True)
    nome = models.CharField(max_length=100)
    capienza = models.PositiveIntegerField()
    unita_capienza = models.CharField(
        "unità della capienza", max_length=30, default="persone", help_text="Es. persone, piazzole."
    )
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "area"
        verbose_name_plural = "aree"
        ordering = ("ordine", "nome")

    def __str__(self) -> str:
        return self.nome


class Struttura(ClusterableModel):
    """Struttura della base, mostrata nella pagina pubblica «Le strutture» (D-12). Si modifica
    nell'editor del sito (snippet di Wagtail), con una galleria facoltativa."""

    class Uso(models.TextChoices):
        CONDIVISA = "CONDIVISA", "condivisa"
        SOLO_ACCANTONAMENTO = "SOLO_ACC", "solo accantonamento"
        SOLO_TENDE = "SOLO_TENDE", "solo tende"
        NON_DISPONIBILE = "NON_DISPONIBILE", "non disponibile"

    nome = models.CharField(max_length=100, unique=True)
    descrizione = models.TextField(blank=True)
    uso = models.CharField(max_length=20, choices=Uso.choices)
    ordine = models.PositiveSmallIntegerField(
        default=0, help_text="Posizione nella pagina delle strutture (prima i numeri più bassi)."
    )

    panels = [
        FieldPanel("nome"),
        FieldPanel("uso"),
        FieldPanel("ordine"),
        FieldPanel("descrizione"),
        InlinePanel("immagini", label="Galleria", heading="Galleria (facoltativa)"),
    ]

    class Meta:
        verbose_name = "struttura"
        verbose_name_plural = "strutture"
        ordering = ("ordine", "nome")

    def __str__(self) -> str:
        return self.nome


class ImmagineStruttura(Orderable):
    """Foto della galleria di una struttura."""

    struttura = ParentalKey(Struttura, on_delete=models.CASCADE, related_name="immagini")
    immagine = models.ForeignKey("wagtailimages.Image", on_delete=models.CASCADE, related_name="+")
    didascalia = models.CharField(max_length=250, blank=True)

    panels = [FieldPanel("immagine"), FieldPanel("didascalia")]

    class Meta(Orderable.Meta):
        verbose_name = "immagine"
        verbose_name_plural = "immagini"


def _giorno_dell_anno(mese: int, giorno: int) -> datetime.date:
    # Anno bisestile di comodo: accetta anche il 29/2
    return datetime.date(2000, mese, giorno)


# Default come funzioni: con un orario fisso il controllo fields.W161 di Django scatta quando
# coincide (±10 s) con l'ora in cui gira il controllo.
def orario_arrivo_standard() -> datetime.time:
    return datetime.time(15, 0)


def orario_partenza_standard() -> datetime.time:
    return datetime.time(12, 0)


class Configurazione(models.Model):
    """Parametri generali modificabili dalla gestione (singleton, pk=1)."""

    # Blocco delle nuove prenotazioni (D-31): vale per tutti, gestione compresa
    prenotazioni_bloccate = models.BooleanField(
        "prenotazioni bloccate",
        default=False,
        help_text="Nessuno può inserire nuove prenotazioni, nemmeno la gestione: al posto del "
        "modulo compare il messaggio qui sotto. Le prenotazioni esistenti proseguono normalmente.",
    )
    messaggio_blocco = models.TextField(
        "messaggio di blocco",
        default="Le prenotazioni sono momentaneamente sospese. Riprova tra qualche giorno.",
        help_text="Mostrato al posto del modulo di richiesta mentre le prenotazioni sono bloccate. "
        "Gli indirizzi web (https://…) diventano link.",
    )
    # Modalità demo (D-32): prova del sistema prima dell'apertura; si attiva e si termina solo
    # con i servizi di tana.prenotazioni.demo (alla fine si cancellano tutte le prenotazioni)
    modalita_demo = models.BooleanField("modalità demo", default=False, editable=False)
    link_prenotazioni_vere = models.URLField(
        "dove prenotare durante la demo",
        blank=True,
        help_text="Durante la modalità demo chi visita il sito legge che le prenotazioni qui non "
        "sono valide e trova questo indirizzo per prenotare davvero.",
    )
    # Stagione invernale ricorrente (D-08): di default dal 1/11 al 15/3, estremi inclusi
    inverno_dal_giorno = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    inverno_dal_mese = models.PositiveSmallIntegerField(
        default=11, validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    inverno_al_giorno = models.PositiveSmallIntegerField(
        default=15, validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    inverno_al_mese = models.PositiveSmallIntegerField(
        default=3, validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    # Acconto (D-13)
    acconto_percentuale = models.PositiveSmallIntegerField(
        "percentuale dell'acconto", default=50, validators=[MaxValueValidator(100)]
    )
    acconto_giorni = models.PositiveSmallIntegerField(
        "giorni per l'acconto",
        default=7,
        help_text="Giorni dall'approvazione per caricare la ricevuta del bonifico.",
    )
    soglia_esenzione_giorni = models.PositiveSmallIntegerField(
        "soglia di esenzione (giorni)",
        default=3,
        help_text="Nessun acconto per i soggiorni fino a questo numero di giorni.",
    )
    # Consenso del gruppo presente (D-06)
    consenso_giorni = models.PositiveSmallIntegerField(
        "giorni per il consenso",
        default=7,
        help_text="Giorni per rispondere (al massimo fino alla vigilia dell'attività); "
        "senza risposta il consenso è negato.",
    )
    # Orari standard (D-04)
    orario_arrivo = models.TimeField("orario di arrivo", default=orario_arrivo_standard)
    orario_partenza = models.TimeField("orario di partenza", default=orario_partenza_standard)
    # Orizzonte massimo (D-25)
    orizzonte_massimo = models.DateField(
        "prenotazioni aperte fino a",
        default=datetime.date(2027, 9, 30),
        help_text="Non si accettano richieste con data di arrivo successiva.",
    )
    # Conservazione dei dati personali (D-18)
    anni_conservazione = models.PositiveSmallIntegerField("anni di conservazione", default=10)
    # Coordinate del bonifico (email di approvazione, PDF di conferma: D-19)
    iban = models.CharField("IBAN", max_length=34, blank=True)
    intestatario_bonifico = models.CharField("intestatario del conto", max_length=200, blank=True)
    causale_bonifico = models.CharField(
        "causale del bonifico",
        max_length=200,
        default="Acconto prenotazione {numero} - {gruppo}",
        help_text="{numero} e {gruppo} si sostituiscono con i dati della prenotazione.",
    )
    aggiornata_il = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configurazione"
        verbose_name_plural = "configurazione"

    def __str__(self) -> str:
        return "configurazione"

    @classmethod
    def corrente(cls) -> Configurazione:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def clean(self) -> None:
        errori = {}
        for campo, mese, giorno in (
            ("inverno_dal_giorno", self.inverno_dal_mese, self.inverno_dal_giorno),
            ("inverno_al_giorno", self.inverno_al_mese, self.inverno_al_giorno),
        ):
            try:
                _giorno_dell_anno(mese, giorno)
            except ValueError:
                errori[campo] = "Data inesistente."
        if errori:
            raise ValidationError(errori)

    def causale(self, numero: str, gruppo: str) -> str:
        """Causale del bonifico di una prenotazione."""
        return self.causale_bonifico.replace("{numero}", numero).replace("{gruppo}", gruppo)

    def e_inverno(self, data: datetime.date) -> bool:
        """True se `data` cade nella stagione invernale (estremi inclusi, anche a cavallo
        dell'anno)."""
        dal = (self.inverno_dal_mese, self.inverno_dal_giorno)
        al = (self.inverno_al_mese, self.inverno_al_giorno)
        giorno = (data.month, data.day)
        if dal <= al:
            return dal <= giorno <= al
        return giorno >= dal or giorno <= al
