"""Form dell'area del richiedente: nuova richiesta in tre passi (mockup 2), ricevuta, messaggi.

I form raccolgono e normalizzano i dati; le regole di dominio restano nei servizi
(`flusso.invia_richiesta`, `contributo`, `consensi`).
"""

import datetime
from typing import Any

from agesci_theme.forms import SelettoreData
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db.models import TextChoices

from tana.base.models import Area
from tana.listini.models import Categoria

from .models import AttivitaGiornaliera, Unita


class PassoRichiedente(forms.Form):
    categoria = forms.ModelChoiceField(
        Categoria.objects.all(),
        label="Associazione o ente",
        empty_label="Scegli…",
        help_text="Le categorie prioritarie (Fo.Ca., eventi regionali, Comune) vanno concesse "
        "dalla gestione: fino ad allora il preventivo è sul listino associativo.",
    )
    specifica_categoria = forms.CharField(
        label="Specifica l'associazione o l'ente",
        required=False,
        max_length=200,
        help_text="Obbligatoria per «altra associazione», «terzo settore» e «altro».",
    )
    gruppo = forms.CharField(label="Gruppo o ente", max_length=200, help_text="Es. Avellino 1.")
    unita = forms.MultipleChoiceField(
        label="Unità presenti",
        choices=Unita.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    referente_nome = forms.CharField(label="Nome e cognome del referente", max_length=200)
    referente_email = forms.EmailField(label="Email del referente")
    referente_telefono = forms.CharField(label="Telefono del referente", max_length=30)
    capo_nome = forms.CharField(
        label="Nome e cognome del capo responsabile", max_length=200, required=False
    )
    capo_email = forms.EmailField(label="Email del capo responsabile", required=False)
    capo_telefono = forms.CharField(
        label="Telefono del capo responsabile", max_length=30, required=False
    )

    def clean(self) -> dict[str, Any]:
        dati: dict[str, Any] = super().clean() or {}
        categoria = dati.get("categoria")
        if categoria and categoria.richiede_specifica and not dati.get("specifica_categoria"):
            self.add_error("specifica_categoria", "Specifica l'associazione o l'ente.")
        return dati


class TipoSoggiorno(TextChoices):
    TENDE = "TENDE", "Campo in tenda"
    ACCANTONAMENTO = "ACC", "Accantonamento"
    CONGIUNTA = "CONGIUNTA", "Tende + accantonamento"
    BIVACCO = "BIVACCO", "Bivacco (una notte)"
    USCITA = "USCITA", "Uscita in giornata"


USCITE = [
    (AttivitaGiornaliera.Tipo.USCITA_CUCINA, "Con uso cucina"),
    (AttivitaGiornaliera.Tipo.USCITA_AREA_VERDE, "Solo area verde"),
]


class PassoSoggiorno(forms.Form):
    tipo = forms.ChoiceField(
        label="Tipo di soggiorno", choices=TipoSoggiorno.choices, widget=forms.RadioSelect
    )
    arrivo = forms.DateField(label="Arrivo", widget=SelettoreData())
    # Per il bivacco e l'uscita in giornata si calcola da sola (campo nascosto dal JavaScript)
    partenza = forms.DateField(label="Partenza", required=False, widget=SelettoreData())
    persone_acc = forms.IntegerField(label="Persone in accantonamento", min_value=0, required=False)
    persone_tende = forms.IntegerField(label="Persone in tenda", min_value=0, required=False)
    area_bivacco = forms.ChoiceField(
        label="Area del bivacco",
        choices=[(Area.ACCANTONAMENTO, "Accantonamento"), (Area.TENDE, "Area tende")],
        required=False,
        widget=forms.RadioSelect,
    )
    tipo_uscita = forms.ChoiceField(
        label="Uscita", choices=USCITE, required=False, widget=forms.RadioSelect
    )
    persone_uscita = forms.IntegerField(label="Persone all'uscita", min_value=0, required=False)
    ospiti_data = forms.DateField(
        label="Giornata genitori e ospiti",
        required=False,
        widget=SelettoreData(),
        help_text="Facoltativa, durante il soggiorno, solo con uso della cucina per il pranzo.",
    )
    ospiti_persone = forms.IntegerField(label="Ospiti", min_value=0, required=False)
    esclusiva_richiesta = forms.BooleanField(
        label="Chiedo l'uso esclusivo della base",
        required=False,
        help_text="Solo prenotando il solo accantonamento: va concesso dalla direzione e può "
        "avere un sovrapprezzo.",
    )

    def clean(self) -> dict[str, Any]:
        dati: dict[str, Any] = super().clean() or {}
        tipo, arrivo = dati.get("tipo"), dati.get("arrivo")
        if not tipo or not arrivo:
            return dati
        presenze: dict[str, int] = {}
        attivita: list[tuple[datetime.date, str, int]] = []
        partenza = dati.get("partenza")

        if tipo == TipoSoggiorno.USCITA:
            if not dati.get("tipo_uscita"):
                self.add_error("tipo_uscita", "Scegli il tipo di uscita.")
            if not dati.get("persone_uscita"):
                self.add_error("persone_uscita", "Indica quante persone.")
            partenza = arrivo
            if dati.get("tipo_uscita") and dati.get("persone_uscita"):
                attivita.append((arrivo, dati["tipo_uscita"], dati["persone_uscita"]))
        elif tipo == TipoSoggiorno.BIVACCO:
            area = dati.get("area_bivacco")
            persone = (
                dati.get("persone_acc")
                if area == Area.ACCANTONAMENTO
                else dati.get("persone_tende")
            )
            if not area:
                self.add_error("area_bivacco", "Scegli l'area del bivacco.")
            elif not persone:
                self.add_error(
                    "persone_acc" if area == Area.ACCANTONAMENTO else "persone_tende",
                    "Indica quante persone.",
                )
            else:
                presenze[area] = persone
            partenza = arrivo + datetime.timedelta(days=1)
        else:
            aree = {
                TipoSoggiorno.TENDE: [Area.TENDE],
                TipoSoggiorno.ACCANTONAMENTO: [Area.ACCANTONAMENTO],
                TipoSoggiorno.CONGIUNTA: [Area.ACCANTONAMENTO, Area.TENDE],
            }[TipoSoggiorno(tipo)]
            for codice in aree:
                campo = "persone_acc" if codice == Area.ACCANTONAMENTO else "persone_tende"
                if not dati.get(campo):
                    self.add_error(campo, "Indica quante persone.")
                else:
                    presenze[codice] = dati[campo]
            if not partenza:
                self.add_error("partenza", "Indica la data di partenza.")
            elif partenza <= arrivo:
                self.add_error("partenza", "La partenza deve essere dopo l'arrivo.")
            if dati.get("ospiti_data") or dati.get("ospiti_persone"):
                if not (dati.get("ospiti_data") and dati.get("ospiti_persone")):
                    self.add_error("ospiti_persone", "Indica data e numero degli ospiti.")
                else:
                    attivita.append(
                        (
                            dati["ospiti_data"],
                            AttivitaGiornaliera.Tipo.GIORNATA_OSPITI,
                            dati["ospiti_persone"],
                        )
                    )
        if dati.get("esclusiva_richiesta") and tipo != TipoSoggiorno.ACCANTONAMENTO:
            self.add_error(
                "esclusiva_richiesta", "L'uso esclusivo si chiede solo con il solo accantonamento."
            )
        dati["partenza"] = partenza
        dati["presenze"] = presenze
        dati["attivita"] = attivita
        return dati


class PassoInvio(forms.Form):
    note = forms.CharField(
        label="Note per la gestione",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Orari di arrivo, esigenze particolari… Nessun dato sui ragazzi.",
    )
    accetto = forms.BooleanField(
        label="Ho letto il regolamento della base e l'informativa sul trattamento dei dati",
        required=True,
    )


class RicevutaForm(forms.Form):
    ricevuta = forms.FileField(
        label="Ricevuta del bonifico",
        help_text="PDF o foto (JPG, PNG), al massimo 10 MB.",
        validators=[FileExtensionValidator(["pdf", "jpg", "jpeg", "png"])],
    )

    MAX_BYTE = 10 * 1024 * 1024

    def clean_ricevuta(self) -> Any:
        ricevuta = self.cleaned_data["ricevuta"]
        if ricevuta.size > self.MAX_BYTE:
            raise ValidationError("Il file supera i 10 MB.")
        return ricevuta


class AnnullaForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo (facoltativo)", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class MessaggioForm(forms.Form):
    testo = forms.CharField(label="Messaggio", widget=forms.Textarea(attrs={"rows": 3}))
