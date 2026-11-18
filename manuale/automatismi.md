# Email e scadenze automatiche

## Le email di Tana

Le email hanno l'oggetto che inizia con «[Base Aiello]» e arrivano:

- **al gruppo**: all'email del referente e a quella dell'account che ha fatto la richiesta;
- **alla gestione**: alla casella della base e agli utenti che ricevono le notifiche di gestione
  (di default amministratore e responsabile).

| Quando | Oggetto | A chi |
| --- | --- | --- |
| richiesta inviata senza account | Conferma la tua richiesta di prenotazione (link valido 24 ore) | il referente |
| richiesta inviata | Richiesta di prenotazione N ricevuta | gruppo e gestione |
| approvata | Prenotazione N approvata (con importo, scadenza e dati del bonifico) | gruppo e gestione |
| rifiutata | Richiesta di prenotazione N non accolta | gruppo e gestione |
| annullata | Prenotazione N annullata | gruppo e gestione |
| ricevuta caricata | Ricevuta dell'acconto N da verificare | gestione |
| ricevuta respinta | Ricevuta dell'acconto N da ricaricare | gruppo e gestione |
| confermata | Prenotazione N confermata (allegati: conferma e regolamento in PDF) | gruppo e gestione |
| scaduta | Prenotazione N scaduta | gruppo e gestione |
| dopo il soggiorno | Grazie per il soggiorno alla base (N) | gruppo e gestione |
| consuntivo inviato | Consuntivo della prenotazione N (allegato: consuntivo in PDF) | gruppo e gestione |
| consenso richiesto | Richiesta di consenso per la prenotazione N | il gruppo già presente e la gestione |
| consenso risposto | Risposta alla richiesta di consenso (N) | il gruppo che l'ha chiesto e la gestione |
| nuovo messaggio | Nuovo messaggio sulla prenotazione N | l'altra parte della conversazione |
| date o persone modificate | Prenotazione N modificata | gruppo e gestione |
| orari concordati | Orari concordati per la prenotazione N | la parte che non li ha inseriti |
| pagamento registrato | Pagamento registrato per la prenotazione N | gruppo e gestione |
| telefono | Richiesta del tuo telefono / Risposta alla richiesta del telefono | i gruppi interessati |

In **modalità demo** l'oggetto inizia con «[DEMO]» e le email al gruppo partono solo verso utenti
di Tana con un ruolo.

## Le scadenze

Tana controlla le scadenze da sola, ogni pochi minuti:

- **Acconto**: una prenotazione approvata senza ricevuta entro la scadenza diventa **scaduta**, le
  date si liberano e il gruppo riceve un'email.
- **Consenso**: una richiesta di consenso senza risposta entro la data diventa **negata**; la
  richiesta del gruppo resta in esame e la decide l'amministrazione.
- **Soggiorno svolto**: una prenotazione confermata diventa **svolta** il giorno dopo la partenza e
  passa tra i consuntivi da compilare.
- **Dati personali**: dopo gli anni di conservazione indicati in Configurazione (di default 10,
  contati dalla fine dell'anno della partenza) i dati personali delle prenotazioni si
  anonimizzano; restano date, presenze e importi per le statistiche e la contabilità.
- **Richieste da confermare**: quelle inviate senza account si cancellano dopo 24 ore, confermate
  o no.

| Scadenza | Valore di default | Dove si cambia |
| --- | --- | --- |
| acconto | 50% del preventivo, entro 7 giorni dall'approvazione; esenti i soggiorni fino a 3 giorni | Configurazione › Acconto |
| consenso | 7 giorni, al massimo fino all'inizio dell'attività; se la richiesta arriva alla vigilia o il giorno stesso, entro le 8:00 del giorno dell'attività | Configurazione › Richieste e dati |
| conservazione dei dati | 10 anni | Configurazione › Richieste e dati |
