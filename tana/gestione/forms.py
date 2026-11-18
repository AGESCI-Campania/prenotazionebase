"""Form dell'area di gestione. Gli importi si inseriscono in euro e diventano centesimi interi."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from agesci_theme.forms import Combobox, InputConAdorno, SelettoreData
from django import forms

from tana.accounts.models import Ruolo
from tana.base.models import Area, Configurazione
from tana.listini.models import Categoria, Listino, VersioneListino, VoceListino
from tana.listini.services import controlla_date
from tana.prenotazioni.models import Pagamento, Prenotazione


class CampoEuro(forms.DecimalField):
    """Importo in euro (virgola decimale) → centesimi interi."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("max_digits", 10)
        kwargs.setdefault("decimal_places", 2)
        kwargs.setdefault("localize", True)
        super().__init__(**kwargs)

    def clean(self, value: Any) -> int | None:  # type: ignore[override]
        euro = super().clean(value)
        if euro is None:
            return None
        return int((Decimal(euro) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class DecisioneForm(forms.Form):
    """Campi delle decisioni discrezionali (P-03)."""

    deciso_da = forms.CharField(
        label="Deciso da", max_length=200, required=False, help_text="Es. Pattuglia, IRO."
    )
    motivazione = forms.CharField(
        label="Motivazione", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class ApprovaForm(DecisioneForm):
    concedi_esclusiva = forms.BooleanField(label="Concedo l'uso esclusivo", required=False)
    concedi_categoria = forms.BooleanField(label="Concedo la categoria prioritaria", required=False)
    acconto = CampoEuro(
        label="Acconto (€)",
        required=False,
        min_value=0,
        help_text="Vuoto: acconto previsto dal regolamento. Zero: esenzione.",
    )


class RifiutaForm(DecisioneForm):
    comunica_motivazione = forms.BooleanField(
        label="Comunica la motivazione al richiedente", required=False
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["deciso_da"].required = True
        self.fields["motivazione"].required = True


class MotivoForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class RespingiForm(forms.Form):
    motivazione = forms.CharField(
        label="Perché la ricevuta non va bene", widget=forms.Textarea(attrs={"rows": 2})
    )


class ModificaForm(forms.Form):
    arrivo = forms.DateField(label="Arrivo", widget=SelettoreData())
    partenza = forms.DateField(label="Partenza", widget=SelettoreData())
    persone_acc = forms.IntegerField(label="Persone in accantonamento", min_value=0, required=False)
    persone_tende = forms.IntegerField(label="Persone in tenda", min_value=0, required=False)
    motivo = forms.CharField(label="Motivo (va nell'email al richiedente)", required=False)

    @classmethod
    def per(cls, prenotazione: Prenotazione, data: Any = None) -> ModificaForm:
        persone = {p.area.codice: p.persone_previste for p in prenotazione.presenze.all()}
        return cls(
            data,
            initial={
                "arrivo": prenotazione.arrivo,
                "partenza": prenotazione.partenza,
                "persone_acc": persone.get(Area.ACCANTONAMENTO),
                "persone_tende": persone.get(Area.TENDE),
            },
        )


class ValorizzaForm(DecisioneForm):
    riga = forms.IntegerField(widget=forms.HiddenInput)
    prezzo = CampoEuro(label="Prezzo unitario (€)", min_value=0)


class VoceLiberaForm(DecisioneForm):
    descrizione = forms.CharField(
        label="Voce", max_length=200, help_text="Es. pellet, danni, sovrapprezzo esclusiva."
    )
    quantita = forms.IntegerField(label="Quantità", min_value=1, initial=1)
    prezzo = CampoEuro(label="Prezzo unitario (€)", min_value=0)


class QuotaForm(DecisioneForm):
    totale = CampoEuro(label="Nuova quota totale (€)", min_value=0)


class OrariForm(forms.Form):
    arrivo = forms.TimeField(
        label="Arrivo concordato", required=False, widget=forms.TimeInput(attrs={"type": "time"})
    )
    partenza = forms.TimeField(
        label="Partenza concordata", required=False, widget=forms.TimeInput(attrs={"type": "time"})
    )


class PagamentoForm(forms.Form):
    tipo = forms.ChoiceField(
        label="Tipo", choices=Pagamento.Tipo.choices, initial=Pagamento.Tipo.SALDO
    )
    importo = CampoEuro(label="Importo (€)", min_value=Decimal("0.01"))
    data_pagamento = forms.DateField(label="Data del pagamento", widget=SelettoreData())


class RispostaForm(forms.Form):
    testo = forms.CharField(
        label="Risposta della Pattuglia", widget=forms.Textarea(attrs={"rows": 3})
    )


class PresenzeEffettiveForm(forms.Form):
    """Persone effettive per area e attività in giornata (campi creati dalla prenotazione)."""

    def __init__(self, prenotazione: Prenotazione, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.prenotazione = prenotazione
        for presenza in prenotazione.presenze.select_related("area").order_by("area__ordine"):
            self.fields[f"area_{presenza.area.codice}"] = forms.IntegerField(
                label=f"{presenza.area} (previste {presenza.persone_previste})",
                min_value=0,
                required=False,
                initial=presenza.persone_effettive,
            )
        for att in prenotazione.attivita_giornaliere.order_by("data"):
            self.fields[f"attivita_{att.pk}"] = forms.IntegerField(
                label=f"{att.get_tipo_display().capitalize()} {att.data:%d/%m} (previste {att.persone_previste})",
                min_value=0,
                required=False,
                initial=att.persone_effettive,
            )

    def presenze(self) -> dict[str, int | None]:
        return {
            nome.removeprefix("area_"): valore
            for nome, valore in self.cleaned_data.items()
            if nome.startswith("area_")
        }

    def attivita(self) -> dict[int, int | None]:
        return {
            int(nome.removeprefix("attivita_")): valore
            for nome, valore in self.cleaned_data.items()
            if nome.startswith("attivita_")
        }


class NuovaPrioritariaForm(DecisioneForm):
    """Prenotazione inserita per conto della gestione (es. date Fo.Ca.), anche senza contatti."""

    categoria = forms.ModelChoiceField(
        Categoria.objects.filter(prioritaria=True), label="Categoria"
    )
    gruppo = forms.CharField(label="Evento o gruppo", max_length=200)
    arrivo = forms.DateField(label="Arrivo", widget=SelettoreData())
    partenza = forms.DateField(label="Partenza", widget=SelettoreData())
    persone_acc = forms.IntegerField(label="Persone in accantonamento", min_value=0, required=False)
    persone_tende = forms.IntegerField(label="Persone in tenda", min_value=0, required=False)
    note = forms.CharField(label="Note", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["deciso_da"].required = True
        self.fields["motivazione"].required = True


class BloccoForm(forms.Form):
    area = forms.ModelChoiceField(Area.objects.all(), label="Area")
    dal = forms.DateField(label="Dal", widget=SelettoreData())
    al = forms.DateField(label="Al (incluso)", widget=SelettoreData())
    motivo = forms.CharField(label="Motivo", max_length=300)


MESI = [
    (numero, nome)
    for numero, nome in enumerate(
        (
            "gennaio",
            "febbraio",
            "marzo",
            "aprile",
            "maggio",
            "giugno",
            "luglio",
            "agosto",
            "settembre",
            "ottobre",
            "novembre",
            "dicembre",
        ),
        start=1,
    )
]


def _numero(suffisso: str) -> InputConAdorno:
    return InputConAdorno(suffisso=suffisso, input_type="number", attrs={"min": 0})


class ConfigurazioneForm(forms.ModelForm):
    # Blocco delle prenotazioni (D-31), in cima alla pagina
    BLOCCO = ("prenotazioni_bloccate", "messaggio_blocco")
    # Gruppi di campi affiancati nel template: (titolo, descrizione, campi, classi della colonna)
    GRUPPI = (
        (
            "Stagione invernale",
            "Periodo che si ripete ogni anno: le tariffe invernali si applicano giorno per "
            "giorno ai soggiorni che vi cadono.",
            ("inverno_dal_giorno", "inverno_dal_mese", "inverno_al_giorno", "inverno_al_mese"),
            "col-6 lg:col-3",
        ),
        (
            "Acconto",
            "",
            ("acconto_percentuale", "acconto_giorni", "soglia_esenzione_giorni"),
            "md:col-4",
        ),
        ("Orari standard", "", ("orario_arrivo", "orario_partenza"), "col-6"),
        (
            "Bonifico dell'acconto",
            "Dati del conto: compaiono nell'email di approvazione e nel PDF di conferma.",
            ("iban", "intestatario_bonifico", "causale_bonifico"),
            "lg:col-4",
        ),
        (
            "Richieste e dati",
            "",
            ("consenso_giorni", "orizzonte_massimo", "anni_conservazione"),
            "lg:col-4",
        ),
    )

    class Meta:
        model = Configurazione
        fields = (
            "prenotazioni_bloccate",
            "messaggio_blocco",
            "inverno_dal_giorno",
            "inverno_dal_mese",
            "inverno_al_giorno",
            "inverno_al_mese",
            "acconto_percentuale",
            "acconto_giorni",
            "soglia_esenzione_giorni",
            "consenso_giorni",
            "orario_arrivo",
            "orario_partenza",
            "orizzonte_massimo",
            "anni_conservazione",
            "iban",
            "intestatario_bonifico",
            "causale_bonifico",
            "link_prenotazioni_vere",
        )
        widgets = {
            "inverno_dal_mese": Combobox(choices=MESI, placeholder="Scegli il mese"),
            "inverno_al_mese": Combobox(choices=MESI, placeholder="Scegli il mese"),
            "acconto_percentuale": _numero("%"),
            "acconto_giorni": _numero("giorni"),
            "soglia_esenzione_giorni": _numero("giorni"),
            "consenso_giorni": _numero("giorni"),
            "anni_conservazione": _numero("anni"),
            "orizzonte_massimo": SelettoreData(),
            "orario_arrivo": forms.TimeInput(attrs={"type": "time"}),
            "orario_partenza": forms.TimeInput(attrs={"type": "time"}),
            "messaggio_blocco": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "inverno_dal_giorno": "Dal giorno",
            "inverno_dal_mese": "Dal mese",
            "inverno_al_giorno": "Al giorno (incluso)",
            "inverno_al_mese": "Al mese",
            "acconto_percentuale": "Percentuale",
            "acconto_giorni": "Giorni per caricare la ricevuta",
            "soglia_esenzione_giorni": "Esenti i soggiorni fino a",
            "orario_arrivo": "Arrivo",
            "orario_partenza": "Partenza",
        }
        help_texts = {
            "acconto_percentuale": "Quota del preventivo da versare come acconto con il "
            "bonifico; all'approvazione si può sempre esentare o cambiare l'importo.",
            "acconto_giorni": "Giorni dall'approvazione entro cui caricare la ricevuta del "
            "bonifico; dopo la richiesta scade e le date si liberano.",
            "soglia_esenzione_giorni": "I soggiorni fino a questo numero di giorni non "
            "pagano l'acconto.",
            "consenso_giorni": "Giorni che il gruppo già presente ha per acconsentire a "
            "un'uscita in giornata o a una giornata genitori (al massimo fino alla vigilia); "
            "senza risposta il consenso è negato.",
            "orario_arrivo": "Orario standard di arrivo: arrivare prima va concordato con il "
            "gruppo uscente.",
            "orario_partenza": "Orario standard di partenza: partire dopo va concordato con il "
            "gruppo entrante.",
            "orizzonte_massimo": "Non si accettano richieste con data di arrivo successiva; "
            "si sposta in avanti quando si pubblica il nuovo listino.",
            "anni_conservazione": "Dopo questi anni dalla partenza i dati personali della "
            "prenotazione si anonimizzano (restano date, presenze e importi).",
            "causale_bonifico": "{numero} e {gruppo} si sostituiscono con i dati della "
            "prenotazione.",
        }

    def campi_blocco(self) -> list[forms.BoundField]:
        return [self[nome] for nome in self.BLOCCO]

    def gruppi(self) -> list[dict[str, Any]]:
        return [
            {"titolo": t, "descrizione": d, "campi": [self[n] for n in campi], "colonna": c}
            for t, d, campi, c in self.GRUPPI
        ]

    def altri_campi(self) -> list[forms.BoundField]:
        a_parte = set(self.BLOCCO).union(*(campi for _, _, campi, _ in self.GRUPPI))
        return [c for c in self.visible_fields() if c.name not in a_parte]


class VersioneForm(forms.Form):
    listino = forms.ModelChoiceField(Listino.objects.all(), label="Listino")
    nome = forms.CharField(label="Nome", max_length=50, help_text="Es. 2028.")
    pubblicata_il = forms.DateField(label="Pubblicata il", widget=SelettoreData())
    valida_dal = forms.DateField(label="Valida dal", widget=SelettoreData())
    copia_da = forms.ModelChoiceField(
        VersioneListino.objects.select_related("listino"),
        label="Copia le voci da",
        required=False,
        empty_label="Nessuna (versione vuota)",
    )


class DatiVersioneForm(forms.ModelForm):
    """Nome e date di una versione non ancora usata (per correggere un errore di inserimento)."""

    class Meta:
        model = VersioneListino
        fields = ("nome", "pubblicata_il", "valida_dal")
        widgets = {"pubblicata_il": SelettoreData(), "valida_dal": SelettoreData()}

    def clean(self) -> dict[str, Any]:
        dati: dict[str, Any] = super().clean() or {}
        if dati.get("pubblicata_il") and dati.get("valida_dal"):
            controlla_date(dati["pubblicata_il"], dati["valida_dal"])
        return dati


class VoceForm(forms.ModelForm):
    importo = CampoEuro(label="Importo (€)", min_value=0)

    class Meta:
        model = VoceListino
        fields = ("descrizione", "attivita", "area", "stagione", "unita")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["importo"] = Decimal(self.instance.importo_centesimi) / 100

    def save(self, commit: bool = True) -> VoceListino:
        self.instance.importo_centesimi = self.cleaned_data["importo"]
        return super().save(commit)


VociFormSet = forms.inlineformset_factory(
    VersioneListino, VoceListino, form=VoceForm, extra=1, can_delete=True
)


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = (
            "nome",
            "codice",
            "listino_default",
            "prioritaria",
            "richiede_specifica",
            "ordine",
        )
        labels = {"richiede_specifica": "Richiede la specifica"}
        help_texts = {
            "nome": "Come la vede chi prenota, nel modulo di richiesta.",
            "codice": "Identificativo breve (lettere minuscole, numeri e trattini), usato anche "
            "dall'import di SuperSaaS: dopo la creazione non si cambia.",
            "listino_default": "Listino proposto per le prenotazioni di questa categoria.",
            "prioritaria": "Ha la priorità prevista dal regolamento sulle date richieste.",
            "richiede_specifica": "Chi prenota deve scrivere di quale associazione o ente si tratta.",
            "ordine": "Posizione nell'elenco: prima i numeri più bassi.",
        }
        widgets = {"ordine": forms.NumberInput(attrs={"min": 0})}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["codice"].disabled = True


class NominaForm(forms.Form):
    email = forms.EmailField(
        label="Email dell'utente",
        help_text=(
            "Se l'account non esiste ancora viene creato: si attiva al primo accesso con "
            "Sestante con la stessa email."
        ),
    )
    ruolo = forms.ChoiceField(label="Ruolo", choices=Ruolo.choices)


class ExportForm(forms.Form):
    dal = forms.DateField(label="Dal", widget=SelettoreData())
    al = forms.DateField(label="Al", widget=SelettoreData())
    contenuto = forms.ChoiceField(
        label="Cosa",
        choices=[
            ("prenotazioni", "Prenotazioni (per data di arrivo)"),
            ("incassi", "Incassi (per data del pagamento)"),
        ],
    )
    formato = forms.ChoiceField(label="Formato", choices=[("xlsx", "Excel"), ("csv", "CSV")])

    def clean(self) -> dict[str, Any]:
        dati: dict[str, Any] = super().clean() or {}
        if dati.get("dal") and dati.get("al") and dati["al"] < dati["dal"]:
            self.add_error("al", "La fine non può precedere l'inizio.")
        return dati
