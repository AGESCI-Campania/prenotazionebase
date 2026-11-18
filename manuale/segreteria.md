# Segreteria regionale

La Segreteria regionale **vede tutte le prenotazioni in sola lettura** (elenchi, schede,
calendario, statistiche, export) e **assegna i ruoli** di Tana. «Arrivi e partenze», che serve
all'accoglienza in base, è solo della Pattuglia e dell'amministrazione. Il ruolo arriva da Sestante
(gruppo `segreteria`) o si assegna in Tana.

## Utenti e ruoli

Menu Gestione › Configurazione › **Utenti e ruoli**. La tabella ha una riga per utente con tutti i
suoi ruoli: chi ne ha più di uno ha i permessi di tutti (per esempio Amministratore e Segreteria
regionale insieme).

| Ruolo | Cosa può fare |
| --- | --- |
| **Pattuglia** | gestione quotidiana: acconti, pagamenti, orari, messaggi, arrivi e partenze, consuntivi |
| **Amministratore**, **Responsabile della base** | tutto quello della Pattuglia, più approvazioni, decisioni, listini, categorie, configurazione, strutture, aggiornamenti |
| **Redazione** | pagine del sito della base |
| **Segreteria regionale** | consultazione di tutto, assegnazione dei ruoli |

**Assegnare un ruolo**: in «Assegna un ruolo» inserisci l'**Email dell'utente** e il **Ruolo**, poi
**Assegna**. Se la persona non è ancora entrata in Tana, l'account viene creato subito con il ruolo
(«Account creato per … sarà attivo al primo accesso con Sestante.») e in tabella compare
**in attesa del primo accesso**: al primo accesso con Sestante con la stessa email trova già i suoi
ruoli. Controlla bene l'indirizzo: deve essere quello del suo account Sestante.

**Revocare**: accanto al ruolo, **revoca**.

```{figure} schermate/utenti-ruoli.png
:alt: Utenti e ruoli: una riga per utente con tutti i suoi ruoli.

Utenti e ruoli: una riga per utente con tutti i suoi ruoli.
```

:::{note}
I ruoli con l'etichetta **Sestante** (Amministratore e Segreteria regionale) arrivano dal login
unico regionale e si ricalcolano a ogni accesso: non si revocano da Tana ma su Sestante.
:::
