"""Helper comuni ai test delle prenotazioni."""

import datetime

from django.utils import timezone

from tana.accounts.models import User
from tana.accounts.services import nomina
from tana.listini.models import Categoria
from tana.prenotazioni import flusso

CASELLA_BASE = "baseaiellodelsabato@campania.agesci.it"
EURO = 100


def tra(giorni):
    return timezone.localdate() + datetime.timedelta(days=giorni)


def utente_con(ruolo, email):
    utente = User.objects.create_user(email)
    if ruolo:
        nomina(utente, ruolo)
    return utente


def richiesta(utente, contatto, arrivo=10, partenza=15, categoria="gruppo-agesci", **campi):
    campi.setdefault("presenze", {"ACC": 28})
    campi.setdefault("gruppo", "Avellino 1")
    return flusso.invia_richiesta(
        utente=utente,
        categoria=Categoria.objects.get(codice=categoria),
        arrivo=tra(arrivo),
        partenza=tra(partenza),
        contatto=contatto,
        **campi,
    )
