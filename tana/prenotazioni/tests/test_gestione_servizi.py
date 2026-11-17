import datetime

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone

from tana.accounts.models import Ruolo, User
from tana.accounts.services import nomina, revoca
from tana.base.models import Area
from tana.core.services import storico
from tana.listini.models import Listino, VersioneListino
from tana.listini.services import nuova_versione
from tana.prenotazioni import conservazione, contributo, flusso
from tana.prenotazioni.models import (
    AttivitaGiornaliera,
    Contatto,
    Conversazione,
    Pagamento,
    Prenotazione,
    Stato,
)
from tana.prenotazioni.services import DateOccupate, crea_blocco, elimina_blocco

from .utils import CASELLA_BASE, EURO, richiesta, tra

pytestmark = pytest.mark.django_db
Fase = contributo.Fase


@pytest.fixture(autouse=True)
def _dati(dati):
    pass


# --- Modifica dalla gestione ------------------------------------------------------------


def test_modifica_date_e_persone(email, richiedente, contatto, admin, pattuglia):
    p = richiesta(richiedente, contatto, arrivo=20, partenza=25)
    with pytest.raises(PermissionDenied):
        flusso.modifica(
            p, utente=pattuglia, arrivo=tra(30), partenza=tra(33), presenze={"ACC": 10}, attivita=[]
        )
    email(
        flusso.modifica,
        p,
        utente=admin,
        arrivo=tra(30),
        partenza=tra(33),
        presenze={"ACC": 10, "TENDE": 6},
        attivita=[],
        motivo="Spostata per un evento regionale",
    )
    assert (p.arrivo, p.partenza) == (tra(30), tra(33))
    assert p.occupazioni.count() == 2
    assert contributo.riepilogo(p).righe[0].persone == 10
    al_richiedente = email.inviate[0]
    assert "modificata" in al_richiedente.subject and "evento regionale" in al_richiedente.body
    evento = storico(p).get(azione="modificata")
    assert (
        evento.dati_prima["presenze"] == {"ACC": 28} and evento.dati_dopo["presenze"]["TENDE"] == 6
    )
    # Le date vecchie sono di nuovo libere
    richiesta(User.objects.create_user("altro@example.org"), contatto, arrivo=20, partenza=25)


def test_modifica_su_date_occupate(richiedente, contatto, admin):
    richiesta(richiedente, contatto, arrivo=30, partenza=35)
    p = richiesta(richiedente, contatto, arrivo=20, partenza=25)
    with pytest.raises(DateOccupate):
        flusso.modifica(
            p, utente=admin, arrivo=tra(33), partenza=tra(36), presenze={"ACC": 10}, attivita=[]
        )
    p.refresh_from_db()
    assert p.arrivo == tra(20)


def test_modifica_ricalcola_l_acconto_se_non_deciso(richiedente, contatto, admin):
    p = richiesta(richiedente, contatto, arrivo=20, partenza=25)
    flusso.approva(p, utente=admin)
    vecchio = p.acconto_centesimi
    flusso.modifica(
        p, utente=admin, arrivo=tra(20), partenza=tra(25), presenze={"ACC": 14}, attivita=[]
    )
    assert p.acconto_centesimi == vecchio // 2


def test_modifica_mantiene_l_acconto_deciso(richiedente, contatto, admin):
    p = richiesta(richiedente, contatto, arrivo=20, partenza=25)
    flusso.approva(
        p, utente=admin, acconto_centesimi=0, deciso_da="Pattuglia", motivazione="Esenzione"
    )
    assert p.acconto_deciso and p.scadenza_acconto is None
    flusso.modifica(
        p, utente=admin, arrivo=tra(20), partenza=tra(26), presenze={"ACC": 30}, attivita=[]
    )
    assert p.acconto_centesimi == 0 and p.scadenza_acconto is None


def test_acconto_che_diventa_dovuto_ha_una_scadenza(richiedente, contatto, admin):
    p = richiesta(richiedente, contatto, arrivo=20, partenza=22)  # 3 giorni: niente acconto
    flusso.approva(p, utente=admin)
    assert (p.acconto_centesimi, p.scadenza_acconto) == (0, None)
    flusso.modifica(
        p, utente=admin, arrivo=tra(20), partenza=tra(26), presenze={"ACC": 28}, attivita=[]
    )
    assert p.acconto_centesimi > 0
    assert p.scadenza_acconto > timezone.now() + datetime.timedelta(days=6)


def test_modifica_dopo_l_acconto(richiedente, contatto, admin):
    p = richiesta(richiedente, contatto, arrivo=20, partenza=25)
    flusso.approva(p, utente=admin)
    flusso.registra_pagamento(
        p, utente=admin, tipo="ACCONTO", importo_centesimi=p.acconto_centesimi, data=tra(0)
    )
    preventivo = contributo.riepilogo(p).totale
    flusso.modifica(
        p, utente=admin, arrivo=tra(21), partenza=tra(26), presenze={"ACC": 40}, attivita=[]
    )
    assert p.stato == Stato.CONFERMATA and p.arrivo == tra(21)
    assert contributo.riepilogo(p).totale == preventivo  # congelato


def test_modifica_chiede_il_consenso_solo_a_chi_ha_prenotato_prima(richiedente, contatto, admin):
    altro = User.objects.create_user("altro@example.org")
    uscita = richiesta(
        altro,
        contatto,
        arrivo=40,
        partenza=40,
        presenze={},
        attivita=[(tra(40), "USCITA_CUCINA", 20)],
    )
    dopo = richiesta(richiedente, contatto, arrivo=45, partenza=48)
    flusso.modifica(
        uscita,
        utente=admin,
        arrivo=tra(46),
        partenza=tra(46),
        presenze={},
        attivita=[(tra(46), "USCITA_CUCINA", 20)],
    )
    assert not uscita.consensi_chiesti.filter(prenotazione_esistente=dopo).exists()


# --- Orari e pagamenti ------------------------------------------------------------------


def test_orari_concordati(email, richiedente, contatto, pattuglia):
    p = richiesta(richiedente, contatto)
    email(flusso.imposta_orari, p, utente=richiedente, arrivo=datetime.time(12, 0), partenza=None)
    assert email.inviate[-1].to[0] == CASELLA_BASE and "12:00" in email.inviate[-1].body
    email(
        flusso.imposta_orari,
        p,
        utente=pattuglia,
        arrivo=datetime.time(11, 0),
        partenza=datetime.time(10, 0),
    )
    assert "mario@example.org" in email.inviate[-1].to
    with pytest.raises(PermissionDenied):
        flusso.imposta_orari(
            p, utente=User.objects.create_user("x@example.org"), arrivo=None, partenza=None
        )


def test_registra_saldo_e_acconto(email, richiedente, contatto, admin, pattuglia):
    p = richiesta(richiedente, contatto)
    flusso.approva(p, utente=admin)
    email(
        flusso.registra_pagamento,
        p,
        utente=pattuglia,
        tipo=Pagamento.Tipo.ACCONTO,
        importo_centesimi=500 * EURO,
        data=tra(0),
    )
    assert p.stato == Stato.CONFERMATA and p.scadenza_acconto is None
    assert "confermata" in email.inviate[0].subject
    flusso.registra_pagamento(
        p, utente=pattuglia, tipo=Pagamento.Tipo.SALDO, importo_centesimi=100 * EURO, data=tra(0)
    )
    assert contributo.acconto_versato(p) == 500 * EURO
    with pytest.raises(PermissionDenied):
        flusso.registra_pagamento(
            p, utente=richiedente, tipo="SALDO", importo_centesimi=1, data=tra(0)
        )
    with pytest.raises(ValidationError):
        flusso.registra_pagamento(
            p, utente=pattuglia, tipo="SALDO", importo_centesimi=0, data=tra(0)
        )


# --- Permessi sul contributo e consuntivo -----------------------------------------------


def test_permessi_sulle_voci(richiedente, contatto, admin, pattuglia):
    p = richiesta(richiedente, contatto)
    with pytest.raises(PermissionDenied):
        contributo.aggiungi_voce_libera(
            p, fase=Fase.PREVENTIVO, descrizione="Sconto", prezzo_centesimi=100, utente=pattuglia
        )
    with pytest.raises(PermissionDenied):
        contributo.modifica_quota(
            p,
            fase=Fase.PREVENTIVO,
            totale_centesimi=0,
            utente=pattuglia,
            deciso_da="P",
            motivazione="M",
        )
    voce = contributo.aggiungi_voce_libera(
        p, fase=Fase.PREVENTIVO, descrizione="Sovrapprezzo", prezzo_centesimi=100, utente=admin
    )
    with pytest.raises(PermissionDenied):
        contributo.rimuovi_voce_libera(voce, utente=pattuglia)
    contributo.rimuovi_voce_libera(voce, utente=admin)
    assert not p.righe_importo.filter(calcolata=False).exists()


def test_consuntivo_dalla_pattuglia(richiedente, contatto, admin, pattuglia):
    p = richiesta(richiedente, contatto, arrivo=10, partenza=15)
    AttivitaGiornaliera.objects.create(
        prenotazione=p, data=tra(12), tipo="GIORNATA_OSPITI", persone_previste=30
    )
    flusso.approva(p, utente=admin)
    flusso.registra_pagamento(
        p, utente=pattuglia, tipo="ACCONTO", importo_centesimi=p.acconto_centesimi, data=tra(0)
    )
    with pytest.raises(PermissionDenied):
        contributo.imposta_presenze_effettive(p, utente=richiedente, presenze={}, attivita={})
    att = p.attivita_giornaliere.get()
    riepilogo = contributo.imposta_presenze_effettive(
        p, utente=pattuglia, presenze={"ACC": 25}, attivita={att.pk: 20}
    )
    assert [r.persone for r in riepilogo.righe] == [25, 20]
    pellet = contributo.aggiungi_voce_libera(
        p, fase=Fase.CONSUNTIVO, descrizione="Pellet", prezzo_centesimi=3000, utente=pattuglia
    )
    contributo.rimuovi_voce_libera(pellet, utente=pattuglia)


# --- Configurazione ---------------------------------------------------------------------


def test_elimina_blocco_libera_le_date(richiedente, contatto, admin):
    blocco = crea_blocco(
        area=Area.objects.get(codice="ACC"), dal=tra(30), al=tra(32), motivo="Lavori"
    )
    with pytest.raises(DateOccupate):
        richiesta(richiedente, contatto, arrivo=30, partenza=33)
    elimina_blocco(blocco, utente=admin)
    richiesta(richiedente, contatto, arrivo=30, partenza=33)


def test_nuova_versione_copia_le_voci():
    associativo = Listino.objects.get(tipo="ASSOCIATIVO")
    corrente = associativo.versioni.get()
    nuova = nuova_versione(
        associativo, nome="2028", pubblicata_il=tra(0), valida_dal=tra(60), copia_da=corrente
    )
    assert nuova.voci.count() == corrente.voci.count()
    with pytest.raises(ValidationError):
        nuova_versione(associativo, nome="x", pubblicata_il=tra(10), valida_dal=tra(5))
    assert VersioneListino.objects.filter(listino=associativo).count() == 2


def test_amministrazione_entra_nell_admin_django():
    utente = User.objects.create_user("capo@example.org")
    nomina(utente, Ruolo.PATTUGLIA)
    assert not utente.is_staff
    nomina(utente, Ruolo.RESPONSABILE)
    utente.refresh_from_db()
    assert utente.is_staff and utente.has_perm("base.change_struttura")
    assert utente.has_perm("listini.add_categoria")
    revoca(utente, Ruolo.RESPONSABILE)
    utente.refresh_from_db()
    assert not utente.is_staff


# --- Anonimizzazione (D-18) -------------------------------------------------------------


def test_anonimizzazione_dopo_dieci_anni(richiedente, contatto, admin):
    p = richiesta(richiedente, contatto, note="Arriviamo col pulmino")
    Prenotazione.objects.filter(pk=p.pk).update(
        arrivo=datetime.date(2016, 7, 10), partenza=datetime.date(2016, 7, 15), stato=Stato.CHIUSA
    )
    p.refresh_from_db()
    pagamento = Pagamento.objects.create(
        prenotazione=p, tipo="ACCONTO", importo_centesimi=100, data=datetime.date(2016, 5, 1)
    )
    pagamento.ricevuta.save("bonifico.pdf", ContentFile(b"%PDF"))
    Conversazione.objects.create(prenotazione=p)
    fine_2026 = datetime.date(2026, 12, 31)
    assert not conservazione.da_anonimizzare(fine_2026).exists()
    assert list(conservazione.da_anonimizzare(datetime.date(2027, 1, 1))) == [p]
    conservazione.anonimizza(p)
    p.refresh_from_db()
    contatto.refresh_from_db()
    pagamento.refresh_from_db()
    assert p.richiedente is None and p.note == "" and p.anonimizzata_il is not None
    assert (contatto.nome, contatto.email, contatto.telefono) == ("anonimizzato", "", "")
    assert not pagamento.ricevuta and pagamento.importo_centesimi == 100
    assert not Conversazione.objects.exists()
    assert p.gruppo == "Avellino 1" and p.presenze.exists()  # statistiche
    assert not conservazione.da_anonimizzare(datetime.date(2027, 1, 1)).exists()


def test_contatto_condiviso_resta(richiedente, contatto):
    vecchia = richiesta(richiedente, contatto)
    richiesta(richiedente, contatto, arrivo=30, partenza=33)
    Prenotazione.objects.filter(pk=vecchia.pk).update(
        arrivo=datetime.date(2010, 1, 1), partenza=datetime.date(2010, 1, 3)
    )
    vecchia.refresh_from_db()
    conservazione.anonimizza(vecchia)
    contatto.refresh_from_db()
    assert contatto.nome == "Mario Rossi"
    assert Contatto.objects.count() == 1
