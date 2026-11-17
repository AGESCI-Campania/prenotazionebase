"""Modalità demo (D-32): prova del sistema prima dell'apertura delle prenotazioni.

Si attiva solo senza prenotazioni. Mentre è attiva prenota solo la gestione (Pattuglia,
amministratore, responsabile) e l'import si può provare; le email partono normalmente. Al
termine si cancellano tutte le prenotazioni con pagamenti, ricevute, messaggi, consensi,
contatti, storico e numerazione; restano account, listini, configurazione e date bloccate.
"""

from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from tana.accounts import permessi
from tana.base.models import Configurazione
from tana.core.models import EventoStorico
from tana.core.services import registra_evento

from .models import BloccoTecnico, ContatoreNumeri, Contatto, Pagamento, Prenotazione

MESSAGGIO_DEMO = (
    "Le prenotazioni non sono ancora aperte: è in corso una prova del sistema. Riprova tra "
    "qualche giorno."
)


def puo_prenotare(utente: Any) -> bool:
    """In demo prenota solo la gestione."""
    return not Configurazione.corrente().modalita_demo or permessi.e_pattuglia(utente)


@transaction.atomic
def attiva(*, utente: Any) -> None:
    if not permessi.e_amministrazione(utente):
        raise PermissionDenied
    conf = Configurazione.objects.select_for_update().get(pk=Configurazione.corrente().pk)
    if Prenotazione.objects.exists():
        raise ValidationError("La modalità demo si attiva solo quando non ci sono prenotazioni.")
    conf.modalita_demo = True
    conf.save(update_fields=["modalita_demo"])
    registra_evento(conf, "modalità demo attivata", utente=utente)


@transaction.atomic
def termina(*, utente: Any) -> int:
    """Cancella tutte le prenotazioni e chiude la demo; restituisce quante erano."""
    if not permessi.e_amministrazione(utente):
        raise PermissionDenied
    conf = Configurazione.objects.select_for_update().get(pk=Configurazione.corrente().pk)
    if not conf.modalita_demo:
        raise ValidationError("La modalità demo non è attiva.")
    numero = Prenotazione.objects.count()
    archivio = Pagamento._meta.get_field("ricevuta").storage  # type: ignore[union-attr]
    ricevute = list(Pagamento.objects.exclude(ricevuta="").values_list("ricevuta", flat=True))
    # Storico delle prenotazioni e dei loro dati (non quello delle date bloccate, sulle aree)
    tipi = ContentType.objects.filter(app_label="prenotazioni").exclude(
        model=BloccoTecnico._meta.model_name
    )
    EventoStorico.objects.filter(content_type__in=tipi).delete()
    Pagamento.objects.all().delete()
    Prenotazione.objects.all().delete()  # a cascata presenze, righe, occupazioni, messaggi…
    Contatto.objects.all().delete()
    ContatoreNumeri.objects.all().delete()  # le prenotazioni vere ripartono da AAAA-001
    conf.modalita_demo = False
    conf.save(update_fields=["modalita_demo"])
    registra_evento(
        conf, "modalità demo terminata", utente=utente, dopo={"prenotazioni_cancellate": numero}
    )

    def elimina_file() -> None:
        for nome in ricevute:
            archivio.delete(nome)

    # I file solo a cancellazione riuscita
    transaction.on_commit(elimina_file)
    return numero
