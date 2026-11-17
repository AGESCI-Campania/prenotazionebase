# Installazione di Tana sul server

Guida per l'amministratore del server, pensata per chi **non conosce il progetto**. Va seguita
dall'inizio alla fine alla prima installazione; i capitoli 13–14 servono anche dopo.

> Stato: prima stesura (F0). Si completa man mano che le fasi aggiungono passi e si prova per
> intero in F8 su un server pulito, finché funziona senza interventi fuori testo. Ogni modifica a
> script, variabili, servizi o passi manuali aggiorna questa guida nello stesso commit.

Regole del server: [`INTEGRAZIONE.md` del frontend](https://raw.githubusercontent.com/AGESCI-Campania/agesci-campania-web-frontend/main/docs/INTEGRAZIONE.md)
e [`INTEGRAZIONE-SSO.md` di Sestante](https://raw.githubusercontent.com/AGESCI-Campania/sestante/main/docs/INTEGRAZIONE-SSO.md).
Stesso modello di installazione di Plancia 3.0.

## In breve

| | |
| --- | --- |
| Repo sul server | `/opt/prenotazionebase`, proprietario `agesci` (gruppo `docker`, senza sudo) |
| Indirizzo | `https://<TANA_HOST>` (es. `baseaiello.agescicampania.net`) |
| Ingresso | servizio `nginx` sulla rete `agesci-proxy`, alias `tana-nginx:80`; nessuna porta pubblicata |
| Servizi | `web` (Django + gunicorn), `scheduler` (scadenze automatiche), `nginx`, `db` (PostgreSQL 18) |
| Variabili | `/opt/prenotazionebase/.env` (da `.env.template`, `chmod 600`) |
| Avvio al boot | unit `prenotazionebase.service` dopo `agesci-campania-web-frontend.service` |
| Backup | ogni notte alle 02:30 (`prenotazionebase-backup.timer`) in `/opt/prenotazionebase/backups` |
| Versione | sempre una release (tag `vX.Y.Z`), aggiornata solo con `scripts/aggiorna.sh` |

## 1. Prerequisiti

- Server Ubuntu 26.04 con Docker e Docker Compose v2 (`docker compose version`).
- `agesci-campania-web-frontend` già installato in `/opt/agesci-campania-web-frontend`: esistono la
  rete `agesci-proxy` (`docker network inspect agesci-proxy`) e la unit
  `agesci-campania-web-frontend.service`.
- Utente `agesci` nel gruppo `docker`, senza sudo; un utente amministratore con sudo.
- Accesso al DNS di `agescicampania.net`.
- Accesso amministrativo a Sestante (`https://auth.agescicampania.net`) e al repo
  `AGESCI-Campania/sestante`.
- Casella mittente `@agescicampania.net` e credenziali SMTP (password per app o relay di Google
  Workspace).

## 2. DNS

Creare il record di `<TANA_HOST>` verso l'IP del server (A/AAAA, oppure CNAME verso il nome del
server). Verifica, da un computer qualsiasi:

```bash
dig +short <TANA_HOST>
```

Finché il DNS non punta al server Caddy non può ottenere il certificato.

## 3. Cartella e codice

Come **amministratore**:

```bash
sudo install -d -o agesci -g agesci /opt/prenotazionebase
```

Come **`agesci`** (mai con sudo o da root dentro `/opt/prenotazionebase`):

```bash
sudo -iu agesci
git clone https://github.com/AGESCI-Campania/prenotazionebase.git /opt/prenotazionebase
cd /opt/prenotazionebase
git checkout "$(git tag -l 'v[0-9]*' --sort=-v:refname | head -1)"   # ultima release
```

## 4. Installazione

Prima si prepara `.env` con l'indirizzo giusto, poi si lancia lo script:

```bash
cd /opt/prenotazionebase
cp .env.template .env && chmod 600 .env
vi .env          # ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, BASE_URL con l'indirizzo scelto
TANA_ADMIN_EMAIL=<email-del-superutente> scripts/installa.sh
```

Lo script:

1. controlla i prerequisiti e la rete `agesci-proxy` (e che non lo si stia eseguendo da root);
2. crea `.env` da `.env.template` se manca e **genera i segreti vuoti** (`DJANGO_SECRET_KEY`,
   `POSTGRES_PASSWORD`), `chmod 600`; i valori già presenti non li tocca mai;
3. avvisa se il repo non è su una release;
4. costruisce le immagini `tana:locale` e `tana-nginx:locale` (una alla volta), avvia lo stack e
   attende che tutti i servizi siano `healthy` (il primo avvio applica le migrazioni: qualche minuto);
5. imposta il dominio del `Site` Django dal primo valore di `ALLOWED_HOSTS` e crea i dati iniziali;
6. crea il **superutente di emergenza** (solo se non ne esiste uno) e ne mostra la password
   **una sola volta**: annotarla subito in un luogo sicuro;
7. installa le unit systemd (vedi § 5);
8. stampa i passi manuali residui e le variabili ancora vuote.

Lo script si può rilanciare: non rigenera segreti né superutenti già esistenti.

## 5. Avvio al boot e backup (amministratore)

`agesci` non è sudoer: lo script non può installare le unit e stampa i comandi da far eseguire a un
amministratore, del tipo:

```bash
sudo bash -c 'cd /opt/prenotazionebase && source scripts/_comune.sh && installa_servizio_systemd prenotazionebase agesci-campania-web-frontend.service'
sudo bash -c 'cd /opt/prenotazionebase && source scripts/_comune.sh && source scripts/_tana.sh && installa_backup_systemd'
```

Usare i comandi **stampati dallo script**, non questi esempi. Verifica:

```bash
systemctl status prenotazionebase prenotazionebase-backup.timer
systemctl list-dependencies --after prenotazionebase
```

## 6. Caddy (repo del frontend)

Nel repo `agesci-campania-web-frontend` aggiungere `caddy/sites/tana.caddy`:

```caddy
# Tana — Prenotazioni e sito della Base Scout «Gianni Sabatino»
# Repo: https://github.com/AGESCI-Campania/prenotazionebase
<TANA_HOST> {
	import comune
	reverse_proxy tana-nginx:80
}
```

e la riga del registro progetti in `docs/INTEGRAZIONE.md` (`Tana | <TANA_HOST> | tana-nginx:80 | —`);
commit, push, poi sul server `/opt/agesci-campania-web-frontend/scripts/aggiorna.sh`. Verifica:

```bash
curl -I https://<TANA_HOST>/healthz/      # 200
curl -I http://<TANA_HOST>/               # redirect a https
```

Quando si spegne il vecchio sito Google (§ 12) si aggiunge anche il redirect da
`www.baseaiello.agescicampania.net`.

## 7. SSO Sestante

1. Il blueprint è in questo repo, `docs/sestante/provider-tana.yaml`: Andrea lo copia come
   `blueprints/provider-tana.yaml` nel repo `sestante`, lo aggiunge a `BLUEPRINTS` in
   `scripts/_sestante.sh` e lo applica con `scripts/aggiorna.sh` di Sestante.
2. Client ID e secret da <https://auth.agescicampania.net/if/admin/#/core/providers> → Tana → modifica.
3. In `/opt/prenotazionebase/.env`: `SOCIAL_SESTANTE_CLIENT_ID`, `SOCIAL_SESTANTE_CLIENT_SECRET`.
4. `docker compose up -d` (ricrea i container: `restart` non rilegge `.env`).

Callback registrata: `https://baseaiello.agescicampania.net/accounts/oidc/sestante/login/callback/`
(slug `tana`, issuer `https://auth.agescicampania.net/application/o/tana/`).

Come funziona l'accesso:
- account di gestione solo con il pulsante «SSO AGESCI Campania»: al primo accesso Tana collega
  l'utente esistente con la stessa email, altrimenti lo crea senza ruoli;
- i ruoli globali arrivano dai gruppi di Sestante a ogni login (`admin-multipiattaforma` →
  Amministratore, `segreteria` → Segreteria regionale); gli altri ruoli li assegna la segreteria;
- chi entra con Sestante non ripete la MFA in Tana; il superutente di emergenza (login locale) deve
  attivare il TOTP al primo accesso e non può più disattivarlo;
- i richiedenti continuano a registrarsi con email e password.

## 8. Email

In `.env`: `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (e, se diversi, host, porta, mittente),
`ADMIN_EMAILS` per le notifiche degli errori (indirizzi separati da virgola); poi
`docker compose up -d`. Le variabili `EMAIL_*` configurano il mailer `default` di Django
(`MAILERS` in `config/settings/base.py`). Prova di invio:

```bash
docker compose exec web uv run python manage.py sendtestemail <indirizzo>
```

## 9. Primo accesso

1. `https://<TANA_HOST>/accounts/login/` con il superutente di emergenza; configurare subito la MFA.
2. Primo login con Sestante di un account di gestione.
3. Assegnazione dei ruoli locali (Pattuglia, Amministratore, Responsabile, Redazione): per ora da
   `/django-admin/` → Utenti → utente → Nomine (l'area della segreteria arriva in F5). Ogni ruolo
   è anche un gruppo con lo stesso nome; il permesso «Riceve le notifiche di gestione» è assegnato
   di default ad Amministratore e Responsabile e si sposta da Gruppi.
4. Prove SSO del contratto: utente nuovo, utente esistente collegato per email, membro di
   `segreteria`, utente senza gruppi.

## 10. Configurazione iniziale nel backend

Da `/django-admin/` → Configurazione: **IBAN, intestatario e causale del bonifico** (finché sono
vuoti l'email di approvazione non mostra le coordinate), orizzonte delle prenotazioni.
Nelle fasi successive: importi mancanti dei listini, contenuti delle pagine del sito (emergenze,
negozi, informazioni interne).

## 11. Import da SuperSaaS

Dalla F7: `manage.py import_supersaas` con `--dry-run`, revisione del file, poi `--apply` (vedi §7
della specifica). I CSV contengono dati personali: copiarli in una cartella fuori dal repo, mai in git,
e cancellarli dopo l'import.

## 12. Spegnimento dei sistemi vecchi

- SuperSaaS: dopo l'import e le verifiche.
- Sito Google della base: tutti i contenuti devono essere già in Tana; poi si sposta il CNAME di
  `www.baseaiello.agescicampania.net` sul server e si aggiunge il redirect in Caddy.

## 13. Verifiche finali

- [ ] `https://<TANA_HOST>` risponde con certificato valido; HTTP reindirizza a HTTPS
- [ ] `docker compose ps`: tutti i servizi `healthy`
- [ ] login richiedente (registrazione email con verifica) e login Sestante
- [ ] caricamento di una ricevuta e download solo da chi ne ha diritto (dalla F3)
- [ ] email ricevute; PDF generati (dalla F3)
- [ ] backup notturno eseguito (`ls backups/`, `systemctl list-timers prenotazionebase-backup.timer`)
- [ ] `scripts/aggiorna.sh` senza versioni nuove: "Tana è già alla versione …"

## 14. Manutenzione

### Aggiornare a una nuova release

```bash
sudo -iu agesci
cd /opt/prenotazionebase && scripts/aggiorna.sh            # ultima release
cd /opt/prenotazionebase && scripts/aggiorna.sh v0.2.0     # una release precisa
```

Rifiuta di partire con modifiche locali, mostra le novità del `CHANGELOG.md`, si ferma se la release
chiede variabili nuove in `.env` (aggiungerle seguendo i commenti di `.env.template`), mette Tana in
manutenzione, fa il backup del database in `backups/` (ultimi 10), costruisce le immagini tenendo
quelle in uso come "precedenti", riavvia e attende `healthy`.

- Se la versione nuova non risponde **torna da sola** alla precedente.
- Se nel frattempo il database era già stato migrato **resta in manutenzione** e indica il backup da
  ripristinare (vedi sotto).

### Backup e ripristino

Archivio notturno `backups/tana-AAAAMMGG-hhmmss-<versione>.tar.gz` con `database.sql`, `env`,
`media.tar`, `privati.tar`; conservato `BACKUP_GIORNI` giorni. A mano: `scripts/backup.sh`.
La copia fuori dal server della cartella `backups/` è a cura dell'amministratore del server.

Ripristino (le istruzioni complete sono anche in testa a `scripts/backup.sh`):

```bash
mkdir /tmp/ripristino && tar -xzf backups/<archivio> -C /tmp/ripristino
docker compose stop web scheduler nginx
docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose exec -T db sh -c 'psql -q -U "$POSTGRES_USER" "$POSTGRES_DB"' < /tmp/ripristino/database.sql
docker compose up -d --wait web
docker compose exec -T web tar -C /app -xf - < /tmp/ripristino/media.tar
docker compose exec -T web tar -C /app -xf - < /tmp/ripristino/privati.tar
docker compose up -d && rm -rf /tmp/ripristino
```

Per il backup del database fatto da `aggiorna.sh` (`backups/tana-db-*.sql.gz`) usare
`gunzip -c <file> | docker compose exec -T db sh -c 'psql -q -U "$POSTGRES_USER" "$POSTGRES_DB"'`
al posto del passo con `database.sql`. Su un server nuovo: copiare prima `env` dell'archivio in `.env`
(`chmod 600`) e lanciare `scripts/installa.sh`, così il database nasce con la stessa password.

### Manutenzione manuale

```bash
docker compose exec web uv run python manage.py manutenzione attiva --messaggio "Lavori in corso"
docker compose exec web uv run python manage.py manutenzione disattiva
docker compose stop          # ferma tutto; al boot successivo la unit lo riavvia
```

### Diagnostica

```bash
cd /opt/prenotazionebase
docker compose ps                               # stato e salute dei servizi
docker compose logs --tail 100 web scheduler    # gunicorn e scadenze
tail -f logs/tana.log                           # log Django
systemctl status prenotazionebase prenotazionebase-backup.timer
```

Dopo ogni modifica a `.env`: `docker compose up -d`.
