import datetime
import io

import pytest
from django.core.management import call_command
from django.db import IntegrityError

from tana.base.models import Area
from tana.listini.models import (
    Attivita,
    Categoria,
    Listino,
    VersioneInUso,
    VersioneListino,
    VoceListino,
)
from tana.listini.services import versione_applicabile
from tana.prenotazioni.services import crea_prenotazione

pytestmark = pytest.mark.django_db

d = datetime.date


def test_listini_iniziali(dati_iniziali):
    assert set(Listino.objects.values_list("tipo", flat=True)) == {
        "ASSOCIATIVO",
        "EXTRA",
        "AGEVOLATO",
        "GRATUITO",
    }
    associativo = VersioneListino.objects.get(listino__tipo="ASSOCIATIVO")
    assert associativo.nome == "2022/2023"
    assert associativo.pubblicata_il == associativo.valida_dal == d(2022, 1, 1)
    importi = {
        (v.attivita, v.area.codice if v.area else None, v.stagione): v.importo_centesimi
        for v in associativo.voci.select_related("area")
    }
    # §5.3, in centesimi
    assert importi == {
        ("CAMPO", "ACC", "INVERNALE"): 1000,
        ("CAMPO", "ACC", "ESTIVA"): 800,
        ("CAMPO", "TENDE", "NESSUNA"): 500,
        ("BIVACCO", "ACC", "NESSUNA"): 1000,
        ("USCITA_CUCINA", None, "NESSUNA"): 300,
        ("USCITA_AREA_VERDE", None, "NESSUNA"): 100,
        ("GIORNATA_OSPITI", None, "NESSUNA"): 100,
    }
    pernotto = VoceListino.objects.get(versione__listino__tipo="EXTRA")
    assert (pernotto.importo_centesimi, pernotto.unita) == (1500, "PERSONA_NOTTE")
    assert not VoceListino.objects.filter(versione__listino__tipo="AGEVOLATO").exists()
    gratuite = VoceListino.objects.filter(versione__listino__tipo="GRATUITO")
    assert gratuite.count() == 7
    assert set(gratuite.values_list("importo_centesimi", flat=True)) == {0}


def test_categorie_iniziali(dati_iniziali):
    assert Categoria.objects.count() == 10
    prioritarie = set(Categoria.objects.filter(prioritaria=True).values_list("codice", flat=True))
    assert prioritarie == {"foca-regionale", "foca-nazionale", "eventi-regionali", "comune"}
    assert Categoria.objects.get(codice="foca-regionale").listino_default.tipo == "AGEVOLATO"
    assert Categoria.objects.get(codice="foca-nazionale").listino_default.tipo == "ASSOCIATIVO"
    assert Categoria.objects.get(codice="comune").listino_default.tipo == "GRATUITO"
    assert Categoria.objects.get(codice="gruppo-cngei").listino_default.tipo == "EXTRA"
    assert Categoria.objects.get(codice="altro").richiede_specifica


def test_dati_iniziali_idempotenti_e_non_sovrascrivono(dati_iniziali):
    Area.objects.filter(codice="ACC").update(capienza=100)
    VoceListino.objects.filter(versione__listino__tipo="ASSOCIATIVO").first().delete()
    voci = VoceListino.objects.count()
    call_command("dati_iniziali", stdout=io.StringIO())
    assert Area.objects.get(codice="ACC").capienza == 100
    assert VoceListino.objects.count() == voci


@pytest.fixture
def due_versioni(dati_iniziali):
    """Associativo: versione 2022/2023 e nuova versione pubblicata il 1/9/2027, valida dal 1/1/2028."""
    listino = Listino.objects.get(tipo="ASSOCIATIVO")
    vecchia = listino.versioni.get()
    nuova = VersioneListino.objects.create(
        listino=listino, nome="2028", pubblicata_il=d(2027, 9, 1), valida_dal=d(2028, 1, 1)
    )
    return listino, vecchia, nuova


@pytest.mark.parametrize(
    ("data_richiesta", "primo_giorno", "attesa"),
    [
        (d(2027, 9, 15), d(2027, 12, 10), "vecchia"),  # campo a dicembre
        (d(2027, 9, 15), d(2028, 2, 10), "nuova"),  # campo a febbraio
        (d(2027, 8, 15), d(2028, 2, 10), "vecchia"),  # nuova non ancora pubblicata
        (d(2027, 9, 1), d(2028, 1, 1), "nuova"),  # estremi inclusi
    ],
)
def test_versione_applicabile_esempi_d09(due_versioni, data_richiesta, primo_giorno, attesa):
    listino, vecchia, nuova = due_versioni
    versione = versione_applicabile(
        listino, data_richiesta=data_richiesta, primo_giorno=primo_giorno
    )
    assert versione == {"vecchia": vecchia, "nuova": nuova}[attesa]


def test_nessuna_versione_applicabile(due_versioni):
    listino, *_ = due_versioni
    assert (
        versione_applicabile(listino, data_richiesta=d(2021, 1, 1), primo_giorno=d(2021, 6, 1))
        is None
    )


def _usa(versione):
    return crea_prenotazione(
        categoria=Categoria.objects.get(codice="gruppo-agesci"),
        arrivo=d(2027, 7, 19),
        partenza=d(2027, 7, 24),
        versione_listino=versione,
    )


def test_versione_in_uso_immutabile(dati_iniziali):
    versione = VersioneListino.objects.get(listino__tipo="ASSOCIATIVO")
    versione.note = "modificabile finché non è usata"
    versione.save()
    _usa(versione)
    versione.note = "non più"
    with pytest.raises(VersioneInUso):
        versione.save()
    with pytest.raises(VersioneInUso):
        versione.delete()
    voce = versione.voci.first()
    voce.importo_centesimi = 1
    with pytest.raises(VersioneInUso):
        voce.save()
    with pytest.raises(VersioneInUso):
        voce.delete()
    with pytest.raises(VersioneInUso):
        VoceListino.objects.create(
            versione=versione,
            attivita=Attivita.BIVACCO,
            area=Area.objects.get(codice="TENDE"),
            unita=VoceListino.Unita.PERSONA_NOTTE,
            importo_centesimi=500,
        )
    assert VoceListino.objects.get(pk=voce.pk).importo_centesimi != 1


def test_voce_non_si_sposta_da_una_versione_in_uso(due_versioni):
    _, vecchia, nuova = due_versioni
    _usa(vecchia)
    voce = vecchia.voci.first()
    voce.versione = nuova
    with pytest.raises(VersioneInUso):
        voce.save()


def test_voce_unica_anche_senza_area(dati_iniziali):
    versione = VersioneListino.objects.get(listino__tipo="ASSOCIATIVO")
    with pytest.raises(IntegrityError):
        VoceListino.objects.create(
            versione=versione,
            attivita=Attivita.USCITA_CUCINA,
            unita=VoceListino.Unita.PERSONA_GIORNO,
            importo_centesimi=400,
        )
