#!/usr/bin/env python3
"""Download summer production + day-ahead price series from energy-charts.info API v2.

Covers Germany (de) and Switzerland (ch) for a range of years, Jun 1 - Aug 31
(local-time calendar summer quarter used as the "summer" window).

Raw responses are pruned to the series we actually need, then stored as gzip
JSON under data/raw/ so the job is resumable.
"""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API = "https://api.energy-charts.info/v2"
UA = "energy-charts-analysis/1.0 (personal research; data CC BY 4.0 energy-charts.info)"


def _ssl_context() -> ssl.SSLContext:
    """macOS python.org builds ship without a trusted CA store; use certifi."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()

# Series kept per dataset. Note: CH public_power has no pumped-storage
# consumption series, DE and AT do.
KEEP_PRODUCTION = {
    "de": [
        "load",
        "hydro_run_of_river",
        "hydro_water_reservoir",
        "hydro_pumped_storage",
        "hydro_pumped_storage_consumption",
        "wind_onshore",
        "wind_offshore",
        "solar",
        "renewable_share_of_load",
    ],
    "at": [
        "load",
        "hydro_run_of_river",
        "hydro_water_reservoir",
        "hydro_pumped_storage",
        "hydro_pumped_storage_consumption",
        "wind_onshore",
        "solar",
        "renewable_share_of_load",
    ],
    "ch": [
        "load",
        "hydro_run_of_river",
        "hydro_water_reservoir",
        "hydro_pumped_storage",
        "wind_onshore",
        "solar",
        "nuclear",
        "renewable_share_of_load",
    ],
}

# DACH / Alpine region, in report order.
COUNTRIES = ("de", "at", "ch")

PRICE_BZN = {"de": "DE-LU", "at": "AT", "ch": "CH"}

KEEP_CAPACITY = {
    "de": ["hydro", "hydro_pumped_storage", "wind_onshore", "wind_offshore", "solar_ac", "load"],
    "at": ["hydro", "hydro_pumped_storage", "wind_onshore", "solar_dc", "solar_ac", "load"],
    "ch": ["hydro", "hydro_pumped_storage", "wind_onshore", "solar_dc", "load"],
}


class NoData(Exception):
    """Raised when the API answers 404 / 'no content available' (range not published)."""


def _is_no_data(body: str) -> bool:
    return body.strip().startswith("no content available")


def http_get(url: str, params: dict, retries: int = 6) -> dict:
    """GET with backoff; the API rate-limits aggressively (HTTP 429)."""
    query = urllib.parse.urlencode(params)
    full = f"{url}?{query}"
    ctx = _ssl_context()
    last_err: str = "unknown"
    for attempt in range(retries):
        req = urllib.request.Request(full, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180, context=ctx) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            body = exc.read()[:200].decode("utf-8", "replace") if exc.fp else ""
            last_err = f"HTTP {exc.code}: {body}"
            if exc.code == 404 or _is_no_data(body):
                raise NoData(last_err)
            if exc.code == 429:
                wait = 20 * (attempt + 1)
            elif exc.code >= 500:
                wait = 5 * (attempt + 1)
            else:
                break
            print(f"    retry in {wait}s ({last_err})", flush=True)
            time.sleep(wait)
        except Exception as exc:  # timeouts, connection resets
            last_err = repr(exc)
            wait = 10 * (attempt + 1)
            print(f"    retry in {wait}s ({last_err})", flush=True)
            time.sleep(wait)
    # Last resort: curl, which uses the system trust store.
    if shutil.which("curl"):
        for attempt in range(retries):
            proc = subprocess.run(
                ["curl", "-sS", "--max-time", "240", "-A", UA, full],
                capture_output=True, text=True,
            )
            out = proc.stdout.strip()
            if proc.returncode == 0 and _is_no_data(out):
                raise NoData(f"curl: {out[:80]}")
            if proc.returncode == 0 and out.startswith("{"):
                try:
                    return json.loads(out)
                except json.JSONDecodeError as exc:
                    last_err = f"curl json: {exc}"
            else:
                last_err = f"curl rc={proc.returncode} {out[:60] or proc.stderr[:120]}"
            wait = 20 * (attempt + 1)
            print(f"    curl retry in {wait}s ({last_err})", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"GET failed: {last_err}")



def prune(payload: dict, keep: list[str]) -> dict:
    """Drop unrequested series and null-only rows to shrink the on-disk cache."""
    out = {k: v for k, v in payload.items() if k not in ("series", "data", "attributes")}
    out["series"] = [s for s in payload.get("series", []) if s["id"] in keep]
    rows = []
    for row in payload.get("data", []):
        vals = {k: v for k, v in row["values"].items() if k in keep}
        if any(v is not None for v in vals.values()):
            rows.append({"timestamp": row["timestamp"], "values": vals})
    out["data"] = rows
    return out


def summers(years: list[int]) -> list[tuple[int, str, str]]:
    spans = []
    for y in years:
        start = date(y, 6, 1)
        end = date(y, 8, 31)
        # API `end` is inclusive of the labelled interval start; add last day.
        spans.append((y, start.isoformat(), (end + timedelta(days=1)).isoformat()))
    return spans


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2017-2026")
    ap.add_argument("--outdir", default=str(Path(__file__).resolve().parents[1] / "data" / "raw"))
    ap.add_argument("--sleep", type=float, default=12.0, help="seconds between API calls")
    args = ap.parse_args()

    if "-" in args.years:
        a, b = args.years.split("-")
        years = list(range(int(a), int(b) + 1))
    else:
        years = [int(x) for x in args.years.split(",")]

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    jobs: list[tuple[str, str, str, dict, list[str]]] = []
    for y, start, end in summers(years):
        for country in COUNTRIES:
            jobs.append((
                "production", "public_power", country,
                {"country": country, "start": start, "end": end},
                KEEP_PRODUCTION[country],
            ))
    for y, start, end in summers(years):
        for country in COUNTRIES:
            jobs.append((
                "price", "price", country,
                {"bzn": PRICE_BZN[country], "start": start, "end": end},
                ["day_ahead_price"],
            ))

    for country in COUNTRIES:
        jobs.append((
            "capacity", "installed_power", country,
            {"country": country, "start": "2000-01-01", "end": "2026-09-30",
             "time_step": "yearly"},
            KEEP_CAPACITY[country],
        ))

    done = skipped = 0
    missing: list[str] = []
    for kind, endpoint, country, params, keep in jobs:
        stem = f"{kind}_{country}_{params['start'][:4]}"
        path = outdir / f"{stem}.json.gz"
        if path.exists() and path.stat().st_size > 2000:
            print(f"[skip] {stem} already cached")
            skipped += 1
            continue
        print(f"[get ] {kind}/{country} {params['start']}..{params['end']}", flush=True)
        try:
            payload = http_get(f"{API}/{endpoint}", params)
        except NoData as exc:
            print(f"       -- not published, skipped ({exc})", flush=True)
            missing.append(stem)
            time.sleep(args.sleep)
            continue
        pruned = prune(payload, keep)
        if not pruned["data"]:
            print(f"       !! empty payload for {stem}: {payload.get('detail')}", flush=True)
            missing.append(stem)
            time.sleep(args.sleep)
            continue
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump(pruned, fh)
        print(f"       -> {path.name} rows={len(pruned['data'])} "
              f"until={pruned.get('available_until')}", flush=True)
        done += 1
        time.sleep(args.sleep)

    print(f"\nfinished: {done} downloaded, {skipped} cached, {len(missing)} unavailable")
    (outdir / "availability.json").write_text(
        json.dumps({"unavailable": sorted(missing),
                    "note": "price v2 is only published from ~2018 (CH) / ~2020 (DE-LU)"}, indent=1),
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
