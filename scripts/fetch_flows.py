#!/usr/bin/env python3
"""Supplementary download: cross-border physical flows (cbpf) for DACH summers.

Reuses the HTTP/backoff logic from fetch_data.py.
"""

from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_data import API, COUNTRIES, NoData, http_get, prune, summers  # noqa: E402

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

KEEP = ["sum", "austria", "switzerland", "france", "italy", "germany", "czechia", "denmark", "poland", "slovenia", "norway", "sweden", "netherlands", "belgium", "great britain", "united kingdom"]


def main() -> int:
    years = [int(x) for x in (sys.argv[1] if len(sys.argv) > 1 else "2017-2026").split("-")]
    rng = list(range(years[0], years[1] + 1))
    RAW.mkdir(parents=True, exist_ok=True)
    got = skipped = missing = 0
    for y, start, end in summers(rng):
        for country in COUNTRIES:
            path = RAW / f"cbpf_{country}_{y}.json.gz"
            if path.exists() and path.stat().st_size > 2000:
                skipped += 1
                continue
            print(f"[get ] cbpf/{country} {start}..{end}", flush=True)
            try:
                payload = http_get(f"{API}/cbpf", {"country": country, "start": start, "end": end})
            except NoData as exc:
                print(f"       -- not published ({exc})", flush=True)
                missing += 1
                time.sleep(12)
                continue
            pruned = prune(payload, KEEP)
            with gzip.open(path, "wt", encoding="utf-8") as fh:
                json.dump(pruned, fh)
            print(f"       -> rows={len(pruned['data'])} series={[s['id'] for s in pruned['series']]}", flush=True)
            got += 1
            time.sleep(14)
    print(f"done: {got} new, {skipped} cached, {missing} unavailable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
