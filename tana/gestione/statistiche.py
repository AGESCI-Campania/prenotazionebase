"""Statistiche per anno solare (D-10, D-18): solo numeri aggregati, nessun dato personale.

Contano le prenotazioni confermate, svolte e chiuse (anche importate come svolte); i blocchi
tecnici sono fuori dalle statistiche (§3).
"""

import calendar
import datetime
from collections import defaultdict
from dataclasses import dataclass, field

from django.db.backends.postgresql.psycopg_any import DateRange
from django.db.models import Sum

from tana.base.models import Area
from tana.listini.models import Categoria
from tana.prenotazioni import contributo
from tana.prenotazioni.models import Occupazione, Pagamento, Prenotazione, Stato

STATI_CONTATI = (Stato.CONFERMATA, Stato.SVOLTA, Stato.CHIUSA)
CODICE_COMUNE = "comune"
GIORNI_COMODATO = 7  # settimana annua del comodato con il Comune (D-10)


@dataclass
class RigaCategoria:
    categoria: Categoria
    prenotazioni: int = 0
    presenze: dict[str, int] = field(default_factory=dict)  # area → persone × giorni
    ospiti: int = 0  # persone delle attività in giornata
    importi: int = 0  # consuntivo, o preventivo se non ancora compilato
    importi_da_definire: int = 0
    incassi: int = 0

    @property
    def presenze_totali(self) -> int:
        return sum(self.presenze.values())


@dataclass
class Statistiche:
    anno: int
    aree: list[Area]
    categorie: list[RigaCategoria]
    giorni_comune: int
    occupazione: dict[str, list[tuple[str, int, int]]]  # area → (mese, notti occupate, notti)
    # Per mese: (mese, presenze previste, presenze effettive registrate), persone × giorni
    presenze_mensili: list[tuple[str, int, int]] = field(default_factory=list)

    @property
    def totale(self) -> RigaCategoria:
        totale = RigaCategoria(categoria=Categoria(nome="Totale"))
        for riga in self.categorie:
            totale.prenotazioni += riga.prenotazioni
            for area, n in riga.presenze.items():
                totale.presenze[area] = totale.presenze.get(area, 0) + n
            totale.ospiti += riga.ospiti
            totale.importi += riga.importi
            totale.importi_da_definire += riga.importi_da_definire
            totale.incassi += riga.incassi
        return totale


def _giorni_nell_anno(arrivo: datetime.date, partenza: datetime.date, anno: int) -> int:
    """Giorni del soggiorno (arrivo e partenza inclusi) che cadono nell'anno."""
    inizio = max(arrivo, datetime.date(anno, 1, 1))
    fine = min(partenza, datetime.date(anno, 12, 31))
    return max((fine - inizio).days + 1, 0)


def _giorni_per_mese(arrivo: datetime.date, partenza: datetime.date, anno: int) -> dict[int, int]:
    """Giorni del soggiorno (arrivo e partenza inclusi) nell'anno, per mese."""
    giorni: dict[int, int] = defaultdict(int)
    giorno = max(arrivo, datetime.date(anno, 1, 1))
    while giorno <= min(partenza, datetime.date(anno, 12, 31)):
        giorni[giorno.month] += 1
        giorno += datetime.timedelta(days=1)
    return giorni


def calcola(anno: int) -> Statistiche:
    aree = list(Area.objects.all())
    righe = {c.pk: RigaCategoria(categoria=c) for c in Categoria.objects.all()}
    inizio, fine = datetime.date(anno, 1, 1), datetime.date(anno, 12, 31)
    prenotazioni = (
        Prenotazione.objects.filter(stato__in=STATI_CONTATI, arrivo__lte=fine, partenza__gte=inizio)
        .select_related("categoria")
        .prefetch_related("presenze__area", "attivita_giornaliere")
    )
    giorni_comune = 0
    previste, effettive = [0] * 12, [0] * 12
    for p in prenotazioni:
        for presenza in p.presenze.all():
            for mese, giorni_mese in _giorni_per_mese(p.arrivo, p.partenza, anno).items():
                previste[mese - 1] += presenza.persone_previste * giorni_mese
                if presenza.persone_effettive is not None:
                    effettive[mese - 1] += presenza.persone_effettive * giorni_mese
        riga = righe[p.categoria_id]
        giorni = _giorni_nell_anno(p.arrivo, p.partenza, anno)
        # Una prenotazione a cavallo d'anno si conta nell'anno dell'arrivo
        if p.arrivo.year == anno:
            riga.prenotazioni += 1
            consuntivo = contributo.riepilogo(p, contributo.Fase.CONSUNTIVO)
            fase = consuntivo if consuntivo.righe else contributo.riepilogo(p)
            if fase.totale is None:
                riga.importi_da_definire += 1
            else:
                riga.importi += fase.totale
        for presenza in p.presenze.all():
            persone = presenza.persone_effettive or presenza.persone_previste
            nome = presenza.area.nome
            riga.presenze[nome] = riga.presenze.get(nome, 0) + persone * giorni
        for att in p.attivita_giornaliere.all():
            if att.data.year == anno:
                riga.ospiti += att.persone_effettive or att.persone_previste
        if p.categoria.codice == CODICE_COMUNE:
            giorni_comune += giorni

    incassi = (
        Pagamento.objects.filter(stato=Pagamento.StatoPagamento.VERIFICATO, data__year=anno)
        .values("prenotazione__categoria")
        .annotate(totale=Sum("importo_centesimi"))
    )
    for voce in incassi:
        righe[voce["prenotazione__categoria"]].incassi = voce["totale"] or 0

    return Statistiche(
        anno=anno,
        aree=aree,
        categorie=[r for r in righe.values() if r.prenotazioni or r.presenze or r.incassi],
        giorni_comune=giorni_comune,
        occupazione=_occupazione(anno, aree),
        presenze_mensili=list(zip(MESI, previste, effettive, strict=True)),
    )


MESI = [
    "gen",
    "feb",
    "mar",
    "apr",
    "mag",
    "giu",
    "lug",
    "ago",
    "set",
    "ott",
    "nov",
    "dic",
]


def _occupazione(anno: int, aree: list[Area]) -> dict[str, list[tuple[str, int, int]]]:
    """Notti occupate da prenotazioni (non blocchi tecnici) per area e mese."""
    notti: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    inizio, fine = datetime.date(anno, 1, 1), datetime.date(anno + 1, 1, 1)
    occupazioni = Occupazione.objects.filter(
        attiva=True,
        tipo=Occupazione.Tipo.PRENOTAZIONE,
        periodo__overlap=DateRange(inizio, fine, "[)"),
    )
    for occupazione in occupazioni:
        giorno = max(occupazione.periodo.lower, inizio)
        while giorno < min(occupazione.periodo.upper, fine):
            notti[occupazione.area_id][giorno.month] += 1
            giorno += datetime.timedelta(days=1)
    return {
        area.nome: [
            (MESI[mese - 1], notti[area.pk][mese], calendar.monthrange(anno, mese)[1])
            for mese in range(1, 13)
        ]
        for area in aree
    }
