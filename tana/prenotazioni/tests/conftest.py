import pytest

from tana.accounts.models import Ruolo, User
from tana.base.models import Configurazione
from tana.prenotazioni.models import Contatto

from .utils import tra, utente_con


@pytest.fixture
def dati(dati_iniziali):
    """Dati iniziali con orizzonte ampio (i test usano date relative a oggi) e IBAN."""
    Configurazione.objects.filter(pk=1).update(orizzonte_massimo=tra(400), iban="IT00X0000")


@pytest.fixture
def email(django_capture_on_commit_callbacks, mailoutbox):
    """Esegue le callback on_commit (le email partono a transazione confermata)."""

    class Posta:
        def __init__(self):
            self.cattura = django_capture_on_commit_callbacks

        def __call__(self, funzione, *args, **kwargs):
            with self.cattura(execute=True):
                return funzione(*args, **kwargs)

        @property
        def inviate(self):
            return mailoutbox

    return Posta()


@pytest.fixture
def richiedente():
    return User.objects.create_user("referente@example.org")


@pytest.fixture
def admin():
    return utente_con(Ruolo.AMMINISTRATORE, "admin@example.org")


@pytest.fixture
def pattuglia():
    return utente_con(Ruolo.PATTUGLIA, "pattuglia@example.org")


@pytest.fixture
def contatto():
    return Contatto.objects.create(
        nome="Mario Rossi", email="mario@example.org", telefono="3331234567"
    )
