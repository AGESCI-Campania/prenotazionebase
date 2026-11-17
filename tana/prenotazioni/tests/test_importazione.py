"""Import SuperSaaS con CSV sintetici (i dati reali non entrano mai nel repo)."""

import csv
import datetime
import io

import pytest
from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed
from django.core.management import CommandError, call_command
from openpyxl import load_workbook

from tana.accounts.models import User
from tana.prenotazioni import contributo, importazione
from tana.prenotazioni.models import Occupazione, Prenotazione, Stato

pytestmark = pytest.mark.django_db

INTESTAZIONI = [
    "Inizio",
    "Fine",
    "Creato da",
    "Aggiornato da",
    "ID",
    "Nome e cognome",
    "Email",
    "Telefono",
    "Cellulare",
    "Partecipanti (inclusi i capi)",
    "Gruppo",
    "Stato",
    "Creato il",
    "Aggiornato il",
    "Unità presenti",
    "Note",
]
OGGI = datetime.date(2026, 11, 17)


@pytest.fixture(autouse=True)
def _dati(dati, monkeypatch):
    # Stati (passata/futura) calcolati rispetto a una data fissa
    monkeypatch.setattr(importazione, "_oggi", lambda: OGGI)


def riga(
    id,
    pacchetto,
    inizio,
    fine,
    gruppo="Avellino 1",
    partecipanti="30",
    stato="In attesa di approvazione  ",
    admin="",
    email="capo@example.org",
    note="",
    unita="3,4",
):
    return {
        "_": pacchetto,
        "Inizio": inizio,
        "Fine": fine,
        "Creato da": admin,
        "Aggiornato da": "",
        "ID": id,
        "Nome e cognome": "Mario  Rossi",
        "Email": email,
        "Telefono": "",
        "Cellulare": " 333 1234567 ",
        "Partecipanti (inclusi i capi)": partecipanti,
        "Gruppo": gruppo,
        "Stato": stato,
        "Creato il": "3/9/2026     10:00",
        "Aggiornato il": "",
        "Unità presenti": unita,
        "Note": note,
    }


def scrivi(percorso, calendario, righe):
    with open(percorso, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([calendario, *INTESTAZIONI])
        for r in righe:
            w.writerow([r["_"], *(r[c] for c in INTESTAZIONI)])
    return percorso


@pytest.fixture
def csv_esempio(tmp_path):
    acc = scrivi(
        tmp_path / "prenotazioni.csv",
        "prenotazioni",
        [
            # Passata e approvata → SVOLTA; fine a mezzanotte = partenza il giorno prima
            riga("1", "6 Giorni", "19/7/2026     15:00", "25/7/2026     0:00", stato="Approvato  "),
            # Futura in attesa, congiunta con la riga 11 delle tende, chiede l'esclusiva nelle note
            riga(
                "2",
                "3 Giorni",
                "4/12/2026   15:00",
                "6/12/2026   10:00",
                partecipanti="circa 20",
                note="Vorremmo l'uso esclusivo",
            ),
            # Data riservata dall'amministratore
            riga(
                "3",
                "3 Giorni",
                "8/1/2027   15:00",
                "10/1/2027   12:00",
                gruppo="CFM LC",
                partecipanti="TBD",
                admin="admin@example.org",
                email="",
            ),
            # Uscita in giornata, CNGEI
            riga(
                "4",
                "Giornata",
                "13/12/2026  9:00",
                "13/12/2026  18:00",
                gruppo="Sezione di Casoria",
                email="x@cngei.it",
            ),
            # Riga di prova
            riga(
                "5",
                "Giornata",
                "11/1/2027  9:00",
                "11/1/2027  10:00",
                gruppo="12121",
                admin="admin@example.org",
            ),
        ],
    )
    tende = scrivi(
        tmp_path / "campotende.csv",
        "campotende",
        [
            riga(
                "11",
                "3 Giorni",
                "4/12/2026  14:00",
                "6/12/2026  11:00",
                partecipanti="12",
                email="altro@example.org",
            ),
            # Passata, in attesa → NON_SVOLTA
            riga(
                "12",
                "Bivacco",
                "1/8/2026  18:00",
                "2/8/2026  10:00",
                gruppo="Salerno 5",
                partecipanti="8",
            ),
            # Gruppo vero inserito dall'amministratore con i propri dati come referente
            riga(
                "13",
                "3 Giorni",
                "15/8/2026  15:00",
                "17/8/2026  10:00",
                gruppo="Caserta 4",
                admin="admin@example.org",
                email="admin@example.org",
            ),
        ],
    )
    return acc, tende


def test_proposte(csv_esempio):
    elenco = {
        p.chiave: p
        for p in importazione.proposte(
            *csv_esempio, oggi=OGGI, amministratori=[" Admin@example.org "]
        )
    }
    assert set(elenco) == {
        "acc-1",
        "acc-2+tende-11",
        "acc-3",
        "acc-4",
        "acc-5",
        "tende-12",
        "tende-13",
    }
    assert any("referente da inserire" in a for a in elenco["tende-13"].anomalie)
    assert not elenco["tende-13"].referente and elenco["acc-1"].referente
    svolta = elenco["acc-1"]
    assert (svolta.stato, svolta.principale.partenza) == (Stato.SVOLTA, datetime.date(2026, 7, 24))
    assert svolta.categoria == "gruppo-agesci" and svolta.persone_acc == 30
    congiunta = elenco["acc-2+tende-11"]
    assert congiunta.unione and congiunta.stato == Stato.RICHIESTA
    assert (congiunta.persone_acc, congiunta.persone_tende) == (20, 12)
    assert congiunta.esclusiva == "RICHIESTA"
    assert any("circa 20" in a for a in congiunta.anomalie)
    riservata = elenco["acc-3"]
    assert riservata.prioritaria_senza_contatti and riservata.categoria == "foca-regionale"
    assert riservata.persone_acc is None
    uscita = elenco["acc-4"]
    assert uscita.uscita == "USCITA_CUCINA" and uscita.categoria == "gruppo-cngei"
    assert elenco["acc-5"].azione == "SCARTA"
    assert elenco["tende-12"].stato == Stato.NON_SVOLTA


def test_csv_con_colonne_sbagliate(tmp_path):
    cattivo = tmp_path / "x.csv"
    cattivo.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(importazione.ErroreImport):
        importazione.leggi(cattivo, "acc")


def revisione(tmp_path, csv_esempio, **modifiche):
    """Dry-run, poi modifica del file come farebbe l'operatore."""
    report = tmp_path / "revisione.xlsx"
    call_command(
        "import_supersaas",
        accantonamento=csv_esempio[0],
        tende=csv_esempio[1],
        dry_run=True,
        report=report,
        amministratori="admin@example.org",
        stdout=io.StringIO(),
    )
    libro = load_workbook(report)
    foglio = libro["Proposte"]
    intestazioni = [c.value for c in foglio[1]]
    for riga_excel in foglio.iter_rows(min_row=2):
        chiave = riga_excel[0].value
        for colonna, valore in modifiche.get(chiave, {}).items():
            riga_excel[intestazioni.index(colonna)].value = valore
    libro.save(report)
    return report


def test_dry_run_non_scrive(tmp_path, csv_esempio):
    revisione(tmp_path, csv_esempio)
    assert not Prenotazione.objects.exists()


def test_apply_senza_persone_si_ferma(tmp_path, csv_esempio):
    report = revisione(tmp_path, csv_esempio)
    with pytest.raises(CommandError, match="indica le persone"):
        call_command(
            "import_supersaas",
            accantonamento=csv_esempio[0],
            tende=csv_esempio[1],
            apply=True,
            decisioni=report,
        )
    assert not Prenotazione.objects.exists()


def test_apply(tmp_path, csv_esempio, mailoutbox):
    report = revisione(
        tmp_path,
        csv_esempio,
        **{
            "acc-3": {"Persone accantonamento": 45},
            "acc-2+tende-11": {"Esclusiva (NO/RICHIESTA/CONCESSA)": "NO"},
            "acc-4": {"Uscita in giornata (tipo)": "USCITA_AREA_VERDE"},
        },
    )
    call_command(
        "import_supersaas",
        accantonamento=csv_esempio[0],
        tende=csv_esempio[1],
        apply=True,
        decisioni=report,
        stdout=io.StringIO(),
    )
    assert Prenotazione.objects.count() == 6  # 7 proposte, una scartata
    assert Prenotazione.objects.get(id_supersaas="tende-13").contatto is None
    assert mailoutbox == []  # storico: nessuna email
    svolta = Prenotazione.objects.get(id_supersaas="acc-1")
    assert svolta.stato == Stato.SVOLTA and svolta.numero.startswith("2026-")
    assert svolta.data_richiesta == datetime.date(2026, 9, 3)
    assert svolta.contatto.telefono == "333 1234567" and svolta.richiedente is None
    assert svolta.unita == ["EG", "RS"]
    assert contributo.riepilogo(svolta).totale is not None
    assert "Importata da SuperSaaS" in svolta.note
    congiunta = Prenotazione.objects.get(id_supersaas="acc-2+tende-11")
    assert {p.area.codice: p.persone_previste for p in congiunta.presenze.all()} == {
        "ACC": 20,
        "TENDE": 12,
    }
    riservata = Prenotazione.objects.get(id_supersaas="acc-3")
    assert riservata.contatto is None and riservata.categoria_prioritaria_concessa
    uscita = Prenotazione.objects.get(id_supersaas="acc-4")
    assert (
        uscita.attivita_giornaliere.get().tipo == "USCITA_AREA_VERDE"
        and not uscita.occupazioni.exists()
    )
    non_svolta = Prenotazione.objects.get(id_supersaas="tende-12")
    assert non_svolta.stato == Stato.NON_SVOLTA and not non_svolta.occupazioni.get().attiva
    # svolta, congiunta ×2, riservata (tende-13 è passata e non svolta: occupazione non attiva)
    assert Occupazione.objects.filter(attiva=True).count() == 4


def test_unione_rifiutata_diventa_due_prenotazioni(tmp_path, csv_esempio):
    report = revisione(
        tmp_path,
        csv_esempio,
        **{"acc-3": {"Persone accantonamento": 45}, "acc-2+tende-11": {"Unione (SI/NO)": "NO"}},
    )
    call_command(
        "import_supersaas",
        accantonamento=csv_esempio[0],
        tende=csv_esempio[1],
        apply=True,
        decisioni=report,
        stdout=io.StringIO(),
    )
    coppia = Prenotazione.objects.filter(arrivo=datetime.date(2026, 12, 4))
    assert coppia.count() == 2 and {p.presenze.get().area.codice for p in coppia} == {
        "ACC",
        "TENDE",
    }


def test_conflitto_interrompe_tutto(tmp_path, csv_esempio):
    from tana.base.models import Area
    from tana.prenotazioni.services import crea_blocco

    crea_blocco(
        area=Area.objects.get(codice="ACC"),
        dal=datetime.date(2027, 1, 8),
        al=datetime.date(2027, 1, 8),
        motivo="Lavori",
    )
    report = revisione(tmp_path, csv_esempio, **{"acc-3": {"Persone accantonamento": 45}})
    with pytest.raises(CommandError, match="acc-3: date occupate"):
        call_command(
            "import_supersaas",
            accantonamento=csv_esempio[0],
            tende=csv_esempio[1],
            apply=True,
            decisioni=report,
        )
    assert not Prenotazione.objects.exists()  # un'unica transazione


def test_riga_senza_decisione(tmp_path, csv_esempio):
    report = revisione(tmp_path, csv_esempio, **{"acc-3": {"Persone accantonamento": 45}})
    libro = load_workbook(report)
    libro["Proposte"].delete_rows(2)
    libro.save(report)
    with pytest.raises(CommandError, match="manca la decisione"):
        call_command(
            "import_supersaas",
            accantonamento=csv_esempio[0],
            tende=csv_esempio[1],
            apply=True,
            decisioni=report,
        )


def test_collegamento_all_account(tmp_path, csv_esempio):
    report = revisione(tmp_path, csv_esempio, **{"acc-3": {"Persone accantonamento": 45}})
    call_command(
        "import_supersaas",
        accantonamento=csv_esempio[0],
        tende=csv_esempio[1],
        apply=True,
        decisioni=report,
        stdout=io.StringIO(),
    )
    # L'amministratore che ha inserito righe con i propri dati non riceve prenotazioni
    amministratore = User.objects.create_user("admin@example.org")
    EmailAddress.objects.create(
        user=amministratore, email="admin@example.org", verified=True, primary=True
    )
    importazione.collega_a_utente(amministratore, "admin@example.org")
    assert not Prenotazione.objects.filter(richiedente=amministratore).exists()
    utente = User.objects.create_user("Capo@Example.org")
    indirizzo = EmailAddress.objects.create(
        user=utente, email="capo@example.org", verified=True, primary=True
    )
    email_confirmed.send(sender=EmailAddress, request=None, email_address=indirizzo)
    assert set(
        Prenotazione.objects.filter(richiedente=utente).values_list("id_supersaas", flat=True)
    ) == {
        "acc-1",
        "acc-2+tende-11",
        "tende-12",
    }
