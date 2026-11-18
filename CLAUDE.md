# CLAUDE.md

Guida per Claude Code nello sviluppo di **Tana** (repo `AGESCI-Campania/prenotazionebase`,
pacchetto `tana`). Leggila per intero prima di scrivere codice.

## Cos'è Tana
Piattaforma di prenotazione e sito della **Base Scout «Gianni Sabatino»** di Aiello del Sabato
(AV), Regione AGESCI Campania. Sostituisce i due calendari SuperSaaS (accantonamento, campo tende)
e il sito Google della base. Utenti: richiedenti (gruppi e enti, registrazione email), Pattuglia,
amministratore (ruolo tecnico), responsabile della base, redazione, segreteria regionale.

## Fonte di verità
**`docs/Tana_Progettazione.md`** è la specifica completa e autorevole (decisioni D-xx, proposte
P-xx, verifiche aperte V-xx). In caso di dubbio prevale quella. Se scopri che la specifica è
incompleta o contraddittoria **fermati e chiedi**: non decidere da solo e non inventare regole,
importi o versioni. Le modifiche alla specifica le approva Andrea.

## Regole di lavoro (anti-confabulazione)
- Verifica su codice, dati o documentazione prima di affermare; dichiara le inferenze come tali.
- Versioni di librerie e immagini: solo quelle verificate (uv.lock, registry), mai a memoria.
- Davanti a un ostacolo (permessi, strumenti che falliscono, informazioni mancanti) fermati e
  riferisci: niente scorciatoie autonome, niente dati finti o risultati scritti a mano.
- Testi per l'utente in **italiano**; codice, identificatori generici e commenti tecnici in
  **inglese**, nomi di dominio in italiano (es. `Prenotazione`, `VersioneListino`). Docstring brevi
  in italiano per le parti di dominio. Nell'interfaccia niente codici di decisione (D-xx).

## Stato e fasi
| Fase | Contenuto | Stato |
| --- | --- | --- |
| F0 | Impianto: progetto, tema, compose, script, unit systemd, guida di installazione, CI | **fatto** |
| F1 | Modello dati, vincoli di non sovrapposizione, configurazione, listini iniziali | **fatto** |
| F2 | Preventivo e consuntivo, test sugli esempi del §5.4 | **fatto** |
| F3 | Flusso richiesta → approvazione → acconto → conferma, scadenze, email, login Sestante | **fatto** |
| F4 | Area richiedente, consensi, messaggi | **fatto** |
| F5 | Area di gestione, decisioni discrezionali con storico, statistiche, export | **fatto** |
| F6 | Sito Wagtail, contenuti dal sito Google, PDF, PWA | **fatto** (testi lunghi da Andrea) |
| F7 | Import SuperSaaS | **fatto** (import reale in F8) |
| F8 | Prova completa di installazione, aggiornamento, backup; messa in produzione | in corso: prova su VM fatta, **v1.0.0** pubblicata, blueprint e blocco Caddy nei rispettivi repo; installazione sul server |

Aggiorna questa tabella e `CHANGELOG.md` alla fine di ogni fase.

## Stack
- Python **≥ 3.14**, Django **6.1**, PostgreSQL **18** (necessario: `daterange` + exclusion
  constraint con `btree_gist`), **uv** (mai pip), mise facoltativo.
- **Wagtail 8.1** per il sito della base (licenza BSD-3-Clause), integrato nello stesso progetto.
- Tema **`django-agesci-campania-theme` 3.0.0a3** (Bootstrap 6 **alpha**: non usare classi o
  JavaScript di Bootstrap 5; regole in <https://django-agesci-campania-theme.readthedocs.io/it/latest/llms.txt>),
  branca `eg` ricolorata con la palette della base in `static/tana/css/tana.css` (P-08).
  Aggiornamento del tema: `uv add --prerelease allow django-agesci-campania-theme`.
- **ALTCHA** (D-33): `altcha` Python + widget 3.5.0 in `static/tana/vendor/` (variante `external`, senza
  `blob:` per la CSP; il worker PBKDF2 si registra a mano), per la richiesta senza account.
- **django-allauth** (email con verifica obbligatoria, MFA, SSO Sestante via `openid_connect`),
  **django-axes**, **WhiteNoise**, **WeasyPrint** (PDF), **openpyxl** (Excel), **gunicorn**.
- Niente Celery/Redis: le scadenze le esegue il servizio `scheduler` (`manage.py scheduler`).
- **PDF sul Mac**: WeasyPrint vuole Pango di Homebrew; `mise.toml` imposta
  `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` (senza mise: esportarla prima di `uv run pytest`).
- Interfaccia: mockup in <https://claude.ai/artifact/L1d4xoj1HZSuHkbP65uRUQ> (solo riferimento: valgono
  testi e colori, il markup è del tema). Classi Bootstrap 6.0.0-alpha.1 verificate sul CSS del CDN
  (es. non esiste `card-title`). Il footer del tema è un `{% include %}`: i suoi blocchi interni
  non si sovrascrivono, `templates/base.html` riscrive l'intero blocco `footer` (in fondo alla
  finestra, fisso da lg: CSS in `tana.css`). In sviluppo con `runserver --noreload` i template
  restano in cache: riavviare il server dopo averli modificati. Sul Mac girano anche altri progetti
  (Plancia sulla 8000): prima di fermare un processo su una porta verificarne il percorso.
- Email con i **`MAILERS`** di Django 6.1 (alias `default`, configurato dalle variabili `EMAIL_*`
  di `.env`): inviare con `msg.send()` / `send_mail(...)` o `using="<alias>"`; **mai** le
  impostazioni `EMAIL_*`, `get_connection()`, `connection=` né `fail_silently=` (deprecati, con
  `MAILERS` sono errori). `ADMINS` è una lista di indirizzi. Nei test ogni
  `RemovedInDjango2028Warning` è un errore.

## Layout
```
config/            settings/{base,dev,test,prod}.py, urls.py (rotta Wagtail SEMPRE per ultima)
tana/core/         healthz, manutenzione, scheduler, dati_iniziali, EventoStorico (P-03), storage privato
tana/accounts/     User con login via email (AUTH_USER_MODEL = "accounts.User"), Nomina (ruoli = gruppi),
                   permessi.py (§6), adapters.py (Sestante, MFA), middleware MFA del superutente
tana/base/         Area, Struttura, Configurazione (singleton)
tana/listini/      Listino, VersioneListino (immutabile se usata), VoceListino, Categoria; versione_applicabile (D-09)
tana/prenotazioni/ Prenotazione, PresenzaArea, Occupazione (exclusion constraint), BloccoTecnico, consensi, importi, pagamenti, messaggi
                   contributo.py: preventivo, consuntivo, acconto, saldo, rettifiche (§5) — unica fonte degli importi
                   flusso.py: transizioni di stato (§4) con permessi, storico, email; scadenze dello scheduler
                   notifiche.py + templates/prenotazioni/email/*.txt: email a richiedente e gestione (D-19)
                   consensi.py (D-06), messaggi.py (D-16, telefoni), disponibilita.py (calendario, D-17)
                   views.py + urls.py: area del richiedente /prenotazioni/; views_pubbliche.py: /disponibilita/
                   conservazione.py: anonimizzazione dopo 10 anni (D-18, scheduler)
                   importazione.py + manage.py import_supersaas (§7): proposte, revisione xlsx, apply
tana/listini/      views.py: /listino/ (listini in vigore); services.nuova_versione
tana/gestione/     area /gestione/ (views, forms), statistiche.py, export.py (xlsx/csv); templates/gestione/
tana/sito/         Wagtail: HomePage, PaginaContenuto, PaginaStrutture, PaginaRegolamento (PDF alla
                   pubblicazione), PaginaRiservata; blocchi P-16; inizializza.py + contenuti_iniziali.py
tana/aggiornamenti/ aggiornamento dal web (P-20): release GitHub, richiesta.json ↔ stato.json
tana/core/pdf.py   WeasyPrint (import pigro); documenti delle prenotazioni in tana/prenotazioni/documenti.py
templates/         base.html (estende agesci_theme/base.html), core/manutenzione.html (statica)
static/tana/       css/tana.css (palette), img/logo/*.svg (loghi della base, non ridisegnarli)
deploy/            entrypoint.sh, nginx/ (Dockerfile + template dell'nginx interno)
scripts/           installa.sh, aggiorna.sh, backup.sh, _comune.sh (copia), _tana.sh
manuale/           manuale d'uso per ruolo (Sphinx + MyST, Read the Docs: .readthedocs.yaml); novita.md include CHANGELOG
docs/              Tana_Progettazione.md (specifica), installazione.md (guida del server),
                   sestante/provider-tana.yaml (blueprint, copiato in sestante/blueprints il 17/11/2026)
note/              istruzioni private di installazione sul server (escluse con .git/info/exclude: mai committarle)
```
Nuove app in `tana/<nome>/` con `label` esplicita. La logica sta nei **servizi** di dominio
(`tana/<app>/services.py`), usati da viste, comandi, PDF, export e import: mai duplicarla.

## Comandi
```bash
mise run install && mise run up && mise run migrate
mise run dev                      # :8000 — sito /, editor /cms/, admin /django-admin/
uv run pytest                     # test (PostgreSQL di sviluppo; sul Mac serve la variabile DYLD dei PDF)
uv run ruff check . && uv run ruff format . && uv run mypy .
shellcheck -x scripts/*.sh deploy/entrypoint.sh
uv run python manage.py scheduler --una-volta
uv run python manage.py manutenzione attiva|disattiva|stato
```
`$COMPOSE` nei task di mise: rileva Docker o Podman (mai `docker compose` fisso nei task locali).

## Vincoli di dominio (§12 della specifica)
- **Importi in centesimi interi**; mai `float` per il denaro.
- **Non sovrapposizione** garantita dal database (exclusion constraint su `daterange [arrivo,
  partenza)` per le occupazioni attive), non solo dai form. Prenotazioni, esclusive e blocchi
  tecnici stanno tutti in `Occupazione`, scritta solo da `tana.prenotazioni.services`
  (`sincronizza_occupazioni`, `crea_blocco`), che traduce la violazione in `DateOccupate`.
- **Unica fonte di verità** per prezzi, disponibilità e permessi: un livello di servizi condiviso.
- **Listino congelato** sulla prenotazione; versioni di listino immutabili una volta usate.
- **Decisioni discrezionali** sempre con "deciso da" e motivazione (P-03), nello storico.
- **Stati** solo da `tana.prenotazioni.flusso` (unica eccezione: l'import dello storico in
  `importazione.py`, che non manda email; mai `prenotazione.stato = ...` altrove); i
  **permessi** solo da `tana.accounts.permessi`; le email partono in `transaction.on_commit`.
- **Dati minimi** (D-18): nessun dato sui ragazzi; info interne solo ai gruppi confermati;
  ricevute solo via `X-Accel-Redirect` dopo il controllo dei permessi, mai in `MEDIA_ROOT`.
- **Import SuperSaaS**: nessuna scrittura senza `--apply`, nessuna riga scartata in silenzio; i CSV
  reali non entrano mai nel repo.
- **Wagtail**: rotta generica per ultima in `config/urls.py`; solo i blocchi di P-16, mai HTML
  libero; Wagtail e Django si aggiornano nella stessa release.
- **Dominio** `agescicampania.net`: nessun riferimento a `agescicampania.org`.

## Server e deploy (modello Plancia 3.0)
Regole vincolanti, da rileggere **prima** di toccare compose, nginx, impostazioni HTTP o script:
- frontend: <https://raw.githubusercontent.com/AGESCI-Campania/agesci-campania-web-frontend/main/docs/INTEGRAZIONE.md>
- SSO: <https://raw.githubusercontent.com/AGESCI-Campania/sestante/main/docs/INTEGRAZIONE-SSO.md>
- riferimento operativo: repo `AGESCI-Campania/plancia`, branch `v3` (`scripts/`, compose, `Dockerfile`, `deploy/`).

In sintesi:
- Server Ubuntu 26.04, repo in **`/opt/prenotazionebase`**, utente **`agesci`** (gruppo `docker`,
  senza sudo). Mai `sudo` o root dentro il repo.
- Solo il servizio `nginx` è sulla rete esterna `agesci-proxy`, alias **`tana-nginx`**; **nessuna
  porta pubblicata**; niente TLS nel progetto; l'nginx interno inoltra
  `X-Forwarded-Proto $http_x_forwarded_proto` (mai `$scheme`).
- Tutti i servizi con `restart: unless-stopped` e `healthcheck` (web su `/healthz/` con `Host` di
  `ALLOWED_HOSTS` e `X-Forwarded-Proto: https`; scheduler sul file di battito).
- Migrazioni solo dal container `web` all'avvio (`ESEGUI_MIGRAZIONI=1`); statici con WhiteNoise e
  `collectstatic` nel `Dockerfile`.
- Variabile nuova → in `.env.template` (vuota o con default, con commento) nello stesso commit:
  `aggiorna.sh` si ferma finché non è in `.env`.
- `scripts/_comune.sh` è una **copia identica** di quello del frontend: non modificarlo, riallinearlo
  copiandolo. Le funzioni di Tana stanno in `_tana.sh`. Bash `set -euo pipefail`, messaggi in
  italiano, `shellcheck -x` pulito, bit eseguibile committato.
- Unit systemd generate dagli script (mai scritte a mano): `prenotazionebase.service`,
  `prenotazionebase-backup.service/.timer`, `prenotazionebase-aggiorna.path/.service`
  (aggiornamento dal web, P-20). Senza sudo gli script stampano il comando per l'amministratore.
- **Non modificare** i repo `agesci-campania-web-frontend` e `sestante` senza una richiesta esplicita
  di Andrea: prepara i contenuti e consegnali. Già fatto su sua richiesta (17/11/2026):
  `caddy/sites/tana.caddy` + registro in `INTEGRAZIONE.md` (frontend), `blueprints/provider-tana.yaml`
  + `BLUEPRINTS` + registro in `INTEGRAZIONE-SSO.md` (sestante). Sestante non usa release: si
  aggiorna con `git pull` dal suo `scripts/aggiorna.sh`.
- **`docs/installazione.md`** si aggiorna nello stesso commit di ogni modifica a script, variabili,
  servizi o passi manuali.

## SSO Sestante (D-28)
- Provider allauth `openid_connect`, id **`sestante`**, slug Authentik `tana` (P-21); issuer sempre
  l'URL pubblico `https://auth.agescicampania.net/application/o/tana/`, mai l'alias Docker.
- Callback `/accounts/oidc/sestante/login/callback/`: verificarla con
  `reverse("openid_connect_callback", kwargs={"provider_id": "sestante"})` prima di consegnare il
  blueprint; non cambiarla senza aggiornare il blueprint.
- Senza `SOCIAL_SESTANTE_CLIENT_ID` il provider non si configura e l'app parte comunque.
- Ruoli globali solo da `admin-multipiattaforma` (Amministratore) e `segreteria` (Segreteria),
  ricalcolati a ogni login SSO; i ruoli locali non si toccano mai dal flusso SSO.
- MFA saltata solo se la **sessione** è autenticata con Sestante (mai per l'esistenza di un
  account collegato); il superutente di emergenza ha la MFA TOTP obbligatoria.
- Il login email dei richiedenti resta: non disattivarlo. Mai segreti nel repo.

## Release
Dal Mac, **prima** dell'aggiornamento del server: versione in `pyproject.toml`, sezione
`## vX.Y.Z — AAAA-MM-GG` in `CHANGELOG.md`, commit su `main`, **attendere la CI verde su quel
commit**, poi `git tag vX.Y.Z && git push origin vX.Y.Z` e `gh release create vX.Y.Z` con le note
della sezione (mai `--prerelease`: la pagina Aggiornamenti legge `releases/latest`, che le ignora).
Tag e release sempre insieme. Sul server solo `scripts/aggiorna.sh`.

**Manuale d'uso** (`manuale/`, pubblicato su Read the Docs a ogni push): ogni modifica visibile
agli utenti aggiorna nello stesso commit il capitolo del ruolo interessato (richiedenti,
pattuglia, amministrazione, segreteria, redazione, automatismi), con le etichette esatte
dell'interfaccia; le «Novità» si aggiornano da sole dal CHANGELOG. Se cambia una pagina fotografata si
rigenerano le schermate (dati inventati, database di test):
`uv run --group schermate pytest manuale/schermate.py` (Chromium: `uv run --group schermate playwright install chromium`). La CI lo compila con
`sphinx-build -W`; in locale:
`uv run --no-project --prerelease=allow --python 3.12 --with-requirements manuale/requirements.txt sphinx-build -W -b html manuale /tmp/manuale`.

## Cosa NON fare
- Non cambiare `AUTH_USER_MODEL` né le `label` delle app dopo le prime migrazioni.
- Non usare `float` per importi; non controllare le sovrapposizioni solo nei form.
- Non servire ricevute o file privati da `/media/`.
- Non usare classi Bootstrap 5 né scrivere HTML libero nei blocchi di Wagtail.
- Non aggiungere porte pubblicate, TLS o `$scheme` nell'nginx interno.
- Non modificare `scripts/_comune.sh`; i repo del frontend o di Sestante solo su richiesta esplicita.
- Non committare `.env`, CSV o Excel con dati reali.
