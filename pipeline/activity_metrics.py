#!/usr/bin/env python3
"""Calcoli derivati da una traccia: dislivello, pendenza, zone, split.

Funzioni pure sui dati gia' letti da `fit_reader.py`: nessuna apre un file,
nessuna scrive. E' cio' che le rende verificabili con tracce sintetiche, ed e'
il motivo per cui stanno separate — i bug di questo progetto sono quasi tutti
stati calcoli sbagliati che nessuno vedeva.
"""
from __future__ import annotations

import math
from statistics import mean

from fit_reader import safe_val  # noqa: F401  (usato da compute_splits)


# Ampiezza massima di una variazione di quota fra due campioni consecutivi.
# Sopra, e' un artefatto del sensore (perdita di fix GPS, sbalzo barometrico in
# galleria o in ascensore), non un gradino vero: a 1 Hz nessuno sale 30 m in un
# secondo.
SPIKE_CAP_M = 30.0

def compute_ascent_from_altitude(timeseries):
    """Ricalcola dislivello positivo e negativo dai campioni di quota.

    Serve in due casi diversi:

    - **totale dell'attivita'**: e' un ripiego. Il valore buono e' quello che il
      dispositivo scrive nel file (`total_ascent`), calcolato col barometro; il
      ricalcolo se ne discosta del 4.6-6.0% mediano e si usa solo quando il file
      non lo dichiara (su questo archivio: solo attivita' indoor).
    - **split al chilometro**: qui non c'e' alternativa, il file non contiene un
      dislivello per chilometro. Si usa sempre, anche outdoor. Validato contro i
      lap del dispositivo su 177 chilometri con auto-lap da 1 km: errore mediano
      2.7% (2.4 m), novantesimo percentile 15.5%.

    Metodo: filtro mediano a 3 campioni per togliere i picchi isolati, poi somma
    delle differenze consecutive scartando quelle oltre `SPIKE_CAP_M`.

    Storia, perche' non venga reintrodotta: qui c'erano tre metodi in parallelo
    ('raw', 'smoothed', 'garmin_like') e un'euristica che ne sceglieva uno.
    Misurati contro il valore del dispositivo su 80 attivita', 'smoothed'
    sbagliava del 97% mediano e 'raw' del 77%; solo questo stava al 6-8%.
    'smoothed' applicava una soglia di 0.5 m alle differenze di una serie gia'
    mediata su 9 campioni, dove ogni passo vale 0.1-0.3 m: le azzerava quasi
    tutte, restituendo ~0 quasi sempre. Non erano stime alternative fra cui
    scegliere: erano due numeri sbagliati che facevano sembrare il problema
    irrisolto.
    """
    alts = [r.get('altitude_m') for r in timeseries]
    n = len(alts)
    if n == 0:
        return (0.0, 0.0)

    first_idx = next((i for i, a in enumerate(alts) if a is not None), None)
    if first_idx is None:
        return (0.0, 0.0)

    # riempimento dei buchi: all'indietro col primo valore valido, in avanti con
    # l'ultimo visto. Un buco lasciato a None diventerebbe un salto fittizio.
    for i in range(first_idx):
        alts[i] = float(alts[first_idx])
    last = float(alts[first_idx])
    for i in range(first_idx, n):
        if alts[i] is None:
            alts[i] = last
        else:
            last = float(alts[i])

    # filtro mediano a 3: toglie il campione isolato fuori scala senza spostare
    # i gradini veri
    med = []
    for i in range(n):
        finestra = sorted(alts[max(0, i - 1): min(n, i + 2)])
        med.append(finestra[len(finestra) // 2])

    ascesa = discesa = 0.0
    for i in range(1, len(med)):
        d = med[i] - med[i - 1]
        if abs(d) > SPIKE_CAP_M:
            continue
        if d > 0:
            ascesa += d
        else:
            discesa += -d

    return (round(ascesa, 2), round(discesa, 2))

# Bande di frequenza cardiaca, in battiti al minuto. Fisse e indipendenti
# dall'atleta: si calcolano una volta sola in conversione, e chi conosce la FC
# massima le mappa sulle zone senza dover riconvertire niente.
# --- passo corretto per la pendenza ----------------------------------------
#
# Curva di Minetti et al. 2002 ("Energy cost of walking and running at extreme
# uphill and downhill slopes", J Appl Physiol 93:1039-1046): costo energetico
# della corsa in J/kg/m in funzione della pendenza, come frazione. Pubblicata e
# misurata su tapis inclinabile, quindi non e' l'ennesima euristica tarata a
# occhio su questo archivio.
#
# Validata comunque sul controllo ovvio: su una corsa piatta il passo corretto
# deve coincidere col passo reale. Su sei corse con meno di 5 m di dislivello
# per km lo scarto assoluto mediano e' 1.6 s/km.
MINETTI = (155.4, -30.4, -43.3, 46.3, 19.5, 3.6)

PENDENZA_MAX = 0.45   # oltre, la curva e' fuori dal suo intervallo di validita'

def costo_energetico(pendenza: float) -> float:
    """J/kg/m per correre a una data pendenza."""
    i = max(-PENDENZA_MAX, min(PENDENZA_MAX, pendenza))
    a, b, c, d, e, f = MINETTI
    return a * i ** 5 + b * i ** 4 + c * i ** 3 + d * i ** 2 + e * i + f

COSTO_PIANO = costo_energetico(0.0)

# Lunghezza minima di un segmento su cui misurare la pendenza. Sotto, il rumore
# di quota domina: mezzo metro di errore su cinque metri di percorso e' un 10%
# di pendenza inventato.
SEGMENTO_MIN_M = 25.0

def segmenti_corretti(timeseries):
    """Spezza la traccia in segmenti e ne restituisce la versione corretta.

    Ogni segmento e' `(secondi, metri reali, metri equivalenti in piano,
    FC media)`. I metri equivalenti sono quelli che, corsi in piano, costerebbero
    la stessa energia: e' questo che rende confrontabile una salita con una
    strada pianeggiante.
    """
    pts = [(t.get("ts"), t.get("distance_m"), t.get("altitude_m"), t.get("heart_rate"))
           for t in (timeseries or [])]
    pts = [p for p in pts if p[0] is not None and p[1] is not None and p[2] is not None]
    if len(pts) < 30:
        return []

    pts.sort(key=lambda x: x[0])
    quote = [p[2] for p in pts]
    n = len(quote)
    # filtro mediano a 3, come per il dislivello: toglie il campione isolato
    med = [sorted(quote[max(0, i - 1): min(n, i + 2)])[
        len(quote[max(0, i - 1): min(n, i + 2)]) // 2] for i in range(n)]

    out = []
    i = 0
    while i < len(pts) - 1:
        j = i + 1
        while j < len(pts) - 1 and pts[j][1] - pts[i][1] < SEGMENTO_MIN_M:
            j += 1
        metri = pts[j][1] - pts[i][1]
        if metri <= 0:
            i = j
            continue

        # Tempo **in movimento**, con la stessa regola con cui il converter
        # calcola `moving_time_s`: si contano solo gli intervalli in cui la
        # distanza avanza. Prendendo l'elapsed del segmento, una sosta dentro al
        # segmento finiva nel passo corretto e lo faceva sembrare piu' lento del
        # passo reale anche su terreno piatto — 13 s/km su una corsa con due
        # minuti di fermo.
        secondi = 0.0
        for k in range(i, j):
            dt = (pts[k + 1][0] - pts[k][0]).total_seconds()
            if 0 < dt <= 60 and pts[k + 1][1] - pts[k][1] > 0.5:
                secondi += dt
        if secondi <= 0:
            i = j
            continue

        pendenza = (med[j] - med[i]) / metri
        hr = [p[3] for p in pts[i:j + 1] if p[3]]
        out.append((secondi, metri,
                    metri * costo_energetico(pendenza) / COSTO_PIANO,
                    sum(hr) / len(hr) if hr else None))
        i = j
    return out

def compute_grade_adjusted_pace(segmenti):
    """Passo equivalente in piano, in secondi al chilometro.

    Su un percorso con dislivello e' piu' veloce del passo reale: dice a che
    ritmo si sarebbe corso in pianura con lo stesso costo energetico. E' cio'
    che rende confrontabile un lungo in montagna con una seduta su strada.
    """
    if not segmenti:
        return None
    tempo = sum(s[0] for s in segmenti)
    equiv = sum(s[2] for s in segmenti)
    if equiv <= 0 or tempo <= 0:
        return None
    return round(tempo / (equiv / 1000.0), 1)

HR_BANDE = [(0, 110), (110, 120), (120, 130), (130, 140), (140, 150),
            (150, 160), (160, 170), (170, 180), (180, 999)]

# Oltre questo intervallo fra due campioni non si sta misurando: e' una pausa,
# una perdita di segnale, o il registratore "smart" che ha saltato. Attribuire
# quel tempo alla banda del campione precedente gonfierebbe i totali.
MAX_DELTA_S = 15.0

def compute_hr_bands(timeseries):
    """Secondi passati in ciascuna banda di frequenza cardiaca.

    Pesati sul **tempo**, non sul numero di campioni: il campionamento non e'
    uniforme. Un Instinct 2 registra a 1 Hz, un Venu 2 in modalita' smart salta
    a intervalli di 1-8 secondi, e contare i campioni darebbe a quest'ultimo un
    peso per battito otto volte piu' basso sugli stessi minuti.

    Restituisce None quando la frequenza cardiaca non c'e' o copre troppo poco.
    """
    campioni = [(t.get("ts"), t.get("heart_rate")) for t in (timeseries or [])]
    campioni = [(ts, hr) for ts, hr in campioni if ts is not None and hr]
    if len(campioni) < 30:
        return None
    campioni.sort(key=lambda x: x[0])

    secondi = [0.0] * len(HR_BANDE)
    totale = 0.0
    for (t0, hr0), (t1, _) in zip(campioni, campioni[1:]):
        dt = (t1 - t0).total_seconds()
        if dt <= 0 or dt > MAX_DELTA_S:
            continue
        for i, (basso, alto) in enumerate(HR_BANDE):
            if basso <= hr0 < alto:
                secondi[i] += dt
                totale += dt
                break

    if totale < 300:  # meno di cinque minuti utili: il dato non dice niente
        return None
    return {f"{b}-{a}" if a < 999 else f"{b}+": round(sec)
            for (b, a), sec in zip(HR_BANDE, secondi)}

# Dislivello massimo, in metri per chilometro, entro cui il decoupling e'
# interpretabile. Vedi la nota nella funzione: sopra, il numero misura il
# terreno e non l'atleta.
DECOUPLING_DPLUS_MAX_M_KM = 10.0

def compute_decoupling(segmenti, sub_sport=None, ascent_m=None, distance_m=None):
    """Scostamento fra intensita' e costo cardiaco tra prima e seconda meta'.

    Rapporto velocita'/FC nella prima meta' contro la seconda, in percentuale.
    Sopra il 5% la stessa andatura e' costata piu' battiti nella seconda meta':
    la seduta e' andata oltre il ritmo sostenibile, o il rifornimento non ha
    retto. E' l'indicatore di durabilita' aerobica.

    **Si calcola solo su terreno sostanzialmente piatto**, e il perche' e' una
    misura, non una cautela generica. Usando la velocita' corretta per la
    pendenza (Minetti), su 29 corse dell'archivio il decoupling mediano viene:

        piatto     (<10 m D+/km)   +3.9%
        collinare  (10-35 m/km)   +14.2%
        montagna   (>35 m/km)     +21.8%

    Un indicatore che cresce in modo monotono col dislivello sta misurando il
    terreno, non l'atleta. La correzione di Minetti e' **metabolica**: non tiene
    conto del fatto che sopra una certa pendenza si cammina invece di correre,
    ne' del costo muscolare eccentrico della discesa, che non si vede nella
    frequenza cardiaca. Il passo corretto resta valido — su corse piatte
    coincide col passo reale entro 1.6 s/km — ma non basta a rendere
    confrontabili le due meta' di un percorso di montagna.

    Restituirlo lo stesso significherebbe consegnare al coach un numero
    plausibile e sbagliato proprio sui lunghi in montagna, dove servirebbe di
    piu'. Meglio non produrlo.

    Escluso anche il tapis roulant: li' la velocita' registrata non e' quella
    vera. Restituisce None quando non e' calcolabile: e' un'assenza voluta.
    """
    if sub_sport == "treadmill":
        return None
    if ascent_m is not None and distance_m and distance_m > 0:
        if ascent_m / (distance_m / 1000.0) > DECOUPLING_DPLUS_MAX_M_KM:
            return None

    utili = [(sec, equiv, hr) for sec, _, equiv, hr in (segmenti or [])
             if hr and hr > 60 and equiv > 0]
    if not utili:
        return None
    tempo_totale = sum(s[0] for s in utili)
    if tempo_totale < 1200:  # meno di venti minuti: il rumore supera il segnale
        return None

    # Divisione a meta' del **tempo**, non del numero di segmenti: in salita un
    # segmento da 25 m dura molto piu' che in discesa.
    meta = tempo_totale / 2
    accumulato = 0.0
    prima, dopo = [], []
    for s in utili:
        (prima if accumulato < meta else dopo).append(s)
        accumulato += s[0]
    if not prima or not dopo:
        return None

    def rapporto(blocco):
        t = sum(x[0] for x in blocco)
        d = sum(x[1] for x in blocco)
        hr = sum(x[2] * x[0] for x in blocco) / t
        return (d / t) / hr if t > 0 and hr > 0 else None

    r1, r2 = rapporto(prima), rapporto(dopo)
    if not r1 or not r2:
        return None
    return round((r1 - r2) / r1 * 100.0, 1)

def compute_splits(timeseries, split_m=1000):
    if not timeseries:
        return []
    splits = []
    n = len(timeseries)
    # if no distance data, can't compute fixed-distance splits
    if all(r.get("distance_m") is None for r in timeseries):
        return []

    # starting target: first full split after the initial distance
    first_dist = timeseries[0].get("distance_m") or 0
    next_target = (math.floor(first_dist / split_m) + 1) * split_m
    current_start_idx = 0
    i = 0
    while i < n:
        di = timeseries[i].get("distance_m")
        if di is None:
            i += 1
            continue
        if di >= next_target:
            start_dist = next_target - split_m
            start_idx = current_start_idx
            while start_idx < i and (timeseries[start_idx].get("distance_m") is None or timeseries[start_idx].get("distance_m") < start_dist):
                start_idx += 1

            start_ts = timeseries[start_idx]["ts"]
            end_ts = timeseries[i]["ts"]
            duration_s = (end_ts - start_ts).total_seconds() if start_ts and end_ts else None
            samples = timeseries[start_idx:i+1]
            hr_vals = [s["heart_rate"] for s in samples if s.get("heart_rate") is not None]
            cad_vals = [s["cadence"] for s in samples if s.get("cadence") is not None]
            alt_vals = [s["altitude_m"] for s in samples if s.get("altitude_m") is not None]
            avg_hr = mean(hr_vals) if hr_vals else None
            hr_min = min(hr_vals) if hr_vals else None
            hr_max = max(hr_vals) if hr_vals else None
            avg_cad = mean(cad_vals) if cad_vals else None
            # compute elevation gain/loss for the split using the chosen method
            elev_gain = None
            elev_loss = None
            if len(alt_vals) >= 2:
                # Il dispositivo dichiara solo il totale dell'attivita',
                # non il dislivello di ogni chilometro: qui si ricalcola
                # sempre dai campioni. Piu' sotto i valori vengono
                # riscalati perche' la loro somma torni col totale.
                try:
                    elev_gain, elev_loss = compute_ascent_from_altitude(samples)
                except Exception:
                    elev_gain = max(alt_vals) - min(alt_vals)
                    elev_loss = 0.0
            # pace in seconds per km for this split (normalize by actual split distance)
            actual_split_distance = split_m
            s_per_km = None
            if duration_s is not None and actual_split_distance and actual_split_distance > 0:
                s_per_km = duration_s * 1000.0 / actual_split_distance
            splits.append({
                "split_distance_m": split_m,
                "split_end_distance_m": di,
                "duration_s": duration_s,
                "s_per_km": s_per_km,
                "start_timestamp": safe_val(start_ts),
                "end_timestamp": safe_val(end_ts),
                "avg_hr": avg_hr,
                "hr_min": hr_min,
                "hr_max": hr_max,
                "avg_cadence": avg_cad,
                "elevation_gain_m": elev_gain,
                "elevation_loss_m": elev_loss,
            })
            next_target += split_m
            current_start_idx = i + 1
        i += 1
    return splits

def scale_splits(splits, target_total, current_sum, key):
    if current_sum <= 0 or target_total is None:
        return 1.0
    # if relative difference > 5%, scale splits to match target_total
    if abs(target_total - current_sum) / max(1.0, current_sum) > 0.05:
        factor = target_total / current_sum
        for sp in splits:
            if sp.get(key) is not None:
                sp[key] = round((sp.get(key) or 0.0) * factor, 2)
        return factor
    return 1.0
