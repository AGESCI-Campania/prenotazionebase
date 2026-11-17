"""Area del richiedente (§8, mockup 2 e 3): nuova richiesta, le mie prenotazioni, dettaglio.

Le viste raccolgono i dati e chiamano i servizi; permessi e regole stanno lì.
"""

import mimetypes
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
    QueryDict,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from tana.accounts import permessi
from tana.base.models import Area, Configurazione
from tana.core.pdf import PdfNonDisponibile
from tana.listini.models import Categoria

from . import consensi, contributo, demo, disponibilita, documenti, flusso, messaggi
from .forms import (
    AnnullaForm,
    MessaggioForm,
    PassoInvio,
    PassoRichiedente,
    PassoSoggiorno,
    RicevutaForm,
)
from .models import (
    Contatto,
    Pagamento,
    Prenotazione,
    RichiestaConsenso,
    RichiestaTelefono,
    Stato,
)

CHIAVE_SESSIONE = "nuova_richiesta"
PASSI = ["Richiedente", "Soggiorno", "Riepilogo e invio"]
TAPPE = ["Richiesta", "Approvata", "Acconto", "Confermata", "Soggiorno", "Consuntivo"]


def _mia(request: HttpRequest, numero: str) -> Prenotazione:
    """Prenotazione del richiedente collegato (404 per le altre: niente enumerazione)."""
    return get_object_or_404(Prenotazione, numero=numero, richiedente_id=request.user.pk)


def _errori(request: HttpRequest, errore: ValidationError) -> None:
    for testo in errore.messages:
        messages.error(request, testo)


# --- Elenco e dettaglio -----------------------------------------------------------------


@login_required
def elenco(request: HttpRequest) -> HttpResponse:
    prenotazioni = (
        Prenotazione.objects.filter(richiedente_id=request.user.pk)
        .select_related("categoria")
        .order_by("-arrivo")
    )
    return render(
        request,
        "prenotazioni/elenco.html",
        {
            "sezione": "prenotazioni",
            "prenotazioni": prenotazioni,
            "consensi": consensi.da_rispondere(request.user),
        },
    )


def _tappa(prenotazione: Prenotazione) -> int:
    """Tappa corrente della linea del mockup 3 (0: stato fuori dal percorso)."""
    return {
        Stato.RICHIESTA: 1,
        Stato.APPROVATA: 3 if prenotazione.acconto_centesimi else 2,
        Stato.CONFERMATA: 4,
        Stato.SVOLTA: 5,
        Stato.CHIUSA: 6,
    }.get(Stato(prenotazione.stato), 0)


@login_required
def dettaglio(request: HttpRequest, numero: str) -> HttpResponse:
    prenotazione = _mia(request, numero)
    vicini = list(messaggi.gruppi_vicini(prenotazione).select_related("contatto"))
    con = request.GET.get("con", "gestione")
    altra = next((v for v in vicini if v.numero == con), None)
    conversazione = (
        messaggi.tra_gruppi(prenotazione, altra) if altra else messaggi.con_gestione(prenotazione)
    )
    messaggi.segna_letti(conversazione, lettore=prenotazione)
    telefoni_chiesti = {r.a_id: r for r in prenotazione.telefoni_chiesti.all()}
    preventivo = contributo.riepilogo(prenotazione, contributo.Fase.PREVENTIVO)
    consuntivo = contributo.riepilogo(prenotazione, contributo.Fase.CONSUNTIVO)
    conf = Configurazione.corrente()
    contesto: dict[str, Any] = {
        "sezione": "prenotazioni",
        "p": prenotazione,
        "tappe": TAPPE,
        "tappa": _tappa(prenotazione),
        "importi_titolo": "Consuntivo" if consuntivo.righe else "Preventivo",
        "importi": consuntivo if consuntivo.righe else preventivo,
        "presenze": prenotazione.presenze.select_related("area").order_by("area__ordine"),
        "attivita": prenotazione.attivita_giornaliere.order_by("data"),
        "pagamenti": prenotazione.pagamenti.order_by("data", "pk"),
        "ricevuta_in_verifica": prenotazione.pagamenti.filter(
            tipo=Pagamento.Tipo.ACCONTO, stato=Pagamento.StatoPagamento.IN_VERIFICA
        ).exists(),
        "conf": conf,
        "causale": conf.causale(prenotazione.numero, prenotazione.gruppo),
        "ricevuta_form": RicevutaForm(),
        "annulla_form": AnnullaForm(),
        "messaggio_form": MessaggioForm(),
        "annullabile": prenotazione.stato in flusso.STATI_ANNULLABILI,
        "consensi_chiesti": prenotazione.consensi_chiesti.select_related("prenotazione_esistente"),
        "consensi_ricevuti": prenotazione.consensi_ricevuti.filter(
            stato=RichiestaConsenso.StatoConsenso.IN_ATTESA, richiesta__stato=Stato.RICHIESTA
        ).select_related("richiesta"),
        "vicini": [(v, telefoni_chiesti.get(v.pk)) for v in vicini],
        "conversazione": conversazione,
        "con": altra.numero if altra else "gestione",
        "altra": altra,
        "telefoni_da_autorizzare": prenotazione.telefoni_richiesti.filter(
            stato=RichiestaTelefono.StatoRichiesta.IN_ATTESA
        ).select_related("da"),
        "telefoni_visibili": messaggi.telefoni_visibili(prenotazione),
        "documenti": [(t, documenti.TIPI[t]) for t in documenti.disponibili(prenotazione)],
    }
    return render(request, "prenotazioni/dettaglio.html", contesto)


@login_required
@require_POST
def carica_ricevuta(request: HttpRequest, numero: str) -> HttpResponse:
    prenotazione = _mia(request, numero)
    form = RicevutaForm(request.POST, request.FILES)
    if not form.is_valid():
        for errori in form.errors.values():
            for testo in errori:
                messages.error(request, str(testo))
        return redirect(prenotazione_url(prenotazione))
    try:
        flusso.carica_ricevuta(
            prenotazione, utente=request.user, ricevuta=form.cleaned_data["ricevuta"]
        )
    except ValidationError as errore:
        _errori(request, errore)
    else:
        messages.success(request, "Ricevuta caricata: la Pattuglia la verifica a breve.")
    return redirect(prenotazione_url(prenotazione))


@login_required
@require_POST
def annulla(request: HttpRequest, numero: str) -> HttpResponse:
    prenotazione = _mia(request, numero)
    form = AnnullaForm(request.POST)
    form.is_valid()
    try:
        flusso.annulla(
            prenotazione, utente=request.user, motivo=form.cleaned_data.get("motivo", "")
        )
    except ValidationError as errore:
        _errori(request, errore)
    else:
        messages.success(request, "Prenotazione annullata: le date sono di nuovo libere.")
    return redirect(prenotazione_url(prenotazione))


@login_required
@require_POST
def scrivi(request: HttpRequest, numero: str) -> HttpResponse:
    prenotazione = _mia(request, numero)
    con = request.POST.get("con", "gestione")
    form = MessaggioForm(request.POST)
    try:
        if con == "gestione":
            conversazione = messaggi.con_gestione(prenotazione)
        else:
            altra = get_object_or_404(Prenotazione, numero=con)
            conversazione = messaggi.tra_gruppi(prenotazione, altra)
        if form.is_valid():
            messaggi.invia(
                conversazione,
                utente=request.user,
                testo=form.cleaned_data["testo"],
                da=prenotazione,
            )
            messages.success(request, "Messaggio inviato.")
        else:
            messages.error(request, "Scrivi il messaggio.")
    except (ValidationError, PermissionDenied) as errore:
        messages.error(request, " ".join(getattr(errore, "messages", [str(errore)])))
    return redirect(f"{prenotazione_url(prenotazione)}?{urlencode({'con': con})}#messaggi")


@login_required
@require_POST
def chiedi_telefono(request: HttpRequest, numero: str, altro: str) -> HttpResponse:
    prenotazione = _mia(request, numero)
    altra = get_object_or_404(Prenotazione, numero=altro)
    try:
        messaggi.chiedi_telefono(prenotazione, altra, utente=request.user)
    except PermissionDenied as errore:
        messages.error(request, str(errore))
    else:
        messages.success(
            request, "Richiesta inviata: il telefono compare qui se il referente lo autorizza."
        )
    return redirect(prenotazione_url(prenotazione))


@login_required
@require_POST
def rispondi_telefono(request: HttpRequest, pk: int) -> HttpResponse:
    richiesta = get_object_or_404(RichiestaTelefono, pk=pk, a__richiedente=request.user)
    try:
        messaggi.rispondi_telefono(
            richiesta, utente=request.user, autorizza=request.POST.get("autorizza") == "1"
        )
    except ValidationError as errore:
        _errori(request, errore)
    return redirect(prenotazione_url(richiesta.a))


@login_required
@require_POST
def rispondi_consenso(request: HttpRequest, pk: int) -> HttpResponse:
    domanda = get_object_or_404(RichiestaConsenso, pk=pk)
    try:
        consensi.rispondi(
            domanda, utente=request.user, concesso=request.POST.get("concesso") == "1"
        )
    except PermissionDenied:
        raise Http404 from None
    except ValidationError as errore:
        _errori(request, errore)
    else:
        messages.success(request, "Risposta registrata.")
    return redirect(prenotazione_url(domanda.prenotazione_esistente))


def ricevuta(request: HttpRequest, numero: str, pk: int) -> HttpResponseBase:
    """Ricevuta privata (P-14): solo il titolare o la Pattuglia; in produzione la serve nginx
    con X-Accel-Redirect dalla location `internal` /protetti/."""
    if not request.user.is_authenticated:
        raise Http404
    pagamento = get_object_or_404(
        Pagamento.objects.select_related("prenotazione"), pk=pk, prenotazione__numero=numero
    )
    if (
        not (
            permessi.e_titolare(request.user, pagamento.prenotazione)
            or permessi.e_pattuglia(request.user)
        )
        or not pagamento.ricevuta
    ):
        raise Http404
    nome = pagamento.ricevuta.name or ""
    if settings.PRIVATI_X_ACCEL:
        tipo, _ = mimetypes.guess_type(nome)
        risposta = HttpResponse(content_type=tipo or "application/octet-stream")
        risposta["X-Accel-Redirect"] = f"/protetti/{nome}"
        risposta["Content-Disposition"] = f'inline; filename="{nome.rsplit("/", 1)[-1]}"'
        return risposta
    return FileResponse(pagamento.ricevuta.open("rb"), filename=nome.rsplit("/", 1)[-1])


def documento(request: HttpRequest, numero: str, tipo: str) -> HttpResponse:
    """PDF della prenotazione (D-19): al titolare e a chi vede tutte le prenotazioni."""
    if not request.user.is_authenticated:
        raise Http404
    prenotazione = get_object_or_404(Prenotazione, numero=numero)
    if not (
        permessi.e_titolare(request.user, prenotazione)
        or permessi.vede_tutte_le_prenotazioni(request.user)
    ) or tipo not in documenti.disponibili(prenotazione):
        raise Http404
    try:
        contenuto = documenti.pdf(prenotazione, tipo)
    except PdfNonDisponibile:
        return HttpResponse("PDF non disponibile in questo momento.", status=503)
    risposta = HttpResponse(contenuto, content_type="application/pdf")
    risposta["Content-Disposition"] = (
        f'inline; filename="{documenti.nome_file(prenotazione, tipo)}"'
    )
    return risposta


def prenotazione_url(prenotazione: Prenotazione) -> str:
    return reverse("prenotazioni:dettaglio", kwargs={"numero": prenotazione.numero})


# --- Nuova richiesta in tre passi -------------------------------------------------------


def _dati(request: HttpRequest, passo: str) -> QueryDict | None:
    salvati = request.session.get(CHIAVE_SESSIONE, {}).get(passo)
    if salvati is None:
        return None
    dati = QueryDict(mutable=True)
    for chiave, valori in salvati.items():
        dati.setlist(chiave, valori)
    return dati


def _salva(request: HttpRequest, passo: str, dati: QueryDict) -> None:
    sessione = request.session.get(CHIAVE_SESSIONE, {})
    sessione[passo] = {k: v for k, v in dati.lists() if k != "csrfmiddlewaretoken"}
    request.session[CHIAVE_SESSIONE] = sessione


def _soggiorno(richiedente: dict[str, Any], soggiorno: dict[str, Any]) -> contributo.Soggiorno:
    categoria: Categoria = richiedente["categoria"]
    aree = {a.codice: a for a in Area.objects.filter(codice__in=soggiorno["presenze"])}
    return contributo.Soggiorno(
        categoria=categoria,
        arrivo=soggiorno["arrivo"],
        partenza=soggiorno["partenza"],
        presenze=[(aree[c], n) for c, n in soggiorno["presenze"].items()],
        attivita=soggiorno["attivita"],
        categoria_prioritaria_richiesta=categoria.prioritaria,
    )


def _preventivo(richiedente: dict[str, Any], soggiorno: dict[str, Any]) -> dict[str, Any]:
    """Preventivo e disponibilità di una richiesta non ancora inviata."""
    righe = contributo.simula(_soggiorno(richiedente, soggiorno))
    totale = None if any(r.importo is None for r in righe) else sum(r.importo or 0 for r in righe)
    esito = disponibilita.verifica_date(
        soggiorno["arrivo"], soggiorno["partenza"], list(soggiorno["presenze"])
    )
    presenti = set()
    for data, _, _ in soggiorno["attivita"]:
        presenti |= {p.gruppo or p.numero for p in consensi.presenti(data)}
    return {
        "righe": righe,
        "totale": totale,
        "acconto": contributo.calcola_acconto(
            totale,
            soggiorno["arrivo"],
            soggiorno["partenza"],
            soggiorno=bool(soggiorno["presenze"]),
        ),
        "esito": esito,
        "serve_consenso": bool(presenti),
        "listino": contributo.listino_applicato(_soggiorno(richiedente, soggiorno)),  # type: ignore[arg-type]
        "conf": Configurazione.corrente(),
    }


@login_required
def nuova(request: HttpRequest, passo: int = 1) -> HttpResponse:
    if passo not in (1, 2, 3):
        raise Http404
    conf = Configurazione.corrente()
    bloccate = conf.messaggio_blocco if conf.prenotazioni_bloccate else ""  # D-31
    if not bloccate and not demo.puo_prenotare(request.user):  # D-32
        bloccate = demo.MESSAGGIO_DEMO
    if bloccate:
        return render(
            request, "prenotazioni/nuova.html", {"sezione": "prenotazioni", "bloccate": bloccate}
        )
    richiedente = PassoRichiedente(_dati(request, "1")) if _dati(request, "1") else None
    if passo > 1 and not (richiedente and richiedente.is_valid()):
        return redirect("prenotazioni:nuova")
    soggiorno = PassoSoggiorno(_dati(request, "2")) if _dati(request, "2") else None
    if passo > 2 and not (soggiorno and soggiorno.is_valid()):
        return redirect("prenotazioni:nuova_passo", passo=2)

    if passo == 1:
        form: Any = PassoRichiedente(
            request.POST or None, initial={"referente_email": getattr(request.user, "email", "")}
        )
        if richiedente is not None and request.method == "GET":
            form = richiedente
    elif passo == 2:
        form = PassoSoggiorno(request.POST or None)
        if soggiorno is not None and request.method == "GET":
            form = soggiorno
    else:
        form = PassoInvio(request.POST or None)

    if request.method == "POST" and form.is_valid():
        if passo < 3:
            _salva(request, str(passo), request.POST)
            return redirect("prenotazioni:nuova_passo", passo=passo + 1)
        assert richiedente is not None and soggiorno is not None
        try:
            prenotazione = _invia(
                request, richiedente.cleaned_data, soggiorno.cleaned_data, form.cleaned_data
            )
        except ValidationError as errore:
            _errori(request, errore)
        else:
            request.session.pop(CHIAVE_SESSIONE, None)
            messages.success(
                request,
                "Richiesta inviata: le date sono riservate a te mentre la Pattuglia la esamina. "
                "Ti abbiamo mandato un'email di riepilogo.",
            )
            return redirect(prenotazione_url(prenotazione))

    contesto: dict[str, Any] = {
        "sezione": "prenotazioni",
        "form": form,
        "passo": passo,
        "passi": PASSI,
    }
    if passo == 3:
        assert richiedente is not None and soggiorno is not None
        contesto["richiedente"] = richiedente.cleaned_data
        contesto["soggiorno"] = soggiorno.cleaned_data
        contesto["aree"] = {a.codice: a for a in Area.objects.all()}
        try:
            contesto["preventivo"] = _preventivo(richiedente.cleaned_data, soggiorno.cleaned_data)
        except ValidationError as errore:
            _errori(request, errore)
    return render(request, "prenotazioni/nuova.html", contesto)


@login_required
@require_POST
def anteprima(request: HttpRequest) -> HttpResponse:
    """Preventivo in tempo reale del passo 2 (frammento HTML)."""
    richiedente = PassoRichiedente(_dati(request, "1")) if _dati(request, "1") else None
    soggiorno = PassoSoggiorno(request.POST)
    if not (richiedente and richiedente.is_valid()) or not soggiorno.is_valid():
        return render(request, "prenotazioni/_preventivo.html", {"incompleto": True})
    try:
        preventivo = _preventivo(richiedente.cleaned_data, soggiorno.cleaned_data)
    except ValidationError as errore:
        return render(request, "prenotazioni/_preventivo.html", {"errori": errore.messages})
    return render(request, "prenotazioni/_preventivo.html", {"preventivo": preventivo})


@transaction.atomic
def _invia(
    request: HttpRequest,
    richiedente: dict[str, Any],
    soggiorno: dict[str, Any],
    invio: dict[str, Any],
) -> Prenotazione:
    referente = Contatto.objects.create(
        nome=richiedente["referente_nome"],
        email=richiedente["referente_email"],
        telefono=richiedente["referente_telefono"],
        organizzazione=richiedente["gruppo"],
    )
    capo = None
    if richiedente.get("capo_nome"):
        capo = Contatto.objects.create(
            nome=richiedente["capo_nome"],
            email=richiedente.get("capo_email") or "",
            telefono=richiedente.get("capo_telefono") or "",
            organizzazione=richiedente["gruppo"],
        )
    return flusso.invia_richiesta(
        utente=request.user,
        categoria=richiedente["categoria"],
        arrivo=soggiorno["arrivo"],
        partenza=soggiorno["partenza"],
        presenze=soggiorno["presenze"],
        attivita=soggiorno["attivita"],
        contatto=referente,
        capo_responsabile=capo,
        gruppo=richiedente["gruppo"],
        specifica_categoria=richiedente.get("specifica_categoria") or "",
        unita=richiedente.get("unita") or [],
        esclusiva_richiesta=soggiorno.get("esclusiva_richiesta", False),
        note=invio.get("note", ""),
    )
