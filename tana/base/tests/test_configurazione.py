import datetime

import pytest
from django.core.exceptions import ValidationError

from tana.base.models import Configurazione

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("data", "inverno"),
    [
        (datetime.date(2026, 10, 31), False),
        (datetime.date(2026, 11, 1), True),
        (datetime.date(2026, 12, 31), True),
        (datetime.date(2027, 1, 1), True),
        (datetime.date(2027, 3, 15), True),
        (datetime.date(2027, 3, 16), False),
        (datetime.date(2027, 7, 19), False),
    ],
)
def test_stagione_invernale_a_cavallo_dell_anno(data, inverno):
    assert Configurazione.corrente().e_inverno(data) is inverno


def test_stagione_nello_stesso_anno():
    conf = Configurazione(
        inverno_dal_giorno=1, inverno_dal_mese=1, inverno_al_giorno=28, inverno_al_mese=2
    )
    assert conf.e_inverno(datetime.date(2027, 2, 1))
    assert not conf.e_inverno(datetime.date(2027, 3, 1))


def test_default_della_configurazione():
    conf = Configurazione.corrente()
    assert conf.pk == 1
    assert (conf.acconto_percentuale, conf.acconto_giorni, conf.soglia_esenzione_giorni) == (
        50,
        7,
        3,
    )
    assert conf.consenso_giorni == 7
    assert conf.orario_arrivo == datetime.time(15, 0)
    assert conf.orario_partenza == datetime.time(12, 0)
    assert conf.orizzonte_massimo == datetime.date(2027, 9, 30)
    assert conf.anni_conservazione == 10


def test_data_invernale_inesistente():
    conf = Configurazione(inverno_dal_giorno=31, inverno_dal_mese=11)
    with pytest.raises(ValidationError) as errore:
        conf.full_clean()
    assert "inverno_dal_giorno" in errore.value.message_dict
