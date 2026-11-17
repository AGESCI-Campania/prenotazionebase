"""Pagina pubblica dei listini in vigore (D-08)."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from tana.base.models import Configurazione

from .services import listini_in_vigore


def listino(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "listini/listino.html",
        {
            "sezione": "listino",
            "listini": listini_in_vigore(timezone.localdate()),
            "conf": Configurazione.corrente(),
        },
    )
