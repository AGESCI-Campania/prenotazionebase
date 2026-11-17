import datetime

import pytest
from django.core.exceptions import ValidationError

from tana.base.models import Area, Configurazione
from tana.core.services import storico
from tana.listini.models import Categoria, Listino, VersioneListino, VoceListino
from tana.prenotazioni import contributo
from tana.prenotazioni.contributo import Fase, PreventivoCongelato
from tana.prenotazioni.models import AttivitaGiornaliera, Pagamento, PresenzaArea, Stato
from tana.prenotazioni.services import crea_prenotazione

pytestmark = pytest.mark.django_db

d = datetime.date
EURO = 100


def prenota(arrivo, partenza, *, acc=0, tende=0, categoria="gruppo-agesci", **campi):
    prenotazione = crea_prenotazione(
        categoria=Categoria.objects.get(codice=categoria),
        arrivo=arrivo,
        partenza=partenza,
        data_richiesta=campi.pop("data_richiesta", d(2026, 11, 17)),
        **campi,
    )
    for codice, persone in (("ACC", acc), ("TENDE", tende)):
        if persone:
            PresenzaArea.objects.create(
                prenotazione=prenotazione,
                area=Area.objects.get(codice=codice),
                persone_previste=persone,
            )
    return prenotazione


def giornata(prenotazione, data, tipo, persone):
    return AttivitaGiornaliera.objects.create(
        prenotazione=prenotazione, data=data, tipo=tipo, persone_previste=persone
    )


@pytest.fixture(autouse=True)
def _dati(dati_iniziali):
    pass


# --- Esempi verificati del §5.4 ---------------------------------------------------------


def test_esempio_accantonamento_estivo():
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28)  # lun–sab
    riepilogo = contributo.aggiorna_preventivo(prenotazione)
    assert riepilogo.totale == 1344 * EURO
    assert [(r.quantita, r.prezzo_centesimi) for r in riepilogo.righe] == [(28 * 6, 8 * EURO)]
    assert contributo.acconto_previsto(prenotazione) == 672 * EURO


def test_esempio_congiunta():
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=20, tende=12)
    riepilogo = contributo.aggiorna_preventivo(prenotazione)
    assert riepilogo.totale == 1320 * EURO
    assert riepilogo.per_area == {"Accantonamento": 960 * EURO, "Area tende": 360 * EURO}
    assert contributo.acconto_previsto(prenotazione) == 660 * EURO


def test_esempio_a_cavallo_di_stagione():
    prenotazione = prenota(d(2027, 3, 13), d(2027, 3, 17), acc=20)
    riepilogo = contributo.aggiorna_preventivo(prenotazione)
    assert riepilogo.totale == 920 * EURO
    righe = {r.stagione: (r.quantita, r.prezzo_centesimi) for r in riepilogo.righe}
    assert righe == {"INVERNALE": (20 * 3, 10 * EURO), "ESTIVA": (20 * 2, 8 * EURO)}
    assert contributo.acconto_previsto(prenotazione) == 460 * EURO


def test_esempio_bivacco():
    prenotazione = prenota(d(2027, 7, 17), d(2027, 7, 18), acc=15)  # sab–dom
    riepilogo = contributo.aggiorna_preventivo(prenotazione)
    assert riepilogo.totale == 150 * EURO
    (riga,) = riepilogo.righe
    assert (riga.attivita, riga.unita, riga.quantita) == ("BIVACCO", "PERSONA_NOTTE", 15)
    assert contributo.acconto_previsto(prenotazione) == 0  # 2 giorni ≤ 3


# --- Listino e versione -----------------------------------------------------------------


def test_extra_associativo_a_notti():
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=10, categoria="gruppo-cngei")
    riepilogo = contributo.aggiorna_preventivo(prenotazione)
    assert riepilogo.totale == 10 * 5 * 15 * EURO  # 5 notti × 15 €


def test_voci_mancanti_da_definire():
    # Extra associativo in tenda e bivacco: voci non ancora nel listino (P-04)
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=10, tende=6, categoria="altro")
    riepilogo = contributo.aggiorna_preventivo(prenotazione)
    assert riepilogo.da_definire
    assert riepilogo.per_area == {"Accantonamento": 750 * EURO, "Area tende": None}
    assert contributo.acconto_previsto(prenotazione) is None
    bivacco = prenota(d(2027, 8, 7), d(2027, 8, 8), acc=10, categoria="altro")
    assert contributo.aggiorna_preventivo(bivacco).da_definire


def test_agevolato_tutto_da_definire():
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=40, categoria="foca-regionale")
    riepilogo = contributo.aggiorna_preventivo(prenotazione)
    assert riepilogo.da_definire
    assert all(r.da_definire for r in riepilogo.righe)


def test_categoria_prioritaria_richiesta_usa_l_associativo():
    prenotazione = prenota(
        d(2027, 7, 19),
        d(2027, 7, 24),
        acc=28,
        categoria="foca-regionale",
        categoria_prioritaria_richiesta=True,
    )
    assert contributo.listino_applicato(prenotazione).tipo == Listino.Tipo.ASSOCIATIVO
    assert contributo.aggiorna_preventivo(prenotazione).totale == 1344 * EURO
    # Concessa: si passa all'agevolato, anche con la versione associativa già congelata
    prenotazione.categoria_prioritaria_concessa = True
    prenotazione.save()
    riepilogo = contributo.aggiorna_preventivo(prenotazione)
    assert prenotazione.versione_listino.listino.tipo == Listino.Tipo.AGEVOLATO
    assert riepilogo.da_definire


def test_comune_gratuito():
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=50, tende=20, categoria="comune")
    assert contributo.aggiorna_preventivo(prenotazione).totale == 0
    assert contributo.acconto_previsto(prenotazione) == 0


def test_versione_congelata_sulla_prenotazione():
    prenotazione = prenota(d(2028, 2, 7), d(2028, 2, 12), acc=10, data_richiesta=d(2027, 9, 15))
    contributo.aggiorna_preventivo(prenotazione)
    vecchia = prenotazione.versione_listino
    # Compare una versione che per D-09 sarebbe applicabile: la prenotazione resta sul vecchio
    nuova = VersioneListino.objects.create(
        listino=vecchia.listino, nome="2028", pubblicata_il=d(2027, 9, 1), valida_dal=d(2028, 1, 1)
    )
    VoceListino.objects.create(
        versione=nuova,
        attivita="CAMPO",
        area=Area.objects.get(codice="ACC"),
        stagione="NESSUNA",
        unita="PERSONA_GIORNO",
        importo_centesimi=20 * EURO,
    )
    riepilogo = contributo.aggiorna_preventivo(prenotazione)
    assert prenotazione.versione_listino == vecchia
    assert riepilogo.totale == 10 * 6 * 10 * EURO


def test_versione_pubblicata_prima_della_richiesta():
    listino = Listino.objects.get(tipo="ASSOCIATIVO")
    nuova = VersioneListino.objects.create(
        listino=listino, nome="2028", pubblicata_il=d(2027, 9, 1), valida_dal=d(2028, 1, 1)
    )
    prenotazione = prenota(d(2028, 2, 7), d(2028, 2, 12), acc=10, data_richiesta=d(2027, 9, 15))
    assert contributo.versione_da_applicare(prenotazione) == nuova


# --- Attività in giornata e acconto -----------------------------------------------------


def test_uscite_e_giornata_ospiti():
    soggiorno = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28)
    giornata(soggiorno, d(2027, 7, 21), AttivitaGiornaliera.Tipo.GIORNATA_OSPITI, 40)
    riepilogo = contributo.aggiorna_preventivo(soggiorno)
    assert riepilogo.totale == (1344 + 40) * EURO
    assert riepilogo.righe[-1].descrizione == "Giornata genitori e ospiti – 21/07/2027"

    uscita = prenota(d(2027, 7, 25), d(2027, 7, 25))
    giornata(uscita, d(2027, 7, 25), AttivitaGiornaliera.Tipo.USCITA_CUCINA, 30)
    giornata(uscita, d(2027, 7, 25), AttivitaGiornaliera.Tipo.USCITA_AREA_VERDE, 5)
    assert contributo.aggiorna_preventivo(uscita).totale == (90 + 5) * EURO
    # Attività in giornata: niente bonifico, si paga all'arrivo (D-13)
    assert contributo.acconto_previsto(uscita) == 0


@pytest.mark.parametrize(("partenza", "acconto"), [(d(2027, 7, 21), 0), (d(2027, 7, 22), 128)])
def test_soglia_di_esenzione_dall_acconto(partenza, acconto):
    prenotazione = prenota(d(2027, 7, 19), partenza, acc=8)
    contributo.aggiorna_preventivo(prenotazione)
    assert contributo.acconto_previsto(prenotazione) == acconto * EURO


def test_acconto_arrotondato_al_centesimo():
    Configurazione.objects.filter(pk=1).update(acconto_percentuale=33)
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=1)  # 48,00 €
    contributo.aggiorna_preventivo(prenotazione)
    assert contributo.acconto_previsto(prenotazione) == 1584  # 15,84 €
    contributo.aggiungi_voce_libera(
        prenotazione, fase=Fase.PREVENTIVO, descrizione="Pellet", prezzo_centesimi=50
    )
    # 33% di 48,50 € = 16,005 → 16,01 €
    assert contributo.acconto_previsto(prenotazione) == 1601


def test_soggiorno_senza_notti_rifiutato():
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 19), acc=10)
    with pytest.raises(ValidationError):
        contributo.aggiorna_preventivo(prenotazione)


# --- Interventi dell'amministratore -----------------------------------------------------


def test_valorizzazione_resta_dopo_il_ricalcolo(django_user_model):
    admin = django_user_model.objects.create_user("admin@example.org")
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=10, tende=6, categoria="altro")
    riepilogo = contributo.aggiorna_preventivo(prenotazione)
    (mancante,) = [r for r in riepilogo.righe if r.da_definire]
    with pytest.raises(ValidationError):
        contributo.valorizza_riga(
            mancante, prezzo_centesimi=7 * EURO, utente=admin, deciso_da="", motivazione=""
        )
    contributo.valorizza_riga(
        mancante,
        prezzo_centesimi=7 * EURO,
        utente=admin,
        deciso_da="Pattuglia",
        motivazione="Tariffa tenda extra associativo in attesa del listino",
    )
    assert contributo.riepilogo(prenotazione).totale == (750 + 6 * 6 * 7) * EURO
    # Più giorni: la voce valorizzata si riapplica alla nuova quantità
    prenotazione.partenza = d(2027, 7, 25)
    prenotazione.save()
    riepilogo = contributo.aggiorna_preventivo(prenotazione)
    assert riepilogo.totale == (10 * 6 * 15 + 6 * 7 * 7) * EURO
    assert storico(prenotazione).filter(deciso_da="Pattuglia").count() == 1


def test_voce_libera_e_modifica_quota(django_user_model):
    admin = django_user_model.objects.create_user("admin@example.org")
    prenotazione = prenota(
        d(2027, 7, 19), d(2027, 7, 24), acc=28, esclusiva_richiesta=True, esclusiva_concessa=True
    )
    contributo.aggiorna_preventivo(prenotazione)
    contributo.aggiungi_voce_libera(
        prenotazione,
        fase=Fase.PREVENTIVO,
        descrizione="Sovrapprezzo esclusiva",
        prezzo_centesimi=100 * EURO,
        utente=admin,
        deciso_da="Pattuglia",
        motivazione="Esclusiva per campo di specialità",
    )
    assert contributo.riepilogo(prenotazione).totale == 1444 * EURO

    riepilogo = contributo.modifica_quota(
        prenotazione,
        fase=Fase.PREVENTIVO,
        totale_centesimi=1000 * EURO,
        utente=admin,
        deciso_da="Responsabile della base",
        motivazione="Gruppo in difficoltà economica",
    )
    assert (riepilogo.totale_calcolato, riepilogo.totale) == (1444 * EURO, 1000 * EURO)
    assert riepilogo.righe[-1].rettifica
    # Il ricalcolo non tocca voci libere e rettifiche
    riepilogo = contributo.aggiorna_preventivo(prenotazione)
    assert riepilogo.totale == 1000 * EURO
    # Azzeramento: sostituisce la rettifica precedente
    riepilogo = contributo.modifica_quota(
        prenotazione,
        fase=Fase.PREVENTIVO,
        totale_centesimi=0,
        utente=admin,
        deciso_da="Pattuglia",
        motivazione="Ospiti della Regione",
    )
    assert riepilogo.totale == 0
    assert sum(r.rettifica for r in riepilogo.righe) == 1
    assert storico(prenotazione).count() == 3


def test_modifica_quota_richiede_la_decisione():
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28)
    contributo.aggiorna_preventivo(prenotazione)
    with pytest.raises(ValidationError):
        contributo.modifica_quota(
            prenotazione,
            fase=Fase.PREVENTIVO,
            totale_centesimi=0,
            utente=None,
            deciso_da="Pattuglia",
            motivazione="",
        )
    assert contributo.riepilogo(prenotazione).totale == 1344 * EURO


def test_preventivo_congelato_dopo_l_acconto():
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28)
    contributo.aggiorna_preventivo(prenotazione)
    Pagamento.objects.create(
        prenotazione=prenotazione,
        tipo=Pagamento.Tipo.ACCONTO,
        importo_centesimi=672 * EURO,
        data=d(2027, 5, 1),
    )
    with pytest.raises(PreventivoCongelato):
        contributo.aggiorna_preventivo(prenotazione)
    with pytest.raises(PreventivoCongelato):
        contributo.aggiungi_voce_libera(
            prenotazione, fase=Fase.PREVENTIVO, descrizione="Pellet", prezzo_centesimi=1
        )


# --- Consuntivo e saldo -----------------------------------------------------------------


def test_consuntivo_con_persone_effettive_e_saldo():
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=20, tende=12)
    ospiti = giornata(prenotazione, d(2027, 7, 21), AttivitaGiornaliera.Tipo.GIORNATA_OSPITI, 40)
    contributo.aggiorna_preventivo(prenotazione)
    Pagamento.objects.create(
        prenotazione=prenotazione,
        tipo=Pagamento.Tipo.ACCONTO,
        importo_centesimi=660 * EURO,
        data=d(2027, 5, 1),
    )
    prenotazione.stato = Stato.SVOLTA
    prenotazione.save()
    prenotazione.presenze.filter(area__codice="ACC").update(persone_effettive=18)
    ospiti.persone_effettive = 35
    ospiti.save()

    riepilogo = contributo.aggiorna_consuntivo(prenotazione)
    # Tende senza effettive: si usano le previste, riga stimata
    assert riepilogo.totale == (18 * 6 * 8 + 12 * 6 * 5 + 35) * EURO
    assert [r.stimata for r in riepilogo.righe] == [False, True, False]
    contributo.aggiungi_voce_libera(
        prenotazione,
        fase=Fase.CONSUNTIVO,
        descrizione="Riscaldamento a pellet",
        prezzo_centesimi=4250,
    )
    assert contributo.saldo(prenotazione) == (864 + 360 + 35 - 660) * EURO + 4250


def test_consuntivo_con_la_versione_del_preventivo():
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=28)
    with pytest.raises(ValidationError):
        contributo.aggiorna_consuntivo(prenotazione)
    contributo.aggiorna_preventivo(prenotazione)
    versione = prenotazione.versione_listino
    # Anche cambiando categoria il consuntivo resta sulla versione del preventivo
    prenotazione.categoria = Categoria.objects.get(codice="gruppo-cngei")
    riepilogo = contributo.aggiorna_consuntivo(prenotazione)
    assert riepilogo.totale == 1344 * EURO
    assert contributo.riepilogo(prenotazione, Fase.CONSUNTIVO).righe[0].voce.versione == versione


def test_calcolo_delle_righe_come_nel_mockup():
    prenotazione = prenota(d(2027, 7, 19), d(2027, 7, 24), acc=20, tende=12)
    giornata(prenotazione, d(2027, 7, 21), AttivitaGiornaliera.Tipo.GIORNATA_OSPITI, 1)
    righe = contributo.aggiorna_preventivo(prenotazione).righe
    assert [r.calcolo for r in righe] == [
        "8,00 € × 20 persone × 6 giorni",
        "5,00 € × 12 persone × 6 giorni",
        "1,00 € × 1 persona × 1 giorno",
    ]
    bivacco = prenota(d(2027, 8, 7), d(2027, 8, 8), acc=15)
    assert (
        contributo.simula(
            contributo.Soggiorno(
                categoria=bivacco.categoria,
                arrivo=bivacco.arrivo,
                partenza=bivacco.partenza,
                presenze=[(Area.objects.get(codice="ACC"), 15)],
            )
        )[0].calcolo
        == "10,00 € × 15 persone × 1 notte"
    )
    libera = contributo.aggiungi_voce_libera(
        prenotazione, fase=Fase.PREVENTIVO, descrizione="Pellet", prezzo_centesimi=4250
    )
    assert libera.calcolo == "42,50 €"
    tende_extra = prenota(d(2027, 9, 1), d(2027, 9, 3), tende=6, categoria="gruppo-cngei")
    (riga,) = contributo.aggiorna_preventivo(tende_extra).righe
    assert riga.calcolo == "importo da definire × 6 persone × 3 giorni"
