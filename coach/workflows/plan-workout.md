# Workflow: plan-workout

**Input**: atleta e descrizione della seduta
(es. `andrea: soglia 5x6min, fase build`).
**Output**: una seduta completa nel formato `coach/formats/workout-detail.md`.

## Procedura

1. Estrai dall'input: atleta, tipo di seduta (soglia, VO2max, lento, lungo,
   velocita', forza), contesto aggiuntivo (fase, giorno, vincoli di tempo,
   note su infortuni).

2. Leggi `athletes/<atleta>/profile.md`:
   - fase corrente (dalle settimane mancanti alla gara primaria)
   - FC max e FC a riposo, per le zone
   - **affidabilita' della FC da polso**: se e' inattendibile su questo atleta,
     governa la seduta a passo e RPE e scrivilo nella seduta
   - vincoli o infortuni attivi

3. Trova le **3 attivita' simili piu' recenti** in
   `athletes/<atleta>/training_data/activities/`:
   - soglia -> ripetute o medi recenti
   - lungo -> lunghi recenti
   - VO2max -> ripetute brevi recenti

   Da li' ricava passo reale a quello sforzo, FC media, distanza. Sono questi i
   riferimenti, non i calcolatori.

4. Leggi `training_data/health_status.md` se esiste: se l'HRV e' sotto l'80%
   della media a 4 settimane, prescrivi la variante **Più facile** e di'
   perche'. Se il file non esiste, dichiara che stai lavorando senza dato di
   recupero.

5. Se oggi cade dentro una settimana attiva in `plans/weeks/`, leggila:
   conferma a quale giorno e' assegnata questa seduta e guarda quelle
   adiacenti. Seduta dura ieri? Lungo domani? Segnala l'accumulo.

6. Scrivi la seduta con `coach/formats/workout-detail.md`.

## Regole

- I passi vengono dai dati dell'atleta. Se non ci sono sedute confrontabili
  abbastanza recenti, dichiara l'assunzione invece di inventare un numero.
- Genera sempre **entrambe** le varianti, piu' facile e piu' difficile.
- La tabella Garmin elenca ogni lap singolarmente: serve per essere copiata
  nell'orologio riga per riga.
- Mai una seduta di qualita' il giorno dopo un'altra, salvo che il piano
  settimanale lo preveda esplicitamente.
- Se HRV o carico recente dicono di abbassare il tiro, dillo prima della
  tabella.
