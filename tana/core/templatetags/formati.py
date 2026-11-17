"""Formati italiani per i template: importi in centesimi → euro."""

from django import template

register = template.Library()


def euro(centesimi: int | None) -> str:
    """Da 134450 a «1.344,50 €»; «da definire» se l'importo manca (P-04)."""
    if centesimi is None:
        return "da definire"
    segno = "-" if centesimi < 0 else ""
    interi, decimali = divmod(abs(centesimi), 100)
    migliaia = f"{interi:,}".replace(",", ".")
    return f"{segno}{migliaia},{decimali:02d} €"


register.filter("euro", euro)
