"""Configurazione comune di pytest."""

import io

import pytest
from django.core.management import call_command


@pytest.fixture
def dati_iniziali(db):
    """Aree, strutture, listini 2022/2023, categorie e configurazione di `dati_iniziali`."""
    call_command("dati_iniziali", stdout=io.StringIO())
