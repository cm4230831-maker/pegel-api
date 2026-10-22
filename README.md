# Pegel API

Danube low-water freight risk pricer: turns water levels into a forward EUR/t range for a barge route.
The Lovable website calls this API; all calculations happen here.

**What's real and what's a placeholder: see [DATA_STATUS.md](DATA_STATUS.md).**

## How it calculates (one quote)

1. **Depth** at each shallow spot on the route = reading of its reference gauge + fixed offset (APPD method).
2. **Draught** = depth at the shallowest spot − 25 cm under-keel clearance.
3. **Tonnes** per Europa IIb barge from the loading table.
4. **EUR/t** = normal rate × (0.77 + 0.23·r) / r, r = load ratio; plus a scarcity premium at low loads.
5. **Forecast**: replay 1996–2025 for the same calendar days, starting from today's levels (today's departure fades over ~30 days). Percentiles → expected, range, bad case.

## Endpoints

| Endpoint | What |
|---|---|
| `POST /quote` | The calculator. Body: `route`, `quantity_t`, `window_start`, `window_end`, optional `normal_rate_eur_t`, `rail_rate_eur_t`, `today` (replay date) |
| `GET /routes` | Available routes with default rates and how many sections are real |
| `GET /gauges` | Today's level at ~76 gauges along the Danube (for the map) |
| `GET /sections` | All shallow spots with offsets and status |
| `GET /assumptions` | Every constant and its source |
| `GET /health` | `{"status": "ok"}` |

## Files

| File | What it does |
|---|---|
| `main.py` | The API |
| `pegel/model.py` | Steps 1–4 (depth, draught, tonnes, EUR/t) |
| `pegel/simulate.py` | Step 5 (replay past years) |
| `pegel/data.py` | Loads and checks all data; refuses to start on broken files |
| `pegel/config.py` | Constants with sources |
| `data/routes.csv`, `sections.csv`, `gauges.csv`, `today.csv` | Model inputs |
| `data/history/*.csv` | Daily levels `date,level_cm` |
| `data/live/` | Raw snapshots (APPD, FIS portal, PEGELONLINE); `today_all_gauges.csv` feeds the map |
| `scripts/data/` | The team's scripts that download and check APPD data |

## Run locally

```bash
pip install -r requirements.txt
pytest                      # 7 tests
uvicorn main:app --reload   # http://127.0.0.1:8000/docs
```

## Render settings

Build: `pip install -r requirements.txt` · Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

Water-level data: Executive Agency "Exploration and Maintenance of the Danube River" (EAEMDR/APPD), www.appd-bg.org – reformatted.
