"""PDF con WeasyPrint (P-09): da un template HTML con CSS di stampa.

WeasyPrint si importa solo qui e solo quando serve: senza le librerie di sistema (Pango) l'app
parte lo stesso e fallisce solo la generazione del PDF (`PdfNonDisponibile`). In sviluppo sul
Mac: `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` (vedi mise.toml).
"""

from pathlib import Path
from typing import Any

from django.contrib.staticfiles import finders
from django.template.loader import render_to_string


class PdfNonDisponibile(Exception):
    """WeasyPrint o le sue librerie di sistema non sono disponibili."""


def file_statico(percorso: str) -> str:
    """URI `file://` di un file statico, per immagini e fogli di stile nel PDF."""
    trovato = finders.find(percorso)
    if not trovato:
        raise FileNotFoundError(percorso)
    return Path(str(trovato)).resolve().as_uri()


def genera(template: str, contesto: dict[str, Any]) -> bytes:
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as errore:
        raise PdfNonDisponibile(str(errore)) from errore
    html = render_to_string(
        template,
        {"logo": file_statico("tana/img/logo/scudo-base-aiello.svg"), **contesto},
    )
    pdf = HTML(string=html).write_pdf()
    assert pdf is not None
    return pdf
