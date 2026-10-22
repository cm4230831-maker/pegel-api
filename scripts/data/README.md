# Data scripts

Real data for the model, from public sources, plus a check report. Run everything from the repository root.

```bash
pip install -r requirements.txt -r scripts/data/requirements.txt
python scripts/data/appd_history.py    # history 1936/1941-2025 (downloads ~21 MB of PDFs once)
python scripts/data/snapshots.py       # today, forecasts, fairway depths - run daily
python scripts/data/search_list.py     # files in the team's search-list format (history incl. 2026 days, depths, prices)
python scripts/data/check.py           # writes data/DATA_REPORT.md and data/SOURCES.md
```

Order matters: `appd_history.py` rewrites `data/history` from the archive only; `search_list.py` then adds the days collected by `snapshots.py` and writes the partial files for Nikopol and the Romanian gauges.

## What you get

| File | Content | Source |
|---|---|---|
| `data/history/<station>.csv` | `date,level_cm`, daily. novo_selo, lom, oryahovo, svishtov, ruse, silistra: archive without gaps up to 2025, then the 2026 days collected so far. nikopol, corabia, zimnicea, giurgiu, oltenita, cernavoda: only the days collected so far (from 15 Oct 2026) | APPD open data, APPD 8-day table |
| `data/depths.csv` | `date,section,depth_cm,gauge,level_cm,source`: depth at each APPD critical section and the reading of the gauge APPD computes it from; search-list names where the km matches (Batin, Belene, Vardin, Gâsca) | APPD |
| `data/prices.csv` | `item,value,unit,date,route,source`: only values read at the source; see SOURCES.md | Pro Danube 2013, USM 2024, Logos Press / UkrAgroConsult 2026 |
| `data/extra/appd_daily.csv` | same days plus discharge (m3/s) and water temperature (degC) | APPD open data |
| `data/extra/appd_stations.csv` | river km and gauge zero (m, Baltic system) per station | APPD yearly files |
| `data/today.csv` | `gauge_id,level_cm,date` for all 8 APPD manual gauges (the model uses ruse and svishtov) | APPD |
| `data/live/appd_today.csv` | today's level, discharge, 24 h change, temperature at 8 manual + 10 automatic gauges | APPD |
| `data/live/appd_forecasts.csv` | 6-day level forecast with min/max for Oryahovo, Nikopol, Svishtov, Ruse, Silistra | APPD |
| `data/live/appd_bottlenecks.csv` | 20 critical sections km 374-610: survey date, width, depth left/middle/right today and 3 forecast days, link to the survey PDF | APPD |
| `data/live/gauges_daily.csv` | daily levels at ~66 gauges along the whole Danube (APPD 8-day table) and German gauges (PEGELONLINE, 30-day daily means) | APPD, PEGELONLINE |
| `data/live/danubeportal.csv` | current level at ~107 gauges in all riparian states, with ISRS code | Danube FIS portal |
| `data/extra/appd_files.csv` | every source PDF with its URL and download date | APPD open data |
| `data/DATA_REPORT.md` | coverage, jumps, riverbed erosion, source comparison, depth offsets | `check.py` |
| `data/SOURCES.md` | overview of all data files (period, places, rows) and every source with URL, terms and what we changed | `check.py` |

`snapshots.py` appends and de-duplicates, so the `data/live` files become our own history from the first run on.

## Sources and terms

- **APPD / EAEMDR** (Bulgarian Executive Agency "Exploration and Maintenance of the Danube River"): <https://www.appd-bg.org>. Open-data terms: name EAEMDR as the source, mark modified data as modified, no use of their name or logo for commercial purposes without consent.
- **Danube FIS portal**: <https://www.danubeportal.com> (operated by the riparian waterway administrations).
- **PEGELONLINE**: <https://www.pegelonline.wsv.de> (German Federal Waterways and Shipping Administration).

## Findings worth knowing (22 Oct 2026)

- **History is complete**: 0 missing days 1941-2025 for all six stations.
- **2026 is below anything on record**: Ruse read -140 cm on 22 Oct 2026; the lowest daily value 1941-2025 was -73 cm.
- **Riverbed erosion is real**: at the same low discharge (1,800-2,200 m3/s) Ruse reads about 100 cm lower in the 2020s than in the 1940s-60s. Use recent decades only (config: `HISTORY_START_YEAR`) or simulate in discharge.
- **APPD computes fairway depth as gauge + constant**: for every critical section the offset is identical today and on all forecast days (`check.py` section 5). That also tells us which gauge APPD uses per section.
- **Batin offset in config is off**: APPD links the Batin area (km 530-527) to **Svishtov +270 cm**, not Ruse +274 cm. With today's levels: config gives 134 cm, APPD 178 cm. Belene island: **Svishtov +250 cm** (config placeholder +230).
- **The shallowest sections today are further downstream**: Albina island (km 414, Silistra +250 cm, 108 cm deep today), G. Byrzina (km 576), Chaika and Popina (km 387/405). They are on the Lom/Ruse -> Constanta route but not in `config.SECTIONS`.
- **Gap**: no daily data for 1 Jan 2026 until the first snapshot (APPD archive ends 2025). The August 2026 replay needs it - see `DATA_REPORT.md` section 6. Until then a replay date in 2026 silently uses the last 2025 value.
