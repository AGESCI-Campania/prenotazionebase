# Changelog

Formato: una sezione `## vX.Y.Z — AAAA-MM-GG` per release (la legge `scripts/aggiorna.sh` per
mostrare le novità). Le variabili nuove di `.env.template` vanno indicate qui.

## Non rilasciato

## v1.0.13 — 2026-11-18

### Novità

- **Inviti su Sestante**: chi assegna un ruolo a una persona che non ha ancora l'account del login unico regionale le fa arrivare il link per crearlo (valido 7 giorni, account valido solo per Tana); al primo accesso con l'SSO trova già il ruolo. In *Utenti e ruoli* si vedono data e scadenza dell'invito, con «Rimanda l'invito»; togliendo l'ultimo ruolo prima dell'iscrizione l'invito si revoca.
- **Responsabile e amministratore** aprono *Utenti e ruoli* e assegnano o revocano i ruoli **Pattuglia** e **Redazione**; gli altri ruoli restano alla segreteria.

### Variabili nuove

- `SESTANTE_INVITI_TOKEN` (facoltativa): token dell'account di servizio `svc-tana-inviti` di Sestante. Vuota = nessun invito.

## v1.0.12 — 2026-11-18

### Sicurezza

- Chi ha un **ruolo di gestione** non entra più con email e password, nemmeno se se n'è impostata una con «Password dimenticata?» o da richiedente prima del ruolo: entra solo con «SSO AGESCI Campania», che chiede la verifica in due passaggi. Vale anche per il login dell'editor del sito e dell'admin; resta escluso il superutente di emergenza (con la sua MFA).

### Modifiche

- **Utenti e ruoli**: la segreteria può assegnare un ruolo anche a chi non è ancora entrato in Tana. L'account viene pre-registrato per email, senza password, e si collega al primo accesso con Sestante con i ruoli già assegnati; in tabella è segnato «in attesa del primo accesso».

## v1.0.11 — 2026-11-18

### Sicurezza

- La **Content Security Policy** è finalmente applicata: le regole c'erano nelle impostazioni ma mancava il middleware che le invia. Ora valgono uguali in sviluppo, test e produzione; provate su tutte le pagine (sito, area richiedente, gestione, editor del sito, admin, mappe incorporate) senza violazioni. Gli avatar Gravatar dell'editor si chiedono sempre in https.
- Superutente senza MFA: `sw.js` e il manifest non vengono più reindirizzati all'attivazione del TOTP (errori in console).

### Modifiche

- Link **«Manuale d'uso»** (<https://baseaiello.readthedocs.io>, versione dell'ultima release) nel piè di pagina per tutti e in fondo al menu della gestione.
- Piè di pagina: il link al sito associativo porta a campania.agesci.it invece che ad agesci.it.
- Menu della gestione: «Arrivi e partenze» solo a chi può aprirla (non più alla Segreteria, che riceveva «accesso negato»); «Messaggi senza risposta» diventa «Messaggi» (l'etichetta era troncata).

## v1.0.10 — 2026-11-18

### Novità

- Richiesta di prenotazione **senza registrazione**: chi non ha un account compila la richiesta e la conferma con il link ricevuto per email (valido 24 ore); le date si riservano alla conferma, l'account nasce da solo e si rientra con «Password dimenticata?». Prima dell'invio, «Non sono un robot» con ALTCHA (nessun servizio esterno, nessun dato a terzi).
- Modalità demo: il messaggio dice che le prenotazioni inserite non sono valide e dà il link per prenotare davvero (nuovo campo «dove prenotare durante la demo» in Configurazione); alla gestione il modulo ricorda che la prenotazione è di prova.

### Documentazione

- Nuovo **manuale d'uso** per ruolo (richiedenti, Pattuglia, amministrazione, segreteria, redazione, automatismi) con le schermate, per Read the Docs (`manuale/`, compilato anche dalla CI); le «Novità» vengono da questo CHANGELOG.
- Schermate del manuale rigenerate solo se cambiano (orologio fermo durante la generazione, confronto dei pixel).
- Guida di installazione: come correggere il file di revisione dell'import dal Mac (copia con `scp`).

Nessuna variabile nuova in `.env`. Dopo l'aggiornamento, se la demo è attiva, compila in Configurazione il campo «dove prenotare durante la demo».

## v1.0.9 — 2026-11-17

### Modifiche

- Modalità demo: registrazioni con email e password chiuse (la pagina «Registrati» mostra il messaggio e il pulsante SSO); il primo accesso con Sestante resta aperto.
- Pagina di registrazione: il pulsante SSO in cima, prima del modulo, come nel login.

Nessuna variabile nuova in `.env`.

## v1.0.8 — 2026-11-17

### Correzioni

- Aggiornamento dal web: la pagina Aggiornamenti legge l'avanzamento in background e, mentre Tana si riavvia, resta lì con l'indicazione «Tana si sta riavviando» e il tempo trascorso, invece di finire sulla pagina di manutenzione; le pagine di manutenzione si ricaricano da sole ogni 30 secondi.

Nessuna variabile nuova in `.env`. La nuova pagina di avanzamento si vede dall'aggiornamento successivo a questo; la pagina di manutenzione dell'nginx si aggiorna con la ricostruzione dell'immagine.

## v1.0.7 — 2026-11-17

### Correzioni

- Niente più email agli amministratori per i 503 durante gli aggiornamenti (es. `/manifest.webmanifest`, `/sw.js`): il logger `django` della configurazione di default di Django ne mandava una sua copia senza filtro, e gli altri errori arrivavano doppi.

### Modifiche

- Utenti e ruoli: una riga per utente con tutti i suoi ruoli.
- Configurazione: il riquadro della modalità demo compare solo quando si può attivare (nessuna prenotazione) o è già attiva.
- L'admin Django è riservato al superutente di emergenza: amministratore e responsabile non vi accedono più (strutture e categorie sono nell'editor del sito e nella gestione). Una migrazione toglie l'accesso agli account esistenti.

Nessuna variabile nuova in `.env`. Le email dei 503 possono arrivare ancora durante questo aggiornamento (gira la versione precedente); dal successivo no.

## v1.0.6 — 2026-11-17

### Novità

- Modalità demo (Configurazione): si attiva solo senza prenotazioni; mentre è attiva prenota solo la gestione e le email ai richiedenti partono solo verso utenti con un ruolo (oggetto «[DEMO]»); al termine, con conferma, si cancellano tutte le prenotazioni con i loro dati e la numerazione riparte.

### Modifiche

- Statistiche: grafico e tabella delle presenze per mese (previste ed effettive) e grafici della percentuale di occupazione per mese di ogni area.
- Configurazione: acconto, orari standard e dati del bonifico su una riga, come la stagione invernale; «Orizzonte massimo» diventa «Prenotazioni aperte fino a».
- Nel messaggio di blocco delle prenotazioni gli indirizzi web diventano link.
- «Blocchi tecnici» si chiamano ora «Date bloccate» in tutta l'interfaccia.
- Listini: nella pagina di una versione non ancora usata da nessuna prenotazione si correggono nome, data di pubblicazione e inizio di validità, e la versione si può eliminare.
- Categorie modificabili nell'area di gestione (Configurazione › Categorie) invece che nell'admin Django: creazione, modifica (il codice resta quello iniziale) ed eliminazione delle categorie mai usate.
- Editor del sito: voce «Gestione prenotazioni» nel menu per tornare all'area di gestione.
- Editor del sito: il logo della base al posto di quello di Wagtail nella barra laterale, e come favicon.
- Login con Sestante: l'immagine del profilo caricata su Sestante diventa quella dell'editor del sito (solo per chi vi accede; un'immagine caricata a mano nell'editor prevale). Serve il blueprint del provider aggiornato in Sestante (scope `avatar`).

Nessuna variabile nuova in `.env`. Prima di aggiornare Tana aggiornare Sestante (`git pull` e il suo `scripts/aggiorna.sh`), che aggiunge al provider di Tana l'immagine del profilo.

## v1.0.5 — 2026-11-17

### Novità
- **Strutture nell'editor del sito** (Gestione › Strutture, o la voce «Strutture» in `/cms/`):
  nome, uso, ordine, descrizione e una galleria di immagini facoltativa, al posto del Django admin.
  Lì si aggiungono anche le strutture nuove.
- Pagina **«Le strutture»**: si scelgono con le caselle le strutture da mostrare, ciascuna con
  descrizione e galleria, raggruppate per area. All'aggiornamento restano scelte quelle mostrate
  finora.

### Interfaccia
- Nel menu della gestione «Strutture e categorie» diventa due voci: «Strutture» (editor del sito)
  e «Categorie» (Django admin).

## v1.0.4 — 2026-11-17

### Novità
- **Blocco delle prenotazioni** (Gestione › Configurazione, in cima): con l'interruttore attivo
  nessuno può inserire nuove prenotazioni, nemmeno la gestione, e al posto del modulo compare un
  messaggio modificabile. Le prenotazioni esistenti proseguono normalmente; l'import dello storico
  non è toccato. Utile per il giro di prova prima dell'import e per chiusure temporanee.

### Correzioni
- Niente più email «Service Unavailable» agli amministratori durante la manutenzione: la pagina
  503 è voluta, ma ogni richiesta (es. il service worker `/sw.js`, che il browser riprova di
  continuo) generava una email. Le risposte 503 restano nel log.

## v1.0.3 — 2026-11-17

### Interfaccia
- Menu della gestione con le icone e con le sezioni Prenotazioni, Configurazione e Report a
  fisarmonica: una sola aperta alla volta, aperta quella della pagina corrente. A sezione
  Prenotazioni chiusa, accanto al titolo compare il totale degli elementi in attesa.
- Pagina Configurazione: percentuale, giorni e anni con l'unità dentro il campo, mesi della stagione
  invernale scelti per nome, i quattro campi della stagione su una riga (due su schermi stretti) e
  una spiegazione sotto ogni etichetta.

### Correzioni
- La voce «Da approvare» del menu della gestione ora si evidenzia quando è la pagina corrente.

## v1.0.2 — 2026-11-17

### Correzioni
- **Accesso con SSO**: errore 500 al clic su «Accedi con SSO AGESCI Campania». L'indirizzo di
  Sestante finiva con «/» e allauth chiedeva `…/tana//.well-known/openid-configuration`, a cui
  Sestante risponde 404: la barra finale ora si toglie sempre (come in Plancia).

### Interfaccia
- Pagina di accesso come in Plancia: pulsante «Accedi con SSO AGESCI Campania» a tutta larghezza
  in cima, poi «oppure con email e password»; niente più pagina intermedia di conferma.
- Piè di pagina compatto (da circa 316 a 98 px) e non più fisso: scorre con la pagina e sulle
  pagine corte resta in fondo alla finestra.

## v1.0.1 — 2026-11-17

### Novità
- Variabile **`EMAIL_EHLO`** (nuova in `.env.template`, può restare vuota): nome con cui Tana si
  presenta al server SMTP. Serve con il relay di Google Workspace (`smtp-relay.gmail.com`), che può
  rifiutare il nome del container; es. `EMAIL_EHLO=srv2.agescicampania.net`. `aggiorna.sh` si
  ferma finché la variabile non è in `.env`.

## v1.0.0 — 2026-11-17

Prima release di produzione: prenotazioni e sito della Base Scout «Gianni Sabatino», al posto
dei calendari SuperSaaS e del sito Google. Contiene le fasi F0–F7 (dettagli nelle sezioni
v0.9.x) e le correzioni emerse dalla prova di installazione su server pulito (F8).

### Documentazione
- Guida di installazione provata per intero su Ubuntu 26.04; recupero dopo un aggiornamento non
  riuscito con il database cambiato; ruoli assegnati da Gestione › Utenti.

### Correzioni
- Orari standard della configurazione come default callable: il controllo `fields.W161` di Django
  falliva se `check --deploy` girava a ridosso delle 12:00 o delle 15:00 (migrazione senza SQL).

## v0.9.2 — 2026-11-17

Terza release di prova (F8).

### Correzioni
- `aggiorna.sh`: se la release nuova non risponde dopo aver migrato il database, rimette le
  immagini della versione precedente, ferma `web` e `scheduler` (niente riavvii continui) e lascia
  acceso `nginx`; la guida spiega come ripristinare il backup e ripartire.
- nginx interno: pagina statica di manutenzione (503) quando Django non risponde, al posto
  dell'errore 502.

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
