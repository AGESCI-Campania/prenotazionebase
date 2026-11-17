"""Editor del sito: ritorno all'area di gestione dal menu di Wagtail."""

from typing import Any

from django.urls import reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem

from tana.accounts import permessi


class VoceGestione(MenuItem):
    def is_shown(self, request: Any) -> bool:
        return permessi.vede_tutte_le_prenotazioni(request.user)


@hooks.register("register_admin_menu_item")
def voce_gestione() -> MenuItem:
    return VoceGestione(
        "Gestione prenotazioni", reverse("gestione:cruscotto"), icon_name="arrow-left", order=1
    )
