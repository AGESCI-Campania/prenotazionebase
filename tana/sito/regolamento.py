"""PDF del regolamento: generato a ogni pubblicazione della pagina, non a ogni richiesta.

Ogni versione resta nell'archivio dei documenti (collezione «Regolamento»), così si sa quale
regolamento è stato allegato a una conferma; le email allegano l'ultima.
"""

import logging

from django.core.files.base import ContentFile
from django.utils import timezone
from wagtail.documents import get_document_model
from wagtail.models import Collection

from tana.core.pdf import PdfNonDisponibile, genera

from .models import PaginaRegolamento

log = logging.getLogger("tana.sito")
NOME_COLLEZIONE = "Regolamento"


def _collezione() -> Collection:
    radice = Collection.get_first_root_node()
    esistente = radice.get_children().filter(name=NOME_COLLEZIONE).first()
    return esistente or radice.add_child(name=NOME_COLLEZIONE)


def genera_pdf(pagina: PaginaRegolamento) -> None:
    """PDF della versione pubblicata, archiviato come documento e collegato alla pagina."""
    adesso = timezone.localtime()
    try:
        contenuto = genera("sito/pdf_regolamento.html", {"page": pagina, "data": adesso})
    except PdfNonDisponibile:
        log.exception("PDF del regolamento non generato: resta quello precedente")
        return
    Documento = get_document_model()
    documento = Documento(
        title=f"Regolamento della base – versione del {adesso:%d/%m/%Y %H:%M}",
        collection=_collezione(),
    )
    documento.file.save(f"regolamento-{adesso:%Y%m%d-%H%M}.pdf", ContentFile(contenuto), save=False)
    documento.save()
    PaginaRegolamento.objects.filter(pk=pagina.pk).update(pdf=documento)


def pdf_in_vigore() -> tuple[str, bytes] | None:
    """Nome e contenuto del PDF del regolamento pubblicato, per gli allegati."""
    pagina = PaginaRegolamento.objects.live().select_related("pdf").first()
    if pagina is None or pagina.pdf is None:
        return None
    with pagina.pdf.file.open("rb") as f:
        return "regolamento-base-aiello.pdf", f.read()
