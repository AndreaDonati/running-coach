# Formato: seduta dettagliata

Prodotto di `plan-workout`. Tutte le sezioni sono obbligatorie.

```markdown
## [NOME SEDUTA] — [Fase] | [Data se nota]

### Overview
| Campo             | Valore                            |
|-------------------|-----------------------------------|
| Tipo              | Soglia / VO2max / Lento / ecc.    |
| Durata totale     | ~X min                            |
| Distanza totale   | ~X km                             |
| Scopo fisiologico | [quale sistema si allena]         |
| Beneficio gara    | [perché questa seduta adesso]     |

### Struttura Allenamento
| Fase       | Dist / Tempo | Pace Target | Zona | BPM Target | Note             |
|------------|-------------|-------------|------|-----------|------------------|
| Warm-up    | 2 km        | >6:00/km    | Z1   | <130      | Progressivo      |
| Main Set   | 5 × 6 min   | 4:20/km     | Z4   | 155–165   | Rec 2 min jog    |
| Cool-down  | 1.5 km      | >6:00/km    | Z1   | <130      |                  |

### Varianti
- **Più facile** (HRV bassa, o prima volta su questa seduta): [versione ridotta]
- **Più difficile** (forma eccezionale): [versione aumentata]

### Note Fisiologiche
[Cosa fanno le zone usate, quali adattamenti ci si aspetta, quanto recupero
serve prima della prossima seduta dura]

### Formato Garmin (lap-by-lap)
| Lap | Tipo        | Durata / Dist | Intensità Target        |
|-----|-------------|--------------|------------------------|
| 1   | Warm-up     | 2.0 km       | Cadenza libera, RPE 3  |
| 2   | Interval 1  | 6:00 min     | 4:20/km, RPE 7–8       |
| 3   | Recovery 1  | 2:00 min     | Jogging lento, RPE 3   |
| 4   | Interval 2  | 6:00 min     | 4:20/km, RPE 7–8       |
| ... | ...         | ...          | ...                    |
| N   | Cool-down   | 1.5 km       | Cadenza libera, RPE 2  |
```

Regole:

- I passi target **devono venire dalle attivita' reali dell'atleta**, non da
  tabelle VDOT o calcolatori. Se non ci sono sedute confrontabili recenti,
  dichiara l'assunzione che stai facendo.
- La tabella Garmin elenca **ogni lap singolarmente**: si copia nel Garmin
  riga per riga, quindi "5 ×" non serve a niente.
- Entrambe le varianti vanno sempre generate, anche quando non servono.
- Se HRV o carico recente suggeriscono di abbassare il tiro, dillo prima della
  tabella, non in fondo.
