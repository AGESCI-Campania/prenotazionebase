"""Grafici a barre in SVG per le statistiche, generati sul server (niente JavaScript).

Barre sottili con l'estremità arrotondata lontana dalla base, 2px di spazio tra le barre di un
gruppo, griglia leggera, valore al passaggio del mouse (`<title>`). I colori sono classi CSS
(`tana-grafico__serie-N` in tana.css); accanto a ogni grafico c'è sempre la tabella dei numeri.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

LARGHEZZA, ALTEZZA = 720, 220
MARGINE_SINISTRO, MARGINE_BASSO, MARGINE_ALTO = 48, 22, 8
SPAZIO = 2  # tra le barre dello stesso gruppo
RAGGIO = 3


@dataclass(frozen=True)
class Serie:
    nome: str
    valori: Sequence[float | None]  # None = dato assente (nessuna barra)
    colore: int = 0  # classe tana-grafico__serie-N; 0 = posizione della serie


def _scala(massimo: float) -> float:
    """Fondo scala "tondo" (1, 2, 2,5 o 5 per una potenza di 10) sopra il massimo."""
    if massimo <= 0:
        return 1
    potenza = 10 ** math.floor(math.log10(massimo))
    for passo in (1, 2, 2.5, 5, 10):
        if massimo <= passo * potenza:
            return passo * potenza
    return 10 * potenza


def _tacche(fondo: float) -> int:
    """Intervalli dell'asse con valori tondi: 200 → 4 da 50, 500 → 5 da 100, 100 → 5 da 20."""
    mantissa = fondo / 10 ** math.floor(math.log10(fondo))
    return 4 if math.isclose(mantissa, 2) else 5


def _barra(x: float, y: float, larghezza: float, altezza: float) -> str:
    """Rettangolo con gli angoli in alto arrotondati, appoggiato alla base."""
    r = min(RAGGIO, larghezza / 2, altezza)
    return (
        f"M{x:.1f},{y + altezza:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}"
        f"H{x + larghezza - r:.1f}Q{x + larghezza:.1f},{y:.1f} {x + larghezza:.1f},{y + r:.1f}"
        f"V{y + altezza:.1f}Z"
    )


def barre(
    categorie: Sequence[str],
    serie: Sequence[Serie],
    *,
    titolo: str,
    formato: Callable[[float], str] = lambda v: f"{v:,.0f}".replace(",", "."),
    massimo: float | None = None,
    larghezza: int = LARGHEZZA,
) -> SafeString:
    """Barre raggruppate per categoria (es. i mesi), una per serie. Con `larghezza` minore il
    grafico è pensato per mezza riga: le scritte restano leggibili."""
    valori = [v for s in serie for v in s.valori if v is not None]
    fondo = massimo if massimo is not None else _scala(max(valori, default=0))
    area_x = larghezza - MARGINE_SINISTRO
    area_y = ALTEZZA - MARGINE_BASSO - MARGINE_ALTO
    gruppo = area_x / len(categorie)
    larghezza_barra = min(14.0, (gruppo * 0.7 - SPAZIO * (len(serie) - 1)) / len(serie))
    parti = [
        f'<svg class="tana-grafico" viewBox="0 0 {larghezza} {ALTEZZA}" role="img" '
        f'aria-label="{escape(titolo)}">'
    ]
    tacche = _tacche(fondo)
    for passo in range(tacche + 1):  # griglia e valori dell'asse
        tacca = fondo * passo / tacche
        y = MARGINE_ALTO + area_y * (1 - passo / tacche)
        parti.append(
            f'<line class="tana-grafico__griglia" x1="{MARGINE_SINISTRO}" x2="{larghezza}" '
            f'y1="{y:.1f}" y2="{y:.1f}"/><text class="tana-grafico__asse" x="{MARGINE_SINISTRO - 6}" '
            f'y="{y + 4:.1f}" text-anchor="end">{escape(formato(tacca))}</text>'
        )
    for i, categoria in enumerate(categorie):
        inizio = MARGINE_SINISTRO + gruppo * i
        occupato = larghezza_barra * len(serie) + SPAZIO * (len(serie) - 1)
        x = inizio + (gruppo - occupato) / 2
        for n, s in enumerate(serie, start=1):
            valore = s.valori[i]
            if valore:
                altezza = area_y * min(valore, fondo) / fondo
                y = MARGINE_ALTO + area_y - altezza
                parti.append(
                    f'<path class="tana-grafico__serie-{s.colore or n}" d="{_barra(x, y, larghezza_barra, altezza)}">'
                    f"<title>{escape(categoria)} · {escape(s.nome)}: {escape(formato(valore))}</title>"
                    "</path>"
                )
            x += larghezza_barra + SPAZIO
        parti.append(
            f'<text class="tana-grafico__asse" x="{inizio + gruppo / 2:.1f}" '
            f'y="{ALTEZZA - 6}" text-anchor="middle">{escape(categoria)}</text>'
        )
    parti.append(
        f'<line class="tana-grafico__base" x1="{MARGINE_SINISTRO}" x2="{larghezza}" '
        f'y1="{MARGINE_ALTO + area_y}" y2="{MARGINE_ALTO + area_y}"/></svg>'
    )
    return mark_safe("".join(parti))  # noqa: S308 - solo numeri e testi passati da escape
