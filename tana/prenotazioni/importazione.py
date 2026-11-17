"""Import una tantum dai due calendari SuperSaaS (§7, D-23).

Due passi: `proposte()` legge i CSV e propone una prenotazione per riga (o per coppia di righe
con le stesse date nei due calendari) con categoria, stato, unione, esclusiva e anomalie; il file
di revisione le mostra all'operatore, che le corregge; `applica()` importa usando le decisioni,
in un'unica transazione. Nessuna riga si perde in silenzio: ogni riga dei CSV deve avere una
decisione (importare o scartare). Nessuna email, nessun consenso: è storico.
"""

import csv
import datetime
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from tana.base.models import Area
from tana.core.services import registra_decisione, registra_evento
from tana.listini.models import Categoria

from . import contributo
from .models import (
    AttivitaGiornaliera,
    Contatto,
    Prenotazione,
    PresenzaArea,
    Stato,
    Unita,
)
from .services import DateOccupate, assegna_numero, sincronizza_occupazioni

NOTA_IMPORT = "Importata da SuperSaaS: importi ricalcolati con il listino, da verificare."
DECISO_DA_IMPORT = "Import SuperSaaS (date riservate dall'amministratore)"

CODICI_UNITA = {
    "1": Unita.CASTORINI,
    "2": Unita.LC,
    "3": Unita.EG,
    "4": Unita.RS,
    "5": Unita.COCA,
    "6": Unita.ALTRO,
}
STATI_IMPORT = (Stato.RICHIESTA, Stato.CONFERMATA, Stato.SVOLTA, Stato.NON_SVOLTA)
ESCLUSIVA = ("NO", "RICHIESTA", "CONCESSA")
USCITE = (AttivitaGiornaliera.Tipo.USCITA_CUCINA, AttivitaGiornaliera.Tipo.USCITA_AREA_VERDE)


class ErroreImport(Exception):
    """Errore che ferma l'import, con l'indicazione delle righe."""


# --- Lettura dei CSV --------------------------------------------------------------------


@dataclass
class Riga:
    """Una riga di un calendario SuperSaaS, già normalizzata."""

    calendario: str  # "acc" o "tende"
    id: str
    pacchetto: str
    arrivo: datetime.date
    partenza: datetime.date
    creata_da_amministratore: bool
    nome: str
    email: str
    telefono: str
    partecipanti: str
    gruppo: str
    approvata: bool
    creata_il: datetime.date
    unita: list[str]
    note: str

    @property
    def notti(self) -> int:
        return (self.partenza - self.arrivo).days

    @property
    def chiave(self) -> str:
        return f"{self.calendario}-{self.id}"


_DATA = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?")


def _data_ora(testo: str, riga: str) -> datetime.datetime:
    m = _DATA.match(testo or "")
    if not m:
        raise ErroreImport(f"{riga}: data non leggibile «{testo}».")
    return datetime.datetime(int(m[3]), int(m[2]), int(m[1]), int(m[4] or 0), int(m[5] or 0))


def leggi(percorso: Path, calendario: str) -> list[Riga]:
    """Legge un export SuperSaaS (17 colonne; la prima ha il nome del calendario)."""
    with open(percorso, encoding="utf-8-sig", newline="") as fh:
        lettore = csv.DictReader(fh)
        colonne = lettore.fieldnames or []
        if len(colonne) != 17:
            raise ErroreImport(f"{percorso.name}: attese 17 colonne, trovate {len(colonne)}.")
        pacchetto = colonne[0]
        righe = []
        for n, dati in enumerate(lettore, start=2):
            etichetta = f"{percorso.name} riga {n}"
            inizio = _data_ora(dati["Inizio"], etichetta)
            fine = _data_ora(dati["Fine"], etichetta)
            # Una fine alle 0:00 vale come partenza il giorno prima
            partenza = (
                (fine - datetime.timedelta(minutes=1)).date()
                if fine.time() == datetime.time(0, 0)
                else fine.date()
            )
            if partenza < inizio.date():
                raise ErroreImport(f"{etichetta}: la fine precede l'inizio.")
            righe.append(
                Riga(
                    calendario=calendario,
                    id=(dati["ID"] or "").strip(),
                    pacchetto=(dati[pacchetto] or "").strip(),
                    arrivo=inizio.date(),
                    partenza=partenza,
                    creata_da_amministratore=bool((dati["Creato da"] or "").strip()),
                    nome=" ".join((dati["Nome e cognome"] or "").split()),
                    email=(dati["Email"] or "").strip().lower(),
                    telefono=" ".join(
                        (
                            (dati["Cellulare"] or "").strip() or (dati["Telefono"] or "").strip()
                        ).split()
                    ),
                    partecipanti=" ".join((dati["Partecipanti (inclusi i capi)"] or "").split()),
                    gruppo=" ".join((dati["Gruppo"] or "").split()),
                    approvata=(dati["Stato"] or "").strip().lower() == "approvato",
                    creata_il=_data_ora(dati["Creato il"], etichetta).date(),
                    unita=[
                        CODICI_UNITA[c] for c in re.findall(r"[1-6]", dati["Unità presenti"] or "")
                    ],
                    note=(dati["Note"] or "").strip(),
                )
            )
    if len({r.id for r in righe}) != len(righe):
        raise ErroreImport(f"{percorso.name}: ID ripetuti.")
    return righe


# --- Proposte ---------------------------------------------------------------------------


@dataclass
class Proposta:
    """Una prenotazione proposta: una riga, o una coppia accantonamento + tende."""

    righe: list[Riga]
    categoria: str
    stato: str
    azione: str = "IMPORTA"
    unione: bool = False
    esclusiva: str = "NO"
    persone_acc: int | None = None
    persone_tende: int | None = None
    uscita: str = ""  # tipo dell'attività in giornata, se la prenotazione non ha notti
    prioritaria_senza_contatti: bool = False
    referente: bool = True  # crea il Contatto dai dati della riga
    anomalie: list[str] = field(default_factory=list)

    @property
    def chiave(self) -> str:
        return "+".join(r.chiave for r in self.righe)

    @property
    def principale(self) -> Riga:
        return self.righe[0]


def _numero(testo: str) -> tuple[int | None, str | None]:
    if re.fullmatch(r"\d+", testo):
        return int(testo), None
    trovato = re.search(r"\d+", testo)
    if trovato and not re.search(r"@|\bvia\b|\bpiazza\b", testo, re.I):
        return int(trovato[0]), f"partecipanti ricavati da «{testo}»"
    return None, f"partecipanti non numerici: «{testo}»" if testo else "partecipanti non indicati"


_PROVA = re.compile(r"^\d+$|\bprova\b|\btest\b", re.I)
_PRIORITARIE = (
    (re.compile(r"^\s*CFA\b", re.I), "foca-nazionale"),
    (re.compile(r"^\s*CF[MT]\b", re.I), "foca-regionale"),
    (re.compile(r"^\s*comune\b", re.I), "comune"),
)


def _categoria(riga: Riga) -> tuple[str, bool]:
    """Categoria proposta e se è una data riservata dall'amministratore (prioritaria)."""
    if riga.creata_da_amministratore:
        for regola, codice in _PRIORITARIE:
            if regola.search(riga.gruppo):
                return codice, True
    testo = f"{riga.gruppo} {riga.note} {riga.email}"
    if re.search(r"cngei|\bsezione\b", testo, re.I):
        return "gruppo-cngei", False
    if re.search(r"campo di competenz|evento regionale", riga.gruppo, re.I):
        return "eventi-regionali", False
    if re.search(r"\bzona\b", riga.gruppo, re.I):
        return "zone-agesci", False
    # Gruppi AGESCI: «Città numero» all'inizio (Avellino 1, montefalcione1, Roma 147 …)
    if re.search(r"agesci", testo, re.I) or re.match(r"^[A-Za-zÀ-ú' ]+?\s?\d{1,3}\b", riga.gruppo):
        return "gruppo-agesci", False
    if re.search(r"associazion|\ba\.?p\.?s\b|onlus|\bodv\b", riga.gruppo, re.I):
        return "terzo-settore", False
    return "altro", False


def _stato(riga: Riga, oggi: datetime.date) -> str:
    passata = riga.partenza < oggi
    if riga.approvata:
        return Stato.SVOLTA if passata else Stato.CONFERMATA
    return Stato.NON_SVOLTA if passata else Stato.RICHIESTA


def _proposta(righe: list[Riga], oggi: datetime.date, amministratori: set[str]) -> Proposta:
    principale = righe[0]
    categoria, riservata = _categoria(principale)
    # L'amministratore che ha inserito la riga con i propri dati non è il referente del gruppo:
    # come Contatto, la prenotazione finirebbe sul suo account e le email arriverebbero a lui
    dati_amministratore = bool({principale.nome.lower(), principale.email} & amministratori)
    proposta = Proposta(
        righe=righe,
        categoria=categoria,
        stato=_stato(principale, oggi),
        unione=len(righe) > 1,
        prioritaria_senza_contatti=riservata,
        referente=not riservata and not dati_amministratore,
    )
    if riservata:
        proposta.anomalie.append("date riservate dall'amministratore: prioritaria senza contatti")
    elif dati_amministratore:
        proposta.anomalie.append(
            "inserita dall'amministratore con i propri dati: referente da inserire dopo l'import"
        )
    elif principale.creata_da_amministratore:
        proposta.anomalie.append("inserita dall'amministratore: verificare il referente")
    if any(_PROVA.search(r.gruppo) for r in righe):
        proposta.azione = "SCARTA"
        proposta.anomalie.append("sembra una riga di prova")
    if any(re.search(r"esclusiv", f"{r.gruppo} {r.note}", re.I) for r in righe):
        proposta.esclusiva = "RICHIESTA"
        proposta.anomalie.append("il testo chiede l'uso esclusivo: decidere")
    if len({r.approvata for r in righe}) > 1:
        proposta.anomalie.append("stati diversi nei due calendari")
    for riga in righe:
        persone, anomalia = _numero(riga.partecipanti)
        if anomalia and not riservata:
            proposta.anomalie.append(f"{riga.calendario}: {anomalia}")
        if riga.calendario == "acc":
            proposta.persone_acc = persone
        else:
            proposta.persone_tende = persone
    if principale.notti == 0:
        proposta.uscita = AttivitaGiornaliera.Tipo.USCITA_CUCINA
        proposta.anomalie.append("in giornata: uscita con uso cucina (o area verde)")
    elif principale.pacchetto.lower() == "giornata":
        proposta.anomalie.append(f"pacchetto «Giornata» ma {principale.notti} notti: soggiorno")
    if categoria == "altro":
        proposta.anomalie.append("categoria non riconosciuta dal testo")
    return proposta


def _oggi() -> datetime.date:
    return timezone.localdate()


def proposte(
    acc: Path,
    tende: Path,
    *,
    oggi: datetime.date | None = None,
    amministratori: Iterable[str] = (),
) -> list[Proposta]:
    """Una proposta per riga; le righe con le stesse date nei due calendari diventano una
    prenotazione congiunta proposta (da confermare). `amministratori`: nomi o email con cui
    l'amministratore ha inserito righe per conto dei gruppi (proposte senza referente)."""
    oggi = oggi or _oggi()
    admin = {" ".join(a.split()).lower() for a in amministratori if a.strip()}
    righe_acc, righe_tende = leggi(acc, "acc"), leggi(tende, "tende")
    per_date: dict[tuple[datetime.date, datetime.date], list[Riga]] = {}
    for riga in righe_tende:
        per_date.setdefault((riga.arrivo, riga.partenza), []).append(riga)
    risultato = []
    usate: set[str] = set()
    for riga in righe_acc:
        compagne = [
            t
            for t in per_date.get((riga.arrivo, riga.partenza), [])
            if t.notti >= 1 and t.chiave not in usate and not _PROVA.search(t.gruppo)
        ]
        if len(compagne) == 1 and riga.notti >= 1 and not _PROVA.search(riga.gruppo):
            usate.add(compagne[0].chiave)
            risultato.append(_proposta([riga, compagne[0]], oggi, admin))
        else:
            risultato.append(_proposta([riga], oggi, admin))
    risultato += [_proposta([t], oggi, admin) for t in righe_tende if t.chiave not in usate]
    return sorted(risultato, key=lambda p: (p.principale.arrivo, p.chiave))


# --- File di revisione ------------------------------------------------------------------

COLONNE = [
    # (intestazione, modificabile)
    ("Chiave", False),
    ("Azione (IMPORTA/SCARTA)", True),
    ("Categoria (codice)", True),
    ("Stato", True),
    ("Unione (SI/NO)", True),
    ("Esclusiva (NO/RICHIESTA/CONCESSA)", True),
    ("Persone accantonamento", True),
    ("Persone tende", True),
    ("Uscita in giornata (tipo)", True),
    ("Referente (SI/NO)", True),
    ("Arrivo", False),
    ("Partenza", False),
    ("Notti", False),
    ("Gruppo", False),
    ("Referente", False),
    ("Email", False),
    ("Telefono", False),
    ("Partecipanti (originale)", False),
    ("Approvata in SuperSaaS", False),
    ("Note", False),
    ("Anomalie", False),
]


def scrivi_revisione(elenco: list[Proposta], percorso: Path) -> None:
    libro = Workbook()
    foglio = libro.active
    assert foglio is not None
    foglio.title = "Proposte"
    foglio.append([c for c, _ in COLONNE])
    giallo = PatternFill("solid", fgColor="FFF3CD")
    for colonna, (_, modificabile) in enumerate(COLONNE, start=1):
        cella = foglio.cell(row=1, column=colonna)
        cella.font = Font(bold=True)
        if modificabile:
            cella.fill = giallo
    for p in elenco:
        r = p.principale
        foglio.append(
            [
                p.chiave,
                p.azione,
                p.categoria,
                p.stato,
                "SI" if p.unione else "NO",
                p.esclusiva,
                p.persone_acc,
                p.persone_tende,
                p.uscita,
                "SI" if p.referente else "NO",
                r.arrivo,
                r.partenza,
                r.notti,
                " | ".join(x.gruppo for x in p.righe),
                " | ".join(x.nome for x in p.righe),
                " | ".join(x.email for x in p.righe),
                " | ".join(x.telefono for x in p.righe),
                " | ".join(x.partecipanti for x in p.righe),
                " | ".join("sì" if x.approvata else "no" for x in p.righe),
                " | ".join(x.note for x in p.righe if x.note),
                "; ".join(p.anomalie),
            ]
        )
    for riga in foglio.iter_rows(min_row=2, min_col=10, max_col=11):
        for cella in riga:
            cella.number_format = "DD/MM/YYYY"
    istruzioni = libro.create_sheet("Istruzioni")
    for testo in (
        "Correggi solo le colonne con l'intestazione gialla, poi lancia l'import con --apply --decisioni.",
        "Azione: IMPORTA o SCARTA. Ogni riga dei CSV deve comparire qui (nessuna riga si perde).",
        "Categoria: " + ", ".join(Categoria.objects.values_list("codice", flat=True)),
        "Stato: " + ", ".join(STATI_IMPORT),
        "Unione: SI per una prenotazione congiunta accantonamento + tende, NO per due prenotazioni.",
        "Esclusiva: NO, RICHIESTA o CONCESSA (solo con il solo accantonamento).",
        "Persone: obbligatorie per i soggiorni nelle aree della prenotazione.",
        "Uscita in giornata: " + ", ".join(USCITE) + " (solo per le prenotazioni senza notti).",
        "Referente: SI crea il referente con nome, email e telefono della riga (le prenotazioni si "
        "collegano all'account con quella email); NO se la riga ha i dati dell'amministratore.",
        "Il file contiene dati personali: tienilo fuori dal repo e cancellalo dopo l'import.",
    ):
        istruzioni.append([testo])
    libro.save(percorso)


def leggi_decisioni(percorso: Path) -> dict[str, dict[str, Any]]:
    foglio = load_workbook(percorso, data_only=True)["Proposte"]
    intestazioni = [c.value for c in next(foglio.iter_rows(max_row=1))]
    decisioni = {}
    for valori in foglio.iter_rows(min_row=2, values_only=True):
        dati = dict(zip(intestazioni, valori, strict=False))
        if dati.get("Chiave"):
            decisioni[str(dati["Chiave"]).strip()] = dati
    return decisioni


# --- Applicazione delle decisioni -------------------------------------------------------


def _intero(valore: Any) -> int | None:
    if valore in (None, ""):
        return None
    try:
        return int(valore)
    except TypeError, ValueError:
        raise ValueError(valore) from None


def _con_decisioni(elenco: list[Proposta], decisioni: dict[str, dict[str, Any]]) -> list[Proposta]:
    """Applica le decisioni alle proposte; raccoglie tutti gli errori prima di fermarsi."""
    errori = []
    chiavi = {p.chiave for p in elenco}
    for estranea in sorted(set(decisioni) - chiavi):
        errori.append(f"{estranea}: nel file di revisione ma non nei CSV")
    categorie = set(Categoria.objects.values_list("codice", flat=True))
    risultato = []
    for p in elenco:
        d = decisioni.get(p.chiave)
        if d is None:
            errori.append(f"{p.chiave}: manca la decisione nel file di revisione")
            continue
        azione = str(d.get("Azione (IMPORTA/SCARTA)") or "").strip().upper()
        if azione not in ("IMPORTA", "SCARTA"):
            errori.append(f"{p.chiave}: azione «{azione}» non valida")
            continue
        p.azione = azione
        if azione == "SCARTA":
            risultato.append(p)
            continue
        p.categoria = str(d.get("Categoria (codice)") or "").strip()
        p.stato = str(d.get("Stato") or "").strip().upper()
        p.unione = str(d.get("Unione (SI/NO)") or "").strip().upper() == "SI"
        p.esclusiva = str(d.get("Esclusiva (NO/RICHIESTA/CONCESSA)") or "NO").strip().upper()
        p.uscita = str(d.get("Uscita in giornata (tipo)") or "").strip().upper()
        referente = str(d.get("Referente (SI/NO)") or "").strip().upper()
        if referente not in ("SI", "NO"):
            errori.append(f"{p.chiave}: referente «{referente}» non valido (SI o NO)")
        p.referente = referente == "SI"
        try:
            p.persone_acc = _intero(d.get("Persone accantonamento"))
            p.persone_tende = _intero(d.get("Persone tende"))
        except ValueError as valore:
            errori.append(f"{p.chiave}: persone non numeriche «{valore}»")
            continue
        if p.categoria not in categorie:
            errori.append(f"{p.chiave}: categoria «{p.categoria}» inesistente")
        if p.stato not in STATI_IMPORT:
            errori.append(f"{p.chiave}: stato «{p.stato}» non valido")
        if p.esclusiva not in ESCLUSIVA:
            errori.append(f"{p.chiave}: esclusiva «{p.esclusiva}» non valida")
        if p.principale.notti == 0:
            if p.uscita not in USCITE:
                errori.append(f"{p.chiave}: indica il tipo di uscita in giornata")
            persone = p.persone_acc or p.persone_tende
            if persone is None:
                errori.append(f"{p.chiave}: indica le persone dell'uscita")
        else:
            for riga in p.righe if p.unione else p.righe[:1]:
                persone = p.persone_acc if riga.calendario == "acc" else p.persone_tende
                if persone is None:
                    errori.append(f"{p.chiave}: indica le persone in {riga.calendario}")
        risultato.append(p)
    if errori:
        raise ErroreImport("Il file di revisione va corretto:\n- " + "\n- ".join(errori))
    return risultato


def _scomponi(p: Proposta) -> list[Proposta]:
    """Una coppia con unione NO diventa due prenotazioni."""
    if len(p.righe) == 1 or p.unione:
        return [p]
    acc, tende = p.righe
    return [
        Proposta(**{**p.__dict__, "righe": [acc], "persone_tende": None, "unione": False}),
        Proposta(
            **{
                **p.__dict__,
                "righe": [tende],
                "persone_acc": None,
                "unione": False,
                "esclusiva": "NO",
            }
        ),
    ]


@dataclass
class Esito:
    importate: list[Prenotazione] = field(default_factory=list)
    scartate: list[str] = field(default_factory=list)


def applica(elenco: list[Proposta], decisioni: dict[str, dict[str, Any]]) -> Esito:
    """Importa in un'unica transazione: o tutto o niente."""
    esito = Esito()
    decise = _con_decisioni(elenco, decisioni)
    aree = {a.codice: a for a in Area.objects.all()}
    categorie = {c.codice: c for c in Categoria.objects.all()}
    with transaction.atomic():
        for proposta in decise:
            if proposta.azione == "SCARTA":
                esito.scartate.append(proposta.chiave)
                continue
            for parte in _scomponi(proposta):
                try:
                    esito.importate.append(_importa(parte, aree, categorie))
                except DateOccupate as errore:
                    raise ErroreImport(
                        f"{parte.chiave}: date occupate da un'altra prenotazione o da un blocco "
                        f"({parte.principale.arrivo:%d/%m/%Y}–{parte.principale.partenza:%d/%m/%Y})."
                    ) from errore
                except ValidationError as errore:
                    raise ErroreImport(f"{parte.chiave}: {'; '.join(errore.messages)}") from errore
    return esito


def _importa(p: Proposta, aree: dict[str, Area], categorie: dict[str, Categoria]) -> Prenotazione:
    r = p.principale
    categoria = categorie[p.categoria]
    contatto = None
    if p.referente and not p.prioritaria_senza_contatti and (r.nome or r.email or r.telefono):
        contatto = Contatto.objects.create(
            nome=r.nome or r.email or "Referente",
            email=r.email,
            telefono=r.telefono,
            organizzazione=r.gruppo,
        )
    note = "\n".join(
        x
        for x in [
            NOTA_IMPORT,
            *(f"{q.calendario}: {q.note}" for q in p.righe if q.note),
            *(
                f"partecipanti nell'export: {q.partecipanti}"
                for q in p.righe
                if q.partecipanti and not q.partecipanti.isdigit()
            ),
        ]
        if x
    )
    prenotazione = Prenotazione.objects.create(
        numero=assegna_numero(r.creata_il.year),
        categoria=categoria,
        contatto=contatto,
        gruppo=r.gruppo,
        unita=sorted({u for q in p.righe for u in q.unita}),
        data_richiesta=r.creata_il,
        arrivo=r.arrivo,
        partenza=r.partenza,
        stato=Stato.RICHIESTA,
        esclusiva_richiesta=p.esclusiva in ("RICHIESTA", "CONCESSA"),
        esclusiva_concessa=p.esclusiva == "CONCESSA",
        categoria_prioritaria_richiesta=categoria.prioritaria,
        categoria_prioritaria_concessa=categoria.prioritaria and p.prioritaria_senza_contatti,
        note=note,
        id_supersaas=p.chiave,
    )
    if r.notti == 0:
        AttivitaGiornaliera.objects.create(
            prenotazione=prenotazione,
            data=r.arrivo,
            tipo=p.uscita,
            persone_previste=p.persone_acc if p.persone_acc is not None else p.persone_tende or 0,
        )
    else:
        for riga in p.righe:
            codice = Area.ACCANTONAMENTO if riga.calendario == "acc" else Area.TENDE
            persone = p.persone_acc if riga.calendario == "acc" else p.persone_tende
            PresenzaArea.objects.create(
                prenotazione=prenotazione, area=aree[codice], persone_previste=persone or 0
            )
    # Preventivo con il listino della data della richiesta, prima di passare allo stato finale
    contributo.aggiorna_preventivo(prenotazione)
    prenotazione.stato = p.stato
    prenotazione.save(update_fields=["stato"])
    sincronizza_occupazioni(prenotazione)
    registra_evento(
        prenotazione,
        "importata da SuperSaaS",
        dopo={"id_supersaas": p.chiave, "stato": p.stato, "anomalie": p.anomalie},
    )
    if prenotazione.categoria_prioritaria_concessa:
        registra_decisione(
            prenotazione,
            "categoria prioritaria assegnata",
            utente=None,
            deciso_da=DECISO_DA_IMPORT,
            motivazione="Date riservate nel calendario SuperSaaS.",
        )
    return prenotazione


# --- Collegamento agli account ----------------------------------------------------------


def collega_a_utente(utente: Any, email: str) -> int:
    """Prenotazioni importate senza account il cui referente ha l'email (verificata) dell'utente."""
    if not email:
        return 0
    return Prenotazione.objects.filter(
        richiedente__isnull=True,
        id_supersaas__isnull=False,
        contatto__email__iexact=email,
    ).update(richiedente=utente)
