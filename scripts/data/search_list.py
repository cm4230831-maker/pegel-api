"""Write the files the team's "Data Search List" asks for, in exactly its formats.

  data/history/<gauge>.csv  date,level_cm - APPD archive plus every day collected since (2026 so far:
                            only the days snapshots.py has seen). Also partial files for Nikopol and
                            the Romanian gauges Corabia, Zimnicea, Giurgiu, Oltenita, Cernavoda.
  data/depths.csv           date,section,depth_cm,gauge,level_cm,source - one row per critical section
                            and snapshot day, from APPD's depth table and the gauge APPD uses for it
  data/prices.csv           item,value,unit,date,route,source - only values we opened at the source

Run after appd_history.py and snapshots.py, from the repository root:
    python scripts/data/search_list.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from check import reference_gauges  # same folder

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

# Gauges named in the search list (Bulgarian with archive, then partial ones)
GAUGES = ["svishtov", "ruse", "silistra", "nikopol", "oryahovo", "lom", "novo_selo",
          "corabia", "zimnicea", "giurgiu", "oltenita", "cernavoda"]

# Search-list name for an APPD section, matched by APPD's upstream km (APPD uses Bulgarian names)
SPOT_NAMES = {565.0: "Belene", 545.0: "Vardin", 538.0: "Gâsca", 530.0: "Batin"}

PRO_DANUBE = ("Pro Danube 2013, A. Capatu, EUSDR WG 16-17.04.2013, https://navigation.danube-region.eu/content/"
              "uploads/sites/10/2019/09/2013-04-17_EUSDR_PA1A_4th_WG_Flashlight1.pdf")
USM_2024 = ("USM (Ukrainian Shipping Magazine) 05.02.2024 citing UGA / Atria Brokers, 6,000 t lots, "
            "https://en.usm.media/barge-freight-rates-to-constanta-have-decreased/")
LOGOS_2026 = ("Logos Press 23.07.2026 (rate: market participants; Atria Brokers calls it extremely tentative), "
              "https://logos-pres.md/en/news/freight-rates-on-the-danube-have-risen/")
UAC_2026 = "UkrAgroConsult 17.08.2026 citing Atria Brokers, https://ukragroconsult.com/en/news/freight-rates-from-ukraines-danube-ports-rise-amid-critically-low-water-levels/"
UAC_ROAD = "UkrAgroConsult 24.08.2026 (from Bg-24), https://ukragroconsult.com/en/news/low-danube-water-levels-effectively-block-grain-exports-from-part-of-bulgaria/"

# Only values we read on the source page ourselves. Nothing estimated, nothing converted.
PRICES = [
    ("barge_rate_corn_reference", 15, "EUR/t", "2024-02-05", "Reni/Izmail-Constanta", USM_2024),
    ("barge_rate_sunflower_reference", 21, "EUR/t", "2024-02-05", "Reni/Izmail-Ruse/Silistra", USM_2024),
    ("barge_rate_upstream_reference", 13, "EUR/t", "2013", "Constanta-Hungary", PRO_DANUBE),
    ("barge_rate_downstream_reference", 17, "EUR/t", "2013", "Hungary-Constanta", PRO_DANUBE),
    ("barge_rate_low_water", 28, "USD/t", "2026-07-23", "Reni/Izmail-Constanta", LOGOS_2026),
    ("coaster_rate_low_water_low", 65, "USD/t", "2026-08-17", "Ukrainian Danube ports-Egypt (sea, corn, 6000 t)", UAC_2026),
    ("coaster_rate_low_water_high", 68, "USD/t", "2026-08-17", "Ukrainian Danube ports-Egypt (sea, corn, 6000 t)", UAC_2026),
    ("road_rate_low", 40, "EUR/t", "2026-08-24", "Vidin region-Black Sea ports (truck)", UAC_ROAD),
    ("road_rate_high", 50, "EUR/t", "2026-08-24", "Vidin region-Black Sea ports (truck)", UAC_ROAD),
    ("max_draught_cernavoda", 2.0, "m", "2026-07-23", "Cernavoda (market participants, 'about')", LOGOS_2026),
    ("capacity_loss_low", 30, "%", "2026-07-23", "Danube barges, depending on design (ASAP Agri estimate)", LOGOS_2026),
    ("capacity_loss_high", 60, "%", "2026-07-23", "Danube barges, depending on design (ASAP Agri estimate)", LOGOS_2026),
    ("convoy_barges", 6, "barges", "2013", "pusher + 6 Europa II, Constanta-Hungary-Constanta", PRO_DANUBE),
    ("barge_payload_at_2.0m", 1000, "t", "2013", "Europa II barge", PRO_DANUBE),
    ("barge_payload_at_2.3m", 1250, "t", "2013", "Europa II barge", PRO_DANUBE),
    ("barge_payload_at_2.5m", 1500, "t", "2013", "Europa II barge", PRO_DANUBE),
    ("barge_payload_at_2.7m", 1750, "t", "2013", "Europa II barge", PRO_DANUBE),
    ("convoy_cost_per_t_at_2.0m", 23.48, "EUR/t", "2013", "Constanta-Hungary-Constanta, round trip", PRO_DANUBE),
    ("convoy_cost_per_t_at_2.3m", 19.45, "EUR/t", "2013", "Constanta-Hungary-Constanta, round trip", PRO_DANUBE),
    ("convoy_cost_per_t_at_2.5m", 16.77, "EUR/t", "2013", "Constanta-Hungary-Constanta, round trip", PRO_DANUBE),
    ("convoy_cost_per_t_at_2.7m", 14.85, "EUR/t", "2013", "Constanta-Hungary-Constanta, round trip", PRO_DANUBE),
    ("convoy_fixed_cost_round_trip", 49500, "EUR", "2013", "salaries, maintenance, depreciation", PRO_DANUBE),
    ("diesel_price_assumed", 850, "EUR/t", "2013", "Pro Danube cost model", PRO_DANUBE),
    ("canal_fee_basis", "per tonne of barge capacity, not cargo", "-", "2013",
     "Danube-Black Sea Canal (ACN)", PRO_DANUBE),
]


def history() -> list[str]:
    """Archive plus collected days, one file per gauge."""
    parts = []
    daily = DATA / "extra" / "appd_daily.csv"
    if daily.exists():
        parts.append(pd.read_csv(daily, usecols=["station", "date", "level_cm"]).assign(prio=0))
    live = DATA / "live" / "gauges_daily.csv"
    if live.exists():
        g = pd.read_csv(live)
        parts.append(g[g["source"] == "appd_statistic"][["station", "date", "level_cm"]].assign(prio=1))
    today = DATA / "live" / "appd_today.csv"
    if today.exists():
        t = pd.read_csv(today)
        parts.append(t[t["source"] == "appd_daily_reading"][["station", "date", "level_cm"]].assign(prio=2))
    allrows = pd.concat(parts).dropna(subset=["level_cm"])
    allrows = allrows.sort_values("prio").drop_duplicates(["station", "date"], keep="first")  # archive wins
    lines = []
    for g in GAUGES:
        s = allrows[allrows["station"] == g].sort_values("date")
        if s.empty:
            lines.append(f"  {g:10s} no data")
            continue
        s[["date", "level_cm"]].astype({"level_cm": int}).to_csv(DATA / "history" / f"{g}.csv", index=False)
        n2026 = (s["date"] >= "2026-01-01").sum()
        lines.append(f"  {g:10s} {s.date.min()} .. {s.date.max()}  {len(s):6d} days, of which 2026: {n2026}")
    return lines


def depths() -> int:
    b = pd.read_csv(DATA / "live" / "appd_bottlenecks.csv")
    rows = []
    for day in sorted(b["retrieved"].unique()):
        for _, r in reference_gauges(day).iterrows():
            if pd.isna(r["depth_today_cm"]) or pd.isna(r["gauge_level_today_cm"]):
                continue
            name = SPOT_NAMES.get(r["km_from"], f"{r['section']} km {r['km_from']:g}-{r['km_to']:g}")
            rows.append({"date": day, "section": name, "depth_cm": int(round(r["depth_today_cm"])),
                         "gauge": r["gauge"], "level_cm": int(r["gauge_level_today_cm"]),
                         "source": f"APPD bottlenecks-en, '{r['section']}' km {r['km_from']:g}-{r['km_to']:g}, "
                                   f"calculated from survey {r['measured_on']}; smallest of left/middle/right; "
                                   f"gauge = the one APPD's depths follow (spread {r['spread_cm']:g} cm)"})
    pd.DataFrame(rows).to_csv(DATA / "depths.csv", index=False)
    return len(rows)


def prices() -> int:
    pd.DataFrame(PRICES, columns=["item", "value", "unit", "date", "route", "source"]).to_csv(
        DATA / "prices.csv", index=False)
    return len(PRICES)


def main() -> None:
    print("history:")
    print("\n".join(history()))
    print(f"depths.csv: {depths()} rows")
    print(f"prices.csv: {prices()} rows")


if __name__ == "__main__":
    main()
