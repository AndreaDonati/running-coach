# Formato: file settimana

Percorso: `athletes/<atleta>/plans/weeks/week_YYYY-MM-DD.md`, dove la data e'
**il lunedi'** della settimana.

E' il documento operativo: nasce con `start-week`, viene aggiornato in corsa da
`log-workout`, si chiude con `close-week`. Le quattro sezioni esistono fin dalla
creazione, anche vuote, perche' i comandi successivi sappiano dove scrivere.

```markdown
# Settimana [N] — [Fase] | Obiettivo: [nome gara primaria]
**Date**: LUN DD/MM – DOM DD/MM
**Settimane alla gara**: [N]

## Piano Settimanale
| Giorno | Data  | Allenamento           | Distanza | Intensità       | Stato |
|--------|-------|-----------------------|----------|-----------------|-------|
| LUN    | DD/MM | [tipo]                | X km     | Z[N] / X:XX/km  | ⬜    |
| MAR    | DD/MM | [tipo]                | X km     | Z[N]            | ⬜    |
| MER    | DD/MM | REST / cross-train    | —        | —               | ⬜    |
| GIO    | DD/MM | [tipo]                | X km     | Z[N]            | ⬜    |
| VEN    | DD/MM | REST / mobilità       | —        | —               | ⬜    |
| SAB    | DD/MM | [long / seduta chiave]| X km     | Z[N]            | ⬜    |
| DOM    | DD/MM | Recovery / REST       | X km     | Z1              | ⬜    |

**Volume totale previsto**: XX km
**Razionale**: [perché questo carico e questo mix di sedute stanno in piedi
data la fase e le settimane che mancano alla gara]

## Log Allenamenti Completati
_(aggiornato durante la settimana)_

## Aggiustamenti Attivi
_(aggiornato durante la settimana)_

## Chiusura Settimana
_(compilato a fine settimana)_
```

Stato: `⬜` da fare, `✅` fatta. Una seduta saltata resta `⬜` e viene nominata
in chiusura: non si riscrive il piano per farlo tornare.
