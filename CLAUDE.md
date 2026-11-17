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
| F4 | Area richiedente, consensi, messaggi | prossima |
| F5 | Area di gestione, decisioni discrezionali con storico, statistiche, export | |
| F6 | Sito Wagtail, contenuti dal sito Google, PDF, PWA | |
| F7 | Import SuperSaaS | |
| F8 | Prova completa di installazione, aggiornamento, backup; messa in produzione | |

Aggiorna questa tabella e `CHANGELOG.md` alla fine di ogni fase.

## Stack
- Python **≥ 3.14**, Django **6.1**, PostgreSQL **18** (necessario: `daterange` + exclusion
  constraint con `btree_gist`), **uv** (mai pip), mise facoltativo.
- **Wagtail 8.1** per il sito della base (licenza BSD-3-Clause), integrato nello stesso progetto.
- Tema **`django-agesci-campania-theme` 3.0.0a3** (Bootstrap 6 **alpha**: non usare classi o
  JavaScript di Bootstrap 5; regole in <https://django-agesci-campania-theme.readthedocs.io/it/latest/llms.txt>),
  branca `eg` ricolorata con la palette della base in `static/tana/css/tana.css` (P-08).
  Aggiornamento del tema: `uv add --prerelease allow django-agesci-campania-theme`.
- **django-allauth** (email con verifica obbligatoria, MFA, SSO Sestante via `openid_connect`),
  **django-axes**, **WhiteNoise**, **WeasyPrint** (PDF), **openpyxl** (Excel), **gunicorn**.
- Niente Celery/Redis: le scadenze le esegue il servizio `scheduler` (`manage.py scheduler`).
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
templates/         base.html (estende agesci_theme/base.html), core/manutenzione.html (statica)
static/tana/       css/tana.css (palette), img/logo/*.svg (loghi della base, non ridisegnarli)
deploy/            entrypoint.sh, nginx/ (Dockerfile + template dell'nginx interno)
scripts/           installa.sh, aggiorna.sh, backup.sh, _comune.sh (copia), _tana.sh
docs/              Tana_Progettazione.md (specifica), installazione.md (guida del server),
                   sestante/provider-tana.yaml (blueprint da consegnare ad Andrea)
```
Nuove app in `tana/<nome>/` con `label` esplicita. La logica sta nei **servizi** di dominio
(`tana/<app>/services.py`), usati da viste, comandi, PDF, export e import: mai duplicarla.

## Comandi
```bash
mise run install && mise run up && mise run migrate
mise run dev                      # :8000 — sito /, editor /cms/, admin /django-admin/
uv run pytest                     # test (PostgreSQL di sviluppo)
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
- **Stati** solo da `tana.prenotazioni.flusso` (mai `prenotazione.stato = ...` altrove); i
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
  `prenotazionebase-backup.service/.timer`. Senza sudo gli script stampano il comando per
  l'amministratore. Aggiornamento dal web: P-20, non ancora approvato.
- **Non modificare** i repo `agesci-campania-web-frontend` e `sestante`: prepara i contenuti (blocco
  Caddy, blueprint `provider-tana.yaml`) e consegnali ad Andrea.
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
`## vX.Y.Z — AAAA-MM-GG` in `CHANGELOG.md`, commit su `main`, `git tag vX.Y.Z && git push origin vX.Y.Z`,
`gh release create vX.Y.Z` con le note della sezione. Tag e release sempre insieme. Sul server solo
`scripts/aggiorna.sh`.

## Cosa NON fare
- Non cambiare `AUTH_USER_MODEL` né le `label` delle app dopo le prime migrazioni.
- Non usare `float` per importi; non controllare le sovrapposizioni solo nei form.
- Non servire ricevute o file privati da `/media/`.
- Non usare classi Bootstrap 5 né scrivere HTML libero nei blocchi di Wagtail.
- Non aggiungere porte pubblicate, TLS o `$scheme` nell'nginx interno.
- Non modificare `scripts/_comune.sh`, i repo del frontend o di Sestante.
- Non committare `.env`, CSV o Excel con dati reali.
