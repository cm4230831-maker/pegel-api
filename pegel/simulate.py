"""Step 4: replay past years over the delivery window, starting from today's levels.

For each past year y and each possible sailing day:
  1. take every gauge's level path in year y for the same calendar days,
  2. add today's departure from year y (today_level - level_y(today)), fading with time,
  3. the convoy passes each shallow spot on its own day (by river km),
  4. the shallowest spot it meets sets the draught -> EUR/t.
All (year, sailing day) results together give the distribution.
"""
from datetime import date, timedelta

import numpy as np
import pandas as pd

from pegel import config, data, model


def _same_day(year: int, d: date):
    try:
        return pd.Timestamp(year=year, month=d.month, day=d.day)
    except ValueError:  # 29 Feb
        return None


def run(route_id: str, today: date, today_levels: dict, window_start: date, window_end: date,
        normal_rate: float, history_end: date | None = None) -> pd.DataFrame:
    route = data.routes().loc[route_id]
    secs = data.route_sections(route_id)
    gauges = list(secs.gauge.unique())
    hist = {g: data.history(g) for g in gauges}
    if history_end is not None:  # replay: never use data after the replay date
        hist = {g: s[s.index <= pd.Timestamp(history_end)] for g, s in hist.items()}

    span = route.from_km - route.to_km
    pass_day = {r.section: int(round((route.from_km - r.river_km) / span * (route.transit_days - 1)))
                for r in secs.itertuples()}
    years = sorted(set.intersection(*[set(s.index.year) for s in hist.values()]))
    years = [y for y in years if y < today.year]
    sail_days = [window_start + timedelta(days=i) for i in range((window_end - window_start).days + 1)]

    rows = []
    for y in years:
        t0 = _same_day(y, today)
        if t0 is None:
            continue
        anomaly = {}
        for g in gauges:
            v = hist[g].get(t0, np.nan)
            if np.isnan(v):
                break
            anomaly[g] = today_levels[g] - v
        else:
            for d in sail_days:
                worst = None
                for s in secs.itertuples():
                    day = d + timedelta(days=pass_day[s.section])
                    ty = _same_day(y + (day.year - today.year), day)
                    if ty is None:
                        ty = _same_day(y + (day.year - today.year), day - timedelta(days=1))
                    level = hist[s.gauge].get(ty, np.nan)
                    if np.isnan(level):
                        worst = None
                        break
                    fade = np.exp(-(day - today).days / config.ANOMALY_FADE_DAYS)
                    depth = model.section_depth_cm(level + anomaly[s.gauge] * fade, s.offset_cm)
                    if worst is None or depth < worst[0]:
                        worst = (depth, s.section, s.status)
                if worst is None:
                    continue
                dr = model.draught_m(worst[0])
                b = model.cost_breakdown(dr, normal_rate)
                rows.append({"year": y, "sail_date": d, "draught_m": dr, "bottleneck": worst[1],
                             "bottleneck_status": worst[2],
                             "cost": None if b is None else b["total"],
                             "scarcity": None if b is None else b["scarcity"]})
    return pd.DataFrame(rows)


def _pct(x, q):
    return round(float(np.percentile(x, q)), 2)


def summarise(runs: pd.DataFrame, quantity_t: float, normal_rate: float) -> dict:
    ok = runs.dropna(subset=["cost"])
    no_service = 1 - len(ok) / len(runs)
    fan = []
    for d, grp in runs.groupby("sail_date"):
        c = grp["cost"].dropna()
        fan.append({"date": d.isoformat(),
                    "p10": _pct(c, 10) if len(c) else None, "p50": _pct(c, 50) if len(c) else None,
                    "p90": _pct(c, 90) if len(c) else None, "p95": _pct(c, 95) if len(c) else None,
                    "no_service_probability": round(1 - len(c) / len(grp), 3)})
    dr = runs["draught_m"]
    p50 = _pct(ok["cost"], 50) if len(ok) else None
    p90 = _pct(ok["cost"], 90) if len(ok) else None
    counts = runs["bottleneck"].value_counts(normalize=True)
    return {
        "summary": {
            "p50_eur_t": p50, "p10_eur_t": _pct(ok["cost"], 10) if len(ok) else None,
            "p90_eur_t": p90, "p95_eur_t": _pct(ok["cost"], 95) if len(ok) else None,
            "risk_premium_eur_t": round(p90 - p50, 2) if p50 is not None else None,
            "scarcity_part_of_p50_eur_t": round(float(ok["scarcity"].median()), 2) if len(ok) else None,
            "no_service_probability": round(no_service, 3),
            "bad_case_is_no_service": bool(no_service > config.NO_SERVICE_WARN),
            "normal_rate_eur_t": normal_rate,
        },
        "fan_chart": fan,
        "bottleneck": {
            "most_common_section": counts.index[0],
            "most_common_share": round(float(counts.iloc[0]), 2),
            "top_sections": [{"section": k, "share": round(float(v), 2)} for k, v in counts.head(3).items()],
            "draught_p50_m": round(max(float(dr.median()), 0), 2),
            "draught_p10_m": round(max(float(np.percentile(dr, 10)), 0), 2),
        },
        "barges": {
            "good_water": model.barges_needed(quantity_t, config.NORMAL_DRAUGHT_M),
            "median": model.barges_needed(quantity_t, float(dr.median())),
            "bad_case": model.barges_needed(quantity_t, float(np.percentile(dr, 10))),
            "note": "null = barges cannot sail at that water level",
        },
    }
