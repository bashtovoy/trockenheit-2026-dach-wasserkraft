#!/usr/bin/env python3
"""Build a self-contained HTML report from output/summary.json (Chart.js via CDN)."""

from __future__ import annotations

import json
from pathlib import Path

from findings import build as build_narrative

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
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

    for c in ("de", "ch"):
        hy = summary[f"{c}_hydro"]
        ps = summary[f"{c}_ps"]
        cur = by_year(hy, CURRENT)
        prev = mean_of(hy, "hydro_total_gwh", BASE)
        prev_rr = mean_of(hy, "run_of_river_gwh", BASE)
        prev_res = mean_of(hy, "reservoir_gwh", BASE)
        prev_ps = mean_of(hy, "pumped_gwh", BASE)
        findings[c] = {
            "hydro_total": rnd(cur.get("hydro_total_gwh")),
            "hydro_mean_prev": rnd(prev),
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
        data[c] = {
            "hydro": {k: series(hy, k) for k in
                      ["run_of_river_gwh", "reservoir_gwh", "pumped_gwh", "hydro_total_gwh",
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
            piv.setdefault(md, {})[y] = {k: rnd(rec.get(k), 2) for k in ("hydro", "ror", "res", "ps_gen", "ps_pump", "price_mean", "price_spread")}
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
    data["hydro_rows"] = {"de": summary["de_hydro"], "ch": summary["ch_hydro"]}
    data["ps_rows"] = {"de": summary["de_ps"], "ch": summary["ch_ps"]}
    data["flow_rows"] = summary.get("flows", [])
    flows = summary.get("flows", [])
    data["flows"] = {
        c: {k: [next((r.get(k) for r in flows if r["country"] == C and r["year"] == y), None)
                for y in data["years"]]
            for k in ("net_import_gwh", "net_as_pct_of_load", "import_gwh", "export_gwh")}
        for c, C in (("de", "DE"), ("ch", "CH"))}
    data["narrative"] = build_narrative(summary)

    (OUT / "report_data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    (OUT / "report.html").write_text(html, encoding="utf-8")
    print("wrote", OUT / "report.html")
    for c in ("de", "ch"):
        print(c.upper(), json.dumps(findings[c], ensure_ascii=False))


TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Гидрогенерация и ГАЭС: Швейцария и Германия, лето 2026 vs 2017–2025</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#0f1419;--card:#171d24;--ink:#e6edf3;--mut:#8b98a5;--de:#4aa3ff;--ch:#ff7a45;--hydro:#3fb950;--ps:#d29922;--line:#232b34}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{padding:28px 32px 12px;border-bottom:1px solid var(--line)}
h1{margin:0 0 6px;font-size:26px}
h2{margin:34px 0 4px;font-size:20px;border-left:4px solid var(--de);padding-left:10px}
h3{margin:22px 0 8px;font-size:16px;color:var(--mut)}
p.sub{color:var(--mut);margin:4px 0 0}
main{padding:0 32px 60px;max-width:1240px;margin:0 auto}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:18px;margin-top:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:18px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kpi .v{font-size:24px;font-weight:650}
.kpi .l{color:var(--mut);font-size:12.5px;text-transform:uppercase;letter-spacing:.04em}
.kpi .d{font-size:13px;margin-top:4px}
.up{color:#3fb950}.down{color:#f85149}
canvas{max-height:320px}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin-top:10px}
th,td{padding:5px 7px;text-align:right;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
th{color:var(--mut);font-weight:600;position:sticky;top:0;background:var(--card)}
tr.cur td{background:rgba(74,163,255,.12);font-weight:600}
.scroll{overflow:auto;max-height:420px;border:1px solid var(--line);border-radius:10px}
.note{background:rgba(210,153,34,.1);border:1px solid rgba(210,153,34,.35);border-radius:10px;padding:12px 14px;margin:14px 0;font-size:13.5px}
ul{margin:8px 0 0;padding-left:20px}
li{margin:4px 0}
.tag{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11.5px;background:var(--line);color:var(--mut);margin-right:6px}
</style></head><body>
<header>
<h1>Гидрогенерация и работа ГАЭС — Швейцария и Германия</h1>
<p class="sub">Летний сезон 2026 (1 июня — 31 августа) в сравнении с 2017–2025 · Источник: <b>energy-charts.info API v2</b> (Fraunhofer ISE, CC BY 4.0) · Единицы: GWh нетто-выработки, цены — day-ahead EUR/MWh</p>
</header>
<main>
<div class="kpis" id="kpis"></div>
<div class="note" id="caveats"></div>

<h2>1. Гидрогенерация за лето: структура и динамика</h2>
<div class="grid">
  <div class="card"><h3>Германия: выработка по типам, GWh (сумма июнь–август)</h3><canvas id="de_stack"></canvas></div>
  <div class="card"><h3>Швейцария: выработка по типам, GWh (сумма июнь–август)</h3><canvas id="ch_stack"></canvas></div>
</div>
<div class="grid">
  <div class="card"><h3>Доля гидро в потреблении (load), %</h3><canvas id="share"></canvas></div>
  <div class="card"><h3>Отклонение лета-2026 от средних 2017–2025, %</h3><canvas id="delta"></canvas></div>
</div>

<h2>2. Помесячная и посуточная картина</h2>
<div class="grid">
  <div class="card"><h3>Германия: гидро по месяцам лета, GWh/сутки (7-дневное сглаживание)</h3><canvas id="de_daily"></canvas></div>
  <div class="card"><h3>Швейцария: гидро по месяцам лета, GWh/сутки (7-дневное сглаживание)</h3><canvas id="ch_daily"></canvas></div>
</div>
<div class="grid">
  <div class="card"><h3>Германия: проточное vs водохранилищное vs ГАЭС, доля месяца</h3><canvas id="de_split"></canvas></div>
  <div class="card"><h3>Швейцария: проточное vs водохранилищное vs ГАЭС, доля месяца</h3><canvas id="ch_split"></canvas></div>
</div>

<h2>3. Pumpspeicherkraftwerk (ГАЭС)</h2>
<div class="grid">
  <div class="card"><h3>Германия: генерация / pumping / net, GWh</h3><canvas id="de_ps"></canvas></div>
  <div class="card"><h3>Швейцария: генерация ГАЭС и её доля в гидро, GWh / %</h3><canvas id="ch_ps"></canvas></div>
</div>
<div class="grid">
  <div class="card"><h3>Германия: средний профиль мощности по часам суток, МВт</h3><canvas id="de_profile"></canvas></div>
  <div class="card"><h3>Германия: цена day-ahead по часам, EUR/MWh</h3><canvas id="de_price_profile"></canvas></div>
</div>
<div class="grid">
  <div class="card"><h3>Германия: часов использования ГАЭС (full-load hours) и КПД</h3><canvas id="de_flh"></canvas></div>
  <div class="card"><h3>Экономика арбитража: спред цен и theoretical DA margin</h3><canvas id="de_econ"></canvas></div>
</div>
<div class="grid">
  <div class="card"><h3>Смена режима работы ГАЭС: доля насоса в 10–16 ч и доля генерации в 17–24 ч</h3><canvas id="de_regime"></canvas></div>
  <div class="card"><h3>Профиль цены по часам (лето 2026 vs 2017–24) — контекст сдвига</h3><canvas id="de_price_yearly"></canvas></div>
</div>

<h2>4. Трансграничный обмен (физические потоки)</h2>
<div class="grid">
  <div class="card"><h3>Нетто-импорт (+) / нетто-экспорт (−) за лето, GWh</h3><canvas id="flows"></canvas></div>
  <div class="card"><h3>Нетто-импорт как % от потребления</h3><canvas id="flows_pct"></canvas></div>
</div>
<div class="scroll" style="margin-top:12px"><table id="tbl_flow"></table></div>

<h2>5. Выводы</h2>
<div class="card" id="narrative"></div>

<h2>6. Таблицы</h2>
<h3>Гидрогенерация по годам</h3>
<div class="scroll"><table id="tbl_hydro"></table></div>
<h3>ГАЭС по годам</h3>
<div class="scroll"><table id="tbl_ps"></table></div>
<h3>Цены day-ahead за лето</h3>
<div class="scroll"><table id="tbl_price"></table></div>
</main>
<script>
const D = __DATA__;
const Y = D.years, CUR = 2026, PREV = Y.filter(y=>y<CUR);
const C = {de:'#4aa3ff', ch:'#ff7a45', ror:'#3fb950', res:'#8ede92', ps:'#d29922', neg:'#f85149', ink:'#e6edf3', mut:'#8b98a5', line:'#232b34'};
Chart.defaults.color = C.mut; Chart.defaults.borderColor = C.line;
Chart.defaults.font.size = 11.5;
const fmt = (v,d=0)=> v==null?'–':Number(v).toLocaleString('de-DE',{minimumFractionDigits:d,maximumFractionDigits:d});

function smooth(arr,w=7){const o=[];for(let i=0;i<arr.length;i++){let s=0,n=0;for(let k=-Math.floor(w/2);k<=Math.floor(w/2);k++){const j=i+k;if(j>=0&&j<arr.length&&arr[j]!=null){s+=arr[j];n++}}o.push(n?+(s/n).toFixed(3):null)}return o}

// ---- daily pivot: per year arrays aligned on month-day
function dailySeries(cc, key, years){
  const md = Object.keys(D[cc].daily);
  return years.map(y=>({label:String(y), data: md.map(k=>D[cc].daily[k][String(y)]?D[cc].daily[k][String(y)][key]:null)}));
}
function dailySmooth(cc,key,years,w=7){return dailySeries(cc,key,years).map(s=>({label:s.label,data:smooth(s.data,w)}))}

function barStack(cc, id){
  const h=D[cc].hydro;
  new Chart(document.getElementById(id),{type:'bar',data:{labels:Y,datasets:[
    {label:'Run-of-River',data:h.run_of_river_gwh,backgroundColor:C.ror},
    {label:'Wasser reservoir',data:h.reservoir_gwh,backgroundColor:C.res},
    {label:'Pumpspeicher',data:h.pumped_gwh,backgroundColor:C.ps}]},
   options:{responsive:true,plugins:{legend:{position:'bottom'}},scales:{x:{stacked:true},y:{stacked:true,title:{display:true,text:'GWh'}}}}});
}
barStack('de','de_stack'); barStack('ch','ch_stack');

new Chart(document.getElementById('share'),{type:'line',data:{labels:Y,datasets:[
  {label:'DE',data:D.de.hydro.hydro_share_of_load_pct,borderColor:C.de,backgroundColor:'transparent',tension:.25},
  {label:'CH',data:D.ch.hydro.hydro_share_of_load_pct,borderColor:C.ch,backgroundColor:'transparent',tension:.25}]},
  options:{plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'% потребления'}}}}});

const dDe=D.findings.de, dCh=D.findings.ch;
new Chart(document.getElementById('delta'),{type:'bar',data:{labels:['Гидро всего','Проточное','Водохранилища','ГАЭС'],datasets:[
  {label:'DE 2026 vs 2017–25',data:[dDe.delta_pct,dDe.ror_delta_pct,dDe.res_delta_pct,dDe.ps_delta_pct],backgroundColor:C.de},
  {label:'CH 2026 vs 2017–25',data:[dCh.delta_pct,dCh.ror_delta_pct,dCh.res_delta_pct,dCh.ps_delta_pct],backgroundColor:C.ch}]},
  options:{plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'% отклонения'}}}}});

new Chart(document.getElementById('de_daily'),{type:'line',data:{datasets:dailySmooth('de','hydro',[2026,2025,2024,2023,2018])},
  options:{plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'GWh/сутки (7-дн. среднее)'}}}}});
new Chart(document.getElementById('ch_daily'),{type:'line',data:{datasets:dailySmooth('ch','hydro',[2026,2025,2024,2023,2018])},
  options:{plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'GWh/сутки (7-дн. среднее)'}}}}});

function splitChart(cc,id){
  const months=['06','07','08'], lab=['Июнь','Июль','Август'];
  const cur=D[cc].monthly.filter(r=>r.year===CUR), prv=D[cc].monthly.filter(r=>r.year<CUR);
  const agg=(sel,key)=>{const v=prv.filter(r=>r.month.endsWith(sel)).map(r=>r[key]).filter(x=>x!=null);return v.length?v.reduce((a,b)=>a+b,0)/v.length:null};
  const g=(sel,key,src)=>src.filter(r=>r.month.endsWith(sel)).reduce((a,r)=>a+(r[key]||0),0);
  const ds=[];
  [['run_of_river_gwh','Проточное',C.ror],['reservoir_gwh','Водохранилища',C.res],['pumped_gwh','ГАЭС',C.ps]].forEach(([k,l,col])=>{
    ds.push({type:'bar',label:l+' 2026',data:months.map(m=>g(m,k,cur)),backgroundColor:col});
    ds.push({type:'bar',label:l+' 2017–25 avg',data:months.map(m=>agg(m,k)),backgroundColor:col+'55'});
  });
  new Chart(document.getElementById(id),{data:{labels:lab,datasets:ds},
    options:{plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'GWh за месяц'}}}}});
}
splitChart('de','de_split'); splitChart('ch','ch_split');

new Chart(document.getElementById('de_ps'),{type:'bar',data:{labels:Y,datasets:[
  {label:'Генерация',data:D.de.ps.ps_generation_gwh,backgroundColor:C.ps},
  {label:'Pumping (расход)',data:D.de.ps.ps_pumping_gwh,backgroundColor:C.neg},
  {label:'Net',data:D.de.ps.ps_net_gwh,backgroundColor:'#8ede92'}]},
  options:{plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'GWh'}}}}});

new Chart(document.getElementById('ch_ps'),{type:'bar',data:{labels:Y,datasets:[
  {type:'bar',label:'Генерация ГАЭС, GWh',data:D.ch.hydro.pumped_gwh,backgroundColor:C.ps,yAxisID:'y'},
  {type:'line',label:'Доля в гидро, %',data:D.ch.hydro.hydro_total_gwh.map((v,i)=>v&&D.ch.hydro.pumped_gwh[i]!=null?+(D.ch.hydro.pumped_gwh[i]/v*100).toFixed(1):null),borderColor:C.de,backgroundColor:'transparent',yAxisID:'y1',tension:.2}]},
  options:{plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'GWh'}},y1:{position:'right',grid:{drawOnChartArea:false},title:{display:true,text:'%'}}}}});

// profiles
const hours=[...Array(24).keys()];
const deGenCur=D.de.ps_hourly['DE_generation_2026']||[], dePumpCur=D.de.ps_hourly['DE_pumping_2026']||[];
function meanPrev(kind){const arrs=Object.keys(D.de.ps_hourly).filter(k=>k.startsWith('DE_'+kind)&&!k.endsWith('2026')).map(k=>D.de.ps_hourly[k]);
  if(!arrs.length)return null;return hours.map(h=>{const v=arrs.map(a=>a[h]).filter(x=>x!=null);return v.length?+(v.reduce((a,b)=>a+b,0)/v.length).toFixed(1):null})}
new Chart(document.getElementById('de_profile'),{type:'line',data:{labels:hours,datasets:[
  {label:'Генерация 2026',data:deGenCur,borderColor:C.ps,backgroundColor:'transparent',tension:.3},
  {label:'Генерация 2017–25 (avg)',data:meanPrev('generation'),borderColor:C.ps+'88',borderDash:[5,4],backgroundColor:'transparent',tension:.3},
  {label:'Pumping 2026',data:dePumpCur,borderColor:C.neg,backgroundColor:'transparent',tension:.3},
  {label:'Pumping 2017–25 (avg)',data:meanPrev('pumping'),borderColor:C.neg+'88',borderDash:[5,4],backgroundColor:'transparent',tension:.3}]},
  options:{plugins:{legend:{position:'bottom'}},scales:{x:{title:{display:true,text:'час суток (local)'}},y:{title:{display:true,text:'средняя мощность, МВт'}}}}});

new Chart(document.getElementById('de_price_profile'),{type:'line',data:{labels:hours,datasets:[
  {label:'2026',data:D.de.price_hourly['2026'],borderColor:C.de,backgroundColor:'transparent',tension:.3},
  {label:'2025',data:D.de.price_hourly['2025'],borderColor:C.ch,backgroundColor:'transparent',tension:.3},
  {label:'2017–24 avg',data:(()=>{const ys=Object.keys(D.de.price_hourly).filter(y=>+y<2025);return hours.map(h=>{const v=ys.map(y=>D.de.price_hourly[y][h]).filter(x=>x!=null);return v.length?+(v.reduce((a,b)=>a+b)/v.length).toFixed(1):null})})(),borderColor:C.mut,borderDash:[5,4],backgroundColor:'transparent',tension:.3}]},
  options:{plugins:{legend:{position:'bottom'}},scales:{x:{title:{display:true,text:'час суток'}},y:{title:{display:true,text:'EUR/MWh'}}}}});

new Chart(document.getElementById('de_flh'),{type:'bar',data:{labels:Y,datasets:[
  {label:'Часов использования (FLH)',data:D.de.ps.ps_gen_full_load_hours,backgroundColor:C.de,yAxisID:'y'},
  {label:'КПД цикла, %',data:D.de.ps.round_trip_eff_pct,type:'line',borderColor:C.ps,backgroundColor:'transparent',yAxisID:'y1',tension:.2}]},
  options:{plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'ч'}},y1:{position:'right',grid:{drawOnChartArea:false},title:{display:true,text:'%'}}}}});

new Chart(document.getElementById('de_econ'),{type:'bar',data:{labels:Y,datasets:[
  {label:'Средняя цена, EUR/MWh',data:D.de.ps.price_mean_eur_mwh,backgroundColor:'#39454f'},
  {label:'Спред пик/вне-пик, EUR/MWh',data:D.de.ps.capture_spread_eur_mwh,type:'line',borderColor:C.ps,backgroundColor:'transparent',tension:.2,yAxisID:'y'},
  {label:'Теор. стоимость арбитража, МЛН EUR',data:D.de.ps.da_arbitrage_value_meur,type:'line',borderColor:C.ror,backgroundColor:'transparent',tension:.2,yAxisID:'y1'}]},
  options:{plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'EUR/MWh'}},y1:{position:'right',grid:{drawOnChartArea:false},title:{display:true,text:'МЛН EUR'}}}}});

new Chart(document.getElementById('de_regime'),{type:'line',data:{labels:Y,datasets:[
  {label:'DE · насос 10–16 ч, %',data:D.de.ps.pump_share_midday_10_15_pct,borderColor:C.neg,backgroundColor:'transparent',tension:.2},
  {label:'DE · генерация 17–24 ч, %',data:D.de.ps.gen_share_evening_17_23_pct,borderColor:C.ps,backgroundColor:'transparent',tension:.2},
  {label:'DE · генерация 0–6 ч, %',data:D.de.ps.gen_share_night_0_5_pct,borderColor:C.de,borderDash:[4,3],backgroundColor:'transparent',tension:.2},
  {label:'CH · генерация 17–24 ч, %',data:D.ch.ps.gen_share_evening_17_23_pct,borderColor:C.ch,borderDash:[7,3],backgroundColor:'transparent',tension:.2}]},
  options:{plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'% объёма за лето'}}}}});

new Chart(document.getElementById('de_price_yearly'),{type:'line',data:{labels:hours,datasets:
  ['2019','2021','2023','2025','2026'].filter(y=>D.de.price_hourly[y]).map((y,i)=>({label:'DE '+y,data:D.de.price_hourly[y],borderColor:['#39454f','#4a5a68','#6b7d8c','#9aa7b1',C.de][i],backgroundColor:'transparent',tension:.3,borderWidth:y==='2026'?2.6:1.2}))},
  options:{plugins:{legend:{position:'bottom'}},scales:{x:{title:{display:true,text:'час суток'}},y:{title:{display:true,text:'средняя цена day-ahead, EUR/MWh'}}}}});

document.getElementById('narrative').innerHTML=D.narrative;

if(D.flow_rows && D.flow_rows.length){
  new Chart(document.getElementById('flows'),{type:'bar',data:{labels:Y,datasets:[
    {label:'DE',data:D.flows.de.net_import_gwh,backgroundColor:C.de},
    {label:'CH',data:D.flows.ch.net_import_gwh,backgroundColor:C.ch}]},
    options:{plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'GWh (положительное = импорт)'}}}}});
  new Chart(document.getElementById('flows_pct'),{type:'line',data:{labels:Y,datasets:[
    {label:'DE',data:D.flows.de.net_as_pct_of_load,borderColor:C.de,backgroundColor:'transparent',tension:.2},
    {label:'CH',data:D.flows.ch.net_as_pct_of_load,borderColor:C.ch,backgroundColor:'transparent',tension:.2}]},
    options:{plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'% потребления'}}}}});
  table('tbl_flow', D.flow_rows, [{k:'country',l:'Страна'},{k:'year',l:'Год',d:0},{k:'import_gwh',l:'Импорт'},{k:'export_gwh',l:'Экспорт'},{k:'net_import_gwh',l:'Нетто'},{k:'net_as_pct_of_load',l:'Нетто, % load'}]);
}else{document.querySelectorAll('[id=flows],[id=flows_pct]').forEach(e=>e.closest('.card').remove());document.getElementById('tbl_flow').closest('.scroll').remove()}

// KPI cards
function kpi(label,val,delta,unit){
  let d='';if(delta!=null){const up=delta>=0;d=`<div class="d ${up?'up':'down'}">${up?'▲':'▼'} ${fmt(Math.abs(delta),1)}% vs 2017–25</div>`}
  return `<div class="kpi"><div class="l">${label}</div><div class="v">${fmt(val,unit==='%'?1:0)}${unit?' '+unit:''}</div>${d}</div>`}
document.getElementById('kpis').innerHTML=[
 kpi('DE · гидро за лето',dDe.hydro_total,dDe.delta_pct,'GWh'),
 kpi('CH · гидро за лето',dCh.hydro_total,dCh.delta_pct,'GWh'),
 kpi('DE · доля гидро в load',dDe.share_of_load,null,'%'),
 kpi('CH · доля гидро в load',dCh.share_of_load,null,'%'),
 kpi('DE · ГАЭС генерация',byrow('de','ps_generation_gwh'),dDe.ps_delta_pct,'GWh'),
 kpi('DE · net-выработка ГАЭС',byrow('de','ps_net_gwh'),null,'GWh')].join('');
function byrow(cc,key){const i=Y.indexOf(CUR);return D[cc].ps[key]?D[cc].ps[key][i]:null}

document.getElementById('caveats').innerHTML=`<b>Методика и ограничения.</b>
Лето = 1 июня – 31 августа по местному времени; интегрирование 15-минутных рядов (DE) и часовых (CH) в GWh нетто-выработки.
DE публично отдельно публикует <span class="tag">hydro_pumped_storage</span> (генерация) и <span class="tag">hydro_pumped_storage_consumption</span> (насосный режим), поэтому для Германии доступны pumping, net и оценка КПД цикла.
Для Швейцарии в API v2 отдельной серии потребления ГАЭС нет — анализ насосного режима ограничен (см. таблицу «reporting»).
Ценовые метрики — day-ahead (BZN DE-LU и CH), расчёт по почасовым часам работы, без учёта балансировки, затрат на сетевые потери и контрактов — это <i>теоретический</i> маржинальный ориентир, а не фактическая выручка.`;

// tables
function table(el, rows, cols, label){
  const t=document.getElementById(el);
  t.innerHTML='<thead><tr>'+cols.map(c=>'<th>'+c.l+'</th>').join('')+'</tr></thead><tbody>'+
   rows.slice().sort((a,b)=>b.year-a.year).map(r=>'<tr class="'+(r.year===CUR?'cur':'')+'">'+
     cols.map((c,i)=>'<td>'+(i===0?r[c.k]:fmt(r[c.k],c.d==null?1:c.d))+'</td>').join('')+'</tr>').join('');
}
const hydroCols=[{k:'year',l:'Год',d:0},{k:'hydro_total_gwh',l:'Гидро, GWh'},{k:'run_of_river_gwh',l:'Проточное'},{k:'reservoir_gwh',l:'Водохр.'},{k:'pumped_gwh',l:'ГАЭС'},{k:'load_gwh',l:'Load, GWh'},{k:'hydro_share_of_load_pct',l:'Гидро/load %'},{k:'renewable_share_of_load_pct',l:'ВИЭ/load %'},{k:'hydro_capacity_mw',l:'Мощн. МВт',d:0},{k:'hydro_flh',l:'Часы исп.'},{k:'intervals',l:'n',d:0},{k:'hydro_cov',l:'покрытие %',d:1}];
table('tbl_hydro', D.hydro_rows.de.concat(D.hydro_rows.ch).sort((a,b)=>a.country.localeCompare(b.country)||b.year-a.year), hydroCols);
const psCols=[{k:'country',l:'Страна'},{k:'year',l:'Год',d:0},{k:'ps_generation_gwh',l:'Генерация'},{k:'ps_pumping_gwh',l:'Pumping'},{k:'ps_net_gwh',l:'Net'},{k:'round_trip_eff_pct',l:'КПД %'},{k:'ps_gen_full_load_hours',l:'FLH ч'},{k:'ps_peak_generation_mw',l:'Пик ген. МВт',d:0},{k:'ps_max_pumping_mw',l:'Пик pump МВт',d:0},{k:'intervals_with_generation_pct',l:'часы с ген., %'},{k:'gen_hours_in_peak_8_20_pct',l:'ген. 8–20ч %'},{k:'pump_hours_in_night_22_6_pct',l:'pump 22–6ч %'},{k:'price_mean_eur_mwh',l:'Цена ср.'},{k:'capture_spread_eur_mwh',l:'Спред'},{k:'da_arbitrage_value_meur',l:'Арбитраж, МЛН'},{k:'ps_capacity_mw',l:'Мощн. МВт',d:0},{k:'pump_share_midday_10_15_pct',l:'насос 10–16ч %'},{k:'gen_share_evening_17_23_pct',l:'ген. 17–24ч %'},{k:'pump_at_negative_price_gwh',l:'pump при отр. цене'},{k:'gen_share_of_price_top_decile_pct',l:'ген. в top-decile %'},{k:'days_with_both_modes_pct',l:'дней 2 режима %'},{k:'max_daily_generation_gwh',l:'макс сут. ген. GWh'},{k:'reporting',l:'учёт'}];
table('tbl_ps', D.ps_rows.de.concat(D.ps_rows.ch), psCols);
const priceCols=[{k:'country',l:'Зона'},{k:'year',l:'Год',d:0},{k:'price_mean',l:'Средняя'},{k:'price_median',l:'Медиана'},{k:'price_min',l:'Мин'},{k:'price_max',l:'Макс'},{k:'daily_spread_mean',l:'Спред/день'},{k:'daily_spread_p90',l:'Спред p90'},{k:'neg_hours_pct',l:'отриц. часы %'}];
table('tbl_price', D.price_rows, priceCols);
</script></body></html>
"""


if __name__ == "__main__":
    main()
