"""Configurazione comune di pytest."""

import io

import pytest
from django.core.management import call_command


@pytest.fixture
def dati_iniziali(db):
    """Aree, strutture, listini 2022/2023, categorie, configurazione e gruppi di `dati_iniziali`,
    senza le pagine del sito (lente da creare: le usa la fixture `sito`)."""
    call_command("dati_iniziali", "--senza-sito", stdout=io.StringIO())


@pytest.fixture
def sito(dati_iniziali):
    """Anche le pagine del sito e i permessi della redazione (gruppi creati con il sito)."""
    from django.contrib.auth.models import Group

    Group.objects.all().delete()
    call_command("dati_iniziali", stdout=io.StringIO())
