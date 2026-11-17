"""Area di gestione (§8, mockup 4 e 5): Pattuglia, amministrazione, responsabile, segreteria.

Le viste mostrano dati e moduli; ogni azione passa dai servizi di dominio, che controllano i
permessi (§6) e scrivono lo storico.
"""

import datetime
from collections import defaultdict
from collections.abc import Callable
from functools import wraps
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.backends.postgresql.psycopg_any import DateRange
from django.db.models import Count, Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from tana.accounts import permessi
from tana.accounts.models import Nomina, Ruolo, User
from tana.accounts.services import nomina, revoca
from tana.aggiornamenti import services as servizi_aggiornamenti
from tana.aggiornamenti.models import ReleaseGitHub, RichiestaAggiornamento
from tana.base.models import Area, Configurazione
from tana.core.services import storico
from tana.listini.models import Categoria, Listino, VersioneListino
from tana.listini.services import nuova_versione
from tana.prenotazioni import consensi, contributo, demo, documenti, flusso, messaggi
from tana.prenotazioni.models import (
    BloccoTecnico,
    Occupazione,
    Pagamento,
    Prenotazione,
    RichiestaConsenso,
    RigaImporto,
    Stato,
)
from tana.prenotazioni.services import crea_blocco, elimina_blocco
from tana.prenotazioni.views_pubbliche import MESI, _mese

from . import export, grafici, statistiche
from .forms import (
    ApprovaForm,
    BloccoForm,
    CategoriaForm,
    ConfigurazioneForm,
    DatiVersioneForm,
    ExportForm,
    ModificaForm,
    MotivoForm,
    NominaForm,
    NuovaPrioritariaForm,
    OrariForm,
    PagamentoForm,
    PresenzeEffettiveForm,
    QuotaForm,
    RespingiForm,
    RifiutaForm,
    RispostaForm,
    ValorizzaForm,
    VersioneForm,
    VoceLiberaForm,
    VociFormSet,
)

Fase = contributo.Fase


def accesso(controllo: Callable[[Any], bool] = permessi.vede_tutte_le_prenotazioni) -> Callable:
    """Login e permesso per una vista della gestione."""

    def decoratore(vista: Callable) -> Callable:
        @wraps(vista)
        @login_required
        def interna(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            if not controllo(request.user):
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return interna

    return decoratore


def _contatori() -> dict[str, int]:
    return {
        "da_approvare": Prenotazione.objects.filter(stato=Stato.RICHIESTA).count(),
        "acconti": Pagamento.objects.filter(stato=Pagamento.StatoPagamento.IN_VERIFICA).count(),
        "consensi": RichiestaConsenso.objects.filter(
            stato=RichiestaConsenso.StatoConsenso.IN_ATTESA, richiesta__stato=Stato.RICHIESTA
        ).count(),
        "consuntivi": Prenotazione.objects.filter(stato=Stato.SVOLTA).count(),
        "messaggi": messaggi.senza_risposta().count(),
    }


# Sezione del menu laterale aperta per la voce attiva (le altre restano chiuse)
SEZIONI_MENU = {
    "configurazione": {
        "blocchi",
        "listini",
        "categorie",
        "configurazione",
        "aggiornamenti",
        "utenti",
    },
    "report": {"statistiche", "export"},
}


def _sezione(voce: str) -> str:
    return next((nome for nome, voci in SEZIONI_MENU.items() if voce in voci), "prenotazioni")


def _render(
    request: HttpRequest, template: str, voce: str, contesto: dict[str, Any]
) -> HttpResponse:
    utente = request.user
    contatori = _contatori()
    contesto.update(
        {
            "contatori": contatori,
            "contatori_totale": sum(contatori.values()),
            "voce_attiva": voce,
            "sezione_attiva": _sezione(voce),
            "demo": Configurazione.corrente().modalita_demo,
            "puo": {
                "pattuglia": permessi.e_pattuglia(utente),
                "amministrazione": permessi.e_amministrazione(utente),
                "ruoli": permessi.assegna_ruoli(utente),
            },
        }
    )
    return render(request, template, contesto)


def _errori(request: HttpRequest, errore: ValidationError | PermissionDenied) -> None:
    for testo in getattr(errore, "messages", None) or [str(errore) or "Operazione non permessa."]:
        messages.error(request, testo)


def _scheda(prenotazione: Prenotazione) -> str:
    return reverse("gestione:scheda", kwargs={"numero": prenotazione.numero})


# --- Cruscotto ed elenchi ---------------------------------------------------------------


@accesso()
def cruscotto(request: HttpRequest) -> HttpResponse:
    oggi = timezone.localdate()
    return _render(
        request,
        "gestione/cruscotto.html",
        "cruscotto",
        {"giornate": _arrivi_e_partenze(oggi, oggi), "oggi": oggi},
    )


ELENCHI = {
    "da_approvare": "Da approvare",
    "acconti": "Acconti da verificare",
    "consensi": "Consensi in attesa",
    "consuntivi": "Consuntivi da compilare",
    "messaggi": "Messaggi senza risposta",
    "tutte": "Tutte le prenotazioni",
}


@accesso()
def elenco(request: HttpRequest) -> HttpResponse:
    tipo = request.GET.get("elenco", "tutte")
    if tipo not in ELENCHI:
        raise Http404
    base = Prenotazione.objects.select_related("categoria", "contatto")
    if tipo == "da_approvare":
        prenotazioni = base.filter(stato=Stato.RICHIESTA).order_by("arrivo")
    elif tipo == "acconti":
        prenotazioni = base.filter(stato=Stato.APPROVATA).order_by("scadenza_acconto", "arrivo")
    elif tipo == "consensi":
        prenotazioni = (
            base.filter(
                consensi_chiesti__stato=RichiestaConsenso.StatoConsenso.IN_ATTESA,
                stato=Stato.RICHIESTA,
            )
            .distinct()
            .order_by("arrivo")
        )
    elif tipo == "consuntivi":
        prenotazioni = base.filter(stato=Stato.SVOLTA).order_by("partenza")
    elif tipo == "messaggi":
        conversazioni = messaggi.senza_risposta()
        prenotazioni = base.filter(conversazioni__in=conversazioni).order_by("arrivo")
    else:
        prenotazioni = base.order_by("-arrivo")
        cerca = request.GET.get("q", "").strip()
        if cerca:
            prenotazioni = prenotazioni.filter(
                Q(numero__icontains=cerca)
                | Q(gruppo__icontains=cerca)
                | Q(contatto__nome__icontains=cerca)
            )
        if request.GET.get("stato") in Stato.values:
            prenotazioni = prenotazioni.filter(stato=request.GET["stato"])
    in_verifica = set(
        Pagamento.objects.filter(stato=Pagamento.StatoPagamento.IN_VERIFICA).values_list(
            "prenotazione_id", flat=True
        )
    )
    return _render(
        request,
        "gestione/elenco.html",
        tipo,
        {
            "titolo": ELENCHI[tipo],
            "tipo": tipo,
            "prenotazioni": prenotazioni[:300],
            "in_verifica": in_verifica,
            "stati": Stato.choices,
            "q": request.GET.get("q", ""),
            "stato": request.GET.get("stato", ""),
        },
    )


# --- Scheda della prenotazione ----------------------------------------------------------


@accesso()
def scheda(request: HttpRequest, numero: str) -> HttpResponse:
    p = get_object_or_404(
        Prenotazione.objects.select_related("categoria", "contatto", "capo_responsabile"),
        numero=numero,
    )
    conversazione = messaggi.con_gestione(p)
    if permessi.e_pattuglia(request.user):
        messaggi.segna_letti(conversazione, lettore=None)
    preventivo = contributo.riepilogo(p)
    return _render(
        request,
        "gestione/scheda.html",
        "tutte",
        {
            "p": p,
            "preventivo": preventivo,
            "consuntivo": contributo.riepilogo(p, Fase.CONSUNTIVO),
            "acconto_previsto": contributo.acconto_previsto(p),
            "acconto_versato": contributo.acconto_versato(p),
            "congelato": contributo.preventivo_congelato(p),
            "presenze": p.presenze.select_related("area").order_by("area__ordine"),
            "attivita": p.attivita_giornaliere.order_by("data"),
            "pagamenti": p.pagamenti.order_by("data", "pk"),
            "consensi_chiesti": p.consensi_chiesti.select_related("prenotazione_esistente"),
            "consensi_mancanti": consensi.mancanti(p).exists(),
            "conversazione": conversazione,
            "storico": storico(p).select_related("utente")[:50],
            "conf": Configurazione.corrente(),
            "approva_form": ApprovaForm(),
            "rifiuta_form": RifiutaForm(),
            "annulla_form": MotivoForm(),
            "modifica_form": ModificaForm.per(p),
            "valorizza_form": ValorizzaForm(),
            "voce_form": VoceLiberaForm(),
            "quota_form": QuotaForm(),
            "orari_form": OrariForm(
                initial={
                    "arrivo": p.orario_arrivo_concordato,
                    "partenza": p.orario_partenza_concordato,
                }
            ),
            "pagamento_form": PagamentoForm(initial={"data_pagamento": timezone.localdate()}),
            "respingi_form": RespingiForm(),
            "risposta_form": RispostaForm(),
            "modificabile": p.stato in flusso.STATI_MODIFICABILI,
            "documenti": [(t, documenti.TIPI[t]) for t in documenti.disponibili(p)],
            "pagabile": p.stato in {Stato.APPROVATA, Stato.CONFERMATA, Stato.SVOLTA, Stato.CHIUSA},
            "preventivo_modificabile": permessi.e_amministrazione(request.user)
            and not contributo.preventivo_congelato(p),
            "annullabile": p.stato in flusso.STATI_ANNULLABILI,
        },
    )


def _azione_approva(request: HttpRequest, p: Prenotazione) -> None:
    form = ApprovaForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        flusso.approva(
            p,
            utente=request.user,
            concedi_esclusiva=d["concedi_esclusiva"],
            concedi_categoria=d["concedi_categoria"],
            acconto_centesimi=d["acconto"],
            deciso_da=d["deciso_da"],
            motivazione=d["motivazione"],
        )
        messages.success(request, "Prenotazione approvata.")
    else:
        raise ValidationError(form.errors.as_text())


def _azione_rifiuta(request: HttpRequest, p: Prenotazione) -> None:
    form = RifiutaForm(request.POST)
    if not form.is_valid():
        raise ValidationError("Indica chi ha deciso e la motivazione del rifiuto.")
    flusso.rifiuta(p, utente=request.user, **form.cleaned_data)
    messages.success(request, "Richiesta rifiutata.")


def _azione_annulla(request: HttpRequest, p: Prenotazione) -> None:
    form = MotivoForm(request.POST)
    form.is_valid()
    flusso.annulla(p, utente=request.user, motivo=form.cleaned_data.get("motivo", ""))
    messages.success(request, "Prenotazione annullata.")


def _azione_modifica(request: HttpRequest, p: Prenotazione) -> None:
    form = ModificaForm(request.POST)
    if not form.is_valid():
        raise ValidationError(form.errors.as_text())
    d = form.cleaned_data
    attivita = [(a.data, a.tipo, a.persone_previste) for a in p.attivita_giornaliere.all()]
    flusso.modifica(
        p,
        utente=request.user,
        arrivo=d["arrivo"],
        partenza=d["partenza"],
        presenze={Area.ACCANTONAMENTO: d["persone_acc"] or 0, Area.TENDE: d["persone_tende"] or 0},
        attivita=attivita,
        motivo=d["motivo"],
    )
    messages.success(request, "Prenotazione modificata.")


def _azione_valorizza(request: HttpRequest, p: Prenotazione) -> None:
    form = ValorizzaForm(request.POST)
    if not form.is_valid():
        raise ValidationError(form.errors.as_text())
    riga = get_object_or_404(RigaImporto, pk=form.cleaned_data["riga"], prenotazione=p)
    contributo.valorizza_riga(
        riga,
        prezzo_centesimi=form.cleaned_data["prezzo"],
        utente=request.user,
        deciso_da=form.cleaned_data["deciso_da"],
        motivazione=form.cleaned_data["motivazione"],
    )
    messages.success(request, "Voce valorizzata.")


def _azione_voce(request: HttpRequest, p: Prenotazione) -> None:
    form = VoceLiberaForm(request.POST)
    if not form.is_valid():
        raise ValidationError(form.errors.as_text())
    fase = Fase.CONSUNTIVO if request.POST.get("fase") == Fase.CONSUNTIVO else Fase.PREVENTIVO
    d = form.cleaned_data
    contributo.aggiungi_voce_libera(
        p,
        fase=fase,
        descrizione=d["descrizione"],
        quantita=d["quantita"],
        prezzo_centesimi=d["prezzo"],
        utente=request.user,
        deciso_da=d["deciso_da"],
        motivazione=d["motivazione"],
    )
    messages.success(request, "Voce aggiunta.")


def _azione_togli_voce(request: HttpRequest, p: Prenotazione) -> None:
    riga = get_object_or_404(RigaImporto, pk=request.POST.get("riga"), prenotazione=p)
    contributo.rimuovi_voce_libera(riga, utente=request.user)
    messages.success(request, "Voce tolta.")


def _azione_quota(request: HttpRequest, p: Prenotazione) -> None:
    form = QuotaForm(request.POST)
    if not form.is_valid():
        raise ValidationError(form.errors.as_text())
    fase = Fase.CONSUNTIVO if request.POST.get("fase") == Fase.CONSUNTIVO else Fase.PREVENTIVO
    contributo.modifica_quota(
        p,
        fase=fase,
        totale_centesimi=form.cleaned_data["totale"],
        utente=request.user,
        deciso_da=form.cleaned_data["deciso_da"],
        motivazione=form.cleaned_data["motivazione"],
    )
    messages.success(request, "Quota modificata.")


def _azione_orari(request: HttpRequest, p: Prenotazione) -> None:
    form = OrariForm(request.POST)
    if not form.is_valid():
        raise ValidationError(form.errors.as_text())
    flusso.imposta_orari(p, utente=request.user, **form.cleaned_data)
    messages.success(request, "Orari salvati.")


def _azione_pagamento(request: HttpRequest, p: Prenotazione) -> None:
    form = PagamentoForm(request.POST)
    if not form.is_valid():
        raise ValidationError(form.errors.as_text())
    d = form.cleaned_data
    flusso.registra_pagamento(
        p,
        utente=request.user,
        tipo=d["tipo"],
        importo_centesimi=d["importo"],
        data=d["data_pagamento"],
    )
    messages.success(request, "Pagamento registrato.")


def _pagamento_in_verifica(request: HttpRequest, p: Prenotazione) -> Pagamento:
    return get_object_or_404(
        Pagamento,
        pk=request.POST.get("pagamento"),
        prenotazione=p,
        stato=Pagamento.StatoPagamento.IN_VERIFICA,
    )


def _azione_verifica(request: HttpRequest, p: Prenotazione) -> None:
    flusso.verifica_ricevuta(_pagamento_in_verifica(request, p), utente=request.user)
    messages.success(request, "Acconto verificato: prenotazione confermata.")


def _azione_respingi(request: HttpRequest, p: Prenotazione) -> None:
    form = RespingiForm(request.POST)
    if not form.is_valid():
        raise ValidationError("Indica perché la ricevuta non va bene.")
    flusso.respingi_ricevuta(
        _pagamento_in_verifica(request, p),
        utente=request.user,
        motivazione=form.cleaned_data["motivazione"],
    )
    messages.success(request, "Ricevuta respinta: il gruppo ne caricherà un'altra.")


def _azione_conferma(request: HttpRequest, p: Prenotazione) -> None:
    flusso.conferma_senza_acconto(p, utente=request.user)
    messages.success(request, "Prenotazione confermata.")


def _azione_svolta(request: HttpRequest, p: Prenotazione) -> None:
    flusso.segna_svolta(p, utente=request.user)
    messages.success(request, "Prenotazione segnata come svolta.")


def _azione_rispondi(request: HttpRequest, p: Prenotazione) -> None:
    form = RispostaForm(request.POST)
    if not form.is_valid():
        raise ValidationError("Scrivi la risposta.")
    messaggi.invia(
        messaggi.con_gestione(p), utente=request.user, testo=form.cleaned_data["testo"], da=None
    )
    messages.success(request, "Risposta inviata.")


AZIONI: dict[str, Callable[[HttpRequest, Prenotazione], None]] = {
    "approva": _azione_approva,
    "rifiuta": _azione_rifiuta,
    "annulla": _azione_annulla,
    "modifica": _azione_modifica,
    "valorizza": _azione_valorizza,
    "voce": _azione_voce,
    "togli_voce": _azione_togli_voce,
    "quota": _azione_quota,
    "orari": _azione_orari,
    "pagamento": _azione_pagamento,
    "verifica": _azione_verifica,
    "respingi": _azione_respingi,
    "conferma": _azione_conferma,
    "svolta": _azione_svolta,
    "rispondi": _azione_rispondi,
}


@accesso()
@require_POST
def azione(request: HttpRequest, numero: str, nome: str) -> HttpResponse:
    """Esegue un'azione della scheda; i servizi controllano permessi e stato."""
    p = get_object_or_404(Prenotazione, numero=numero)
    esegui = AZIONI.get(nome)
    if esegui is None:
        raise Http404
    try:
        esegui(request, p)
    except (ValidationError, PermissionDenied) as errore:
        _errori(request, errore)
    destinazione = request.POST.get("torna") or _scheda(p)
    if not destinazione.startswith("/gestione/"):
        destinazione = _scheda(p)
    return redirect(destinazione)


@accesso(permessi.e_pattuglia)
def consuntivo(request: HttpRequest, numero: str) -> HttpResponse:
    p = get_object_or_404(Prenotazione, numero=numero)
    form = PresenzeEffettiveForm(p, request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            contributo.imposta_presenze_effettive(
                p, utente=request.user, presenze=form.presenze(), attivita=form.attivita()
            )
        except (ValidationError, PermissionDenied) as errore:
            _errori(request, errore)
        else:
            messages.success(request, "Consuntivo ricalcolato.")
            return redirect("gestione:consuntivo", numero=numero)
    riepilogo = contributo.riepilogo(p, Fase.CONSUNTIVO)
    return _render(
        request,
        "gestione/consuntivo.html",
        "consuntivi",
        {
            "p": p,
            "form": form,
            "consuntivo": riepilogo,
            "acconto_versato": contributo.acconto_versato(p),
            "saldo": contributo.saldo(p),
            "voce_form": VoceLiberaForm(),
            "quota_form": QuotaForm(),
            "valorizza_form": ValorizzaForm(),
            "pagamento_form": PagamentoForm(
                initial={"data": timezone.localdate(), "importo": None}
            ),
        },
    )


@accesso(permessi.e_pattuglia)
@require_POST
def chiudi(request: HttpRequest, numero: str) -> HttpResponse:
    p = get_object_or_404(Prenotazione, numero=numero)
    try:
        flusso.chiudi(p, utente=request.user)
    except (ValidationError, PermissionDenied) as errore:
        _errori(request, errore)
        return redirect("gestione:consuntivo", numero=numero)
    messages.success(request, "Consuntivo chiuso e inviato al gruppo.")
    return redirect(_scheda(p))


@accesso(permessi.e_amministrazione)
def nuova(request: HttpRequest) -> HttpResponse:
    """Prenotazione per conto della gestione (prioritarie, anche senza contatti e oltre
    l'orizzonte): nasce senza titolare."""
    conf = Configurazione.corrente()
    if conf.prenotazioni_bloccate:
        return _render(request, "gestione/nuova.html", "tutte", {"bloccate": conf.messaggio_blocco})
    form = NuovaPrioritariaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            p = flusso.invia_richiesta(
                utente=request.user,
                categoria=d["categoria"],
                arrivo=d["arrivo"],
                partenza=d["partenza"],
                presenze={
                    Area.ACCANTONAMENTO: d["persone_acc"] or 0,
                    Area.TENDE: d["persone_tende"] or 0,
                },
                gruppo=d["gruppo"],
                note=d["note"],
                da_gestione=True,
                deciso_da=d["deciso_da"],
                motivazione=d["motivazione"],
            )
        except ValidationError as errore:
            _errori(request, errore)
        else:
            messages.success(request, f"Prenotazione {p.numero} inserita: va approvata.")
            return redirect(_scheda(p))
    return _render(request, "gestione/nuova.html", "tutte", {"form": form})


# --- Calendario e accoglienza -----------------------------------------------------------


@accesso()
def calendario(request: HttpRequest) -> HttpResponse:
    """Calendario completo con i nomi dei gruppi (§8)."""
    primo = _mese(request.GET.get("mese"))
    ultimo = (primo + datetime.timedelta(days=32)).replace(day=1)
    giorni: dict[datetime.date, list[tuple[str, str, Prenotazione | None]]] = defaultdict(list)
    occupazioni = Occupazione.objects.filter(
        attiva=True, periodo__overlap=DateRange(primo, ultimo, "[)")
    ).select_related("area", "prenotazione", "blocco")
    for o in occupazioni:
        giorno = max(o.periodo.lower, primo)
        while giorno < min(o.periodo.upper, ultimo):
            if o.blocco:
                giorni[giorno].append((o.area.nome, f"Blocco: {o.blocco.motivo}", None))
            elif o.prenotazione:
                etichetta = o.prenotazione.gruppo or o.prenotazione.numero
                if o.tipo == Occupazione.Tipo.ESCLUSIVA:
                    etichetta += " (esclusiva)"
                giorni[giorno].append((o.area.nome, etichetta, o.prenotazione))
            giorno += datetime.timedelta(days=1)
    giornaliere = Prenotazione.objects.filter(
        stato__in=flusso.STATI_MODIFICABILI | {Stato.SVOLTA, Stato.CHIUSA},
        attivita_giornaliere__data__gte=primo,
        attivita_giornaliere__data__lt=ultimo,
    ).prefetch_related("attivita_giornaliere")
    for p in giornaliere.distinct():
        for att in p.attivita_giornaliere.all():
            if primo <= att.data < ultimo:
                giorni[att.data].append(("In giornata", p.gruppo or p.numero, p))
    elenco = []
    giorno = primo
    while giorno < ultimo:
        elenco.append((giorno, sorted(giorni.get(giorno, []), key=lambda v: v[0])))
        giorno += datetime.timedelta(days=1)
    precedente = (primo - datetime.timedelta(days=1)).replace(day=1)
    return _render(
        request,
        "gestione/calendario.html",
        "calendario",
        {
            "giorni": elenco,
            "titolo_mese": f"{MESI[primo.month]} {primo.year}",
            "precedente": f"{precedente:%Y-%m}",
            "successivo": f"{ultimo:%Y-%m}",
        },
    )


def _arrivi_e_partenze(
    dal: datetime.date, al: datetime.date
) -> list[tuple[datetime.date, list[dict[str, Any]]]]:
    """Arrivi, partenze e attività in giornata tra `dal` e `al` (D-26): solo prenotazioni
    approvate, confermate o in corso (le richieste in esame non si accolgono)."""
    stati = {Stato.APPROVATA, Stato.CONFERMATA, Stato.SVOLTA}
    prenotazioni = (
        Prenotazione.objects.filter(stato__in=stati)
        .filter(
            Q(arrivo__range=(dal, al))
            | Q(partenza__range=(dal, al))
            | Q(attivita_giornaliere__data__range=(dal, al))
        )
        .select_related("contatto", "capo_responsabile", "categoria")
        .prefetch_related("presenze__area", "attivita_giornaliere", "consensi_chiesti")
        .distinct()
    )
    conf = Configurazione.corrente()
    giornate: dict[datetime.date, list[dict[str, Any]]] = defaultdict(list)
    for p in prenotazioni:
        presenze = list(p.presenze.all())
        totale = contributo.riepilogo(p, Fase.CONSUNTIVO)
        totale = totale if totale.righe else contributo.riepilogo(p)
        versato = contributo.acconto_versato(p)
        base = {
            "p": p,
            "presenze": presenze,
            "versato": versato,
            "da_incassare": None if totale.totale is None else totale.totale - versato,
        }
        if presenze and dal <= p.arrivo <= al:
            giornate[p.arrivo].append(
                {
                    **base,
                    "movimento": "ARRIVA",
                    "orario": p.orario_arrivo_concordato or conf.orario_arrivo,
                    "concordato": bool(p.orario_arrivo_concordato),
                }
            )
        if presenze and dal <= p.partenza <= al:
            giornate[p.partenza].append(
                {
                    **base,
                    "movimento": "PARTE",
                    "orario": p.orario_partenza_concordato or conf.orario_partenza,
                    "concordato": bool(p.orario_partenza_concordato),
                }
            )
        for att in p.attivita_giornaliere.all():
            if dal <= att.data <= al:
                giornate[att.data].append(
                    {
                        **base,
                        "movimento": "IN GIORNATA",
                        "attivita": att,
                        "consensi": list(p.consensi_chiesti.all()),
                    }
                )
    return [(g, giornate[g]) for g in sorted(giornate)]


@accesso(permessi.e_pattuglia)
def arrivi(request: HttpRequest) -> HttpResponse:
    """Arrivi e partenze per l'accoglienza, pensata per il telefono (D-26, mockup 5)."""
    periodo = request.GET.get("periodo", "oggi")
    giorni = {"oggi": 0, "settimana": 6, "mese": 30}.get(periodo, 0)
    oggi = timezone.localdate()
    return _render(
        request,
        "gestione/arrivi.html",
        "arrivi",
        {
            "giornate": _arrivi_e_partenze(oggi, oggi + datetime.timedelta(days=giorni)),
            "periodo": periodo,
        },
    )


# --- Configurazione ---------------------------------------------------------------------


@accesso(permessi.e_amministrazione)
def blocchi(request: HttpRequest) -> HttpResponse:
    form = BloccoForm(request.POST or None)
    if request.method == "POST":
        if "elimina" in request.POST:
            blocco = get_object_or_404(BloccoTecnico, pk=request.POST["elimina"])
            elimina_blocco(blocco, utente=request.user)
            messages.success(request, "Blocco tolto: le date sono di nuovo libere.")
            return redirect("gestione:blocchi")
        if form.is_valid():
            try:
                crea_blocco(utente=request.user, **form.cleaned_data)
            except ValidationError as errore:
                _errori(request, errore)
            else:
                messages.success(request, "Date bloccate.")
                return redirect("gestione:blocchi")
    elenco = BloccoTecnico.objects.select_related("area").filter(
        al__gte=timezone.localdate() - datetime.timedelta(days=365)
    )
    return _render(request, "gestione/blocchi.html", "blocchi", {"form": form, "blocchi": elenco})


@accesso(permessi.e_amministrazione)
def configurazione(request: HttpRequest) -> HttpResponse:
    form = ConfigurazioneForm(request.POST or None, instance=Configurazione.corrente())
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Configurazione salvata.")
        return redirect("gestione:configurazione")
    contesto = {"form": form, "prenotazioni": Prenotazione.objects.count()}
    return _render(request, "gestione/configurazione.html", "configurazione", contesto)


@require_POST
@accesso(permessi.e_amministrazione)
def modalita_demo(request: HttpRequest) -> HttpResponse:
    """Attiva o termina la modalità demo (D-32)."""
    try:
        if request.POST.get("azione") == "attiva":
            demo.attiva(utente=request.user)
            messages.success(request, "Modalità demo attivata.")
        elif request.POST.get("conferma"):
            numero = demo.termina(utente=request.user)
            messages.success(request, f"Demo terminata: {numero} prenotazioni cancellate.")
        else:
            messages.error(request, "Conferma la cancellazione di tutte le prenotazioni.")
    except ValidationError as errore:
        _errori(request, errore)
    return redirect("gestione:configurazione")


@accesso(permessi.e_amministrazione)
def listini(request: HttpRequest) -> HttpResponse:
    form = VersioneForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            versione = nuova_versione(**form.cleaned_data)
        except ValidationError as errore:
            _errori(request, errore)
        else:
            messages.success(request, "Versione creata: controlla le voci prima che venga usata.")
            return redirect("gestione:versione", pk=versione.pk)
    elenco = Listino.objects.prefetch_related("versioni")
    return _render(request, "gestione/listini.html", "listini", {"listini": elenco, "form": form})


@accesso(permessi.e_amministrazione)
def versione(request: HttpRequest, pk: int) -> HttpResponse:
    v = get_object_or_404(VersioneListino.objects.select_related("listino"), pk=pk)
    in_uso = v.in_uso()
    azione = request.POST.get("azione", "voci") if request.method == "POST" else None
    # Copia a parte: con dati non validi il titolo della pagina resta quello salvato
    copia = VersioneListino.objects.get(pk=pk)
    dati = DatiVersioneForm(request.POST if azione == "dati" else None, instance=copia)
    formset = VociFormSet(request.POST if azione == "voci" else None, instance=v)
    if azione and in_uso:
        messages.error(request, "Versione già usata da una prenotazione: non si modifica.")
    elif azione == "elimina":
        v.delete()
        messages.success(request, f"Versione {v} eliminata.")
        return redirect("gestione:listini")
    elif azione == "dati" and dati.is_valid():
        dati.save()
        messages.success(request, "Nome e date salvati.")
        return redirect("gestione:versione", pk=pk)
    elif azione == "voci" and formset.is_valid():
        try:
            formset.save()
        except ValidationError as errore:
            _errori(request, errore)
        else:
            messages.success(request, "Voci salvate.")
            return redirect("gestione:versione", pk=pk)
    return _render(
        request,
        "gestione/versione.html",
        "listini",
        {"v": v, "dati": dati, "formset": formset, "in_uso": in_uso},
    )


@accesso(permessi.e_amministrazione)
def categorie(request: HttpRequest) -> HttpResponse:
    form = CategoriaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        categoria = form.save()
        messages.success(request, f"Categoria «{categoria}» creata.")
        return redirect("gestione:categorie")
    elenco = Categoria.objects.select_related("listino_default").annotate(
        usata=Count("prenotazioni")
    )
    return _render(
        request, "gestione/categorie.html", "categorie", {"categorie": elenco, "form": form}
    )


@accesso(permessi.e_amministrazione)
def categoria(request: HttpRequest, pk: int) -> HttpResponse:
    c = get_object_or_404(Categoria, pk=pk)
    usata = c.prenotazioni.exists()
    if request.method == "POST" and "elimina" in request.POST:
        if usata:
            messages.error(request, "Categoria usata da almeno una prenotazione: non si elimina.")
        else:
            c.delete()
            messages.success(request, f"Categoria «{c}» eliminata.")
            return redirect("gestione:categorie")
    form = CategoriaForm(request.POST or None, instance=c)
    if request.method == "POST" and "elimina" not in request.POST and form.is_valid():
        form.save()
        messages.success(request, "Categoria salvata.")
        return redirect("gestione:categorie")
    return _render(
        request, "gestione/categoria.html", "categorie", {"c": c, "form": form, "usata": usata}
    )


@accesso(permessi.assegna_ruoli)
def utenti(request: HttpRequest) -> HttpResponse:
    """La segreteria assegna i ruoli locali (P-12); quelli da Sestante non si toccano qui."""
    form = NominaForm(request.POST or None)
    if request.method == "POST":
        if "revoca" in request.POST:
            n = get_object_or_404(Nomina, pk=request.POST["revoca"], da_sso=False, attiva=True)
            revoca(n.utente, n.ruolo)
            messages.success(request, f"Ruolo {n.get_ruolo_display()} revocato a {n.utente}.")
            return redirect("gestione:utenti")
        if form.is_valid():
            utente = User.objects.filter(email__iexact=form.cleaned_data["email"]).first()
            if utente is None:
                messages.error(
                    request, "Nessun utente con questa email: deve prima entrare in Tana."
                )
            else:
                nomina(utente, form.cleaned_data["ruolo"], assegnata_da=request.user)
                messages.success(request, f"Ruolo assegnato a {utente}.")
                return redirect("gestione:utenti")
    nomine = (
        Nomina.objects.filter(attiva=True)
        .select_related("utente")
        .order_by("ruolo", "utente__email")
    )
    return _render(
        request, "gestione/utenti.html", "utenti", {"form": form, "nomine": nomine, "ruoli": Ruolo}
    )


# --- Report -----------------------------------------------------------------------------


@accesso()
def statistiche_anno(request: HttpRequest) -> HttpResponse:
    oggi = timezone.localdate()
    try:
        anno = int(request.GET.get("anno", oggi.year))
    except ValueError:
        anno = oggi.year
    s = statistiche.calcola(anno)
    mesi = statistiche.MESI
    presenze = grafici.barre(
        mesi,
        [
            grafici.Serie("previste", [p for _, p, _ in s.presenze_mensili]),
            grafici.Serie("effettive", [e for _, _, e in s.presenze_mensili]),
        ],
        titolo=f"Presenze per mese nel {anno}, previste ed effettive",
    )
    occupazione = {
        area: grafici.barre(
            mesi,
            [grafici.Serie("occupazione", [100 * n / notti for _, n, notti in valori], colore=2)],
            titolo=f"Occupazione per mese nel {anno}: {area}",
            formato=lambda v: f"{v:.0f}%",
            massimo=100,
            larghezza=420,
        )
        for area, valori in s.occupazione.items()
    }
    return _render(
        request,
        "gestione/statistiche.html",
        "statistiche",
        {
            "s": s,
            "grafico_presenze": presenze,
            "grafici_occupazione": occupazione,
            "mesi": statistiche.MESI,
            "giorni_comodato": statistiche.GIORNI_COMODATO,
            "anni": range(oggi.year + 1, 2021, -1),
        },
    )


@accesso()
def esporta(request: HttpRequest) -> HttpResponse:
    oggi = timezone.localdate()
    form = ExportForm(
        request.GET or None,
        initial={"dal": oggi.replace(month=1, day=1), "al": oggi.replace(month=12, day=31)},
    )
    if request.GET and form.is_valid():
        d = form.cleaned_data
        intestazione, righe = (
            export.prenotazioni if d["contenuto"] == "prenotazioni" else export.incassi
        )(d["dal"], d["al"])
        nome = f"tana-{d['contenuto']}-{d['dal']:%Y%m%d}-{d['al']:%Y%m%d}"
        if d["formato"] == "xlsx":
            risposta = HttpResponse(
                export.in_excel(d["contenuto"], intestazione, righe),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            risposta["Content-Disposition"] = f'attachment; filename="{nome}.xlsx"'
        else:
            risposta = HttpResponse(
                export.in_csv(intestazione, righe), content_type="text/csv; charset=utf-8"
            )
            risposta["Content-Disposition"] = f'attachment; filename="{nome}.csv"'
        return risposta
    return _render(request, "gestione/export.html", "export", {"form": form})


# --- Aggiornamento dal web (P-20) -------------------------------------------------------


@accesso(permessi.e_amministrazione)
def aggiornamenti(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        azione_richiesta = request.POST.get("azione")
        try:
            if azione_richiesta == "controlla":
                release = servizi_aggiornamenti.controlla_ultima_release()
                if release.errore:
                    messages.warning(request, f"GitHub non ha risposto: {release.errore}")
            elif azione_richiesta == "aggiorna":
                if not servizi_aggiornamenti.autenticazione_recente(request):
                    messages.error(
                        request,
                        "Per aggiornare il server conferma la tua identità: rientra (o usa "
                        "«Conferma la tua identità») e riprova entro 5 minuti.",
                    )
                else:
                    servizi_aggiornamenti.crea_richiesta(
                        request.user, request.POST.get("versione", "")
                    )
                    messages.success(
                        request, "Aggiornamento richiesto: il server lo avvia entro pochi secondi."
                    )
            elif azione_richiesta == "annulla":
                servizi_aggiornamenti.annulla_richiesta(request.user)
                messages.success(request, "Richiesta annullata.")
        except ValidationError as errore:
            _errori(request, errore)
        except (
            servizi_aggiornamenti.RichiestaInCorso,
            servizi_aggiornamenti.CartellaNonScrivibile,
        ) as errore:
            messages.error(request, str(errore))
        return redirect("gestione:aggiornamenti")
    in_corso = servizi_aggiornamenti.sincronizza_storico()
    return _render(
        request,
        "gestione/aggiornamenti.html",
        "aggiornamenti",
        {
            "installata": servizi_aggiornamenti.versione_installata(),
            "release": ReleaseGitHub.corrente(),
            "disponibile": servizi_aggiornamenti.aggiornamento_disponibile(),
            "in_corso": in_corso if in_corso and in_corso.aperta else None,
            "ultima": in_corso,
            "storico": RichiestaAggiornamento.objects.all()[:20],
            "recente": servizi_aggiornamenti.autenticazione_recente(request),
        },
    )
