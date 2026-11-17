"""Calcolo del contributo: preventivo, consuntivo, acconto e saldo (§5).

Unica fonte di verità per gli importi: viste, PDF, export e import usano solo queste funzioni.
Importi in centesimi interi.
"""

import datetime
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from tana.base.models import Area, Configurazione
from tana.core.services import registra_decisione
from tana.listini.models import Attivita, Categoria, Listino, VersioneListino, VoceListino
from tana.listini.services import versione_applicabile

from .models import Pagamento, Prenotazione, RigaImporto, Stato, calcolo_riga

Fase = RigaImporto.Fase
Stagione = VoceListino.Stagione
Unita = VoceListino.Unita

# Con l'acconto (o dopo la conferma) il preventivo non si ricalcola più (D-13)
STATI_PREVENTIVO_CONGELATO = frozenset({Stato.CONFERMATA, Stato.SVOLTA, Stato.CHIUSA})

# Unità di conteggio quando la voce manca nel listino (D-07)
UNITA_PREDEFINITA: dict[str, str] = {
    Attivita.CAMPO: Unita.PERSONA_GIORNO,
    Attivita.BIVACCO: Unita.PERSONA_NOTTE,
}


class PreventivoCongelato(ValidationError):
    def __init__(self) -> None:
        super().__init__("Il preventivo è congelato: l'acconto è già stato versato.")


@dataclass
class RigaCalcolata:
    """Riga generata dal listino, non ancora salvata. `prezzo` None: da definire (P-04)."""

    attivita: str
    area: Area | None
    stagione: str
    unita: str
    quantita: int
    prezzo: int | None
    voce: VoceListino | None = None
    descrizione: str = ""
    stimata: bool = False
    persone: int | None = None
    conteggio: int | None = None

    @property
    def importo(self) -> int | None:
        return None if self.prezzo is None else self.prezzo * self.quantita

    @property
    def calcolo(self) -> str:
        return calcolo_riga(self.prezzo, self.quantita, self.persone, self.conteggio, self.unita)

    @property
    def chiave(self) -> tuple[str, int | None, str, str]:
        return (self.attivita, self.area.pk if self.area else None, self.stagione, self.unita)


@dataclass
class Riepilogo:
    """Totali di una fase. `totale` None finché c'è una riga da definire."""

    righe: list[RigaImporto]
    totale_calcolato: int | None
    totale: int | None
    per_area: dict[str, int | None] = field(default_factory=dict)

    @property
    def da_definire(self) -> bool:
        return self.totale is None


# --- Listino e versione -----------------------------------------------------------------


def listino_applicato(prenotazione: Prenotazione) -> Listino:
    """Listino della categoria; associativo finché la categoria prioritaria chiesta non è
    concessa (P-06)."""
    categoria = prenotazione.categoria
    if (
        categoria.prioritaria
        and prenotazione.categoria_prioritaria_richiesta
        and not prenotazione.categoria_prioritaria_concessa
    ):
        return Listino.objects.get(tipo=Listino.Tipo.ASSOCIATIVO)
    return categoria.listino_default


def versione_da_applicare(prenotazione: Prenotazione) -> VersioneListino:
    """Versione congelata sulla prenotazione se è del listino applicato, altrimenti quella di
    D-09 (data della richiesta, primo giorno del soggiorno)."""
    listino = listino_applicato(prenotazione)
    congelata = prenotazione.versione_listino
    if congelata is not None and congelata.listino_id == listino.pk:
        return congelata
    versione = versione_applicabile(
        listino, data_richiesta=prenotazione.data_richiesta, primo_giorno=prenotazione.arrivo
    )
    if versione is None:
        raise ValidationError(f"Nessuna versione del listino «{listino}» applicabile.")
    return versione


# --- Calcolo ----------------------------------------------------------------------------


def _giorni(arrivo: datetime.date, partenza: datetime.date, unita: str) -> Iterator[datetime.date]:
    """Giorni contati: a giorni arrivo e partenza inclusi, a notti escluso il giorno di
    partenza (D-04)."""
    fine = partenza if unita == Unita.PERSONA_NOTTE else partenza + datetime.timedelta(days=1)
    giorno = arrivo
    while giorno < fine:
        yield giorno
        giorno += datetime.timedelta(days=1)


class _Voci:
    """Voci di una versione indicizzate per attività, area e stagione."""

    def __init__(self, versione: VersioneListino, conf: Configurazione) -> None:
        self.conf = conf
        self.voci: dict[tuple[str, int | None], dict[str, VoceListino]] = defaultdict(dict)
        for voce in versione.voci.all():
            self.voci[(voce.attivita, voce.area_id)][voce.stagione] = voce

    def unita(self, attivita: str, area: Area | None) -> str:
        voci = self.voci.get((attivita, area.pk if area else None))
        if voci:
            return next(iter(voci.values())).unita
        return UNITA_PREDEFINITA.get(attivita, Unita.PERSONA_GIORNO)

    def per_giorno(
        self, attivita: str, area: Area | None, giorno: datetime.date
    ) -> tuple[str, VoceListino | None]:
        """Stagione e voce di quel giorno; la voce "tutto l'anno" vale in ogni stagione."""
        voci = self.voci.get((attivita, area.pk if area else None), {})
        stagione = Stagione.INVERNALE if self.conf.e_inverno(giorno) else Stagione.ESTIVA
        if stagione in voci:
            return stagione, voci[stagione]
        if Stagione.NESSUNA in voci:
            return Stagione.NESSUNA, voci[Stagione.NESSUNA]
        # Manca la voce: senza voci stagionali la chiave resta "tutto l'anno"
        return (stagione if voci else Stagione.NESSUNA), None


def _righe(
    voci: _Voci,
    attivita: str,
    area: Area | None,
    giorni: list[datetime.date],
    persone: int,
    *,
    stimata: bool,
    descrizione: str = "",
) -> list[RigaCalcolata]:
    """Righe per `persone` nei `giorni` contati, raggruppate per voce (stagione)."""
    unita = voci.unita(attivita, area)
    gruppi: dict[str, tuple[VoceListino | None, int]] = {}
    for giorno in giorni:
        stagione, voce = voci.per_giorno(attivita, area, giorno)
        _, conteggio = gruppi.get(stagione, (voce, 0))
        gruppi[stagione] = (voce, conteggio + 1)
    righe = []
    for stagione, (voce, conteggio) in gruppi.items():
        quantita = 1 if unita == Unita.FORFAIT else persone * conteggio
        righe.append(
            RigaCalcolata(
                attivita=attivita,
                area=area,
                stagione=stagione,
                unita=unita,
                quantita=quantita,
                prezzo=voce.importo_centesimi if voce else None,
                voce=voce,
                descrizione=descrizione or (voce.descrizione if voce else ""),
                stimata=stimata,
                persone=None if unita == Unita.FORFAIT else persone,
                conteggio=None if unita == Unita.FORFAIT else conteggio,
            )
        )
    return righe


@dataclass
class Soggiorno:
    """Dati di un soggiorno non ancora salvato, per il preventivo in tempo reale del modulo.

    Ha gli stessi attributi usati da `listino_applicato` e `versione_da_applicare`.
    """

    categoria: Categoria
    arrivo: datetime.date
    partenza: datetime.date
    presenze: list[tuple[Area, int]]
    attivita: list[tuple[datetime.date, str, int]] = field(default_factory=list)
    data_richiesta: datetime.date = field(default_factory=timezone.localdate)
    categoria_prioritaria_richiesta: bool = False
    categoria_prioritaria_concessa: bool = False
    versione_listino: VersioneListino | None = None


def calcola(prenotazione: Prenotazione, fase: str = Fase.PREVENTIVO) -> list[RigaCalcolata]:
    """Righe del listino per la prenotazione (§5.1), senza salvarle.

    Nel consuntivo valgono le persone effettive; dove mancano le previste (riga stimata).
    """
    versione = (
        versione_da_applicare(prenotazione)
        if fase == Fase.PREVENTIVO
        else _versione_del_preventivo(prenotazione)
    )
    presenze = [
        (p.area, *_persone(p, fase))
        for p in prenotazione.presenze.select_related("area").order_by("area__ordine")
    ]
    attivita = [
        (a.data, a.tipo, *_persone(a, fase))
        for a in prenotazione.attivita_giornaliere.order_by("data", "pk")
    ]
    return _calcola(versione, prenotazione.arrivo, prenotazione.partenza, presenze, attivita)


def simula(soggiorno: Soggiorno) -> list[RigaCalcolata]:
    """Preventivo di un soggiorno non salvato, con le stesse regole di `calcola`."""
    return _calcola(
        versione_da_applicare(soggiorno),  # type: ignore[arg-type]
        soggiorno.arrivo,
        soggiorno.partenza,
        [(area, persone, False) for area, persone in soggiorno.presenze if persone],
        [(data, tipo, persone, False) for data, tipo, persone in soggiorno.attivita if persone],
    )


def _calcola(
    versione: VersioneListino,
    arrivo: datetime.date,
    partenza: datetime.date,
    presenze: list[tuple[Area, int, bool]],
    attivita: list[tuple[datetime.date, str, int, bool]],
) -> list[RigaCalcolata]:
    voci = _Voci(versione, Configurazione.corrente())
    notti = (partenza - arrivo).days
    righe: list[RigaCalcolata] = []

    for area, persone, stimata in presenze:
        if notti < 1:
            raise ValidationError("Un soggiorno in un'area dura almeno una notte.")
        # Una sola notte è un bivacco, conteggiato a notti (D-04, D-07)
        soggiorno: str = Attivita.BIVACCO if notti == 1 else Attivita.CAMPO
        unita = voci.unita(soggiorno, area)
        giorni = list(_giorni(arrivo, partenza, unita))
        righe += _righe(voci, soggiorno, area, giorni, persone, stimata=stimata)

    for data, tipo, persone, stimata in attivita:
        descrizione = f"{Attivita(tipo).label.capitalize()} – {data:%d/%m/%Y}"
        righe += _righe(voci, tipo, None, [data], persone, stimata=stimata, descrizione=descrizione)

    for riga in righe:
        if not riga.descrizione:
            riga.descrizione = _descrizione_predefinita(riga)
    return righe


def _persone(oggetto: Any, fase: str) -> tuple[int, bool]:
    if fase == Fase.CONSUNTIVO and oggetto.persone_effettive is not None:
        return oggetto.persone_effettive, False
    return oggetto.persone_previste, fase == Fase.CONSUNTIVO


def _descrizione_predefinita(riga: RigaCalcolata) -> str:
    testo = Attivita(riga.attivita).label.capitalize()
    if riga.area:
        testo += f" – {riga.area}"
    if riga.stagione != Stagione.NESSUNA:
        testo += f" ({Stagione(riga.stagione).label})"
    return testo


def _versione_del_preventivo(prenotazione: Prenotazione) -> VersioneListino:
    # Il consuntivo usa la stessa versione del preventivo (§5.2)
    if prenotazione.versione_listino is None:
        raise ValidationError("Prima del consuntivo serve il preventivo.")
    return prenotazione.versione_listino


# --- Salvataggio e riepiloghi -----------------------------------------------------------


def preventivo_congelato(prenotazione: Prenotazione) -> bool:
    # Basta la ricevuta caricata; una ricevuta respinta non conta
    return (
        prenotazione.stato in STATI_PREVENTIVO_CONGELATO
        or prenotazione.pagamenti.filter(tipo=Pagamento.Tipo.ACCONTO)
        .exclude(stato=Pagamento.StatoPagamento.RESPINTO)
        .exists()
    )


@transaction.atomic
def aggiorna_preventivo(prenotazione: Prenotazione, *, utente: Any = None) -> Riepilogo:
    """Ricalcola e salva le righe del preventivo, congelando la versione di listino (D-09).

    Voci libere e rettifiche restano; le voci da definire già valorizzate mantengono il
    prezzo deciso.
    """
    if preventivo_congelato(prenotazione):
        raise PreventivoCongelato
    righe = calcola(prenotazione, Fase.PREVENTIVO)
    prenotazione.versione_listino = versione_da_applicare(prenotazione)
    prenotazione.save(update_fields=["versione_listino", "aggiornata_il"])
    _salva_righe(prenotazione, Fase.PREVENTIVO, righe, utente)
    return riepilogo(prenotazione, Fase.PREVENTIVO)


@transaction.atomic
def aggiorna_consuntivo(prenotazione: Prenotazione, *, utente: Any = None) -> Riepilogo:
    """Ricalcola e salva le righe del consuntivo con la versione del preventivo (§5.2)."""
    righe = calcola(prenotazione, Fase.CONSUNTIVO)
    _salva_righe(prenotazione, Fase.CONSUNTIVO, righe, utente)
    return riepilogo(prenotazione, Fase.CONSUNTIVO)


def _salva_righe(
    prenotazione: Prenotazione, fase: str, righe: list[RigaCalcolata], utente: Any
) -> None:
    vecchie = prenotazione.righe_importo.filter(fase=fase, calcolata=True)
    # Prezzi decisi per le voci da definire (P-04): si riapplicano alla stessa chiave
    valorizzate = {
        (r.attivita, r.area_id, r.stagione, r.unita): r
        for r in vecchie.filter(voce__isnull=True, prezzo_centesimi__isnull=False)
    }
    vecchie.delete()
    for ordine, riga in enumerate(righe):
        decisa = valorizzate.get(riga.chiave) if riga.prezzo is None else None
        prezzo = decisa.prezzo_centesimi if decisa else riga.prezzo
        RigaImporto.objects.create(
            prenotazione=prenotazione,
            fase=fase,
            voce=riga.voce,
            descrizione=riga.descrizione,
            attivita=riga.attivita,
            area=riga.area,
            stagione=riga.stagione,
            unita=riga.unita,
            quantita=riga.quantita,
            persone=riga.persone,
            conteggio=riga.conteggio,
            prezzo_centesimi=prezzo,
            importo_centesimi=None if prezzo is None else prezzo * riga.quantita,
            calcolata=True,
            stimata=riga.stimata,
            deciso_da=decisa.deciso_da if decisa else "",
            motivazione=decisa.motivazione if decisa else "",
            registrata_da=decisa.registrata_da if decisa else utente,
            ordine=ordine,
        )


def riepilogo(prenotazione: Prenotazione, fase: str = Fase.PREVENTIVO) -> Riepilogo:
    """Totale calcolato (senza rettifiche), totale e dettaglio per area di una fase."""
    # Prima le righe del listino, poi le voci libere, per ultima la rettifica
    righe = list(
        prenotazione.righe_importo.filter(fase=fase)
        .select_related("area")
        .order_by("rettifica", "-calcolata", "ordine", "pk")
    )
    senza_rettifiche = [r for r in righe if not r.rettifica]
    totale_calcolato = _somma(senza_rettifiche)
    totale = None if totale_calcolato is None else _somma(righe)
    per_area: dict[str, int | None] = {}
    for riga in senza_rettifiche:
        if riga.area is None:
            continue
        nome = str(riga.area)
        parziale = per_area.get(nome, 0)
        per_area[nome] = (
            None
            if parziale is None or riga.importo_centesimi is None
            else parziale + riga.importo_centesimi
        )
    return Riepilogo(
        righe=righe, totale_calcolato=totale_calcolato, totale=totale, per_area=per_area
    )


def _somma(righe: list[RigaImporto]) -> int | None:
    if any(r.importo_centesimi is None for r in righe):
        return None
    return sum(r.importo_centesimi or 0 for r in righe)


# --- Acconto e saldo --------------------------------------------------------------------


def acconto_previsto(prenotazione: Prenotazione) -> int | None:
    """Acconto da versare (D-13, §5.1 punto 7), in centesimi; None se il preventivo è da
    definire.

    Zero per i soggiorni fino alla soglia di giorni e per le sole attività in giornata (le quote
    si consegnano all'arrivo). Percentuale arrotondata al centesimo, il mezzo per eccesso.
    """
    return calcola_acconto(
        riepilogo(prenotazione, Fase.PREVENTIVO).totale,
        prenotazione.arrivo,
        prenotazione.partenza,
        soggiorno=prenotazione.presenze.exists(),
    )


def calcola_acconto(
    totale: int | None, arrivo: datetime.date, partenza: datetime.date, *, soggiorno: bool
) -> int | None:
    """Regola dell'acconto (D-13) su un totale; `soggiorno` falso per le sole attività in
    giornata."""
    if totale is None:
        return None
    conf = Configurazione.corrente()
    giorni = (partenza - arrivo).days + 1
    if not soggiorno or giorni <= conf.soglia_esenzione_giorni:
        return 0
    return (totale * conf.acconto_percentuale + 50) // 100


def acconto_versato(prenotazione: Prenotazione) -> int:
    somma = prenotazione.pagamenti.filter(
        tipo=Pagamento.Tipo.ACCONTO, stato=Pagamento.StatoPagamento.VERIFICATO
    ).aggregate(totale=Sum("importo_centesimi"))["totale"]
    return somma or 0


def saldo(prenotazione: Prenotazione) -> int | None:
    """Saldo da incassare: totale del consuntivo meno l'acconto versato (§5.2)."""
    totale = riepilogo(prenotazione, Fase.CONSUNTIVO).totale
    return None if totale is None else totale - acconto_versato(prenotazione)


# --- Interventi dell'amministratore -----------------------------------------------------


@transaction.atomic
def valorizza_riga(
    riga: RigaImporto, *, prezzo_centesimi: int, utente: Any, deciso_da: str, motivazione: str
) -> RigaImporto:
    """Prezzo di una voce da definire (P-04), con "deciso da" e motivazione (P-03)."""
    if not riga.calcolata or riga.voce_id is not None:
        raise ValidationError("Si valorizzano solo le voci mancanti nel listino.")
    if riga.fase == Fase.PREVENTIVO and preventivo_congelato(riga.prenotazione):
        raise PreventivoCongelato
    prima = {"prezzo_centesimi": riga.prezzo_centesimi}
    riga.prezzo_centesimi = prezzo_centesimi
    riga.importo_centesimi = prezzo_centesimi * riga.quantita
    riga.deciso_da, riga.motivazione, riga.registrata_da = deciso_da, motivazione, utente
    registra_decisione(
        riga.prenotazione,
        f"voce valorizzata: {riga.descrizione}",
        utente=utente,
        deciso_da=deciso_da,
        motivazione=motivazione,
        prima=prima,
        dopo={"prezzo_centesimi": prezzo_centesimi},
    )
    riga.save()
    return riga


@transaction.atomic
def aggiungi_voce_libera(
    prenotazione: Prenotazione,
    *,
    fase: str,
    descrizione: str,
    prezzo_centesimi: int,
    quantita: int = 1,
    area: Area | None = None,
    utente: Any = None,
    deciso_da: str = "",
    motivazione: str = "",
) -> RigaImporto:
    """Voce libera (§5.1 punto 5): sovrapprezzo dell'esclusiva, pellet, forfait, danni.

    Con "deciso da" la voce è una decisione discrezionale (D-14) e va nello storico.
    """
    if fase == Fase.PREVENTIVO and preventivo_congelato(prenotazione):
        raise PreventivoCongelato
    if deciso_da or motivazione:
        registra_decisione(
            prenotazione,
            f"voce libera: {descrizione}",
            utente=utente,
            deciso_da=deciso_da,
            motivazione=motivazione,
            dopo={"quantita": quantita, "prezzo_centesimi": prezzo_centesimi},
        )
    return RigaImporto.objects.create(
        prenotazione=prenotazione,
        fase=fase,
        descrizione=descrizione,
        area=area,
        quantita=quantita,
        prezzo_centesimi=prezzo_centesimi,
        importo_centesimi=prezzo_centesimi * quantita,
        deciso_da=deciso_da,
        motivazione=motivazione,
        registrata_da=utente,
        ordine=1000,
    )


@transaction.atomic
def modifica_quota(
    prenotazione: Prenotazione,
    *,
    fase: str,
    totale_centesimi: int,
    utente: Any,
    deciso_da: str,
    motivazione: str,
) -> Riepilogo:
    """Porta il totale di una fase all'importo deciso, anche zero (D-24): una riga di
    rettifica per la differenza; il totale calcolato resta visibile."""
    if fase == Fase.PREVENTIVO and preventivo_congelato(prenotazione):
        raise PreventivoCongelato
    if totale_centesimi < 0:
        raise ValidationError("La quota non può essere negativa.")
    prima = riepilogo(prenotazione, fase)
    if prima.totale_calcolato is None:
        raise ValidationError("Valorizza prima le voci da definire.")
    registra_decisione(
        prenotazione,
        f"quota modificata ({Fase(fase).label})",
        utente=utente,
        deciso_da=deciso_da,
        motivazione=motivazione,
        prima={"totale_centesimi": prima.totale},
        dopo={"totale_centesimi": totale_centesimi},
    )
    prenotazione.righe_importo.filter(fase=fase, rettifica=True).delete()
    differenza = totale_centesimi - prima.totale_calcolato
    if differenza:
        RigaImporto.objects.create(
            prenotazione=prenotazione,
            fase=fase,
            descrizione="Rettifica della quota",
            prezzo_centesimi=differenza,
            importo_centesimi=differenza,
            rettifica=True,
            deciso_da=deciso_da,
            motivazione=motivazione,
            registrata_da=utente,
            ordine=2000,
        )
    return riepilogo(prenotazione, fase)
