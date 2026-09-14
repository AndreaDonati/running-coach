# Formato: log di stagione

Percorso: `athletes/<atleta>/plans/season.md`.

Una riga per settimana chiusa, in ordine cronologico. È l'indice narrativo di
`plans/weeks/`: dice cosa è successo e perché, e da quale file andare a leggere
il dettaglio.

Lo scrive `close-week`, in coda, subito dopo aver compilato la Chiusura
Settimana. **Non si rigenera da uno script**: i file settimana sono prosa, e un
parser che li legge si romperebbe alla prima volta che cambia il modo di
scrivere un piano.

```markdown
| Settimana | Fase | → gara | Previsto | Effettivo | Aderenza | Nota |
|-----------|------|-------:|---------:|----------:|---------:|------|
| 2026-09-07 | Build | 9 | 45 km | 48 km | 85% | Soglia 3×10 tenuta a 5:40/km. Lunedì saltato. |
```

Regole:

- **Una riga, una settimana.** Se una riga non ci sta, il posto giusto è la
  Chiusura Settimana del file corrispondente, non qui.
- La **Nota** dice la cosa che conta per capire la settimana dopo: cosa ha
  funzionato, o cosa è saltato e perché. Non un riassunto del piano.
- **Le righe passate non si riscrivono.** Se una valutazione si rivela
  sbagliata, lo si annota nella riga nuova.
- Aderenza sotto il 70% per due settimane di fila: va nominato nella Nota, è il
  segnale che il piano è tarato male e non che l'atleta non si impegna.

## Cosa sta dove

| Domanda | File |
|---------|------|
| Quanto ho corso davvero, settimana per settimana | `training_data/weekly.md` (generato) |
| Cosa era previsto e perché, e com'è andata | `plans/season.md` (una riga per settimana) |
| Il dettaglio di una settimana | `plans/weeks/week_YYYY-MM-DD.md` |

I numeri di `weekly.md` sono generati dalle attività a ogni sincronizzazione:
non copiarli a mano in `season.md`, mettici il **previsto** e il giudizio.
