"""Contenuti iniziali del sito (P-17): pagine, indirizzi e testi di partenza.

I testi di home, La storia, Gianni Sabatino e Info sono quelli del Google Site forniti da Andrea
(17/11/2026), in `contenuti/*.json`; il regolamento viene dal PDF di gennaio 2023. Dove manca un
testo c'è un segnaposto «Da completare» per la redazione. `manage.py dati_iniziali` crea le pagine solo
se non esistono: dopo l'avvio i contenuti si curano dall'editor.
"""

from typing import Any

DA_COMPLETARE = "<p><b>Da completare:</b> {}</p>"

CORPO_HOME = "home.json"
# Fornita da Andrea il 17/11/2026 (pagina «Le strutture» del Google Site)
CITAZIONE_STRUTTURE = (
    "Il campo è la parte gioiosa della vita di uno scout. Vivere fuori, all'aperto, tra montagne "
    "e alberi, tra uccelli ed animali, tra mare e fiumi, in una parola vivere in mezzo alla natura "
    "di Dio, con la propria casetta di tela, cucinando da sé ed esplorando: tutto questo reca tanta "
    "gioia e salute, quanta mai ne potete trovare tra i muri ed il fumo della città"
)
PRESENTAZIONE_HOME = (
    "Un bosco di oltre 20.000 m² ad Aiello del Sabato, in Irpinia, con area tende e "
    "accantonamento per campi, uscite ed eventi."
)


def paragrafo(html: str) -> dict[str, Any]:
    return {"type": "paragrafo", "value": html}


def titolo(testo: str) -> dict[str, Any]:
    return {"type": "titolo", "value": testo}


# slug → (tipo, titolo, riassunto, corpo, figlie)
PAGINE: list[dict[str, Any]] = [
    {
        "slug": "la-storia",
        "tipo": "PaginaContenuto",
        "titolo": "La storia",
        "riassunto": "Dal 1986 gli scout ad Aiello del Sabato.",
        "corpo_da_file": "la-storia.json",
    },
    {
        "slug": "gianni-sabatino",
        "tipo": "PaginaContenuto",
        "titolo": "Gianni Sabatino",
        "riassunto": "Il pioniere dello scautismo irpino a cui è dedicata la base.",
        "corpo_da_file": "gianni-sabatino.json",
    },
    {
        "slug": "le-strutture",
        "tipo": "PaginaStrutture",
        "titolo": "Le strutture",
        "riassunto": "Dormitori, cucina, sale, area tende, arena.",
        # L'elenco delle strutture lo genera la pagina dai dati della base (D-12)
        "corpo": [
            {"type": "citazione", "value": {"testo": CITAZIONE_STRUTTURE, "autore": "B.P."}},
            paragrafo(
                "<p>La base si trova in un bosco di castagni e querce di oltre 20.000 m², con "
                "strutture al chiuso e spazi all'aperto.</p>"
            ),
        ],
    },
    {
        "slug": "info",
        "tipo": "PaginaContenuto",
        "titolo": "Info",
        "riassunto": "Dove si trova la base, come arrivare, servizi vicini.",
        "corpo_da_file": "info.json",
        "figlie": [
            {
                "slug": "regolamento",
                "tipo": "PaginaRegolamento",
                "titolo": "Regolamento",
                "riassunto": "Le regole da leggere prima di venire alla base.",
                # Testo del regolamento di gennaio 2023 (PDF su Drive), in bozza: va rivisto e
                # allineato alle regole di Tana prima di pubblicarlo (la pubblicazione genera il PDF)
                "corpo_da_file": "regolamento.json",
                "aggiornato_a": "gennaio 2023",
                "bozza": True,
            },
            {
                "slug": "emergenze",
                "tipo": "PaginaContenuto",
                "titolo": "Emergenze",
                "riassunto": "Numeri utili in caso di emergenza.",
                "corpo": [
                    titolo("In caso di emergenza"),
                    paragrafo(
                        "<p><b>Numero unico di emergenza: 112</b></p>"
                        + DA_COMPLETARE.format(
                            "guardia medica, ospedale più vicino, carabinieri, con numeri e indirizzi."
                        )
                    ),
                ],
            },
            {
                "slug": "negozi-e-servizi-vicini",
                "tipo": "PaginaContenuto",
                "titolo": "Negozi e servizi vicini",
                "riassunto": "Spesa, farmacia e servizi vicino alla base.",
                "corpo": [paragrafo(DA_COMPLETARE.format("negozi, farmacia e servizi vicini."))],
            },
            {
                "slug": "per-chi-e-in-base",
                "tipo": "PaginaRiservata",
                "titolo": "Info per chi è in base",
                "riassunto": "Informazioni interne per i gruppi con prenotazione confermata.",
                "corpo": [
                    paragrafo(
                        DA_COMPLETARE.format(
                            "informazioni interne (WiFi, chiavi, raccolta differenziata, …)."
                        )
                    )
                ],
            },
        ],
    },
]

# Vecchi indirizzi del Google Site che cambiano (P-17): percorso → destinazione
REINDIRIZZAMENTI = {
    "/home": "/",
    "/info/listino-prezzi": "/listino/",
}
