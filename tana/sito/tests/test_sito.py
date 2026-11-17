import pytest
from django.test import Client
from wagtail.blocks import StructBlockValidationError
from wagtail.models import Page

from tana.accounts.models import Ruolo, User
from tana.accounts.services import nomina
from tana.core.pdf import PdfNonDisponibile
from tana.prenotazioni import flusso
from tana.prenotazioni.tests.utils import richiesta
from tana.sito import regolamento
from tana.sito.blocchi import MappaBlock, PulsanteBlock
from tana.sito.models import HomePage, PaginaRegolamento

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _dati(dati, sito):
    pass


def test_albero_e_indirizzi_del_google_site(client):
    home = HomePage.objects.get()
    assert home.url == "/" and not Page.objects.filter(title__startswith="Welcome").exists()
    for indirizzo in (
        "/",
        "/la-storia/",
        "/gianni-sabatino/",
        "/le-strutture/",
        "/info/",
        "/info/emergenze/",
    ):
        assert client.get(indirizzo).status_code == 200, indirizzo
    # Regolamento in bozza finché la redazione non lo pubblica
    assert client.get("/info/regolamento/").status_code == 404
    assert PaginaRegolamento.objects.get().corpo  # testo iniziale dal PDF di Drive
    # Vecchi indirizzi del Google Site
    assert client.get("/home").url == "/"
    assert client.get("/info/listino-prezzi").url == "/listino/"


def test_home_e_menu(client):
    html = client.get("/").content.decode()
    assert "Base Scout «Gianni Sabatino»" in html and "Disponibilità dei prossimi giorni" in html
    assert 'href="/la-storia/"' in html and 'href="/info/emergenze/"' in html
    assert "basegiannisabatino" in html  # social dalle impostazioni del sito
    assert 'data-bs-toggle="menu"' in html


def test_strutture_scelte_nella_pagina(client):
    from wagtail.images.models import Image
    from wagtail.images.tests.utils import get_test_image_file

    from tana.base.models import ImmagineStruttura, Struttura
    from tana.sito.models import PaginaStrutture

    html = client.get("/le-strutture/").content.decode()
    assert "Arena con altare" in html and "140 m²" in html and "In comune" in html
    # Una struttura nuova compare solo se la si sceglie nella pagina (D-12)
    roccia = Struttura.objects.create(
        nome="Palestra di roccia", uso=Struttura.Uso.CONDIVISA, descrizione="Per l'arrampicata."
    )
    assert "Palestra di roccia" not in client.get("/le-strutture/").content.decode()
    foto = Image.objects.create(title="Parete", file=get_test_image_file())
    ImmagineStruttura.objects.create(struttura=roccia, immagine=foto, didascalia="La parete est")
    pagina = PaginaStrutture.objects.get()
    pagina.strutture.add(roccia)
    pagina.strutture.remove(Struttura.objects.get(nome="Sala laboratorio"))
    pagina.save_revision().publish()
    html = client.get("/le-strutture/").content.decode()
    assert "Palestra di roccia" in html and "Per l&#x27;arrampicata." in html
    assert "La parete est" in html and "<img" in html
    assert "Sala laboratorio" not in html


def test_strutture_nell_editor_solo_per_l_amministrazione():
    amministratore = User.objects.create_user("amministratore@example.org")
    nomina(amministratore, Ruolo.AMMINISTRATORE)
    c = Client()
    c.force_login(amministratore)
    assert c.get("/cms/snippets/base/struttura/").status_code == 200
    assert c.get("/cms/snippets/base/struttura/add/").status_code == 200
    redazione = User.objects.create_user("redazione@example.org")
    nomina(redazione, Ruolo.REDAZIONE)
    c.force_login(redazione)
    assert c.get("/cms/snippets/base/struttura/").status_code in (302, 403)


def test_logo_della_base_nell_editor():
    redazione = User.objects.create_user("redazione@example.org")
    nomina(redazione, Ruolo.REDAZIONE)
    c = Client()
    c.force_login(redazione)
    html = c.get("/cms/").content.decode()
    assert (
        "tana/img/logo/lupo-base-aiello"
        in html.split("data-wagtail-sidebar-branding-logo")[1][:300]
    )
    # La redazione non entra nella gestione: niente voce di ritorno
    assert "Gestione prenotazioni" not in html
    amministratore = User.objects.create_user("amministratore@example.org")
    nomina(amministratore, Ruolo.AMMINISTRATORE)
    c.force_login(amministratore)
    assert "Gestione prenotazioni" in c.get("/cms/").content.decode()


def test_pagina_riservata(client, richiedente, contatto, admin):
    url = "/info/per-chi-e-in-base/"
    assert client.get(url).status_code == 403
    c = Client()
    c.force_login(richiedente)
    assert c.get(url).status_code == 403
    p = richiesta(richiedente, contatto, arrivo=10, partenza=12)
    flusso.approva(p, utente=admin)
    flusso.conferma_senza_acconto(p, utente=admin)
    assert c.get(url).status_code == 200
    redazione = User.objects.create_user("redazione@example.org")
    nomina(redazione, Ruolo.REDAZIONE)
    c.force_login(redazione)
    assert c.get(url).status_code == 200


def test_blocchi_validati():
    with pytest.raises(StructBlockValidationError):
        MappaBlock().clean({"indirizzo": "https://example.org/mappa", "titolo": ""})
    MappaBlock().clean(
        {"indirizzo": "https://www.openstreetmap.org/export/embed.html?bbox=1", "titolo": ""}
    )
    with pytest.raises(StructBlockValidationError):
        PulsanteBlock().clean({"etichetta": "Vai", "pagina": None, "indirizzo": ""})


def test_redazione_entra_nell_editor():
    utente = User.objects.create_user("redazione@example.org")
    nomina(utente, Ruolo.REDAZIONE)
    c = Client()
    c.force_login(utente)
    assert c.get("/cms/").status_code == 200
    home = HomePage.objects.get()
    assert c.get(f"/cms/pages/{home.pk}/edit/").status_code == 200
    assert c.get("/gestione/").status_code == 403  # solo l'editor (P-15)
    nessuno = User.objects.create_user("nessuno@example.org")
    c.force_login(nessuno)
    risposta = c.get("/cms/", follow=True)  # niente ciclo login ↔ editor
    assert risposta.status_code == 200 and len(risposta.redirect_chain) == 1


def test_pdf_del_regolamento_alla_pubblicazione(monkeypatch):
    monkeypatch.setattr(regolamento, "genera", lambda template, contesto: b"%PDF-finto")
    pagina = PaginaRegolamento.objects.get()
    assert regolamento.pdf_in_vigore() is None
    pagina.save_revision().publish()
    pagina.refresh_from_db()
    assert pagina.pdf.collection.name == "Regolamento"
    assert regolamento.pdf_in_vigore() == ("regolamento-base-aiello.pdf", b"%PDF-finto")
    # Una nuova pubblicazione archivia una nuova versione
    primo = pagina.pdf
    pagina.save_revision().publish()
    pagina.refresh_from_db()
    assert pagina.pdf != primo


def test_pdf_non_disponibile_non_blocca_la_pubblicazione(monkeypatch):
    def guasto(template, contesto):
        raise PdfNonDisponibile("niente Pango")

    monkeypatch.setattr(regolamento, "genera", guasto)
    pagina = PaginaRegolamento.objects.get()
    pagina.save_revision().publish()
    pagina.refresh_from_db()
    assert pagina.live and pagina.pdf is None
