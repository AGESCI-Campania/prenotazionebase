"""Blocchi di contenuto delle pagine (P-16): solo questi, mai HTML libero."""

from typing import Any
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from wagtail import blocks
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.images.blocks import ImageChooserBlock

# Testo formattato senza titoli né incorporamenti: i titoli hanno il loro blocco
FORMATTAZIONE = ["bold", "italic", "ol", "ul", "link", "document-link"]

# Mappe incorporate solo da questi fornitori (anche nella CSP di produzione, frame-src)
MAPPE_CONSENTITE = {
    "www.google.com": "/maps/embed",
    "www.openstreetmap.org": "/export/embed.html",
}


class ImmagineBlock(blocks.StructBlock):
    immagine = ImageChooserBlock(label="Immagine")
    didascalia = blocks.CharBlock(label="Didascalia", required=False, max_length=250)

    class Meta:
        icon = "image"
        label = "Immagine con didascalia"
        template = "sito/blocchi/immagine.html"


class DocumentoBlock(blocks.StructBlock):
    documento = DocumentChooserBlock(label="Documento PDF")
    etichetta = blocks.CharBlock(
        label="Testo del link", required=False, help_text="Vuoto: il titolo del documento."
    )

    class Meta:
        icon = "doc-full"
        label = "Documento (PDF)"
        template = "sito/blocchi/documento.html"


class CitazioneBlock(blocks.StructBlock):
    testo = blocks.TextBlock(label="Citazione")
    autore = blocks.CharBlock(label="Autore", required=False)

    class Meta:
        icon = "openquote"
        label = "Citazione"
        template = "sito/blocchi/citazione.html"


class PulsanteBlock(blocks.StructBlock):
    etichetta = blocks.CharBlock(label="Testo del pulsante")
    pagina = blocks.PageChooserBlock(label="Pagina del sito", required=False)
    indirizzo = blocks.URLBlock(label="Oppure un indirizzo", required=False)

    class Meta:
        icon = "link"
        label = "Pulsante o link"
        template = "sito/blocchi/pulsante.html"

    def clean(self, value: Any) -> Any:
        valore = super().clean(value)
        if bool(valore.get("pagina")) == bool(valore.get("indirizzo")):
            raise blocks.StructBlockValidationError(
                block_errors={
                    "indirizzo": ValidationError("Indica una pagina oppure un indirizzo.")
                }
            )
        return valore


class MappaBlock(blocks.StructBlock):
    indirizzo = blocks.URLBlock(
        label="Indirizzo della mappa da incorporare",
        help_text="Google Maps (Condividi › Incorpora una mappa) o OpenStreetMap (Condividi › HTML).",
    )
    titolo = blocks.CharBlock(
        label="Descrizione", required=False, help_text="Per chi usa un lettore di schermo."
    )

    class Meta:
        icon = "site"
        label = "Mappa"
        template = "sito/blocchi/mappa.html"

    def clean(self, value: Any) -> Any:
        valore = super().clean(value)
        url = urlparse(valore.get("indirizzo") or "")
        percorso = MAPPE_CONSENTITE.get(url.hostname or "")
        if url.scheme != "https" or percorso is None or not url.path.startswith(percorso):
            raise blocks.StructBlockValidationError(
                block_errors={
                    "indirizzo": ValidationError(
                        "Sono ammesse solo mappe incorporate da Google Maps o OpenStreetMap."
                    )
                }
            )
        return valore


class Corpo(blocks.StreamBlock):
    titolo = blocks.CharBlock(label="Titolo", icon="title", template="sito/blocchi/titolo.html")
    paragrafo = blocks.RichTextBlock(label="Paragrafo", features=FORMATTAZIONE)
    immagine = ImmagineBlock()
    galleria = blocks.ListBlock(
        ImmagineBlock(), label="Galleria", icon="image", template="sito/blocchi/galleria.html"
    )
    documento = DocumentoBlock()
    citazione = CitazioneBlock()
    pulsante = PulsanteBlock()
    mappa = MappaBlock()
