# TODO

Lavori pianificati e non ancora realizzati. Ogni voce diventa una proposta nella specifica
(`docs/Tana_Progettazione.md`) solo dopo l'approvazione di Andrea.

## Ruoli di gestione personalizzati

*Pianificato il 18/11/2026. Da decidere prima di realizzare: vedi «Decisioni aperte».*

Gli amministratori creano nuovi ruoli di gestione scegliendo i permessi da una tabella come
quella del manuale (`manuale/ruoli.md`): per esempio «Cassa» (ricevute, pagamenti, statistiche)
o «Accoglienza» (solo arrivi e partenze).

### Come funziona oggi

- I ruoli sono un elenco fisso nel codice (`Ruolo` in `tana/accounts/models.py`).
- Ogni controllo di `tana/accounts/permessi.py` dice quali ruoli servono, e un controllo copre
  più righe della tabella. Per esempio `e_pattuglia` (Pattuglia, Amministratore, Responsabile)
  copre pagamenti, messaggi, arrivi, consuntivi e altro.
- Editor del sito, Strutture ed email di gestione passano dai gruppi Django dei ruoli, con i
  permessi assegnati solo da `dati_iniziali` (`PERMESSI_DEI_RUOLI`).

### Proposta

1. **Catalogo fisso di permessi**, uno per riga della tabella del manuale: consultare le
   prenotazioni, statistiche ed export, arrivi e partenze, ricevute e pagamenti, messaggi e
   soggiorno, approvare e decidere, modificare e annullare, prenotazioni della gestione e date
   bloccate, listini e configurazione, aggiornamenti, editor del sito, Strutture, assegnare
   ruoli, email di gestione, informazioni riservate. Sta nel codice, perché ogni permesso
   corrisponde a controlli nel codice.
2. **Ruoli di base come preimpostazioni** del catalogo, non modificabili: Pattuglia,
   Amministratore, Responsabile della base, Redazione, Segreteria regionale.
3. **Ruoli personalizzati**: nuova pagina Configurazione › **Ruoli**, con nome, descrizione e
   una casella per ogni permesso ammesso.
4. **`permessi.py` resta l'unica fonte**: i controlli diventano «ha il permesso X», calcolato
   dai ruoli attivi della persona (i permessi si sommano). Flusso, viste, menu ed export cambiano
   solo il controllo che chiamano, non la logica.
5. **Gruppi Django allineati in automatico** dai permessi del ruolo (editor del sito, Strutture,
   email di gestione), non più solo da `dati_iniziali`.
6. **Assegnazione** da *Utenti e ruoli* come per Pattuglia e Redazione: invito su Sestante,
   accesso solo con l'SSO, badge di attesa del primo accesso.
7. **Storico**: creazione, modifica e disattivazione di un ruolo nello storico, con chi l'ha
   fatto. Un ruolo con persone assegnate non si cancella: si disattiva.

### Fasi

- **A.** Rifattorizzare `permessi.py` sul catalogo con le preimpostazioni dei ruoli di base. Un
  test blocca la tabella attuale: ogni ruolo di base deve poter fare esattamente quello che fa
  oggi. Nessun cambiamento visibile.
- **B.** Modello dei ruoli personalizzati, pagina *Ruoli*, allineamento dei gruppi, storico.
- **C.** Assegnazione e inviti; tabella del manuale generata dal catalogo; specifica (nuova
  proposta, §6) e manuale.

### Decisioni aperte

1. **Chi crea i ruoli?** «Solo gli amministratori» vuol dire Amministratore e Responsabile della
   base (oggi hanno gli stessi permessi)? Anche l'amministratore globale da Sestante? E la
   Segreteria regionale?
2. **Quali permessi può contenere un ruolo personalizzato?** Se un amministratore può creare un
   ruolo con «approvare», «configurazione» o «assegnare ruoli», di fatto crea nuovi
   amministratori, aggirando la regola per cui Amministratore e Responsabile li nomina solo la
   segreteria (P-12). Proposta:
   - **ammessi**: i permessi operativi, cioè quelli di Pattuglia e Redazione, più statistiche ed
     export;
   - **mai**: approvare e decidere, modificare e annullare, listini e configurazione,
     aggiornamenti, Strutture, assegnare ruoli.
3. **Chi assegna i ruoli personalizzati?** Proposta: amministrazione e segreteria, come per
   Pattuglia e Redazione.
4. **Granularità**: bastano le righe della tabella attuale, o alcune vanno separate (per esempio
   «verificare le ricevute» e «registrare i pagamenti», oggi nella stessa riga)?
