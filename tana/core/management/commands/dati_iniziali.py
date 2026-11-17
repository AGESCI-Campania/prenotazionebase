"""manage.py dati_iniziali — dati di partenza, idempotente (lanciato da scripts/installa.sh).

Crea aree, strutture, categorie, listini con la versione 2022/2023, la configurazione, l'albero
delle pagine del sito (D-30, P-17) e i gruppi dei ruoli di gestione con i loro permessi (§3,
§5.3, §6, D-10, D-12, P-15).
Mai sovrascrivere dati già modificati dalla gestione: si crea solo ciò che manca, e le voci di
una versione di listino solo quando si crea la versione.
"""

import datetime

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction
from wagtail.models import Collection, GroupCollectionPermission, GroupPagePermission

from tana.accounts.models import Ruolo
from tana.base.models import Area, Configurazione, Struttura
from tana.listini.models import Attivita, Categoria, Listino, VersioneListino, VoceListino
from tana.sito.inizializza import crea_sito
from tana.sito.models import HomePage

ACC, TENDE = Area.ACCANTONAMENTO, Area.TENDE

AREE = (
    (ACC, "Accantonamento", 109, "persone"),
    (TENDE, "Area tende", 6, "piazzole"),
)

U = Struttura.Uso
STRUTTURE = (
    (
        "Dormitori e stanzette staff",
        "Due dormitori, fino a 50 persone, con bagni e docce con acqua calda, e tre stanzette "
        "per lo staff. In emergenza o con forti piogge si possono condividere per la sicurezza "
        "di chi è in tenda.",
        U.SOLO_ACCANTONAMENTO,
    ),
    (
        "Cucina",
        "Per gruppi fino a 50 persone. Condivisibile previo accordo tra i gruppi.",
        U.SOLO_ACCANTONAMENTO,
    ),
    (
        "Refettorio",
        "Fino a 50 persone. Condivisibile previo accordo tra i gruppi.",
        U.SOLO_ACCANTONAMENTO,
    ),
    ("Sala polifunzionale", "140 m².", U.SOLO_ACCANTONAMENTO),
    ("Sala laboratorio", "", U.SOLO_ACCANTONAMENTO),
    ("Bagni e docce interni", "", U.SOLO_ACCANTONAMENTO),
    ("Bagni esterni", "", U.CONDIVISA),
    ("Arena con altare", "Con spiazzo e gradinata per 200 persone.", U.CONDIVISA),
    ("Area tende", "Sei piazzole.", U.SOLO_TENDE),
    ("Lavabi area tende", "", U.SOLO_TENDE),
    ("Frigorifero accantonamento", "", U.SOLO_ACCANTONAMENTO),
    ("Frigorifero area tende", "", U.SOLO_TENDE),
    ("Area fuochi accantonamento", "", U.SOLO_ACCANTONAMENTO),
    ("Area fuochi area tende", "", U.SOLO_TENDE),
    (
        "Parcheggio",
        "Solo per i veicoli essenziali: di norma si parcheggia fuori dalla base.",
        U.CONDIVISA,
    ),
)

T = Listino.Tipo
LISTINI = (
    (T.ASSOCIATIVO, "Associativo"),
    (T.EXTRA, "Extra associativo"),
    (T.AGEVOLATO, "Agevolato"),
    (T.GRATUITO, "Gratuito"),
)

# Versione iniziale: data convenzionale, anteriore a ogni prenotazione (anche importata)
VERSIONE_INIZIALE = "2022/2023"
DATA_VERSIONE_INIZIALE = datetime.date(2022, 1, 1)

A, S, UN = Attivita, VoceListino.Stagione, VoceListino.Unita
# (attività, area, stagione, unità, euro, descrizione). Voci non note (extra associativo in
# tenda, bivacco in tenda, agevolato): assenti, il preventivo risulta "da definire" (P-04).
VOCI: dict[str, tuple[tuple[str, str | None, str, str, int, str], ...]] = {
    T.ASSOCIATIVO: (
        (A.CAMPO, ACC, S.INVERNALE, UN.PERSONA_GIORNO, 10, "Campo invernale in accantonamento"),
        (A.CAMPO, ACC, S.ESTIVA, UN.PERSONA_GIORNO, 8, "Campo estivo in accantonamento"),
        (A.CAMPO, TENDE, S.NESSUNA, UN.PERSONA_GIORNO, 5, "Campo in tenda"),
        (A.BIVACCO, ACC, S.NESSUNA, UN.PERSONA_NOTTE, 10, "Bivacco"),
        (A.USCITA_CUCINA, None, S.NESSUNA, UN.PERSONA_GIORNO, 3, "Uscita con utilizzo cucina"),
        (A.USCITA_AREA_VERDE, None, S.NESSUNA, UN.PERSONA_GIORNO, 1, "Uscita area verde"),
        (
            A.GIORNATA_OSPITI,
            None,
            S.NESSUNA,
            UN.PERSONA_GIORNO,
            1,
            "Giornata genitori e ospiti (con uso cucina)",
        ),
    ),
    T.EXTRA: ((A.CAMPO, ACC, S.NESSUNA, UN.PERSONA_NOTTE, 15, "Pernotto extra associativo"),),
    T.AGEVOLATO: (),
    # Comune di Aiello del Sabato: tutte le voci a zero
    T.GRATUITO: (
        (A.CAMPO, ACC, S.NESSUNA, UN.PERSONA_GIORNO, 0, "Campo in accantonamento"),
        (A.CAMPO, TENDE, S.NESSUNA, UN.PERSONA_GIORNO, 0, "Campo in tenda"),
        (A.BIVACCO, ACC, S.NESSUNA, UN.PERSONA_NOTTE, 0, "Bivacco in accantonamento"),
        (A.BIVACCO, TENDE, S.NESSUNA, UN.PERSONA_NOTTE, 0, "Bivacco in tenda"),
        (A.USCITA_CUCINA, None, S.NESSUNA, UN.PERSONA_GIORNO, 0, "Uscita con utilizzo cucina"),
        (A.USCITA_AREA_VERDE, None, S.NESSUNA, UN.PERSONA_GIORNO, 0, "Uscita area verde"),
        (A.GIORNATA_OSPITI, None, S.NESSUNA, UN.PERSONA_GIORNO, 0, "Giornata genitori e ospiti"),
    ),
}

# (codice, nome, prioritaria, listino di default, richiede specifica)
CATEGORIE = (
    (
        "foca-regionale",
        "Fo.Ca. regionale (compresi i campi di Formazione Capi delle Zone, es. CFT)",
        True,
        T.AGEVOLATO,
        False,
    ),
    ("foca-nazionale", "Fo.Ca. nazionale (CFA)", True, T.ASSOCIATIVO, False),
    ("eventi-regionali", "Eventi regionali", True, T.AGEVOLATO, False),
    ("comune", "Comune di Aiello del Sabato", True, T.GRATUITO, False),
    ("gruppo-agesci", "Gruppo AGESCI", False, T.ASSOCIATIVO, False),
    ("zone-agesci", "Zone AGESCI", False, T.ASSOCIATIVO, False),
    ("gruppo-cngei", "Gruppo CNGEI", False, T.EXTRA, False),
    ("altra-associazione", "Gruppo scout altra associazione", False, T.EXTRA, True),
    ("terzo-settore", "Associazione terzo settore", False, T.EXTRA, True),
    ("altro", "Altro (da specificare)", False, T.EXTRA, True),
)


# Permessi iniziali dei gruppi dei ruoli, assegnati solo quando il gruppo si crea: poi li
# modifica l'amministratore (es. chi riceve le notifiche di gestione)
# Strutture e categorie si modificano nell'admin Django (F5)
_ADMIN_DJANGO = tuple(
    f"{app}.{azione}_{modello}"
    for app, modello in (("base", "struttura"), ("listini", "categoria"))
    for azione in ("view", "add", "change", "delete")
)
# Editor del sito (P-15): Redazione, e anche amministratore e responsabile
_EDITOR = ("wagtailadmin.access_admin", "sito.change_impostazionisito")
PERMESSI_DEI_RUOLI: dict[str, tuple[str, ...]] = {
    Ruolo.AMMINISTRATORE: ("prenotazioni.ricevi_notifiche_gestione", *_ADMIN_DJANGO, *_EDITOR),
    Ruolo.RESPONSABILE: ("prenotazioni.ricevi_notifiche_gestione", *_ADMIN_DJANGO, *_EDITOR),
    Ruolo.REDAZIONE: _EDITOR,
}
RUOLI_EDITOR = (Ruolo.AMMINISTRATORE, Ruolo.RESPONSABILE, Ruolo.REDAZIONE)
PERMESSI_PAGINE = ("add", "change", "publish", "lock", "unlock")
PERMESSI_ARCHIVIO = (
    ("wagtailimages", "image"),
    ("wagtaildocs", "document"),
)


class Command(BaseCommand):
    help = "Crea i dati iniziali di Tana se mancano (idempotente)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--senza-sito",
            action="store_true",
            help="Non crea le pagine del sito (test che non le usano: più veloci).",
        )

    @transaction.atomic
    def handle(self, *args, senza_sito: bool = False, **options) -> None:
        self.creati = 0
        aree = self._aree()
        self._strutture()
        listini = self._listini(aree)
        self._categorie(listini)
        if not senza_sito:
            self.creati += crea_sito()
        self._gruppi()
        Configurazione.corrente()
        self.stdout.write(f"Dati iniziali: {self.creati} elementi creati.")

    def _conta(self, creato: bool) -> None:
        self.creati += int(creato)

    def _aree(self) -> dict[str, Area]:
        aree = {}
        for ordine, (codice, nome, capienza, unita) in enumerate(AREE):
            area, creata = Area.objects.get_or_create(
                codice=codice,
                defaults={
                    "nome": nome,
                    "capienza": capienza,
                    "unita_capienza": unita,
                    "ordine": ordine,
                },
            )
            self._conta(creata)
            aree[codice] = area
        return aree

    def _strutture(self) -> None:
        for ordine, (nome, descrizione, uso) in enumerate(STRUTTURE):
            _, creata = Struttura.objects.get_or_create(
                nome=nome, defaults={"descrizione": descrizione, "uso": uso, "ordine": ordine}
            )
            self._conta(creata)

    def _listini(self, aree: dict[str, Area]) -> dict[str, Listino]:
        listini: dict[str, Listino] = {}
        for tipo, nome in LISTINI:
            listino, creato = Listino.objects.get_or_create(tipo=tipo, defaults={"nome": nome})
            self._conta(creato)
            listini[tipo] = listino
            if listino.versioni.exists():
                continue
            versione = VersioneListino.objects.create(
                listino=listino,
                nome=VERSIONE_INIZIALE,
                pubblicata_il=DATA_VERSIONE_INIZIALE,
                valida_dal=DATA_VERSIONE_INIZIALE,
                note="Valori del listino 2022/2023, senza il forfait anti-COVID.",
            )
            self._conta(True)
            for attivita, area, stagione, unita, euro, descrizione in VOCI[tipo]:
                VoceListino.objects.create(
                    versione=versione,
                    attivita=attivita,
                    area=aree[area] if area else None,
                    stagione=stagione,
                    unita=unita,
                    importo_centesimi=euro * 100,
                    descrizione=descrizione,
                )
                self._conta(True)
        return listini

    def _categorie(self, listini: dict[str, Listino]) -> None:
        for ordine, (codice, nome, prioritaria, listino, specifica) in enumerate(CATEGORIE):
            _, creata = Categoria.objects.get_or_create(
                codice=codice,
                defaults={
                    "nome": nome,
                    "prioritaria": prioritaria,
                    "listino_default": listini[listino],
                    "richiede_specifica": specifica,
                    "ordine": ordine,
                },
            )
            self._conta(creata)

    def _gruppi(self) -> None:
        for ruolo in Ruolo:
            gruppo, creato = Group.objects.get_or_create(name=ruolo.label)
            self._conta(creato)
            if not creato:
                continue
            for nome in PERMESSI_DEI_RUOLI.get(ruolo, ()):
                app, codice = nome.split(".")
                gruppo.permissions.add(
                    Permission.objects.get(content_type__app_label=app, codename=codice)
                )
            if ruolo in RUOLI_EDITOR:
                self._editor(gruppo)

    def _editor(self, gruppo: Group) -> None:
        """Pagine del sito e archivio di immagini e documenti (P-15)."""
        home = HomePage.objects.first()
        if home is not None:
            for tipo in PERMESSI_PAGINE:
                GroupPagePermission.objects.get_or_create(
                    group=gruppo,
                    page=home,
                    permission=Permission.objects.get(
                        content_type__app_label="wagtailcore", codename=f"{tipo}_page"
                    ),
                )
        radice = Collection.get_first_root_node()
        for app, modello in PERMESSI_ARCHIVIO:
            for azione in ("add", "change", "choose"):
                GroupCollectionPermission.objects.get_or_create(
                    group=gruppo,
                    collection=radice,
                    permission=Permission.objects.get(
                        content_type__app_label=app, codename=f"{azione}_{modello}"
                    ),
                )
