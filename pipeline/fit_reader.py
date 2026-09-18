#!/usr/bin/env python3
"""Lettura di un file .fit: da messaggi Garmin a strutture Python.

Solo estrazione. Niente calcoli derivati (quelli stanno in
`activity_metrics.py`) e niente formattazione (`activity_markdown.py`).
"""
from __future__ import annotations

import gzip
import os
import tempfile
import zipfile
from datetime import datetime


def safe_val(v):
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8", "ignore")
        except Exception:
            return list(v)
    return v

def _sport_name(v):
    """Nome dello sport, o `sconosciuto_<codice>` se fitparse non lo conosce."""
    if v is None:
        return None
    if isinstance(v, int) or str(v).isdigit():
        return f"sconosciuto_{v}"
    return v

def _summary_field(key, value):
    """Mappa un campo FIT sulla chiave usata nel summary, o None se va ignorato."""
    k = key.lower()
    if k in ("total_distance", "distance", "distance_1", "total_distance_1"):
        return "distance_m", value
    if k in ("total_timer_time", "total_moving_time", "moving_time", "moving_time_s"):
        return "moving_time_s", value
    if k in ("total_elapsed_time", "elapsed_time", "timer_time"):
        return "elapsed_time_s", value
    if k == "start_time":
        return "start_time", safe_val(value)
    if k in ("sport", "activity_type"):
        return "activity_type", _sport_name(safe_val(value))
    if k == "sub_sport":
        v = safe_val(value)
        # Garmin usa codici che la tabella di fitparse non sempre conosce: senza
        # questo filtro il riassunto riportava "Terrain: 70", che il coach legge
        # come un terreno. Un codice nudo non e' un'informazione utilizzabile.
        if v is None or v == "generic" or isinstance(v, int) or str(v).isdigit():
            return None
        return "sub_sport", v
    if k in ("name", "activity_name"):
        return "activity_name", safe_val(value)
    if k in ("avg_heart_rate", "avg_heart_rate_bpm"):
        return "avg_hr", value
    if k in ("max_heart_rate", "max_heart_rate_bpm"):
        return "max_hr", value
    if k in ("min_heart_rate", "min_heart_rate_bpm"):
        return "min_hr", value
    if k in ("avg_cadence", "avg_running_cadence"):
        return "avg_cadence", value
    if k in ("max_cadence", "max_running_cadence"):
        return "max_cadence", value
    if k in ("total_ascent", "total_ascent_1", "total_ascent_positive"):
        return "fit_total_ascent_m", value
    if k in ("total_descent", "total_descent_1", "total_descent_negative"):
        return "fit_total_descent_m", value
    if k in ("calories", "total_calories"):
        return "calories", value
    if k == "total_training_effect":
        return "training_effect_aerobic", value
    if k == "total_anaerobic_training_effect":
        return "training_effect_anaerobic", value
    if k == "avg_power":
        return "avg_power_w", value
    if k == "normalized_power":
        return "normalized_power_w", value
    if k == "max_power":
        return "max_power_w", value
    if k == "enhanced_max_altitude":
        return "max_altitude_m", value
    if k == "enhanced_min_altitude":
        return "min_altitude_m", value
    return None

# Priorita' di provenienza dei valori di riepilogo. Un file FIT contiene i
# totali della sessione E quelli di ogni singolo lap, con gli stessi nomi di
# campo. La versione precedente scorreva tutti i messaggi in ordine di file
# mescolandoli: per alcuni campi vinceva il primo incontrato (di norma il lap 1),
# per altri l'ultimo. Su una corsa trail di 16 lap questo dava 272 W come
# potenza media invece di 199, e un dislivello di attivita' pari a quello
# dell'ultimo lap. Ora i messaggi 'session' hanno sempre la precedenza e gli
# altri servono solo a colmare i buchi.
_SOURCE_PRIORITY = ("session", "activity", "file_id", "lap", "record")

def extract_summary(fitfile):
    """Estrae i campi di riepilogo da un file FIT.

    I valori vengono presi dal messaggio 'session' quando c'e'; gli altri tipi
    di messaggio riempiono solo i campi che la sessione non fornisce.
    """
    by_source = {name: {} for name in _SOURCE_PRIORITY}
    for msg in fitfile.get_messages():
        bucket = by_source.get(msg.name.lower())
        if bucket is None:
            continue
        for field in msg:
            if field.value is None:
                continue
            mapped = _summary_field(field.name, field.value)
            if mapped:
                bucket.setdefault(*mapped)

    summary = {}
    for name in _SOURCE_PRIORITY:
        for k, v in by_source[name].items():
            summary.setdefault(k, v)
    return summary

def extract_timeseries(fitfile):
    ts = []
    for msg in fitfile.get_messages():
        if msg.name.lower() != "record":
            continue
        rec = {"ts": None, "timestamp": None, "distance_m": None, "speed_m_s": None,
               "heart_rate": None, "cadence": None, "altitude_m": None, "lat": None, "lon": None}
        for field in msg:
            k = field.name.lower()
            v = field.value
            if k == "timestamp":
                rec["ts"] = v
                rec["timestamp"] = safe_val(v)
            elif k in ("distance", "distance_1", "total_distance"):
                rec["distance_m"] = v
            elif k in ("speed", "enhanced_speed"):
                # I Garmin recenti scrivono solo `enhanced_speed`: con la
                # sola chiave `speed` la velocita' campione per campione
                # restava None su ogni attivita'.
                if rec["speed_m_s"] is None:
                    rec["speed_m_s"] = v
            elif k in ("heart_rate", "heart_rate_bpm"):
                rec["heart_rate"] = v
            elif k in ("cadence", "cadence_running"):
                rec["cadence"] = v
            elif k in ("altitude", "altitude_1", "enhanced_altitude"):
                rec["altitude_m"] = v
            elif k == "position_lat":
                rec["lat"] = v
            elif k == "position_long":
                rec["lon"] = v
        ts.append(rec)
    ts = [r for r in ts if r.get("ts") is not None]
    ts.sort(key=lambda x: x["ts"])
    return ts

def extract_laps(fitfile):
    laps = []
    for msg in fitfile.get_messages():
        if msg.name.lower() != "lap":
            continue
        lap = {}
        for field in msg:
            lap[field.name.lower()] = safe_val(field.value)
        laps.append(lap)
    return laps

def extract_hr_settings(fitfile):
    """Cosa l'orologio pensa del cuore di chi lo porta, al momento dell'attivita'.

    Garmin scrive in ogni `.fit` una copia delle proprie impostazioni: la FC a
    riposo che ha misurato, la FC massima e la soglia con cui calcola le zone,
    e il metodo (percentuale della massima, della riserva, o della soglia).

    Vale la pena leggerlo per due motivi. La FC a riposo e' un dato che
    altrimenti andrebbe chiesto a mano, e l'orologio la misura tutte le notti.
    La FC massima, invece, sull'Instinct e' **auto-rilevata**: cambia da sola
    quando il dispositivo vede uno sforzo piu' duro, e con lei si spostano le
    zone dell'orologio senza che nessuno abbia toccato niente. Se il piano e
    l'orologio danno numeri diversi, spesso e' questo.

    Tutti i campi possono mancare, ed essere `0` significa "non impostato".
    """
    out = {"resting_hr": None, "fcmax_dispositivo": None,
           "soglia_dispositivo": None, "metodo_zone": None}
    for msg in fitfile.get_messages():
        nome = msg.name.lower()
        if nome == "user_profile":
            v = msg.get_value("resting_heart_rate")
            if v:
                out["resting_hr"] = v
        elif nome == "zones_target":
            for chiave, campo in (("fcmax_dispositivo", "max_heart_rate"),
                                  ("soglia_dispositivo", "threshold_heart_rate")):
                v = msg.get_value(campo)
                if v:
                    out[chiave] = v
            v = msg.get_value("hr_calc_type")
            if v:
                out["metodo_zone"] = safe_val(v)
    return out


def prepare_input_path(path):
    """If `path` is a ZIP or GZIP container, extract the first .fit file
    and return the path to a temporary extracted file along with a cleanup flag.
    Otherwise return the original path and False.
    """
    # ZIP archive
    try:
        if zipfile.is_zipfile(path):
            z = zipfile.ZipFile(path, "r")
            # find first entry ending with .fit (case-insensitive)
            for name in z.namelist():
                if name.lower().endswith(".fit"):
                    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".fit")
                    tf.write(z.read(name))
                    tf.close()
                    z.close()
                    return tf.name, True
            z.close()
    except Exception:
        pass

    # GZIP single-file
    try:
        with open(path, "rb") as f:
            sig = f.read(2)
            if sig == b"\x1f\x8b":
                # gzip
                f.seek(0)
                with gzip.open(f, "rb") as gz:
                    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".fit")
                    tf.write(gz.read())
                    tf.close()
                    return tf.name, True
    except Exception:
        pass

    return path, False
