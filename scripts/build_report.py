#!/usr/bin/env python3
"""Build a self-contained HTML report from output/summary.json (Chart.js via CDN)."""

from __future__ import annotations

import json
from pathlib import Path

from findings import build as build_narrative

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
COUNTRIES = ("de", "at", "ch")   # DACH, in report order
CURRENT = 2026
BASE = list(range(2017, 2026))  # reference years, "previous years" excluding current


def rnd(x, n=1):
    try:
        if x is None:
            return None
        return round(float(x), n)
    except (TypeError, ValueError):
        return None


def by_year(records, year):
    for r in records:
        if int(r["year"]) == year:
            return r
    return {}


def mean_of(records, key, years):
    vals = [r.get(key) for r in records if int(r["year"]) in years and r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def series(records, key, years=None):
    years = years or list(range(2017, CURRENT + 1))
    out = []
    for y in years:
        r = by_year(records, y)
        out.append(rnd(r.get(key), 1))
    return out


def main() -> None:
    summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))

    data: dict = {"years": list(range(2017, CURRENT + 1))}
    findings: dict = {}

    for c in COUNTRIES:
        hy = summary[f"{c}_hydro"]
        ps = summary[f"{c}_ps"]
        cur = by_year(hy, CURRENT)
        prev = mean_of(hy, "hydro_total_gwh", BASE)
        prev_rr = mean_of(hy, "run_of_river_gwh", BASE)
        prev_res = mean_of(hy, "reservoir_gwh", BASE)
        prev_ps = mean_of(hy, "pumped_gwh", BASE)
        prev_nat = mean_of(hy, "natural_gwh", BASE)
        findings[c] = {
            "hydro_total": rnd(cur.get("hydro_total_gwh")),
            "hydro_mean_prev": rnd(prev),
            "natural": rnd(cur.get("natural_gwh")),
            "natural_mean_prev": rnd(prev_nat),
            "nat_delta_pct": rnd(100 * (cur["natural_gwh"] / prev_nat - 1)) if prev_nat and cur.get("natural_gwh") else None,
            "nat_rank": None,
            "delta_pct": rnd(100 * (cur["hydro_total_gwh"] / prev - 1)) if prev and cur.get("hydro_total_gwh") else None,
            "ror_delta_pct": rnd(100 * (cur["run_of_river_gwh"] / prev_rr - 1)) if prev_rr and cur.get("run_of_river_gwh") else None,
            "res_delta_pct": rnd(100 * (cur["reservoir_gwh"] / prev_res - 1)) if prev_res and cur.get("reservoir_gwh") else None,
            "ps_delta_pct": rnd(100 * (cur["pumped_gwh"] / prev_ps - 1)) if prev_ps and cur.get("pumped_gwh") else None,
            "share_of_load": rnd(cur.get("hydro_share_of_load_pct"), 2),
            "share_of_load_prev": rnd(mean_of(hy, "hydro_share_of_load_pct", BASE), 2),
            "rank": None,
        }
        totals = sorted([r["hydro_total_gwh"] for r in hy], reverse=True)
        if cur.get("hydro_total_gwh") is not None:
            findings[c]["rank"] = totals.index(cur["hydro_total_gwh"]) + 1
        nats = sorted([r["natural_gwh"] for r in hy], reverse=True)
        if cur.get("natural_gwh") is not None:
            findings[c]["nat_rank"] = nats.index(cur["natural_gwh"]) + 1
        data[c] = {
            "hydro": {k: series(hy, k) for k in
                      ["run_of_river_gwh", "reservoir_gwh", "pumped_gwh", "hydro_total_gwh",
                       "natural_gwh",
                       "hydro_share_of_load_pct", "load_gwh", "renewable_share_of_load_pct"]},
            "ps": {k: series(ps, k) for k in
                   ["ps_generation_gwh", "ps_pumping_gwh", "ps_net_gwh", "round_trip_eff_pct",
                    "ps_gen_full_load_hours", "capture_spread_eur_mwh", "da_arbitrage_value_meur",
                    "price_mean_eur_mwh", "price_max_eur_mwh", "price_neg_hours_pct",
                    "ps_peak_generation_mw", "gen_hours_in_peak_8_20_pct", "pump_hours_in_night_22_6_pct",
                    "pump_share_midday_10_15_pct", "gen_share_evening_17_23_pct", "gen_share_night_0_5_pct",
                    "days_with_both_modes_pct", "max_daily_generation_gwh",
                    "gen_at_negative_price_gwh", "pump_at_negative_price_gwh",
                    "gen_share_of_price_top_decile_pct", "pump_share_of_price_bottom_decile_pct"]
                   if any(r.get(k) is not None for r in ps)},
            "ps_reporting": [r.get("reporting") for r in ps],
            "monthly": summary[f"{c}_monthly"],
        }
        # monthly pivot: month label -> list per year
        monthly = {}
        for rec in summary.get(f"{c}_monthly", []) or []:
            monthly.setdefault(rec["month"][-2:], {})[str(rec["year"])] = rnd(rec["hydro_gwh"])
        data[c]["monthly_by_month"] = monthly

        daily = summary.get(f"{c}_daily", [])
        piv: dict = {}
        for rec in daily:
            d = rec["date"][:10]
            y, md = d[:4], d[5:]
            piv.setdefault(md, {})[y] = {k: rnd(rec.get(k), 2) for k in ("hydro", "ror", "res", "nat", "ps_gen", "ps_pump", "price_mean", "price_spread")}
        data[c]["daily"] = dict(sorted(piv.items()))

        prof = summary.get(f"{c}_ps_hourly", [])
        hp: dict = {}
        for rec in prof:
            key = f"{rec['country']}_{rec['kind']}_{rec['year']}"
            hp[key] = [rec.get(f"h{h:02d}") for h in range(24)]
        data[c]["ps_hourly"] = hp
        data[c]["price_hourly"] = {
            str(r["year"]): [rnd(r["price"], 2) for r in sorted(
                [x for x in summary.get(f"{c}_price_hourly", []) if x["year"] == r["year"]],
                key=lambda x: x["hour"])]
            for r in summary.get(f"{c}_price_hourly", [])
        }

    data["prices"] = {k: series(summary["prices"], k) for k in
                      ["price_mean", "price_median", "price_max", "daily_spread_mean", "neg_hours_pct"]}
    data["price_rows"] = summary["prices"]
    data["findings"] = findings
    data["hydro_rows"] = {c: summary[f"{c}_hydro"] for c in COUNTRIES}
    data["ps_rows"] = {c: summary[f"{c}_ps"] for c in COUNTRIES}
    data["flow_rows"] = summary.get("flows", [])
    flows = summary.get("flows", [])
    data["flows"] = {
        c: {k: [next((r.get(k) for r in flows if r["country"] == C and r["year"] == y), None)
                for y in data["years"]]
            for k in ("net_import_gwh", "net_as_pct_of_load", "import_gwh", "export_gwh")}
        for c, C in zip(COUNTRIES, (x.upper() for x in COUNTRIES))}
    data["narrative"] = build_narrative(summary)

    (OUT / "report_data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    (OUT / "report.html").write_text(html, encoding="utf-8")
    print("wrote", OUT / "report.html")
    # GitHub Pages copy: the report is self-contained, so mirror it to
    # docs/index.html on every rebuild and a redeploy can never serve a stale page.
    docs = ROOT / "docs"
    if docs.is_dir():
        (docs / "index.html").write_text(html, encoding="utf-8")
        print("wrote", docs / "index.html")
    for c in COUNTRIES:
        print(c.upper(), json.dumps(findings[c], ensure_ascii=False))


TEMPLATE = r"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wasserkraft und Pumpspeicher im DACH-Raum: Deutschland, Österreich, Schweiz – Sommer 2026 vs. 2017–2025</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#f5f5f5;--card:#ffffff;--ink:#212529;--mut:#6c757d;--brand:#009374;--de:#1f5fbf;--at:#8e44ad;--ch:#e8710a;--line:#dee2e6;--shadow:0 1px 2px rgba(0,0,0,.05)}
*{box-sizing:border-box}
body{margin:0;background:var(--card);color:#4e4e4e;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
header{padding:22px 32px 14px;background:var(--card);border-bottom:3px solid var(--brand)}
h1{margin:0 0 6px;font-size:24px;font-weight:500;color:#454545}
h2{margin:34px 0 4px;font-size:19px;font-weight:500;border-left:4px solid var(--brand);padding-left:10px}
h3{margin:0 0 10px;font-size:14px;font-weight:600;color:var(--ink)}
p.sub{color:var(--mut);margin:4px 0 0;font-size:13px}
main{padding:0 32px 60px;max-width:1240px;margin:0 auto}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px;margin-top:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:3.5px;padding:14px 16px 10px;box-shadow:var(--shadow)}
.grid>.card{height:340px;display:flex;flex-direction:column}
.cbody{position:relative;flex:1;min-height:0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:18px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-top:3px solid var(--brand);border-radius:3.5px;padding:12px 14px;box-shadow:var(--shadow)}
.kpi .v{font-size:23px;font-weight:600}
.kpi .l{color:var(--mut);font-size:11.5px;text-transform:uppercase;letter-spacing:.04em}
.kpi .d{font-size:13px;margin-top:4px}
.up{color:#00663c}.down{color:#b1002d}
.cbody>canvas{position:absolute;left:0;top:0;width:100%!important;height:100%!important}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin-top:10px}
th,td{padding:5px 7px;text-align:right;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
th{color:var(--mut);font-weight:600;position:sticky;top:0;background:var(--card)}
tr.cur td{background:rgba(0,147,116,.09);font-weight:600}
.scroll{overflow:auto;max-height:420px;border:1px solid var(--line);border-radius:3.5px;background:var(--card)}
.note{background:#f0faf7;border:1px solid #bfe5da;border-left:4px solid var(--brand);border-radius:3.5px;padding:12px 14px;margin:14px 0;font-size:13px;color:#24423a}
ul{margin:8px 0 0;padding-left:20px}
li{margin:4px 0}
.tag{display:inline-block;padding:1px 7px;border-radius:10px;font-size:11.5px;background:#e9f7f3;color:#00664f;border:1px solid #bfe5da;margin-right:6px;font-family:"Lucida Sans Unicode","Lucida Grande",sans-serif}
</style></head><body>
<header>
<h1>Wasserkraft und Pumpspeicherbetrieb im DACH-Raum – Deutschland, Österreich, Schweiz</h1>
<p class="sub">Alpenraum / DACH · Sommersaison 2026 (1. Juni – 31. August) im Vergleich zu 2017–2025 · Dürre-Indikator: <b>natürliche Wasserkraft (Laufwasser + Speicherwasser)</b>, Pumpspeicher getrennt · Quelle: <b>energy-charts.info API v2</b> (Fraunhofer ISE, CC BY 4.0) · Einheiten: GWh Erzeugung, Preise: Day-ahead in EUR/MWh</p>
</header>
<main>
<div class="kpis" id="kpis"></div>
<div class="note" id="caveats"></div>

<h2>1. Natürliche Wasserkraft – der eigentliche Dürre-Indikator</h2>
<div class="note">Pumpspeicherkraftwerke sind kein vom Zufluss abhängiger Erzeuger: Sie entnehmen dem Netz Strom und speisen ihn wirkungsgradbedingt wieder ein. Für das <b>Trockenheitssignal</b> zählt daher die <b>natürliche Wasserkraft = Laufwasser + Speicherwasser</b>; die Pumpspeicher werden in Abschnitt&nbsp;3 getrennt behandelt. <span class="tag">Laufwasser</span> <span class="tag">Speicherwasser</span> = natürlich &nbsp;·&nbsp; <span class="tag">Pumpspeicher</span> = Speicher.</div>
<div class="grid">
  <div class="card"><h3>Natürliche Wasserkraft (Laufwasser + Speicherwasser) je Sommer, GWh</h3><div class="cbody"><canvas id="nat_yearly"></canvas></div></div>
  <div class="card"><h3>Was die PSW-Menge verdeckt: Abweichung natürlich vs. gesamt, %</h3><div class="cbody"><canvas id="nat_mask"></canvas></div></div>
  <div class="card"><h3>Anteil der natürlichen Wasserkraft am Verbrauch (Last), %</h3><div class="cbody"><canvas id="share"></canvas></div></div>
</div>
<div class="grid">
  <div class="card"><h3>Deutschland: Erzeugung nach Art, GWh (Summe Juni–August)</h3><div class="cbody"><canvas id="de_stack"></canvas></div></div>
  <div class="card"><h3>Österreich: Erzeugung nach Art, GWh (Summe Juni–August)</h3><div class="cbody"><canvas id="at_stack"></canvas></div></div>
  <div class="card"><h3>Schweiz: Erzeugung nach Art, GWh (Summe Juni–August)</h3><div class="cbody"><canvas id="ch_stack"></canvas></div></div>
</div>
<div class="grid">
  <div class="card"><h3>Abweichung Sommer 2026 vom Mittel 2017–2025 nach Sparte, %</h3><div class="cbody"><canvas id="delta"></canvas></div></div>
</div>

<h2>2. Monats- und Tagesverlauf</h2>
<div class="grid">
  <div class="card"><h3>Deutschland: natürliche Wasserkraft je Sommertag, GWh/Tag (7-Tage-Mittel)</h3><div class="cbody"><canvas id="de_daily"></canvas></div></div>
  <div class="card"><h3>Österreich: natürliche Wasserkraft je Sommertag, GWh/Tag (7-Tage-Mittel)</h3><div class="cbody"><canvas id="at_daily"></canvas></div></div>
  <div class="card"><h3>Schweiz: natürliche Wasserkraft je Sommertag, GWh/Tag (7-Tage-Mittel)</h3><div class="cbody"><canvas id="ch_daily"></canvas></div></div>
</div>
<div class="grid">
  <div class="card"><h3>Deutschland: Laufwasser vs. Speicherwasser vs. Pumpspeicher je Monat</h3><div class="cbody"><canvas id="de_split"></canvas></div></div>
  <div class="card"><h3>Österreich: Laufwasser vs. Speicherwasser vs. Pumpspeicher je Monat</h3><div class="cbody"><canvas id="at_split"></canvas></div></div>
  <div class="card"><h3>Schweiz: Laufwasser vs. Speicherwasser vs. Pumpspeicher je Monat</h3><div class="cbody"><canvas id="ch_split"></canvas></div></div>
</div>

<h2>3. Pumpspeicherkraftwerke (PSW)</h2>
<div class="grid">
  <div class="card"><h3>Deutschland: Erzeugung / Pumpstrom / Netto, GWh</h3><div class="cbody"><canvas id="de_ps"></canvas></div></div>
  <div class="card"><h3>Österreich: Erzeugung / Pumpstrom / Netto, GWh</h3><div class="cbody"><canvas id="at_ps"></canvas></div></div>
  <div class="card"><h3>Schweiz: PSW-Erzeugung und Anteil an der Wasserkraft, GWh / %</h3><div class="cbody"><canvas id="ch_ps"></canvas></div></div>
</div>
<div class="grid">
  <div class="card"><h3>Deutschland: mittleres Leistungsprofil nach Tagesstunde, MW</h3><div class="cbody"><canvas id="de_profile"></canvas></div></div>
  <div class="card"><h3>Deutschland: Day-ahead-Preis nach Stunden, EUR/MWh</h3><div class="cbody"><canvas id="de_price_profile"></canvas></div></div>
</div>
<div class="grid">
  <div class="card"><h3>Österreich: mittleres Leistungsprofil nach Tagesstunde, MW</h3><div class="cbody"><canvas id="at_profile"></canvas></div></div>
  <div class="card"><h3>Day-ahead-Preisprofile Sommer 2026: DE · AT · CH, EUR/MWh</h3><div class="cbody"><canvas id="dach_price"></canvas></div></div>
</div>
<div class="grid">
  <div class="card"><h3>Deutschland: Benutzungsstunden der PSW und Wirkungsgrad</h3><div class="cbody"><canvas id="de_flh"></canvas></div></div>
  <div class="card"><h3>Arbitrage-Ökonomie: Preisspread und theoretische DA-Marge</h3><div class="cbody"><canvas id="de_econ"></canvas></div></div>
</div>
<div class="grid">
  <div class="card"><h3>Wandel des PSW-Betriebsregimes (DE · AT · CH): Pumpanteil 10–16 Uhr, Erzeugungsanteil 17–24 Uhr</h3><div class="cbody"><canvas id="de_regime"></canvas></div></div>
  <div class="card"><h3>Preisprofil nach Stunden (Sommer 2026 vs. 2017–24) – Kontext des Wandels</h3><div class="cbody"><canvas id="de_price_yearly"></canvas></div></div>
</div>

<h2>4. Grenzüberschreitender Austausch (physikalische Flüsse)</h2>
<div class="grid">
  <div class="card"><h3>Nettoimport (+) / Nettoexport (−) im Sommer, GWh</h3><div class="cbody"><canvas id="flows"></canvas></div></div>
  <div class="card"><h3>Nettoimport in % des Verbrauchs</h3><div class="cbody"><canvas id="flows_pct"></canvas></div></div>
</div>
<div class="scroll" style="margin-top:12px"><table id="tbl_flow"></table></div>

<h2>5. Fazit</h2>
<div class="card" id="narrative"></div>

<h2>6. Tabellen</h2>
<h3>Wasserkraft nach Jahren</h3>
<div class="scroll"><table id="tbl_hydro"></table></div>
<h3>Pumpspeicher nach Jahren</h3>
<div class="scroll"><table id="tbl_ps"></table></div>
<h3>Day-ahead-Preise im Sommer</h3>
<div class="scroll"><table id="tbl_price"></table></div>
</main>
<script>
const D = __DATA__;
const Y = D.years, CUR = 2026, PREV = Y.filter(y=>y<CUR);
const C = {de:'#1f5fbf', at:'#8e44ad', ch:'#e8710a', ror:'#0000c8', res:'#afc8ff', ps:'#0096e1', pump:'#323296', netto:'#77a8a3', hydro:'#007d8c', price:'#e41a1c', load:'#323232', wind:'#c3d7b9', solar:'#ffcd64', nuclear:'#a0459a', renewal:'#fb8072', ink:'#212529', mut:'#6c757d', line:'#e6e6e6'};
Chart.defaults.color = '#6c757d'; Chart.defaults.borderColor = C.line;
Chart.defaults.font.family = '"Lucida Sans Unicode","Lucida Grande",sans-serif';
Chart.defaults.font.size = 11.5;
// energy-charts style: horizontal gridlines only (#e6e6e6), no vertical grid
Chart.defaults.scale.grid.display = true; Chart.defaults.scale.grid.color = '#e6e6e6';
Chart.defaults.scales.category.grid = {display:false};
Chart.defaults.plugins.legend.labels.boxWidth = 10; Chart.defaults.plugins.legend.labels.boxHeight = 10; Chart.defaults.plugins.legend.labels.pointStyle = 'rect';
Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(255,255,255,.95)'; Chart.defaults.plugins.tooltip.titleColor = '#212529';
Chart.defaults.plugins.tooltip.bodyColor = '#212529'; Chart.defaults.plugins.tooltip.borderColor = '#adb5bd'; Chart.defaults.plugins.tooltip.borderWidth = 1;
const fmt = (v,d=0)=>{
  if(v==null||v==='')return '–';
  if(typeof v==='number'){return Number.isFinite(v)? v.toLocaleString('de-DE',{minimumFractionDigits:d,maximumFractionDigits:d}):'–';}
  const n=Number(v);
  return Number.isFinite(n)&&v!==''? n.toLocaleString('de-DE',{minimumFractionDigits:d,maximumFractionDigits:d}): String(v);
};

function smooth(arr,w=7){const o=[];for(let i=0;i<arr.length;i++){let s=0,n=0;for(let k=-Math.floor(w/2);k<=Math.floor(w/2);k++){const j=i+k;if(j>=0&&j<arr.length&&arr[j]!=null){s+=arr[j];n++}}o.push(n?+(s/n).toFixed(3):null)}return o}

// ---- daily pivot: per year arrays aligned on month-day
function dailySeries(cc, key, years){
  const md = Object.keys(D[cc].daily);
  return years.map(y=>({label:String(y), data: md.map(k=>D[cc].daily[k][String(y)]?D[cc].daily[k][String(y)][key]:null)}));
}
function dailySmooth(cc,key,years,w=7){const P=['#0000c8','#0096e1','#e8710a','#a0459a','#007d8c'];return dailySeries(cc,key,years).map((s,i)=>({label:s.label,borderColor:P[i%P.length],backgroundColor:'transparent',borderWidth:s.label===String(CUR)?2.6:1.6,pointRadius:0,data:smooth(s.data,w)}))}
function dailyLabels(cc){return Object.keys(D[cc].daily).map(md=>md.replace('-','.'))}

function barStack(cc, id){
  const h=D[cc].hydro;
  new Chart(document.getElementById(id),{type:'bar',data:{labels:Y,datasets:[
    {label:'Run-of-River',data:h.run_of_river_gwh,backgroundColor:C.ror},
    {label:'Speicherwasser',data:h.reservoir_gwh,backgroundColor:C.res},
    {label:'Pumpspeicher',data:h.pumped_gwh,backgroundColor:C.ps}]},
   options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{x:{stacked:true,grid:{display:false}},y:{stacked:true,grid:{color:'#e6e6e6'},title:{display:true,text:'GWh'}}}}});
}
barStack('de','de_stack'); barStack('at','at_stack'); barStack('ch','ch_stack');

// ---- DACH natural/total/ps aggregates ----
const iCUR=Y.indexOf(CUR);
function dachAgg(key){return Y.map((_,i)=>[D.de.hydro[key][i],D.at.hydro[key][i],D.ch.hydro[key][i]].reduce((a,b)=>a+(b||0),0))}
function meanPrevA(a){const p=a.filter((_,i)=>i<iCUR);return p.reduce((x,y)=>x+y,0)/p.length}
function dachDelta(key){const a=dachAgg(key);return +(100*(a[iCUR]/meanPrevA(a)-1)).toFixed(1)}
const natY=dachAgg('natural_gwh');
const dDe=D.findings.de, dAt=D.findings.at, dCh=D.findings.ch;

// ---- Headline: natuerliche Wasserkraft je Jahr (2026 betont) ----
function natLine(cc,label,col){const arr=D[cc].hydro.natural_gwh;return{label,data:arr,borderColor:col,backgroundColor:'transparent',tension:.25,borderWidth:2,
  pointRadius:arr.map((_,i)=>i===iCUR?5:2),pointHoverRadius:6,pointBackgroundColor:arr.map((_,i)=>i===iCUR?col:'transparent'),pointBorderColor:col}}
new Chart(document.getElementById('nat_yearly'),{type:'line',data:{labels:Y,datasets:[
  natLine('de','DE natürlich',C.de),natLine('at','AT natürlich',C.at),natLine('ch','CH natürlich',C.ch),
  {label:'DACH (Summe)',data:natY,borderColor:C.hydro,borderDash:[6,3],backgroundColor:'transparent',tension:.25,borderWidth:1.6,pointRadius:0}]},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{x:{grid:{display:false}},y:{grid:{color:'#e6e6e6'},title:{display:true,text:'GWh (Laufwasser + Speicherwasser)'}}}}});

// ---- Was die PSW-Menge verdeckt: natuerlich vs. gesamt vs. PSW ----
new Chart(document.getElementById('nat_mask'),{type:'bar',data:{labels:['DE','AT','CH','DACH'],datasets:[
  {label:'Natürliche WK (o. PSW)',data:[dDe.nat_delta_pct,dAt.nat_delta_pct,dCh.nat_delta_pct,dachDelta('natural_gwh')],backgroundColor:C.hydro},
  {label:'Wasserkraft gesamt (m. PSW)',data:[dDe.delta_pct,dAt.delta_pct,dCh.delta_pct,dachDelta('hydro_total_gwh')],backgroundColor:'#9c9999'},
  {label:'Pumpspeicher',data:[dDe.ps_delta_pct,dAt.ps_delta_pct,dCh.ps_delta_pct,dachDelta('pumped_gwh')],backgroundColor:C.ps}]},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{x:{grid:{display:false}},y:{grid:{color:'#e6e6e6'},title:{display:true,text:'% ggü. Mittel 2017–2025'}}}}});

// ---- Natuerliche Wasserkraft als Anteil an der Last ----
function natShare(cc){const n=D[cc].hydro.natural_gwh,l=D[cc].hydro.load_gwh;return n.map((v,i)=>(v!=null&&l[i])?+(v/l[i]*100).toFixed(2):null)}
new Chart(document.getElementById('share'),{type:'line',data:{labels:Y,datasets:[
  {label:'DE',data:natShare('de'),borderColor:C.de,backgroundColor:'transparent',tension:.25},
  {label:'AT',data:natShare('at'),borderColor:C.at,backgroundColor:'transparent',tension:.25},
  {label:'CH',data:natShare('ch'),borderColor:C.ch,backgroundColor:'transparent',tension:.25}]},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{x:{grid:{display:false}},y:{grid:{color:'#e6e6e6'},title:{display:true,text:'% des Verbrauchs'}}}}});

new Chart(document.getElementById('delta'),{type:'bar',data:{labels:['Natürliche WK (o. PSW)','Wasserkraft gesamt','Laufwasser','Speicherwasser','Pumpspeicher'],datasets:[
  {label:'DE 2026 ggü. 2017–25',data:[dDe.nat_delta_pct,dDe.delta_pct,dDe.ror_delta_pct,dDe.res_delta_pct,dDe.ps_delta_pct],backgroundColor:C.de},
  {label:'AT 2026 ggü. 2017–25',data:[dAt.nat_delta_pct,dAt.delta_pct,dAt.ror_delta_pct,dAt.res_delta_pct,dAt.ps_delta_pct],backgroundColor:C.at},
  {label:'CH 2026 ggü. 2017–25',data:[dCh.nat_delta_pct,dCh.delta_pct,dCh.ror_delta_pct,dCh.res_delta_pct,dCh.ps_delta_pct],backgroundColor:C.ch}]},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{x:{grid:{display:false}},y:{grid:{color:'#e6e6e6'},title:{display:true,text:'% Abweichung'}}}}});

new Chart(document.getElementById('de_daily'),{type:'line',data:{labels:dailyLabels('de'),datasets:dailySmooth('de','nat',[2026,2025,2024,2023,2018])},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{x:{ticks:{maxTicksLimit:12,autoSkip:true},grid:{display:false}},y:{grid:{color:'#e6e6e6'},title:{display:true,text:'GWh/Tag (7-Tage-Mittel)'}}}}});
new Chart(document.getElementById('at_daily'),{type:'line',data:{labels:dailyLabels('at'),datasets:dailySmooth('at','nat',[2026,2025,2024,2023,2018])},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{x:{ticks:{maxTicksLimit:12,autoSkip:true},grid:{display:false}},y:{grid:{color:'#e6e6e6'},title:{display:true,text:'GWh/Tag (7-Tage-Mittel)'}}}}});
new Chart(document.getElementById('ch_daily'),{type:'line',data:{labels:dailyLabels('ch'),datasets:dailySmooth('ch','nat',[2026,2025,2024,2023,2018])},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{x:{ticks:{maxTicksLimit:12,autoSkip:true},grid:{display:false}},y:{grid:{color:'#e6e6e6'},title:{display:true,text:'GWh/Tag (7-Tage-Mittel)'}}}}});

function splitChart(cc,id){
  const months=['06','07','08'], lab=['Juni','Juli','August'];
  const cur=D[cc].monthly.filter(r=>r.year===CUR), prv=D[cc].monthly.filter(r=>r.year<CUR);
  const agg=(sel,key)=>{const v=prv.filter(r=>r.month.endsWith(sel)).map(r=>r[key]).filter(x=>x!=null);return v.length?v.reduce((a,b)=>a+b,0)/v.length:null};
  const g=(sel,key,src)=>src.filter(r=>r.month.endsWith(sel)).reduce((a,r)=>a+(r[key]||0),0);
  const ds=[];
  [['run_of_river_gwh','Laufwasser',C.ror],['reservoir_gwh','Speicherwasser',C.res],['pumped_gwh','Pumpspeicher',C.ps]].forEach(([k,l,col])=>{
    ds.push({type:'bar',label:l+' 2026',data:months.map(m=>g(m,k,cur)),backgroundColor:col});
    ds.push({type:'bar',label:l+' 2017–25 Ø',data:months.map(m=>agg(m,k)),backgroundColor:col+'66'});
  });
  new Chart(document.getElementById(id),{data:{labels:lab,datasets:ds},
    options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'GWh je Monat'}}}}});
}
splitChart('de','de_split'); splitChart('at','at_split'); splitChart('ch','ch_split');

new Chart(document.getElementById('de_ps'),{type:'bar',data:{labels:Y,datasets:[
  {label:'Erzeugung',data:D.de.ps.ps_generation_gwh,backgroundColor:C.ps},
  {label:'Pumpstrom (Verbrauch)',data:D.de.ps.ps_pumping_gwh,backgroundColor:C.pump},
  {label:'Netto',data:D.de.ps.ps_net_gwh,backgroundColor:C.netto}]},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'GWh'}}}}});

new Chart(document.getElementById('at_ps'),{type:'bar',data:{labels:Y,datasets:[
  {label:'Erzeugung',data:D.at.ps.ps_generation_gwh,backgroundColor:C.ps},
  {label:'Pumpstrom (Verbrauch)',data:D.at.ps.ps_pumping_gwh,backgroundColor:C.pump},
  {label:'Netto',data:D.at.ps.ps_net_gwh,backgroundColor:C.netto}]},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'GWh'}}}}});

new Chart(document.getElementById('ch_ps'),{type:'bar',data:{labels:Y,datasets:[
  {type:'bar',label:'PSW-Erzeugung, GWh',data:D.ch.hydro.pumped_gwh,backgroundColor:C.ps,yAxisID:'y'},
  {type:'line',label:'Anteil an Wasserkraft, %',data:D.ch.hydro.hydro_total_gwh.map((v,i)=>v&&D.ch.hydro.pumped_gwh[i]!=null?+(D.ch.hydro.pumped_gwh[i]/v*100).toFixed(1):null),borderColor:C.de,backgroundColor:'transparent',yAxisID:'y1',tension:.2}]},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'GWh'}},y1:{position:'right',grid:{drawOnChartArea:false},title:{display:true,text:'%'}}}}});

// profiles
const hours=[...Array(24).keys()];
const deGenCur=D.de.ps_hourly['DE_generation_2026']||[], dePumpCur=D.de.ps_hourly['DE_pumping_2026']||[];
function meanPrev(cc,kind){const CC=cc.toUpperCase();const arrs=Object.keys(D[cc].ps_hourly).filter(k=>k.startsWith(CC+'_'+kind)&&!k.endsWith('2026')).map(k=>D[cc].ps_hourly[k]);
  if(!arrs.length)return null;return hours.map(h=>{const v=arrs.map(a=>a[h]).filter(x=>x!=null);return v.length?+(v.reduce((a,b)=>a+b,0)/v.length).toFixed(1):null})}
new Chart(document.getElementById('de_profile'),{type:'line',data:{labels:hours,datasets:[
  {label:'Erzeugung 2026',data:deGenCur,borderColor:C.ps,backgroundColor:'transparent',tension:.3},
  {label:'Erzeugung 2017–25 (Ø)',data:meanPrev('de','generation'),borderColor:C.ps+'88',borderDash:[5,4],backgroundColor:'transparent',tension:.3},
  {label:'Pumpstrom 2026',data:dePumpCur,borderColor:C.pump,backgroundColor:'transparent',tension:.3},
  {label:'Pumpstrom 2017–25 (Ø)',data:meanPrev('de','pumping'),borderColor:C.pump+'88',borderDash:[5,4],backgroundColor:'transparent',tension:.3}]},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{x:{grid:{display:false},title:{display:true,text:'Tagesstunde (Ortszeit)'}},y:{grid:{color:'#e6e6e6'},title:{display:true,text:'mittlere Leistung, MW'}}}}});

const atGenCur=D.at.ps_hourly['AT_generation_2026']||[], atPumpCur=D.at.ps_hourly['AT_pumping_2026']||[];
new Chart(document.getElementById('at_profile'),{type:'line',data:{labels:hours,datasets:[
  {label:'Erzeugung 2026',data:atGenCur,borderColor:C.ps,backgroundColor:'transparent',tension:.3},
  {label:'Erzeugung 2017–25 (Ø)',data:meanPrev('at','generation'),borderColor:C.ps+'88',borderDash:[5,4],backgroundColor:'transparent',tension:.3},
  {label:'Pumpstrom 2026',data:atPumpCur,borderColor:C.pump,backgroundColor:'transparent',tension:.3},
  {label:'Pumpstrom 2017–25 (Ø)',data:meanPrev('at','pumping'),borderColor:C.pump+'88',borderDash:[5,4],backgroundColor:'transparent',tension:.3}]},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{x:{grid:{display:false},title:{display:true,text:'Tagesstunde (Ortszeit)'}},y:{grid:{color:'#e6e6e6'},title:{display:true,text:'mittlere Leistung, MW'}}}}});

new Chart(document.getElementById('dach_price'),{type:'line',data:{labels:hours,datasets:[
  {label:'DE-LU 2026',data:D.de.price_hourly['2026'],borderColor:C.de,backgroundColor:'transparent',tension:.3},
  {label:'AT 2026',data:D.at.price_hourly['2026'],borderColor:C.at,backgroundColor:'transparent',tension:.3},
  {label:'CH 2026',data:D.ch.price_hourly['2026'],borderColor:C.ch,backgroundColor:'transparent',tension:.3}]},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{x:{grid:{display:false},title:{display:true,text:'Tagesstunde (Ortszeit)'}},y:{grid:{color:'#e6e6e6'},title:{display:true,text:'EUR/MWh'}}}}});

new Chart(document.getElementById('de_price_profile'),{type:'line',data:{labels:hours,datasets:[
  {label:'2026',data:D.de.price_hourly['2026'],borderColor:C.de,backgroundColor:'transparent',tension:.3},
  {label:'2025',data:D.de.price_hourly['2025'],borderColor:C.ch,backgroundColor:'transparent',tension:.3},
  {label:'2017–24 Ø',data:(()=>{const ys=Object.keys(D.de.price_hourly).filter(y=>+y<2025);return hours.map(h=>{const v=ys.map(y=>D.de.price_hourly[y][h]).filter(x=>x!=null);return v.length?+(v.reduce((a,b)=>a+b)/v.length).toFixed(1):null})})(),borderColor:'#6c757d',borderDash:[5,4],backgroundColor:'transparent',tension:.3}]},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{x:{grid:{display:false},title:{display:true,text:'Tagesstunde'}},y:{grid:{color:'#e6e6e6'},title:{display:true,text:'EUR/MWh'}}}}});

new Chart(document.getElementById('de_flh'),{type:'bar',data:{labels:Y,datasets:[
  {label:'Benutzungsstunden',data:D.de.ps.ps_gen_full_load_hours,backgroundColor:C.de,yAxisID:'y'},
  {label:'Kreislaufwirkungsgrad, %',data:D.de.ps.round_trip_eff_pct,type:'line',borderColor:C.ps,backgroundColor:'transparent',yAxisID:'y1',tension:.2}]},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'Benutzungsstunden (h)'}},y1:{position:'right',grid:{drawOnChartArea:false},title:{display:true,text:'%'}}}}});

new Chart(document.getElementById('de_econ'),{type:'bar',data:{labels:Y,datasets:[
  {label:'Mittlerer Preis, EUR/MWh',data:D.de.ps.price_mean_eur_mwh,backgroundColor:C.price},
  {label:'Spread Erzeugung/Pumpen, EUR/MWh',data:D.de.ps.capture_spread_eur_mwh,type:'line',borderColor:C.ps,backgroundColor:'transparent',tension:.2,yAxisID:'y'},
  {label:'Theor. Arbitragewert, Mio. EUR',data:D.de.ps.da_arbitrage_value_meur,type:'line',borderColor:C.ror,backgroundColor:'transparent',tension:.2,yAxisID:'y1'}]},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'EUR/MWh'}},y1:{position:'right',grid:{drawOnChartArea:false},title:{display:true,text:'Mio. EUR'}}}}});

new Chart(document.getElementById('de_regime'),{type:'line',data:{labels:Y,datasets:[
  {label:'DE · Pumpen 10–16 Uhr, %',data:D.de.ps.pump_share_midday_10_15_pct,borderColor:C.pump,backgroundColor:'transparent',tension:.2},
  {label:'DE · Erzeugung 17–24 Uhr, %',data:D.de.ps.gen_share_evening_17_23_pct,borderColor:C.ps,backgroundColor:'transparent',tension:.2},
  {label:'DE · Erzeugung 0–6 Uhr, %',data:D.de.ps.gen_share_night_0_5_pct,borderColor:C.de,borderDash:[4,3],backgroundColor:'transparent',tension:.2},
  {label:'AT · Pumpen 10–16 Uhr, %',data:D.at.ps.pump_share_midday_10_15_pct,borderColor:C.at,backgroundColor:'transparent',tension:.2},
  {label:'AT · Erzeugung 17–24 Uhr, %',data:D.at.ps.gen_share_evening_17_23_pct,borderColor:C.at,borderDash:[7,3],backgroundColor:'transparent',tension:.2},
  {label:'CH · Erzeugung 17–24 Uhr, %',data:D.ch.ps.gen_share_evening_17_23_pct,borderColor:C.ch,borderDash:[7,3],backgroundColor:'transparent',tension:.2}]},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'% der Sommermenge'}}}}});

new Chart(document.getElementById('de_price_yearly'),{type:'line',data:{labels:hours,datasets:
  ['2019','2021','2023','2025','2026'].filter(y=>D.de.price_hourly[y]).map((y,i)=>({label:'DE '+y,data:D.de.price_hourly[y],borderColor:['#9c9999','#e5cc06','#0096e1','#a0459a','#0000c8'][i],backgroundColor:'transparent',tension:.3,borderWidth:y==='2026'?2.8:1.5}))},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{x:{grid:{display:false},title:{display:true,text:'Tagesstunde'}},y:{grid:{color:'#e6e6e6'},title:{display:true,text:'Mittlerer Day-ahead-Preis, EUR/MWh'}}}}});

document.getElementById('narrative').innerHTML=D.narrative;

if(D.flow_rows && D.flow_rows.length){
  new Chart(document.getElementById('flows'),{type:'bar',data:{labels:Y,datasets:[
    {label:'DE',data:D.flows.de.net_import_gwh,backgroundColor:C.de},
    {label:'AT',data:D.flows.at.net_import_gwh,backgroundColor:C.at},
    {label:'CH',data:D.flows.ch.net_import_gwh,backgroundColor:C.ch}]},
    options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'GWh (positiv = Import)'}}}}});
  new Chart(document.getElementById('flows_pct'),{type:'line',data:{labels:Y,datasets:[
    {label:'DE',data:D.flows.de.net_as_pct_of_load,borderColor:C.de,backgroundColor:'transparent',tension:.2},
    {label:'AT',data:D.flows.at.net_as_pct_of_load,borderColor:C.at,backgroundColor:'transparent',tension:.2},
    {label:'CH',data:D.flows.ch.net_as_pct_of_load,borderColor:C.ch,backgroundColor:'transparent',tension:.2}]},
    options:{maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'% des Verbrauchs'}}}}});
  table('tbl_flow', D.flow_rows, [{k:'country',l:'Land'},{k:'year',l:'Jahr',raw:1},{k:'import_gwh',l:'Import'},{k:'export_gwh',l:'Export'},{k:'net_import_gwh',l:'Netto'},{k:'net_as_pct_of_load',l:'Netto, % Verbrauch'}]);
}else{document.querySelectorAll('[id=flows],[id=flows_pct]').forEach(e=>e.closest('.card').remove());document.getElementById('tbl_flow').closest('.scroll').remove()}

// KPI cards
function kpi(label,val,delta,unit){
  let d='';if(delta!=null){const up=delta>=0;d=`<div class="d ${up?'up':'down'}">${up?'▲':'▼'} ${fmt(Math.abs(delta),1)}% ggü. 2017–25</div>`}
  return `<div class="kpi"><div class="l">${label}</div><div class="v">${fmt(val,unit==='%'?1:0)}${unit?' '+unit:''}</div>${d}</div>`}
const dachNatCur=natY[iCUR], dachNatMean=meanPrevA(natY);
document.getElementById('kpis').innerHTML=[
 kpi('DACH · natürliche WK',Math.round(dachNatCur),+(100*(dachNatCur/dachNatMean-1)).toFixed(1),'GWh'),
 kpi('DE · natürliche WK (o. PSW)',dDe.natural,dDe.nat_delta_pct,'GWh'),
 kpi('AT · natürliche WK (o. PSW)',dAt.natural,dAt.nat_delta_pct,'GWh'),
 kpi('CH · natürliche WK (o. PSW)',dCh.natural,dCh.nat_delta_pct,'GWh'),
 kpi('DE · WK gesamt (m. PSW)',dDe.hydro_total,dDe.delta_pct,'GWh'),
 kpi('DE · PSW-Erzeugung',byrow('de','ps_generation_gwh'),dDe.ps_delta_pct,'GWh'),
 kpi('AT · PSW-Erzeugung',byrow('at','ps_generation_gwh'),dAt.ps_delta_pct,'GWh'),
 kpi('DE · PSW-Nettobilanz',byrow('de','ps_net_gwh'),null,'GWh')].join('');
function byrow(cc,key){const i=Y.indexOf(CUR);return D[cc].ps[key]?D[cc].ps[key][i]:null}

document.getElementById('caveats').innerHTML=`<b>Methode und Datengrenzen.</b>
<b>Natürliche Wasserkraft</b> (Laufwasser + Speicherwasser) ist der Dürre-Indikator dieser Analyse, denn nur sie hängt vom Zufluss ab. Pumpspeicher werden getrennt behandelt (Abschnitt&nbsp;3), weil ihre Erzeugung dem Netz entnommene Energie verschiebt (Round-trip&nbsp;&lt;&nbsp;100&nbsp;%) und nicht vom Niederschlag bestimmt wird. „Wasserkraft gesamt“ enthält die Pumpspeicher und dient nur dem Vergleich mit der üblichen Statistik.
Sommer = 1. Juni – 31. August in Ortszeit; 15-Minuten-Reihen (DE, AT) und Stundenwerte (CH) zu GWh Erzeugung integriert.
Deutschland und Österreich weisen <span class="tag">hydro_pumped_storage</span> (Erzeugung) und <span class="tag">hydro_pumped_storage_consumption</span> (Pumpbetrieb) getrennt aus, daher sind für diese Länder Pumpstrom, Nettobilanz und der Kreislaufwirkungsgrad berechenbar – für Österreich bleibt die Verbrauchsseite jedoch unvollständig (der scheinbare Wirkungsgrad liegt in allen zehn Jahren über 100 %, Pumpstrom ist dort eine Untergrenze).
Für die Schweiz enthält die API v2 keine separate PSW-Verbrauchsserie – die Analyse des Pumpbetriebs ist eingeschränkt (siehe Spalte „Bilanzierung“).
Preismetriken: Day-ahead (Gebotszonen DE-LU, AT, CH; AT und DE-LU sind seit Oktober 2018 getrennt, daher Preise dort erst ab 2019), bezogen auf die Stunden mit Erzeugung bzw. Pumpen, ohne Regelenergie, Netzverluste und Verträge – ein <i>theoretischer</i> Orientierungswert, nicht der tatsächliche Erlös.`;

// tables
function table(el, rows, cols, label){
  const t=document.getElementById(el);
  t.innerHTML='<thead><tr>'+cols.map(c=>'<th>'+c.l+'</th>').join('')+'</tr></thead><tbody>'+
   rows.slice().sort((a,b)=> (a.country&&b.country&&a.country!==b.country)? a.country.localeCompare(b.country) : b.year-a.year).map(r=>'<tr class="'+(r.year===CUR?'cur':'')+'">'+
     cols.map((c,i)=>'<td>'+(c.raw||i===0?r[c.k]:fmt(r[c.k],c.d==null?1:c.d))+'</td>').join('')+'</tr>').join('');
}
const hydroCols=[{k:'country',l:'Land'},{k:'year',l:'Jahr',raw:1},{k:'hydro_total_gwh',l:'Wasserkraft, GWh'},{k:'run_of_river_gwh',l:'Laufwasser'},{k:'reservoir_gwh',l:'Speicherwasser'},{k:'pumped_gwh',l:'Pumpspeicher'},{k:'load_gwh',l:'Verbrauch, GWh'},{k:'hydro_share_of_load_pct',l:'WK/Last %'},{k:'renewable_share_of_load_pct',l:'EE/Last %'},{k:'hydro_capacity_mw',l:'Leistung MW',d:0},{k:'hydro_flh',l:'Benutzungsstd.'},{k:'intervals',l:'n',raw:1},{k:'hydro_cov',l:'Abdeckung %',d:1}];
table('tbl_hydro', ['de','at','ch'].flatMap(c=>D.hydro_rows[c]).sort((a,b)=>a.country.localeCompare(b.country)||b.year-a.year), hydroCols);
const psCols=[{k:'country',l:'Land'},{k:'year',l:'Jahr',raw:1},{k:'ps_generation_gwh',l:'Erzeugung'},{k:'ps_pumping_gwh',l:'Pumpstrom'},{k:'ps_net_gwh',l:'Netto'},{k:'round_trip_eff_pct',l:'Wirkungsgrad %'},{k:'ps_gen_full_load_hours',l:'Benutzungsstd.'},{k:'ps_peak_generation_mw',l:'Spitze Erzg. MW',d:0},{k:'ps_max_pumping_mw',l:'Spitze Pumpen MW',d:0},{k:'intervals_with_generation_pct',l:'Std. mit Erzg., %'},{k:'gen_hours_in_peak_8_20_pct',l:'Erzg. 8–20 Uhr %'},{k:'pump_hours_in_night_22_6_pct',l:'Pumpen 22–6 Uhr %'},{k:'price_mean_eur_mwh',l:'Preis Ø'},{k:'capture_spread_eur_mwh',l:'Spread'},{k:'da_arbitrage_value_meur',l:'Arbitrage, Mio.'},{k:'ps_capacity_mw',l:'Leistung MW',d:0},{k:'pump_share_midday_10_15_pct',l:'Pumpen 10–16 Uhr %'},{k:'gen_share_evening_17_23_pct',l:'Erzg. 17–24 Uhr %'},{k:'pump_at_negative_price_gwh',l:'Pumpen bei neg. Preis'},{k:'gen_share_of_price_top_decile_pct',l:'Erzg. oberes Dezil %'},{k:'days_with_both_modes_pct',l:'Tage mit beiden Modi %'},{k:'max_daily_generation_gwh',l:'max. Tageserzg. GWh'},{k:'reporting',l:'Bilanzierung'}];
table('tbl_ps', ['de','at','ch'].flatMap(c=>D.ps_rows[c]), psCols);
const priceCols=[{k:'country',l:'Gebotszone'},{k:'year',l:'Jahr',raw:1},{k:'price_mean',l:'Mittel'},{k:'price_median',l:'Median'},{k:'price_min',l:'Min'},{k:'price_max',l:'Max'},{k:'daily_spread_mean',l:'Spread/Tag'},{k:'daily_spread_p90',l:'Spread p90'},{k:'neg_hours_pct',l:'neg. Stunden %'}];
table('tbl_price', D.price_rows, priceCols);
</script></body></html>
"""


if __name__ == "__main__":
    main()
