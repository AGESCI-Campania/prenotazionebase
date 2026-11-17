# Changelog

Formato: una sezione `## vX.Y.Z — AAAA-MM-GG` per release (la legge `scripts/aggiorna.sh` per
mostrare le novità). Le variabili nuove di `.env.template` vanno indicate qui.

## Non rilasciato

## v0.9.1 — 2026-11-17

Seconda release di prova (F8): aggiornamento da v0.9.0 e ritorno indietro.

### Correzioni
- Immagine: `libharfbuzz-subset0` per WeasyPrint (senza, i PDF usano un ripiego deprecato).
- uv: modalità pre-release `explicit` al posto di `if-necessary-or-explicit`, deprecata (il tema
  resta alla versione alpha fissata).

## v0.9.0 — 2026-11-17

Prima release di prova (F8): installazione, aggiornamento e backup su un server pulito.
Contiene le fasi F0–F7.

### Correzioni
- Il pacchetto `tana.aggiornamenti` (aggiornamento dal web) mancava dal repo per una regola del
  `.gitignore`; le cartelle del server nel `.gitignore` sono ora ancorate alla radice.

### F7 — import da SuperSaaS
- `manage.py import_supersaas`: `--dry-run` con file di revisione Excel (categoria, stato, unione,
  esclusiva, persone, tipo di uscita, anomalie), `--apply` con le decisioni in un'unica transazione;
  nessuna riga persa in silenzio, conflitti di date con l'indicazione della riga.
- Prenotazioni congiunte per le stesse date nei due calendari, date riservate come prioritarie
  senza contatti, uscite in giornata, numero con l'anno di creazione, `id_supersaas` conservato.
- Collegamento delle prenotazioni importate all'account del referente con la stessa email
  verificata; le righe con i dati dell'amministratore (`--amministratori`) sono proposte senza
  referente.

### F6 — sito della base, PDF, PWA, aggiornamento dal web
- Sito Wagtail: home (mockup 6), pagine di contenuto con i blocchi di P-16 (niente HTML libero),
  pagina delle strutture generata dai dati della base, pagina riservata ai gruppi confermati, menu a
  tendina; albero con gli indirizzi del Google Site e reindirizzamenti dai vecchi; impostazioni del
  sito (contatti e social). Editor `/cms/` per Redazione, Amministratore e Responsabile (P-15).
- Testi del Google Site (home, La storia, Gianni Sabatino, Info) forniti da Andrea.
- Regolamento come pagina Wagtail (in bozza, dal PDF di gennaio 2023): PDF generato a ogni
  pubblicazione e archiviato, allegato alle email di conferma.
- PDF di preventivo, conferma e consuntivo (WeasyPrint), scaricabili dal richiedente e dalla
  gestione, allegati alle email di conferma e di chiusura.
- PWA: manifest, icone (anche maskable e Apple), service worker senza uso offline.
- Aggiornamento dal web (P-20): pagina Gestione › Aggiornamenti, `scripts/esegui-aggiornamento.sh`,
  unit `prenotazionebase-aggiorna.path/.service`; cartella `aggiornamenti/` montata nel container web.
- CI: Pango per i test dei PDF, `astral-sh/setup-uv@v10.3.3`.
- Corretto: ciclo di reindirizzamenti tra login ed editor per chi è collegato senza permessi.

### F5 — area di gestione, statistiche, export
- `/gestione/` con barra laterale e contatori: cruscotto, elenchi (da approvare, acconti, consensi,
  consuntivi, messaggi senza risposta, tutte), calendario con i nomi, arrivi e partenze per il
  telefono (D-26).
- Scheda della prenotazione: approvazione con concessioni e acconto, rifiuto, annullamento,
  modifica di date e persone, voci da definire, voci libere, modifica della quota, ricevute,
  pagamenti, orari concordati, messaggi con il gruppo, storico. Consuntivo con presenze
  effettive, voci, saldo e chiusura.
- Prenotazioni per conto della gestione (prioritarie, anche senza contatti e oltre l'orizzonte).
- Blocchi tecnici, versioni di listino con copia delle voci, configurazione (anche IBAN e causale),
  ruoli assegnati dalla segreteria; strutture e categorie nell'admin Django per l'amministrazione.
- Statistiche per anno e export Excel/CSV di prenotazioni e incassi.
- Anonimizzazione dei dati personali dopo 10 anni nello scheduler (D-18).
- Controlli dei permessi nel calcolo degli importi; orari concordati anche dal richiedente.

### F4 — area del richiedente, consensi, messaggi
- Nuova richiesta in tre passi (gruppo e referenti, soggiorno, riepilogo) con preventivo e
  disponibilità in tempo reale, calcolati con le stesse regole dell'invio.
- Area personale: elenco, pagina della prenotazione con le tappe, acconto e caricamento della
  ricevuta, annullamento, preventivo o consuntivo, pagamenti; ricevute servite con
  X-Accel-Redirect in produzione (P-14).
- Consensi del gruppo presente (D-06): domande alla richiesta, risposta dall'area personale,
  scadenza nello scheduler; senza consenso l'approvazione è bloccata.
- Messaggi con la gestione e con i gruppi negli stessi giorni, con email; telefono dell'altro
  referente solo se autorizzato (D-16).
- Pagine pubbliche: calendario della disponibilità con le mezze giornate (D-17) e listini in
  vigore. Navigazione e piè di pagina della base.
- Righe del preventivo e del consuntivo con il calcolo come nei mockup («8,00 € × 20 persone ×
  6 giorni»): persone e giorni (o notti) salvati sulla riga.
- Piè di pagina sempre in fondo alla finestra; da desktop resta visibile e il corpo scorre sopra.
- Prenotazione: capo responsabile. Un amministratore che prenota è titolare come ogni
  richiedente; senza titolare solo le prenotazioni inserite per conto della gestione.

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
