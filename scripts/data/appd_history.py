"""Build daily history files from the APPD open data (Bulgarian Danube agency).

Source: Executive Agency "Exploration and Maintenance of the Danube River" (EAEMDR / APPD),
https://www.appd-bg.org/pages-en?id=opendata. Reuse terms: name EAEMDR as the source and
mark modified data as modified.

Inputs (downloaded once into data/raw/appd/, skipped if already there):
  - long-term tables 1936/1941-2019: daily water level H (cm), discharge Q (m3/s), water temperature t (degC)
    layout: one row per calendar day, one column per year; 29 Feb lists leap years only
  - yearly files 2020-2025: one row per date with H, Q, t

Outputs:
  data/history/<station>.csv   date,level_cm            (the format pegel/data.py reads)
  data/extra/appd_daily.csv    station,date,level_cm,discharge_m3s,water_temp_c
  data/extra/appd_stations.csv station,name,river_km,zero_elevation_m
  data/extra/appd_files.csv    one row per source PDF: file,url,station,content,downloaded,bytes

Run from the repository root:
    python scripts/data/appd_history.py            # download if needed, then parse
    python scripts/data/appd_history.py --offline  # parse what is already in data/raw/appd
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "appd"
OPENDATA_URL = "https://www.appd-bg.org/pages-en?id=opendata"
BASE_URL = "https://www.appd-bg.org/"
USER_AGENT = "Pegel-Hackathon/0.1 (research prototype)"

# File-name fragment -> station id used everywhere in the repo
STATIONS = {
    "novo_selo": "novo_selo", "lom": "lom", "oryahovo": "oryahovo",
    "svishtov": "svishtov", "ruse": "ruse", "silistra": "silistra",
}
LONG_TERM_KIND = [  # (pattern in file name, variable)
    (re.compile(r"water_level", re.I), "level_cm"),
    (re.compile(r"water_discharge|gauging_station_lom", re.I), "discharge_m3s"),
    (re.compile(r"water_temp", re.I), "water_temp_c"),
]
YEARLY = re.compile(r"_(?P<station>[a-z_]+?)_(?P<year>20\d\d)\.pdf$", re.I)
DATA_ROW = re.compile(r"^\s*(\d{1,2})\s+(\d{1,2})\s+(.*)$")
YEARLY_ROW = re.compile(r"^\s*(\d{2})\.(\d{2})\.(\d{4})\s+(.*)$")
NUMBER = re.compile(r"^-?\d+(?:[.,]\d+)?$")


def download() -> None:
    """Fetch every PDF linked on the open-data page (skips files already present)."""
    RAW.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(OPENDATA_URL, headers={"User-Agent": USER_AGENT})
    page = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")
    (RAW / "opendata.html").write_text(page, encoding="utf-8")
    links = sorted({html.unescape(l) for l in re.findall(r'href="([^"]*documents/kpetrov/[^"]+\.pdf)"', page)})
    new = 0
    for link in links:
        target = RAW / link.split("/")[-1]
        if target.exists():
            continue
        req = urllib.request.Request(BASE_URL + link.lstrip("/"), headers={"User-Agent": USER_AGENT})
        target.write_bytes(urllib.request.urlopen(req, timeout=120).read())
        new += 1
        time.sleep(0.5)  # be polite to the agency's server
    print(f"APPD open data: {len(links)} files listed, {new} downloaded")


def pdf_text(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def station_of(name: str) -> str | None:
    low = name.lower()
    for key in sorted(STATIONS, key=len, reverse=True):
        if key in low:
            return STATIONS[key]
    return None


def number(token: str) -> float:
    return float(token.replace(",", "."))


def parse_long_term(path: Path) -> pd.Series:
    """Day x year table -> Series indexed by date."""
    lines = pdf_text(path).splitlines()
    head_end = next(i for i, l in enumerate(lines) if l.strip().lower().startswith("date"))
    years = [int(t) for l in lines[:head_end] for t in l.split() if re.fullmatch(r"(19|20)\d\d", t)]
    leap_years = [y for y in years if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)]
    values = {}
    for line in lines[head_end + 1:]:
        m = DATA_ROW.match(line)
        if not m:
            continue
        day, month = int(m.group(1)), int(m.group(2))
        tokens = [t for t in m.group(3).split() if NUMBER.match(t)]
        if day == 29 and month == 2:
            cols = leap_years  # 29 Feb only exists in leap years; columns are listed in order
        else:
            cols = years
        if len(tokens) != len(cols):
            raise ValueError(f"{path.name}: {day}.{month}. has {len(tokens)} values, expected {len(cols)}")
        for y, t in zip(cols, tokens):
            values[pd.Timestamp(date(y, month, day))] = number(t)
    return pd.Series(values).sort_index()


def parse_yearly(path: Path) -> pd.DataFrame:
    """Yearly file: date, H (cm), Q (m3/s), t (degC). Missing values stay empty."""
    rows = []
    for line in pdf_text(path).splitlines():
        m = YEARLY_ROW.match(line)
        if not m:
            continue
        d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        tokens = [t for t in m.group(4).split() if NUMBER.match(t)]
        level, discharge, temp = (tokens + [None, None, None])[:3]
        rows.append({"date": pd.Timestamp(d),
                     "level_cm": number(level) if level is not None else None,
                     "discharge_m3s": number(discharge) if discharge is not None else None,
                     "water_temp_c": number(temp) if temp is not None else None})
    return pd.DataFrame(rows).set_index("date")


def station_meta(path: Path, station: str) -> dict:
    text = pdf_text(path)
    km = re.search(r"located at km\s*([\d.]+)", text)
    zero = re.search(r"zero elevation of\s*([\d.]+)\s*m", text)
    return {"station": station, "name": station.replace("_", " ").title(),
            "river_km": float(km.group(1)) if km else None,
            "zero_elevation_m": float(zero.group(1)) if zero else None,
            "elevation_system": "Baltic Sea - Kronstadt" if zero else None}


def build() -> None:
    pdfs = sorted(RAW.glob("*.pdf"))
    if not pdfs:
        sys.exit("No PDFs in data/raw/appd - run without --offline first.")
    frames: dict[str, list[pd.DataFrame]] = {}
    meta: dict[str, dict] = {}
    provenance = []
    for pdf in pdfs:
        station = station_of(pdf.name)
        if station is None:
            print(f"  skipped (unknown station): {pdf.name}")
            continue
        kind = next((var for pat, var in LONG_TERM_KIND if pat.search(pdf.name)), None)
        if kind:
            part = parse_long_term(pdf).rename(kind).to_frame()
            content = f"{kind}, {part.index.min().year}-{part.index.max().year}"
        elif YEARLY.search(pdf.name):
            part = parse_yearly(pdf)
            content = f"level_cm, discharge_m3s, water_temp_c, {part.index.min().year}"
            meta.setdefault(station, station_meta(pdf, station))  # yearly files state km and gauge zero
        else:
            print(f"  skipped (unknown layout): {pdf.name}")
            continue
        frames.setdefault(station, []).append(part)
        provenance.append({"file": pdf.name, "url": f"{BASE_URL}documents/kpetrov/{pdf.name}",
                           "station": station, "content": content,
                           "downloaded": pd.Timestamp(pdf.stat().st_mtime, unit="s").date(),
                           "bytes": pdf.stat().st_size})

    hist_dir, extra_dir = ROOT / "data" / "history", ROOT / "data" / "extra"
    hist_dir.mkdir(parents=True, exist_ok=True)
    extra_dir.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for station, parts in sorted(frames.items()):
        df = pd.concat(parts).groupby(level=0).first()  # long-term and yearly files do not overlap
        df = df.reindex(columns=["level_cm", "discharge_m3s", "water_temp_c"])
        level = df["level_cm"].dropna().astype(int)
        pd.DataFrame({"date": level.index.date, "level_cm": level.values}).to_csv(
            hist_dir / f"{station}.csv", index=False)
        out = df.reset_index().rename(columns={"index": "date"})
        out.insert(0, "station", station)
        out["date"] = out["date"].dt.date
        all_rows.append(out)
        print(f"  {station:10s} level {level.index.min().date()} .. {level.index.max().date()} "
              f"({len(level)} days), discharge {int(df['discharge_m3s'].notna().sum())} days, "
              f"temperature {int(df['water_temp_c'].notna().sum())} days")
    pd.concat(all_rows).to_csv(extra_dir / "appd_daily.csv", index=False)
    pd.DataFrame(meta.values()).sort_values("river_km", ascending=False).to_csv(
        extra_dir / "appd_stations.csv", index=False)
    pd.DataFrame(provenance).sort_values(["station", "file"]).to_csv(extra_dir / "appd_files.csv", index=False)
    print("Wrote data/history/<station>.csv and data/extra/appd_daily.csv, appd_stations.csv, appd_files.csv")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true", help="do not download, only parse data/raw/appd")
    args = ap.parse_args()
    if not args.offline:
        download()
    build()


if __name__ == "__main__":
    main()
