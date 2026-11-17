import base64
import io

import pytest
from django.core.files.base import ContentFile
from PIL import Image
from wagtail.users.models import UserProfile

from tana.accounts.adapters import TanaSocialAccountAdapter
from tana.accounts.avatar import PictureSestante, allinea_avatar, estrai_picture
from tana.accounts.models import Ruolo, User
from tana.accounts.services import nomina
from tana.accounts.tests.test_ruoli_sso import richiesta, social_login

pytestmark = pytest.mark.usefixtures("dati_iniziali")  # permessi dell'editor dei ruoli


def data_uri(colore="red", formato="PNG", tipo="image/png"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), colore).save(buffer, formato)
    return f"data:{tipo};base64," + base64.b64encode(buffer.getvalue()).decode()


@pytest.fixture
def redazione():
    utente = User.objects.create_user("redazione@example.org")
    nomina(utente, Ruolo.REDAZIONE)
    return utente


def avatar(utente):
    return UserProfile.get_for_user(utente).avatar


def test_estrai_picture_toglie_il_data_uri():
    extra = {"userinfo": {"picture": data_uri()}, "id_token": {}}
    picture = estrai_picture(extra)
    assert picture.da_userinfo and picture.valore.startswith("data:image/png")
    assert "picture" not in extra["userinfo"]
    extra = {"userinfo": {"picture": "https://gravatar.com/x"}}
    assert estrai_picture(extra).valore == "https://gravatar.com/x"
    assert extra["userinfo"]["picture"] == "https://gravatar.com/x"
    assert not estrai_picture({"id_token": {"picture": "x"}}).da_userinfo


def test_immagine_salvata_e_riscritta_solo_se_cambia(redazione):
    allinea_avatar(redazione, PictureSestante(True, data_uri()))
    primo = avatar(redazione).name
    assert primo and redazione.avatar_sestante == primo
    allinea_avatar(redazione, PictureSestante(True, data_uri()))
    assert avatar(redazione).name == primo
    allinea_avatar(redazione, PictureSestante(True, data_uri("blue")))
    assert avatar(redazione).name not in ("", primo)


@pytest.mark.parametrize("valore", ["https://gravatar.com/x", None])
def test_immagine_tolta_se_su_sestante_non_c_e_piu(redazione, valore):
    allinea_avatar(redazione, PictureSestante(True, data_uri()))
    allinea_avatar(redazione, PictureSestante(True, valore))
    assert not avatar(redazione)


def test_senza_userinfo_non_cambia_niente(redazione):
    allinea_avatar(redazione, PictureSestante(True, data_uri()))
    allinea_avatar(redazione, PictureSestante(False, None))
    assert avatar(redazione)


def test_immagine_caricata_nell_editor_non_si_tocca(redazione):
    profilo = UserProfile.get_for_user(redazione)
    profilo.avatar.save("mia.png", ContentFile(base64.b64decode(data_uri().split(",")[1])))
    nome = profilo.avatar.name
    allinea_avatar(redazione, PictureSestante(True, data_uri("blue")))
    allinea_avatar(redazione, PictureSestante(True, None))
    assert avatar(redazione).name == nome


@pytest.mark.parametrize(
    "valore",
    [
        "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=",
        "data:image/png;base64,non-base64!",
        data_uri(formato="JPEG"),  # dichiarata PNG, contenuto JPEG
    ],
)
def test_immagini_non_valide_ignorate(redazione, valore):
    allinea_avatar(redazione, PictureSestante(True, valore))
    assert not avatar(redazione)


def test_solo_per_chi_entra_nell_editor():
    richiedente = User.objects.create_user("gruppo@example.org")
    allinea_avatar(richiedente, PictureSestante(True, data_uri()))
    assert not avatar(richiedente)


def test_login_sestante_salva_l_immagine(settings):
    from tana.accounts.tests.test_ruoli_sso import PROVIDER_SESTANTE

    settings.SOCIALACCOUNT_PROVIDERS = PROVIDER_SESTANTE
    sociallogin = social_login("nuovo@example.org", groups=["admin-multipiattaforma"])
    sociallogin.account.extra_data["userinfo"]["picture"] = data_uri()
    adapter = TanaSocialAccountAdapter()
    request = richiesta()
    adapter.pre_social_login(request, sociallogin)
    utente = adapter.save_user(request, sociallogin)
    assert avatar(utente)
    assert "picture" not in sociallogin.account.extra_data["userinfo"]
