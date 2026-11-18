# Pattuglia: la gestione quotidiana

La Pattuglia lavora nell'area **Gestione** (menu in alto). Quello che vede la Pattuglia lo vedono
anche amministratore e responsabile della base, che hanno in più le funzioni del capitolo
{doc}`amministrazione`.

## Il menu della gestione

La barra laterale ha tre sezioni a fisarmonica (se ne apre una alla volta):

- **Prenotazioni**: «Cruscotto», «Da approvare», «Acconti da verificare», «Consensi in attesa»,
  «Consuntivi», «Messaggi senza risposta», «Tutte le prenotazioni», «Calendario», «Arrivi e
  partenze». Il numero accanto al titolo è il totale delle cose da fare.
- **Configurazione**: solo amministrazione e segreteria.
- **Report**: «Statistiche», «Export contabilità».

## Cruscotto

I riquadri contano le **richieste da approvare**, le **ricevute da verificare**, i **consensi in
attesa**, i **consuntivi da compilare** e i **messaggi senza risposta**; sotto, **Oggi alla base**:
chi arriva e chi parte oggi.

```{figure} schermate/cruscotto.png
:alt: Il cruscotto della gestione, con la barra laterale.

Il cruscotto della gestione, con la barra laterale.
```

## Gli elenchi

Ogni voce del menu apre l'elenco corrispondente (numero, gruppo, categoria, date, stato). In
«Tutte le prenotazioni» si può cercare per **numero, gruppo o referente** e filtrare per **stato**.
Da un elenco si apre la **scheda** della prenotazione.

```{figure} schermate/elenco-acconti.png
:alt: L'elenco «Acconti da verificare».

L'elenco «Acconti da verificare».
```

## La scheda di una prenotazione

In alto lo stato e le azioni del momento; sotto preventivo, messaggi e storico; a lato gruppo,
documenti, orari, pagamenti e consensi.

### Acconti da verificare

Quando il gruppo carica la ricevuta arriva un'email «Ricevuta dell'acconto … da verificare». Nella
scheda, riquadro **Acconto**:

1. **apri la ricevuta** e controlla importo e causale;
2. se è corretta premi **Verificata: conferma la prenotazione**: il gruppo riceve la conferma con il
   PDF e il regolamento;
3. se non va bene scrivi **Perché la ricevuta non va bene** e premi **Respingi la ricevuta**: il
   gruppo riceve il motivo e la scadenza riparte.

Se l'acconto non è dovuto compare «Nessun acconto dovuto»: premi **Conferma la prenotazione**.

```{figure} schermate/scheda-acconto.png
:alt: La scheda di una prenotazione con una ricevuta da verificare.

La scheda di una prenotazione con una ricevuta da verificare.
```

### Pagamenti

Nel riquadro **Pagamenti** si registrano gli importi incassati: **Tipo** (acconto o saldo),
**Importo (€)**, **Data del pagamento**, poi **Registra**. Un acconto registrato su una
prenotazione approvata la conferma.

### Orari

Nel riquadro **Orari** si salvano **Arrivo concordato** e **Partenza concordata** (senza, valgono
gli orari standard della configurazione). Il gruppo riceve un'email.

### Messaggi

In **Messaggi con il gruppo** scrivi nel campo «Risposta della Pattuglia» e premi **Invia**. I
messaggi a cui la gestione non ha ancora risposto sono in «Messaggi senza risposta».

### Storico

Ogni passaggio (cambi di stato, decisioni, pagamenti, modifiche) resta nello **Storico**, con chi
l'ha fatto e, per le decisioni, chi le ha prese e perché.

## Calendario

Il mese con, per ogni giorno, le aree occupate e da chi («Area: gruppo», con «(esclusiva)» o «In
giornata»), le **date bloccate** e i giorni liberi. Colori: in esame, approvata, confermata o
svolta, date bloccate.

```{figure} schermate/calendario.png
:alt: Il calendario della gestione.

Il calendario della gestione.
```

## Arrivi e partenze

Per **Oggi**, i prossimi **7 giorni** o il **Mese**: chi arriva, chi parte e chi viene in giornata,
con l'orario (concordato o standard), l'acconto versato o da incassare e i pulsanti per chiamare o
scrivere al **Referente** e al **Capo responsabile**, e per aprire il **Consuntivo**.

```{figure} schermate/arrivi.png
:alt: «Arrivi e partenze» dei prossimi 7 giorni.

«Arrivi e partenze» dei prossimi 7 giorni.
```

## Dopo il soggiorno: il consuntivo

Il giorno dopo la partenza Tana segna da sola la prenotazione come **svolta** e la mette in
«Consuntivi». Puoi anche farlo tu dalla scheda con **Segna come svolta**, dopo la partenza.

Dalla scheda, **Consuntivo**:

1. **Presenze effettive**: le persone che sono venute davvero, area per area (vuoto = quelle
   previste), poi **Prepara il consuntivo** (o **Ricalcola il consuntivo**);
2. **Aggiungi una voce** per pellet, danni o sovrapprezzi;
3. controlla **Totale**, **Acconto versato** e **Saldo dovuto**;
4. **Chiudi e invia al gruppo**: il gruppo riceve il consuntivo in PDF;
5. quando il gruppo paga, **Registra il pagamento del saldo**.

```{figure} schermate/consuntivo.png
:alt: La pagina del consuntivo.

La pagina del consuntivo.
```

## Report

- **Statistiche**: per anno, prenotazioni, presenze, ospiti, importi e incassi per categoria; i
  giorni usati dal Comune; i grafici delle **presenze per mese** (previste ed effettive) e
  dell'**occupazione per mese** di ogni area. Passando sopra una barra si legge il valore.

```{figure} schermate/statistiche.png
:alt: Le statistiche dell'anno.

Le statistiche dell'anno.
```
- **Export contabilità**: scegli il periodo, **Prenotazioni** (per data di arrivo) o **Incassi**
  (per data del pagamento) e il formato (Excel o CSV), poi **Scarica**.
