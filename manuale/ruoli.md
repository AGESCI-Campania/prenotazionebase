# Ruoli e permessi

Cosa può fare ciascun ruolo in Tana. I ruoli si sommano: chi ne ha più di uno (per esempio
Pattuglia e Redazione) ha i permessi di tutti. I ruoli si assegnano in Configurazione › **Utenti e
ruoli** (vedi {doc}`segreteria`).

## Senza un ruolo

**Chiunque, anche senza account**
: vede il sito della base, il calendario delle disponibilità e il listino prezzi; può mandare una
  richiesta di prenotazione confermandola con il link ricevuto per email.

**Gruppi ed enti** (account con email e password)
: inviano e seguono le proprie richieste, le annullano, caricano la ricevuta dell'acconto,
  indicano gli orari di arrivo e partenza, scrivono alla Pattuglia, rispondono alle richieste di
  consenso e di telefono. Le informazioni riservate del sito (per esempio il WiFi) le vedono solo
  con una prenotazione confermata. Non entrano nella gestione e non vedono le prenotazioni degli
  altri (vedi {doc}`richiedenti`).

## Ruoli di gestione

Chi ha un ruolo di gestione entra **solo** con «Accedi con SSO AGESCI Campania» (vedi
{doc}`accesso`).

| Cosa | Pattuglia | Amministratore, Responsabile della base | Redazione | Segreteria regionale |
| --- | :---: | :---: | :---: | :---: |
| Cruscotto, elenco e schede delle prenotazioni, calendario | ✓ | ✓ | | ✓ (solo consultazione) |
| Statistiche ed export contabilità | ✓ | ✓ | | ✓ |
| Arrivi e partenze, con i contatti dei gruppi | ✓ | ✓ | | |
| Verificare o respingere le ricevute, registrare i pagamenti, confermare senza acconto | ✓ | ✓ | | |
| Messaggi con i gruppi, orari, «svolta», consuntivo e chiusura | ✓ | ✓ | | |
| Approvare o rifiutare le richieste, decisioni con «Deciso da» e «Motivazione» | | ✓ | | |
| Modificare date e persone, annullare, preventivo e voci di prezzo | | ✓ | | |
| Prenotazioni per conto della gestione, date bloccate | | ✓ | | |
| Listini, categorie, configurazione, modalità demo | | ✓ | | |
| Aggiornamenti di Tana | | ✓ | | |
| Editor del sito: pagine, immagini, documenti | | ✓ | ✓ | |
| Strutture nell'editor del sito | | ✓ | | |
| Assegnare e revocare **Pattuglia** e **Redazione** (con l'invito su Sestante) | | ✓ | | ✓ |
| Assegnare e revocare **Amministratore**, **Responsabile della base**, **Segreteria regionale** | | | | ✓ |
| Email di gestione (nuove richieste, ricevute da verificare, messaggi…) | | ✓ | | |
| Informazioni riservate del sito | ✓ | ✓ | ✓ | ✓ |

- **Amministratore** e **Responsabile della base** hanno gli stessi permessi in Tana.
- Amministratore e Segreteria regionale con l'etichetta **Sestante** arrivano dal login unico
  regionale: valgono come quelli assegnati in Tana, ma si tolgono su Sestante.
- La **Segreteria regionale** vede tutto ma non modifica le prenotazioni.
- In **modalità demo** inseriscono prenotazioni solo Pattuglia, amministratore e responsabile.
- Le email di gestione arrivano di serie ad amministratore e responsabile, oltre che alla casella
  della base; per altri ruoli le attiva il superutente tecnico (vedi {doc}`automatismi`).
