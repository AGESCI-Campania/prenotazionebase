"""Export per la contabilità (D-19, P-09): prenotazioni e incassi di un periodo, in Excel o CSV.

Importi in euro con due decimali (dai centesimi, senza float nei calcoli: si divide solo per
scriverli). I dati personali si limitano al gruppo e al numero di prenotazione.
"""

import csv
import datetime
import io
from decimal import Decimal

from openpyxl import Workbook

from tana.prenotazioni import contributo
from tana.prenotazioni.models import Pagamento, Prenotazione


def _euro(centesimi: int | None) -> Decimal | None:
    return None if centesimi is None else Decimal(centesimi) / 100


def prenotazioni(dal: datetime.date, al: datetime.date) -> tuple[list[str], list[list]]:
    """Prenotazioni con arrivo nel periodo, con preventivo, consuntivo e pagamenti."""
    intestazione = [
        "Numero",
        "Gruppo",
        "Categoria",
        "Stato",
        "Arrivo",
        "Partenza",
        "Aree",
        "Persone",
        "Preventivo €",
        "Consuntivo €",
        "Acconto versato €",
        "Saldo €",
    ]
    righe = []
    elenco = (
        Prenotazione.objects.filter(arrivo__gte=dal, arrivo__lte=al)
        .select_related("categoria")
        .prefetch_related("presenze__area")
        .order_by("arrivo", "numero")
    )
    for p in elenco:
        consuntivo = contributo.riepilogo(p, contributo.Fase.CONSUNTIVO)
        righe.append(
            [
                p.numero,
                p.gruppo,
                p.categoria.nome,
                p.get_stato_display(),
                p.arrivo,
                p.partenza,
                ", ".join(pr.area.nome for pr in p.presenze.all()),
                sum(pr.persone_effettive or pr.persone_previste for pr in p.presenze.all()),
                _euro(contributo.riepilogo(p).totale),
                _euro(consuntivo.totale) if consuntivo.righe else None,
                _euro(contributo.acconto_versato(p)),
                _euro(contributo.saldo(p)) if consuntivo.righe else None,
            ]
        )
    return intestazione, righe


def incassi(dal: datetime.date, al: datetime.date) -> tuple[list[str], list[list]]:
    """Pagamenti verificati con data nel periodo."""
    intestazione = ["Data", "Prenotazione", "Gruppo", "Categoria", "Tipo", "Importo €"]
    elenco = (
        Pagamento.objects.filter(
            stato=Pagamento.StatoPagamento.VERIFICATO, data__gte=dal, data__lte=al
        )
        .select_related("prenotazione__categoria")
        .order_by("data", "pk")
    )
    righe = [
        [
            pg.data,
            pg.prenotazione.numero,
            pg.prenotazione.gruppo,
            pg.prenotazione.categoria.nome,
            pg.get_tipo_display(),
            _euro(pg.importo_centesimi),
        ]
        for pg in elenco
    ]
    return intestazione, righe


def in_excel(titolo: str, intestazione: list[str], righe: list[list]) -> bytes:
    libro = Workbook()
    foglio = libro.active
    assert foglio is not None
    foglio.title = titolo[:31]
    foglio.append(intestazione)
    for riga in righe:
        foglio.append(riga)
    for colonna, nome in enumerate(intestazione, start=1):
        if nome.endswith("€"):
            for cella in foglio.iter_rows(min_row=2, min_col=colonna, max_col=colonna):
                cella[0].number_format = "#,##0.00"
        elif nome in ("Arrivo", "Partenza", "Data"):
            for cella in foglio.iter_rows(min_row=2, min_col=colonna, max_col=colonna):
                cella[0].number_format = "DD/MM/YYYY"
    uscita = io.BytesIO()
    libro.save(uscita)
    return uscita.getvalue()


def in_csv(intestazione: list[str], righe: list[list]) -> bytes:
    """CSV per Excel in italiano: separatore punto e virgola, virgola decimale, BOM UTF-8."""
    testo = io.StringIO()
    scrittore = csv.writer(testo, delimiter=";")
    scrittore.writerow(intestazione)
    for riga in righe:
        scrittore.writerow([_cella_csv(v) for v in riga])
    return ("﻿" + testo.getvalue()).encode("utf-8")


def _cella_csv(valore: object) -> str:
    if valore is None:
        return ""
    if isinstance(valore, Decimal):
        return f"{valore:.2f}".replace(".", ",")
    if isinstance(valore, datetime.date):
        return f"{valore:%d/%m/%Y}"
    return str(valore)
