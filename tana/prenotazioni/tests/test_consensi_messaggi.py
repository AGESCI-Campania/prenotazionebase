import datetime

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from tana.accounts.models import User
from tana.base.models import Area, Configurazione
from tana.listini.models import Listino, VersioneListino
from tana.listini.services import listini_in_vigore
from tana.prenotazioni import consensi, contributo, disponibilita, flusso, messaggi
from tana.prenotazioni.models import AttivitaGiornaliera, Contatto, RichiestaConsenso, Stato
from tana.prenotazioni.services import crea_blocco

from .utils import CASELLA_BASE, richiesta, tra

pytestmark = pytest.mark.django_db

StatoConsenso = RichiestaConsenso.StatoConsenso
USCITA = AttivitaGiornaliera.Tipo.USCITA_CUCINA


@pytest.fixture(autouse=True)
def _dati(dati):
    pass


@pytest.fixture
def secondo():
    return User.objects.create_user("secondo@example.org")


@pytest.fixture
def contatto2():
    return Contatto.objects.create(
        nome="Anna Bianchi", email="anna@example.org", telefono="3337654321"
    )


def uscita(utente, contatto, giorno, **campi):
    return richiesta(
        utente,
        contatto,
        arrivo=giorno,
        partenza=giorno,
        presenze={},
        attivita=[(tra(giorno), USCITA, 30)],
        gruppo="Salerno 3",
        **campi,
    )


# --- Disponibilità ----------------------------------------------------------------------


def test_mezze_giornate_del_calendario(richiedente, contatto):
    richiesta(richiedente, contatto, arrivo=10, partenza=15)
    arrivo, partenza = tra(10), tra(15)
    notti = disponibilita.notti(tra(9), tra(16))[Area.objects.get(codice="ACC").pk]
    assert tra(9) not in notti and partenza not in notti
    assert notti[arrivo] == notti[tra(14)] == disponibilita.OCCUPATO
    settimane = disponibilita.calendario_mese(arrivo.year, arrivo.month)
    giorni = {g.data: g for settimana in settimane for g in settimana}
    _, prima, dopo = giorni[arrivo].aree[0]
    assert (prima, dopo) == (disponibilita.LIBERO, disponibilita.OCCUPATO)
    _, prima, dopo = giorni[partenza].aree[0]
    assert (prima, dopo) == (disponibilita.OCCUPATO, disponibilita.LIBERO)


def test_non_disponibile_per_blocchi_esclusive_e_prioritarie(richiedente, contatto, admin):
    acc, tende = Area.objects.get(codice="ACC"), Area.objects.get(codice="TENDE")
    crea_blocco(area=acc, dal=tra(30), al=tra(31), motivo="Lavori")
    p = richiesta(richiedente, contatto, arrivo=10, partenza=15, esclusiva_richiesta=True)
    flusso.approva(p, utente=admin, concedi_esclusiva=True, deciso_da="P", motivazione="M")
    richiesta(
        admin,
        None,
        arrivo=40,
        partenza=42,
        categoria="foca-regionale",
        da_gestione=True,
        deciso_da="Pattuglia",
        motivazione="Campo regionale",
    )
    stati = disponibilita.notti(tra(0), tra(50))
    assert stati[acc.pk][tra(30)] == disponibilita.NON_DISPONIBILE
    assert stati[tende.pk][tra(10)] == disponibilita.NON_DISPONIBILE
    assert stati[acc.pk][tra(10)] == disponibilita.OCCUPATO
    assert stati[acc.pk][tra(40)] == disponibilita.NON_DISPONIBILE


def test_verifica_date_e_giorni_di_cambio(richiedente, contatto):
    richiesta(richiedente, contatto, arrivo=10, partenza=15)
    esito = disponibilita.verifica_date(tra(15), tra(18), ["ACC", "TENDE"])
    assert esito.tutte_libere
    assert esito.arrivo_con_partenza == ["Accantonamento"]
    assert not disponibilita.verifica_date(tra(14), tra(18), ["ACC"]).tutte_libere
    esito = disponibilita.verifica_date(tra(5), tra(10), ["ACC"])
    assert esito.partenza_con_arrivo == ["Accantonamento"]


def test_listini_in_vigore_con_la_versione_successiva():
    associativo = Listino.objects.get(tipo="ASSOCIATIVO")
    prossima = VersioneListino.objects.create(
        listino=associativo, nome="2028", pubblicata_il=tra(-1), valida_dal=tra(60)
    )
    VersioneListino.objects.create(
        listino=associativo, nome="non pubblicata", pubblicata_il=tra(5), valida_dal=tra(90)
    )
    listini = {listino.tipo: (c, p) for listino, c, p in listini_in_vigore(timezone.localdate())}
    corrente, successiva = listini["ASSOCIATIVO"]
    assert corrente.nome == "2022/2023" and successiva == prossima


def test_simulazione_uguale_al_preventivo(richiedente, contatto):
    p = richiesta(richiedente, contatto, presenze={"ACC": 20, "TENDE": 12})
    simulato = contributo.simula(
        contributo.Soggiorno(
            categoria=p.categoria,
            arrivo=p.arrivo,
            partenza=p.partenza,
            presenze=[(Area.objects.get(codice="ACC"), 20), (Area.objects.get(codice="TENDE"), 12)],
        )
    )
    assert sum(r.importo for r in simulato) == contributo.riepilogo(p).totale


# --- Consensi ---------------------------------------------------------------------------


def test_uscita_chiede_il_consenso_ai_presenti(
    email, richiedente, contatto, secondo, contatto2, admin
):
    soggiorno = richiesta(richiedente, contatto, arrivo=10, partenza=15)
    # Giorno di partenza: il gruppo è ancora in base
    nuova = email(uscita, secondo, contatto2, 15)
    domanda = nuova.consensi_chiesti.get()
    assert domanda.prenotazione_esistente == soggiorno
    assert domanda.stato == StatoConsenso.IN_ATTESA
    oggetti = [m.subject for m in email.inviate]
    assert any("consenso" in o and soggiorno.numero in o for o in oggetti)
    al_presente = next(m for m in email.inviate if soggiorno.numero in m.subject)
    assert "mario@example.org" in al_presente.to and "Salerno 3" in al_presente.body
    # Senza consenso non si approva
    with pytest.raises(ValidationError):
        flusso.approva(nuova, utente=admin)
    with pytest.raises(PermissionDenied):
        consensi.rispondi(domanda, utente=secondo, concesso=True)
    email(consensi.rispondi, domanda, utente=richiedente, concesso=True)
    assert "anna@example.org" in email.inviate[-2].to
    flusso.approva(nuova, utente=admin)
    assert nuova.stato == Stato.APPROVATA


def test_uscita_in_un_giorno_libero_senza_consenso(secondo, contatto2):
    assert not uscita(secondo, contatto2, 20).consensi_chiesti.exists()


def test_seconda_uscita_chiede_alla_prima(richiedente, contatto, secondo, contatto2):
    prima = uscita(richiedente, contatto, 20)
    seconda = uscita(secondo, contatto2, 20)
    assert seconda.consensi_chiesti.get().prenotazione_esistente == prima
    assert not prima.consensi_chiesti.exists()


def test_consenso_negato_lascia_la_decisione_all_amministrazione(
    richiedente, contatto, secondo, contatto2, admin
):
    richiesta(richiedente, contatto, arrivo=10, partenza=15)
    nuova = uscita(secondo, contatto2, 12)
    consensi.rispondi(nuova.consensi_chiesti.get(), utente=richiedente, concesso=False)
    nuova.refresh_from_db()
    assert nuova.stato == Stato.RICHIESTA  # niente rifiuto automatico
    with pytest.raises(ValidationError):
        flusso.approva(nuova, utente=admin)
    flusso.rifiuta(nuova, utente=admin, deciso_da="Pattuglia", motivazione="Consenso negato")


def test_consenso_scaduto_e_negato(email, richiedente, contatto, secondo, contatto2):
    richiesta(richiedente, contatto, arrivo=10, partenza=15)
    nuova = uscita(secondo, contatto2, 12)
    domanda = nuova.consensi_chiesti.get()
    RichiestaConsenso.objects.filter(pk=domanda.pk).update(
        scadenza=timezone.now() - datetime.timedelta(minutes=1)
    )
    with pytest.raises(ValidationError):
        consensi.rispondi(domanda, utente=richiedente, concesso=True)
    with email.cattura(execute=True):
        assert consensi.scadi_consensi() == 1
    domanda.refresh_from_db()
    assert domanda.stato == StatoConsenso.SCADUTO
    assert "nessuna risposta entro il termine" in email.inviate[0].body
    assert consensi.scadi_consensi() == 0


def test_consenso_non_serve_se_il_presente_annulla(
    richiedente, contatto, secondo, contatto2, admin
):
    soggiorno = richiesta(richiedente, contatto, arrivo=10, partenza=15)
    nuova = uscita(secondo, contatto2, 12)
    flusso.annulla(soggiorno, utente=richiedente)
    assert not consensi.mancanti(nuova).exists()
    flusso.approva(nuova, utente=admin)


def test_prenotazione_senza_titolare_risponde_l_amministrazione(admin, secondo, contatto2):
    regionale = richiesta(
        admin,
        None,
        arrivo=10,
        partenza=15,
        categoria="eventi-regionali",
        da_gestione=True,
        deciso_da="Pattuglia",
        motivazione="Evento regionale",
    )
    domanda = uscita(secondo, contatto2, 12).consensi_chiesti.get()
    assert domanda.prenotazione_esistente == regionale
    consensi.rispondi(domanda, utente=admin, concesso=True)


@pytest.mark.parametrize(
    ("giorni_all_attivita", "atteso"),
    [
        (30, "sette giorni"),
        (3, "inizio del giorno"),
    ],
)
def test_termine_del_consenso(giorni_all_attivita, atteso):
    adesso = timezone.now()
    data = (adesso + datetime.timedelta(days=giorni_all_attivita)).date()
    scadenza = consensi.termine(data, adesso)
    if atteso == "sette giorni":
        assert scadenza == adesso + datetime.timedelta(
            days=Configurazione.corrente().consenso_giorni
        )
    else:
        assert timezone.localtime(scadenza).time() == datetime.time.min
        assert timezone.localtime(scadenza).date() == data


def test_termine_alle_otto_del_giorno_stesso():
    data = datetime.date(2027, 7, 20)
    sera_prima = timezone.make_aware(datetime.datetime(2027, 7, 19, 23, 30))
    scadenza = consensi.termine(data, sera_prima)
    assert timezone.localtime(scadenza) == timezone.make_aware(datetime.datetime(2027, 7, 20, 8, 0))
    mattina_vigilia = timezone.make_aware(datetime.datetime(2027, 7, 19, 7, 0))
    assert consensi.termine(data, mattina_vigilia) == scadenza
    due_giorni_prima = timezone.make_aware(datetime.datetime(2027, 7, 18, 23, 0))
    assert timezone.localtime(consensi.termine(data, due_giorni_prima)).time() == datetime.time.min
    troppo_tardi = timezone.make_aware(datetime.datetime(2027, 7, 20, 9, 0))
    with pytest.raises(ValidationError):
        consensi.termine(data, troppo_tardi)


# --- Messaggi e telefoni ----------------------------------------------------------------


def test_gruppi_vicini(richiedente, contatto, secondo, contatto2):
    primo = richiesta(richiedente, contatto, arrivo=10, partenza=15)
    cambio = richiesta(secondo, contatto2, arrivo=15, partenza=18, gruppo="Salerno 3")
    lontano = richiesta(secondo, contatto2, arrivo=25, partenza=27)
    tende = richiesta(secondo, contatto2, arrivo=11, partenza=12, presenze={"TENDE": 6})
    vicini = set(messaggi.gruppi_vicini(primo))
    assert vicini == {cambio, tende}
    assert lontano not in vicini


def test_messaggi_con_la_gestione(email, richiedente, contatto, pattuglia):
    p = richiesta(richiedente, contatto)
    conversazione = messaggi.con_gestione(p)
    email(
        messaggi.invia, conversazione, utente=richiedente, testo="Possiamo arrivare alle 12?", da=p
    )
    (alla_gestione,) = email.inviate
    assert CASELLA_BASE in alla_gestione.to and "alle 12" in alla_gestione.body
    assert messaggi.senza_risposta().get() == conversazione
    with pytest.raises(PermissionDenied):
        messaggi.invia(conversazione, utente=richiedente, testo="finta gestione", da=None)
    email(messaggi.invia, conversazione, utente=pattuglia, testo="Sì, nessun problema", da=None)
    assert email.inviate[-1].to == ["mario@example.org", "referente@example.org"]
    assert not messaggi.senza_risposta().exists()
    assert messaggi.segna_letti(conversazione, lettore=p) == 1


def test_messaggi_tra_gruppi(email, richiedente, contatto, secondo, contatto2):
    primo = richiesta(richiedente, contatto, arrivo=10, partenza=15)
    cambio = richiesta(secondo, contatto2, arrivo=15, partenza=18, gruppo="Salerno 3")
    lontano = richiesta(secondo, contatto2, arrivo=25, partenza=27)
    conversazione = messaggi.tra_gruppi(cambio, primo)
    assert conversazione == messaggi.tra_gruppi(primo, cambio)  # una sola per coppia
    with pytest.raises(PermissionDenied):
        messaggi.tra_gruppi(primo, lontano)
    with pytest.raises(PermissionDenied):
        messaggi.invia(conversazione, utente=richiedente, testo="Ciao", da=cambio)
    email(messaggi.invia, conversazione, utente=secondo, testo="A che ora partite?", da=cambio)
    (messaggio,) = email.inviate
    assert messaggio.to == ["mario@example.org", "referente@example.org"]  # solo l'altro gruppo
    assert "Salerno 3" in messaggio.body
    assert "anna@example.org" not in messaggio.body  # l'email dell'altro gruppo resta nascosta


def test_telefono_solo_se_autorizzato(email, richiedente, contatto, secondo, contatto2):
    primo = richiesta(richiedente, contatto, arrivo=10, partenza=15)
    cambio = richiesta(secondo, contatto2, arrivo=15, partenza=18)
    domanda = email(messaggi.chiedi_telefono, cambio, primo, utente=secondo)
    assert messaggi.telefoni_visibili(cambio) == []
    assert email.inviate[0].to == ["mario@example.org", "referente@example.org"]
    with pytest.raises(PermissionDenied):
        messaggi.rispondi_telefono(domanda, utente=secondo, autorizza=True)
    messaggi.rispondi_telefono(domanda, utente=richiedente, autorizza=True)
    ((altro, referente),) = messaggi.telefoni_visibili(cambio)
    assert altro == primo and referente.telefono == "3331234567"
    assert messaggi.telefoni_visibili(primo) == []  # non è reciproco
