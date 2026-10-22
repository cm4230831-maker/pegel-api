"""Creates FAKE history files so the code runs before the real data is ready.
Delete data/history/*.csv and replace them with real data as soon as Person A has it."""
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
dates = pd.date_range("1996-01-01", "2026-10-21", freq="D")
doy = dates.dayofyear.to_numpy()
season = 150 * np.cos(2 * np.pi * (doy - 120) / 365)        # high in spring, low in autumn
noise = np.cumsum(rng.normal(0, 6, len(dates)))
noise = noise - pd.Series(noise).rolling(120, min_periods=1).mean().to_numpy()
year_effect = pd.Series(rng.normal(0, 60, 40), index=range(1990, 2030))[dates.year].to_numpy()

out = Path(__file__).parent / "data" / "history"
out.mkdir(parents=True, exist_ok=True)
for gauge, base in {"ruse": 120, "svishtov": 160}.items():
    level = base + season + noise + year_effect
    pd.DataFrame({"date": dates.date, "level_cm": level.round().astype(int)}).to_csv(
        out / f"{gauge}.csv", index=False)
print("Fake history written to", out)
