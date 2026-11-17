import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from tana.accounts.models import User
from tana.prenotazioni import contributo, documenti, flusso
from tana.sito import regolamento
from tana.sito.models import PaginaRegolamento

from .utils import richiesta

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _dati(dati):
    pass


@pytest.fixture
def confermata(richiedente, contatto, admin, pattuglia):
    p = richiesta(richiedente, contatto)
    flusso.approva(p, utente=admin)
    flusso.registra_pagamento(
        p, utente=pattuglia, tipo="ACCONTO", importo_centesimi=p.acconto_centesimi, data=p.arrivo
    )
    return p


def test_pdf_veri(confermata, pattuglia):
    """Generazione reale con WeasyPrint (serve Pango: in CI e nel Dockerfile c'è)."""
    for tipo in ("preventivo", "conferma"):
        assert documenti.pdf(confermata, tipo).startswith(b"%PDF")
    contributo.aggiorna_consuntivo(confermata, utente=pattuglia)
    assert documenti.disponibili(confermata) == ["preventivo", "conferma", "consuntivo"]
    assert documenti.pdf(confermata, "consuntivo").startswith(b"%PDF")


def test_documenti_secondo_lo_stato(richiedente, contatto):
    p = richiesta(richiedente, contatto)
    assert documenti.disponibili(p) == ["preventivo"]


def test_scaricare_i_documenti(confermata, richiedente, pattuglia, monkeypatch):
    monkeypatch.setattr(documenti, "genera", lambda template, contesto: b"%PDF-finto")
    url = reverse("prenotazioni:documento", args=[confermata.numero, "conferma"])
    titolare = Client()
    titolare.force_login(richiedente)
    risposta = titolare.get(url)
    assert risposta["Content-Type"] == "application/pdf" and risposta.content == b"%PDF-finto"
    assert (
        titolare.get(
            reverse("prenotazioni:documento", args=[confermata.numero, "consuntivo"])
        ).status_code
        == 404
    )
    gestione = Client()
    gestione.force_login(pattuglia)
    assert gestione.get(url).status_code == 200
    altro = Client()
    altro.force_login(User.objects.create_user("altro@example.org"))
    assert altro.get(url).status_code == 404


def test_allegati_alla_conferma(
    sito,
    richiedente,
    contatto,
    admin,
    pattuglia,
    monkeypatch,
    django_capture_on_commit_callbacks,
    mailoutbox,
):
    monkeypatch.setattr(documenti, "genera", lambda template, contesto: b"%PDF-documento")
    monkeypatch.setattr(regolamento, "genera", lambda template, contesto: b"%PDF-regolamento")
    PaginaRegolamento.objects.get().save_revision().publish()
    p = richiesta(richiedente, contatto)
    flusso.approva(p, utente=admin)
    with django_capture_on_commit_callbacks(execute=True):
        flusso.registra_pagamento(
            p,
            utente=pattuglia,
            tipo="ACCONTO",
            importo_centesimi=p.acconto_centesimi,
            data=p.arrivo,
        )
    al_richiedente, alla_gestione = mailoutbox
    assert [a[0] for a in al_richiedente.attachments] == [
        f"conferma-{p.numero}.pdf",
        "regolamento-base-aiello.pdf",
    ]
    assert al_richiedente.attachments[1][1] == b"%PDF-regolamento"
    assert alla_gestione.attachments == []


def test_senza_pdf_l_email_parte_lo_stesso(
    richiedente,
    contatto,
    admin,
    pattuglia,
    monkeypatch,
    django_capture_on_commit_callbacks,
    mailoutbox,
):
    from tana.core.pdf import PdfNonDisponibile

    def guasto(template, contesto):
        raise PdfNonDisponibile("niente Pango")

    monkeypatch.setattr(documenti, "genera", guasto)
    p = richiesta(richiedente, contatto)
    flusso.approva(p, utente=admin)
    with django_capture_on_commit_callbacks(execute=True):
        flusso.registra_pagamento(
            p, utente=pattuglia, tipo="ACCONTO", importo_centesimi=100, data=p.arrivo
        )
    assert len(mailoutbox) == 2 and mailoutbox[0].attachments == []


def test_pwa(client):
    manifest = client.get("/manifest.webmanifest")
    assert manifest["Content-Type"] == "application/manifest+json"
    import json

    dati = json.loads(manifest.content)
    assert dati["display"] == "standalone" and any(
        i.get("purpose") == "maskable" for i in dati["icons"]
    )
    sw = client.get("/sw.js")
    assert sw["Content-Type"] == "application/javascript" and b"senza-rete" in sw.content
    assert client.get("/senza-rete/").status_code == 200
    assert 'rel="manifest"' in client.get("/listino/").content.decode()
    call_command("check")
