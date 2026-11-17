import datetime

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone

from tana.accounts.models import Ruolo, User
from tana.base.models import Configurazione
from tana.core.formati import euro
from tana.core.services import storico
from tana.listini.models import Categoria
from tana.prenotazioni import contributo, flusso
from tana.prenotazioni.flusso import TransizioneNonValida
from tana.prenotazioni.models import (
    AttivitaGiornaliera,
    Occupazione,
    Pagamento,
    Prenotazione,
    Stato,
)
from tana.prenotazioni.services import DateOccupate

from .utils import CASELLA_BASE, EURO, richiesta, tra, utente_con

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _dati(dati):
    pass


# --- Richiesta --------------------------------------------------------------------------


def test_richiesta_occupa_le_date_e_avvisa(email, richiedente, contatto, admin):
    prenotazione = email(richiesta, richiedente, contatto)
    assert prenotazione.stato == Stato.RICHIESTA
    assert prenotazione.richiedente == richiedente
    assert prenotazione.occupazioni.get().attiva
    assert contributo.riepilogo(prenotazione).totale is not None
    al_richiedente, alla_gestione = email.inviate
    assert set(al_richiedente.to) == {"mario@example.org", "referente@example.org"}
    assert al_richiedente.reply_to == [CASELLA_BASE]
    assert (
        al_richiedente.subject
        == f"[Base Aiello] Richiesta di prenotazione {prenotazione.numero} ricevuta"
    )
    # Gestione: casella della base + chi ha il permesso (Amministratore di default)
    assert alla_gestione.to == [CASELLA_BASE, "admin@example.org"]
    assert "Avellino 1" in al_richiedente.body
    assert euro(contributo.riepilogo(prenotazione).totale) in al_richiedente.body


def test_email_alla_gestione_secondo_il_permesso(email, richiedente, contatto, pattuglia):
    superutente = User.objects.create_superuser("tecnico@example.org", "password-lunga-1")
    responsabile = utente_con(Ruolo.RESPONSABILE, "responsabile@example.org")
    email(richiesta, richiedente, contatto)
    destinatari = email.inviate[1].to
    assert responsabile.email in destinatari
    assert pattuglia.email not in destinatari  # la Pattuglia non ha il permesso di default
    assert superutente.email not in destinatari


def test_richiesta_senza_dati_obbligatori(richiedente, contatto):
    with pytest.raises(ValidationError) as errore:
        flusso.invia_richiesta(
            utente=richiedente,
            categoria=Categoria.objects.get(codice="altro"),
            arrivo=tra(-1),
            partenza=tra(-1),
            presenze={"ACC": 10, "TENDE": 5},
            esclusiva_richiesta=True,
        )
    assert set(errore.value.message_dict) >= {
        "arrivo",
        "partenza",
        "specifica_categoria",
        "esclusiva_richiesta",
        "contatto",
    }
    assert not Prenotazione.objects.exists()


def test_richiesta_anonima_non_ammessa(contatto):
    from django.contrib.auth.models import AnonymousUser

    with pytest.raises(PermissionDenied):
        richiesta(AnonymousUser(), contatto)


def test_orizzonte_massimo(richiedente, contatto, admin):
    Configurazione.objects.filter(pk=1).update(orizzonte_massimo=tra(30))
    with pytest.raises(ValidationError):
        richiesta(richiedente, contatto, arrivo=40, partenza=45)
    # Oltre il limite solo l'amministrazione, per le prenotazioni prioritarie (D-25)
    with pytest.raises(ValidationError):
        richiesta(admin, contatto, arrivo=40, partenza=45)
    prioritaria = richiesta(
        admin,
        None,
        arrivo=40,
        partenza=45,
        categoria="foca-regionale",
        da_gestione=True,
        deciso_da="Pattuglia e IRO",
        motivazione="Campo di formazione regionale",
    )
    assert prioritaria.categoria_prioritaria_concessa
    assert prioritaria.richiedente is None
    assert storico(prioritaria).filter(deciso_da="Pattuglia e IRO").exists()


def test_prenotazioni_bloccate_per_tutti(richiedente, contatto, admin):
    # D-31: nessuna nuova prenotazione, nemmeno dalla gestione; il messaggio è l'errore
    Configurazione.objects.filter(pk=1).update(
        prenotazioni_bloccate=True, messaggio_blocco="Chiuse per il giro di prova."
    )
    with pytest.raises(ValidationError, match="Chiuse per il giro di prova."):
        richiesta(richiedente, contatto)
    with pytest.raises(ValidationError, match="Chiuse per il giro di prova."):
        richiesta(
            admin,
            None,
            categoria="foca-regionale",
            da_gestione=True,
            deciso_da="Pattuglia",
            motivazione="Prova",
        )
    assert not Prenotazione.objects.exists()
    Configurazione.objects.filter(pk=1).update(prenotazioni_bloccate=False)
    assert richiesta(richiedente, contatto).stato == Stato.RICHIESTA


def test_categoria_prioritaria_dall_amministrazione_richiede_la_decisione(admin):
    with pytest.raises(ValidationError):
        richiesta(admin, None, categoria="eventi-regionali", da_gestione=True)
    assert not Prenotazione.objects.exists()


def test_amministratore_prenota_anche_da_richiedente(admin, contatto, pattuglia):
    # Un amministratore capo di un gruppo prenota il suo campo: è il titolare
    propria = richiesta(admin, contatto, categoria="foca-regionale")
    assert propria.richiedente == admin
    assert propria.categoria_prioritaria_richiesta
    assert not propria.categoria_prioritaria_concessa
    # Per conto della gestione può farlo solo l'amministrazione
    with pytest.raises(PermissionDenied):
        richiesta(pattuglia, contatto, arrivo=20, partenza=22, da_gestione=True)


def test_richiesta_su_date_occupate(richiedente, contatto):
    richiesta(richiedente, contatto)
    with pytest.raises(DateOccupate):
        richiesta(richiedente, contatto, arrivo=12, partenza=14)


def test_uscita_in_giornata(email, richiedente, contatto):
    uscita = email(
        richiesta,
        richiedente,
        contatto,
        arrivo=20,
        partenza=20,
        presenze={},
        attivita=[(tra(20), AttivitaGiornaliera.Tipo.USCITA_CUCINA, 30)],
    )
    assert not uscita.occupazioni.exists()
    assert contributo.riepilogo(uscita).totale == 90 * EURO


# --- Approvazione -----------------------------------------------------------------------


def test_percorso_completo(email, richiedente, contatto, admin, pattuglia):
    prenotazione = email(richiesta, richiedente, contatto)
    acconto = contributo.acconto_previsto(prenotazione)
    assert acconto == contributo.riepilogo(prenotazione).totale // 2 > 0
    with pytest.raises(PermissionDenied):
        flusso.approva(prenotazione, utente=pattuglia)
    email(flusso.approva, prenotazione, utente=admin)
    assert prenotazione.stato == Stato.APPROVATA
    assert prenotazione.acconto_centesimi == acconto
    assert prenotazione.scadenza_acconto > timezone.now() + datetime.timedelta(days=6)
    approvata = email.inviate[2]
    assert "IBAN: IT00X0000" in approvata.body
    assert f"Causale: Acconto prenotazione {prenotazione.numero} - Avellino 1" in approvata.body

    pagamento = email(
        flusso.carica_ricevuta,
        prenotazione,
        utente=richiedente,
        ricevuta=ContentFile(b"%PDF", name="bonifico.pdf"),
    )
    prenotazione.refresh_from_db()
    assert prenotazione.scadenza_acconto is None
    assert pagamento.stato == Pagamento.StatoPagamento.IN_VERIFICA
    assert pagamento.ricevuta.name.startswith(f"ricevute/{prenotazione.numero}/")
    assert email.inviate[-1].to == [CASELLA_BASE, admin.email]  # solo alla gestione
    with pytest.raises(PermissionDenied):
        flusso.verifica_ricevuta(pagamento, utente=richiedente)

    email(flusso.verifica_ricevuta, pagamento, utente=pattuglia)
    prenotazione.refresh_from_db()
    assert prenotazione.stato == Stato.CONFERMATA
    assert contributo.acconto_versato(prenotazione) == acconto
    assert "confermata" in email.inviate[-1].subject

    # Dopo la partenza: svolta (scheduler), poi consuntivo e chiusura
    Prenotazione.objects.filter(pk=prenotazione.pk).update(arrivo=tra(-8), partenza=tra(-3))
    with email.cattura(execute=True):
        assert flusso.segna_svolte() == 1
    prenotazione.refresh_from_db()
    assert prenotazione.stato == Stato.SVOLTA
    with pytest.raises(ValidationError):
        flusso.chiudi(prenotazione, utente=pattuglia)
    contributo.aggiorna_consuntivo(prenotazione, utente=pattuglia)
    email(flusso.chiudi, prenotazione, utente=pattuglia)
    assert prenotazione.stato == Stato.CHIUSA
    consuntivo = email.inviate[-1]
    assert f"Saldo: {euro(contributo.saldo(prenotazione))}" in consuntivo.body
    assert contributo.saldo(prenotazione) == acconto  # stesse persone: resta l'altra metà
    azioni = list(storico(prenotazione).values_list("azione", flat=True))
    assert azioni[:3] == ["chiusa", "svolta", "confermata (acconto verificato)"]


def test_approvazione_con_voci_da_definire(richiedente, contatto, admin):
    prenotazione = richiesta(
        richiedente,
        contatto,
        categoria="altro",
        specifica_categoria="AGESCI estero",
        presenze={"TENDE": 6},
    )
    with pytest.raises(ValidationError):
        flusso.approva(prenotazione, utente=admin)
    (riga,) = contributo.riepilogo(prenotazione).righe
    contributo.valorizza_riga(
        riga, prezzo_centesimi=7 * EURO, utente=admin, deciso_da="Pattuglia", motivazione="Tariffa"
    )
    flusso.approva(prenotazione, utente=admin)
    assert prenotazione.acconto_centesimi == 6 * 6 * 7 * EURO // 2


def test_concessioni_e_acconto_come_decisioni(email, richiedente, contatto, admin):
    prenotazione = richiesta(
        richiedente,
        contatto,
        categoria="foca-regionale",
        esclusiva_richiesta=True,
    )
    assert prenotazione.categoria_prioritaria_richiesta
    assert not prenotazione.categoria_prioritaria_concessa
    # Concedere l'esclusiva senza "deciso da" non è possibile (P-03)
    with pytest.raises(ValidationError):
        flusso.approva(prenotazione, utente=admin, concedi_esclusiva=True)
    prenotazione.refresh_from_db()
    assert not prenotazione.esclusiva_concessa
    assert not prenotazione.occupazioni.filter(area__codice="TENDE").exists()

    email(
        flusso.approva,
        prenotazione,
        utente=admin,
        concedi_esclusiva=True,
        acconto_centesimi=0,
        deciso_da="Pattuglia",
        motivazione="Campo di formazione: esclusiva ed esenzione dall'acconto",
    )
    assert prenotazione.esclusiva_concessa
    assert prenotazione.occupazioni.get(area__codice="TENDE").tipo == Occupazione.Tipo.ESCLUSIVA
    # Acconto zero: niente scadenza, la conferma resta manuale
    assert (prenotazione.acconto_centesimi, prenotazione.scadenza_acconto) == (0, None)
    assert "la Pattuglia della base confermerà" in email.inviate[-2].body
    with pytest.raises(TransizioneNonValida):
        flusso.carica_ricevuta(prenotazione, utente=richiedente, ricevuta=ContentFile(b"x"))
    flusso.conferma_senza_acconto(prenotazione, utente=admin)
    assert prenotazione.stato == Stato.CONFERMATA


def test_categoria_prioritaria_concessa_all_approvazione(richiedente, contatto, admin):
    prenotazione = richiesta(richiedente, contatto, categoria="foca-nazionale")
    totale_associativo = contributo.riepilogo(prenotazione).totale
    flusso.approva(
        prenotazione,
        utente=admin,
        concedi_categoria=True,
        deciso_da="Responsabili regionali",
        motivazione="CFA nazionale",
    )
    # Fo.Ca. nazionale: listino di default associativo, stesso totale
    assert contributo.riepilogo(prenotazione).totale == totale_associativo
    assert prenotazione.categoria_prioritaria_concessa


def test_soggiorno_breve_senza_acconto(richiedente, contatto, admin):
    prenotazione = richiesta(richiedente, contatto, arrivo=10, partenza=12)  # 3 giorni
    flusso.approva(prenotazione, utente=admin)
    assert prenotazione.acconto_centesimi == 0 and prenotazione.scadenza_acconto is None


# --- Rifiuto, annullamento, scadenze ----------------------------------------------------


@pytest.mark.parametrize("comunica", [True, False])
def test_rifiuto(email, richiedente, contatto, admin, comunica):
    prenotazione = richiesta(richiedente, contatto)
    with pytest.raises(ValidationError):
        flusso.rifiuta(prenotazione, utente=admin, deciso_da="Pattuglia", motivazione="")
    email(
        flusso.rifiuta,
        prenotazione,
        utente=admin,
        deciso_da="Pattuglia",
        motivazione="Base chiusa per lavori",
        comunica_motivazione=comunica,
    )
    assert prenotazione.stato == Stato.RIFIUTATA
    assert not prenotazione.occupazioni.get().attiva
    al_richiedente, alla_gestione = email.inviate
    assert ("Base chiusa per lavori" in al_richiedente.body) is comunica
    assert "Base chiusa per lavori" in alla_gestione.body
    with pytest.raises(TransizioneNonValida):
        flusso.approva(prenotazione, utente=admin)


def test_annullamento_libera_le_date(email, richiedente, contatto, admin):
    prenotazione = richiesta(richiedente, contatto)
    altro = User.objects.create_user("altro@example.org")
    with pytest.raises(PermissionDenied):
        flusso.annulla(prenotazione, utente=altro)
    flusso.approva(prenotazione, utente=admin)
    email(flusso.annulla, prenotazione, utente=richiedente, motivo="Campo spostato")
    assert prenotazione.stato == Stato.ANNULLATA
    assert prenotazione.scadenza_acconto is None
    assert "Campo spostato" in email.inviate[0].body
    richiesta(richiedente, contatto)  # date di nuovo libere
    with pytest.raises(TransizioneNonValida):
        flusso.annulla(prenotazione, utente=richiedente)


def test_scadenza_dell_acconto(email, richiedente, contatto, admin):
    prenotazione = richiesta(richiedente, contatto)
    flusso.approva(prenotazione, utente=admin)
    assert flusso.scadi_acconti() == 0
    Prenotazione.objects.filter(pk=prenotazione.pk).update(
        scadenza_acconto=timezone.now() - datetime.timedelta(minutes=1)
    )
    with pytest.raises(ValidationError):
        flusso.carica_ricevuta(prenotazione, utente=richiedente, ricevuta=ContentFile(b"x"))
    with email.cattura(execute=True):
        assert flusso.scadi_acconti() == 1
    prenotazione.refresh_from_db()
    assert prenotazione.stato == Stato.SCADUTA
    assert not prenotazione.occupazioni.get().attiva
    assert "scaduta" in email.inviate[0].subject
    assert flusso.scadi_acconti() == 0


def test_ricevuta_respinta_fa_ripartire_il_termine(email, richiedente, contatto, admin, pattuglia):
    prenotazione = richiesta(richiedente, contatto)
    flusso.approva(prenotazione, utente=admin)
    pagamento = flusso.carica_ricevuta(
        prenotazione, utente=richiedente, ricevuta=ContentFile(b"x", name="r.pdf")
    )
    with pytest.raises(ValidationError):
        flusso.carica_ricevuta(prenotazione, utente=richiedente, ricevuta=ContentFile(b"y"))
    # Ricevuta in verifica: non scade anche se la Pattuglia verifica dopo il termine
    assert flusso.scadi_acconti() == 0
    email(flusso.respingi_ricevuta, pagamento, utente=pattuglia, motivazione="Importo errato")
    assert prenotazione.scadenza_acconto > timezone.now() + datetime.timedelta(days=6)
    assert "Importo errato" in email.inviate[0].body
    # Una ricevuta respinta non congela il preventivo; se ne carica un'altra
    assert not contributo.preventivo_congelato(prenotazione)
    nuovo = flusso.carica_ricevuta(
        prenotazione, utente=richiedente, ricevuta=ContentFile(b"z", name="r2.pdf")
    )
    flusso.verifica_ricevuta(nuovo, utente=pattuglia, importo_centesimi=1234)
    assert contributo.acconto_versato(prenotazione) == 1234


def test_svolta_non_prima_della_partenza(richiedente, contatto, admin):
    prenotazione = richiesta(richiedente, contatto, arrivo=10, partenza=12)
    flusso.approva(prenotazione, utente=admin)
    flusso.conferma_senza_acconto(prenotazione, utente=admin)
    assert flusso.segna_svolte() == 0
    with pytest.raises(TransizioneNonValida):
        flusso.segna_svolta(prenotazione, utente=admin)


def test_storico_importato_corretto_in_svolta(email, richiedente, contatto, admin, pattuglia):
    prenotazione = richiesta(richiedente, contatto)
    Prenotazione.objects.filter(pk=prenotazione.pk).update(stato=Stato.NON_SVOLTA)
    with pytest.raises(PermissionDenied):
        flusso.segna_svolta(prenotazione, utente=pattuglia)
    email(flusso.segna_svolta, prenotazione, utente=admin)
    assert prenotazione.stato == Stato.SVOLTA
    assert email.inviate == []  # niente email per lo storico importato


def test_euro():
    assert euro(134400) == "1.344,00 €"
    assert euro(5) == "0,05 €"
    assert euro(-123456) == "-1.234,56 €"
    assert euro(None) == "da definire"
