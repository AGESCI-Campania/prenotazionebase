import pytest
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.django_db


def test_utente_si_identifica_con_email():
    User = get_user_model()
    utente = User.objects.create_user("Referente@Example.org", "password-lunga-1")
    assert utente.email == "Referente@example.org"
    assert utente.check_password("password-lunga-1")
    assert not utente.is_staff


def test_superutente():
    admin = get_user_model().objects.create_superuser("admin@example.org", "password-lunga-1")
    assert admin.is_staff and admin.is_superuser


def test_email_obbligatoria():
    with pytest.raises(ValueError):
        get_user_model().objects.create_user("", "x")
