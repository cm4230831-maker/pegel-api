# Data status – what is real, what is a placeholder

Prototype for the hackathon, 22 Oct 2026. **Placeholders are invented values so every feature works in the demo.
They are marked `placeholder` in the data files and in every API answer (`data_quality`). Say so in the pitch.**

## Real data

| What | File | Source |
|---|---|---|
| Daily water levels 1941–2025 + 15–22 Oct 2026: Novo Selo, Lom, Oryahovo, Svishtov, Ruse, Silistra | `data/history/*.csv` | APPD / EAEMDR open data (appd-bg.org) |
| 19 critical sections km 386–608 with depth offsets | `data/sections.csv` (status `real`) | APPD critical sections, 22 Oct 2026 (deepest of left/middle/right lane) |
| Today's levels at ~76 gauges along the whole Danube (all countries) | `data/live/today_all_gauges.csv`, `data/today.csv` | APPD 8-day table, PEGELONLINE |
| Barge loading table (draught → tonnes) | `pegel/config.py` | Pro Danube 2013, Kiliya shipyard |
| Fixed cost share 0.77 | `pegel/config.py` | fitted to Pro Danube 2013 convoy costs |
| Scarcity premium | `pegel/config.py` | calibrated on July 2026: rates doubled at ~50 % load (Logos Press, ASAP Agri) |
| Truck alternative EUR 40–50/t (Bulgaria) | `data/routes.csv` | UkrAgroConsult, Aug 2026 |
| Price and barge facts | `data/prices.csv` (status `real`) | Pro Danube 2013, USM 2024, Logos Press / UkrAgroConsult 2026 |

## Placeholders (invented for the prototype)

| What | Where | How it was made | To replace with |
|---|---|---|---|
| Water-level history for Kienstock, Wildungsmauer, Medveďov, Budapest, Dunaföldvár, Apatin, Bogojevo, Novi Sad | `data/history/<gauge>.csv`, `data/gauges.csv` | Lom's **real** daily pattern 1996–2025, scaled (×0.7 Austria, ×0.8 others) and shifted to the gauge's **real** level on 22 Oct 2026 | eHYD (AT), hydroinfo.hu (HU), SHMÚ (SK), RHMZ (RS), DanubeHIS |
| 11 shallow sections outside the APPD list (Austria, Hungary, Slovakia, Serbia/Croatia, Lom–Oryahovo, Băloiu, Cernavodă) | `data/sections.csv` (status `placeholder`) | offsets chosen so today's depths are 1.6–2.1 m (2026 low water); each row says how | viadonau DoRIS, national waterway administrations, AFDJ |
| Normal barge rates for Novi Sad, Vienna, Linz → Constanța; rail rates; transit days for all routes | `data/routes.csv` | invented / proxies (each row says which) | broker quotes |
| Minimum draught for "no barge service" (1.0 m) | `pegel/config.py` | invented | operator / broker |
| Forecast fade time (30 days) | `pegel/config.py` | invented | backtest |
| Jan–14 Oct 2026 water levels | – | **not filled** (no August 2026 replay; we don't invent past events) | DanubeHIS, APPD |

## How to swap a placeholder for real data

1. Put the real file in `data/history/<gauge>.csv` (`date,level_cm`) – same name, it replaces the placeholder.
2. In `data/gauges.csv` set `history` to `real` and write the source.
3. For a section: in `data/sections.csv` set the real `offset_cm` (depth − same-day gauge reading), `status` = `real`, source.
4. Commit. Render redeploys; the API answer's `data_quality` updates by itself.
