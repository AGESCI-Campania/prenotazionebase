"""Flusso della prenotazione (§4): richiesta → approvazione → acconto → conferma → svolta →
chiusa, con rifiuto, annullamento e scadenze.

Ogni transizione controlla i permessi (§6), aggiorna le occupazioni, scrive lo storico e invia
le email (D-19). Le decisioni discrezionali richiedono "deciso da" e motivazione (P-03).
"""

import datetime
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files import File
from django.db import transaction
from django.utils import timezone

from tana.accounts import permessi
from tana.base.models import Area, Configurazione
from tana.core.services import registra_decisione, registra_evento
from tana.listini.models import Categoria

from . import consensi, contributo, notifiche
from .models import (
    AttivitaGiornaliera,
    Contatto,
    Pagamento,
    Prenotazione,
    PresenzaArea,
    Stato,
)
from .services import crea_prenotazione, sincronizza_occupazioni

StatoPagamento = Pagamento.StatoPagamento

# Da questi stati la prenotazione si può annullare (§4)
STATI_ANNULLABILI = frozenset({Stato.RICHIESTA, Stato.APPROVATA, Stato.CONFERMATA})


class TransizioneNonValida(ValidationError):
    def __init__(self, prenotazione: Prenotazione, azione: str) -> None:
        super().__init__(
            f"Non si può {azione}: la prenotazione {prenotazione.numero} è "
            f"{prenotazione.get_stato_display()}."
        )


def _richiedi(condizione: bool) -> None:
    if not condizione:
        raise PermissionDenied("Non hai i permessi per questa operazione.")


def _blocca(prenotazione: Prenotazione) -> None:
    """Blocca la riga (scheduler e utenti possono agire insieme) e rilegge lo stato."""
    Prenotazione.objects.select_for_update().filter(pk=prenotazione.pk).first()
    prenotazione.refresh_from_db()


def _cambia_stato(
    prenotazione: Prenotazione, nuovo: str, *, utente: Any, azione: str, **dati: Any
) -> None:
    prima = prenotazione.stato
    prenotazione.stato = nuovo
    prenotazione.save()
    sincronizza_occupazioni(prenotazione)
    registra_evento(
        prenotazione,
        azione,
        utente=utente,
        prima={"stato": prima},
        dopo={"stato": nuovo, **dati},
    )


# --- Richiesta --------------------------------------------------------------------------


@transaction.atomic
def invia_richiesta(
    *,
    utente: Any,
    categoria: Categoria,
    arrivo: datetime.date,
    partenza: datetime.date,
    presenze: dict[str, int] | None = None,
    attivita: list[tuple[datetime.date, str, int]] | None = None,
    contatto: Contatto | None = None,
    capo_responsabile: Contatto | None = None,
    gruppo: str = "",
    specifica_categoria: str = "",
    unita: list[str] | None = None,
    esclusiva_richiesta: bool = False,
    note: str = "",
    da_gestione: bool = False,
    deciso_da: str = "",
    motivazione: str = "",
) -> Prenotazione:
    """Nuova richiesta (stato RICHIESTA, le date si occupano subito: P-01).

    `presenze`: persone per codice di area; `attivita`: (data, tipo, persone) delle attività in
    giornata. Chi invia è il titolare, anche se ha un ruolo di gestione, e chiede la categoria
    prioritaria (P-06). Con `da_gestione` (solo amministrazione) la prenotazione non ha titolare
    e la categoria prioritaria è assegnata: è una decisione discrezionale (D-14), come la
    prenotazione oltre l'orizzonte (D-25) o senza contatti (D-10).
    """
    _richiedi(getattr(utente, "is_authenticated", False))
    if da_gestione:
        _richiedi(permessi.e_amministrazione(utente))
    gestione = da_gestione
    presenze = {codice: persone for codice, persone in (presenze or {}).items() if persone}
    attivita = attivita or []
    oggi = timezone.localdate()
    conf = Configurazione.corrente()
    errori: dict[str, str] = {}

    if not presenze and not attivita:
        errori["presenze"] = "Indica le persone in almeno un'area o un'attività in giornata."
    if partenza < arrivo:
        errori["partenza"] = "La partenza non può precedere l'arrivo."
    elif presenze and partenza == arrivo:
        errori["partenza"] = "Un soggiorno dura almeno una notte."
    if arrivo < oggi:
        errori["arrivo"] = "La data di arrivo è già passata."
    if arrivo > conf.orizzonte_massimo and not (gestione and categoria.prioritaria):
        errori["arrivo"] = (
            f"Si accettano richieste con arrivo fino al {conf.orizzonte_massimo:%d/%m/%Y}."
        )
    if categoria.richiede_specifica and not specifica_categoria.strip():
        errori["specifica_categoria"] = "Specifica l'associazione o l'ente."
    if esclusiva_richiesta and set(presenze) != {Area.ACCANTONAMENTO}:
        errori["esclusiva_richiesta"] = (
            "L'uso esclusivo si chiede solo prenotando l'accantonamento."
        )
    if contatto is None and not (gestione and categoria.prioritaria):
        errori["contatto"] = "Indica il referente della prenotazione."
    for data, _, _ in attivita:
        if not arrivo <= data <= partenza:
            errori["attivita"] = "Le attività in giornata devono cadere nel periodo richiesto."
    if errori:
        raise ValidationError(errori)

    concessa = gestione and categoria.prioritaria
    prenotazione = crea_prenotazione(
        categoria=categoria,
        specifica_categoria=specifica_categoria.strip(),
        richiedente=None if gestione else utente,
        contatto=contatto,
        capo_responsabile=capo_responsabile,
        gruppo=gruppo.strip(),
        unita=unita or [],
        arrivo=arrivo,
        partenza=partenza,
        esclusiva_richiesta=esclusiva_richiesta,
        categoria_prioritaria_richiesta=categoria.prioritaria,
        categoria_prioritaria_concessa=concessa,
        note=note,
    )
    aree = {a.codice: a for a in Area.objects.filter(codice__in=presenze)}
    for codice, persone in presenze.items():
        PresenzaArea.objects.create(
            prenotazione=prenotazione, area=aree[codice], persone_previste=persone
        )
    for data, tipo, persone in attivita:
        AttivitaGiornaliera.objects.create(
            prenotazione=prenotazione, data=data, tipo=tipo, persone_previste=persone
        )
    sincronizza_occupazioni(prenotazione)
    contributo.aggiorna_preventivo(prenotazione, utente=utente)
    consensi.chiedi_consensi(prenotazione)
    if concessa:
        registra_decisione(
            prenotazione,
            "categoria prioritaria assegnata",
            utente=utente,
            deciso_da=deciso_da,
            motivazione=motivazione,
            dopo={"categoria": categoria.codice},
        )
    registra_evento(
        prenotazione, "richiesta inviata", utente=utente, dopo={"stato": Stato.RICHIESTA}
    )
    notifiche.notifica(prenotazione, "richiesta_inviata")
    return prenotazione


# --- Approvazione e rifiuto -------------------------------------------------------------


@transaction.atomic
def approva(
    prenotazione: Prenotazione,
    *,
    utente: Any,
    concedi_esclusiva: bool = False,
    concedi_categoria: bool = False,
    acconto_centesimi: int | None = None,
    deciso_da: str = "",
    motivazione: str = "",
) -> Prenotazione:
    """Approva una richiesta (solo amministrazione).

    Concessione dell'esclusiva o della categoria prioritaria e importo dell'acconto diverso dal
    previsto (anche zero: esenzione) sono decisioni discrezionali (D-14). Con le voci da definire
    l'approvazione non è possibile (P-04). Con acconto zero la conferma resta manuale.
    """
    _richiedi(permessi.e_amministrazione(utente))
    _blocca(prenotazione)
    if prenotazione.stato != Stato.RICHIESTA:
        raise TransizioneNonValida(prenotazione, "approvare")
    if consensi.mancanti(prenotazione).exists():
        raise ValidationError(
            "Manca il consenso del gruppo già presente: senza consenso la richiesta va rifiutata."
        )
    decisioni: dict[str, Any] = {}
    if concedi_esclusiva:
        if not prenotazione.esclusiva_richiesta:
            raise ValidationError("L'esclusiva non è stata richiesta.")
        prenotazione.esclusiva_concessa = True
        decisioni["esclusiva_concessa"] = True
    if concedi_categoria:
        if not prenotazione.categoria_prioritaria_richiesta:
            raise ValidationError("La categoria prioritaria non è stata richiesta.")
        prenotazione.categoria_prioritaria_concessa = True
        decisioni["categoria_prioritaria_concessa"] = True
    if decisioni:
        prenotazione.save()
        sincronizza_occupazioni(prenotazione)
    preventivo = contributo.aggiorna_preventivo(prenotazione, utente=utente)
    if preventivo.da_definire:
        raise ValidationError("Valorizza le voci da definire del preventivo prima di approvare.")
    previsto = contributo.acconto_previsto(prenotazione)
    acconto = previsto if acconto_centesimi is None else acconto_centesimi
    if acconto != previsto:
        decisioni["acconto_centesimi"] = acconto
    if decisioni:
        registra_decisione(
            prenotazione,
            "decisioni dell'approvazione",
            utente=utente,
            deciso_da=deciso_da,
            motivazione=motivazione,
            prima={"acconto_previsto": previsto},
            dopo=decisioni,
        )
    adesso = timezone.now()
    giorni = Configurazione.corrente().acconto_giorni
    prenotazione.approvata_il = adesso
    prenotazione.acconto_centesimi = acconto
    prenotazione.scadenza_acconto = adesso + datetime.timedelta(days=giorni) if acconto else None
    _cambia_stato(
        prenotazione, Stato.APPROVATA, utente=utente, azione="approvata", acconto_centesimi=acconto
    )
    notifiche.notifica(prenotazione, "approvata")
    return prenotazione


@transaction.atomic
def rifiuta(
    prenotazione: Prenotazione,
    *,
    utente: Any,
    deciso_da: str,
    motivazione: str,
    comunica_motivazione: bool = False,
) -> Prenotazione:
    """Rifiuta una richiesta: motivazione obbligatoria, comunicata al richiedente solo se
    indicato."""
    _richiedi(permessi.e_amministrazione(utente))
    _blocca(prenotazione)
    if prenotazione.stato != Stato.RICHIESTA:
        raise TransizioneNonValida(prenotazione, "rifiutare")
    registra_decisione(
        prenotazione,
        "richiesta rifiutata",
        utente=utente,
        deciso_da=deciso_da,
        motivazione=motivazione,
        dopo={"comunica_motivazione": comunica_motivazione},
    )
    _cambia_stato(prenotazione, Stato.RIFIUTATA, utente=utente, azione="rifiutata")
    notifiche.notifica(
        prenotazione,
        "rifiutata",
        motivazione=motivazione.strip(),
        comunica_motivazione=comunica_motivazione,
    )
    return prenotazione


@transaction.atomic
def annulla(prenotazione: Prenotazione, *, utente: Any, motivo: str = "") -> Prenotazione:
    """Annulla (il richiedente sempre online, o l'amministrazione): le date si liberano,
    l'acconto versato resta alla base (D-13)."""
    _richiedi(permessi.e_titolare(utente, prenotazione) or permessi.e_amministrazione(utente))
    _blocca(prenotazione)
    if prenotazione.stato not in STATI_ANNULLABILI:
        raise TransizioneNonValida(prenotazione, "annullare")
    prenotazione.scadenza_acconto = None
    _cambia_stato(
        prenotazione, Stato.ANNULLATA, utente=utente, azione="annullata", motivo=motivo.strip()
    )
    notifiche.notifica(
        prenotazione,
        "annullata",
        motivo=motivo.strip(),
        acconto_versato=contributo.acconto_versato(prenotazione),
    )
    return prenotazione


# --- Acconto e conferma -----------------------------------------------------------------


@transaction.atomic
def carica_ricevuta(prenotazione: Prenotazione, *, utente: Any, ricevuta: File) -> Pagamento:
    """Ricevuta del bonifico dell'acconto: entro il termine ferma la scadenza (D-13)."""
    _richiedi(permessi.e_titolare(utente, prenotazione) or permessi.e_pattuglia(utente))
    _blocca(prenotazione)
    if prenotazione.stato != Stato.APPROVATA or not prenotazione.acconto_centesimi:
        raise TransizioneNonValida(prenotazione, "caricare la ricevuta")
    if prenotazione.pagamenti.filter(
        tipo=Pagamento.Tipo.ACCONTO, stato=StatoPagamento.IN_VERIFICA
    ).exists():
        raise ValidationError("C'è già una ricevuta da verificare.")
    if prenotazione.scadenza_acconto and prenotazione.scadenza_acconto < timezone.now():
        raise ValidationError("Il termine per caricare la ricevuta è scaduto.")
    pagamento = Pagamento(
        prenotazione=prenotazione,
        tipo=Pagamento.Tipo.ACCONTO,
        importo_centesimi=prenotazione.acconto_centesimi,
        stato=StatoPagamento.IN_VERIFICA,
        registrato_da=utente,
        data=timezone.localdate(),
    )
    pagamento.ricevuta.save(ricevuta.name or "ricevuta", ricevuta, save=False)
    pagamento.save()
    prenotazione.scadenza_acconto = None
    prenotazione.save(update_fields=["scadenza_acconto", "aggiornata_il"])
    registra_evento(prenotazione, "ricevuta caricata", utente=utente)
    notifiche.notifica(prenotazione, "ricevuta_caricata", pagamento=pagamento)
    return pagamento


@transaction.atomic
def verifica_ricevuta(
    pagamento: Pagamento, *, utente: Any, importo_centesimi: int | None = None
) -> Prenotazione:
    """La Pattuglia verifica la ricevuta (importo correggibile): la prenotazione è confermata."""
    _richiedi(permessi.e_pattuglia(utente))
    prenotazione = pagamento.prenotazione
    _blocca(prenotazione)
    pagamento.refresh_from_db()
    if pagamento.stato != StatoPagamento.IN_VERIFICA or prenotazione.stato != Stato.APPROVATA:
        raise TransizioneNonValida(prenotazione, "verificare la ricevuta")
    if importo_centesimi is not None:
        pagamento.importo_centesimi = importo_centesimi
    pagamento.stato = StatoPagamento.VERIFICATO
    pagamento.verificato_da, pagamento.verificato_il = utente, timezone.now()
    pagamento.save()
    _cambia_stato(
        prenotazione,
        Stato.CONFERMATA,
        utente=utente,
        azione="confermata (acconto verificato)",
        acconto_versato=pagamento.importo_centesimi,
    )
    notifiche.notifica(prenotazione, "confermata", pagamento=pagamento)
    return prenotazione


@transaction.atomic
def respingi_ricevuta(pagamento: Pagamento, *, utente: Any, motivazione: str) -> Prenotazione:
    """Ricevuta non valida: il termine per caricarne un'altra riparte da ora."""
    _richiedi(permessi.e_pattuglia(utente))
    if not motivazione.strip():
        raise ValidationError({"motivazione": "Indica perché la ricevuta non è valida."})
    prenotazione = pagamento.prenotazione
    _blocca(prenotazione)
    pagamento.refresh_from_db()
    if pagamento.stato != StatoPagamento.IN_VERIFICA or prenotazione.stato != Stato.APPROVATA:
        raise TransizioneNonValida(prenotazione, "respingere la ricevuta")
    pagamento.stato = StatoPagamento.RESPINTO
    pagamento.verificato_da, pagamento.verificato_il = utente, timezone.now()
    pagamento.save()
    giorni = Configurazione.corrente().acconto_giorni
    prenotazione.scadenza_acconto = timezone.now() + datetime.timedelta(days=giorni)
    prenotazione.save(update_fields=["scadenza_acconto", "aggiornata_il"])
    registra_evento(
        prenotazione, "ricevuta respinta", utente=utente, dopo={"motivazione": motivazione}
    )
    notifiche.notifica(prenotazione, "ricevuta_respinta", motivazione=motivazione.strip())
    return prenotazione


@transaction.atomic
def conferma_senza_acconto(prenotazione: Prenotazione, *, utente: Any) -> Prenotazione:
    """Conferma manuale delle prenotazioni approvate senza acconto (Pattuglia)."""
    _richiedi(permessi.e_pattuglia(utente))
    _blocca(prenotazione)
    if prenotazione.stato != Stato.APPROVATA or prenotazione.acconto_centesimi:
        raise TransizioneNonValida(prenotazione, "confermare senza acconto")
    _cambia_stato(prenotazione, Stato.CONFERMATA, utente=utente, azione="confermata")
    notifiche.notifica(prenotazione, "confermata")
    return prenotazione


# --- Dopo il soggiorno ------------------------------------------------------------------


@transaction.atomic
def segna_svolta(prenotazione: Prenotazione, *, utente: Any = None) -> Prenotazione:
    """Soggiorno concluso (dopo la partenza). Lo storico importato NON_SVOLTA si corregge in
    SVOLTA solo dall'amministrazione, senza email."""
    _blocca(prenotazione)
    if prenotazione.stato == Stato.NON_SVOLTA:
        _richiedi(permessi.e_amministrazione(utente))
        _cambia_stato(prenotazione, Stato.SVOLTA, utente=utente, azione="corretta in svolta")
        return prenotazione
    if utente is not None:
        _richiedi(permessi.e_pattuglia(utente))
    if prenotazione.stato != Stato.CONFERMATA or prenotazione.partenza > timezone.localdate():
        raise TransizioneNonValida(prenotazione, "segnare come svolta")
    _cambia_stato(prenotazione, Stato.SVOLTA, utente=utente, azione="svolta")
    notifiche.notifica(prenotazione, "svolta")
    return prenotazione


@transaction.atomic
def chiudi(prenotazione: Prenotazione, *, utente: Any) -> Prenotazione:
    """Consuntivo compilato e inviato al richiedente (§4)."""
    _richiedi(permessi.e_pattuglia(utente))
    _blocca(prenotazione)
    if prenotazione.stato != Stato.SVOLTA:
        raise TransizioneNonValida(prenotazione, "chiudere")
    consuntivo = contributo.riepilogo(prenotazione, contributo.Fase.CONSUNTIVO)
    if not consuntivo.righe:
        raise ValidationError("Compila il consuntivo prima di chiudere.")
    if consuntivo.da_definire:
        raise ValidationError("Valorizza le voci da definire del consuntivo.")
    saldo = contributo.saldo(prenotazione)
    _cambia_stato(
        prenotazione,
        Stato.CHIUSA,
        utente=utente,
        azione="chiusa",
        totale_centesimi=consuntivo.totale,
        saldo_centesimi=saldo,
    )
    notifiche.notifica(
        prenotazione,
        "chiusa",
        consuntivo=consuntivo,
        acconto_versato=contributo.acconto_versato(prenotazione),
        saldo=saldo,
    )
    return prenotazione


# --- Scadenze (servizio scheduler, P-07) ------------------------------------------------


def scadi_acconti() -> int:
    """Approvate senza ricevuta entro il termine → SCADUTA, date liberate (D-13)."""
    scadute = 0
    candidate = Prenotazione.objects.filter(
        stato=Stato.APPROVATA, scadenza_acconto__lt=timezone.now()
    ).values_list("pk", flat=True)
    for pk in candidate:
        with transaction.atomic():
            prenotazione = Prenotazione.objects.get(pk=pk)
            _blocca(prenotazione)
            if (
                prenotazione.stato != Stato.APPROVATA
                or prenotazione.scadenza_acconto is None
                or prenotazione.scadenza_acconto >= timezone.now()
            ):
                continue
            prenotazione.scadenza_acconto = None
            _cambia_stato(prenotazione, Stato.SCADUTA, utente=None, azione="scaduta")
            notifiche.notifica(prenotazione, "scaduta")
            scadute += 1
    return scadute


def segna_svolte() -> int:
    """Confermate con la partenza passata → SVOLTA (§4)."""
    svolte = 0
    candidate = Prenotazione.objects.filter(
        stato=Stato.CONFERMATA, partenza__lt=timezone.localdate()
    ).values_list("pk", flat=True)
    for pk in candidate:
        try:
            segna_svolta(Prenotazione.objects.get(pk=pk))
        except TransizioneNonValida:
            continue  # cambiata nel frattempo
        svolte += 1
    return svolte
