#!/usr/bin/env python3
"""Aggregate cached energy-charts.info API v2 data into summer hydro metrics.

Outputs (in output/):
  hydro_summer_<country>.csv    one row per year: GWh by hydro category + shares
  hydro_monthly_<country>.csv   GWh per month per year
  ps_summer_<country>.csv       pumped-storage metrics; DE and AT have a separate
                                pumping series, CH only generation (flagged in `reporting`)
  hourly_profiles.csv           mean MW by hour of day, per year, for PS/hydro
  price_summer.csv              day-ahead price statistics per summer
  summary.json                  machine-readable summary used by the report
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "output"

CURRENT_YEAR = 2026
BASE_FIRST = 2017  # first year of the comparison window
COUNTRIES = ("de", "at", "ch")            # DACH, in report order
COUNTRIES_UPPER = ("DE", "AT", "CH")
HYDRO_COLS = ["hydro_run_of_river", "hydro_water_reservoir", "hydro_pumped_storage"]
MONTH_ABBR = {6: "jun", 7: "jul", 8: "aug"}


# ---------------------------------------------------------------- loading ----

def load(kind: str, country: str, year: int) -> tuple[pd.DataFrame, float] | None:
    """Return a tidy frame (index=local timestamp, cols=series) plus interval hours."""
    path = RAW / f"{kind}_{country}_{year}.json.gz"
    if not path.exists():
        return None
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        payload = json.load(fh)
    rows = payload["data"]
    if not rows:
        return None
    idx = [r["timestamp"] for r in rows]
    vals = [r["values"] for r in rows]
    df = pd.DataFrame(vals, index=pd.to_datetime(idx))
    df = df[~df.index.duplicated(keep="first")].sort_index()
    diffs = df.index.to_series().diff().dropna().dt.total_seconds() / 3600.0
    interval_h = float(diffs.median()) if len(diffs) else 1.0
    return df, interval_h


def to_numeric(df: pd.DataFrame) -> pd.DataFrame:
    return df.apply(pd.to_numeric, errors="coerce")


def gwh(series: pd.Series, interval_h: float) -> float:
    """Integrate MW over time -> GWh (nulls treated as missing, not zero)."""
    x = pd.to_numeric(series, errors="coerce")
    return float(x.sum(skipna=True) * interval_h / 1000.0)


def gwh_from_gw(series: pd.Series, interval_h: float) -> float:
    """cbpf/cbet endpoints report GW, not MW."""
    x = pd.to_numeric(series, errors="coerce")
    return float(x.sum(skipna=True) * interval_h)


def coverage(series: pd.Series) -> float:
    return float(pd.to_numeric(series, errors="coerce").notna().mean())


def onshore(df: pd.DataFrame) -> pd.Series:
    return df["wind_onshore"].astype(float)


def wind_total(df: pd.DataFrame) -> pd.Series:
    if "wind_offshore" in df:
        return df["wind_onshore"].astype(float).add(df["wind_offshore"].astype(float), fill_value=0)
    return df["wind_onshore"].astype(float)


# ------------------------------------------------------- hydro per country ----

def hydro_table(country: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    per_year, monthly, profiles = [], [], []
    for year in range(BASE_FIRST, CURRENT_YEAR + 1):
        got = load("production", country, year)
        if got is None:
            continue
        df, ih = got
        df = to_numeric(df)
        df = df[(df.index >= f"{year}-06-01") & (df.index < f"{year}-09-01")]
        if df.empty:
            continue

        total_hydro = df[HYDRO_COLS].sum(axis=1, min_count=1)
        load_mw = df["load"] if "load" in df else pd.Series(np.nan, index=df.index)

        row = {
            "country": country.upper(),
            "year": year,
            "months_covered": sorted({ts.strftime("%m") for ts in df.index}),
            "intervals": len(df),
            "interval_h": ih,
            "run_of_river_gwh": gwh(df["hydro_run_of_river"], ih),
            "reservoir_gwh": gwh(df["hydro_water_reservoir"], ih),
            "pumped_gwh": gwh(df["hydro_pumped_storage"], ih),
            "hydro_total_gwh": gwh(total_hydro, ih),
            "load_gwh": gwh(load_mw, ih),
            "wind_gwh": gwh(onshore(df), ih),
            "solar_gwh": gwh(df["solar"], ih),
            "hydro_cov": coverage(total_hydro),
            "load_cov": coverage(load_mw),
        }
        row["hydro_share_of_load_pct"] = 100 * row["hydro_total_gwh"] / row["load_gwh"] if row["load_gwh"] else np.nan
        row["run_of_river_share_pct"] = 100 * row["run_of_river_gwh"] / row["hydro_total_gwh"]
        row["reservoir_share_pct"] = 100 * row["reservoir_gwh"] / row["hydro_total_gwh"]
        row["pumped_share_pct"] = 100 * row["pumped_gwh"] / row["hydro_total_gwh"]
        row["renewable_share_of_load_pct"] = float(
            pd.to_numeric(df["renewable_share_of_load"], errors="coerce").mean()
        ) if "renewable_share_of_load" in df else np.nan
        row["hydro_capacity_mw"] = installed_power(country, "hydro", year)
        # full-load hours for non-storage hydro (run-of-river + reservoir)
        row["hydro_flh"] = ((row["run_of_river_gwh"] + row["reservoir_gwh"]) * 1000 / row["hydro_capacity_mw"]
                            if row.get("hydro_capacity_mw") else np.nan)
        per_year.append(row)

        # monthly split (int month keys avoid tz/Period conversion warnings)
        def by_month(s: pd.Series) -> pd.Series:
            return s.groupby(s.index.month).apply(lambda v: v.sum(skipna=True) * ih / 1000.0)

        m = by_month(total_hydro)
        mr, ms, mp = (by_month(df[c]) for c in
                      ["hydro_run_of_river", "hydro_water_reservoir", "hydro_pumped_storage"])
        for mon, v in m.items():
            monthly.append({
                "country": country.upper(), "year": year, "month": f"{year}-{int(mon):02d}",
                "hydro_gwh": float(v),
                "run_of_river_gwh": float(mr.get(mon, np.nan)),
                "reservoir_gwh": float(ms.get(mon, np.nan)),
                "pumped_gwh": float(mp.get(mon, np.nan)),
            })

        # hourly profile (local hour of day)
        for col, label in [("hydro_pumped_storage", "pumped_storage_gen"),
                           ("hydro_run_of_river", "run_of_river"),
                           ("hydro_water_reservoir", "reservoir")]:
            if col not in df:
                continue
            prof = df[col].groupby(df.index.hour).mean()
            for h, v in prof.items():
                profiles.append({"country": country.upper(), "year": year,
                                 "series": label, "hour": int(h), "mean_mw": float(v)})

    return pd.DataFrame(per_year), pd.DataFrame(monthly), pd.DataFrame(profiles)


# ------------------------------------------------------------ pumped storage --

def pumped_storage_table(country: str) -> pd.DataFrame:
    rows = []
    for year in range(BASE_FIRST, CURRENT_YEAR + 1):
        got = load("production", country, year)
        if got is None:
            continue
        df, ih = got
        df = to_numeric(df)
        df = df[(df.index >= f"{year}-06-01") & (df.index < f"{year}-09-01")]
        if "hydro_pumped_storage" not in df:
            continue

        ps = df["hydro_pumped_storage"]
        pump_col = "hydro_pumped_storage_consumption"
        if pump_col in df:
            # Germany: separate consumption series, reported as negative MW
            gen = ps.clip(lower=0)
            pump = (-df[pump_col]).clip(lower=0)
            reporting = "Erzeugung und Pumpstrom getrennt ausgewiesen"
        else:
            # Switzerland: single series; pumping appears as negative values
            gen = ps.clip(lower=0)
            pump = (-ps.clip(upper=0))
            reporting = "Nettoreihe (Pumpen als negative Werte)"
            if float(pump.sum(skipna=True)) == 0:
                reporting = "nur Erzeugung (kein Pumpbetrieb in der Reihe)"

        gen_gwh = gwh(gen, ih)
        pump_gwh = gwh(pump, ih)
        net_gwh = gen_gwh - pump_gwh
        cap = installed_power(country, "hydro_pumped_storage", year)

        rec = {
            "country": country.upper(),
            "year": year,
            "reporting": reporting,
            "ps_capacity_mw": cap,
            "ps_generation_gwh": gen_gwh,
            "ps_pumping_gwh": pump_gwh,
            "ps_net_gwh": net_gwh,
            "losses_gwh": pump_gwh - gen_gwh if pump_gwh else np.nan,
            "round_trip_eff_pct": 100 * gen_gwh / pump_gwh if pump_gwh else np.nan,
            "ps_gen_full_load_hours": gen_gwh * 1000 / cap if cap else np.nan,
            "ps_pump_full_load_hours": pump_gwh * 1000 / cap if cap else np.nan,
            "ps_peak_generation_mw": float(gen.max(skipna=True)),
            "ps_max_pumping_mw": float(pump.max(skipna=True)),
            "intervals_with_generation_pct": 100 * float((gen > 0).mean()),
            "intervals_with_pumping_pct": 100 * float((pump > 0).mean()),
            "cycles_equivalent": (gen_gwh * 1000 / cap) / 8 if cap else np.nan,  # 8 h discharge assumption
            "pumping_data_suspect": bool(pump_gwh and gen_gwh / pump_gwh > 1.05),
        }

        # economics: day-ahead price in the generation vs pumping hours
        price = price_frame(country, year)
        if price is not None:
            p = price.reindex(df.index, method="nearest")
            gen_mean_px = float((gen * p).sum(skipna=True) / gen.sum(skipna=True)) if gen.sum() else np.nan
            pump_mean_px = float((pump * p).sum(skipna=True) / pump.sum(skipna=True)) if pump.sum() else np.nan
            rec.update({
                "price_mean_eur_mwh": float(p.mean(skipna=True)),
                "price_min_eur_mwh": float(p.min(skipna=True)),
                "price_max_eur_mwh": float(p.max(skipna=True)),
                "price_p99_eur_mwh": float(p.quantile(0.99)),
                "price_neg_hours_pct": 100 * float((p < 0).mean()),
                "gen_hours_mean_price": gen_mean_px,
                "pump_hours_mean_price": pump_mean_px,
                "capture_spread_eur_mwh": gen_mean_px - pump_mean_px if pump_gwh else np.nan,
                "da_arbitrage_value_meur": (gen_gwh * gen_mean_px - pump_gwh * pump_mean_px) / 1000.0
                if pump_gwh else np.nan,
            })

        # hourly shape
        rec["gen_hours_in_peak_8_20_pct"] = 100 * float(
            gen.between_time("08:00", "19:59").sum(skipna=True) / gen.sum(skipna=True)
        ) if gen.sum() else np.nan
        rec["pump_hours_in_night_22_6_pct"] = 100 * float(
            pump.between_time("22:00", "05:59").sum(skipna=True) / pump.sum(skipna=True)
        ) if pump.sum() else np.nan
        # regime-shift indicators: midday (solar-trough) pumping vs evening generation
        rec["pump_share_midday_10_15_pct"] = 100 * float(
            pump.between_time("10:00", "15:59").sum(skipna=True) / pump.sum(skipna=True)
        ) if pump.sum() else np.nan
        rec["gen_share_evening_17_23_pct"] = 100 * float(
            gen.between_time("17:00", "23:59").sum(skipna=True) / gen.sum(skipna=True)
        ) if gen.sum() else np.nan
        rec["gen_share_night_0_5_pct"] = 100 * float(
            gen.between_time("00:00", "05:59").sum(skipna=True) / gen.sum(skipna=True)
        ) if gen.sum() else np.nan
        # daily cycling behaviour: how many days run both modes
        day = gen.index.normalize()
        both = (gen.groupby(day).sum() > 0) & (pump.groupby(day).sum() > 0)
        rec["days_with_both_modes_pct"] = 100 * float(both.mean())
        rec["max_daily_generation_gwh"] = float(gen.groupby(day).sum().max() * ih / 1000.0)
        px_all = price
        if px_all is not None:
            px = px_all.reindex(df.index, method="nearest")
            rec["gen_at_negative_price_gwh"] = float(
                gen.where(px < 0, 0).sum(skipna=True) * ih / 1000.0)
            rec["pump_at_negative_price_gwh"] = float(
                pump.where(px < 0, 0).sum(skipna=True) * ih / 1000.0)
            rec["gen_share_of_price_top_decile_pct"] = 100 * float(
                gen.where(px >= px.quantile(0.9), 0).sum(skipna=True) / gen.sum(skipna=True)
            ) if gen.sum() else np.nan
            rec["pump_share_of_price_bottom_decile_pct"] = 100 * float(
                pump.where(px <= px.quantile(0.1), 0).sum(skipna=True) / pump.sum(skipna=True)
            ) if pump.sum() else np.nan

        # monthly generation split, to show seasonal behaviour
        pm = gen.groupby(gen.index.month).sum() * ih / 1000.0
        for mon, v in pm.items():
            rec[f"gen_{MONTH_ABBR[int(mon)]}_gwh"] = float(v)

        rows.append(rec)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------- prices ---

def price_frame(country: str, year: int) -> pd.Series | None:
    got = load("price", country, year)
    if got is None:
        return None
    df, _ = got
    return df["day_ahead_price"].astype(float)


def price_table() -> pd.DataFrame:
    rows = []
    for country in COUNTRIES:
        for year in range(BASE_FIRST, CURRENT_YEAR + 1):
            p = price_frame(country, year)
            if p is None:
                continue
            p = p[(p.index >= f"{year}-06-01") & (p.index < f"{year}-09-01")]
            daily = p.resample("1D").mean()
            spread = p.resample("1D").agg(lambda s: float(s.max() - s.min()))
            rows.append({
                "country": country.upper(), "year": year,
                "price_mean": float(p.mean()), "price_median": float(p.median()),
                "price_min": float(p.min()), "price_max": float(p.max()),
                "price_p05": float(p.quantile(0.05)), "price_p95": float(p.quantile(0.95)),
                "neg_hours_pct": 100 * float((p < 0).mean()),
                "daily_spread_mean": float(spread.mean()),
                "daily_spread_p90": float(spread.quantile(0.9)),
                "price_std_of_mean": float(daily.std() / daily.mean()),
            })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------- capacity ---

_capacity_cache: dict[str, pd.DataFrame] = {}


def installed_power(country: str, series: str, year: int) -> float | None:
    """Installed MW. Rows are labelled with the END of the stated year."""
    path = RAW / f"capacity_{country}_2000.json.gz"
    if not path.exists():
        return None
    if country not in _capacity_cache:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            payload = json.load(fh)
        df = pd.DataFrame([r["values"] for r in payload["data"]],
                          index=pd.to_datetime([r["timestamp"] for r in payload["data"]]))
        df = df.apply(pd.to_numeric, errors="coerce")
        df["year"] = df.index.year
        _capacity_cache[country] = df
    df = _capacity_cache[country]
    if series not in df:
        return None
    for y in [year] + list(range(year - 1, year - 6, -1)):   # fall back to the last known year
        sub = df.loc[df["year"] == y, series].dropna()
        if not sub.empty:
            return float(sub.iloc[0]) * 1000.0  # GW -> MW
    return None


# --------------------------------------------------------------------- main ---

def daily_series(country: str) -> pd.DataFrame:
    """Daily GWh per hydro category + day-ahead price stats, Jun 1 - Aug 31."""
    frames = []
    for year in range(BASE_FIRST, CURRENT_YEAR + 1):
        got = load("production", country, year)
        if got is None:
            continue
        df, ih = got
        df = to_numeric(df)
        df = df[(df.index >= f"{year}-06-01") & (df.index < f"{year}-09-01")]
        if df.empty:
            continue
        # one row per calendar day: index comes from a daily resample, not from the
        # raw (15-min / hourly) timestamps normalised to midnight, which would repeat
        # every day 96x once the aggregated columns align onto it.
        anchor = "hydro_run_of_river" if "hydro_run_of_river" in df else "load"
        d = pd.DataFrame(index=df[anchor].resample("1D").sum().index)
        for col, name in [("hydro_run_of_river", "ror"), ("hydro_water_reservoir", "res"),
                          ("hydro_pumped_storage", "ps_gen")]:
            if col in df:
                d[name] = df[col].clip(lower=0).resample("1D").sum() * ih / 1000.0
        if "hydro_pumped_storage_consumption" in df:
            d["ps_pump"] = (-df["hydro_pumped_storage_consumption"]).clip(lower=0).resample("1D").sum() * ih / 1000.0
        elif "hydro_pumped_storage" in df:
            # CH: if the single series is reported net, pumping shows up as negatives
            d["ps_pump"] = (-df["hydro_pumped_storage"].clip(upper=0)).resample("1D").sum() * ih / 1000.0
        if "load" in df:
            d["load"] = df["load"].resample("1D").sum() * ih / 1000.0
        if "solar" in df:
            d["solar"] = df["solar"].resample("1D").sum() * ih / 1000.0
        d["wind"] = wind_total(df).resample("1D").sum() * ih / 1000.0
        d["hydro"] = d[["ror", "res", "ps_gen"]].sum(axis=1, min_count=1)
        px = price_frame(country, year)
        if px is not None:
            px = px[(px.index >= f"{year}-06-01") & (px.index < f"{year}-09-01")]
            p = px.resample("1D").agg(mean="mean", mx="max", mn="min")
            # match on calendar date, so a tz difference between price and production
            # stamps cannot silently null out the whole column
            pm = {k.normalize().date(): v for k, v in p["mean"].items()}
            ps_ = {k.normalize().date(): v for k, v in (p["mx"] - p["mn"]).items()}
            days = list(d.index.normalize().date)
            d["price_mean"] = [pm.get(x) for x in days]
            d["price_spread"] = [ps_.get(x) for x in days]
        d["year"] = d.index.year
        d["doy"] = d.index.dayofyear
        frames.append(d)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames)
    out.index.name = "date"
    out = out.reset_index()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out


def price_hourly_profile(country: str) -> pd.DataFrame:
    rows = []
    for year in range(BASE_FIRST, CURRENT_YEAR + 1):
        px = price_frame(country, year)
        if px is None:
            continue
        px = px[(px.index >= f"{year}-06-01") & (px.index < f"{year}-09-01")]
        for h, v in px.groupby(px.index.hour).mean().items():
            rows.append({"country": country.upper(), "year": year, "hour": int(h), "price": float(v)})
    return pd.DataFrame(rows)


def ps_hourly_profile(country: str) -> pd.DataFrame:
    """Mean MW by local hour for PS generation and pumping."""
    rows = []
    for year in range(BASE_FIRST, CURRENT_YEAR + 1):
        got = load("production", country, year)
        if got is None:
            continue
        df, _ = got
        df = to_numeric(df)
        df = df[(df.index >= f"{year}-06-01") & (df.index < f"{year}-09-01")]
        gen = df["hydro_pumped_storage"].clip(lower=0)
        rows.append({
            "country": country.upper(), "year": year, "kind": "generation",
            **{f"h{h:02d}": float(gen.groupby(gen.index.hour).mean().get(h, np.nan)) for h in range(24)},
        })
        if "hydro_pumped_storage_consumption" in df:
            pump = (-df["hydro_pumped_storage_consumption"]).clip(lower=0)
            rows.append({
                "country": country.upper(), "year": year, "kind": "pumping",
                **{f"h{h:02d}": float(pump.groupby(pump.index.hour).mean().get(h, np.nan)) for h in range(24)},
            })
    return pd.DataFrame(rows)


def flows_table() -> pd.DataFrame:
    """Net cross-border position per summer, GWh (positive = net import)."""
    rows = []
    for country in COUNTRIES:
        for year in range(BASE_FIRST, CURRENT_YEAR + 1):
            got = load("cbpf", country, year)
            if got is None:
                continue
            df, ih = got
            df = to_numeric(df)
            df = df[(df.index >= f"{year}-06-01") & (df.index < f"{year}-09-01")]
            if "sum" not in df:
                continue
            rec = {"country": country.upper(), "year": year,
                   "net_import_gwh": gwh_from_gw(df["sum"], ih),
                   "import_gwh": gwh_from_gw(df["sum"].clip(lower=0), ih),
                   "export_gwh": gwh_from_gw(-df["sum"].clip(upper=0), ih)}
            for col in df.columns:
                if col != "sum":
                    rec[f"net_to_{col}_gwh"] = -gwh_from_gw(df[col], ih)  # positive = export to that partner
            rows.append(rec)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    loads = []
    for country in COUNTRIES_UPPER:
        hy = pd.read_csv(OUT / f"hydro_summer_{country.lower()}.csv")[["year", "load_gwh"]]
        hy["country"] = country
        loads.append(hy)
    df = df.merge(pd.concat(loads), on=["country", "year"], how="left")
    df["net_as_pct_of_load"] = 100 * df["net_import_gwh"] / df["load_gwh"]
    return df


def main() -> None:
    OUT.mkdir(exist_ok=True)
    summary: dict = {"generated_from": "energy-charts.info API v2", "summer_window": "06-01..08-31"}
    profiles = []

    for country in COUNTRIES:
        yearly, monthly, prof = hydro_table(country)
        yearly.to_csv(OUT / f"hydro_summer_{country}.csv", index=False)
        monthly.to_csv(OUT / f"hydro_monthly_{country}.csv", index=False)
        profiles.append(prof)
        summary[f"{country}_hydro"] = yearly.to_dict(orient="records")

        ps = pumped_storage_table(country)
        ps.to_csv(OUT / f"ps_summer_{country}.csv", index=False)
        summary[f"{country}_ps"] = ps.to_dict(orient="records")
        summary[f"{country}_monthly"] = monthly.to_dict(orient="records")
        print(f"[{country}] hydro rows={len(yearly)} ps rows={len(ps)}")

    pd.concat(profiles, ignore_index=True).to_csv(OUT / "hourly_profiles.csv", index=False)
    prices = price_table()
    prices.to_csv(OUT / "price_summer.csv", index=False)
    summary["prices"] = prices.to_dict(orient="records")

    for country in COUNTRIES:
        daily = daily_series(country)
        if not daily.empty:
            daily.to_csv(OUT / f"daily_{country}.csv", index=False)
            summary[f"{country}_daily"] = daily.to_dict(orient="records")
        pp = price_hourly_profile(country)
        pp.to_csv(OUT / f"price_hourly_{country}.csv", index=False)
        summary[f"{country}_price_hourly"] = pp.to_dict(orient="records")
        sp = ps_hourly_profile(country)
        sp.to_csv(OUT / f"ps_hourly_{country}.csv", index=False)
        summary[f"{country}_ps_hourly"] = sp.to_dict(orient="records")

    flows = flows_table()
    if not flows.empty:
        flows.to_csv(OUT / "flows_summer.csv", index=False)
    summary["flows"] = flows.to_dict(orient="records") if not flows.empty else []

    with open(OUT / "summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1, default=float)
    print("wrote", OUT / "summary.json")


if __name__ == "__main__":
    main()
