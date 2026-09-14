# Profilo — [Nome Cognome]

> Questo e' l'unico file che scrivi tu: tutto il resto lo genera il sistema
> dalle tue attivita'.
>
> Non serve compilarlo a mano da cima a fondo — `/onboard` lo fa con te, facendo
> le domande una alla volta e riempiendo da solo quello che si ricava dai dati.
> Se preferisci scriverlo tu, sostituisci le righe fra parentesi quadre: quelle
> lasciate cosi' vengono lette come "non disponibile", non come un valore.

---

## Anagrafica

- **Nome**: [nome cognome]
- **Sport principali**: [es. corsa su strada, trail, escursionismo]
- **Dati disponibili da**: [mese anno della prima attivita' scaricata]
- **Zona**: [dove si allena — serve per capire dislivello e terreno tipici]

## Forma attuale

- **Livello**: [principiante / amatore allenato / competitivo]
- **Volume settimanale tipico**: [km/sett — se non lo sai, scrivi n.d.]
- **Trend recente**: [in crescita / stabile / rientro da stop]
- **Focus**: [endurance / velocita' / dislivello]

## Storico

- **Anni di allenamento**: [n]
- **Risultati chiave**: [gare, PB, traguardi — citare le fonti nei dati]
- **Punti di forza (con evidenza)**: [affermazioni ancorate a numeri reali
  presi da `training_data/`, non impressioni]
- **Da migliorare (con evidenza)**: [idem]

## Recupero

- **Sonno tipico**: n.d.
- **HRV di riferimento**: n.d.
- **FC a riposo**: n.d.
- **Peso / altezza**: n.d.
- **FC massima**: n.d.
- **FC da polso attendibile**: n.d.

> La **FC massima** va scritta come numero secco (`- **FC massima**: 190`): e'
> l'unico campo che uno script legge da questo file, e serve a trasformare il
> tempo per banda di frequenza — che la pipeline calcola per ogni attivita' — in
> una distribuzione per zona Z1-Z5. Senza, quella distribuzione non compare.
>
> Non usare 220 meno l'eta': sbaglia di 10-12 battiti su un individuo, che basta
> a spostare una seduta di una zona intera. Meglio il valore piu' alto mai visto
> in gara o in una prova massimale, annotando quale.

> HRV, sonno e stress **non sono prodotti dalla pipeline**: Garmin non li
> espone per la via che usiamo. O li scrivi qui a mano, o il coach lavora senza. Il coach e' istruito a dirlo esplicitamente invece di
> inventarseli.

### Affidabilita' del cardio

- **Orologio**: [modello]
- **HR da polso attendibile?**: [si' / no — e perche', con un caso concreto]

> Sezione non decorativa: se l'HR da polso e' gonfiato da *cadence lock*, il
> coach deve governare le sedute a passo e RPE invece che a fascia cardiaca.
> Vedi `athletes/giorgia/profile.md` per un caso reale documentato.

## Obiettivi

### Obiettivo primario

- **Gara**: [nome]
- **Data**: [YYYY-MM-DD]
- **Distanza + D+**: [es. 21 km, 1000 m D+]
- **Target**: [tempo o semplicemente "completare"]

> La **data** e' il campo piu' importante del file: da li' il coach calcola le
> settimane mancanti e quindi la fase (Base / Build / Peak / Taper). Se manca,
> ogni piano settimanale e' campato in aria.

### Obiettivi secondari

| Gara | Data | Distanza | Priorita' |
|------|------|----------|-----------|
| [nome] | [YYYY-MM-DD] | [dist + D+] | [secondaria — non compromettere la primaria] |

## Comportamento reale osservato

> Compilare **dopo** 3-4 settimane di dati veri. E' la sezione che fa la
> differenza fra un piano teorico e uno che l'atleta segue davvero: qui si
> annota dove il comportamento diverge dal piano e si ricalibra il piano, non
> l'atleta.

| Parametro | Da piano | Osservato |
|-----------|----------|-----------|
| Volume settimanale | [x km] | [y km] |
| Giorni REST rispettati | [n/7] | [m/7] |
| Intensita' spontanea | [zona] | [zona] |

### Regole derivate

1. [regola operativa che ogni piano deve rispettare, con il perche']

## Vincoli e preferenze

- **Giorni disponibili**: [n/settimana]
- **Ore massime**: [h/settimana]
- **Infortuni passati / punti fragili**: [elenco]
- **Terreni e strutture disponibili**: [strada, trail, pista, palestra]

---

**Ultimo aggiornamento**: [YYYY-MM-DD]
