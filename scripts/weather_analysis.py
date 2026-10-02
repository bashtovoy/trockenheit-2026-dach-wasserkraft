#!/usr/bin/env python3
"""Meteorological correlation layer: ERA5 weather (Open-Meteo) x hydro generation.

Reads the cached daily weather (data/raw/weather_{country}_{year}.json.gz,
written by fetch_weather.py) and the hydro records already computed in
summary.json, and quantifies how the natural-hydro signal co-varies with
independent meteorological drivers and a physically-grounded water-balance
drought index.

Design (external-methodology audit, incorporated):
  * Raw drivers: summer mean 2 m temperature, summer precipitation sum, summer
    mean shortwave radiation, summer ET0 (FAO-56 reference evapotranspiration).
  * Derived water-balance driver D = P - ET0 (mm over Jun-Aug): a METEOROLOGICAL
    water-balance proxy for the atmospheric water budget (ET0 is a reference
    grass with unlimited water), folding temperature/radiation into evaporative
    demand instead of treating them as separate crude proxies. It is NOT the
    catchment runoff balance: snow/glacier and soil/groundwater storage sit
    between P - ET0 and actual discharge (esp. in the Alps).
  * Climate baseline: every driver is STANDARDIZED against the fixed
    1991-2020 ERA5 climatology (WMO reference period). The z of the summer D
    (a Jun-Aug SUM, mu/sigma taken across the 30 seasonal-sum values) is
    reported as a "Saisonaler Wasserbilanz-Index Z_JJA" (negative = deficit).
    This is deliberately a plain seasonal z-score, NOT a real SPEI: SPEI
    requires a log-logistic probability transform of a 3-month rolling water
    balance, which we do not claim to implement.
  * Energy baseline stays 2017-2025 (the hydro side cannot use 1991-2020:
    Energy-Charts has no earlier generation record) - documented asymmetry.
  * Two grains: ANNUAL summers (n = analysis years, 10 CONSECUTIVE years, so
    lagged/inter-annual autocorrelation may remain -> purely exploratory) and
    MONTHLY
    within-month anomalies (value minus that country-month climatology) so the
    seasonal cycle does not masquerade as correlation (~30 obs). The monthly
    obs are NOT independent (3 months per season + autocorrelation), so the
    Student-t p is optimistic; a year-block permutation p (p_block) that
    permutes hydro seasons across weather seasons at the whole-year level is
    reported alongside it as the honest significance.
  * Antecedent: spring (Mar-May) precipitation -> summer hydro (prior-store
    proxy; snow-water-equivalent is not available in the selected long ERA5
    daily series - snow variables live only in other Open-Meteo products such
    as ERA5-Land snow_depth or CERRA snow_depth_water_equivalent, whose record
    ends mid-2021).
  * Two coefficients per pair: Pearson r (linear) AND Spearman rho (monotonic,
    robust for small n), each with a two-tailed p (Student t via the
    regularized incomplete beta; no scipy).

Attribution: ERA5 (Copernicus Climate Change Service) via open-meteo.com.
"""
from __future__ import annotations

import gzip
import json
import math
import random
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "output"

COUNTRIES = ("de", "at", "ch")
ANALYSIS_YEARS = list(range(2017, 2027))   # hydro generation available
BASELINE_YEARS = list(range(1991, 2021))   # fixed WMO climate normal
SUMMER = (6, 7, 8)
SPRING = (3, 4, 5)
DRIVERS = ("t", "p", "rad", "et0", "D", "spring_p")


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


def _ranks(x: list[float]) -> list[float]:
    """Average ranks (ties share the mean rank)."""
    n = len(x)
    order = sorted(range(n), key=lambda i: x[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and x[order[j + 1]] == x[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> tuple[float, float, int]:
    """Spearman rho with two-tailed p (t-approximation on ranks)."""
    n = len(x)
    if n < 3:
        return float("nan"), float("nan"), n
    return pearson(_ranks(x), _ranks(y))


def _corr(x: list[float], y: list[float]) -> dict:
    """Bundle Pearson r/p and Spearman rho/p for one driver-response pair."""
    if len(x) < 3:
        return {"r": float("nan"), "p": float("nan"), "rho": float("nan"),
                "p_rho": float("nan"), "n": len(x)}
    r, p, n = pearson(x, y)
    rho, p_rho, _ = spearman(x, y)
    return {"r": r, "p": p, "rho": rho, "p_rho": p_rho, "n": n}


def _year_block_perm_p(blocks: dict, obs_r: float, b: int = 10000,
                       seed: int = 20261002) -> float | None:
    """Two-sided year-block permutation p for a pooled within-month anomaly r.

    ``blocks`` maps {year: {month: (wx_anom, hydro_anom)}}. Observations stay
    grouped by year so the June-July-August structure (and its autocorrelation)
    is preserved; the null re-assigns whole hydro seasons to weather seasons by
    permuting years and recomputes Pearson r on the month-aligned pool.
    """
    years = sorted(blocks)
    n = len(years)
    if n < 3 or obs_r is None or math.isnan(obs_r):
        return None
    rng = random.Random(seed)
    idx = list(range(n))
    abs_obs = abs(obs_r)
    ge = 0
    for _ in range(b):
        perm = idx[:]
        rng.shuffle(perm)
        xs, ys = [], []
        for i, y in enumerate(years):
            wy = years[perm[i]]
            by, bw = blocks[y], blocks[wy]
            for m, (wx, _hv) in by.items():
                if m in bw:
                    xs.append(wx)
                    ys.append(bw[m][1])
        if len(xs) > 2:
            r = pearson(xs, ys)[0]
            if r is not None and not math.isnan(r) and abs(r) >= abs_obs:
                ge += 1
    return (ge + 1) / (b + 1)


# ------------------------------------------------------------- data loading --

def _load_weather(country: str, year: int) -> dict | None:
    path = RAW / f"weather_{country}_{year}.json.gz"
    if not path.exists():
        return None
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def _monthly_from_daily(daily: dict) -> dict:
    """Return {month_int: {"t","p","rad","et0"}} aggregated from {date:{...}}."""
    acc: dict[int, dict[str, list[float]]] = {}
    for date, v in daily.items():
        m = int(date[5:7])
        for k in ("t", "p", "rad", "et0"):
            if v.get(k) is None:
                continue
            acc.setdefault(m, {"t": [], "p": [], "rad": [], "et0": []})[k].append(v[k])
    out = {}
    for m, d in acc.items():
        out[m] = {
            "t": sum(d["t"]) / len(d["t"]) if d["t"] else None,
            "p": sum(d["p"]) if d["p"] else None,
            "rad": sum(d["rad"]) / len(d["rad"]) if d["rad"] else None,
            "et0": sum(d["et0"]) if d["et0"] else None,
        }
    return out


def _summer_metrics(daily: dict) -> dict:
    """Summer (Jun-Aug) aggregates + water balance D = P - ET0 + spring precip."""
    tt, pp, rr, ee, sp = [], [], [], [], []
    for date, v in daily.items():
        m = int(date[5:7])
        if m in SUMMER:
            if v.get("t") is not None:
                tt.append(v["t"])
            if v.get("p") is not None:
                pp.append(v["p"])
            if v.get("rad") is not None:
                rr.append(v["rad"])
            if v.get("et0") is not None:
                ee.append(v["et0"])
        elif m in SPRING and v.get("p") is not None:
            sp.append(v["p"])
    p_sum = sum(pp) if pp else None
    et0_sum = sum(ee) if ee else None
    return {
        "t": sum(tt) / len(tt) if tt else None,
        "p": p_sum,
        "rad": sum(rr) / len(rr) if rr else None,
        "et0": et0_sum,
        "D": (p_sum - et0_sum) if (p_sum is not None and et0_sum is not None) else None,
        "spring_p": sum(sp) if sp else None,
    }


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


def _zval(x, mu, sd):
    if x is None or mu is None or not sd:
        return None
    return (x - mu) / sd


def compute(summary: dict) -> dict:
    # ---- load summer metrics for all available years (baseline + analysis) ----
    summer = {c: {} for c in COUNTRIES}
    months = {c: {} for c in COUNTRIES}
    for c in COUNTRIES:
        for y in BASELINE_YEARS + ANALYSIS_YEARS:
            daily = _load_weather(c, y)
            if not daily:
                continue
            summer[c][y] = _summer_metrics(daily)
            months[c][y] = _monthly_from_daily(daily)

    # ---- baseline (1991-2020) mean/std per driver, per country ----
    baseline = {c: {} for c in COUNTRIES}
    for c in COUNTRIES:
        for key in DRIVERS:
            vs = [summer[c][y][key] for y in BASELINE_YEARS
                  if y in summer[c] and summer[c][y].get(key) is not None]
            mu = st.mean(vs) if vs else None
            sd = st.pstdev(vs) if len(vs) > 1 else None
            baseline[c][key] = {"mean": mu, "std": sd, "n": len(vs)}

    # ---- hydro maps (analysis years) ----
    hann, hmon = {}, {}
    for c in COUNTRIES:
        a, m = _hydro_maps(summary, c)
        hann[c], hmon[c] = a, m

    def series(c, key, ys):
        xs, ysv = [], []
        for y in ys:
            wv = summer[c].get(y, {}).get(key)
            hv = hann[c].get(y, {}).get("natural")
            if wv is not None and hv is not None:
                xs.append(wv)
                ysv.append(hv)
        return xs, ysv

    ys_all = [y for y in ANALYSIS_YEARS if y in summer.get("de", {})]

    # ---- annual correlations (raw summer values vs natural hydro) ----
    annual = {c: {} for c in COUNTRIES}
    for c in COUNTRIES:
        ys = [y for y in ANALYSIS_YEARS if y in summer[c] and y in hann[c]]
        for wv in DRIVERS:
            xs, ysv = series(c, wv, ys)
            annual[c][wv] = _corr(xs, ysv)
        # water-balance index expressed as z vs 1991-2020 (same r as raw D, but
        # reported as a climate-referenced deficit index for interpretation)
    # run-of-river sensitivity to water balance (nearest to discharge)
    for c in COUNTRIES:
        ys = [y for y in ANALYSIS_YEARS if y in summer[c] and y in hann[c]]
        xs, ysv = [], []
        for y in ys:
            wv = summer[c].get(y, {}).get("D")
            hv = hann[c].get(y, {}).get("ror")
            if wv is not None and hv is not None:
                xs.append(wv); ysv.append(hv)
        annual[c]["D_vs_ror"] = _corr(xs, ysv)

    # ---- monthly correlations on within-month ANOMALIES (n ~ 3*years) ----
    monthly = {c: {} for c in COUNTRIES}
    for c in COUNTRIES:
        clim, hclim = {}, {}
        for m in SUMMER:
            for key in ("t", "p", "rad", "et0"):
                vs = [months[c][y][m][key] for y in ANALYSIS_YEARS
                      if y in months[c] and m in months[c][y] and months[c][y][m].get(key) is not None]
                clim[(m, key)] = st.mean(vs) if vs else None
            vs = [hmon[c][(y, m)] for y in ANALYSIS_YEARS if (y, m) in hmon[c] and hmon[c][(y, m)] is not None]
            hclim[m] = st.mean(vs) if vs else None
        for wv in ("t", "p", "rad", "D_m"):
            xs, ysv = [], []
            blocks = {}
            for y in ANALYSIS_YEARS:
                for m in SUMMER:
                    if y not in months[c] or m not in months[c][y] or (y, m) not in hmon[c]:
                        continue
                    if wv == "D_m":
                        pw, ew = months[c][y][m].get("p"), months[c][y][m].get("et0")
                        cw, ce = clim.get((m, "p")), clim.get((m, "et0"))
                        if None in (pw, ew, cw, ce):
                            continue
                        wx = (pw - ew) - (cw - ce)
                    else:
                        wx = months[c][y][m].get(wv)
                        cw = clim.get((m, wv))
                        if wx is None or cw is None:
                            continue
                        wx = wx - cw
                    hv = hmon[c][(y, m)]
                    if hv is None or hclim.get(m) is None:
                        continue
                    ha = hv - hclim[m]
                    xs.append(wx); ysv.append(ha)
                    blocks.setdefault(y, {})[m] = (wx, ha)
            res = _corr(xs, ysv)
            pb = _year_block_perm_p(blocks, res["r"])
            res["p_block"] = round(pb, 4) if pb is not None else None
            monthly[c][wv] = res

    # ---- scatter: Wasserbilanz-Index z(D) vs natural hydro (% of analysis mean) ----
    scatter = {}
    for c in COUNTRIES:
        ys = [y for y in ANALYSIS_YEARS if y in summer[c] and y in hann[c]]
        base_h = [hann[c][y]["natural"] for y in ys if hann[c].get(y, {}).get("natural")]
        mh = st.mean(base_h) if base_h else None
        bD = baseline[c]["D"]
        pts = []
        for y in ys:
            h = hann[c][y].get("natural")
            d = summer[c][y].get("D")
            if not h or mh is None or d is None or bD["mean"] is None or not bD["std"]:
                continue
            pts.append({"year": y,
                        "x": round((d - bD["mean"]) / bD["std"], 2),
                        "y": round(100 * h / mh, 1)})
        scatter[c] = pts

    # ---- per-year annual table (analysis) with z-scores vs baseline ----
    annual_weather = {}
    for c in COUNTRIES:
        rows = {}
        bD = baseline[c]["D"]
        for y in ANALYSIS_YEARS:
            if y not in summer[c]:
                continue
            s = summer[c][y]
            rows[str(y)] = {
                "t": s["t"], "p": s["p"], "rad": s["rad"], "et0": s["et0"], "D": s["D"],
                "z_t": _zval(s["t"], baseline[c]["t"]["mean"], baseline[c]["t"]["std"]),
                "z_p": _zval(s["p"], baseline[c]["p"]["mean"], baseline[c]["p"]["std"]),
                "z_D": _zval(s["D"], bD["mean"], bD["std"]),
                "natural": hann[c].get(y, {}).get("natural"),
            }
        annual_weather[c] = rows

    return {
        "source": "ERA5 (Copernicus CDS) via open-meteo.com",
        "model": "ERA5 (single reanalysis; no best-match model mixing)",
        "window": "summer 06-01..08-31; antecedent 03-01..05-31",
        "climate_baseline": "1991-2020 (WMO reference period)",
        "energy_baseline": "2017-2025 (Energy-Charts hydro record; no earlier data)",
        "index_def": "Saisonaler Wasserbilanz-Index Z_JJA = ((P-ET0)_Jun-Aug - mu_JJA(1991-2020))/sigma_JJA(1991-2020); <0 = Defizit. Bewusst KEIN SPEI (keine log-logistic-Wahrscheinlichkeitstransformation).",
        "grain_note": "annual = raw summer values (n=10 consecutive summers, exploratory - inter-annual autocorrelation not modeled); monthly = within-month anomalies -> p_block from a year-block permutation test (blocks exchangeable whole summers; Student-t p assumes independence and is optimistic here)",
        "years": ys_all,
        "cells": {c: _cell_latlon(c) for c in COUNTRIES},
        "baseline": baseline,
        "annual_weather": annual_weather,
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
    print("weather block written; analysis years:", w["years"])
    for c in COUNTRIES:
        a, m = w["annual_corr"][c], w["monthly_corr"][c]
        bd = w["baseline"][c]["D"]
        print(f"{c.upper()} baseline D summer-sum: mean={bd['mean']:.0f}mm sd={bd['std']:.0f}mm (n={bd['n']})")
        for k in DRIVERS:
            v = a[k]
            print(f"  {k:>8}: Pearson r={v['r']:+.2f}(p={v['p']:.3f})  Spearman rho={v['rho']:+.2f}(p={v['p_rho']:.3f})  n={v['n']}")
        print(f"  monthly D-anom: r={m['D_m']['r']:+.2f}(p={m['D_m']['p']:.3f}, p_block={m['D_m'].get('p_block')}) n={m['D_m']['n']}")


if __name__ == "__main__":
    main()
