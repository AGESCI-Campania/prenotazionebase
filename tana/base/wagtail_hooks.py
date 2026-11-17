"""Le strutture nell'editor del sito (D-12): snippet con la galleria."""

from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from .models import Struttura


class StrutturaViewSet(SnippetViewSet):
    model = Struttura
    icon = "home"
    menu_label = "Strutture"
    menu_order = 250
    add_to_admin_menu = True
    list_display = ["nome", "uso", "ordine"]
    list_filter = ["uso"]


register_snippet(StrutturaViewSet)
