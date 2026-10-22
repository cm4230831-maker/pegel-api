"""Loading data. Every history file has the same format:

    data/history/<gauge_id>.csv
    date,level_cm
    1996-01-01,215
    ...

(one row per day, level in cm, negative values allowed)
"""
from pathlib import Path

import pandas as pd
import requests

from pegel import config

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_history(gauge_id: str) -> pd.Series:
    df = pd.read_csv(DATA_DIR / "history" / f"{gauge_id}.csv", parse_dates=["date"])
    s = df.set_index("date")["level_cm"].astype(float).sort_index()
    s = s[s.index.year >= config.HISTORY_START_YEAR]
    return s.asfreq("D").interpolate(limit=5)  # fill short gaps only


def load_all_history() -> dict:
    return {g: load_history(g) for g in config.GAUGES}


def latest_levels(history: dict) -> dict:
    """Today's level per gauge. Uses data/today.csv if present (typed in from the
    APPD bulletin), otherwise the last value in the history file."""
    today_file = DATA_DIR / "today.csv"
    if today_file.exists():
        df = pd.read_csv(today_file)  # columns: gauge_id,level_cm,date
        return {r.gauge_id: float(r.level_cm) for r in df.itertuples()}
    return {g: float(s.dropna().iloc[-1]) for g, s in history.items()}


# --- Live German gauges for the map (PEGELONLINE, free, no login) ----------------
PEGELONLINE = "https://www.pegelonline.wsv.de/webservices/rest-api/v2"


def pegelonline_danube() -> list:
    """Current water level for every German Danube gauge."""
    url = f"{PEGELONLINE}/stations.json"
    params = {"waters": "DONAU", "timeseries": "W", "includeTimeseries": "true",
              "includeCurrentMeasurement": "true"}
    stations = requests.get(url, params=params, timeout=10).json()
    out = []
    for st in stations:
        ts = st["timeseries"][0]
        m = ts.get("currentMeasurement")
        if m and "latitude" in st:
            out.append({"name": st["longName"], "lat": st["latitude"], "lon": st["longitude"],
                        "level_cm": m["value"], "time": m["timestamp"]})
    return out
