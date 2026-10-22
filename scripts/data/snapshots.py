"""Collect today's readings, forecasts and fairway depths from several public sources.

Run it once a day (or more often). Every run appends to data/live/*.csv and drops duplicates,
so the files grow into our own history for 2026 onwards - the APPD archive stops at 2025.

Sources (all public, no login):
  APPD (Bulgaria)   https://www.appd-bg.org        today's levels, 6-day forecasts with min/max,
                                                  depths at critical sections, last 8 days at ~66 gauges
  Danube FIS portal https://www.danubeportal.com   current level at ~107 gauges, all riparian states
  PEGELONLINE (DE)  https://www.pegelonline.wsv.de German Danube gauges, last 30 days, daily means

Outputs:
  data/today.csv                    gauge_id,level_cm,date   (what pegel/data.py uses as "today")
  data/live/appd_today.csv          station,river_km,date,level_cm,discharge_m3s,change_24h_cm,water_temp_c,source
  data/live/appd_forecasts.csv      issued,station,date,level_min_cm,level_forecast_cm,level_max_cm
  data/live/appd_bottlenecks.csv    retrieved,section,km_from,km_to,measured_on,kind,date,depth_left_cm,...
  data/live/gauges_daily.csv        source,country,station,river_km,date,level_cm
  data/live/danubeportal.csv        retrieved,isrs,station,fairway,river_km,observed_at,level_cm

Run from the repository root:
    python scripts/data/snapshots.py
    python scripts/data/snapshots.py --skip pegelonline
"""
from __future__ import annotations

import argparse
import html
import json
import re
import urllib.request
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "data" / "live"
USER_AGENT = "Pegel-Hackathon/0.1 (research prototype)"
APPD = "https://www.appd-bg.org/"
PEGELONLINE = "https://www.pegelonline.wsv.de/webservices/rest-api/v2"

# APPD shows some names in Bulgarian or with typos; map them to our station ids
APPD_IDS = {"novo selo": "novo_selo", "vidin": "vidin", "lom": "lom", "oryahovo": "oryahovo",
            "nikopol": "nikopol", "svishtov": "svishtov", "ruse": "ruse", "silistra": "silistra",
            "силистра": "silistra", "gomotartsi": "gomotartsi", "kozloduj": "kozloduy",
            "bajkal": "baykal", "ryahovo": "ryahovo", "malak preslavets": "malak_preslavets"}
TODAY_GAUGES = ("ruse", "svishtov")  # gauges the model needs; data/today.csv lists all manual gauges


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")


def tables(page: str) -> list[list[list[str]]]:
    """All HTML tables as lists of rows of cell texts."""
    out = []
    for tbl in re.findall(r"<table.*?</table>", page, re.S):
        rows = []
        for tr in re.findall(r"<tr.*?</tr>", tbl, re.S):
            cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            rows.append(cells)
        out.append(rows)
    return out


def num(text: str | None) -> float | None:
    if text is None:
        return None
    m = re.search(r"[-+]?\d+(?:[.,]\d+)?", text.replace("−", "-"))
    return float(m.group().replace(",", ".")) if m else None


def station_id(name: str) -> str:
    key = name.strip().lower()
    return APPD_IDS.get(key, re.sub(r"\W+", "_", key).strip("_"))


def day_month(text: str, today: date) -> date:
    """'15.10' -> date in the current year, or last year for dates after today (around New Year)."""
    d, m = (int(x) for x in text.split(".")[:2])
    guess = date(today.year, m, d)
    return guess if guess <= today.replace(day=min(today.day + 7, 28)) or m <= today.month else date(today.year - 1, m, d)


def append(name: str, rows: list[dict], keys: list[str]) -> int:
    """Append rows to data/live/<name>.csv, keep the newest row per key."""
    if not rows:
        return 0
    LIVE.mkdir(parents=True, exist_ok=True)
    path = LIVE / f"{name}.csv"
    new = pd.DataFrame(rows)
    df = pd.concat([pd.read_csv(path), new]) if path.exists() else new
    df = df.astype({k: str for k in keys}).drop_duplicates(subset=keys, keep="last").sort_values(keys)
    df.to_csv(path, index=False)
    return len(new)


# --- APPD -------------------------------------------------------------------------------------

def appd_today(today: date) -> dict:
    page = fetch(APPD + "hidrology-en")
    rows = []
    for tbl in tables(page)[:2]:
        manual = "discharge" in " ".join(tbl[0]).lower()
        for r in tbl[1:]:
            if len(r) < 3 or num(r[2]) is None:
                continue
            rows.append({"station": station_id(r[0]), "river_km": num(r[1]), "date": today.isoformat(),
                         "level_cm": num(r[2]),
                         "discharge_m3s": num(r[3]) if manual and len(r) > 3 else None,
                         "change_24h_cm": num(r[4]) if manual and len(r) > 4 else None,
                         "water_temp_c": num(r[5] if manual else r[4]) if len(r) > (5 if manual else 4) else None,
                         "source": "appd_daily_reading" if manual else "appd_automatic_gauge"})
    n = append("appd_today", rows, ["station", "date", "source"])
    # data/today.csv in the format the model reads: the duty officer's daily reading at every manual gauge.
    # Only written when the gauges the model needs are there, so a broken page never empties the file.
    official = [r for r in rows if r["source"] == "appd_daily_reading"]
    if all(g in {r["station"] for r in official} for g in TODAY_GAUGES):
        pd.DataFrame([{"gauge_id": r["station"], "level_cm": int(r["level_cm"]), "date": r["date"]}
                      for r in official]).to_csv(ROOT / "data" / "today.csv", index=False)
    return {"appd_today": n, "today.csv": len(official)}


def appd_forecasts(today: date) -> dict:
    page = fetch(APPD + "forecasts-en")
    names = re.findall(r"<h3[^>]*>\s*([^<]+?)\s*</h3>", page)
    rows = []
    for name, tbl in zip(names, tables(page)):
        head = {r[0].lower(): r[1:] for r in tbl if r}
        for i, dm in enumerate(head.get("day", [])):
            rows.append({"issued": today.isoformat(), "station": station_id(name),
                         "date": day_month(dm, today).isoformat(),
                         "level_min_cm": num(head["min"][i]), "level_forecast_cm": num(head["forecast"][i]),
                         "level_max_cm": num(head["max"][i])})
    return {"appd_forecasts": append("appd_forecasts", rows, ["issued", "station", "date"])}


def appd_bottlenecks(today: date) -> dict:
    page = fetch(APPD + "bottlenecks-en")
    forecast_days = [datetime.strptime(d, "%d.%m.%Y").date().isoformat()
                     for d in re.findall(r"Forecast for\s*(\d{2}\.\d{2}\.\d{4})", page)]
    table = re.findall(r"<table.*?</table>", page, re.S)[0]
    rows = []
    for raw, r in zip(re.findall(r"<tr.*?</tr>", table, re.S), tables(table)[0]):
        km = re.search(r"km\.?\s*([\d.]+)\s*-\s*([\d.]+)", r[0]) if r else None
        if not km or len(r) < 7:
            continue
        scheme = re.search(r'href="(documents/fairways/[^"]+\.pdf)"', raw)
        base = {"retrieved": today.isoformat(), "section": r[0].split(",")[0].strip(),
                "km_from": float(km.group(1)), "km_to": float(km.group(2)),
                "measured_on": datetime.strptime(r[1], "%d.%m.%Y").date().isoformat(),
                "width_m": num(r[6]),
                "scheme_pdf": APPD + scheme.group(1) if scheme else None}

        def depths(cells):  # APPD gives decimetres
            return {f"depth_{side}_cm": (num(c) * 10 if num(c) is not None else None)
                    for side, c in zip(("left", "middle", "right"), cells)}
        rows.append({**base, "kind": "calculated_today", "date": today.isoformat(), **depths(r[3:6])})
        for i, day in enumerate(forecast_days):
            cells = r[7 + 3 * i: 10 + 3 * i]
            if len(cells) == 3:
                rows.append({**base, "kind": "forecast", "date": day, **depths(cells)})
    return {"appd_bottlenecks": append("appd_bottlenecks", rows, ["retrieved", "km_from", "kind", "date"])}


def appd_statistic(today: date) -> dict:
    """Last 8 days at ~66 gauges along the whole Danube and tributaries."""
    tbl = tables(fetch(APPD + "statistic-en"))[0]
    days = [day_month(d, today) for d in tbl[0][3:] if re.fullmatch(r"\d{2}\.\d{2}", d)]
    rows = []
    for r in tbl[1:]:
        for d, cell in zip(days, r[3:]):
            level = num(cell.split()[0]) if cell.strip() else None
            if level is not None:
                rows.append({"source": "appd_statistic", "country": r[0], "station": station_id(r[2]),
                             "river_km": num(r[1]), "date": d.isoformat(), "level_cm": level})
    return {"gauges_daily(appd)": append("gauges_daily", rows, ["source", "station", "date"])}


# --- Danube FIS portal ---------------------------------------------------------------------------

def danubeportal(today: date) -> dict:
    page = fetch("https://www.danubeportal.com/waterLevel")
    rows = []
    for isrs, tr in re.findall(r'<tr class="clickable-row" id="([^"]+)">(.*?)</tr>', page, re.S):
        c = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()
             for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(c) >= 5 and num(c[4]) is not None:
            rows.append({"retrieved": today.isoformat(), "isrs": isrs, "station": c[0], "fairway": c[1],
                         "river_km": num(c[2]), "observed_at": c[3], "level_cm": num(c[4])})
    return {"danubeportal": append("danubeportal", rows, ["isrs", "observed_at"])}


# --- PEGELONLINE (Germany) -------------------------------------------------------------------------

def pegelonline(today: date) -> dict:
    stations = json.loads(fetch(f"{PEGELONLINE}/stations.json?waters=DONAU&timeseries=W"))
    rows = []
    for st in stations:
        try:
            meas = json.loads(fetch(f"{PEGELONLINE}/stations/{st['uuid']}/W/measurements.json?start=P30D"))
        except Exception as e:  # one broken station must not stop the run
            print(f"  PEGELONLINE {st.get('longname')}: {e}")
            continue
        if not meas:
            continue
        s = pd.DataFrame(meas)
        s["date"] = pd.to_datetime(s["timestamp"], utc=True).dt.tz_convert("Europe/Berlin").dt.date
        for d, v in s.groupby("date")["value"].mean().items():
            rows.append({"source": "pegelonline_daily_mean", "country": "Germany",
                         "station": station_id(st["longname"]), "river_km": st.get("km"),
                         "date": d.isoformat(), "level_cm": round(float(v), 1)})
    return {"gauges_daily(pegelonline)": append("gauges_daily", rows, ["source", "station", "date"])}


SOURCES = {"appd_today": appd_today, "appd_forecasts": appd_forecasts, "appd_bottlenecks": appd_bottlenecks,
           "appd_statistic": appd_statistic, "danubeportal": danubeportal, "pegelonline": pegelonline}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skip", nargs="*", default=[], choices=list(SOURCES), help="sources to leave out")
    args = ap.parse_args()
    today = date.today()
    for name, fn in SOURCES.items():
        if name in args.skip:
            continue
        try:
            print(f"{name:16s}", fn(today))
        except Exception as e:  # keep going: one site down must not lose the others
            print(f"{name:16s} FAILED: {e}")


if __name__ == "__main__":
    main()
