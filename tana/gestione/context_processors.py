from django.http import HttpRequest

from tana.accounts import permessi


def menu(request: HttpRequest) -> dict[str, bool]:
    """Voce «Gestione» nel menu per chi ha un ruolo che la vede (§6)."""
    return {"menu_gestione": permessi.vede_tutte_le_prenotazioni(request.user)}
