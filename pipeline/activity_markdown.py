#!/usr/bin/env python3
"""Resa in Markdown del riassunto di un'attivita'.

E' il prodotto che il coach legge. Riceve strutture gia' calcolate e non fa
conti propri: se un numero e' sbagliato, il posto dove guardare e'
`activity_metrics.py`.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path


# Helper functions
def format_seconds(sec):
    if sec is None:
        return None
    try:
        sec = int(round(sec))
    except Exception:
        return None
    td = timedelta(seconds=sec)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:d}:{seconds:02d}"

def pace_str(s_per_km):
    """Format seconds-per-km as M:SS/km string. Return None if input is None."""
    if s_per_km is None:
        return None
    try:
        s = int(round(s_per_km))
    except Exception:
        return None
    mins = s // 60
    secs = s % 60
    return f"{mins:d}:{secs:02d}/km"

def _metadati(summary):
    """Intestazione e metadati: tipo, data, distanza, calorie."""
    lines = []
    lines.append("# Activity Summary")
    lines.append("")

    # metadata block
    lines.append("**Metadata:**")
    meta_items = []
    if summary.get('activity_name'):
        meta_items.append(f"**Name:** {summary.get('activity_name')}")
    if summary.get('activity_type'):
        meta_items.append(f"**Type:** {summary.get('activity_type')}")
    if summary.get('start_time'):
        meta_items.append(f"**Date:** {summary.get('start_time')}")
    if summary.get('distance_m') is not None:
        dist_km = (summary.get('distance_m') or 0.0) / 1000.0
        meta_items.append(f"**Distance:** {dist_km:.2f} km")
    if summary.get('calories') is not None:
        meta_items.append(f"**Calories:** {summary.get('calories')}")
    if meta_items:
        lines.extend([f"- {m}" for m in meta_items])
        lines.append("")

    # descriptive summary with named fields
    return lines


def _riassunto(summary):
    """Il blocco **Summary**: totali, cardio, dislivello, e le metriche derivate
    (bande di frequenza, passo corretto per la pendenza, decoupling)."""
    lines = []
    lines.append("**Summary:**")
    sum_lines = []
    def add_k(label, key, fmt=None):
        v = summary.get(key)
        if v is None:
            return
        if fmt == 'time':
            sum_lines.append(f"- **{label}:** {format_seconds(v)}")
        elif fmt == 'meters':
            sum_lines.append(f"- **{label}:** {v} m")
        elif fmt == 'distance_km':
            sum_lines.append(f"- **{label}:** {v/1000.0:.2f} km")
        elif fmt == 'bpm':
            sum_lines.append(f"- **{label}:** {v:.1f} bpm")
        else:
            sum_lines.append(f"- **{label}:** {v}")

    add_k('Total distance', 'distance_m', 'distance_km')
    add_k('Moving time', 'moving_time_s', 'time')
    add_k('Elapsed time', 'elapsed_time_s', 'time')
    add_k('Duration', 'duration_s', 'time')
    add_k('Calories', 'calories')
    add_k('Avg HR', 'avg_hr', 'bpm')
    add_k('Max HR', 'max_hr', 'bpm')
    add_k('Min HR', 'min_hr', 'bpm')
    # Il dislivello e' etichettato con la sua provenienza: letto dal
    # dispositivo, oppure ricalcolato dai campioni di quota quando il file
    # non lo dichiara. Il coach deve sapere quale dei due sta leggendo prima
    # di costruirci sopra un ragionamento sul carico in salita.
    asc = summary.get('total_ascent_m')
    if asc is not None:
        if summary.get('total_ascent_m_source') == 'device':
            sum_lines.append(f"- **Total ascent:** {asc} m")
        else:
            sum_lines.append(
                f"- **Total ascent:** ~{asc} m (stimato dai campioni di quota, "
                f"non dichiarato dal dispositivo)")
    desc = summary.get('total_descent_m')
    if desc is not None:
        sum_lines.append(f"- **Total descent:** {desc} m")
    if summary.get('training_effect_aerobic') is not None:
        try:
            sum_lines.append(f"- **Training Effect (aerobic):** {float(summary.get('training_effect_aerobic')):.1f}")
        except Exception:
            pass
    if summary.get('training_effect_anaerobic') is not None:
        try:
            sum_lines.append(f"- **Training Effect (anaerobic):** {float(summary.get('training_effect_anaerobic')):.1f}")
        except Exception:
            pass

    # Campi presenti nel FIT e finora non riportati nel riassunto.
    # La potenza di corsa e' insensibile alla pendenza: su trail dice quello
    # che il passo non puo' dire. Il sub_sport distingue trail e tapis
    # (dove il passo GPS non vale) senza doverlo dedurre dal dislivello.
    if summary.get('sub_sport'):
        sum_lines.append(f"- **Terrain:** {summary['sub_sport']}")
    if summary.get('avg_power_w') is not None:
        sum_lines.append(f"- **Avg power:** {summary['avg_power_w']} W")
    if summary.get('normalized_power_w') is not None:
        sum_lines.append(f"- **Normalized power:** {summary['normalized_power_w']} W")
    if summary.get('max_power_w') is not None:
        sum_lines.append(f"- **Max power:** {summary['max_power_w']} W")
    # La cadenza FIT e' per gamba: i passi al minuto sono il doppio.
    # Riportata in spm perche' e' l'unita' che si legge sull'orologio, e
    # perche' serve al confronto con la FC (cadence lock del sensore ottico).
    for etichetta, chiave in (("Avg cadence", "avg_cadence"), ("Max cadence", "max_cadence")):
        v = summary.get(chiave)
        if v is not None:
            spm = v * 2 if v < 120 else v
            sum_lines.append(f"- **{etichetta}:** {spm:.0f} spm")
    if summary.get('min_altitude_m') is not None and summary.get('max_altitude_m') is not None:
        sum_lines.append(
            f"- **Altitude range:** {summary['min_altitude_m']:.0f}–"
            f"{summary['max_altitude_m']:.0f} m")
    gap = summary.get('grade_adjusted_pace_s_km')
    dist_km = (summary.get('distance_m') or 0) / 1000.0
    mov = summary.get('moving_time_s')
    if gap and dist_km > 0.5 and mov:
        reale = mov / dist_km
        # Su terreno piatto i due valori coincidono e la riga non aggiunge
        # niente: si mostra solo quando la pendenza ha spostato qualcosa.
        if abs(gap - reale) >= 10:
            sum_lines.append(
                f"- **Passo corretto per la pendenza:** {pace_str(gap)} "
                f"(reale {pace_str(reale)}) — equivalente in piano")

    bande = summary.get('hr_bands_s') or {}
    if bande:
        # Una riga sola: il coach ci mappa sopra le zone conoscendo la FC
        # massima dell'atleta, che qui non e' nota.
        pezzi = [f"{k} {v // 60}:{v % 60:02d}" for k, v in bande.items() if v >= 30]
        if pezzi:
            sum_lines.append("- **Tempo per banda FC (bpm):** " + " · ".join(pezzi))

    if summary.get('decoupling_pct') is not None:
        d = summary['decoupling_pct']
        verdict = "tenuta buona" if d < 5 else ("deriva marcata" if d > 10 else "deriva moderata")
        sum_lines.append(
            f"- **Decoupling (1a vs 2a metà):** {d:+.1f}% — {verdict}")

    if sum_lines:
        lines.extend(sum_lines)
        lines.append("")
    return lines


def _tabella_split(splits_km):
    """Tabella degli split al chilometro."""
    lines = []
    # splits table (per-km) - only relevant fields
    if splits_km:
        lines.append("**Per-km splits:**")
        hdr = "|km|duration|avg HR|min HR|max HR|elev gain (m)|elev loss (m)|"
        sep = "|--:|--:|--:|--:|--:|--:|--:|"
        lines.append(hdr)
        lines.append(sep)
        for idx, sp in enumerate(splits_km, start=1):
            dur = format_seconds(sp.get('duration_s')) if sp.get('duration_s') is not None else ""
            avg_hr = f"{sp.get('avg_hr'):.1f}" if sp.get('avg_hr') is not None else ""
            hr_min = f"{sp.get('hr_min'):.0f}" if sp.get('hr_min') is not None else ""
            hr_max = f"{sp.get('hr_max'):.0f}" if sp.get('hr_max') is not None else ""
            elev = f"{sp.get('elevation_gain_m'):.1f}" if sp.get('elevation_gain_m') is not None else ""
            elev_loss = f"{sp.get('elevation_loss_m'):.1f}" if sp.get('elevation_loss_m') is not None else ""
            lines.append(f"|{idx}|{dur}|{avg_hr}|{hr_min}|{hr_max}|{elev}|{elev_loss}|")
        lines.append("")
    return lines


def _campo_lap(lap, *chiavi):
    """Primo dei campi presenti nel lap, o None.

    Con `or` a catena uno zero legittimo (un lap da 0 secondi) verrebbe
    scartato in favore del campo successivo.
    """
    for k in chiavi:
        v = lap.get(k)
        if v is not None:
            return v
    return None


def _tabella_lap(laps):
    """Tabella dei lap registrati dall'orologio."""
    lines = []
    # laps table - concise
    if laps:
        lines.append("**Recorded laps (concise):**")
        hdr = "|start|distance (m)|elapsed|moving time|avg pace|avg HR|max HR|elev gain (m)|elev loss (m)|"
        sep = "|--|--:|--:|--:|--:|--:|--:|--:|--:|"
        lines.append(hdr)
        lines.append(sep)
        for lap in laps:
            start = lap.get('start_time') or lap.get('timestamp') or ''
            dist = ''
            if lap.get('total_distance') is not None:
                try:
                    dist = f"{float(lap.get('total_distance')):.1f}"
                except Exception:
                    dist = str(lap.get('total_distance'))
            elif lap.get('distance') is not None:
                try:
                    dist = f"{float(lap.get('distance')):.1f}"
                except Exception:
                    dist = str(lap.get('distance'))
            # `elapsed` e `moving` vengono entrambi dal .fit, con la stessa
            # convenzione del riassunto (`fit_reader._summary_field`):
            # total_elapsed_time e' il tempo a orologio, total_timer_time quello
            # col cronometro in moto. Quando differiscono l'atleta si e' fermato,
            # e questa e' l'unica riga della tabella che lo dice.
            #
            # Prima: `elapsed` mostrava total_timer_time, quindi le soste non si
            # vedevano, e `moving` veniva ricalcolato dalla timeseries con una
            # finestra sbagliata — `lap_start` veniva sovrascritto col campo
            # `timestamp`, che nel .fit e' la **fine** del lap, e la finestra
            # finiva sul lap successivo. Risultato: il moving time di ogni lap
            # era la durata di quello dopo, e l'ultimo stampava "None".
            # Il .fit non contiene un moving time per lap (total_moving_time e'
            # assente su tutti), quindi non c'era niente da ricalcolare.
            elapsed_s = _campo_lap(lap, 'total_elapsed_time', 'elapsed_time')
            moving_s = _campo_lap(lap, 'total_moving_time', 'moving_time',
                                  'total_timer_time')
            elapsed = format_seconds(elapsed_s) or ''
            moving = format_seconds(moving_s) or ''
            avg_hr = ''
            if lap.get('avg_heart_rate') is not None:
                avg_hr = f"{lap.get('avg_heart_rate'):.1f}"
            elif lap.get('avg_heart_rate_bpm') is not None:
                avg_hr = f"{lap.get('avg_heart_rate_bpm'):.1f}"
            max_hr = f"{lap.get('max_heart_rate'):.1f}" if lap.get('max_heart_rate') is not None else ''
            # avg pace from timer time / distance
            pace = ''
            try:
                timer_t = moving_s if moving_s is not None else elapsed_s
                lap_d = lap.get('total_distance') or lap.get('distance')
                if timer_t is not None and lap_d is not None and float(lap_d) > 0:
                    pace = format_seconds(round(float(timer_t) * 1000.0 / float(lap_d))) or ''
            except Exception:
                pace = ''
            elev_gain_lap = f"{float(lap.get('total_ascent')):.0f}" if lap.get('total_ascent') is not None else ''
            elev_loss_lap = f"{float(lap.get('total_descent')):.0f}" if lap.get('total_descent') is not None else ''
            lines.append(f"|{start}|{dist}|{elapsed}|{moving}|{pace}|{avg_hr}|{max_hr}|{elev_gain_lap}|{elev_loss_lap}|")
        lines.append("")
    return lines


def write_markdown(md_path, summary, splits_km, laps):
    """Scrive il riassunto Markdown dell'attivita' nel percorso indicato.

    Quattro sezioni indipendenti, ciascuna che restituisce le proprie righe.
    Prima erano un unico blocco da 250 righe in cui una sola lista veniva
    riempita da capo a fondo: per cambiare la tabella dei lap bisognava
    leggere tutto il resto.
    """
    md_path = Path(md_path)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    lines = (_metadati(summary)
             + _riassunto(summary)
             + _tabella_split(splits_km)
             + _tabella_lap(laps))
    md_path.write_text("\n".join(lines), encoding="utf-8")
