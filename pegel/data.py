"""Loads and checks all data files. The server refuses to start on broken data
instead of quietly giving wrong prices."""
from functools import lru_cache
from pathlib import Path

import pandas as pd

from pegel import config

DATA = Path(__file__).resolve().parent.parent / "data"


class DataError(Exception):
    pass


def _read(name: str, cols: list[str]) -> pd.DataFrame:
    path = DATA / name
    if not path.exists():
        raise DataError(f"missing file data/{name}")
    df = pd.read_csv(path)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise DataError(f"data/{name}: missing columns {missing}")
    return df


@lru_cache
def routes() -> pd.DataFrame:
    df = _read("routes.csv", ["route_id", "name", "from_km", "to_km", "transit_days",
                              "normal_rate_eur_t", "alternative_mode", "alternative_rate_eur_t", "status", "source"])
    return df.set_index("route_id")


@lru_cache
def sections() -> pd.DataFrame:
    df = _read("sections.csv", ["section", "country", "river_km", "gauge", "offset_cm", "status", "source"])
    unknown = set(df.gauge) - set(gauges().index)
    if unknown:
        raise DataError(f"sections.csv uses gauges not in gauges.csv: {unknown}")
    return df


@lru_cache
def gauges() -> pd.DataFrame:
    return _read("gauges.csv", ["gauge_id", "name", "country", "river_km", "history", "history_source"]).set_index("gauge_id")


@lru_cache
def history(gauge_id: str) -> pd.Series:
    df = _read(f"history/{gauge_id}.csv", ["date", "level_cm"])
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")
    if df["date"].isna().any():
        raise DataError(f"history/{gauge_id}.csv: {df['date'].isna().sum()} bad dates (use YYYY-MM-DD)")
    if df["date"].duplicated().any():
        raise DataError(f"history/{gauge_id}.csv: duplicate dates")
    s = df.set_index("date")["level_cm"].astype(float).sort_index()
    if s.abs().max() > 2000:
        raise DataError(f"history/{gauge_id}.csv: value over 20 m - metres instead of cm?")
    s = s[s.index.year >= config.HISTORY_START_YEAR]
    if len(s) < 365 * 5:
        raise DataError(f"history/{gauge_id}.csv: less than 5 years since {config.HISTORY_START_YEAR}")
    return s.asfreq("D").interpolate(limit=5)


@lru_cache
def today_levels() -> dict:
    df = _read("today.csv", ["gauge_id", "level_cm", "date"])
    return {r.gauge_id: float(r.level_cm) for r in df.itertuples()}


@lru_cache
def today_date() -> str:
    return str(_read("today.csv", ["gauge_id", "level_cm", "date"])["date"].max())


@lru_cache
def all_gauges_today() -> pd.DataFrame:
    return _read("live/today_all_gauges.csv", ["gauge_id", "country", "river_km", "level_cm", "date", "source"])


def route_sections(route_id: str) -> pd.DataFrame:
    r = routes().loc[route_id]
    s = sections()
    return s[(s.river_km <= r.from_km) & (s.river_km >= r.to_km)].sort_values("river_km", ascending=False)


def check_all() -> None:
    """Called at startup: loads every file once so errors show up immediately."""
    routes(); sections(); gauges(); today_levels(); all_gauges_today()
    for rid in routes().index:
        for g in route_sections(rid).gauge.unique():
            history(g)
            if g not in today_levels():
                raise DataError(f"today.csv has no level for gauge {g} (needed by route {rid})")
