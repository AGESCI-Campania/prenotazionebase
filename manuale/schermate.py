"""Schermate del manuale d'uso, generate con Playwright su dati di esempio (inventati).

Uso (Chromium una volta sola: `uv run --group schermate playwright install chromium`):

    uv run --group schermate pytest manuale/schermate.py

Gira sul database di test (quello di sviluppo non si tocca) con un server di prova
(`live_server`) e salva le PNG in manuale/schermate/, che il manuale include. Da
rilanciare quando cambia l'interfaccia di una pagina fotografata (vedi CLAUDE.md, Release).

L'orologio è fermo al 17/11/2026 alle 10:00, così date e orari dei dati di esempio non cambiano
da un'esecuzione all'altra; una PNG si riscrive solo se l'immagine è diversa da quella salvata.
"""

import datetime
import io
import os
import zoneinfo
from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from django.test import Client
from django.utils import timezone

# Playwright (API sincrona) tiene un event loop nel thread dei test: l'ORM lo rifiuterebbe
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

CARTELLA = Path(__file__).parent / "schermate"
ADESSO = datetime.datetime(2026, 11, 17, 10, 0, tzinfo=zoneinfo.ZoneInfo("Europe/Rome"))
LARGHEZZA, ALTEZZA = 1280, 800
EURO = 100

pytestmark = pytest.mark.django_db(transaction=True)


def tra(giorni: int) -> datetime.date:
    return timezone.localdate() + datetime.timedelta(days=giorni)


@pytest.fixture(autouse=True)
def orologio():
    import time_machine

    with time_machine.travel(ADESSO, tick=False):
        yield


@pytest.fixture
def dati(orologio, sito):
    from tana.base.models import Configurazione

    Configurazione.objects.filter(pk=1).update(
        orizzonte_massimo=tra(400),
        iban="IT00X0000000000000000000000",
        intestatario_bonifico="AGESCI Regione Campania",
    )


def _utente(email: str, ruolo: str | None = None):
    from tana.accounts.models import User
    from tana.accounts.services import nomina

    utente = User.objects.create_user(email, first_name=email.split("@")[0].title())
    if ruolo:
        nomina(utente, ruolo)
    return utente


def _contatto(nome: str):
    from tana.prenotazioni.models import Contatto

    email = nome.lower().replace(" ", ".") + "@example.org"
    return Contatto.objects.create(nome=nome, email=email, telefono="333 0000000")


def _richiesta(utente, contatto, arrivo, partenza, gruppo, **campi):
    from tana.listini.models import Categoria
    from tana.prenotazioni import flusso

    campi.setdefault("presenze", {"ACC": 28})
    return flusso.invia_richiesta(
        utente=utente,
        categoria=Categoria.objects.get(codice=campi.pop("categoria", "gruppo-agesci")),
        arrivo=tra(arrivo),
        partenza=tra(partenza),
        contatto=contatto,
        gruppo=gruppo,
        **campi,
    )


@pytest.fixture
def scenario(dati):
    """Utenti dei ruoli e prenotazioni in tutti gli stati che le schermate mostrano."""
    from tana.accounts.models import Ruolo
    from tana.base.models import Area
    from tana.prenotazioni import contributo, flusso, messaggi
    from tana.prenotazioni.models import Prenotazione, Stato
    from tana.prenotazioni.services import crea_blocco, sincronizza_occupazioni

    u = {
        "richiedente": _utente("referente@example.org"),
        "pattuglia": _utente("pattuglia@example.org", Ruolo.PATTUGLIA),
        "admin": _utente("amministratore@example.org", Ruolo.AMMINISTRATORE),
        "segreteria": _utente("segreteria@example.org", Ruolo.SEGRETERIA),
        "redazione": _utente("redazione@example.org", Ruolo.REDAZIONE),
    }
    admin, pattuglia, richiedente = u["admin"], u["pattuglia"], u["richiedente"]
    mario = _contatto("Mario Rossi")

    # Del richiedente: una in esame, una approvata in attesa dell'acconto (con un messaggio)
    in_esame = _richiesta(richiedente, mario, 40, 43, "Avellino 1", unita=["EG"])
    approvata = _richiesta(richiedente, mario, 20, 24, "Avellino 1", unita=["LC", "EG"])
    flusso.approva(approvata, utente=admin)
    messaggi.invia(
        messaggi.con_gestione(approvata),
        utente=richiedente,
        testo="Buongiorno, possiamo arrivare alle 14 invece che alle 15?",
        da=approvata,
    )
    # Altri gruppi: una ricevuta da verificare, una confermata, un campo in tenda
    con_ricevuta = _richiesta(
        _utente("benevento3@example.org"), _contatto("Luca Ferraro"), 6, 9, "Benevento 3"
    )
    flusso.approva(con_ricevuta, utente=admin)
    flusso.carica_ricevuta(
        con_ricevuta,
        utente=pattuglia,
        ricevuta=ContentFile(b"%PDF-1.4 ricevuta di esempio", name="ricevuta.pdf"),
    )
    confermata = _richiesta(
        _utente("salerno7@example.org"), _contatto("Chiara Romano"), 1, 3, "Salerno 7"
    )
    flusso.approva(
        confermata,
        utente=admin,
        acconto_centesimi=0,
        deciso_da="Pattuglia",
        motivazione="Uscita breve di fine anno",
    )
    flusso.conferma_senza_acconto(confermata, utente=pattuglia)
    _richiesta(
        _utente("napoli12@example.org"),
        _contatto("Davide Russo"),
        12,
        16,
        "Napoli 12",
        presenze={"TENDE": 35},
    )
    # Svolta il mese scorso: consuntivo da compilare
    svolta = _richiesta(
        _utente("caserta2@example.org"), _contatto("Sara Marino"), 30, 33, "Caserta 2"
    )
    Prenotazione.objects.filter(pk=svolta.pk).update(arrivo=tra(-12), partenza=tra(-9))
    svolta.refresh_from_db()
    sincronizza_occupazioni(svolta)
    contributo.aggiorna_preventivo(svolta)
    Prenotazione.objects.filter(pk=svolta.pk).update(stato=Stato.SVOLTA)
    crea_blocco(
        area=Area.objects.get(codice="TENDE"),
        dal=tra(26),
        al=tra(28),
        motivo="Taglio dell'erba",
        utente=admin,
    )
    return {
        **u,
        "in_esame": in_esame,
        "approvata": approvata,
        "con_ricevuta": con_ricevuta,
        "svolta": Prenotazione.objects.get(pk=svolta.pk),
    }


@pytest.fixture
def browser():
    from playwright.sync_api import sync_playwright

    CARTELLA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        # Il pulsante dei file («Choose file») segue la lingua del sistema, non --lang
        b = p.chromium.launch()
        yield b
        b.close()


PIXEL_TOLLERATI = 50  # sfumature delle icone che il browser disegna in modo variabile


def _uguali(a: bytes, b: Path) -> bool:
    """Stessa immagine, salvo pochi pixel di sfumatura (i byte del PNG possono differire comunque)."""
    from PIL import Image, ImageChops

    if not b.exists():
        return False
    with Image.open(io.BytesIO(a)) as nuova, Image.open(b) as vecchia:
        if nuova.size != vecchia.size:
            return False
        diff = ImageChops.difference(nuova.convert("RGB"), vecchia.convert("RGB")).convert("L")
        diversi = sum(diff.point(lambda v: 255 if v > 24 else 0).histogram()[255:])
        return diversi <= PIXEL_TOLLERATI


class Fotografo:
    def __init__(self, browser, base: str) -> None:
        self.browser, self.base = browser, base
        self.cambiate: list[str] = []

    def come(self, utente=None):
        """Una pagina del browser con la sessione di `utente` (None: anonimo)."""
        contesto = self.browser.new_context(
            viewport={"width": LARGHEZZA, "height": ALTEZZA}, locale="it-IT"
        )
        if utente is not None:
            client = Client()
            client.force_login(utente)
            contesto.add_cookies(
                [
                    {
                        "name": "sessionid",
                        "value": client.cookies["sessionid"].value,
                        "url": self.base,
                    }
                ]
            )
        return contesto.new_page()

    def scatta(self, pagina, percorso: str, nome: str, *, intera: bool = False, prima=None) -> None:
        pagina.goto(self.base + percorso)
        pagina.wait_for_load_state("networkidle")
        if prima:
            prima(pagina)
        if intera:
            # Il contenuto scorre in .ag-scroll-area, non nella finestra (full_page non lo vede):
            # si allunga la finestra fino alla fine del contenuto
            altezza = pagina.evaluate(
                """() => {
                    const area = document.querySelector('.ag-scroll-area');
                    return area ? area.getBoundingClientRect().top + area.scrollHeight
                                : document.documentElement.scrollHeight;
                }"""
            )
            pagina.set_viewport_size({"width": LARGHEZZA, "height": max(ALTEZZA, int(altezza))})
            pagina.wait_for_timeout(200)
        # Font e icone (lo sprite di Wagtail arriva dopo il caricamento): immagini stabili
        pagina.evaluate("document.fonts.ready")
        pagina.wait_for_timeout(500)
        immagine = pagina.screenshot()
        file = CARTELLA / f"{nome}.png"
        if not _uguali(immagine, file):
            file.write_bytes(immagine)
            self.cambiate.append(nome)
        pagina.set_viewport_size({"width": LARGHEZZA, "height": ALTEZZA})


def test_schermate(scenario, live_server, browser):
    s = scenario
    f = Fotografo(browser, live_server.url)

    # Pubblico e richiedente
    anonimo = f.come()
    f.scatta(anonimo, "/accounts/login/", "accesso")
    f.scatta(anonimo, "/disponibilita/", "disponibilita")
    f.scatta(anonimo, "/listino/", "listino")
    gruppo = f.come(s["richiedente"])
    f.scatta(gruppo, "/prenotazioni/nuova/", "richiesta-passo-1", intera=True)
    f.scatta(gruppo, "/prenotazioni/", "mie-prenotazioni")
    f.scatta(gruppo, f"/prenotazioni/{s['approvata'].numero}/", "prenotazione-acconto", intera=True)

    # Pattuglia
    pattuglia = f.come(s["pattuglia"])
    f.scatta(pattuglia, "/gestione/", "cruscotto")
    f.scatta(pattuglia, "/gestione/prenotazioni/?elenco=acconti", "elenco-acconti")
    f.scatta(
        pattuglia,
        f"/gestione/prenotazioni/{s['con_ricevuta'].numero}/",
        "scheda-acconto",
        intera=True,
    )
    f.scatta(pattuglia, "/gestione/calendario/", "calendario", intera=True)
    f.scatta(pattuglia, "/gestione/arrivi/?periodo=settimana", "arrivi")
    f.scatta(
        pattuglia,
        f"/gestione/prenotazioni/{s['svolta'].numero}/consuntivo/",
        "consuntivo",
        intera=True,
    )
    f.scatta(pattuglia, "/gestione/statistiche/", "statistiche", intera=True)

    # Amministrazione
    admin = f.come(s["admin"])
    f.scatta(
        admin,
        f"/gestione/prenotazioni/{s['in_esame'].numero}/",
        "scheda-approvazione",
        intera=True,
    )
    f.scatta(admin, "/gestione/blocchi/", "date-bloccate")
    f.scatta(admin, "/gestione/listini/", "listini")
    f.scatta(admin, "/gestione/categorie/", "categorie")
    f.scatta(admin, "/gestione/configurazione/", "configurazione", intera=True)
    f.scatta(admin, "/gestione/prenotazioni/nuova/", "prenotazione-gestione")

    # Segreteria e redazione
    f.scatta(f.come(s["segreteria"]), "/gestione/utenti/", "utenti-ruoli")
    redazione = f.come(s["redazione"])
    f.scatta(redazione, "/cms/pages/", "editor-pagine")

    print("Schermate cambiate:", ", ".join(f.cambiate) or "nessuna")
    assert len(list(CARTELLA.glob("*.png"))) >= 21
