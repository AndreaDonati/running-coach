# Gli atleti

Una cartella per persona. Il nome che le dai — minuscolo, senza spazi — diventa
il modo in cui la chiami ovunque: `/start-week marco`, `/sync-run marco`.

Più persone possono convivere nella stessa installazione, ognuna coi suoi
obiettivi e i suoi piani, senza mescolarsi.

## Aggiungerne una

```bash
cp -R athletes/_template athletes/<nome>
```

Poi lascia fare a `/onboard`: ti intervista, importa le attività, compila il
profilo e scrive la prima settimana. Se preferisci a mano, i passi sono nel
README principale.

## Cosa trovi dentro

```
athletes/<nome>/
├── profile.md        chi sei, che gara vuoi fare, quanto tempo hai
├── raw/activities/   i file .fit così come escono dall'orologio
├── training_data/    i riassunti che legge l'allenatore
└── plans/            le tue settimane
```

**`profile.md` è l'unico file che scrivi tu.** Ci stanno gli obiettivi, i
vincoli reali (quanti giorni hai davvero, non quanti vorresti), gli infortuni da
tenere d'occhio, e un paio di cose sull'orologio che cambiano il modo in cui
l'allenatore ti prescrive le sedute.

Il campo che pesa più di tutti è la **data della gara**: da lì l'allenatore
calcola quante settimane mancano e in che fase sei. Senza, qualsiasi piano è
campato in aria — e infatti un controllo si rifiuta di procedere.

**`training_data/` è generato.** Un riassunto per ogni corsa, i raggruppamenti
per trimestre, un quadro settimana per settimana. Non si modifica a mano: se un
numero è sbagliato, si corregge lo script e si rigenera, altrimenti la correzione
sparisce al primo aggiornamento.

**`plans/` è il lavoro dell'allenatore.** Una settimana per file in `weeks/`, il
piano della gara in `race/`, e `season.md` con una riga per ogni settimana
chiusa — che è il posto dove guardare per farsi un'idea di come sta andando la
preparazione senza aprire dodici file.

## Verificare che sia tutto a posto

```bash
pipeline/.venv/bin/python pipeline/profile_check.py <nome>
```

Dice se manca qualcosa di importante nel profilo: la data della gara, i giorni
disponibili, l'affidabilità della frequenza cardiaca. Non giudica il contenuto,
verifica che ci sia.

## I tuoi dati non finiscono in git

Tutto quello che sta qui dentro, tranne questo file e `_template/`, è escluso
dal controllo di versione. Non solo i file dell'orologio: anche i riassunti, il
profilo, le settimane. Quei file dicono quanto corri, a che frequenza cardiaca,
quanto pesi, dove abiti e che gare hai in programma.

Chi clona il repository trova solo il modello e ci mette i propri.

<details>
<summary>Se vuoi comunque tenere una storia dei tuoi dati</summary>

**Un repository privato separato** è la strada più sicura. Sposti la tua
cartella altrove e la rimetti al suo posto con un collegamento:

```bash
mv athletes/marco ~/running-coach-data/marco
ln -s ~/running-coach-data/marco athletes/marco
```

Il collegamento è ignorato come il resto, e `~/running-coach-data` può essere un
repository privato per conto suo. Gli script funzionano identici.

**Un ramo locale che non pubblichi** funziona, ma basta un `git push --all`
distratto per vanificarlo.

**Togliere l'esclusione** e fidarsi che il repository resti privato è la strada
che sconsiglio: i repository cambiano visibilità, i fork no.

</details>
