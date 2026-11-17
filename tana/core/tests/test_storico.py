import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from tana.base.models import Area
from tana.core.services import registra_decisione, registra_evento, storico
from tana.core.storage import StoragePrivato

pytestmark = pytest.mark.django_db


@pytest.fixture
def area(db):
    return Area.objects.create(codice="ACC", nome="Accantonamento", capienza=109)


def test_storico_dell_oggetto(area, django_user_model):
    utente = django_user_model.objects.create_user("pattuglia@example.org")
    registra_evento(area, "creata", utente=utente, dopo={"capienza": 109})
    registra_evento(
        area, "modificata", utente=utente, prima={"capienza": 109}, dopo={"capienza": 100}
    )
    eventi = list(storico(area))
    assert [e.azione for e in eventi] == ["modificata", "creata"]
    assert eventi[0].oggetto == area
    assert eventi[0].dati_dopo == {"capienza": 100}


@pytest.mark.parametrize(("deciso_da", "motivazione"), [("", "perché sì"), ("Pattuglia", " ")])
def test_decisione_senza_deciso_da_o_motivazione(area, deciso_da, motivazione):
    with pytest.raises(ValidationError):
        registra_decisione(
            area, "esclusiva concessa", utente=None, deciso_da=deciso_da, motivazione=motivazione
        )
    assert not storico(area).exists()


def test_decisione_registrata(area):
    evento = registra_decisione(
        area,
        "esclusiva concessa",
        utente=None,
        deciso_da="Pattuglia e IRO",
        motivazione="Campo di Formazione",
    )
    assert (evento.deciso_da, evento.motivazione) == ("Pattuglia e IRO", "Campo di Formazione")


def test_file_privati_senza_url(tmp_path):
    storage = StoragePrivato(location=tmp_path)
    nome = storage.save("ricevute/2026-001/bonifico.pdf", ContentFile(b"%PDF"))
    assert (tmp_path / nome).exists()
    with pytest.raises(NotImplementedError):
        storage.url(nome)
