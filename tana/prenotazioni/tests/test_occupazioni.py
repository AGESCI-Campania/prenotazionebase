import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.backends.postgresql.psycopg_any import DateRange
from django.utils import timezone

from tana.base.models import Area
from tana.listini.models import Categoria
from tana.prenotazioni.models import (
    AttivitaGiornaliera,
    BloccoTecnico,
    Occupazione,
    PresenzaArea,
    RichiestaConsenso,
    RigaImporto,
    Stato,
)
from tana.prenotazioni.services import (
    DateOccupate,
    assegna_numero,
    crea_blocco,
    crea_prenotazione,
    sincronizza_occupazioni,
)

pytestmark = pytest.mark.django_db

d = datetime.date


@pytest.fixture
def aree(dati_iniziali):
    return Area.objects.get(codice="ACC"), Area.objects.get(codice="TENDE")


def prenota(arrivo, partenza, *, acc=0, tende=0, **campi):
    """Prenotazione con le presenze indicate e le sue occupazioni."""
    prenotazione = crea_prenotazione(
        categoria=Categoria.objects.get(codice="gruppo-agesci"),
        arrivo=arrivo,
        partenza=partenza,
        **campi,
    )
    for codice, persone in (("ACC", acc), ("TENDE", tende)):
        if persone:
            PresenzaArea.objects.create(
                prenotazione=prenotazione,
                area=Area.objects.get(codice=codice),
                persone_previste=persone,
            )
    sincronizza_occupazioni(prenotazione)
    return prenotazione


def test_numeri_progressivi_per_anno(db):
    assert assegna_numero(2026) == "2026-001"
    assert assegna_numero(2026) == "2026-002"
    assert assegna_numero(2027) == "2027-001"
    assert assegna_numero(2026) == "2026-003"


def test_numero_con_anno_di_creazione(aree):
    prenotazione = prenota(d(2028, 7, 1), d(2028, 7, 5), acc=10)
    assert prenotazione.numero.startswith(f"{timezone.localdate().year}-")


def test_occupazione_semiaperta(aree):
    acc, _ = aree
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28)
    occupazione = prenotazione.occupazioni.get()
    assert occupazione.area == acc
    assert occupazione.periodo == DateRange(d(2027, 7, 19), d(2027, 7, 24), "[)")
    assert occupazione.attiva


def test_sovrapposizione_rifiutata(aree):
    prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28)
    with pytest.raises(DateOccupate):
        prenota(d(2027, 7, 23), d(2027, 7, 26), acc=10)
    assert Occupazione.objects.count() == 1


def test_vincolo_nel_database_anche_senza_servizi(aree):
    acc, _ = aree
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28)
    altra = crea_prenotazione(
        categoria=prenotazione.categoria, arrivo=d(2027, 7, 20), partenza=d(2027, 7, 21)
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Occupazione.objects.create(
            tipo=Occupazione.Tipo.PRENOTAZIONE,
            area=acc,
            periodo=DateRange(d(2027, 7, 20), d(2027, 7, 21), "[)"),
            prenotazione=altra,
        )


def test_giorno_di_cambio_libero(aree):
    prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28)
    entrante = prenota(d(2027, 7, 24), d(2027, 7, 30), acc=20)
    assert entrante.occupazioni.get().attiva


def test_aree_diverse_nello_stesso_periodo(aree):
    prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28)
    prenota(d(2027, 7, 19), d(2027, 7, 24), tende=12)
    assert Occupazione.objects.filter(attiva=True).count() == 2


def test_prenotazione_congiunta_occupa_due_aree(aree):
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=20, tende=12)
    assert prenotazione.occupazioni.count() == 2
    with pytest.raises(DateOccupate):
        prenota(d(2027, 7, 20), d(2027, 7, 22), tende=6)


@pytest.mark.parametrize(
    "stato", [Stato.RIFIUTATA, Stato.SCADUTA, Stato.ANNULLATA, Stato.NON_SVOLTA]
)
def test_stati_che_liberano_le_date(aree, stato):
    prima = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28)
    prima.stato = stato
    prima.save()
    sincronizza_occupazioni(prima)
    assert not prima.occupazioni.get().attiva
    prenota(d(2027, 7, 19), d(2027, 7, 24), acc=10)
    # Riattivarla ora non è possibile: le date sono di un altro gruppo
    prima.stato = Stato.RICHIESTA
    prima.save()
    with pytest.raises(DateOccupate):
        sincronizza_occupazioni(prima)
    assert not prima.occupazioni.get().attiva


def test_richiesta_in_attesa_occupa_le_date(aree):
    prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28, stato=Stato.RICHIESTA)
    with pytest.raises(DateOccupate):
        prenota(d(2027, 7, 19), d(2027, 7, 24), acc=10)


def test_cambio_date_e_presenze(aree):
    _, tende = aree
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=20, tende=12)
    prenotazione.presenze.filter(area=tende).delete()
    prenotazione.partenza = d(2027, 7, 26)
    prenotazione.save()
    sincronizza_occupazioni(prenotazione)
    occupazione = prenotazione.occupazioni.get()
    assert occupazione.periodo.upper == d(2027, 7, 26)
    prenota(d(2027, 7, 19), d(2027, 7, 24), tende=6)


def test_esclusiva_occupa_l_area_tende(aree):
    _, tende = aree
    prenotazione = prenota(
        d(2027, 7, 19), d(2027, 7, 24), acc=28, esclusiva_richiesta=True, esclusiva_concessa=True
    )
    esclusiva = prenotazione.occupazioni.get(area=tende)
    assert esclusiva.tipo == Occupazione.Tipo.ESCLUSIVA
    with pytest.raises(DateOccupate):
        prenota(d(2027, 7, 20), d(2027, 7, 21), tende=6)


def test_esclusiva_solo_con_il_solo_accantonamento(aree):
    with pytest.raises(ValidationError):
        prenota(d(2027, 7, 19), d(2027, 7, 24), acc=20, tende=12, esclusiva_concessa=True)


def test_esclusiva_non_concessa_lascia_libere_le_tende(aree):
    prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28, esclusiva_richiesta=True)
    prenota(d(2027, 7, 19), d(2027, 7, 24), tende=6)


def test_attivita_in_giornata_non_occupa_aree(aree):
    prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28)
    uscita = prenota(d(2027, 7, 20), d(2027, 7, 20))
    AttivitaGiornaliera.objects.create(
        prenotazione=uscita,
        data=d(2027, 7, 20),
        tipo=AttivitaGiornaliera.Tipo.USCITA_CUCINA,
        persone_previste=30,
    )
    sincronizza_occupazioni(uscita)
    assert not uscita.occupazioni.exists()


def test_partenza_prima_dell_arrivo_rifiutata(aree):
    with pytest.raises(IntegrityError):
        prenota(d(2027, 7, 24), d(2027, 7, 19))


def test_blocco_tecnico_estremi_inclusi(aree):
    acc, _ = aree
    blocco = crea_blocco(area=acc, dal=d(2027, 3, 3), al=d(2027, 3, 5), motivo="Impianto elettrico")
    assert blocco.occupazioni.get().periodo == DateRange(d(2027, 3, 3), d(2027, 3, 6), "[)")
    with pytest.raises(DateOccupate):
        prenota(d(2027, 3, 5), d(2027, 3, 7), acc=10)
    prenota(d(2027, 3, 6), d(2027, 3, 8), acc=10)
    prenota(d(2027, 3, 1), d(2027, 3, 3), acc=10)


def test_blocco_su_date_prenotate_rifiutato(aree):
    acc, _ = aree
    prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28)
    with pytest.raises(DateOccupate):
        crea_blocco(area=acc, dal=d(2027, 7, 23), al=d(2027, 7, 23), motivo="Potatura")
    assert not acc.occupazioni.filter(tipo=Occupazione.Tipo.BLOCCO).exists()
    assert not BloccoTecnico.objects.exists()


def test_rettifica_richiede_decisione(aree):
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28)
    with pytest.raises(IntegrityError), transaction.atomic():
        RigaImporto.objects.create(
            prenotazione=prenotazione,
            fase=RigaImporto.Fase.PREVENTIVO,
            descrizione="Sconto",
            prezzo_centesimi=-10000,
            importo_centesimi=-10000,
            rettifica=True,
        )
    RigaImporto.objects.create(
        prenotazione=prenotazione,
        fase=RigaImporto.Fase.PREVENTIVO,
        descrizione="Sconto",
        prezzo_centesimi=-10000,
        importo_centesimi=-10000,
        rettifica=True,
        deciso_da="Pattuglia",
        motivazione="Gruppo in difficoltà",
    )


def test_consenso_non_a_se_stessa(aree):
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28)
    with pytest.raises(IntegrityError):
        RichiestaConsenso.objects.create(
            richiesta=prenotazione,
            prenotazione_esistente=prenotazione,
            scadenza=datetime.datetime(2027, 7, 1, tzinfo=datetime.UTC),
        )
