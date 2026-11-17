"""Albero iniziale del sito (D-30, P-17), richiamato da `manage.py dati_iniziali`.

Idempotente: crea solo le pagine che mancano (per indirizzo) e non tocca quelle esistenti,
che dopo l'avvio cura la redazione.
"""

import json
from pathlib import Path
from typing import Any

from wagtail.contrib.redirects.models import Redirect
from wagtail.models import Page, Site

from tana.base.models import Struttura

from . import contenuti_iniziali as contenuti
from .models import HomePage, PaginaContenuto, PaginaRegolamento, PaginaRiservata, PaginaStrutture

TIPI: dict[str, type[PaginaContenuto]] = {
    "PaginaContenuto": PaginaContenuto,
    "PaginaStrutture": PaginaStrutture,
    "PaginaRegolamento": PaginaRegolamento,
    "PaginaRiservata": PaginaRiservata,
}
CARTELLA = Path(__file__).parent / "contenuti"
TITOLO_HOME = "Base Scout «Gianni Sabatino»"


def home() -> HomePage:
    """La home del sito: sostituisce la pagina di benvenuto di Wagtail alla prima esecuzione."""
    esistente = HomePage.objects.first()
    if esistente is not None:
        return esistente
    radice = Page.get_first_root_node()
    nuova = HomePage(
        title=TITOLO_HOME,
        slug="home-tana",
        presentazione=contenuti.PRESENTAZIONE_HOME,
        corpo=json.loads((CARTELLA / contenuti.CORPO_HOME).read_text(encoding="utf-8")),
    )
    radice.add_child(instance=nuova)
    nuova.save_revision().publish()
    for vecchia in radice.get_children().exclude(pk=nuova.pk):
        # La pagina di benvenuto di Wagtail (senza figlie) se ne va; altro resta com'è
        if type(vecchia.specific) is Page and vecchia.numchild == 0:
            Site.objects.filter(root_page=vecchia).update(root_page=nuova)
            vecchia.delete()
    Site.objects.filter(is_default_site=True).update(root_page=nuova, site_name=TITOLO_HOME)
    if not Site.objects.exists():
        Site.objects.create(
            hostname="localhost", root_page=nuova, is_default_site=True, site_name=TITOLO_HOME
        )
    nuova.refresh_from_db()
    if not nuova.get_siblings().filter(slug="home").exists():
        nuova.slug = "home"
        nuova.save_revision().publish()
    # Riletta dal database: url_path aggiornato per le pagine figlie
    return HomePage.objects.get(pk=nuova.pk)


def _crea(genitore: Page, dati: dict[str, Any]) -> int:
    creati = 0
    pagina = genitore.get_children().filter(slug=dati["slug"]).first()
    if pagina is None:
        corpo = dati.get("corpo", [])
        if "corpo_da_file" in dati:
            corpo = json.loads((CARTELLA / dati["corpo_da_file"]).read_text(encoding="utf-8"))
        tipo = TIPI[dati["tipo"]]
        campi: dict[str, Any] = {
            "title": dati["titolo"],
            "slug": dati["slug"],
            "riassunto": dati.get("riassunto", ""),
            "corpo": corpo,
            "show_in_menus": True,
        }
        if tipo is PaginaRegolamento:
            campi["aggiornato_a"] = dati.get("aggiornato_a", "")
        pagina = tipo(**campi)
        if tipo is PaginaStrutture:
            # Tutte quelle disponibili; poi le sceglie la redazione nella pagina (D-12)
            pagina.strutture = list(Struttura.objects.exclude(uso=Struttura.Uso.NON_DISPONIBILE))
        if dati.get("bozza"):
            pagina.live = False
        genitore.add_child(instance=pagina)
        revisione = pagina.save_revision()
        if not dati.get("bozza"):
            revisione.publish()
        creati += 1
    for figlia in dati.get("figlie", []):
        creati += _crea(pagina, figlia)
    return creati


def crea_sito() -> int:
    """Home, pagine (P-17) e reindirizzamenti dai vecchi indirizzi del Google Site."""
    radice_sito = home()
    creati = sum(_crea(radice_sito, dati) for dati in contenuti.PAGINE)
    for vecchio, nuovo in contenuti.REINDIRIZZAMENTI.items():
        _, creato = Redirect.objects.get_or_create(
            old_path=Redirect.normalise_path(vecchio),
            site=None,
            defaults={"redirect_link": nuovo, "is_permanent": True},
        )
        creati += int(creato)
    return creati
