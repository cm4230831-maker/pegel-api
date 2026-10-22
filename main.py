"""The API "door" the Lovable website talks to. Run locally with:
    uvicorn main:app --reload
then open http://127.0.0.1:8000/docs to try it in the browser."""
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pegel import config, data, model, simulate

app = FastAPI(title="Pegel API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

HISTORY = data.load_all_history()  # loaded once when the server starts


class QuoteRequest(BaseModel):
    route: str = "lom-constanta"
    cargo: str = "wheat"
    quantity_t: float = 3000
    window_start: date
    window_end: date
    normal_rate_eur_t: float = 12.0
    rail_rate_eur_t: float | None = None
    today: date | None = None          # set this to replay a past date (e.g. 2026-06-15)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/quote")
def quote(req: QuoteRequest):
    if req.window_end < req.window_start:
        raise HTTPException(400, "window_end is before window_start")
    if req.today:  # replay mode: pretend it is that day
        hist = {g: s[s.index <= str(req.today)] for g, s in HISTORY.items()}
        today_levels = {g: float(s.dropna().iloc[-1]) for g, s in hist.items()}
        today = req.today
    else:
        today_levels = data.latest_levels(HISTORY)
        today = date.today()
    sim = simulate.simulate(HISTORY, today_levels, today, req.window_start,
                            req.window_end, req.normal_rate_eur_t)
    if sim["runs"].empty:
        raise HTTPException(422, "Not enough history for this window")
    result = simulate.summarise(sim["runs"], req.quantity_t)
    now_draught, now_section = model.max_draught_m(today_levels)
    result["today"] = {"date": today.isoformat(), "levels_cm": today_levels,
                       "draught_m": round(now_draught, 2), "bottleneck": now_section}
    result["rail_breakeven"] = (model.rail_breakeven(req.normal_rate_eur_t, req.rail_rate_eur_t)
                                if req.rail_rate_eur_t else None)
    result["years_simulated"] = sim["years_used"]
    result["inputs"] = req.model_dump(mode="json")
    return result


@app.get("/gauges")
def gauges():
    """Live German Danube gauges for the map."""
    try:
        return data.pegelonline_danube()
    except Exception as e:
        raise HTTPException(502, f"PEGELONLINE unavailable: {e}")
