"""Pegel API - the door the Lovable website talks to.
Run locally:  uvicorn main:app --reload   then open http://127.0.0.1:8000/docs
"""
from datetime import date

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pegel import config, data, model, simulate

app = FastAPI(title="Pegel API", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

data.check_all()  # refuse to start on broken data


class QuoteRequest(BaseModel):
    route: str = "lom-constanta"
    cargo: str = "wheat"
    quantity_t: float = 3000
    window_start: date
    window_end: date
    normal_rate_eur_t: float | None = None   # empty -> the route's default rate
    rail_rate_eur_t: float | None = None     # empty -> the route's default rail/truck rate
    today: date | None = None                # replay mode, e.g. "2022-06-15"


def _sections_today(route_id: str, levels: dict) -> list:
    out = []
    for s in data.route_sections(route_id).itertuples():
        depth = model.section_depth_cm(levels[s.gauge], s.offset_cm)
        out.append({"section": s.section, "country": s.country, "river_km": s.river_km,
                    "gauge": s.gauge, "gauge_level_cm": levels[s.gauge], "depth_cm": round(depth),
                    "max_draught_m": round(model.draught_m(depth), 2), "status": s.status})
    return out


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/routes")
def routes():
    out = []
    for rid, r in data.routes().iterrows():
        secs = data.route_sections(rid)
        out.append({"route_id": rid, "name": r["name"], "from_km": r.from_km, "to_km": r.to_km,
                    "transit_days": int(r.transit_days), "normal_rate_eur_t": r.normal_rate_eur_t,
                    "alternative_mode": r.alternative_mode, "alternative_rate_eur_t": r.alternative_rate_eur_t,
                    "status": r.status, "source": r.source,
                    "sections_real": int((secs.status == "real").sum()),
                    "sections_placeholder": int((secs.status == "placeholder").sum())})
    return out


@app.post("/quote")
def quote(req: QuoteRequest):
    if req.route not in data.routes().index:
        raise HTTPException(400, f"unknown route '{req.route}'. Options: {list(data.routes().index)}")
    if req.window_end < req.window_start:
        raise HTTPException(400, "window_end is before window_start")
    if (req.window_end - req.window_start).days > 92:
        raise HTTPException(400, "delivery window longer than 3 months")
    r = data.routes().loc[req.route]
    normal = req.normal_rate_eur_t or float(r.normal_rate_eur_t)
    alt = req.rail_rate_eur_t or float(r.alternative_rate_eur_t)
    gauges = list(data.route_sections(req.route).gauge.unique())

    if req.today:  # replay: pretend it is that day, using only data up to then
        levels = {}
        for g in gauges:
            s = data.history(g)
            s = s[s.index <= pd.Timestamp(req.today)].dropna()
            if s.empty:
                raise HTTPException(422, f"no history for {g} before {req.today}")
            levels[g] = float(s.iloc[-1])
        today, hist_end = req.today, req.today
    else:
        levels = {g: data.today_levels()[g] for g in gauges}
        today, hist_end = date.fromisoformat(data.today_date()[:10]), None
    if req.window_start < today:
        raise HTTPException(400, f"window_start is before 'today' ({today})")

    runs = simulate.run(req.route, today, levels, req.window_start, req.window_end, normal, hist_end)
    if runs.empty:
        raise HTTPException(422, "not enough history for this window")
    result = simulate.summarise(runs, req.quantity_t, normal)

    secs_today = _sections_today(req.route, levels)
    worst = min(secs_today, key=lambda s: s["depth_cm"])
    be = model.breakeven_draught(normal, alt)
    result["today"] = {"date": today.isoformat(), "levels_cm": levels,
                       "draught_m": max(worst["max_draught_m"], 0), "bottleneck": worst["section"],
                       "cost_eur_t": (round(c, 2) if (c := model.cost_per_t(worst["max_draught_m"], normal)) else None),
                       "sections": secs_today}
    result["rail_breakeven"] = None if be is None else {
        "mode": r.alternative_mode, "rate_eur_t": alt, "draught_m": be,
        "text": f"{r.alternative_mode.capitalize()} is cheaper when the max draught falls below {be} m",
        "gauge_levels": {s["section"]: {"gauge": s["gauge"],
                                         "level_cm": round(be * 100 + config.UKC_CM - (s["depth_cm"] - s["gauge_level_cm"]))}
                         for s in secs_today}}
    n_real = sum(s["status"] == "real" for s in secs_today)
    result["route"] = {"route_id": req.route, "name": r["name"], "transit_days": int(r.transit_days),
                       "status": r.status, "source": r.source}
    result["data_quality"] = {
        "sections_real": n_real, "sections_placeholder": len(secs_today) - n_real,
        "placeholder_gauges": [g for g in gauges if data.gauges().loc[g, "history"] == "placeholder"],
        "bottleneck_is_placeholder_share": round(float((runs.bottleneck_status == "placeholder").mean()), 2),
        "label": "real data" if n_real == len(secs_today) else "partly placeholder data (prototype)",
    }
    result["years_simulated"] = int(runs.year.nunique())
    result["inputs"] = {**req.model_dump(mode="json"), "normal_rate_eur_t": normal, "rail_rate_eur_t": alt}
    return result


@app.get("/gauges")
def gauges():
    """Today's level at ~80 Danube gauges (all countries) for the map."""
    df = data.all_gauges_today()
    return df.where(df.notna(), None).to_dict(orient="records")


@app.get("/sections")
def sections():
    return data.sections().to_dict(orient="records")


@app.get("/assumptions")
def assumptions():
    """Every number the model uses and where it comes from."""
    return {
        "constants": [
            {"name": "barge_table", "value": config.BARGE_TABLE, "source": "Pro Danube 2013 (operator data), Kiliya shipyard specs", "status": "real"},
            {"name": "under_keel_clearance_cm", "value": config.UKC_CM, "source": "Contargo (~20 cm), RiverSat (30 cm)", "status": "real"},
            {"name": "fixed_cost_share", "value": config.FIXED_COST_SHARE, "source": "fitted to Pro Danube 2013 convoy costs", "status": "real"},
            {"name": "scarcity_slope", "value": config.SCARCITY_SLOPE, "source": "calibrated: July 2026 rates +100 % at ~50 % load (Logos Press / ASAP Agri)", "status": "real"},
            {"name": "min_draught_m", "value": config.MIN_DRAUGHT_M, "source": "PLACEHOLDER", "status": "placeholder"},
            {"name": "history_start_year", "value": config.HISTORY_START_YEAR, "source": "riverbed erosion in APPD data", "status": "real"},
            {"name": "anomaly_fade_days", "value": config.ANOMALY_FADE_DAYS, "source": "PLACEHOLDER (to be tested in a backtest)", "status": "placeholder"},
        ],
        "routes": data.routes().reset_index().to_dict(orient="records"),
        "sections": data.sections().to_dict(orient="records"),
        "gauges": data.gauges().reset_index().to_dict(orient="records"),
    }
