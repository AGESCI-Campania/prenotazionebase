# Amministratore e responsabile della base

Amministratore e responsabile della base hanno gli stessi permessi: tutto quello che fa la
{doc}`Pattuglia <pattuglia>`, più le decisioni sulle richieste e la configurazione della base.

## Decisioni discrezionali: «Deciso da» e «Motivazione»

Le eccezioni alle regole (uso esclusivo, categoria prioritaria, acconto diverso dal previsto,
rifiuto, voci di prezzo da definire, prenotazioni per conto della gestione) chiedono sempre due
campi:

- **Deciso da**: chi ha preso la decisione (es. «Pattuglia», «IRO»), anche se non è chi la
  inserisce;
- **Motivazione**: perché.

Restano nello **Storico** della prenotazione.

## Approvare o rifiutare una richiesta

Le richieste nuove sono in «Da approvare». Nella scheda, riquadro **Approvazione**:

- avvisi se manca il **consenso** di un gruppo già presente o se il **preventivo ha voci da
  definire**;
- **Concedo l'uso esclusivo** / **Concedo la categoria prioritaria**, se il gruppo li ha chiesti;
- **Acconto (€)**: vuoto = quello previsto dal regolamento, zero = esenzione, un altro importo =
  acconto diverso;
- **Deciso da** e **Motivazione**, solo per concessioni o acconto diverso dal previsto.

**Approva**: il gruppo riceve l'email con importo, scadenza e dati del bonifico (o la notizia che
l'acconto non è dovuto).

**Rifiuta…**: chiede «Deciso da» e «Motivazione»; con **Comunica la motivazione al richiedente**
la motivazione va anche nell'email al gruppo. Le date si liberano.

:::{note}
Se un gruppo già presente non ha dato il consenso entro la scadenza, il consenso è negato ma la
richiesta resta in esame: decidi tu se rifiutarla o modificarla.
:::

```{figure} schermate/scheda-approvazione.png
:alt: Una richiesta in esame: il riquadro «Approvazione» con acconto, «Deciso da» e motivazione.

Una richiesta in esame: il riquadro «Approvazione» con acconto, «Deciso da» e motivazione.
```

## Preventivo e voci di prezzo

Nella scheda, riquadro **Preventivo**:

- **Valorizza** una voce «da definire» indicando **Prezzo unitario (€)**, «Deciso da» e
  «Motivazione»;
- **Aggiungi una voce o modifica la quota**: una voce libera (voce, quantità, prezzo) oppure una
  **Nuova quota totale (€)**;
- **togli** una voce libera aggiunta per errore.

Dal momento della conferma, o da quando il gruppo ha caricato una ricevuta, il preventivo è
**congelato**: le differenze si sistemano nel consuntivo, dove puoi anche **modificare la quota
del consuntivo**.

## Modificare o annullare una prenotazione

- **Modifica date e persone**: arrivo, partenza, persone per area e un **motivo** che va
  nell'email al gruppo. Si può anche dopo l'acconto: il preventivo resta quello e le differenze
  vanno nel consuntivo.
- **Annulla**: le date tornano libere; l'acconto versato resta alla base.
- **Correggi in svolta**: per una prenotazione segnata «non svolta» che invece c'è stata.

## Prenotazione per conto della gestione

Dal Cruscotto, **Prenotazione per la gestione**: per le date riservate a eventi prioritari (Fo.Ca.,
eventi regionali, Comune). Si scelgono la **Categoria** (solo prioritarie), l'**Evento o gruppo**,
le date, le persone e le note, con «Deciso da» e «Motivazione». Può superare la data di apertura
delle prenotazioni e non ha referente; nasce in esame e va approvata come le altre.

```{figure} schermate/prenotazione-gestione.png
:alt: La prenotazione per conto della gestione.

La prenotazione per conto della gestione.
```

## Menu Configurazione

### Date bloccate

Per rendere un'area non prenotabile (manutenzione, lavori): **Area**, **Dal**, **Al (incluso)**,
**Motivo**, poi **Blocca le date**. Le date compaiono come non disponibili nel calendario pubblico
e non contano nelle statistiche. **Togli** le libera di nuovo. Non si possono bloccare date già
occupate.

```{figure} schermate/date-bloccate.png
:alt: Le date bloccate.

Le date bloccate.
```

### Listini e versioni

Ogni listino ha più **versioni** nel tempo. A una prenotazione si applica la versione già
pubblicata alla data della richiesta e in vigore il primo giorno del soggiorno, per tutto il
soggiorno.

- **Nuova versione**: listino, nome (es. «2028»), **Pubblicata il**, **Valida dal** (non prima della
  pubblicazione) e, di solito, **Copia le voci da** una versione esistente. Poi si correggono i
  prezzi nella pagina della versione e **Salva le voci**.
- Finché nessuna prenotazione la usa, nella pagina della versione si possono correggere **nome e
  date** (**Salva nome e date**) o **eliminarla**.
- Una versione **in uso** non si modifica più: per cambiare i prezzi da una certa data si crea una
  nuova versione con quella data di validità.

```{figure} schermate/listini.png
:alt: Listini e versioni, con il riquadro per una nuova versione.

Listini e versioni, con il riquadro per una nuova versione.
```

### Categorie

Le categorie «Associazione o ente» tra cui scelgono i gruppi: **nome**, **codice** (fisso dopo la
creazione), **listino di default**, **prioritaria**, **Richiede la specifica**, **ordine**. Una
categoria usata da almeno una prenotazione non si elimina.

```{figure} schermate/categorie.png
:alt: Le categorie.

Le categorie.
```

### Configurazione

- **Prenotazioni bloccate** e **messaggio di blocco**: con il blocco attivo **nessuno**, nemmeno la
  gestione, inserisce nuove prenotazioni; al posto del modulo compare il messaggio (gli indirizzi
  web scritti nel messaggio diventano link). Le prenotazioni esistenti proseguono normalmente.
- **Stagione invernale**: il periodo, ripetuto ogni anno, delle tariffe invernali.
- **Acconto**: percentuale, giorni per caricare la ricevuta, soggiorni esenti fino a N giorni.
- **Orari standard** di arrivo e partenza.
- **Bonifico dell'acconto**: IBAN, intestatario, causale (`{numero}` e `{gruppo}` si sostituiscono).
- **Richieste e dati**: giorni per il consenso, **prenotazioni aperte fino a** (data massima di
  arrivo), anni di conservazione dei dati personali.

```{figure} schermate/configurazione.png
:alt: La pagina Configurazione, con in fondo il riquadro della modalità demo.

La pagina Configurazione, con in fondo il riquadro della modalità demo.
```

#### Modalità demo

Per provare il sistema prima dell'apertura, import compreso. Il riquadro compare **solo se non ci
sono prenotazioni** (per attivarla) o se la demo è attiva (per terminarla).

- Mentre è attiva prenotano solo Pattuglia, amministratore e responsabile; la registrazione con
  email e password è chiusa (si entra con l'SSO); le email ai richiedenti partono solo verso
  utenti con un ruolo e hanno «[DEMO]» nell'oggetto. Un avviso lo ricorda in ogni pagina della
  gestione e nel modulo di richiesta.
- Chi non è della gestione legge che le prenotazioni inserite qui non sono valide e, se è
  impostato il campo **dove prenotare durante la demo** della Configurazione, trova il link per
  prenotare davvero.
- **Termina la demo**, dopo aver spuntato la conferma, **cancella tutte le prenotazioni** con
  pagamenti, ricevute, messaggi e storico; la numerazione riparte. Account, listini, categorie,
  configurazione e date bloccate restano. Non si può annullare.

### Strutture e Pagine del sito

**Strutture** e **Pagine del sito** aprono l'editor del sito: vedi {doc}`redazione`. Le strutture
(nome, uso, ordine, descrizione, galleria) le modificano solo amministratore e responsabile; nella
pagina «Le strutture» si spuntano quelle da mostrare.

### Aggiornamenti

Mostra la **versione installata** e l'**ultima release**, con le novità. **Aggiorna a …** avvia
l'aggiornamento del server: Tana va in manutenzione, si fa il backup, si installa la nuova
versione e, se qualcosa non va, si torna alla precedente.

- Serve un **accesso recente** (ultimi 5 minuti): se richiesto, conferma la tua identità o esci e
  rientra con Sestante.
- Durante l'aggiornamento la pagina mostra l'avanzamento; mentre Tana si riavvia indica da quanti
  secondi non risponde e riprende da sola. Gli altri utenti vedono una pagina di manutenzione che
  si ricarica ogni 30 secondi.

## Notifiche

Amministratore e responsabile ricevono le email di gestione (nuove richieste, ricevute da
verificare, messaggi…), insieme alla casella della base.
