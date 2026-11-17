"""Sito della base in Wagtail (D-30): home, pagine di contenuto, pagina riservata (D-20).

Listino, prenotazioni e disponibilità non sono pagine Wagtail: sono pagine di Tana collegate
nel menu (`config/urls.py`, rotta di Wagtail per ultima).
"""

from typing import Any

from django import forms
from django.db import models
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from modelcluster.fields import ParentalManyToManyField
from wagtail.admin.panels import FieldPanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.search import index

from tana.accounts import permessi

from .blocchi import Corpo


class PaginaContenuto(Page):
    """Pagina del sito fatta di blocchi (P-16)."""

    riassunto = models.CharField(
        max_length=250,
        blank=True,
        help_text="Una frase per i riquadri della home e per i motori di ricerca.",
    )
    immagine_riquadro = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="immagine del riquadro",
        help_text="Foto del riquadro nella home.",
    )
    corpo = StreamField(Corpo(), blank=True, use_json_field=True)

    content_panels = [
        *Page.content_panels,
        FieldPanel("riassunto"),
        FieldPanel("immagine_riquadro"),
        FieldPanel("corpo"),
    ]
    search_fields = [
        *Page.search_fields,
        index.SearchField("riassunto"),
        index.SearchField("corpo"),
    ]
    parent_page_types = ["sito.HomePage", "sito.PaginaContenuto"]
    subpage_types = [
        "sito.PaginaContenuto",
        "sito.PaginaStrutture",
        "sito.PaginaRegolamento",
        "sito.PaginaRiservata",
    ]
    template = "sito/pagina_contenuto.html"

    class Meta:
        verbose_name = "pagina"
        verbose_name_plural = "pagine"


class PaginaStrutture(PaginaContenuto):
    """Le strutture: i blocchi della redazione più le strutture scelte nella pagina (D-12), con
    descrizione e galleria, raggruppate per area."""

    GRUPPI = (
        ("SOLO_ACC", "Accantonamento"),
        ("SOLO_TENDE", "Area tende"),
        ("CONDIVISA", "In comune"),
    )

    strutture = ParentalManyToManyField(
        "base.Struttura",
        blank=True,
        related_name="+",
        verbose_name="strutture mostrate",
        help_text="Le strutture da mostrare nella pagina: si modificano in Strutture.",
    )

    content_panels = [
        *PaginaContenuto.content_panels,
        FieldPanel("strutture", widget=forms.CheckboxSelectMultiple),
    ]
    template = "sito/pagina_strutture.html"
    max_count = 1

    class Meta:
        verbose_name = "pagina delle strutture"

    def get_context(self, request: HttpRequest, *args: Any, **kwargs: Any) -> dict[str, Any]:
        contesto = super().get_context(request, *args, **kwargs)
        scelte = list(
            self.strutture.order_by("ordine", "nome").prefetch_related("immagini__immagine")
        )
        contesto["gruppi"] = [
            (titolo, [s for s in scelte if s.uso == uso]) for uso, titolo in self.GRUPPI
        ]
        return contesto


class PaginaRegolamento(PaginaContenuto):
    """Regolamento della base: il testo sta qui (cronologia delle versioni di Wagtail); a ogni
    pubblicazione Tana ne genera il PDF, archiviato tra i documenti e allegato alle conferme."""

    aggiornato_a = models.CharField(
        "aggiornato a", max_length=50, blank=True, help_text="Es. «gennaio 2027», nel PDF."
    )
    pdf = models.ForeignKey(
        "wagtaildocs.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        editable=False,
        help_text="PDF dell'ultima versione pubblicata, generato da Tana.",
    )

    content_panels = [*PaginaContenuto.content_panels, FieldPanel("aggiornato_a")]
    template = "sito/pagina_regolamento.html"
    max_count = 1

    class Meta:
        verbose_name = "regolamento"
        verbose_name_plural = "regolamento"


class PaginaRiservata(PaginaContenuto):
    """Informazioni interne (D-20): solo ai gruppi con una prenotazione confermata e alla
    gestione."""

    template = "sito/pagina_contenuto.html"

    class Meta:
        verbose_name = "pagina riservata ai gruppi confermati"
        verbose_name_plural = "pagine riservate"

    def serve(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not permessi.vede_info_interne(request.user):
            return TemplateResponse(
                request, "sito/accesso_riservato.html", {"page": self, "self": self}, status=403
            )
        return super().serve(request, *args, **kwargs)


class HomePage(Page):
    """Home del sito (mockup 6)."""

    presentazione = models.TextField(
        blank=True, help_text="Frase sotto il titolo, nel riquadro verde in alto."
    )
    corpo = StreamField(Corpo(), blank=True, use_json_field=True)

    content_panels = [*Page.content_panels, FieldPanel("presentazione"), FieldPanel("corpo")]
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = ["sito.PaginaContenuto", "sito.PaginaStrutture", "sito.PaginaRiservata"]
    max_count = 1
    template = "sito/home_page.html"

    class Meta:
        verbose_name = "home"

    def get_context(self, request: HttpRequest, *args: Any, **kwargs: Any) -> dict[str, Any]:
        from tana.prenotazioni import disponibilita

        contesto = super().get_context(request, *args, **kwargs)
        oggi = timezone.localdate()
        contesto["riquadri"] = (
            self.get_children().live().in_menu().specific().filter(depth=self.depth + 1)
        )
        contesto["prossimi_giorni"] = disponibilita.prossimi_giorni(oggi, 14)
        return contesto


@register_setting(icon="cog")
class ImpostazioniSito(BaseSiteSetting):
    """Contatti, social e regolamento, modificabili dalla redazione (Impostazioni › Sito)."""

    email = models.EmailField(default="baseaiellodelsabato@campania.agesci.it")
    telefono = models.CharField(
        max_length=50,
        blank=True,
        default="081 457721 (segreteria regionale)",
        help_text="Es. il numero della segreteria regionale.",
    )
    facebook = models.URLField(blank=True, default="https://fb.me/basegiannisabatino")
    instagram = models.URLField(blank=True, default="https://www.instagram.com/basegiannisabatino/")

    panels = [
        FieldPanel("email"),
        FieldPanel("telefono"),
        FieldPanel("facebook"),
        FieldPanel("instagram"),
    ]

    class Meta:
        verbose_name = "impostazioni del sito"
