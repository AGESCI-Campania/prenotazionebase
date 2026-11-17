from typing import Any

from wagtail.signals import page_published

from .models import PaginaRegolamento


def regolamento_pubblicato(sender: Any, instance: PaginaRegolamento, **kwargs: Any) -> None:
    from .regolamento import genera_pdf

    genera_pdf(instance)


page_published.connect(regolamento_pubblicato, sender=PaginaRegolamento)
