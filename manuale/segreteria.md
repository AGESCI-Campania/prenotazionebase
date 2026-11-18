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
| **Segreteria regionale** | consultazione di tutto, assegnazione di tutti i ruoli |

Il dettaglio, voce per voce, è in {doc}`ruoli`.

Anche **amministratore e responsabile** aprono questa pagina, ma assegnano e revocano solo
**Pattuglia** e **Redazione** (vedi {doc}`amministrazione`).

**Assegnare un ruolo**: in «Assegna un ruolo» inserisci l'**Email dell'utente** e il **Ruolo**, poi
**Assegna**. Se la persona non è ancora entrata in Tana, l'account viene creato subito con il ruolo
(«Account creato per … sarà attivo al primo accesso con Sestante.») e in tabella compare
**in attesa del primo accesso con Sestante**: al primo accesso con Sestante con la stessa email trova già i suoi
ruoli. Controlla bene l'indirizzo: deve essere quello del suo account Sestante, se ne ha già uno.

**Invito su Sestante**: se la persona non è mai entrata con Sestante, Tana le manda un'email con il
link per creare l'account del login unico regionale («Inviato a … il link per creare l'account
Sestante (valido fino al …)»). Il link vale 7 giorni e l'account creato vale **solo per Tana**; chi
ha già un account Sestante con quell'email entra direttamente con l'SSO. Sotto il nome compaiono
la data dell'invito e la scadenza; **Rimanda l'invito** rispedisce lo stesso link, o uno nuovo se
è scaduto (nei due minuti dopo un invio non rispedisce niente: protegge dai doppi clic). Se Sestante non risponde compare «L'invito … non è partito»: il ruolo resta assegnato,
riprova più tardi con **Rimanda l'invito**. Se gli inviti non sono configurati sul server, Tana
ricorda che la persona deve farsi creare l'account dalla Segreteria regionale.

**Revocare**: accanto al ruolo, **revoca**. Se era l'ultimo ruolo di una persona non ancora
iscritta su Sestante, anche l'invito viene revocato.

```{figure} schermate/utenti-ruoli.png
:alt: Utenti e ruoli: una riga per utente con tutti i suoi ruoli.

Utenti e ruoli: una riga per utente con tutti i suoi ruoli.
```

:::{note}
I ruoli con l'etichetta **Sestante** (Amministratore e Segreteria regionale) arrivano dal login
unico regionale e si ricalcolano a ogni accesso: non si revocano da Tana ma su Sestante.
:::
