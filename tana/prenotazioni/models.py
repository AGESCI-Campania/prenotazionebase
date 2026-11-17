"""Prenotazioni, occupazioni delle aree e movimenti collegati (§3, §4).

La non sovrapposizione è garantita dal database: exclusion constraint su `Occupazione`
(stessa area, intervalli `[arrivo, partenza)` che si sovrappongono, solo occupazioni attive).
Prenotazioni, esclusive e blocchi tecnici stanno nella stessa tabella. Le occupazioni si
creano e si aggiornano solo con `tana.prenotazioni.services`.
"""

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import ArrayField, DateRangeField, RangeOperators
from django.db import models
from django.db.models import Q
from django.utils import timezone

from tana.core.storage import storage_privato
from tana.listini.models import Attivita, VoceListino


class Stato(models.TextChoices):
    """Stati della prenotazione (§4)."""

    RICHIESTA = "RICHIESTA", "richiesta"
    APPROVATA = "APPROVATA", "approvata (attesa acconto)"
    CONFERMATA = "CONFERMATA", "confermata"
    SVOLTA = "SVOLTA", "svolta"
    CHIUSA = "CHIUSA", "chiusa"
    RIFIUTATA = "RIFIUTATA", "rifiutata"
    SCADUTA = "SCADUTA", "scaduta"
    ANNULLATA = "ANNULLATA", "annullata"
    NON_SVOLTA = "NON_SVOLTA", "non svolta"


# Stati che occupano le date (§4, P-01); gli altri le liberano
STATI_ATTIVI = frozenset(
    {Stato.RICHIESTA, Stato.APPROVATA, Stato.CONFERMATA, Stato.SVOLTA, Stato.CHIUSA}
)


class Unita(models.TextChoices):
    """Unità presenti nel gruppo (solo per le statistiche, nessun dato sui ragazzi: D-18)."""

    CASTORINI = "CASTORINI", "Castorini"
    LC = "LC", "L/C"
    EG = "EG", "E/G"
    RS = "RS", "R/S"
    COCA = "COCA", "Co.Ca."
    ALTRO = "ALTRO", "Altro"


class Contatto(models.Model):
    """Referente di una prenotazione, anche senza account (import, D-10)."""

    nome = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    organizzazione = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "contatto"
        verbose_name_plural = "contatti"
        ordering = ("nome",)

    def __str__(self) -> str:
        return self.nome


class ContatoreNumeri(models.Model):
    """Ultimo numero assegnato per anno (numeri `AAAA-NNN`, mai riusati)."""

    anno = models.PositiveSmallIntegerField(primary_key=True)
    ultimo = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "contatore dei numeri"
        verbose_name_plural = "contatori dei numeri"

    def __str__(self) -> str:
        return f"{self.anno}: {self.ultimo}"


class Prenotazione(models.Model):
    numero = models.CharField(
        max_length=12,
        unique=True,
        editable=False,
        help_text="AAAA-NNN, con l'anno di creazione della richiesta.",
    )
    categoria = models.ForeignKey(
        "listini.Categoria", on_delete=models.PROTECT, related_name="prenotazioni"
    )
    specifica_categoria = models.CharField("specifica della categoria", max_length=200, blank=True)
    richiedente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="prenotazioni",
    )
    contatto = models.ForeignKey(
        Contatto,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="prenotazioni",
        help_text="Può mancare per le prenotazioni prioritarie (D-10).",
    )
    gruppo = models.CharField("gruppo o ente", max_length=200, blank=True)
    unita = ArrayField(
        models.CharField(max_length=10, choices=Unita.choices),
        verbose_name="unità presenti",
        default=list,
        blank=True,
    )
    data_richiesta = models.DateField(
        "data della richiesta",
        default=timezone.localdate,
        help_text="Sceglie la versione di listino (D-09); per lo storico importato è quella reale.",
    )
    arrivo = models.DateField()
    partenza = models.DateField()
    stato = models.CharField(max_length=20, choices=Stato.choices, default=Stato.RICHIESTA)
    esclusiva_richiesta = models.BooleanField("esclusiva richiesta", default=False)
    esclusiva_concessa = models.BooleanField("esclusiva concessa", default=False)
    categoria_prioritaria_richiesta = models.BooleanField(
        "categoria prioritaria richiesta", default=False
    )
    categoria_prioritaria_concessa = models.BooleanField(
        "categoria prioritaria concessa", default=False
    )
    versione_listino = models.ForeignKey(
        "listini.VersioneListino",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="prenotazioni",
        verbose_name="versione di listino",
        help_text="Congelata sulla prenotazione (D-09).",
    )
    note = models.TextField(blank=True)
    id_supersaas = models.CharField(
        "id SuperSaaS", max_length=50, unique=True, null=True, blank=True, editable=False
    )
    creata_il = models.DateTimeField(auto_now_add=True)
    aggiornata_il = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "prenotazione"
        verbose_name_plural = "prenotazioni"
        ordering = ("-arrivo", "-pk")
        constraints = (
            models.CheckConstraint(
                condition=Q(partenza__gte=models.F("arrivo")),
                name="prenotazione_partenza_dopo_arrivo",
            ),
        )

    def __str__(self) -> str:
        return f"{self.numero} {self.gruppo}".strip()

    @property
    def attiva(self) -> bool:
        return self.stato in STATI_ATTIVI


class PresenzaArea(models.Model):
    """Persone in un'area; le prenotazioni congiunte hanno due righe."""

    prenotazione = models.ForeignKey(
        Prenotazione, on_delete=models.CASCADE, related_name="presenze"
    )
    area = models.ForeignKey("base.Area", on_delete=models.PROTECT, related_name="+")
    persone_previste = models.PositiveIntegerField("persone previste")
    persone_effettive = models.PositiveIntegerField("persone effettive", null=True, blank=True)

    class Meta:
        verbose_name = "presenza in un'area"
        verbose_name_plural = "presenze nelle aree"
        constraints = (
            models.UniqueConstraint(fields=("prenotazione", "area"), name="presenza_area_unica"),
        )

    def __str__(self) -> str:
        return f"{self.area}: {self.persone_previste}"


class BloccoTecnico(models.Model):
    """Date bloccate per manutenzione: fuori dalle categorie e dalle statistiche."""

    area = models.ForeignKey("base.Area", on_delete=models.PROTECT, related_name="+")
    dal = models.DateField()
    al = models.DateField(help_text="Ultimo giorno bloccato (incluso).")
    motivo = models.CharField(max_length=300)
    creato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    creato_il = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "blocco tecnico"
        verbose_name_plural = "blocchi tecnici"
        ordering = ("-dal",)
        constraints = (
            models.CheckConstraint(condition=Q(al__gte=models.F("dal")), name="blocco_al_dopo_dal"),
        )

    def __str__(self) -> str:
        return f"{self.area} {self.dal:%d/%m/%Y}–{self.al:%d/%m/%Y}: {self.motivo}"


class Occupazione(models.Model):
    """Area occupata nell'intervallo `[inizio, fine)` (D-05): il giorno di fine resta libero."""

    class Tipo(models.TextChoices):
        PRENOTAZIONE = "PRENOTAZIONE", "prenotazione"
        ESCLUSIVA = "ESCLUSIVA", "esclusiva"  # area tende senza persone (D-03)
        BLOCCO = "BLOCCO", "blocco tecnico"

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    area = models.ForeignKey("base.Area", on_delete=models.PROTECT, related_name="occupazioni")
    periodo = DateRangeField()
    attiva = models.BooleanField(default=True)
    prenotazione = models.ForeignKey(
        Prenotazione,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="occupazioni",
    )
    blocco = models.ForeignKey(
        BloccoTecnico,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="occupazioni",
    )

    class Meta:
        verbose_name = "occupazione"
        verbose_name_plural = "occupazioni"
        constraints = (
            ExclusionConstraint(
                name="occupazioni_non_sovrapposte",
                expressions=(("area", RangeOperators.EQUAL), ("periodo", RangeOperators.OVERLAPS)),
                condition=Q(attiva=True),
            ),
            models.CheckConstraint(
                condition=Q(periodo__isempty=False), name="occupazione_periodo_non_vuoto"
            ),
            models.CheckConstraint(
                condition=(
                    Q(tipo="BLOCCO", blocco__isnull=False, prenotazione__isnull=True)
                    | Q(
                        tipo__in=("PRENOTAZIONE", "ESCLUSIVA"),
                        blocco__isnull=True,
                        prenotazione__isnull=False,
                    )
                ),
                name="occupazione_tipo_coerente",
            ),
            models.UniqueConstraint(
                fields=("prenotazione", "area"), name="occupazione_unica_per_area"
            ),
        )

    def __str__(self) -> str:
        return f"{self.area} {self.periodo} ({self.get_tipo_display()})"


class AttivitaGiornaliera(models.Model):
    """Attività in giornata (uscite, ospiti): non occupa un'area in esclusiva (P-05)."""

    class Tipo(models.TextChoices):
        USCITA_CUCINA = "USCITA_CUCINA", "uscita con uso cucina"
        USCITA_AREA_VERDE = "USCITA_AREA_VERDE", "uscita area verde"
        GIORNATA_OSPITI = "GIORNATA_OSPITI", "giornata genitori e ospiti"

    prenotazione = models.ForeignKey(
        Prenotazione, on_delete=models.CASCADE, related_name="attivita_giornaliere"
    )
    data = models.DateField()
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    persone_previste = models.PositiveIntegerField("persone previste")
    persone_effettive = models.PositiveIntegerField("persone effettive", null=True, blank=True)

    class Meta:
        verbose_name = "attività in giornata"
        verbose_name_plural = "attività in giornata"
        ordering = ("data",)

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.data:%d/%m/%Y}"


class RichiestaConsenso(models.Model):
    """Domanda di consenso al gruppo già presente (D-06): senza risposta entro la scadenza il
    consenso è negato."""

    class StatoConsenso(models.TextChoices):
        IN_ATTESA = "IN_ATTESA", "in attesa"
        CONCESSO = "CONCESSO", "concesso"
        NEGATO = "NEGATO", "negato"
        SCADUTO = "SCADUTO", "scaduto (negato)"

    richiesta = models.ForeignKey(
        Prenotazione, on_delete=models.CASCADE, related_name="consensi_chiesti"
    )
    prenotazione_esistente = models.ForeignKey(
        Prenotazione, on_delete=models.CASCADE, related_name="consensi_ricevuti"
    )
    stato = models.CharField(
        max_length=20, choices=StatoConsenso.choices, default=StatoConsenso.IN_ATTESA
    )
    scadenza = models.DateTimeField()
    risposta_il = models.DateTimeField(null=True, blank=True)
    risposto_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    creata_il = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "richiesta di consenso"
        verbose_name_plural = "richieste di consenso"
        constraints = (
            models.UniqueConstraint(
                fields=("richiesta", "prenotazione_esistente"), name="consenso_unico"
            ),
            models.CheckConstraint(
                condition=~Q(richiesta=models.F("prenotazione_esistente")),
                name="consenso_non_a_se_stessa",
            ),
        )

    def __str__(self) -> str:
        return f"{self.richiesta} → {self.prenotazione_esistente}: {self.get_stato_display()}"


class RigaImporto(models.Model):
    """Riga del preventivo o del consuntivo (§5).

    - calcolata: dal listino (si rigenera a ogni ricalcolo); prezzo vuoto se la voce manca nel
      listino ("da definire", P-04) finché l'amministratore non la valorizza;
    - voce libera: inserita a mano (sovrapprezzi, pellet, forfait, danni);
    - rettifica: differenza che porta il totale all'importo deciso (D-24).
    Rettifiche e valorizzazioni richiedono "deciso da" e motivazione (P-03).
    """

    class Fase(models.TextChoices):
        PREVENTIVO = "PREVENTIVO", "preventivo"
        CONSUNTIVO = "CONSUNTIVO", "consuntivo"

    prenotazione = models.ForeignKey(
        Prenotazione, on_delete=models.CASCADE, related_name="righe_importo"
    )
    fase = models.CharField(max_length=20, choices=Fase.choices)
    voce = models.ForeignKey(
        "listini.VoceListino",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="Vuota per le voci libere (sovrapprezzi, pellet, forfait, danni).",
    )
    descrizione = models.CharField(max_length=200)
    # Chiave della voce di listino (anche quando manca): attività × area × stagione × unità
    attivita = models.CharField("attività", max_length=20, choices=Attivita.choices, blank=True)
    area = models.ForeignKey(
        "base.Area", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    stagione = models.CharField(max_length=10, choices=VoceListino.Stagione.choices, blank=True)
    unita = models.CharField("unità", max_length=20, choices=VoceListino.Unita.choices, blank=True)
    quantita = models.PositiveIntegerField("quantità", default=1)
    prezzo_centesimi = models.IntegerField(
        "prezzo unitario (centesimi)", null=True, blank=True, help_text="Vuoto: da definire."
    )
    importo_centesimi = models.IntegerField("importo (centesimi)", null=True, blank=True)
    calcolata = models.BooleanField(default=False, help_text="Generata dal listino.")
    stimata = models.BooleanField(
        default=False, help_text="Consuntivo con le persone previste al posto delle effettive."
    )
    rettifica = models.BooleanField(default=False)
    deciso_da = models.CharField("deciso da", max_length=200, blank=True)
    motivazione = models.TextField(blank=True)
    registrata_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "riga di importo"
        verbose_name_plural = "righe di importo"
        ordering = ("prenotazione", "fase", "ordine", "pk")
        constraints = (
            models.CheckConstraint(
                condition=Q(rettifica=False) | (~Q(deciso_da="") & ~Q(motivazione="")),
                name="rettifica_con_decisione",
            ),
            models.CheckConstraint(
                condition=Q(prezzo_centesimi__isnull=True, importo_centesimi__isnull=True)
                | Q(prezzo_centesimi__isnull=False, importo_centesimi__isnull=False),
                name="riga_prezzo_e_importo_insieme",
            ),
            models.CheckConstraint(
                condition=Q(calcolata=True) | Q(prezzo_centesimi__isnull=False),
                name="riga_manuale_con_prezzo",
            ),
        )

    def __str__(self) -> str:
        return self.descrizione

    @property
    def da_definire(self) -> bool:
        return self.importo_centesimi is None


def _percorso_ricevuta(pagamento: Pagamento, nome: str) -> str:
    return f"ricevute/{pagamento.prenotazione.numero}/{nome}"


class Pagamento(models.Model):
    class Tipo(models.TextChoices):
        ACCONTO = "ACCONTO", "acconto"
        SALDO = "SALDO", "saldo"

    prenotazione = models.ForeignKey(
        Prenotazione, on_delete=models.PROTECT, related_name="pagamenti"
    )
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    importo_centesimi = models.PositiveIntegerField("importo (centesimi)")
    # Mai in MEDIA_ROOT: si serve solo con X-Accel-Redirect dopo il controllo dei permessi (P-14)
    ricevuta = models.FileField(
        upload_to=_percorso_ricevuta, storage=storage_privato, blank=True, max_length=300
    )
    registrato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    data = models.DateField()

    class Meta:
        verbose_name = "pagamento"
        verbose_name_plural = "pagamenti"
        ordering = ("prenotazione", "data", "pk")

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.prenotazione.numero}"


class Messaggio(models.Model):
    """Messaggio tra referenti o con la gestione su una prenotazione (D-16)."""

    prenotazione = models.ForeignKey(
        Prenotazione, on_delete=models.CASCADE, related_name="messaggi"
    )
    mittente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="messaggi_inviati"
    )
    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="messaggi_ricevuti",
        help_text="Vuoto: messaggio alla gestione della base.",
    )
    testo = models.TextField()
    letto = models.BooleanField(default=False)
    inviato_il = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "messaggio"
        verbose_name_plural = "messaggi"
        ordering = ("prenotazione", "inviato_il")

    def __str__(self) -> str:
        return f"{self.mittente} → {self.destinatario or 'gestione'} ({self.inviato_il:%d/%m/%Y})"
