"""«Non sono un robot» per le richieste senza account (D-33), con ALTCHA: una prova di lavoro
che il browser risolve in pochi decimi di secondo. Nessun servizio esterno e nessun dato fuori
dal server; il widget è in static/tana/vendor/altcha-3.5.0/.
"""

import datetime
import hashlib
import hmac

from altcha import Payload, create_challenge, verify_solution
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

ALGORITMO = "PBKDF2/SHA-256"
COSTO = 5_000  # iterazioni per tentativo (esempio della libreria): sotto il secondo nel browser
VALIDITA = datetime.timedelta(minutes=20)


def _segreto() -> bytes:
    # Derivato dalla SECRET_KEY: niente variabili nuove in .env
    return hmac.new(settings.SECRET_KEY.encode(), b"tana-altcha", hashlib.sha256).digest()


def sfida() -> dict:
    """La sfida per il widget (JSON)."""
    return create_challenge(
        ALGORITMO, COSTO, expires_at=timezone.now() + VALIDITA, hmac_secret=_segreto()
    ).to_dict()


def verifica(soluzione: str | None) -> bool:
    """La soluzione inviata dal modulo; ogni sfida vale una volta sola."""
    if not soluzione:
        return False
    try:
        esito = verify_solution(soluzione, _segreto())
        firma = Payload.from_base64(soluzione).challenge.signature
    except Exception:  # payload malformato
        return False
    if not esito.verified:
        return False
    # cache.add è falso se la chiave c'è già: soluzione già usata
    return cache.add(f"altcha:{firma}", True, int(VALIDITA.total_seconds()))
