"""Check the data and write data/DATA_REPORT.md.

What it checks:
  1. Coverage of every history file (first/last day, missing days, lowest level per decade)
  2. Day-to-day jumps of 50 cm or more (can mean the gauge zero was moved)
  3. Riverbed erosion: level at the same low discharge, decade by decade (APPD gives both H and Q)
  4. Today's level for the same gauge from different sources (APPD daily, APPD automatic,
     APPD 8-day table, Danube FIS portal)
  5. Depth offsets at critical sections: APPD's calculated depth minus the level at the nearest
     APPD gauge, today and for each forecast day. A constant offset confirms "depth = gauge + offset".

Run from the repository root:
    python scripts/data/check.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
JUMP_CM = 50
LOW_Q = (1800, 2200)  # m3/s band used to compare low-water levels across decades
MODEL_SECTIONS = {"Batin": 528, "Belene": 563}  # sections in pegel/config.py, by river km


def table(df: pd.DataFrame) -> str:
    """Small markdown table without extra dependencies."""
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |")
    return "\n".join(lines)


def coverage(out: list[str]) -> None:
    out.append("## 1. History files (data/history)\n")
    rows, lows = [], []
    for f in sorted((DATA / "history").glob("*.csv")):
        s = pd.read_csv(f, parse_dates=["date"]).set_index("date")["level_cm"]
        full = pd.date_range(s.index.min(), s.index.max(), freq="D")
        rows.append({"station": f.stem, "first": s.index.min().date(), "last": s.index.max().date(),
                     "days": len(s), "missing days": len(full.difference(s.index)),
                     "min cm": int(s.min()), "max cm": int(s.max())})
        dec = s.groupby((s.index.year // 10) * 10).min()
        lows.append(dec.rename(f.stem))
    out.append(table(pd.DataFrame(rows)) + "\n")
    out.append("Lowest daily level per decade (cm). A falling trend at similar flows points to riverbed erosion (section 3).\n")
    low = pd.concat(lows, axis=1).astype("Int64")
    low.index = [f"{d}s" for d in low.index]
    out.append(table(low.reset_index().rename(columns={"index": "decade"})) + "\n")


def jumps(out: list[str]) -> None:
    out.append(f"## 2. Day-to-day jumps of {JUMP_CM} cm or more\n")
    rows = []
    for f in sorted((DATA / "history").glob("*.csv")):
        s = pd.read_csv(f, parse_dates=["date"]).set_index("date")["level_cm"]
        d = s.diff()
        big = d[d.abs() >= JUMP_CM]
        rows.append({"station": f.stem, "jumps": len(big),
                     "largest": f"{int(big.abs().max())} cm on {big.abs().idxmax().date()}" if len(big) else ""})
    out.append(table(pd.DataFrame(rows)))
    out.append("\nFloods can rise this fast; a jump that is not mirrored at the neighbouring gauge, or a level shift "
               "without a discharge change, would mean a moved gauge zero.\n")


def erosion(out: list[str]) -> None:
    out.append(f"## 3. Riverbed erosion: median level at {LOW_Q[0]}-{LOW_Q[1]} m3/s, by decade\n")
    daily = pd.read_csv(DATA / "extra" / "appd_daily.csv", parse_dates=["date"])
    band = daily[daily["discharge_m3s"].between(*LOW_Q)]
    pivot = band.assign(decade=(band["date"].dt.year // 10) * 10).pivot_table(
        index="decade", columns="station", values="level_cm", aggfunc="median").round().astype("Int64")
    pivot.index = [f"{d}s" for d in pivot.index]
    out.append(table(pivot.reset_index().rename(columns={"index": "decade"})))
    out.append("\nSame flow, lower reading = the bed has dropped (or the rating curve changed). Old years shifted "
               "\"to today's level\" will then overstate depth. Use recent decades or simulate in discharge.\n")


def sources_today(out: list[str]) -> None:
    out.append("## 4. Same gauge, different sources (latest day)\n")
    rows = []
    t = pd.read_csv(DATA / "live" / "appd_today.csv")
    g = pd.read_csv(DATA / "live" / "gauges_daily.csv")
    p = pd.read_csv(DATA / "live" / "danubeportal.csv")
    day = t["date"].max()
    for st in sorted(t.loc[t["source"] == "appd_daily_reading", "station"]):
        r = {"station": st, "date": day}
        for src in ("appd_daily_reading", "appd_automatic_gauge"):
            v = t[(t.station == st) & (t.source == src) & (t.date == day)]["level_cm"]
            r[src] = int(v.iloc[0]) if len(v) else None
        v = g[(g.station == st) & (g.source == "appd_statistic") & (g.date == day)]["level_cm"]
        r["appd_8day_table"] = int(v.iloc[0]) if len(v) else None
        km = t[t.station == st]["river_km"].iloc[0]
        v = p[(p["river_km"] - km).abs() < 1.5].sort_values("observed_at")["level_cm"]
        r["danubeportal (RO/BG gauge at same km)"] = int(v.iloc[-1]) if len(v) else None
        rows.append(r)
    out.append(table(pd.DataFrame(rows)))
    out.append("\nThe portal value at the same km can be the Romanian gauge on the other bank (different gauge zero).\n")


def reference_gauges(retrieved: str | None = None) -> pd.DataFrame:
    """For every APPD critical section: the gauge APPD computes its depth from, and the offset.

    APPD gives the depth for today and three forecast days. The reference gauge is the APPD forecast
    gauge for which depth - level stays constant over all those days (spread 0 = exact match).
    Returns one row per section with today's depth and that gauge's reading on the same day.
    """
    b = pd.read_csv(DATA / "live" / "appd_bottlenecks.csv")
    retrieved = retrieved or b["retrieved"].max()
    b = b[b["retrieved"] == retrieved]
    t = pd.read_csv(DATA / "live" / "appd_today.csv")
    t = t[(t["source"] == "appd_daily_reading") & (t["date"] == retrieved)]
    f = pd.read_csv(DATA / "live" / "appd_forecasts.csv")
    f = f[f["issued"] == retrieved]
    level_today = dict(zip(t["station"], t["level_cm"]))
    km_of = dict(zip(t["station"], t["river_km"]))
    rows = []
    for (sec, km), grp in b.groupby(["section", "km_from"]):
        mid_km = (km + grp["km_to"].iloc[0]) / 2
        depth = grp[["depth_left_cm", "depth_middle_cm", "depth_right_cm"]].where(lambda d: d > 0).min(axis=1)
        grp = grp.assign(depth=depth).dropna(subset=["depth"])  # negative depths in the source are errors
        best = None
        for st in f["station"].unique():
            offs = []
            for _, r in grp.iterrows():
                if r["kind"] == "calculated_today":
                    level = level_today.get(st)
                else:
                    lv = f[(f["station"] == st) & (f["date"] == r["date"])]["level_forecast_cm"]
                    level = lv.iloc[0] if len(lv) else None
                if level is not None:
                    offs.append(r["depth"] - level)
            if len(offs) >= 2:
                key = (max(offs) - min(offs), abs(km_of.get(st, 0) - mid_km))
                if best is None or key < best[0]:
                    best = (key, st, offs)
        today_depth = grp.loc[grp["kind"] == "calculated_today", "depth"]
        gauge = best[1] if best else None
        rows.append({"section": sec, "km_from": km, "km_to": grp["km_to"].iloc[0] if len(grp) else None,
                     "mid_km": mid_km, "measured_on": grp["measured_on"].iloc[0] if len(grp) else None,
                     "date": retrieved, "depth_today_cm": today_depth.iloc[0] if len(today_depth) else None,
                     "gauge": gauge, "gauge_level_today_cm": level_today.get(gauge),
                     "offset_cm": best[2][0] if best else None, "spread_cm": best[0][0] if best else None})
    return pd.DataFrame(rows).sort_values("km_from")


def offsets(out: list[str]) -> None:
    out.append("## 5. Depth offsets at critical sections (APPD)\n")
    ref = reference_gauges()
    df = pd.DataFrame({
        "section": ref["section"],
        "km": [f"{a:g}-{b:g}" for a, b in zip(ref["km_from"], ref["km_to"])],
        "measured": ref["measured_on"],
        "min depth today cm": ref["depth_today_cm"].round().astype("Int64"),
        "reference gauge (inferred)": ref["gauge"],
        "offset cm": ref["offset_cm"].round().astype("Int64"),
        "spread over days cm": ref["spread_cm"].round().astype("Int64"),
        "model section": [next((n for n, k in MODEL_SECTIONS.items() if abs(k - m) <= 3), "") for m in ref["mid_km"]],
    })
    out.append(table(df))
    out.append("\nOffset = smallest positive left/middle/right depth from APPD minus the level at the reference gauge "
               "(today: today's reading; forecast days: APPD's level forecast). The reference gauge is the APPD "
               "forecast gauge for which the offset stays constant over all days - a spread of 0 means APPD itself "
               "computes depth = gauge + constant at that gauge.\n\n"
               "Compare with pegel/config.py: Batin +274 cm against Ruse, Belene +230 cm against Svishtov (placeholder).\n\n"
               "APPD notes that depths come from the last survey (\"measured\"); the bed may have changed since.\n")


def gap_2026(out: list[str]) -> None:
    out.append("## 6. Known gap\n")
    g = pd.read_csv(DATA / "live" / "gauges_daily.csv")
    first = g[g["station"].isin(["ruse", "svishtov"])]["date"].min()
    out.append(f"Daily levels for Ruse/Svishtov exist up to 2025-12-31 (APPD archive) and again from {first} "
               "(APPD 8-day table, collected by snapshots.py). **1 Jan 2026 to the day before is missing** - "
               "needed for the August 2026 replay. Options: DanubeHIS (registration), ask APPD for the 2026 file, "
               "or the Danube FIS portal history if it becomes available.\n")


SOURCES_TEXT = """
## Data flow

```mermaid
flowchart LR
  A["APPD open data<br/>PDF archive 1936-2025"] -->|appd_history.py| H["data/history/*.csv<br/>data/extra/*.csv"]
  B["APPD website<br/>today, forecasts, critical sections, 8-day table"] -->|snapshots.py| L["data/live/*.csv<br/>data/today.csv"]
  C["Danube FIS portal"] -->|snapshots.py| L
  D["PEGELONLINE"] -->|snapshots.py| L
  H --> M["pegel model / API"]
  L --> M
  H -->|check.py| R["DATA_REPORT.md<br/>SOURCES.md"]
  L -->|check.py| R
  H -->|search_list.py| S["search-list files<br/>depths.csv, prices.csv,<br/>history incl. 2026 days"]
  L -->|search_list.py| S
```

## Sources

### APPD / EAEMDR (Bulgaria)
- **Publisher:** Executive Agency "Exploration and Maintenance of the Danube River" (Изпълнителна агенция „Проучване и поддържане на река Дунав"), Ruse.
- **Archive:** <https://www.appd-bg.org/pages-en?id=opendata> - daily water level (cm), discharge (m3/s) and water temperature (degC) for Novo Selo, Lom, Oryahovo, Svishtov, Ruse, Silistra. Every PDF we used, with its URL and download date: `data/extra/appd_files.csv`.
- **Live pages:** today's readings <https://www.appd-bg.org/hidrology-en>, forecasts <https://www.appd-bg.org/forecasts-en>, critical sections <https://www.appd-bg.org/bottlenecks-en> (each row links its survey PDF), 8-day table <https://www.appd-bg.org/statistic-en>.
- **Terms (open-data page):** name EAEMDR as the source; mark modified data as modified; their name and logo may not be used commercially without written consent.
- **What we changed:** PDF and HTML tables converted to CSV; day-by-year tables turned into one row per date; depths converted from dm to cm. Values themselves are unchanged. Levels are in cm against each gauge's zero (see `appd_stations.csv`); negative values are real.
- **Caveat from APPD:** depths at critical sections are calculated from the last survey; the riverbed and buoys may have changed since the survey date.

### Danube FIS portal
- **Publisher:** the waterway administrations of the Danube states (FIS portal), <https://www.danubeportal.com/waterLevel>.
- **What we take:** the latest level per gauge with its ISRS location code and timestamp.
- **Terms:** none found on the page - ask before publishing the data in a product.
- **Caveat:** gauges belong to different countries and use different gauge zeros; compare levels only at the same gauge.

### PEGELONLINE (Germany)
- **Publisher:** Federal Waterways and Shipping Administration (WSV), <https://www.pegelonline.wsv.de/webservices/rest-api/v2>.
- **What we take:** water level W of all German Danube gauges, last 30 days, averaged to daily means by us.

### Prices and barge facts (`data/prices.csv`)
Every line names its source and date; each value was read on the source page itself. Nothing is estimated or converted (USD stays USD).
- **Pro Danube 2013** (A. Capatu, EUSDR working group, 16-17 Apr 2013): <https://navigation.danube-region.eu/content/uploads/sites/10/2019/09/2013-04-17_EUSDR_PA1A_4th_WG_Flashlight1.pdf> - convoy, payload and cost by draught, freight rates Constanta-Hungary, canal fee basis.
- **USM / UGA / Atria Brokers, 5 Feb 2024**: <https://en.usm.media/barge-freight-rates-to-constanta-have-decreased/> - barge rates Reni/Izmail to Constanta and to Ruse/Silistra.
- **Logos Press, 23 Jul 2026**: <https://logos-pres.md/en/news/freight-rates-on-the-danube-have-risen/> - ~28 USD/t Reni/Izmail-Constanta, ~2 m max draught at Cernavoda, 30-60 % capacity loss (ASAP Agri).
- **UkrAgroConsult, 17 and 24 Aug 2026**: <https://ukragroconsult.com/en/news/freight-rates-from-ukraines-danube-ports-rise-amid-critically-low-water-levels/>, <https://ukragroconsult.com/en/news/low-danube-water-levels-effectively-block-grain-exports-from-part-of-bulgaria/> - coaster rate to Egypt, truck cost Vidin region to Black Sea ports.
- **Not found (left out on purpose):** a normal barge rate Ruse/Lom-Constanta, a rail rate, convoy transit days, the depth at which barges stop, the current canal tariff.

## How to cite on slides or the website

> Water level data: EAEMDR / APPD (Bulgaria), reformatted by Pegel; Danube FIS portal; PEGELONLINE (WSV). Status: see date in the app.
"""


def write_sources() -> None:
    """data/SOURCES.md: one overview table built from the files on disk, plus fixed source notes."""
    rows = []

    def add(dataset, file, period, places, n, source):
        rows.append({"dataset": dataset, "file": f"`{file}`", "period": period, "places": places,
                     "rows": f"{n:,}".replace(",", "."), "source": source})

    hist = sorted((DATA / "history").glob("*.csv"))
    if hist:
        h = [pd.read_csv(f, parse_dates=["date"]) for f in hist]
        add("Daily water level (model input)", "data/history/<station>.csv",
            f"{min(x.date.min() for x in h):%Y-%m-%d} .. {max(x.date.max() for x in h):%Y-%m-%d}",
            f"{len(hist)} gauges: {', '.join(f.stem for f in hist)}", sum(len(x) for x in h), "APPD archive")
    p = DATA / "extra" / "appd_daily.csv"
    if p.exists():
        d = pd.read_csv(p, parse_dates=["date"])
        add("Daily level + discharge + water temperature", "data/extra/appd_daily.csv",
            f"{d.date.min():%Y-%m-%d} .. {d.date.max():%Y-%m-%d}", f"{d.station.nunique()} gauges", len(d), "APPD archive")
    for name, label in [("appd_stations", "Gauge km and gauge zero"), ("appd_files", "List of source PDFs with URL")]:
        p = DATA / "extra" / f"{name}.csv"
        if p.exists():
            d = pd.read_csv(p)
            add(label, f"data/extra/{name}.csv", "-", f"{d['station'].nunique()} gauges", len(d), "APPD archive")
    p = DATA / "today.csv"
    if p.exists():
        d = pd.read_csv(p)
        add("Today's level used by the model", "data/today.csv", d["date"].max(),
            ", ".join(f"{g} {int(v)} cm" for g, v in zip(d.gauge_id, d.level_cm)), len(d), "APPD today")
    live = DATA / "live"
    specs = [("appd_today", "Today's readings (manual + automatic gauges)", "date", "station", "APPD today"),
             ("appd_forecasts", "6-day level forecast with min/max", "date", "station", "APPD forecasts"),
             ("appd_bottlenecks", "Depth at critical sections (today + 3 forecast days)", "date", "km_from", "APPD critical sections"),
             ("danubeportal", "Latest level at gauges in all Danube states", "observed_at", "isrs", "Danube FIS portal")]
    for name, label, datecol, placecol, src in specs:
        p = live / f"{name}.csv"
        if p.exists():
            d = pd.read_csv(p)
            add(label, f"data/live/{name}.csv", f"{str(d[datecol].min())[:10]} .. {str(d[datecol].max())[:10]}",
                f"{d[placecol].nunique()} {'sections' if placecol == 'km_from' else 'gauges'}", len(d), src)
    p = live / "gauges_daily.csv"
    if p.exists():
        d = pd.read_csv(p)
        for src, label, who in [("appd_statistic", "Daily level along the whole Danube (8-day table)", "APPD 8-day table"),
                                ("pegelonline_daily_mean", "Daily mean level, German Danube gauges", "PEGELONLINE")]:
            s = d[d["source"] == src]
            if len(s):
                add(label, "data/live/gauges_daily.csv", f"{s.date.min()} .. {s.date.max()}",
                    f"{s.station.nunique()} gauges", len(s), who)

    p = DATA / "depths.csv"
    if p.exists():
        d = pd.read_csv(p)
        add("Depth at a critical section + same-day gauge reading (search-list format)", "data/depths.csv",
            f"{d.date.min()} .. {d.date.max()}", f"{d.section.nunique()} sections", len(d), "APPD critical sections")
    p = DATA / "prices.csv"
    if p.exists():
        d = pd.read_csv(p)
        add("Prices, barge and convoy facts with source per line (search-list format)", "data/prices.csv",
            f"{d.date.astype(str).min()} .. {d.date.astype(str).max()}", f"{d['item'].nunique()} items", len(d),
            "Pro Danube 2013, USM 2024, Logos Press / UkrAgroConsult 2026")

    head = ["# Data sources and overview\n",
            f"Generated by scripts/data/check.py on {pd.Timestamp.now():%Y-%m-%d %H:%M}. "
            "Numbers below are read from the files, so re-run after every update.\n",
            "## Overview\n", table(pd.DataFrame(rows)) + "\n",
            "The `data/live` files grow with every run of `snapshots.py`; the archive ends on 2025-12-31.\n"]
    (DATA / "SOURCES.md").write_text("\n".join(head) + SOURCES_TEXT, encoding="utf-8")
    print("Wrote data/SOURCES.md")


def main() -> None:
    out = ["# Data report\n", f"Generated by scripts/data/check.py on {pd.Timestamp.now():%Y-%m-%d %H:%M}.\n"]
    for step in (coverage, jumps, erosion, sources_today, offsets, gap_2026):
        try:
            step(out)
        except FileNotFoundError as e:
            out.append(f"_Skipped {step.__name__}: {e.filename} not found - run the fetch scripts first._\n")
    (DATA / "DATA_REPORT.md").write_text("\n".join(out), encoding="utf-8")
    print("Wrote data/DATA_REPORT.md")
    write_sources()


if __name__ == "__main__":
    main()
