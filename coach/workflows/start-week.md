# Workflow: start-week

**Input**: nome atleta.
**Output**: un file nuovo `athletes/<atleta>/plans/weeks/week_YYYY-MM-DD.md`
(data del lunedi').

## Procedura

1. Leggi `athletes/<atleta>/profile.md`, sezione **Obiettivi**:
   - gara primaria: nome, data, distanza, D+, target
   - giorni mancanti -> settimane mancanti -> **fase** (Base / Build / Peak / Taper)
   - obiettivi secondari che cadono nelle prossime 4 settimane

   Se la data della gara primaria manca, fermati e chiedila: senza quella la
   fase non e' derivabile e il piano sarebbe arbitrario.

2. Leggi la sezione **Comportamento reale osservato** di `profile.md`, se c'e'.
   Le regole scritte li' hanno precedenza sul piano teorico: sono state
   ricavate da settimane di dati veri.

3. Leggi `training_data/weekly.md` (le ultime 4-6 righe) e `plans/season.md`
   (le ultime righe): danno carico reale e giudizio delle settimane recenti
   senza aprire un file per settimana. La tendenza su 4 settimane conta piu'
   della settimana singola.

4. Apri l'ultimo file in `plans/weeks/` e leggine la **Chiusura Settimana**:
   segnali di fatica e focus indicato per questa settimana.

5. Leggi `training_data/health_status.md` se esiste. Se non esiste — ed e' il
   caso normale — usa quello che c'e' in `profile.md` e dichiara su cosa ti
   stai basando.

6. Calcola la data del lunedi' e scrivi il file usando
   `coach/formats/week-file.md`.

7. Verifica quello che hai appena scritto:

   ```bash
   pipeline/.venv/bin/python pipeline/week_check.py <atleta>
   ```

   Non giudica se il piano e' buono — quello e' compito tuo. Controlla le cose
   meccaniche su cui e' facile scivolare: i sette giorni, le date coerenti con
   la settimana, il volume dichiarato che torna con la somma della colonna
   Distanza, il salto rispetto al carico reale delle ultime sei settimane, le
   sedute intense consecutive, le sezioni che `/log-workout` e `/close-week` si
   aspettano di trovare.

   Correggi i problemi bloccanti prima di mostrare il piano. Sugli avvisi
   decidi tu: una settimana di carico con due sedute vicine puo' essere voluta,
   ma dillo nel Razionale invece di lasciarlo implicito.

## Regole

- I passi target si derivano dalle attivita' reali delle ultime 2-3 settimane
  (`training_data/activities/`), non da tabelle generiche.
- Se la settimana precedente segnalava fatica, riduci volume o intensita' nei
  primi due giorni: e' li' che si paga il debito, non il sabato.
- Se un obiettivo secondario cade in questa settimana, quel giorno diventa la
  seduta chiave e i giorni attorno si adattano.
- Il **Razionale** deve dire perche' *questo* carico in *questa* fase a *N*
  settimane dalla gara. Se e' una frase che varrebbe per qualsiasi settimana,
  riscrivila.
