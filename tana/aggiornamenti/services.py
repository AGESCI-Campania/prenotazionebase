"""Aggiornamento del server dal web (P-20), solo per l'amministrazione.

Django scrive SOLO `richiesta.json` nella cartella `settings.AGGIORNAMENTI_DIR` (bind mount di
`/opt/prenotazionebase/aggiornamenti`); sull'host la unit `prenotazionebase-aggiorna.path` la vede
e lancia `scripts/esegui-aggiornamento.sh`, che la sposta in `in-corso.json`, esegue
`scripts/aggiorna.sh --si --stato-file …` e lascia l'esito in `stato.json`. Il container non
ha mai accesso a Docker. Contratto dei file: lo stesso di Plancia 3.0 (docs/installazione.md).
"""

import contextlib
import datetime
import json
import logging
import os
import re
import tempfile
import time
import tomllib
import urllib.request
from functools import cache
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import STATI_APERTI, ReleaseGitHub, RichiestaAggiornamento, StatoRichiesta

log = logging.getLogger("tana.aggiornamenti")

URL_ULTIMA_RELEASE = "https://api.github.com/repos/AGESCI-Campania/prenotazionebase/releases/latest"
TIMEOUT_GITHUB = 10
FILE_RICHIESTA = "richiesta.json"
FILE_IN_CORSO = "in-corso.json"
FILE_STATO = "stato.json"
MAX_RIGHE_LOG = 200
CONTROLLO_OGNI = datetime.timedelta(hours=24)
_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
ESITI = {
    "completato": StatoRichiesta.COMPLETATO,
    "fallito": StatoRichiesta.FALLITO,
    "annullato": StatoRichiesta.ANNULLATO,
}


class RichiestaInCorso(Exception):
    """C'è già un aggiornamento in attesa o in corso."""


class CartellaNonScrivibile(Exception):
    """La cartella degli aggiornamenti manca o non è scrivibile."""


# --- Versioni ---------------------------------------------------------------------------


@cache
def versione_installata() -> str:
    """Versione `X.Y.Z` di pyproject.toml (cambia solo con una nuova immagine)."""
    try:
        with open(settings.BASE_DIR / "pyproject.toml", "rb") as f:
            return str(tomllib.load(f).get("project", {}).get("version") or "?")
    except OSError, tomllib.TOMLDecodeError:
        return "?"


def tag_valido(tag: str) -> bool:
    return bool(_TAG.match(tag or ""))


def _tupla(versione: str) -> tuple[int, int, int] | None:
    v = versione or ""
    m = _TAG.match(v if v.startswith("v") else f"v{v}")
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def e_successiva(tag: str, installata: str) -> bool:
    nuova, attuale = _tupla(tag), _tupla(installata)
    return bool(nuova and (attuale is None or nuova > attuale))


def aggiornamento_disponibile() -> bool:
    release = ReleaseGitHub.corrente()
    return tag_valido(release.versione) and e_successiva(release.versione, versione_installata())


# --- Release su GitHub ------------------------------------------------------------------


def controlla_ultima_release() -> ReleaseGitHub:
    """Legge l'ultima release dalla API di GitHub (repo pubblico, senza token). Non solleva
    mai eccezioni: l'errore si salva e si mostra nella pagina."""
    release = ReleaseGitHub.corrente()
    richiesta = urllib.request.Request(
        URL_ULTIMA_RELEASE,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"tana/{versione_installata()}",
        },
    )
    try:
        with urllib.request.urlopen(richiesta, timeout=TIMEOUT_GITHUB) as risposta:
            dati = json.load(risposta)
        release.versione = str(dati.get("tag_name") or "")[:40]
        release.nome = str(dati.get("name") or "")[:200]
        release.note = str(dati.get("body") or "")
        release.pubblicata_il = parse_datetime(dati.get("published_at") or "")
        release.url = str(dati.get("html_url") or "")[:500]
        release.errore = ""
    except Exception as errore:  # rete, 404 (nessuna release), JSON non valido
        log.warning("Controllo dell'ultima release non riuscito: %s", errore)
        release.errore = (str(errore) or errore.__class__.__name__)[:500]
    release.controllata_il = timezone.now()
    release.save()
    return release


def controllo_periodico() -> None:
    """Servizio scheduler: al massimo un controllo al giorno."""
    if not settings.AGGIORNAMENTI_CONTROLLO_RELEASE:
        return
    release = ReleaseGitHub.corrente()
    if release.controllata_il is None or timezone.now() - release.controllata_il > CONTROLLO_OGNI:
        controlla_ultima_release()


# --- File di scambio con l'host ---------------------------------------------------------


def cartella() -> Path:
    return Path(settings.AGGIORNAMENTI_DIR)


def _scrivi_json(percorso: Path, dati: dict[str, Any]) -> None:
    """Scrittura atomica: file temporaneo nella stessa cartella, poi rename."""
    fd, tmp = tempfile.mkstemp(dir=percorso.parent, prefix=f".{percorso.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dati, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o640)
        os.replace(tmp, percorso)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def leggi_stato() -> dict[str, Any] | None:
    try:
        with open(cartella() / FILE_STATO, encoding="utf-8") as f:
            dati = json.load(f)
    except OSError, ValueError:
        return None
    return dati if isinstance(dati, dict) else None


# --- Riautenticazione -------------------------------------------------------------------


def autenticazione_recente(request: Any) -> bool:
    """Login o riautenticazione allauth (password, MFA, Sestante) più recente del limite di
    allauth (5 minuti)."""
    from allauth.account import app_settings
    from allauth.account.internal.flows.login import get_authentication_records

    adesso = time.time()
    return any(
        isinstance(r, dict)
        and adesso - float(r.get("at") or 0) < app_settings.REAUTHENTICATION_TIMEOUT
        for r in get_authentication_records(request, request.user)
    )


# --- Richieste --------------------------------------------------------------------------


def richiesta_aperta() -> RichiestaAggiornamento | None:
    return RichiestaAggiornamento.objects.filter(stato__in=STATI_APERTI).first()


def crea_richiesta(utente: Any, versione: str) -> RichiestaAggiornamento:
    """Registra la richiesta e scrive `richiesta.json` per l'host: solo l'ultima release nota,
    successiva all'installata, con nessun altro aggiornamento aperto."""
    versione = (versione or "").strip()
    if not tag_valido(versione):
        raise ValidationError("La versione deve essere un tag nel formato vX.Y.Z.")
    installata = versione_installata()
    with transaction.atomic():
        release = ReleaseGitHub.objects.select_for_update().filter(pk=1).first()
        if release is None or release.versione != versione:
            raise ValidationError("La versione richiesta non è l'ultima release disponibile.")
        if not e_successiva(versione, installata):
            raise ValidationError(
                f"La {versione} non è successiva alla versione installata ({installata})."
            )
        if (
            richiesta_aperta()
            or (cartella() / FILE_IN_CORSO).exists()
            or (cartella() / FILE_RICHIESTA).exists()
        ):
            raise RichiestaInCorso("C'è già un aggiornamento in attesa o in corso.")
        richiesta = RichiestaAggiornamento.objects.create(
            versione=versione,
            versione_partenza=installata,
            richiesta_da=utente,
            richiesta_da_email=utente.email or "",
            messaggio="In attesa che il server la prenda in carico.",
        )
        try:
            cartella().mkdir(parents=True, exist_ok=True)
            _scrivi_json(
                cartella() / FILE_RICHIESTA,
                {
                    "id": richiesta.pk,
                    "versione": versione,
                    "richiesta_da": richiesta.richiesta_da_email,
                    "richiesta_at": richiesta.richiesta_il.isoformat(),
                },
            )
        except OSError as errore:
            log.error("Richiesta di aggiornamento non scritta: %s", errore)
            transaction.set_rollback(True)
            raise CartellaNonScrivibile(
                "La cartella degli aggiornamenti non è scrivibile: contatta l'amministratore del server."
            ) from errore
    log.info("Aggiornamento a %s richiesto da %s (#%s)", versione, utente, richiesta.pk)
    return richiesta


def annulla_richiesta(utente: Any) -> RichiestaAggiornamento:
    """Annulla la richiesta se il server non l'ha ancora presa in carico."""
    richiesta = richiesta_aperta()
    if richiesta is None:
        raise ValidationError("Nessun aggiornamento in attesa da annullare.")
    if (cartella() / FILE_IN_CORSO).exists():
        raise RichiestaInCorso("L'aggiornamento è già in corso sul server: non si può annullare.")
    with contextlib.suppress(OSError):
        (cartella() / FILE_RICHIESTA).unlink()
    richiesta.stato = StatoRichiesta.ANNULLATO
    richiesta.messaggio = f"Annullato da {utente}."[:500]
    richiesta.completato_il = timezone.now()
    richiesta.save()
    return richiesta


def sincronizza_storico() -> RichiestaAggiornamento | None:
    """Riporta nello storico l'avanzamento di `stato.json`; restituisce la richiesta a cui si
    riferisce (o quella aperta)."""
    stato = leggi_stato()
    richiesta = None
    if stato and stato.get("id") is not None:
        with contextlib.suppress(TypeError, ValueError):
            richiesta = RichiestaAggiornamento.objects.filter(pk=int(stato["id"])).first()
    if stato is None or richiesta is None or not richiesta.aperta:
        aperta = richiesta_aperta()
        if (
            aperta
            and aperta.stato == StatoRichiesta.IN_ATTESA
            and (cartella() / FILE_IN_CORSO).exists()
        ):
            aperta.stato = StatoRichiesta.IN_CORSO
            aperta.messaggio = "Presa in carico dal server."
            aperta.save()
        return aperta or richiesta
    if isinstance(stato.get("fase"), str):
        richiesta.fase = stato["fase"][:40]
    if isinstance(stato.get("messaggio"), str):
        richiesta.messaggio = stato["messaggio"][:500]
    percentuale = stato.get("percentuale")
    if isinstance(percentuale, int | float) and not isinstance(percentuale, bool):
        richiesta.percentuale = max(0, min(100, int(percentuale)))
    if isinstance(stato.get("log"), list):
        richiesta.log = "\n".join(str(r) for r in stato["log"][-MAX_RIGHE_LOG:])
    esito = stato.get("esito")
    if esito in ESITI:
        richiesta.stato = ESITI[esito]
        richiesta.completato_il = (
            parse_datetime(str(stato.get("aggiornato_at") or "")) or timezone.now()
        )
    elif richiesta.stato == StatoRichiesta.IN_ATTESA:
        richiesta.stato = StatoRichiesta.IN_CORSO
    richiesta.save()
    return richiesta
