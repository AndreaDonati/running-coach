# Workflow: log-workout

**Input**: nome atleta.
**Output**: la settimana attiva aggiornata sul posto.

Da lanciare dopo aver eseguito la pipeline: le attivita' nuove arrivano in
`training_data/activities/` solo dopo `pipeline/run_pipeline.py <atleta>`.

## Procedura

1. Trova la **settimana attiva**: il file in `athletes/<atleta>/plans/weeks/`
   il cui intervallo LUN-DOM contiene oggi. Leggilo tutto: quali giorni sono
   gia' `✅`, quali voci di log esistono gia'.

2. Scorri `athletes/<atleta>/training_data/activities/`:
   - leggi la data di ogni `activity_*.md`
   - tieni quelle che cadono nell'intervallo della settimana attiva **e** non
     compaiono gia' nel Log

3. Per ognuna:
   - annunciala: `Trovata nuova attività: [data] — [tipo] [distanza]`
   - leggi il file per intero
   - confrontala con la seduta pianificata per quel giorno

4. Aggiorna il file settimana:
   - marca `✅` il giorno corrispondente nel Piano Settimanale
   - aggiungi una voce in **Log Allenamenti Completati**
     (`coach/formats/log-entry.md`)
   - se lo scarto dal piano e' significativo — carico molto sopra o sotto,
     segnale di dolore, passo inatteso — aggiungi o aggiorna una voce in
     **Aggiustamenti Attivi** per i giorni che restano, col perche'

5. Se non c'e' niente di nuovo: rispondi
   `Nessuna nuova attività trovata per questa settimana.` e fermati.

## Regole

- **Le voci gia' scritte non si toccano.** Si aggiunge in coda e si modificano
  solo i giorni futuri.
- Gli aggiustamenti sono minimi e giustificati: cambia solo cio' che il dato
  nuovo rende necessario. Non riscrivere la settimana.
- Un'attivita' non pianificata si logga comunque: fa parte del carico reale.
- Se l'attivita' e' su tapis roulant, il passo non e' confrontabile con
  l'outdoor: valuta sulla FC e dillo nella nota.
- Se emerge fatica o dolore, segnalalo esplicitamente e proponi aggiustamenti
  conservativi.
