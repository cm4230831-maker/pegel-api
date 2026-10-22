"""Step 4: replay past years over the delivery window, starting from today's level."""
from datetime import date, timedelta

import numpy as np
import pandas as pd

from pegel import config, model


def _same_day(year: int, d: date):
    try:
        return pd.Timestamp(year=year, month=d.month, day=d.day)
    except ValueError:  # 29 Feb in a non-leap year
        return None


def simulate(history: dict, today_levels: dict, today: date,
             window_start: date, window_end: date, normal_rate: float) -> dict:
    years = sorted(set.intersection(*[set(s.index.year) for s in history.values()]))
    years = [y for y in years if y < today.year]  # never use the year we are forecasting
    sail_days = [window_start + timedelta(days=i)
                 for i in range((window_end - window_start).days + 1)]

    rows = []  # one row per (past year, sailing day)
    for y in years:
        t0 = _same_day(y, today)
        if t0 is None:
            continue
        # shift each gauge so the past year starts at today's level
        shift = {}
        for g, s in history.items():
            v = s.get(t0, np.nan)
            if np.isnan(v):
                break
            shift[g] = today_levels[g] - v
        else:
            for d in sail_days:
                ty = _same_day(y + (d.year - today.year), d)
                if ty is None:
                    continue
                transit = pd.date_range(ty, periods=config.TRANSIT_DAYS, freq="D")
                worst_draught, worst_section = 99.0, None
                for t in transit:
                    lv = {g: history[g].get(t, np.nan) + shift[g] for g in history}
                    if any(np.isnan(v) for v in lv.values()):
                        break
                    dr, sec = model.max_draught_m(lv)
                    if dr < worst_draught:
                        worst_draught, worst_section = dr, sec
                else:
                    cost = model.cost_per_t(worst_draught, normal_rate)
                    rows.append({"year": y, "sail_date": d, "draught_m": worst_draught,
                                 "bottleneck": worst_section, "cost": cost})
    return {"runs": pd.DataFrame(rows), "years_used": len({r["year"] for r in rows})}


def summarise(runs: pd.DataFrame, quantity_t: float) -> dict:
    """Turn the simulated runs into the numbers the website shows."""
    ok = runs.dropna(subset=["cost"])
    no_service_share = 1 - len(ok) / len(runs) if len(runs) else 0.0

    def pct(x, q):
        return round(float(np.percentile(x, q)), 2)

    fan = []
    for d, grp in runs.groupby("sail_date"):
        c = grp["cost"].dropna()
        if len(c):
            fan.append({"date": d.isoformat(), "p10": pct(c, 10), "p50": pct(c, 50),
                        "p90": pct(c, 90), "p95": pct(c, 95)})

    dr = runs["draught_m"]
    return {
        "summary": {
            "p50_eur_t": pct(ok["cost"], 50), "p10_eur_t": pct(ok["cost"], 10),
            "p90_eur_t": pct(ok["cost"], 90), "p95_eur_t": pct(ok["cost"], 95),
            "no_service_probability": round(no_service_share, 3),
        },
        "fan_chart": fan,
        "bottleneck": {
            "most_common_section": runs["bottleneck"].mode().iat[0],
            "draught_p50_m": round(float(dr.median()), 2),
            "draught_p10_m": round(float(np.percentile(dr, 10)), 2),
        },
        "barges": {
            "good_water": model.barges_needed(quantity_t, config.NORMAL_DRAUGHT_M),
            "median": model.barges_needed(quantity_t, float(dr.median())),
            "bad_case": model.barges_needed(quantity_t, float(np.percentile(dr, 10))),
        },
    }
