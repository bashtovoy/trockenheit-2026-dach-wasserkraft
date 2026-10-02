#!/usr/bin/env python3
"""Meteorological correlation layer: ERA5 weather (Open-Meteo) x hydro generation.

Reads the cached daily weather (data/raw/weather_{country}_{year}.json.gz,
written by fetch_weather.py) and the hydro records already computed in
summary.json, and quantifies how the natural-hydro signal co-varies with
independent meteorological drivers: 2 m temperature, precipitation and
surface solar (shortwave) radiation.

Two grains, per the review decision:
  * ANNUAL summer (Jun-Aug): n = years in window (10). Directly matches the
    "Sommer 2026 vs 2017-2025" frame. Small-n, so r is reported with p and n.
  * MONTHLY within summer: n = 3 x years per country (~30). Correlated on
    WITHIN-MONTH ANOMALIES (value minus that country-month climatology) so the
    seasonal cycle (Jun>Aug flow) does not masquerade as correlation.
Plus an ANTECEDENT check: spring (Mar-May) precipitation -> summer hydro.

Output: a dict for summary["weather"], consumed by build_report.py.
Attribution: ERA5 (Copernicus Climate Change Service) via open-meteo.com.
"""
from __future__ import annotations

import gzip
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "output"

COUNTRIES = ("de", "at", "ch")
YEARS = list(range(2017, 2027))
SUMMER = (6, 7, 8)
SPRING = (3, 4, 5)


# ----------------------------------------------------- statistics helpers ----

def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta (Lentz's method)."""
    tiny, fpmin = 1e-300, 1e-30
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, 200):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-10:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbeta + b * math.log1p(-x) + a * math.log(x)) * _betacf(b, a, 1 - x) / b


def pearson(x: list[float], y: list[float]) -> tuple[float, float, int]:
    """Pearson r, two-tailed p (Student t), and n. Returns (nan, nan, n) if undefined."""
    n = len(x)
    if n < 3:
        return float("nan"), float("nan"), n
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    if sxx <= 0 or syy <= 0:
        return float("nan"), float("nan"), n
    r = sxy / math.sqrt(sxx * syy)
    r = max(-1.0, min(1.0, r))
    df = n - 2
    if abs(r) >= 1.0:
        p = 0.0
    else:
        t = r * math.sqrt(df / (1 - r * r))
        p = _betai(df / 2.0, 0.5, df / (df + t * t))
    return r, p, n


# ------------------------------------------------------------- data loading --

def _load_weather(country: str, year: int) -> dict | None:
    path = RAW / f"weather_{country}_{year}.json.gz"
    if not path.exists():
        return None
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def _monthly_from_daily(daily: dict) -> dict:
    """Return {month_int: {"t":mean, "p":sum, "rad":mean}} from {date:{t,p,rad}}."""
    acc: dict[int, dict[str, list[float]]] = {}
    for date, v in daily.items():
        m = int(date[5:7])
        for k in ("t", "p", "rad"):
            if v.get(k) is None:
                continue
            acc.setdefault(m, {"t": [], "p": [], "rad": []})[k].append(v[k])
    out = {}
    for m, d in acc.items():
        out[m] = {
            "t": sum(d["t"]) / len(d["t"]) if d["t"] else None,
            "p": sum(d["p"]) if d["p"] else None,
            "rad": sum(d["rad"]) / len(d["rad"]) if d["rad"] else None,
        }
    return out


def _hydro_maps(summary: dict, country: str) -> tuple[dict, dict]:
    """Return ({year: {"natural","ror","res"}}, {(year,month): natural_gwh})."""
    ann = {int(r["year"]): {"natural": r.get("natural_gwh"), "ror": r.get("run_of_river_gwh"),
                            "res": r.get("reservoir_gwh")} for r in summary[f"{country}_hydro"]}
    mon = {(int(r["year"]), int(r["month"][5:7])): r.get("natural_gwh")
           for r in summary[f"{country}_monthly"]}
    return ann, mon


def _cell_latlon(country: str) -> list:
    from fetch_weather import CELLS
    return [list(x) for x in CELLS[country]]


def compute(summary: dict) -> dict:
    years = [y for y in YEARS if _load_weather("de", y)]
    wmo = {}       # per-country monthly weather
    wan = {}       # per-country annual weather
    hann = {}      # per-country annual hydro
    hmon = {}      # per-country monthly hydro
    for c in COUNTRIES:
        ann, mon = _hydro_maps(summary, c)
        hann[c], hmon[c] = ann, mon
        wmo[c], wan[c] = {}, {}
        for y in years:
            daily = _load_weather(c, y)
            if not daily:
                continue
            mm = _monthly_from_daily(daily)
            wmo[c][y] = mm
            st_t = [mm[m]["t"] for m in SUMMER if m in mm and mm[m]["t"] is not None]
            st_p = [mm[m]["p"] for m in SUMMER if m in mm and mm[m]["p"] is not None]
            st_r = [mm[m]["rad"] for m in SUMMER if m in mm and mm[m]["rad"] is not None]
            sp_p = [mm[m]["p"] for m in SPRING if m in mm and mm[m]["p"] is not None]
            wan[c][y] = {
                "t": sum(st_t) / len(st_t) if st_t else None,
                "p": sum(st_p) if st_p else None,
                "rad": sum(st_r) / len(st_r) if st_r else None,
                "spring_p": sum(sp_p) if sp_p else None,
            }

    def corr(vals_x, vals_y):
        r, p, n = pearson(vals_x, vals_y)
        return {"r": r, "p": p, "n": n}

    def pair(c, wvar, hyd_var, ys):
        xs, ysv = [], []
        for y in ys:
            wx = wan[c].get(y, {}).get(wvar)
            hv = hann[c].get(y, {}).get(hyd_var)
            if wx is not None and hv is not None:
                xs.append(wx); ysv.append(hv)
        return corr(xs, ysv) if len(xs) >= 3 else {"r": float("nan"), "p": float("nan"), "n": len(xs)}

    # ---- annual correlations (raw, n = years) ----
    annual = {c: {} for c in COUNTRIES}
    for c in COUNTRIES:
        ys = [y for y in years if y in wan[c] and y in hann[c]]
        for wv in ("t", "p", "rad", "spring_p"):
            annual[c][wv] = pair(c, wv, "natural", ys)
        annual[c]["p_vs_ror"] = pair(c, "p", "ror", ys)

    # ---- monthly correlations on within-month ANOMALIES (n = 3*years) ----
    monthly = {c: {} for c in COUNTRIES}
    for c in COUNTRIES:
        # climatology per (month) over the window
        clim = {}
        for m in SUMMER:
            for key in ("t", "p", "rad"):
                vs = [wmo[c][y][m][key] for y in years
                      if y in wmo[c] and m in wmo[c][y] and wmo[c][y][m][key] is not None]
                clim[(m, key)] = sum(vs) / len(vs) if vs else None
        hclim = {}
        for m in SUMMER:
            vs = [hmon[c][(y, m)] for y in years if (y, m) in hmon[c] and hmon[c][(y, m)] is not None]
            hclim[m] = sum(vs) / len(vs) if vs else None
        for wv in ("t", "p", "rad"):
            xs, ysv = [], []
            for y in years:
                for m in SUMMER:
                    if y not in wmo[c] or m not in wmo[c][y] or (y, m) not in hmon[c]:
                        continue
                    wx = wmo[c][y][m][wv]; hv = hmon[c][(y, m)]
                    if wx is None or hv is None or clim.get((m, wv)) is None or hclim.get(m) is None:
                        continue
                    xs.append(wx - clim[(m, wv)]); ysv.append(hv - hclim[m])
            monthly[c][wv] = corr(xs, ysv) if len(xs) >= 3 else {"r": float("nan"), "p": float("nan"), "n": len(xs)}

    # ---- scatter data (percent-of-country-mean) for the report chart ----
    scatter = {}
    for c in COUNTRIES:
        ys = [y for y in years if y in wan[c] and y in hann[c]]
        base_h = [hann[c][y]["natural"] for y in ys if hann[c].get(y, {}).get("natural")]
        base_p = [wan[c][y]["p"] for y in ys if wan[c].get(y, {}).get("p") is not None]
        mh = sum(base_h) / len(base_h) if base_h else None
        mp = sum(base_p) / len(base_p) if base_p else None
        pts = []
        for y in ys:
            h = hann[c][y].get("natural"); p = wan[c][y].get("p")
            if h and p is not None and mh and mp:
                pts.append({"year": y, "x": round(100 * p / mp, 1), "y": round(100 * h / mh, 1)})
        scatter[c] = pts

    return {
        "source": "ERA5 (Copernicus CDS) via open-meteo.com",
        "window": "summer 06-01..08-31; antecedent 03-01..05-31",
        "grain_note": "annual = raw; monthly = within-month anomalies; antecedent = spring precip -> summer hydro",
        "years": years,
        "cells": {c: _cell_latlon(c) for c in COUNTRIES},
        "annual_weather": {c: {str(y): wan[c].get(y) for y in years} for c in COUNTRIES},
        "annual_hydro": {c: {str(y): hann[c].get(y) for y in years} for c in COUNTRIES},
        "annual_corr": annual,
        "monthly_corr": monthly,
        "scatter": scatter,
    }


def main() -> None:
    summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    summary["weather"] = compute(summary)
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    w = summary["weather"]
    print("weather block written; years:", w["years"])
    for c in COUNTRIES:
        a, m = w["annual_corr"][c], w["monthly_corr"][c]
        print(f"{c.upper()} annual: t r={a['t']['r']:+.2f}(p={a['t']['p']:.3f}) "
              f"precip r={a['p']['r']:+.2f}(p={a['p']['p']:.3f}) rad r={a['rad']['r']:+.2f}(p={a['rad']['p']:.3f}) "
              f"| springP-> r={a['spring_p']['r']:+.2f}(p={a['spring_p']['p']:.3f})")
        print(f"      monthly(anom): t r={m['t']['r']:+.2f}(p={m['t']['p']:.3f}) "
              f"precip r={m['p']['r']:+.2f}(p={m['p']['p']:.3f}) rad r={m['rad']['r']:+.2f}(p={m['rad']['p']:.3f})")


if __name__ == "__main__":
    main()
