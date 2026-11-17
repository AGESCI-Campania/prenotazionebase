"""Menu del sito (D-30): le pagine di primo livello in menu; quelle con sottopagine diventano
un menu a tendina (es. Info)."""

from typing import Any

from django.http import HttpRequest
from wagtail.models import Site


def menu(request: HttpRequest) -> dict[str, Any]:
    sito = Site.find_for_request(request)
    if sito is None:
        return {"menu_sito": [], "home_sito": None}
    home = sito.root_page
    voci = []
    for pagina in home.get_children().live().in_menu():
        figlie = list(pagina.get_children().live().in_menu())
        voci.append({"pagina": pagina, "figlie": figlie})
    return {"menu_sito": voci, "home_sito": home}
