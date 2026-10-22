# Pegel API – starter

The calculation core of Pegel plus the API the Lovable website calls.

## Run it on your laptop

```bash
pip install -r requirements.txt
python make_fake_data.py        # FAKE data so the code runs; replace with real data
pytest                          # 5 tests should pass
uvicorn main:app --reload       # then open http://127.0.0.1:8000/docs
```

## Files

| File | What it does | Who edits it |
| --- | --- | --- |
| `pegel/config.py` | Every number the model uses (sections, offsets, barge table, UKC) | Model + Data |
| `pegel/data.py` | Loads history CSVs, today's levels, live PEGELONLINE gauges | Data |
| `pegel/model.py` | Steps 1–3: level → depth → draught → tonnes → EUR/t | Model |
| `pegel/simulate.py` | Step 4: replay past years, percentiles, fan chart | Model |
| `main.py` | The API: `/quote`, `/gauges`, `/health` | Model |
| `data/history/<gauge>.csv` | `date,level_cm`, one row per day | Data |
| `data/today.csv` | `gauge_id,level_cm,date` – today's readings typed in from APPD | Data |

## Deploy on Render

Build command: `pip install -r requirements.txt`
Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
