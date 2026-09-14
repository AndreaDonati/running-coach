# Workflow: close-week

**Input**: nome atleta.
**Output**: sezione **Chiusura Settimana** compilata nella settimana attiva,
piu' una proposta a voce per quella successiva.

## Procedura

1. Apri la settimana attiva in `athletes/<atleta>/plans/weeks/` e leggila
   intera: Piano Settimanale, tutte le voci di Log, Aggiustamenti Attivi.

2. Leggi `athletes/<atleta>/profile.md`: settimane mancanti alla gara primaria
   e fase corrente.

3. Leggi `training_data/health_status.md` se esiste, per la fotografia finale
   di HRV e sonno. Se non esiste, scrivi `n.d.` nel consuntivo.

4. Compila la sezione usando `coach/formats/week-closing.md`.

5. Aggiungi **una riga** in coda a `athletes/<atleta>/plans/season.md`, nel
   formato di `coach/formats/season-log.md`. I km effettivi li trovi già
   calcolati in `training_data/weekly.md`: non ricontarli a mano.

6. **Poi**, nella conversazione e non nel file, proponi la direzione della
   settimana successiva in 3-4 frasi: fase, direzione del volume, seduta
   chiave. **Non creare il file della settimana nuova** finche' non te lo
   chiedono esplicitamente.

## Regole

- Le sedute saltate si nominano. Un consuntivo che fa quadrare i conti non
  serve a nessuno.
- Aderenza sotto il 70%, o segnali di recupero cattivi: raccomanda una
  settimana di scarico prima di aumentare il carico, esplicitamente.
- Il **Focus settimana prossima** deve citare fase e conto alla rovescia.
- Se lo scarto fra pianificato ed effettivo si ripete da 3-4 settimane nella
  stessa direzione, il problema e' la **taratura del piano**, non l'atleta.
  Le ultime righe di `plans/season.md` lo rendono visibile in un colpo d'occhio:
  se quattro righe di fila hanno l'effettivo sopra (o sotto) il previsto,
  proponi di aggiornare la sezione "Comportamento reale osservato" di
  `profile.md` coi numeri veri, e da li' in poi pianifica su quelli.
- Quando una seduta non ha funzionato per come era **prescritta** — passo
  irrealistico, seduta impossibile da incastrare, intensita' sbagliata per la
  fase — scrivilo nella Nota di `season.md` come limite del piano, non come
  mancanza dell'atleta. E' l'unica traccia che resta di quando il coach ha
  sbagliato, e serve a non ripetere l'errore.
