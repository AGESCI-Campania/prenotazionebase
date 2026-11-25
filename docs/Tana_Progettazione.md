# Tana — Prenotazioni Base Aiello — Documento di progettazione

Piattaforma web (installabile come PWA) per le prenotazioni della Base Scout regionale
«Gianni Sabatino» di Aiello del Sabato (AV), gestita dalla Regione AGESCI Campania tramite la
Pattuglia Operativa di Gestione. Sostituisce i due calendari SuperSaaS (accantonamento e campo
tende), che saranno dismessi.

- **Nome:** **Tana** (rifugio del lupo, richiama il logo della base). Pacchetto `tana`.
- **Stato:** analisi chiusa (risposte della Pattuglia e di Andrea del 10/11/2026; sintesi v0.3
  inviata alla Pattuglia), aggiornata il 13/11/2026 per il nuovo server e il dominio
  `agescicampania.net`, il 14–15/11 per il sito in Wagtail (sintesi v0.4), il 17/11/2026 per
  installazione e SSO sul modello di Plancia 3.0. Restano le verifiche del §11. In sviluppo: F0–F7 fatte.
- **Repository:** `AGESCI-Campania/prenotazionebase` (il pacchetto Python resta `tana`). Licenza MIT, © Andrea Bruno.
- **Hosting:** nuovo server dedicato Ubuntu 26.04, installazione pulita senza Virtualmin né Apache;
  Docker Compose in `/opt/prenotazionebase` (utente `agesci`), dietro il reverse proxy Caddy comune;
  script, unit systemd e backup sul modello di **Plancia 3.0** (§9.1, D-27).
- **Dominio:** `*.agescicampania.net` (il dominio `.org` è stato abbandonato). Indirizzo di Tana:
  **`baseaiello.agescicampania.net`** (V-14, chiusa il 17/11/2026).
- **Sviluppo:** Claude Code, a partire da questo documento.

Convenzioni: le decisioni sono **D-nn**, le verifiche aperte **V-nn**, le proposte **P-nn**.
Le *proposte* sono scelte di progetto non ancora confermate esplicitamente da Andrea o dalla
Pattuglia: quelle non contestate valgono come approvate. Le *inferenze* sono deduzioni da
verificare prima di usarle. Tutto il resto è stato confermato da Andrea o dalla Pattuglia.

---

## 0. Proposte da approvare

P-01…P-10 approvate da Andrea il 10/11/2026, P-11…P-14 il 13/11/2026: valgono come decisioni.
P-15…P-18 (14/11/2026) legate al sito della base in Wagtail (D-30); P-19…P-21 nuove (17/11/2026),
legate a SSO e installazione sul modello di Plancia 3.0.

| N. | Proposta | Dove | Alternativa |
| --- | --- | --- | --- |
| P-01 | ✅ Approvata. Le richieste in attesa (`RICHIESTA`) occupano già le date: vale l'ordine di arrivo | D-05, §4 | Le date si bloccano solo all'approvazione |
| P-02 | ✅ Approvata. Una prenotazione prioritaria non scavalca in automatico una richiesta già presente: l'amministratore deve prima rifiutarla o spostarla | D-11 | Rifiuto automatico della richiesta non prioritaria |
| P-03 | ✅ Approvata. Ogni azione discrezionale dell'amministratore (esclusiva, categoria prioritaria, sconto, modifica di quota o acconto, esenzione) richiede i campi "deciso da" e "motivazione", salvati nello storico | D-14 | Solo traccia automatica di chi ha operato |
| P-04 | ✅ Approvata. Se una voce manca nel listino applicabile, il preventivo è "da definire" e l'approvazione richiede che l'amministratore la valorizzi | D-08 | Blocco dell'invio della richiesta |
| P-05 | ✅ Approvata. Le attività in giornata (uscite, giornate genitori) non occupano un'area in esclusiva: se c'è già una prenotazione nello stesso giorno serve il consenso del suo titolare (D-06) | D-05, D-06 | Uscite in esclusiva come i soggiorni |
| P-06 | ✅ Approvata. Il preventivo di chi chiede una categoria prioritaria si calcola sul listino ordinario e passa a quello agevolato solo quando la categoria è concessa | D-10 | Preventivo subito agevolato |
| P-07 | ✅ Approvata. Scadenze automatiche (acconto, consenso) eseguite da un comando periodico (`manage.py`), senza Celery. Meccanismo aggiornato: servizio `scheduler` nel compose (P-11) | §9 | Coda di task |
| P-08 | ✅ Approvata. Palette della piattaforma ricavata dal logo della base (verde `#076633`, `#0D8E36`, `#80C077`) come palette personalizzata del tema regionale | D-21 | Palette istituzionale viola |
| P-09 | ✅ Approvata. PDF generati con WeasyPrint, export con openpyxl | §9 | Altre librerie |
| P-10 | ✅ Approvata. Autenticazione con django-allauth (verifica email obbligatoria), già supportato dal tema | D-15 | Autenticazione Django di base |
| P-11 | ✅ Approvata. Servizio `scheduler` nel compose (stessa immagine dell'app) che lancia il comando periodico a intervalli, con healthcheck su un file di battito; niente cron sull'host | §9.1 | Cron/systemd timer sull'host con `docker compose exec` |
| P-12 | ✅ Approvata. Ruoli di Tana assegnati in Tana dalla segreteria agli utenti entrati con Sestante (al primo accesso nessun ruolo locale). Precisazione del 17/11/2026 per il contratto SSO: solo i due ruoli globali (`admin-multipiattaforma` → Amministratore, `segreteria` → Segreteria regionale) arrivano dal claim `groups`. Precisazione del 18/11/2026: la segreteria può assegnare un ruolo anche a chi non è ancora entrato, indicandone l'email; Tana **pre-registra** l'account senza password (P-13) e il primo login Sestante lo collega per email (D-28) con i ruoli già assegnati. Approvato il 18/11/2026: anche **responsabile e amministratore** assegnano e revocano **Pattuglia e Redazione** (mai Amministratore, Responsabile o Segreteria); a chi non ha un account Sestante Tana manda un **invito** per crearlo (contratto SSO di Sestante § 10, token `SESTANTE_INVITI_TOKEN`), valido 7 giorni e solo per Tana | D-28 | Ruoli derivati dai gruppi di Sestante (claim `groups`) |
| P-13 | ✅ Approvata. Account di gestione solo via Sestante, senza password locale; un solo superutente tecnico locale per emergenza, se Sestante non è raggiungibile, creato da `installa.sh` con MFA TOTP obbligatoria. Precisazione del 18/11/2026: i backend con password rifiutano chi ha un ruolo attivo (anche se una password l'ha impostata, per esempio con il recupero o da richiedente prima del ruolo); l'SSO e le sessioni aperte non cambiano | D-28 | Anche password locali |
| P-14 | ✅ Approvata. Ricevute dei bonifici e altri allegati privati serviti solo tramite Django con controllo dei permessi (`X-Accel-Redirect` verso una location `internal` di nginx), mai come `/media/` pubblico | D-27 | Media pubblici con URL non indovinabili |
| P-15 | ✅ Approvata il 17/11/2026. Ruolo **Redazione** assegnato dalla segreteria (anche a membri della Pattuglia): dà accesso solo all'editor delle pagine del sito; l'amministratore ha anche questo permesso | D-30, §6 | Editor riservato all'amministratore |
| P-16 | ✅ Approvata il 17/11/2026. Blocchi di contenuto limitati e senza HTML libero: paragrafo (testo formattato), titolo, immagine con didascalia, galleria, documento (PDF), citazione, pulsante/link, mappa incorporata da URL consentiti | D-30 | Blocco HTML libero |
| P-17 | ✅ Approvata il 17/11/2026. Migrazione manuale delle poche pagine del Google Site (testi e immagini) in F6, mantenendo gli stessi indirizzi relativi (`/la-storia/`, `/gianni-sabatino/`, `/le-strutture/`, `/info/regolamento/`) | D-30 | Comando di importazione automatica |
| P-18 | ✅ Decisa il 17/11/2026. Il Google Site (migrato su `agescicampania.net` il 15/11, raggiungibile su `www.baseaiello.agescicampania.net`) resta online **così com'è, senza manutenzione**, solo come fonte dei contenuti: all'avvio di Tana i contenuti sono già tutti in Wagtail e il sito Google si **spegne** | D-30 | — |
| P-19 | Chi entra con Sestante senza alcun ruolo di gestione (es. un capo AGESCI) può **prenotare come richiedente** con lo stesso account, senza registrarsi di nuovo; i richiedenti esterni restano con la registrazione email | D-15, D-28 | Sestante solo per la gestione |
| P-20 | ✅ Approvata il 17/11/2026. **Aggiornamento dal web** come in Plancia 3.0: pagina *Configurazione › Aggiornamenti* (solo amministratore, con riautenticazione), che scrive una richiesta letta da una unit systemd `.path` sull'host; il container non ha mai accesso a Docker | §9.1 | Solo `scripts/aggiorna.sh` da terminale |
| P-21 | Slug Sestante **`tana`** (provider "Tana – Prenotazioni Base Aiello", blueprint `provider-tana.yaml`) | D-28 | `prenotazionebase` come il repo |

---

## 1. Scopo e contesto

### 1.1 Situazione attuale

- Due calendari SuperSaaS separati: `prenotazioni` (strutture al chiuso / accantonamento) e
  `campotende` (piazzole tenda). Non si possono prenotare le due aree insieme; le
  sovrapposizioni venivano evitate a mano.
- SuperSaaS impone un orario su ogni prenotazione: gli orari inseriti sono casuali, gli accordi
  reali di arrivo e partenza erano informali.
- Flusso attuale: scelta date sul calendario → email con l'importo dell'acconto (50%) → invio
  della ricevuta del bonifico entro 3 giorni → email di conferma.
- Le date riservate a Formazione Capi, eventi regionali e Comune venivano inserite
  dall'amministratore come date bloccate con dati segnaposto.
- Listino 2022/2023 e regolamento (aggiornato a gennaio 2023) pubblicati sul sito della base
  (Google Sites) e nel PDF del regolamento. Il listino 2022/2023 è ancora in vigore.

### 1.2 La base

- Bosco di ~21.000 m² in località "Acqua o' Lupo", Contrada Bosco Materdomini, Aiello del
  Sabato (AV). Terreno e strutture in comodato gratuito dal Comune alla Regione AGESCI Campania.
- Logo: un lupo (simbolo dell'Irpinia) con le montagne irpine all'interno. Vocazione montana.
- **Accantonamento**: 2 dormitori da 100 posti complessivi + 9 posti in 3 stanzette per lo
  staff, sempre incluse con i dormitori.
- **Area tende**: 6 piazzole per tende di squadriglia, nessun limite su tipo e dimensione delle tende.
- Il palco con camerini non è più disponibile.

### 1.3 Fonti

- Sito della base: https://www.baseaiello.agescicampania.org (listino, regolamento, prenotazioni, strutture), consultato l'08/11/2026 sul vecchio dominio `.org`, poi abbandonato.
- Regolamento PDF, aggiornato a gennaio 2023.
- Documento preliminare v0.1 (08/11/2026) e risposte della Pattuglia (10/11/2026).
- Export CSV SuperSaaS dei due calendari (ultima esportazione, novembre 2026).

---

## 2. Decisioni

### D-01 — Canale unico
Una sola richiesta in cui si sceglie: solo tende, solo accantonamento, oppure tende +
accantonamento (congiunta), più le attività in giornata (D-07).

### D-02 — Un gruppo alla volta per area
Accantonamento e area tende ospitano ciascuno **un solo gruppo alla volta**. Le due aree
possono essere occupate contemporaneamente da gruppi diversi, salvo esclusiva (D-03).

### D-03 — Uso esclusivo
Chi prenota **solo l'accantonamento** può chiedere l'uso esclusivo della base (nessun altro
gruppo in area tende nello stesso periodo). L'esclusiva va concessa (D-14) e può avere un
sovrapprezzo stabilito caso per caso (voce libera, D-09). Se non è chiesta o non è concessa,
un altro gruppo può prenotare l'area tende nello stesso periodo.

### D-04 — Conteggio a giorni e giorni di cambio
- Il soggiorno si conta a giorni, **arrivo e partenza inclusi** (lunedì–sabato = 6 giorni).
  Eccezioni: bivacco e pernotto extra associativo si contano a notti.
- Nel giorno di arrivo e in quello di partenza possono coesistere il gruppo uscente e quello
  entrante nella stessa area.
- Orari standard di arrivo e partenza configurabili. Arrivare prima dell'orario va concordato
  con il gruppo uscente; partire dopo va concordato con il gruppo entrante.

### D-05 — Occupazione delle date
- Le aree occupate si modellano come **occupazioni** `(area, intervallo)` con intervallo
  semiaperto `[arrivo, partenza)`: il giorno di partenza resta libero per chi arriva.
  Il calcolo dei giorni fatturati (D-04) è separato dall'intervallo di occupazione.
- Vincolo di non sovrapposizione garantito dal database (PostgreSQL, *exclusion constraint* su
  `daterange` con `btree_gist`), solo per le occupazioni attive (§4).
- L'esclusiva concessa (D-03) crea un'occupazione dell'area tende senza persone.
- Ordine di arrivo: P-01. Attività in giornata: P-05.

### D-06 — Consenso del gruppo presente
Uscite in giornata e giornate genitori/ospiti in un giorno in cui la base è già prenotata si
possono fare solo se il gruppo già presente acconsente. Conta il primo che prenota.
- La richiesta genera una domanda di consenso al titolare della prenotazione esistente.
- Termine di risposta configurabile; **senza risposta entro il termine il consenso è negato**.

### D-07 — Tipi di attività prenotabili
| Tipo | Area | Unità di conteggio |
| --- | --- | --- |
| Campo in accantonamento | accantonamento | persona × giorno, tariffa per stagione |
| Campo in tenda | tende | persona × giorno |
| Bivacco (una sola notte) | accantonamento o tende | persona × notte |
| Uscita con uso cucina | (cucina, bagni, sala polifunzionale) | persona × giorno |
| Uscita area verde | (bagni, sala polifunzionale) | persona × giorno |
| Giornata genitori e ospiti | aggiuntiva a un soggiorno, solo se si usa la cucina per il pranzo | persona × giorno |

Uscita in area verde con l'accantonamento occupato: si svolge **senza la sala polifunzionale**
(riservata all'accantonamento, D-12); resta comunque il consenso di D-06.
Due attività in giornata nello stesso giorno: la seconda chiede il consenso a chi ha prenotato per primo (D-06).

### D-08 — Listini
- **Listini paralleli**, ognuno con le sue versioni: associativo, extra associativo, agevolato
  (Fo.Ca. regionale ed eventi regionali), gratuito (Comune). Tutti modificabili dall'app.
- Voci: tipo di attività × area × stagione, con unità (persona/giorno, persona/notte, forfait).
- Stagione invernale 1/11–15/3, ricorrente ogni anno e configurabile. Un soggiorno a cavallo
  delle stagioni si calcola **giorno per giorno**.
- Voci mancanti (extra associativo in tenda, bivacco in tenda, valori dell'agevolato):
  le inserisce la gestione prima dell'avvio. P-04.
- Il listino extra associativo ha **voci proprie**, configurate dalla gestione: non si deduce dal
  listino associativo. Il «pernotto extra associativo» del 2022/2023 è la sua voce iniziale.
- Pagina pubblica con i listini in vigore.
- Valori iniziali: listino 2022/2023 (§5.3). Il forfait anti-COVID è eliminato.

### D-09 — Quale versione di listino si applica
- Ogni versione ha una **data di pubblicazione** e una **data di inizio validità**, comunicata in anticipo.
- Si applica la versione, tra quelle già pubblicate alla data della richiesta, in vigore il
  **primo giorno del soggiorno**; vale per tutto il soggiorno (niente calcolo giorno per giorno
  tra versioni). Esempi:
  - nuovo listino pubblicato il 1/9, valido dal 1/1: richiesta del 15/9 per un campo a dicembre → vecchio listino; per un campo a febbraio → nuovo.
  - richiesta del 15/8 (nuovo non ancora pubblicato) per febbraio → vecchio listino.
- La prenotazione **congela** la versione applicata e le righe del preventivo.

### D-10 — Categorie "Associazione o ente"
Campo obbligatorio su ogni prenotazione, anche importata, usato per tariffa e statistiche.

| Categoria | Prioritaria | Listino di default |
| --- | --- | --- |
| Fo.Ca. regionale (compresi i campi di Formazione Capi organizzati dalle Zone, es. CFT) | sì | agevolato |
| Fo.Ca. nazionale (CFA) | sì (stessa priorità della Fo.Ca. regionale) | associativo |
| Eventi regionali | sì | agevolato |
| Comune di Aiello del Sabato | sì | gratuito; forfait per manifestazioni particolari e oltre la settimana annua del comodato |
| Gruppo AGESCI | no | associativo |
| Zone AGESCI | no | associativo |
| Gruppo CNGEI | no | extra associativo |
| Gruppo scout altra associazione | no | extra associativo |
| Associazione terzo settore | no | extra associativo |
| Altro (da specificare) | no | extra associativo |

- Le categorie prioritarie le assegna l'amministratore, oppure il richiedente le chiede e, se
  concesse, si applica il listino agevolato (P-06).
- Agevolazioni sempre possibili su qualunque prenotazione (D-14).
- Le prenotazioni prioritarie possono non avere contatti (es. date riservate a un campo
  regionale non ancora assegnato a uno staff).
- Le statistiche per categoria danno anche il conteggio della settimana annua del Comune.

### D-11 — Priorità
Fo.Ca. (regionale e CFA), eventi regionali e Comune hanno priorità (regolamento, §5). P-02.

### D-12 — Strutture
| Struttura | Uso | Note |
| --- | --- | --- |
| Dormitori (2) + 3 stanzette staff | solo accantonamento | in emergenza o con forti piogge si possono condividere per la sicurezza di chi è in tenda |
| Cucina | solo accantonamento | condivisibile previo accordo tra i gruppi |
| Refettorio | solo accantonamento | condivisibile previo accordo tra i gruppi |
| Sala polifunzionale | solo accantonamento | |
| Sala laboratorio | solo accantonamento | |
| Bagni e docce interni | solo accantonamento | |
| Bagni esterni | condivisi | |
| Arena con altare | condivisa | |
| Area tende (6 piazzole) | solo tende | |
| Lavabi area tende | solo tende | |
| Frigorifero accantonamento | solo accantonamento | |
| Frigorifero area tende | solo tende | |
| Area fuochi accantonamento | solo accantonamento | |
| Area fuochi area tende | solo tende | |
| Parcheggio | — | solo veicoli essenziali; di norma si parcheggia fuori dalla base |

Le strutture sono dati configurabili (nome, descrizione, uso: condivisa / solo accantonamento /
solo tende / non disponibile, ordine) con una **galleria di immagini facoltativa** (immagine e
didascalia, riordinabili). Si modificano nell'**editor del sito** (sezione «Strutture», snippet di
Wagtail), aperto all'amministrazione; anche le nuove strutture si aggiungono lì. Nella pagina
«Le strutture» la redazione **sceglie quali mostrare** (caselle): l'elenco si genera da quelle
scelte, raggruppate per area, con descrizione e galleria. Le non disponibili non compaiono
(deciso il 17/11/2026).

### D-13 — Acconto
- 50% del preventivo, configurabile.
- Ricevuta del bonifico da caricare entro **7 giorni** dall'approvazione (configurabile);
  altrimenti la richiesta scade e le date si liberano.
- Di default **nessun acconto per soggiorni fino a 3 giorni** (soglia configurabile).
- All'approvazione l'amministratore può sempre esentare dall'acconto o cambiarne l'importo.
- Con l'acconto la prenotazione è congelata definitivamente.
- L'acconto non è rimborsabile. Annullamento online sempre possibile: le date si liberano,
  l'acconto resta alla base, nessun'altra penale.
- Per le attività in giornata, come da regolamento, niente bonifico: le quote si consegnano
  all'arrivo.

### D-14 — Decisioni discrezionali
La "direzione" della base è la Pattuglia insieme agli IRO e ai Responsabili regionali.
L'**amministratore** è un ruolo tecnico: applica in app le decisioni dopo aver sentito chi deve
decidere, senza che il flusso in app diventi un iter di approvazioni a più livelli.
Rientrano: concessione dell'esclusiva e del sovrapprezzo, categorie prioritarie, agevolazioni,
accesso di enti esterni, modifica o azzeramento della quota di una prenotazione, importo o
esenzione dell'acconto. P-03.

### D-15 — Account
- **Richiedenti**: si registrano da soli con email verificata (P-10). Storico delle proprie prenotazioni.
- **Account di gestione** (Pattuglia, amministratori, responsabile, redazione, segreteria): accedono
  con il login unico di **Sestante** (D-28). La segreteria assegna i ruoli locali in Tana (anche prima del primo
  accesso, per email) e nomina il responsabile della base (P-12); i ruoli globali arrivano da Sestante (D-28).
- Un utente Sestante senza ruoli di gestione può prenotare come richiedente (P-19).

### D-16 — Comunicazione tra gruppi
- Messaggi tra i referenti dei gruppi tramite la piattaforma (giorni di cambio, consensi),
  con evidenza dei messaggi senza risposta per la Pattuglia.
- I contatti telefonici dell'altro gruppo si condividono solo su richiesta e con l'autorizzazione
  dell'interessato; la gestione si limita a mediare la richiesta.

### D-17 — Calendario pubblico
Solo libero/occupato per accantonamento e tende, nessun nome di gruppo. Mostra le mezze
giornate di arrivo/partenza.

### D-18 — Dati personali minimi
- Solo numeri aggregati di presenze (per area e per giorno, più ospiti) e dati del referente e del
  capo responsabile. **Nessun dato sui ragazzi.**
- Titolare del trattamento: **Regione AGESCI Campania**.
- Conservazione: **10 anni** (contabilità), poi anonimizzazione dei dati personali delle prenotazioni
  (le statistiche restano). Comando periodico come per le scadenze (P-07).
- Informativa privacy, che per i dati importati dichiara la provenienza dal sistema precedente.

### D-19 — Documenti e notifiche
- PDF: preventivo, conferma di prenotazione (con regolamento e coordinate del bonifico),
  consuntivo con ricevuta.
- Export Excel/CSV di prenotazioni e incassi per periodo, per la contabilità.
- Notifiche **solo email**, a ogni cambio di stato, a richiedente e gestione.

### D-20 — Pagine informative (realizzate con Wagtail, D-30)
- Emergenze (guardia medica, ospedali vicini, carabinieri…) e negozi/supermercati vicini: pubbliche.
- Informazioni interne (WiFi, raccolta differenziata…): **solo per i gruppi con prenotazione confermata**.
- Contenuto modificabile dalla redazione (P-15) nell'editor di Wagtail. I contenuti (numeri utili,
  negozi, WiFi, raccolta differenziata) li inserisce **direttamente la gestione nel backend**
  (decisione del 17/11/2026): non si raccolgono prima né si caricano con dati iniziali.

### D-21 — Grafica
- Logo della base (lupo), palette P-08, tema `django-agesci-campania-theme`, font del tema.
- PWA installabile (D-22).
- **Sorgenti del logo** (consegnati da Andrea il 17/11/2026, cartella `LoghiBaseAiello`):
  `logo.ai` (Illustrator 31, compatibile PDF, due versioni dello **scudo**: contorni neri e
  contorni bianchi), più PNG storici (lupo solo a 1x–4x, scudi, logo con scritta, PSD).
  Convertiti in SVG il 17/11/2026 (pdftocairo, testi in tracciati), salvati in
  `LoghiBaseAiello/svg/`, da copiare nel repo in F0 (`static/tana/img/logo/`):

  | File | Contenuto | Uso |
  | --- | --- | --- |
  | `scudo-base-aiello.svg` | scudo completo, contorni neri, emblema AGESCI e scritta | documenti, PDF, pagine chiare |
  | `scudo-base-aiello-bianco.svg` | scudo completo, contorni bianchi | intestazioni su fondo verde |
  | `lupo-base-aiello.svg` | solo il lupo, separazioni bianche (su fondo bianco appare come il logo del sito) | barra di navigazione, icone PWA, favicon |
  | `lupo-base-aiello-contorno.svg` | solo il lupo, contorno nero | stampa, fondi chiari |

  Le icone PWA (192, 512, maskable) e la favicon si generano da `lupo-base-aiello.svg`; i
  colori del lupo (`#72CB70`, `#27963C`, `#1D6434`) e del fondo dello scudo (`#3AAC6C`) si
  affiancano alla palette P-08.

### D-22 — PWA
Installabile su telefono per accedere a prenotazioni, listino e gestione in generale. **Nessun
uso offline**: serve la rete. Icone dichiarate tramite
`{% static %}` con `ManifestStaticFilesStorage`, per evitare il problema della cache delle icone
su iOS già incontrato in altri progetti.

### D-23 — Import da SuperSaaS
Comando CLI una tantum in fase di installazione (§7). SuperSaaS viene poi dismesso: nessuna
sincronizzazione, nessun funzionamento in parallelo.

### D-24 — Modifica della quota sulla singola prenotazione
La quota di una prenotazione può essere modificata o azzerata dall'amministratore (D-14),
sia sul preventivo sia sul consuntivo. Il preventivo calcolato resta visibile accanto
all'importo modificato.

### D-25 — Orizzonte massimo delle prenotazioni
- Data limite configurabile dalla gestione (oggi 30/09/2027): non si accettano prenotazioni con
  **data di arrivo** successiva.
- Serve a governare il cambio dei listini: l'orizzonte si sposta in avanti quando il nuovo
  listino è pubblicato.
- L'amministratore può inserire **prenotazioni prioritarie oltre la data limite** (es. date Fo.Ca.
  dell'anno successivo); le richieste dei gruppi oltre il limite sono bloccate nel modulo,
  senza lista d'attesa.

### D-26 — Arrivi e partenze (accoglienza)
Vista per la Pattuglia, pensata per il telefono (PWA), per accogliere i gruppi:
- arrivi e partenze di oggi e dei prossimi giorni, con area, persone previste, orari concordati,
  esclusiva, note;
- contatti del referente e del capo responsabile, con chiamata ed email diretti dal telefono;
- stato dei pagamenti (acconto versato, saldo da incassare) e collegamento al consuntivo.
Accesso: tutto il ruolo Pattuglia (e quindi anche amministratore e responsabile). Nessun ruolo
"accoglienza" separato.

### D-27 — Installazione sul server e integrazione con il frontend comune
Tana segue il contratto `docs/INTEGRAZIONE.md` del repo `AGESCI-Campania/agesci-campania-web-frontend`
(riletto il 17/11/2026) e, per script, unit systemd, backup e guida di installazione, il **modello
di Plancia 3.0** (repo `AGESCI-Campania/plancia`, branch `v3`, letto il 17/11/2026), richiesta
esplicita di Andrea. **Caddy** è l'unico reverse proxy del server, termina TLS con Let's Encrypt
e raggiunge i progetti sulla rete Docker condivisa `agesci-proxy`. Dettagli in §9.1–9.2. In sintesi:
- server nuovo Ubuntu 26.04, senza Virtualmin, Apache o altri proxy; progetto in `/opt/prenotazionebase`,
  proprietario l'utente **`agesci`** (gruppo `docker`, senza sudo; ci si entra con `sudo -iu agesci`);
- unit systemd **`prenotazionebase.service`** (avvio al boot dopo il reverse proxy), timer di backup
  notturno e, se approvata P-20, unit `.path` per l'aggiornamento dal web; installate dagli script,
  che senza sudo stampano il comando per l'amministratore;
- il server resta sempre su una **release** (tag `vX.Y.Z`, detached HEAD) come Plancia 3.0;
- solo il container d'ingresso (`nginx`) è su `agesci-proxy`, con alias **`tana-nginx`** (già
  previsto nello schema della guida); database, app e scheduler restano sulla rete `default`;
- **nessuna porta su `0.0.0.0`**, nessun TLS/certbot nel progetto, nginx interno in HTTP sulla 80;
- header inoltrati da Caddy passati così come sono (`$http_x_forwarded_proto`, mai `$scheme`);
- `scripts/installa.sh`, `scripts/aggiorna.sh` e `scripts/backup.sh` nello stile di Plancia 3.0 (§9.1);
- **guida dettagliata di prima installazione** nel repo (`docs/installazione.md`, §9.2);
- il blocco Caddy `caddy/sites/tana.caddy` **non** sta nel repo di Tana: si prepara e si consegna ad
  Andrea per il repo del frontend (insieme alla riga del registro progetti).

### D-28 — Login unico Sestante per la gestione
Contratto: `docs/INTEGRAZIONE-SSO.md` del repo `AGESCI-Campania/sestante` (letto il 17/11/2026, cita
già Tana); implementazione di riferimento: Plancia (`docs/guide/sso_sestante.md`,
`apps/accounts/adapters.py`).
- **Provider** allauth `openid_connect`, id **`sestante`** (uguale su tutte le piattaforme), nome
  "SSO AGESCI Campania"; slug Authentik `tana` (P-21): issuer/discovery
  `https://auth.agescicampania.net/application/o/tana/`, sempre l'URL pubblico, mai l'alias Docker.
- **Callback**: `https://<TANA_HOST>/accounts/oidc/sestante/login/callback/` (schema di allauth 65.x,
  da verificare con `reverse("openid_connect_callback", kwargs={"provider_id": "sestante"})` sulla
  versione installata prima di consegnare il blueprint); launch URL
  `https://<TANA_HOST>/accounts/oidc/sestante/login/?next=/gestione/`.
- **Credenziali** `SOCIAL_SESTANTE_CLIENT_ID` / `SOCIAL_SESTANTE_CLIENT_SECRET` solo in `.env`;
  vuote = pulsante nascosto e app comunque avviabile; `installa.sh` le elenca tra i passi manuali.
- **Blueprint** `blueprints/provider-tana.yaml` (provider confidential, authorization code, `sub`
  hashed, scope openid/profile/email/avatar; application con slug e launch URL): lo **prepara l'agente** e
  lo consegna ad Andrea, che lo aggiunge al repo `sestante` e lo applica. Mai modificare quel repo
  né creare provider a mano. Aggiornare anche il registro delle piattaforme del contratto SSO.
- **Primo login**: collegamento per email (case-insensitive) a un utente esistente, altrimenti
  creazione senza ruoli locali; senza email o con email duplicata → rifiutato con messaggio, nessun
  account parziale; email arrivate da Sestante marcate verificate; auto-signup solo per `sestante`.
- **Ruoli globali** dal claim `groups`, ricalcolati a ogni login SSO (create/revocate come nomine
  `da_sso=True`): `admin-multipiattaforma` → **Amministratore**, `segreteria` → **Segreteria
  regionale**. I ruoli locali (Pattuglia, Amministratore assegnato in Tana, Responsabile, Redazione)
  li assegna la segreteria in Tana (P-12) e il flusso SSO non li tocca mai.
- **Immagine del profilo** (scope `avatar`, contratto § 5.1): a ogni login SSO il claim `picture`
  di `userinfo` diventa l'immagine del profilo dell'editor del sito, solo per chi vi accede (dati
  minimi); un'immagine caricata a mano nell'editor prevale; il data-URI non resta in `extra_data`.
- **MFA**: la fa Sestante; Tana non la richiede a chi è entrato con Sestante **in questa sessione**
  (metodo di autenticazione della sessione, mai l'esistenza di un account collegato). Il superutente
  tecnico locale di emergenza (P-13) ha la MFA TOTP obbligatoria.
- **Logout**: chiude solo la sessione di Tana.
- **Login locale**: resta per i richiedenti (registrazione email) e per il superutente di emergenza;
  gli account di gestione non hanno password locale e i backend con password li rifiutano (P-13). Non è una transizione: Tana nasce nuova,
  senza utenti di gestione da migrare.
- **Test di fine installazione** (contratto § 8): utente nuovo, utente esistente collegato per
  email, membro di `segreteria`, utente senza gruppi.
- Sestante non è una dipendenza d'avvio della unit systemd: serve solo al login.
- P-12, P-13, P-19, P-21.

### D-29 — Email
- Mittente: casella dedicata **@agescicampania.net** (Google Workspace), nome da scegliere (es.
  `prenotazioni@`); risposte (`Reply-To`) alla casella della base
  `baseaiellodelsabato@campania.agesci.it`.
- Credenziali SMTP solo in `.env` (V-16 per il metodo di invio).
- Nessun indirizzo `@agescicampania.org` in codice, fixture o documentazione.

### D-30 — Sito della base con Wagtail
Le pagine statiche del sito della base, oggi su Google Sites
(`https://sites.google.com/agescicampania.net/baseaiello`, migrato dal vecchio dominio `.org` il 15/11/2026), entrano in Tana con **Wagtail**, il CMS
basato su Django, integrato nello stesso progetto (stesso database, login, tema e script).
Scelto il 14/11/2026 tra: editor di testo in un modello di Tana, WordPress separato, Google Sites
spostato sul Workspace `.net`.
- **Pagine**: Home, La storia, Gianni Sabatino, Le strutture, Info › Regolamento (testo e PDF),
  Emergenze, Negozi e servizi vicini, Info interne (riservata, D-20). Listino, Prenotazioni e
  Disponibilità **non** sono pagine Wagtail: sono pagine applicative di Tana (il listino si genera dai
  dati), collegate nel menu.
- **Redazione** (P-15): editor visuale a blocchi (P-16), bozze, anteprima, cronologia delle versioni,
  pubblicazione programmata, archivio di immagini e documenti. Nessuna conoscenza di HTML richiesta.
- **Accesso all'editor** con il login Sestante (D-28), interfaccia di Wagtail in italiano.
- **Info interne**: tipo di pagina con controllo di accesso personalizzato, che usa il servizio
  di Tana per verificare che l'utente abbia una prenotazione confermata.
- **Grafica**: i template delle pagine estendono quelli di `django-agesci-campania-theme`, con la
  palette P-08, logo del lupo, link a Facebook e Instagram della base nel piè di pagina.
- **Indirizzi**: Wagtail serve la radice del sito; le pagine di Tana hanno prefissi propri
  (es. `/prenotazioni/`, `/disponibilita/`, `/listino/`, `/gestione/`, `/accounts/`, `/cms/`) registrati prima
  della rotta generica di Wagtail. Stessi indirizzi relativi del Google Site (P-17).
- **Ricerca** nel sito con il backend su database di Wagtail (PostgreSQL), senza servizi esterni.
- **Versioni**: Wagtail 8.x, l'unica serie che supporta Django 6.1 (Wagtail 8.0: Django 5.2, 6.0,
  6.1; Python fino al 3.14). La serie LTS 7.4 arriva solo a Django 6.0. Wagtail si aggiorna nella
  stessa release in cui si aggiorna Django. Licenza BSD-3-Clause, compatibile con la licenza MIT di Tana.
- **Migrazione dei contenuti**: P-17, P-18. Tutte le pagine del Google Site (escluse Listino e
  Prenotazioni, che diventano pagine di Tana) si ricreano in Wagtail prima dell'avvio; poi il sito
  Google si spegne e il nome `www.baseaiello.agescicampania.net` passa al server (V-14).

### D-31 — Blocco delle prenotazioni
Decisa il 17/11/2026 (giro di prova prima dell'import, e in futuro ogni chiusura temporanea).
- Interruttore **«prenotazioni bloccate»** nella Configurazione, con un **messaggio** modificabile.
- Con il blocco attivo **nessuno** inserisce nuove prenotazioni, **gestione compresa**: il
  controllo è nel servizio che crea la richiesta, non solo nei moduli.
- Il messaggio compare **solo al posto del modulo** (richiesta del gruppo e prenotazione per la
  gestione); il resto del sito non cambia.
- Le prenotazioni già presenti seguono il flusso normale (approvazione, acconto, conferma,
  scadenze). L'import dello storico (§7) non è toccato dal blocco.
- Gli indirizzi web scritti nel messaggio diventano link.

### D-32 — Modalità demo
Decisa il 17/11/2026 (prova completa del sistema, import compreso, prima dell'apertura).
- Si **attiva** dalla Configurazione (amministrazione) **solo se non ci sono prenotazioni**.
- Mentre è attiva **prenota solo la gestione** (Pattuglia, amministratore, responsabile); gli altri
  vedono al posto del modulo un messaggio di prenotazioni non ancora aperte. Il controllo è nel
  servizio che crea la richiesta. L'import (§7) si può provare.
- **Registrazioni** con email e password **chiuse**: la pagina «Registrati» mostra il messaggio e
  il pulsante SSO; il primo accesso con Sestante crea l'account normalmente. Gli account esistenti
  entrano come sempre.
- **Email**: alla gestione partono normalmente; al richiedente **solo verso utenti con un ruolo**
  (mai ai referenti veri, es. delle prenotazioni importate, nemmeno dalle scadenze dello
  scheduler); oggetto con «[DEMO]». Nelle pagine di gestione un avviso ricorda la modalità.
- Si **termina** dalla Configurazione con una conferma esplicita: si cancellano **tutte** le
  prenotazioni con presenze, importi, pagamenti e ricevute, messaggi, consensi, contatti, il loro
  storico e la numerazione (le prenotazioni vere ripartono da AAAA-001). Restano account e ruoli,
  listini, categorie, configurazione e date bloccate. Attivazione e termine vanno nello storico
  della Configurazione.
- Se D-31 (blocco) è attivo prevale il blocco: nessuno prenota.
- Il messaggio per chi non è della gestione dice che le prenotazioni inserite non sono valide e,
  se impostato in Configurazione («dove prenotare durante la demo»), dà il link per prenotare
  davvero (in produzione `https://www.baseaiello.agescicampania.net/prenotazioni`). Alla gestione
  il modulo ricorda che la prenotazione è di prova.

### D-33 — Richiesta senza registrazione
Decisa il 17/11/2026 (non complicare la vita a chi prenota).
- La richiesta si compila **anche senza account**. All'invio i dati restano in attesa e il
  referente riceve un'email con un **link valido 24 ore**; il link apre una pagina con il pulsante
  «Conferma la richiesta» (aprire il link da solo non conferma: i controlli della posta lo fanno).
- **Le date si riservano solo alla conferma**, con i controlli di sempre; se nel frattempo si sono
  occupate, la pagina lo dice e invita a una nuova richiesta.
- Alla conferma la prenotazione va sull'**account con quell'email**, creato se manca (senza
  password, email verificata dal clic). Accesso automatico, con l'indicazione di usare «Password
  dimenticata?» per rientrare; **nessun accesso automatico** per gli account con un ruolo o per il
  superutente (entrano con SSO o password e verifica in due passaggi).
- Prima dell'invio senza account, «Non sono un robot» con **ALTCHA** (prova di lavoro risolta dal
  browser; nessun servizio esterno, widget nel progetto, chiave derivata dalla `SECRET_KEY`): ogni
  sfida vale 20 minuti e una volta sola. Scelto al posto di reCAPTCHA per non mandare dati a terzi.
- Al massimo 3 richieste da confermare per email nelle 24 ore; le richieste in attesa si
  cancellano dopo 24 ore (anche quelle confermate: la prenotazione ha già i dati).
- «Registrati» resta, ma non serve più: nel menu «Richiedi una prenotazione» c'è anche per chi non
  ha fatto l'accesso. In modalità demo (D-32) chi non è della gestione non invia richieste.

---

## 3. Modello dati

Nomi di dominio in italiano, codice in inglese (convenzione dei progetti). Importi in
**centesimi interi**. Date senza orario per i soggiorni (gli orari standard sono configurazione).

| Entità | Campi principali | Note |
| --- | --- | --- |
| `Area` | codice (`ACC`, `TENDE`), nome, capienza | capienza configurabile (109 / 6 piazzole) |
| `Struttura` | nome, descrizione, uso (condivisa / solo ACC / solo TENDE / non disponibile), ordine; galleria (`ImmagineStruttura`: immagine, didascalia, ordine) | D-12 |
| `Categoria` | codice, nome, prioritaria, listino_default, richiede_specifica | D-10 |
| `Listino` | tipo (associativo, extra, agevolato, gratuito), nome | D-08 |
| `VersioneListino` | listino, pubblicata_il, valida_dal, note | D-09; immutabile dopo la prima prenotazione che la usa |
| `VoceListino` | versione, attività, area, stagione (nessuna/estiva/invernale), unità, importo_centesimi | |
| `Configurazione` | blocco delle prenotazioni e messaggio (D-31), stagione invernale, % acconto, giorni acconto, soglia esenzione, termine consenso, orari standard, orizzonte massimo (D-25), anni di conservazione (D-18) | singleton |
| `Contatto` | nome, email, telefono, organizzazione | anche senza account (import, D-10) |
| `Prenotazione` | numero (`AAAA-NNN`), categoria, specifica_categoria, richiedente (utente, nullable), contatto, gruppo/ente (testo), unità presenti (Castorini, L/C, E/G, R/S, Co.Ca., Altro), arrivo, partenza, stato, esclusiva_richiesta, esclusiva_concessa, categoria_prioritaria_richiesta/concessa, versione_listino, note, id_supersaas | |
| `PresenzaArea` | prenotazione, area, persone_previste, persone_effettive | prenotazioni congiunte = due righe |
| `Occupazione` | prenotazione, area, intervallo `daterange` `[arrivo, partenza)`, attiva | D-05; exclusion constraint |
| `AttivitaGiornaliera` | prenotazione, data, tipo (uscita cucina, area verde, ospiti), persone | |
| `RichiestaConsenso` | richiesta, prenotazione_esistente, stato, scadenza | D-06 |
| `RigaImporto` | prenotazione, fase (preventivo / consuntivo), voce, quantità, prezzo, importo, rettifica (bool), deciso_da, motivazione | D-09, D-24 |
| `Pagamento` | prenotazione, tipo (acconto, saldo), importo, ricevuta (file), registrato_da, data | |
| `Messaggio` | prenotazione, mittente, destinatario, testo, letto | D-16 |
| `EventoStorico` | oggetto, azione, utente, deciso_da, motivazione, dati_prima/dopo | P-03 |
| Pagine del sito | tipi di pagina Wagtail: `HomePage`, `PaginaContenuto` (StreamField), `PaginaRiservata` (info interne) | D-30; sostituiscono il modello `PaginaInfo` previsto prima |
| `BloccoTecnico` | area, intervallo, motivo | manutenzione: fuori dalle categorie e dalle statistiche |

Scelte di F1 (Andrea, 17/11/2026):
- **Blocco tecnico**: tabella unica `Occupazione` con un tipo (prenotazione, esclusiva, blocco), così
  lo stesso exclusion constraint del database copre anche i blocchi. Il blocco si indica dal primo
  all'ultimo giorno **inclusi** (occupa `[dal, al + 1)`).
- **Numero** `AAAA-NNN`: anno di **creazione** della richiesta, contatore che riparte ogni anno,
  assegnato alla creazione e mai riusato (anche se la richiesta è rifiutata).
- **Versione iniziale** 2022/2023 di tutti i listini con pubblicazione e validità convenzionali al
  1/1/2022 (si applica anche a tutto lo storico importato).
- **Voci non note** (extra associativo in tenda, bivacco in tenda, agevolato) assenti: preventivo
  "da definire" (P-04). Listino **gratuito** con tutte le voci a 0 €.
- **Configurazione iniziale**: termine del consenso 7 giorni dalla domanda, comunque non oltre la
  vigilia dell'attività (D-06); orari standard arrivo 15:00, partenza 12:00 (D-04).

---

## 4. Stati della prenotazione

```
RICHIESTA ──approva──► APPROVATA (attesa acconto) ──ricevuta verificata──► CONFERMATA
    │                      │  └─ scade dopo N giorni ─► SCADUTA                │
    │                      └─ esenzione acconto ──────────────────────────────►│
    ├─ rifiuta ─► RIFIUTATA                                                    ▼
    └─ annulla ─► ANNULLATA  (possibile anche da APPROVATA e CONFERMATA)   SVOLTA ──► CHIUSA (consuntivo)
                                                                      NON_SVOLTA (solo storico importato, modificabile in SVOLTA)
```

- Occupazioni attive negli stati: `RICHIESTA` (P-01), `APPROVATA`, `CONFERMATA`, `SVOLTA`, `CHIUSA`.
- Liberano le date: `RIFIUTATA`, `SCADUTA`, `ANNULLATA`, `NON_SVOLTA`.
- `SVOLTA` si imposta dopo la data di partenza (manualmente o con il comando periodico, P-07).
- `CHIUSA`: consuntivo compilato e inviato.
- Ogni transizione genera email (D-19) ed evento di storico.

Scelte di F3 (Andrea, 17/11/2026):
- **Notifiche di gestione**: alla casella della base e agli utenti con il permesso «Riceve le
  notifiche di gestione», assegnabile a qualunque ruolo (ogni ruolo è un gruppo); di default
  Amministratore e Responsabile della base.
- **Acconto zero** (esenzione o soggiorno sotto la soglia): la prenotazione resta `APPROVATA`, senza
  scadenza, finché la Pattuglia non la conferma a mano.
- **Ricevuta**: caricata entro il termine ferma la scadenza anche se la verifica arriva dopo; la
  verifica (importo correggibile) porta a `CONFERMATA`; una ricevuta respinta fa ripartire il termine.
- **Rifiuto**: motivazione obbligatoria (con "deciso da", P-03); l'invio della motivazione nell'email
  al richiedente si sceglie al momento del rifiuto.
- `NON_SVOLTA` → `SVOLTA` (storico importato) solo dall'amministrazione e senza email.

Scelte di F4 (Andrea, 17/11/2026):
- **Chi prenota è il titolare**, anche se ha un ruolo di gestione: un amministratore capo di un
  gruppo prenota il suo campo come ogni richiedente. Solo le prenotazioni inserite *per conto
  della gestione* (area di gestione, F5) nascono senza titolare, con la categoria prioritaria
  assegnata come decisione discrezionale.
- **Consenso** (D-06): lo chiedono le attività in giornata a ogni prenotazione attiva con il
  gruppo in base quel giorno, **compresi i giorni di arrivo e di partenza**, e alle attività in
  giornata già richieste per quel giorno. Termine: `consenso_giorni` (7) dalla domanda, non oltre
  la fine della vigilia; se la domanda arriva la vigilia o il giorno stesso, le **8:00 del giorno
  dell'attività**. Consenso negato o scaduto: **nessun rifiuto automatico**, la richiesta non si
  approva e la rifiuta l'amministrazione. Se la prenotazione esistente non ha titolare, risponde
  l'amministrazione.
- **Messaggi** (D-16): con la gestione sempre; con un altro gruppo solo se le prenotazioni attive
  condividono un giorno (anche di cambio) o c'è una domanda di consenso tra loro. Email al
  destinatario con il testo; gli indirizzi dell'altro gruppo restano nascosti.
- **Telefono** dell'altro referente: si chiede e si vede solo se lui lo autorizza.
- Calendario pubblico (D-17) e pagina dei listini in vigore (con la versione successiva già
  pubblicata) fanno parte della F4. Riferimento grafico: i mockup del 15/11/2026.
- Ogni prenotazione ha anche il **capo responsabile** (D-18, D-26), oltre al referente.

Scelte di F5 (Andrea, 17/11/2026):
- **Area di gestione** `/gestione/` con la barra laterale del mockup 4. Blocchi tecnici, versioni di
  listino (con copia delle voci; nome e date correggibili, ed eliminazione, finché non usate),
  configurazione e **categorie** (dal 17/11/2026: codice fisso
  dopo la creazione, eliminazione solo se nessuna prenotazione la usa) si modificano lì; le
  **strutture nell'editor del sito** (D-12, dal 17/11/2026), che ha una voce per tornare alla
  gestione.
- **Modifica** di date e persone dall'amministrazione in ogni stato attivo, anche dopo l'acconto
  (P-02): il preventivo congelato resta e le differenze vanno nel consuntivo. Un acconto deciso
  all'approvazione (importo o esenzione) non si ricalcola; se diventa dovuto parte il termine.
- **Orari concordati** (D-26): li propone il richiedente o la Pattuglia; l'altra parte riceve
  un'email.
- **Statistiche** per **anno solare**: prenotazioni, presenze (persone × giorni) per area, ospiti
  in giornata, importi e incassi per categoria; giorni del Comune rispetto alla settimana del
  comodato; notti occupate per area e mese. **Export** Excel e CSV di prenotazioni e incassi per
  periodo libero.
- **Anonimizzazione** (D-18) dal 1° gennaio dell'undicesimo anno dopo quello della partenza:
  contatti svuotati (se non servono ad altre prenotazioni), utente scollegato, note, messaggi,
  richieste di telefono e ricevute cancellati; restano numero, categoria, gruppo, date, presenze,
  importi e pagamenti. La esegue lo scheduler.
- Permessi sugli importi: valorizzazioni, modifiche della quota e voci del preventivo solo
  all'amministrazione; voci del consuntivo, presenze effettive e pagamenti anche alla Pattuglia.
  Gli arrivi e le partenze mostrano solo prenotazioni approvate, confermate o in corso.

Scelte di F6 (Andrea, 17/11/2026):
- Approvate **P-15, P-16, P-17** (redazione, blocchi, pagine con gli stessi indirizzi) e **P-20**
  (aggiornamento dal web, come Plancia 3.0).
- **Regolamento in Tana**: il testo sta in una pagina Wagtail dedicata (cronologia delle versioni);
  il PDF lo genera Tana **solo alla pubblicazione** e ogni versione resta nell'archivio dei
  documenti; le email di conferma allegano l'ultima. Il PDF di Google Drive (gennaio 2023) è servito
  solo a popolare la prima versione, che nasce **in bozza**: va allineata alle regole di Tana prima
  di pubblicarla.
- **Contenuti del Google Site**: i dati di fatto (strutture, distanze, contatti, social) sono già
  nelle pagine; i testi lunghi (storia, Gianni Sabatino, ecc.) li fornisce Andrea; le foto le carica
  la redazione. Vecchi indirizzi: `/home` → `/`, `/info/listino-prezzi` → `/listino/`.
- **Le strutture**: introduzione e citazione di B.P. dall'editor; l'elenco si genera a ogni visita
  dalle strutture scelte nella pagina (D-12), raggruppato per area, con capienze e superfici nelle
  descrizioni e la galleria di ciascuna. Il palco con camerini non esiste più (i camerini sono depositi della base, non a
  disposizione dei gruppi): va tolto anche dal testo del regolamento in bozza.
- **PDF** di preventivo, conferma (con orari, coordinate del bonifico) e consuntivo con i pagamenti
  ricevuti; la conferma e il regolamento sono allegati all'email di conferma, il consuntivo a quella
  di chiusura.
- **PWA** installabile con service worker che va sempre in rete (nessun uso offline: senza rete
  mostra solo un avviso).

---

## 5. Calcolo del contributo

### 5.1 Algoritmo del preventivo
1. Listino: dalla categoria (D-10), salvo categoria prioritaria non ancora concessa (P-06) o
   rettifica dell'amministratore.
2. Versione: D-09.
3. Per ogni area con persone:
   - soggiorno a giorni: per ogni giorno da arrivo a partenza inclusi, voce della stagione di quel
     giorno × persone dell'area;
   - bivacco / pernotto extra associativo: notti = partenza − arrivo, × persone × voce a notte.
4. Attività in giornata e ospiti: persone × giorni × voce.
5. Voci libere (sovrapprezzo esclusiva, pellet, forfait, danni): righe manuali.
6. Totale unico anche per le prenotazioni congiunte, con dettaglio per area.
7. Acconto: % configurabile del totale; zero se i giorni sono ≤ soglia; modificabile (D-13).

### 5.2 Consuntivo
Persone effettive per area e voci extra (pellet al costo effettivo, danni, sovrapprezzi,
forfait). Ricalcolo con la **stessa versione di listino** del preventivo; saldo = totale − acconto
versato.

### 5.3 Listino iniziale (2022/2023, associativo salvo dove indicato)
| Voce | Importo | Unità |
| --- | --- | --- |
| Bivacco | 10,00 € | persona/notte |
| Campo invernale in accantonamento (1/11–15/3) | 10,00 € | persona/giorno |
| Campo estivo in accantonamento | 8,00 € | persona/giorno |
| Pernotto extra associativo (voce iniziale del listino extra associativo) | 15,00 € | persona/notte |
| Uscita con utilizzo cucina | 3,00 € | persona/giorno |
| Uscita area verde | 1,00 € | persona/giorno |
| Giornata genitori e ospiti (con uso cucina) | 1,00 € | persona/giorno |
| Campo in tenda | 5,00 € | persona/giorno |
| Riscaldamento a pellet | costo effettivo | voce libera |

### 5.4 Esempi verificati (calcolati con uno script)
| Caso | Calcolo | Totale | Acconto 50% |
| --- | --- | --- | --- |
| Accantonamento, 28 persone, lun 19 – sab 24/7/2027 | 28 × 6 gg × 8 € | 1.344,00 € | 672,00 € |
| Congiunta, 20 in accantonamento + 12 in tenda, stesse date | 20 × 6 × 8 + 12 × 6 × 5 | 1.320,00 € | 660,00 € |
| Accantonamento a cavallo di stagione, 20 persone, 13–17/3/2027 | 20 × 3 gg × 10 + 20 × 2 gg × 8 | 920,00 € | 460,00 € |
| Bivacco, 15 persone, sab–dom | 15 × 1 notte × 10 | 150,00 € | nessuno (2 gg ≤ 3) |

Gli esempi per gli extra associativi dipendono dalle voci del listino extra associativo, ancora da
configurare (D-08).

### 5.5 Scelte di F2 (Andrea, 17/11/2026)
- **Listino ordinario** di P-06: l'**associativo**, per tutte le categorie prioritarie chieste e non
  ancora concesse.
- **Bivacco automatico**: ogni soggiorno di **una sola notte** in un'area è un bivacco (a notti);
  da due notti in su è un campo (a giorni). Il bivacco in tenda, senza voce, risulta "da definire".
- Il conteggio a giorni o a notti segue l'**unità della voce** (uguale in tutte le stagioni di una
  voce): il «pernotto extra associativo» è il campo in accantonamento a persona/notte. Il bivacco
  extra associativo **non** usa il pernotto: resta "da definire" finché la gestione non lo inserisce.
- **Voci da definire** (P-04): righe senza prezzo; l'amministratore le valorizza con "deciso da" e
  motivazione, e il prezzo resta anche se il preventivo si ricalcola.
- **Acconto** arrotondato **al centesimo** (il mezzo centesimo per eccesso); zero per le sole
  attività in giornata.
- **Consuntivo**: dove mancano le persone effettive si usano le previste e la riga è segnata come
  stimata.
- **Modifica della quota** (D-24): una riga di rettifica per la differenza, così il totale calcolato
  resta visibile; una nuova modifica sostituisce la precedente.
- La prenotazione ha una **data della richiesta** (D-09), di default il giorno di creazione; per lo
  storico importato è quella reale.

---

## 6. Ruoli e permessi

| Azione | Pubblico | Richiedente | Pattuglia | Amministratore | Segreteria |
| --- | --- | --- | --- | --- | --- |
| Calendario libero/occupato, listini, strutture, pagine pubbliche | ✓ | ✓ | ✓ | ✓ | ✓ |
| Inviare, vedere e annullare le proprie richieste; caricare ricevute | | ✓ | | | |
| Info interne (WiFi) | | ✓ con prenotazione confermata | ✓ | ✓ | ✓ |
| Vedere tutte le prenotazioni | | | ✓ | ✓ | ✓ (sola lettura) |
| Verificare acconti, registrare pagamenti, compilare consuntivi, messaggi | | | ✓ | ✓ | |
| Arrivi e partenze con contatti dei gruppi (D-26) | | | ✓ | ✓ | |
| Approvare/rifiutare; decisioni discrezionali (D-14) | | | | ✓ | |
| Prenotazioni prioritarie senza contatti, blocchi tecnici | | | | ✓ | |
| Listini, strutture, configurazione | | | | ✓ | |
| Pagine del sito in Wagtail (anche il ruolo Redazione, P-15) | | | | ✓ | |
| Assegnare i ruoli di gestione in Tana (account di Sestante, anche pre-registrati per email e invitati su Sestante), nominare il responsabile della base | | | | | ✓ |
| Assegnare e revocare Pattuglia e Redazione, con l'invito su Sestante (P-12) | | | | ✓ | ✓ |

- Responsabile della base: nominato dalla segreteria; ha **gli stessi permessi dell'amministratore**.
  L'amministratore resta un ruolo tecnico, non necessariamente coincidente con il responsabile.
- Redazione (P-15): ruolo aggiuntivo, assegnato dalla segreteria, che dà accesso solo all'editor
  delle pagine del sito.
- Diarchia: i ruoli sono assegnazioni multiple, nessun ruolo è limitato a una persona.

---

## 7. Import da SuperSaaS (CLI una tantum)

```
manage.py import_supersaas --accantonamento prenotazioni.csv --tende campotende.csv --dry-run --report revisione.xlsx
manage.py import_supersaas --accantonamento prenotazioni.csv --tende campotende.csv --apply --decisioni revisione.xlsx
```

1. `--dry-run` legge i file, non scrive nel database e produce un file di revisione con una riga
   per prenotazione proposta (categoria, stato, unione, esclusiva, anomalie).
2. L'operatore corregge il file; `--apply` importa usando le decisioni del file, in un'unica
   transazione.

### 7.1 Formato dei CSV (verificato sull'export di novembre 2026)
- 17 colonne; la prima ha come intestazione il nome del calendario (`prenotazioni`, `campotende`)
  e contiene il "pacchetto" (Giornata, Bivacco, N Giorni).
- Campi tra virgolette con a capo interni: usare un parser CSV, mai lo split per righe.
- Date `g/m/aaaa` seguite da **più spazi** e `H:MM`. La fine può essere alle `23:59` o alle `0:00`
  del giorno dopo (in quel caso la data di partenza è il giorno precedente).
- Il pacchetto **non** corrisponde sempre alla durata reale: la durata si ricava dalle date.
- `Stato`: `In attesa di approvazione`, `Approvato` con spazi in coda.
- `Partecipanti (inclusi i capi)`: testo libero (`circa 35`, `TBD`, a volte un indirizzo o una
  città). Numero se ricavabile, altrimenti vuoto con anomalia e valore originale nelle note.
- `Gruppo`: testo libero, a volte con note o richieste (es. uso esclusivo).
- `Unità presenti`: codici separati da virgola: 1 Castorini, 2 L/C, 3 E/G, 4 R/S, 5 Co.Ca., 6 Altro.
- Email e telefoni a volte vuoti o con spazi; righe di prova create dall'amministratore.
- Gli orari sono casuali: si importano solo le date.

### 7.2 Regole
| Caso | Esito |
| --- | --- |
| Riga creata dall'amministratore con dati segnaposto (CFM, CFA, Comune…) | prenotazione prioritaria senza contatti; categoria proposta dal testo (CFA → Fo.Ca. nazionale, CFM e CFT → Fo.Ca. regionale, Comune → Comune di Aiello del Sabato) |
| Riga di prova | proposta di scarto, da confermare |
| Stesse date nei due calendari | proposta di prenotazione congiunta (l'email può differire: confronto su date e gruppo), da confermare |
| Testo che chiede l'uso esclusivo | segnalata per decidere l'esclusiva |
| Passata, `Approvato` | `SVOLTA`, storico in sola lettura |
| Passata, in attesa | `NON_SVOLTA`, modificabile in `SVOLTA` |
| Futura, `Approvato` | `CONFERMATA`; l'amministratore inserisce preventivo concordato e acconto versato |
| Futura, in attesa | `RICHIESTA` |
| Categoria non prioritaria | proposta dal testo (CNGEI nel nome o nell'email → Gruppo CNGEI; dominio `campania.agesci.it` o "AGESCI" → Gruppo AGESCI o Zone AGESCI…), sempre da confermare |
| Importi | non presenti nell'export: preventivo ricalcolato con il listino corrente e segnato "importato, da verificare" |
| Account | nessuno: solo `Contatto`; collegamento quando l'utente si registra con la stessa email verificata |
| Tracciabilità | `id_supersaas` conservato su ogni prenotazione |

- Un conflitto di occupazione tra righe importate interrompe l'import con un errore che indica le righe.
- Statistiche dell'export di novembre 2026: 50 righe accantonamento e 10 tende (11/2025 – 08/2027);
  16 righe dell'amministratore; 18 con partecipanti non numerici; 4 coppie con le stesse date
  nei due calendari. Export del 17/11/2026 (F7): 7 coppie con le stesse date (6 proposte come
  congiunte, una contiene una riga di prova), nessuna sovrapposizione nello stesso calendario.

Implementazione (F7, 17/11/2026):
- File di revisione Excel con una riga per prenotazione proposta, colonne gialle modificabili
  (azione, categoria, stato, unione, esclusiva, persone, tipo di uscita) e anomalie; `--apply`
  rifiuta un file senza la decisione di ogni riga dei CSV e si ferma su persone mancanti.
- Le righe dell'amministratore non sono tutte date riservate: solo CFM, CFT, CFA e Comune diventano
  prioritarie senza contatti; le altre (gruppi inseriti a mano) restano con il referente, segnalate.
- «Creato da» contiene il nome dell'account SuperSaaS, non i dati del referente: con
  `--amministratori` si indicano nome ed email dell'amministratore, e le righe con quei dati come
  referente sono proposte senza referente (colonna «Referente» modificabile), perché il
  collegamento per email le porterebbe sul suo account.
  Righe di prova: gruppo solo numerico o con «prova»/«test».
- Categoria proposta anche da «Città numero» (Gruppo AGESCI), «Sezione» (Gruppo CNGEI),
  «Associazione»/«A.p.s.» (terzo settore), «Campo di competenze» (eventi regionali).
- Prenotazioni con zero notti: attività in giornata (uscita con uso cucina proposta, modificabile).
- Numero `AAAA-NNN` con l'anno di creazione in SuperSaaS; nessuna email, nessuna domanda di consenso.
- Collegamento all'account alla conferma dell'email o all'accesso con email verificata.

---

## 8. Interfaccia

**Pubblico**: sito della base in Wagtail (home, storia, Gianni Sabatino, strutture, regolamento,
emergenze, negozi; D-30), calendario libero/occupato (mockup 1 del documento preliminare), listini
in vigore, registrazione/accesso.

**Richiedente**: nuova richiesta in passi (richiedente e categoria → soggiorno → riepilogo), con
preventivo in tempo reale e richiesta di esclusiva o di categoria prioritaria (mockup 2);
area personale con tappe, scadenza dell'acconto, caricamento della ricevuta, documenti, messaggi,
richieste di consenso ricevute, annullamento (mockup 3); info interne se confermata.

**Gestione**: arrivi e partenze per l'accoglienza (D-26), elenchi da approvare / acconti da verificare / consensi in scadenza / consuntivi,
calendario completo con nomi, scheda prenotazione con storico, consuntivo (mockup 4), listini e
versioni, strutture, configurazione, statistiche per categoria, export. Le pagine del sito si
modificano nell'editor di Wagtail (D-30).

Testi utente in italiano, senza codici di decisione.

---

## 9. Stack

| Componente | Scelta |
| --- | --- |
| Backend | Django ultima stabile (6.1 rilasciata il 05/08/2026; versione effettiva fissata in F0 con uv) |
| Python | ≥ 3.14, gestito con uv; comandi in `mise.toml` |
| Database | PostgreSQL 18 (necessario per `daterange` ed exclusion constraint), come Plancia 3.0 |
| Tema | `django-agesci-campania-theme` serie 3 (3.0.0a5 pre-release al 25/11/2026, Bootstrap 6 alpha.2), confermata da Andrea; si aggiorna di volta in volta (`uv add --prerelease allow`); palette P-08 |
| Autenticazione | django-allauth (P-10) |
| Sito della base | Wagtail 8.x (D-30), template sul tema regionale |
| PDF / Excel | WeasyPrint / openpyxl (P-09) |
| Scadenze | comando periodico (P-07) |
| PWA | manifest + service worker minimo scritto a mano, senza cache offline (D-22) |
| Email | SMTP configurabile da `.env` (D-29) |
| Login gestione | Sestante via OIDC (D-28) |
| Statici | WhiteNoise, `collectstatic` nel `Dockerfile` (manifest nell'immagine) |
| Esecuzione | Docker Compose; immagine `tana:locale` Python 3.14 slim con uv (versione fissata), gunicorn, librerie di sistema per WeasyPrint, utente non root; nginx interno; PostgreSQL 18; scheduler (P-11) |
| Avvio, backup, aggiornamenti | unit systemd e script sul modello di Plancia 3.0 (§9.1) |

Versioni e licenze effettive annotate in F0, mai scritte a memoria. Tag delle immagini Docker
fissati (mai `latest`), come nel repo del frontend.

### 9.1 Installazione (contratto `INTEGRAZIONE.md`, modello Plancia 3.0)

Riferimento operativo: repo `AGESCI-Campania/plancia`, branch `v3` (letto il 17/11/2026):
`scripts/`, `docker-compose.yml`, `Dockerfile`, `deploy/`, `.env.template`, sezione «Produzione» del
README. Tana ne riprende struttura, nomi delle funzioni e comportamento; le differenze sono indicate.

**Server**

| | |
| --- | --- |
| URL | `https://<TANA_HOST>` (V-14) |
| Repo sul server | `/opt/prenotazionebase`, utente `agesci` (gruppo `docker`, senza sudo né SSH: `sudo -iu agesci` da un amministratore) |
| Ingresso | servizio `nginx` (solo HTTP) su rete esterna `agesci-proxy`, alias `tana-nginx:80`; nessuna porta pubblicata, nessuna porta di debug (come Plancia) |
| Variabili | `.env` da `.env.template`, `chmod 600`, mai nel repo |
| Avvio al boot | unit `prenotazionebase.service` (`docker compose up -d --wait`, dopo `agesci-campania-web-frontend.service`) + `restart: unless-stopped` su tutti i servizi |
| Backup | `scripts/backup.sh` ogni notte (timer `prenotazionebase-backup.timer`, 02:30 + ritardo casuale) in `backups/` |
| Aggiornamento dal web (P-20) | `prenotazionebase-aggiorna.path` → `scripts/esegui-aggiornamento.sh` |

**Servizi del compose**

| Servizio | Ruolo | Rete | Note |
| --- | --- | --- | --- |
| `db` | PostgreSQL 18 (tag fissato, es. `postgres:18.x-trixie`) | default | volume montato su `/var/lib/postgresql` (layout della 18); healthcheck `pg_isready` |
| `web` | Django + gunicorn | default | immagine `tana:locale` costruita in locale (`pull_policy: never`); utente non root con uid/gid di `agesci` (build args `APP_UID`/`APP_GID`); **solo lui applica le migrazioni** all'avvio (`ESEGUI_MIGRAZIONI=1`, `deploy/entrypoint.sh`); statici con **WhiteNoise** e `collectstatic` nel `Dockerfile`; healthcheck su `/healthz/` con `Host` di `ALLOWED_HOSTS` e `X-Forwarded-Proto: https`, `start_period` lungo per le migrazioni |
| `scheduler` | comando periodico (scadenze acconti e consensi, stato `SVOLTA`, anonimizzazione a 10 anni) | default | stessa immagine `tana:locale`; healthcheck su file di battito (P-11). Plancia usa Celery beat + Redis: Tana non ne ha bisogno (P-07) |
| `nginx` | ingresso; media pubblici di Wagtail; allegati protetti | default + `agesci-proxy` (alias `tana-nginx`) | immagine nginx ufficiale con tag fissato e template `deploy/nginx/default.conf.template`; `client_max_body_size` adatto alle ricevute; `resolver` locale con `proxy_pass` su variabile, come Plancia, per non tenere in cache l'IP vecchio di `web` dopo un aggiornamento (502) |

Volumi: `tana_db`, `tana_media` (pubblici di Wagtail), `tana_privati` (ricevute, P-14), più i bind
mount `./logs` e, con P-20, `./aggiornamenti`.

**nginx interno** (estratto)

```nginx
resolver ${NGINX_LOCAL_RESOLVERS} valid=10s ipv6=off;
location / {
    set $app http://web:8000;
    proxy_pass $app;
    include /etc/nginx/conf.d/proxy-django.inc;   # Host, X-Forwarded-Proto $http_x_forwarded_proto (NON $scheme), -Host, -For
}
location /media/    { alias /srv/media/; }                   # solo immagini e documenti pubblici di Wagtail
location /protetti/ { internal; alias /srv/privati/; }       # ricevute: solo via X-Accel-Redirect (P-14)
location = /nginx-health { access_log off; return 200 "ok\n"; }
```

**Django** (valori da `.env`)

```python
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")              # es. baseaiello.agescicampania.net
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
```

Variabili come Plancia (`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `BASE_URL`, `DJANGO_SECRET_KEY`,
`POSTGRES_*`, `SOCIAL_SESTANTE_*`, email, `ADMIN_EMAILS`, `BACKUP_DIR`, `BACKUP_GIORNI`,
`GITHUB_TOKEN_RELEASES` con P-20); `DATABASE_URL` composta nel compose. Il dominio del `Site` di
Django si imposta da `ALLOWED_HOSTS` in `installa.sh`. IP del client dal penultimo
`X-Forwarded-For` (Caddy → nginx), mai `REMOTE_ADDR`.

**Script** (`scripts/`, eseguiti da `/opt/prenotazionebase` come `agesci`, mai root; bash
`set -euo pipefail`, messaggi in italiano, `shellcheck -x scripts/*.sh` pulito, bit eseguibile
committato)

| File | Contenuto |
| --- | --- |
| `_comune.sh` | **copia identica** di quello del frontend (rete, `.env`, `controlla_var_nuove`, `richiedi_albero_pulito`, `come_root`, `installa_servizio_systemd`, `attendi_salute`): non si modifica, si riallinea copiandolo |
| `_tana.sh` | funzioni di Tana, come `_plancia.sh`: `SERVIZI_SALUTE=(db web scheduler nginx)`, `APP_UID`/`APP_GID`, `manage`, `installa_backup_systemd`, `installa_aggiornamenti_systemd` (P-20), `costruisci_immagini`, `conserva_immagini`/`ripristina_immagini` (tag `precedente` di `tana:locale`), `servizi_sani`, `credenziali_mancanti` |
| `installa.sh` | prerequisiti (`docker`, `git`, `openssl`, rete `agesci-proxy`); `.env` da `.env.template` solo se manca, segreti con `openssl rand`, `chmod 600`; controllo variabili obbligatorie; avviso se il repo non è su un tag `vX.Y.Z`; cartelle `logs`, `backups`, `aggiornamenti/log`; build, `up -d`, attesa `healthy`; `Site` Django; **dati iniziali** idempotenti (`manage.py dati_iniziali`: aree, strutture, categorie, listini 2022/2023, configurazione, albero delle pagine Wagtail); **superutente di emergenza** con email da `TANA_ADMIN_EMAIL` o domanda, password generata e mostrata una sola volta, MFA al primo accesso; unit systemd; riepilogo dei **passi manuali** (DNS, blocco Caddy, credenziali Sestante, `ADMIN_EMAILS`, import SuperSaaS) |
| `aggiorna.sh` | come Plancia 3.0: si esegue da una copia temporanea (il checkout lo sostituisce); `--si`, `--stato-file`, `--id`, `--log`; albero pulito; `git fetch --tags`; versione = argomento o ultimo tag; novità da `CHANGELOG.md` tra installata e nuova; si ferma se la release chiede variabili nuove; **manutenzione** (`manage.py manutenzione attiva|disattiva|stato`); **backup del database** in `backups/` (ultimi 10); checkout del tag; build tenendo le immagini in uso come `precedente`; `up -d`; attesa `healthy`; unit systemd aggiornate. Se la release non risponde torna da solo alla precedente senza ricostruire; se le migrazioni erano già applicate resta in manutenzione e indica il backup da ripristinare |
| `backup.sh` | archivio unico con dump del database, `.env`, media pubblici e **allegati privati**; scritto con nome nascosto e rinominato alla fine; rotazione a `BACKUP_GIORNI`; istruzioni di ripristino nel commento iniziale |
| `esegui-aggiornamento.sh` | (P-20) runner lanciato da `prenotazionebase-aggiorna.service`: lock, `richiesta.json` → `in-corso.json`, validazione, `aggiorna.sh --si`, stato in `aggiornamenti/stato.json` |

- **Unit systemd** (tutte generate dagli script, mai scritte a mano; senza sudo stampano il comando
  `sudo bash -c '…'` per l'amministratore e proseguono):
  `prenotazionebase.service` (da `installa_servizio_systemd prenotazionebase "$UNIT_PROXY"`),
  `prenotazionebase-backup.service` + `.timer`, e con P-20 `prenotazionebase-aggiorna.service` + `.path`.
- **Deroga al § 3 della guida** (detached HEAD sul tag invece di `git pull --ff-only`): è la stessa
  di Plancia 3.0, già proposta ad Andrea per il testo di `INTEGRAZIONE.md`.
- L'import da SuperSaaS (§7) resta un comando separato, lanciato a mano dopo `installa.sh`.
- In locale i task di `mise.toml` rilevano il motore (`docker` o `podman`) con la variabile
  `COMPOSE`; gli script del server usano `docker compose` v2.

**Blocco Caddy da consegnare** (per `caddy/sites/tana.caddy` nel repo del frontend; lo stampa anche `installa.sh`)

```caddy
# Tana — Prenotazioni e sito della Base Scout «Gianni Sabatino»
# Repo: https://github.com/AGESCI-Campania/prenotazionebase
<TANA_HOST> {
	import comune
	reverse_proxy tana-nginx:80
}
```

Se si sceglie `baseaiello.agescicampania.net`, al momento dello spegnimento del Google Site si
aggiunge anche `www.baseaiello.agescicampania.net { redir https://baseaiello.agescicampania.net{uri} permanent }`
(V-14). Riga per il registro progetti della guida: `Tana | <TANA_HOST> | tana-nginx:80 | —`.

**Release**: dal Mac versione in `pyproject.toml`, sezione in `CHANGELOG.md` (letta da
`aggiorna.sh`), commit su `main`, poi `git tag vX.Y.Z && git push origin vX.Y.Z` e
`gh release create vX.Y.Z` con le note della sezione: tag e release sempre insieme, **prima**
dell'aggiornamento del server. Le variabili nuove vanno in `.env.template` nello stesso commit, con
un commento.

### 9.2 Guida di prima installazione (requisito di Andrea, 17/11/2026)

Nel repo `docs/installazione.md` (pubblicata anche nella documentazione MkDocs) e un riassunto nella
sezione «Produzione» del README, come Plancia. Deve permettere a un amministratore del server di
installare Tana da zero **senza conoscere il progetto**. Contenuto minimo:

1. **Prerequisiti**: server Ubuntu 26.04 con Docker e Compose v2; `agesci-campania-web-frontend`
   installato (rete `agesci-proxy`, unit `agesci-campania-web-frontend.service`); utente `agesci`;
   accesso amministrativo a Sestante; accesso al DNS di `agescicampania.net`; casella mittente (V-16).
2. **DNS**: record per `<TANA_HOST>` verso l'IP del server, e come verificarlo (`dig`).
3. **Cartella e clone**, come amministratore poi come `agesci`:
   ```bash
   sudo install -d -o agesci -g agesci /opt/prenotazionebase
   sudo -iu agesci
   git clone https://github.com/AGESCI-Campania/prenotazionebase.git /opt/prenotazionebase
   cd /opt/prenotazionebase && git checkout "$(git tag -l 'v[0-9]*' --sort=-v:refname | head -1)"
   ```
4. **`scripts/installa.sh`**: cosa fa passo per passo, cosa chiede (`TANA_ADMIN_EMAIL`), dove
   annotare la password mostrata una sola volta, come leggere l'esito.
5. **Unit systemd**: i comandi `sudo bash -c '…'` stampati dallo script, da eseguire come
   amministratore; verifica con `systemctl status prenotazionebase prenotazionebase-backup.timer`.
6. **Caddy**: aggiunta di `caddy/sites/tana.caddy` e della riga del registro nel repo del frontend,
   commit, push, `/opt/agesci-campania-web-frontend/scripts/aggiorna.sh`; verifica `curl -I`.
7. **Sestante**: consegna del blueprint `provider-tana.yaml`, applicazione nel repo `sestante`,
   copia di client id e secret in `.env` da `https://auth.agescicampania.net/if/admin/#/core/providers`,
   `docker compose up -d` (ricrea i container; `restart` non rilegge `.env`).
8. **Email**: variabili SMTP, `ADMIN_EMAILS`, invio di prova.
9. **Primo accesso**: superutente di emergenza + MFA; primo login Sestante; assegnazione dei ruoli
   (segreteria, amministratore, Pattuglia, redazione); i quattro test SSO del contratto.
10. **Configurazione iniziale nel backend**: importi mancanti dei listini, orizzonte, coordinate
    bancarie, contenuti delle pagine del sito (D-20, D-30).
11. **Import da SuperSaaS** (§7): dry-run, revisione, apply.
12. **Spegnimento dei sistemi vecchi**: SuperSaaS e Google Site; spostamento di
    `www.baseaiello.agescicampania.net` sul server (V-14).
13. **Verifiche finali**: checklist (HTTPS, redirect, login richiedente e Sestante, caricamento di
    una ricevuta e suo download protetto, email, PDF, backup notturno eseguito, `aggiorna.sh` a vuoto).
14. **Manutenzione**: aggiornamento (terminale e, con P-20, dal web), backup e **ripristino**
    passo per passo, diagnostica (`docker compose ps`, `docker compose logs --tail 100 web scheduler`,
    `tail -f logs/tana.log`, `systemctl status …`, log degli aggiornamenti), cosa fare se `aggiorna.sh`
    torna indietro o resta in manutenzione.

La guida si prova per intero in F8 su un server pulito (o una VM Ubuntu 26.04) e si corregge
finché non funziona senza interventi fuori testo.

Prova del 17/11/2026 (F8) su VM Ubuntu 26.04 arm64 (Lima), frontend simulato (rete
`agesci-proxy`, unit fittizia, Caddy di prova con `X-Forwarded-Proto: https`), release v0.9.0 →
v0.9.1 → v0.9.2: installazione secondo la guida senza interventi fuori testo; aggiornamento dal web
(P-20) e da terminale; ritorno automatico con una release rotta (database invariato); release rotta
dopo una migrazione (resta in manutenzione, recupero con la procedura della guida); ritorno manuale a
una release precedente; backup (anche dalla unit) e ripristino completo; avvio al boot. Correzioni
emerse: pacchetto `tana.aggiornamenti` escluso dal `.gitignore`, `libharfbuzz-subset0`
nell'immagine, pre-release di uv `explicit`, immagini precedenti e pagina di manutenzione di nginx
nel caso «database cambiato», default orari callable (W161 in CI).

**Messa in produzione** (guida del frontend § 4 + § 9.2): frontend già installato → DNS → clone e
`scripts/installa.sh` → unit systemd → blocco Caddy → Sestante → email → configurazione iniziale e
contenuti → import SuperSaaS → verifiche → spegnimento di SuperSaaS e del Google Site.

---

## 10. Fasi di sviluppo

| Fase | Contenuto |
| --- | --- |
| F0 | Repo `AGESCI-Campania/prenotazionebase`; progetto Django con uv/mise, tema, PostgreSQL 18, Docker Compose conforme a `INTEGRAZIONE.md`; `scripts/` sul modello di Plancia 3.0 (`_comune.sh` copiato, `_tana.sh`, `installa.sh`, `aggiorna.sh`, `backup.sh`) con le unit systemd, mantenuti in ogni fase successiva; comando `manutenzione`; `/healthz/`; loghi SVG (D-21); prima stesura di `docs/installazione.md`; CI (anche `shellcheck`), `CLAUDE.md`, `CHANGELOG.md` |
| F1 | Modello dati, vincoli di non sovrapposizione, configurazione, listini con i valori iniziali |
| F2 | Calcolo del preventivo e del consuntivo con test sugli esempi del §5.4 |
| F3 | Flusso richiesta → approvazione → acconto → conferma, scadenze, email; login Sestante (D-28) con adapter, ruoli globali e MFA, blueprint `provider-tana.yaml` pronto da consegnare |
| F4 | Area richiedente, consensi, messaggi |
| F5 | Area di gestione, decisioni discrezionali con storico, statistiche, export |
| F6 | Sito della base in Wagtail (tipi di pagina, template, redazione, pagina riservata), ricreazione di tutti i contenuti del Google Site (P-17, P-18), PDF, PWA; aggiornamento dal web (P-20) |
| F7 | Import SuperSaaS (dry-run, revisione, apply) |
| F8 | Prova completa della guida `docs/installazione.md` e di `installa.sh` su un server pulito, di `aggiorna.sh` tra due release (anche il ritorno indietro) e di backup/ripristino; installazione sul nuovo server (§9.1–9.2), Provider OIDC in Sestante, test SSO, import reale, blocco Caddy, spegnimento di SuperSaaS e del Google Site |

---

## 11. Verifiche aperte

| N. | Verifica | Come si procede intanto |
| --- | --- | --- |
| V-16 | *(si decide in codifica)* Nome della casella mittente e metodo di invio da Google Workspace (password per app o SMTP relay) | Variabili in `.env` |
| V-13 | Punti 11.1–11.9 della sintesi v0.2 in lettura alla Pattuglia: le risposte di Andrea del 10/11 valgono salvo diversa indicazione | Decisioni attuali |

Chiuse il 10/11/2026: V-02 (importi inseriti dalla gestione), V-03 (responsabile = amministratore),
V-04 (hosting), V-05 (titolare e conservazione), V-06 (listino extra con voci proprie), V-07 (area
verde senza sala), V-08 (frigo e fuochi per area), V-09 (niente offline), V-10 (CFT → Fo.Ca.
regionale), V-11 (consenso alla prima uscita), V-12 (orizzonte). Chiusa il 13/11/2026: V-01
(repository `AGESCI-Campania/prenotazionebase`). Chiusa il 17/11/2026 in F3: V-14 (indirizzo `baseaiello.agescicampania.net`; allo spegnimento
del Google Site `www.baseaiello.agescicampania.net` passa al server con redirect, blocco Caddy §9.1).
Chiuse il 17/11/2026: V-15 (Sestante secondo il
contratto `INTEGRAZIONE-SSO.md`, slug `tana`, blueprint preparato dall'agente: D-28, P-21; client id e
secret si copiano in `.env` all'installazione), V-17 (backup notturno di progetto con `backup.sh` e
timer systemd come Plancia 3.0; la copia fuori dal server della cartella `backups/` è compito
dell'amministratore del server), V-18 (il Google Site non si mantiene: si spegne all'avvio, P-18).

---

## 12. Vincoli per l'implementazione (da riportare in CLAUDE.md)

- **Anti-confabulazione**: verificare su codice, dati o documentazione prima di affermare; dichiarare
  le inferenze; mai inventare versioni, valori di listino o regole.
- **Importi** in centesimi interi; nessun `float` per denaro.
- **Non sovrapposizione** garantita dal database, non solo dai form.
- **Unica fonte di verità** per calcolo prezzi, disponibilità e permessi: un livello di servizi
  condiviso da viste, API, PDF, export e import.
- **Listino congelato** sulla prenotazione; versioni di listino immutabili una volta usate.
- **Ogni decisione discrezionale** con "deciso da" e motivazione (P-03).
- **Dati minimi** (D-18): nessun dato sui ragazzi; info interne solo ai confermati.
- **Import**: nessuna scrittura senza `--apply`; nessuna riga scartata in silenzio.
- **Testi utente** in italiano, codice e commenti in inglese.
- **Integrazione** (`INTEGRAZIONE.md` del frontend, da rileggere prima di toccare compose, nginx,
  HTTP/HTTPS o script): solo `nginx` su `agesci-proxy` con alias `tana-nginx`; nessuna porta su
  `0.0.0.0`; nessun TLS; header di Caddy passati invariati; impostazioni proxy di Django;
  healthcheck su tutti i servizi; script conformi; **non modificare il repo del frontend né quello
  di Sestante**: preparare i contenuti e consegnarli ad Andrea.
- **Modello Plancia 3.0** per tutto ciò che riguarda il server (repo `AGESCI-Campania/plancia`,
  branch `v3`): prima di scrivere o modificare `scripts/`, compose, `Dockerfile`, `deploy/` o le unit
  systemd, rileggere i file corrispondenti di Plancia e allinearsi; `_comune.sh` è una copia identica
  di quello del frontend. Mai `sudo` o root dentro `/opt/prenotazionebase`.
- **SSO** (`INTEGRAZIONE-SSO.md` di Sestante, da rileggere prima di toccare autenticazione e ruoli):
  provider id `sestante`; callback verificata sulla versione installata di allauth; ruoli globali solo
  da `admin-multipiattaforma` e `segreteria`; MFA saltata solo per sessioni Sestante; mai segreti nel
  repo; il login locale dei richiedenti non si tocca.
- **Guida di installazione** (§9.2) aggiornata nello stesso commit di ogni modifica a script,
  variabili, servizi o passi manuali.
- **Wagtail**: rotta generica di Wagtail registrata per ultima; solo i blocchi di P-16, mai HTML
  libero; Wagtail e Django aggiornati nella stessa release; file privati mai nel volume `media`.
- **Dominio** `agescicampania.net`: nessun riferimento a `agescicampania.org` nel codice, nella
  configurazione, nelle fixture e nelle email (i riferimenti storici di questo documento restano).

---

## 13. Riferimenti

- https://www.baseaiello.agescicampania.org — Home, Le strutture, Info › Regolamento, Info › Listino prezzi, Prenotazioni (consultato l'08/11/2026, sul vecchio dominio `.org` abbandonato)
- `AGESCI-Campania/agesci-campania-web-frontend` — `docs/INTEGRAZIONE.md` (§ 2.7 avvio al boot, § 3 script, utente `agesci`), `caddy/Caddyfile`, `scripts/_comune.sh` (riletti il 17/11/2026): https://raw.githubusercontent.com/AGESCI-Campania/agesci-campania-web-frontend/main/docs/INTEGRAZIONE.md
- `AGESCI-Campania/sestante` — `docs/INTEGRAZIONE-SSO.md` (letto il 17/11/2026): https://raw.githubusercontent.com/AGESCI-Campania/sestante/main/docs/INTEGRAZIONE-SSO.md
- `AGESCI-Campania/plancia`, branch `v3` (commit `661168b`, letto il 17/11/2026) — `scripts/` (`installa.sh`, `aggiorna.sh`, `backup.sh`, `esegui-aggiornamento.sh`, `_plancia.sh`, `_comune.sh`), `docker-compose.yml`, `Dockerfile`, `deploy/`, `.env.template`, README § Produzione, `docs/guide/sso_sestante.md`, `docs/piano-plancia-3.md`
- Sorgenti del logo della base: `logo.ai` (Illustrator 31, due versioni dello scudo) e PNG storici, consegnati da Andrea il 17/11/2026; SVG derivati in `LoghiBaseAiello/svg/` (D-21)
- Regolamento della base (PDF, aggiornato a gennaio 2023), collegato dalla pagina Regolamento
- Google Site della base: https://sites.google.com/agescicampania.net/baseaiello, anche su https://www.baseaiello.agescicampania.net (migrato dal `.org` il 15/11/2026, da spegnere all'avvio di Tana; pagine: Home, La storia, Gianni Sabatino, Le Strutture, Info › Regolamento, Info › Listino prezzi, Prenotazioni; letto il 14/11/2026)
- Wagtail, versioni e compatibilità con Django/Python: https://endoflife.date/wagtail (letto il 14/11/2026)
- `AGESCI-Campania/django-agesci-campania-theme` (v3.0.0a5, `docs/allauth.md`, `docs/branche.md`, `docs/palette.md`)
- Django 6.1 released: https://www.djangoproject.com/weblog/2026/aug/05/django-61-released/
- Documento preliminare v0.1 per la Pattuglia (08/11/2026) e risposte (10/11/2026)
