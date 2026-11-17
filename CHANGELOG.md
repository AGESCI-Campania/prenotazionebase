# Changelog

Formato: una sezione `## vX.Y.Z — AAAA-MM-GG` per release (la legge `scripts/aggiorna.sh` per
mostrare le novità). Le variabili nuove di `.env.template` vanno indicate qui.

## Non rilasciato

### Script
- `aggiorna.sh` lancia `manage.py dati_iniziali` dopo l'avvio della nuova versione (idempotente:
  crea solo i dati nuovi della release).

### F3 — flusso, email e login Sestante
- Ruoli di gestione come nomine (Pattuglia, Amministratore, Responsabile, Redazione, Segreteria),
  ognuno con il suo gruppo Django; permessi del §6 in `tana.accounts.permessi`.
- Login Sestante: provisioning, collegamento per email, rifiuto senza email o con email doppia,
  ruoli globali dal claim `groups` a ogni login; niente MFA ripetuta per le sessioni Sestante;
  TOTP obbligatorio e non rimovibile per il superutente di emergenza. Blueprint
  `docs/sestante/provider-tana.yaml` per `baseaiello.agescicampania.net`.
- Flusso della prenotazione (`tana.prenotazioni.flusso`): richiesta (orizzonte, prioritarie,
  esclusiva), approvazione con concessioni e acconto come decisioni, rifiuto motivato, annullamento,
  ricevuta dell'acconto (caricamento, verifica, rifiuto), conferma senza acconto, svolta, chiusura
  con consuntivo.
- Scheduler: acconti scaduti → SCADUTA, soggiorni conclusi → SVOLTA.
- Email a ogni cambio di stato al richiedente e alla gestione (casella della base e permesso
  «Riceve le notifiche di gestione», di default ad Amministratore e Responsabile).
- Configurazione: IBAN, intestatario e causale del bonifico.

### F2 — preventivo e consuntivo
- `tana.prenotazioni.contributo`: preventivo (§5.1) giorno per giorno con le stagioni, bivacco a
  notti per i soggiorni di una notte, attività in giornata, voci "da definire" (P-04), listino
  associativo per le categorie prioritarie non ancora concesse (P-06), versione congelata.
- Acconto con soglia di esenzione e arrotondamento al centesimo; consuntivo con le persone
  effettive (previste dove mancano) e la versione del preventivo; saldo.
- Valorizzazione delle voci mancanti, voci libere e modifica della quota (D-24) con "deciso da"
  e motivazione nello storico; preventivo congelato dopo l'acconto.
- Prenotazione: data della richiesta (D-09). Test sugli esempi del §5.4.

### F1 — modello dati
- App `base` (aree, strutture, configurazione), `listini` (listini con versioni e voci in
  centesimi, categorie) e `prenotazioni` (prenotazioni, presenze, occupazioni, blocchi tecnici,
  attività in giornata, consensi, righe di importo, pagamenti, messaggi); storico degli eventi
  e delle decisioni discrezionali in `core`.
- Non sovrapposizione garantita da PostgreSQL: exclusion constraint con `btree_gist` sulle
  occupazioni attive, che comprendono esclusive e blocchi tecnici.
- Versioni di listino immutabili dopo il primo uso; scelta della versione applicabile (D-09).
- Ricevute in uno storage privato (`STORAGES["privato"]`, in `PRIVATE_MEDIA_ROOT`) senza URL.
- `manage.py dati_iniziali` crea aree, strutture, categorie, listini 2022/2023 e configurazione.

### Email sui `MAILERS` di Django 6.1
- Le impostazioni `EMAIL_*` (deprecate) sono sostituite dal mailer `default`. Le variabili
  `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` di `.env`
  restano invariate; `ADMINS` è ora una lista di indirizzi (da `ADMIN_EMAILS`, invariata).
- Sviluppo: email in console, oppure a Mailpit con `EMAIL_MAILPIT=true` in `.env.dev` (variabile
  nuova, solo sviluppo).
- I test falliscono su ogni `RemovedInDjango2028Warning`.

### F0 — impianto del progetto
- Progetto Django 6.1 con uv, Python 3.14, PostgreSQL 18, Wagtail 8.1, tema regionale 3.0.0a3
  con la palette della base, django-allauth (email + SSO Sestante predisposto), django-axes.
- Utente con login via email (`accounts.User`), manutenzione (`manage.py manutenzione`),
  scheduler (`manage.py scheduler`), `/healthz/`.
- Docker Compose di produzione (web, scheduler, nginx, db) conforme a `INTEGRAZIONE.md` del
  frontend; script `installa.sh`, `aggiorna.sh`, `backup.sh` e unit systemd sul modello di
  Plancia 3.0; guida `docs/installazione.md`.
- Loghi SVG della base (scudo, scudo bianco, lupo, lupo con contorno).
