#!/usr/bin/env python3
"""Download ERA5 daily weather from Open-Meteo Archive API for the DACH region.

Fetches summer (Jun-Aug) plus preceding spring (Mar-May) for each year in
the analysis window (2017-2026) from a grid of representative cells per
country, weighted toward the Alps (where hydro actually runs).

Output: data/raw/weather_{country}_{year}.json.gz (gzip JSON, resumable).
No API key required. Data attribution: ERA5 / Copernicus Climate Change
Service, retrieved via open-meteo.com.

Usage:
    python3 scripts/fetch_weather.py [--years 2017-2026] [--sleep 1.0]
"""
from __future__ import annotations

import argparse
import gzip
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://archive-api.open-meteo.com/v1/archive"
UA = "energy-charts-analysis/1.0 (personal research; weather: ERA5 via open-meteo.com)"

# Representative ERA5 grid cells per country, weighted toward Alpine/pre-Alpine
# catchments feeding hydropower (not political centroids).
CELLS: dict[str, list[tuple[float, float]]] = {
    "de": [(47.5, 10.5), (47.7, 12.0), (48.8, 10.3), (49.5, 8.0),
           (50.9, 7.0), (51.2, 9.5), (53.3, 9.8)],
    "at": [(47.07, 11.4), (47.8, 13.0), (46.6, 14.2), (48.2, 14.0),
           (47.3, 9.7), (47.0, 13.5)],
    "ch": [(46.5, 8.0), (46.9, 8.2), (46.4, 10.1), (46.0, 7.9),
           (46.2, 6.1), (47.0, 8.5)],
}


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def http_get(url: str, params: dict, retries: int = 4):
    query = urllib.parse.urlencode(params)
    full = f"{url}?{query}"
    ctx = _ssl_context()
    for attempt in range(retries):
        req = urllib.request.Request(full, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=180, context=ctx) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                time.sleep(20 * (attempt + 1))
            elif exc.code >= 500:
                time.sleep(5 * (attempt + 1))
            else:
                raise
        except Exception:
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} retries: {full}")


def fetch_country_year(country: str, year: int) -> dict:
    lats = ",".join(str(a) for a, b in CELLS[country])
    lons = ",".join(str(b) for a, b in CELLS[country])
    params = {
        "latitude": lats,
        "longitude": lons,
        "start_date": f"{year}-03-01",
        "end_date": f"{year}-08-31",
        "daily": "temperature_2m_mean,precipitation_sum,shortwave_radiation_sum",
        "timezone": "Europe/Berlin",
    }
    res = http_get(API, params)
    arr = res if isinstance(res, list) else [res]
    n = len(arr)
    times = arr[0]["daily"]["time"]
    out: dict[str, dict] = {}
    for i, dt in enumerate(times):
        tv = [arr[j]["daily"]["temperature_2m_mean"][i] for j in range(n)]
        pv = [arr[j]["daily"]["precipitation_sum"][i] for j in range(n)]
        rv = [arr[j]["daily"]["shortwave_radiation_sum"][i] for j in range(n)]
        tv = [x for x in tv if x is not None]
        pv = [x for x in pv if x is not None]
        rv = [x for x in rv if x is not None]
        out[dt] = {
            "t": sum(tv) / len(tv) if tv else None,
            "p": sum(pv) / len(pv) if pv else None,
            "rad": sum(rv) / len(rv) if rv else None,
            "n_cells": len(tv),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2017-2026")
    ap.add_argument("--outdir", default=str(Path(__file__).resolve().parents[1] / "data" / "raw"))
    ap.add_argument("--sleep", type=float, default=1.0)
    args = ap.parse_args()

    if "-" in args.years:
        a, b = args.years.split("-")
        years = list(range(int(a), int(b) + 1))
    else:
        years = [int(x) for x in args.years.split(",")]

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    done = skipped = 0
    for country in CELLS:
        for year in years:
            stem = f"weather_{country}_{year}"
            path = outdir / f"{stem}.json.gz"
            if path.exists() and path.stat().st_size > 200:
                print(f"[skip] {stem}")
                skipped += 1
                continue
            print(f"[get ] {stem}", flush=True)
            data = fetch_country_year(country, year)
            with gzip.open(path, "wt", encoding="utf-8") as fh:
                json.dump(data, fh)
            print(f"       -> {path.name} days={len(data)}", flush=True)
            done += 1
            time.sleep(args.sleep)

    print(f"\nfinished: {done} fetched, {skipped} cached")
    return 0


if __name__ == "__main__":
    sys.exit(main())
