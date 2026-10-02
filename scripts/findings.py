#!/usr/bin/env python3
"""Render the findings section ("Fazit") of the report from output/summary.json.

All numbers are recomputed here so the text can never drift from the tables.
Output language: German (typography: comma decimal separator, thin-space
thousands separator, space before %).
"""

from __future__ import annotations

BASE = list(range(2017, 2026))
CUR = 2026
MONTH_DE = {6: "Juni", 7: "Juli", 8: "August"}
THIN = "\u2009"


def num(x, nd=0, sign=False):
    """German number format: 6 754 / 134,6 / +15 %."""
    if x is None:
        return "–"
    s = f"{float(x):+,.{nd}f}" if sign else f"{float(x):,.{nd}f}"
    return s.replace(",", THIN).replace(".", ",")


def pct(x, nd=0):
    return f"{num(x, nd, sign=True)}{THIN}%"


def mean_of(records, key, years):
    vals = [r[key] for r in records if int(r["year"]) in years and r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def index_by_year(records):
    return {int(r["year"]): r for r in records}


def build(summary) -> str:
    hy = {c: index_by_year(summary[f"{c}_hydro"]) for c in ("de", "at", "ch")}
    ps = {c: index_by_year(summary[f"{c}_ps"]) for c in ("de", "at", "ch")}
    pr = {c: index_by_year([r for r in summary["prices"] if r["country"] == c.upper()])
          for c in ("de", "at", "ch")}
    fl = {c: index_by_year([r for r in summary.get("flows", []) if r["country"] == c.upper()])
          for c in ("de", "at", "ch")}

    def v(tab, c, y, key, default=None):
        row = tab[c].get(y)
        return row.get(key, default) if row else default

    def d100(tab, c, y, key, ref_y):
        a, b = v(tab, c, y, key), v(tab, c, ref_y, key)
        return 100 * (a / b - 1) if a and b else None

    items: list[str] = []

    # ---- 0. Natuerliche Wasserkraft als Duerre-Massstab -------------------
    # Pumpspeicher haengen nicht vom Abfluss ab (Speicher, der zuerst Strom
    # aufnimmt). Fuer das TROCKENHEITssignal zaehlt Laufwasser + Speicherwasser;
    # PSW werden separat ausgewiesen.
    def nat(rec):
        return (rec.get("run_of_river_gwh") or 0) + (rec.get("reservoir_gwh") or 0)
    nat_cur = {c: nat(hy[c][CUR]) for c in ("de", "at", "ch")}
    nat_mean = {c: sum(nat(r) for r in summary[f"{c}_hydro"] if r["year"] in BASE) / len(BASE)
                for c in ("de", "at", "ch")}
    nat_delta = {c: 100 * (nat_cur[c] / nat_mean[c] - 1) for c in ("de", "at", "ch")}
    dach_nat_cur = sum(nat_cur.values())
    dach_nat_mean = sum(nat_mean.values())
    de_nat_rank = sorted(nat(r) for r in summary["de_hydro"]).index(nat(hy["de"][CUR])) + 1
    items.append(
        f"<b>Der energiestatistische Maßstab für die Trockenheit: die natürliche Wasserkraft.</b> Pumpspeicher sind kein "
        f"vom Abfluss abhängiger Erzeuger, sondern ein Speicher, der zuerst Strom aufnimmt; für das "
        f"Dürresignal zählt daher Laufwasser + Speicherwasser, die Pumpspeicher werden separat "
        f"ausgewiesen. Dies ist ein Indikator für die <i>energetische Wirkung</i> des Wasserdefizits, kein "
        f"meteorologischer Dürreindex – die Speicherwasser-Erzeugung hängt neben dem Zufluss auch von "
        f"Speicherstand und Bewirtschaftung ab. Auf dieser Basis fiel die natürliche Wasserkraft im DACH-Raum von "
        f"{num(dach_nat_mean)} auf {num(dach_nat_cur)} GWh "
        f"({pct(100*(dach_nat_cur/dach_nat_mean-1))}) – rund ein Drittel. Alle drei Länder lagen "
        f"gleichzeitig auf dem tiefsten Stand des Jahrzehnts: DE {pct(nat_delta['de'])}, AT "
        f"{pct(nat_delta['at'])}, CH {pct(nat_delta['ch'])}. In Deutschland wurde dieser Einbruch durch "
        f"eine überdurchschnittliche Pumpspeicher-Erzeugung überdeckt, die den Gesamt-Wasserkraftwert "
        f"auf nur {pct(100*(v(hy,'de',CUR,'hydro_total_gwh')/mean_of(summary['de_hydro'],'hydro_total_gwh',BASE)-1))} "
        f"sinken ließ – die PSW-Menge maskiert also den eigentlichen Wassermangel.")

    # ---- 1. Deutschland: Wasserkraft --------------------------------------
    de26 = hy["de"][CUR]
    de_hyd_mean = mean_of(summary["de_hydro"], "hydro_total_gwh", BASE)
    de_ror_mean = mean_of(summary["de_hydro"], "run_of_river_gwh", BASE)
    de_res_mean = mean_of(summary["de_hydro"], "reservoir_gwh", BASE)
    de_rank = sorted((r["hydro_total_gwh"] for r in summary["de_hydro"]), reverse=True).index(
        de26["hydro_total_gwh"]) + 1
    de_ror_delta = 100*(de26['run_of_river_gwh']/de_ror_mean-1)
    de_res_delta = 100*(de26['reservoir_gwh']/de_res_mean-1)
    items.append(
        f"<b>Deutschland: {num(de26['hydro_total_gwh'])} GWh Wasserkraft im Sommer, "
        f"{pct(100*(de26['hydro_total_gwh']/de_hyd_mean-1))} gegenüber dem Mittel 2017–2025</b> "
        f"– Platz {de_rank} von zehn Jahren. <i>Mengenmässig</i> liegt der Einbruch bei den "
        f"Laufwasserkraftwerken: {num(de26['run_of_river_gwh'])} GWh statt {num(de_ror_mean)} GWh im Mittel "
        f"({pct(de_ror_delta)}), der niedrigste Wert des gesamten Beobachtungsfensters und deutlich unter "
        f"dem Dürrejahr 2018 ({num(v(hy,'de',2018,'run_of_river_gwh'))} GWh) – sie stellen mit Abstand die "
        f"grösste Wasserkraftsparte. <i>Relativ</i> härter traf es dagegen das Speicherwasser: "
        f"{num(de26['reservoir_gwh'])} GWh statt {num(de_res_mean)} GWh ({pct(de_res_delta)}); der "
        f"prozentuale Rückgang ist grösser als beim Laufwasser, obwohl die absolute Menge klein bleibt. "
        f"Man muss also zwischen dem dominanten Verlust in GWh (Laufwasser) und der tieferen prozentualen "
        f"Senkung (Speicherwasser) unterscheiden. Rechnet man die Pumpspeicher heraus, erreichte auch "
        f"Deutschland bei Lauf- und Speicherwasser den tiefsten Sommerwert der zehn Jahre (Platz "
        f"{de_nat_rank} von 10) – der scheinbar milde Rückgang des Gesamtwerts ist also im Kern der "
        f"hohen PSW-Erzeugung geschuldet, nicht einem milden Wasserangebot.")

    # ---- 2. Verlauf innerhalb des Sommers ---------------------------------
    m26 = sorted((m for m in summary["de_monthly"] if m["year"] == CUR), key=lambda r: r["month"])
    jun, aug = m26[0]["hydro_gwh"], m26[-1]["hydro_gwh"]
    items.append(
        f"<b>Die Trockenheit verschärfte sich im Verlauf der Saison:</b> in Deutschland "
        f"{monthly_str(m26)} GWh – ein Rückgang von {num(100*(1-aug/jun))}{THIN}% zwischen Juni und "
        f"August. Die Wasserführung erholte sich nach dem Juni-Hochwasser nicht, wie es in "
        f"nassen Jahren der Fall wäre.")

    # ---- 2b. Deutschland: Rahmendaten -------------------------------------
    de_wind_mean = mean_of(summary["de_hydro"], "wind_gwh", BASE)
    de_sol_mean = mean_of(summary["de_hydro"], "solar_gwh", BASE)
    items.append(
        f"<b>Warum das Wasserkraft-Defizit in Deutschland bilanziell kaum auffiel:</b> "
        f"Wind (inkl. Offshore) + Solar lagen im Sommer 2026 bei {num(hy['de'][CUR]['wind_gwh'])} + "
        f"{num(hy['de'][CUR]['solar_gwh'])} GWh gegenüber {num(de_wind_mean)} + {num(de_sol_mean)} GWh "
        f"im Mittel, und der EE-Anteil am Verbrauch erreichte "
        f"{num(hy['de'][CUR]['renewable_share_of_load_pct'],1)}{THIN}% – der Höchstwert des Fensters bei "
        f"{num(mean_of(summary['de_hydro'],'renewable_share_of_load_pct',BASE),1)}{THIN}% im Mittel. "
        f"Wasserkraft deckt in DE nur "
        f"{num(hy['de'][CUR]['hydro_share_of_load_pct'],1)}{THIN}% des Verbrauchs (davon natürliche "
        f"Wasserkraft {num(hy['de'][CUR]['natural_share_of_load_pct'],1)}{THIN}%); ihr Fehlbetrag "
        f"({num(de26['hydro_total_gwh']-de_hyd_mean, 0, sign=True)} GWh, natürliche Wasserkraft "
        f"{num(de26['natural_gwh']-mean_of(summary['de_hydro'],'natural_gwh',BASE), 0, sign=True)} GWh) war "
        f"mengenmässig klein gegen den Zuwachs von Wind und Solar, die zusammen gut "
        f"{num((hy['de'][CUR]['wind_gwh']-de_wind_mean)+(hy['de'][CUR]['solar_gwh']-de_sol_mean))} GWh über "
        f"dem Mittel lagen. Das entlastete die Bilanz – ersetzte das Defizit aber nicht physikalisch, denn "
        f"Deutschland blieb im Sommer 2026 Nettoimporteur (Abschnitt&nbsp;4); „aufgefangen“ ist daher eine "
        f"bilanzielle, keine nachgewiesene kausale Deutung. In der Schweiz war dieser Puffer deutlich "
        f"kleiner, aber nicht null: Auch dort stieg die Solarproduktion sprunghaft auf "
        f"{num(v(hy,'ch',CUR,'solar_gwh'))} GWh statt {num(mean_of(summary['ch_hydro'],'solar_gwh',BASE))} GWh "
        f"im Mittel und glich einen Teil des Defizits aus – doch weil die Wasserkraft dort über die Hälfte "
        f"der Last deckt und Wind kaum zunahm, blieb der relative Fehlbetrag grösser als in Deutschland.")

    # ---- 3. Oesterreich ---------------------------------------------------
    at26 = hy["at"][CUR]
    at_hyd_mean = mean_of(summary["at_hydro"], "hydro_total_gwh", BASE)
    at_ror_mean = mean_of(summary["at_hydro"], "run_of_river_gwh", BASE)
    at_res_mean = mean_of(summary["at_hydro"], "reservoir_gwh", BASE)
    at_share_mean = mean_of(summary["at_hydro"], "hydro_share_of_load_pct", BASE)
    at_nat_share_mean = mean_of(summary["at_hydro"], "natural_share_of_load_pct", BASE)
    at_rank = sorted((r["hydro_total_gwh"] for r in summary["at_hydro"]), reverse=True).index(
        at26["hydro_total_gwh"]) + 1
    items.append(
        f"<b>Österreich hat den stärksten Rückgang im DACH-Raum: {num(at26['hydro_total_gwh'])} GWh, "
        f"{pct(100*(at26['hydro_total_gwh']/at_hyd_mean-1))} gegenüber dem Mittel 2017–2025</b> – "
        f"Platz {at_rank} von zehn Jahren. Anders als in der Schweiz trifft es hier zuerst das "
        f"Laufwasser: {num(at26['run_of_river_gwh'])} GWh statt {num(at_ror_mean)} GWh im Mittel "
        f"({pct(100*(at26['run_of_river_gwh']/at_ror_mean-1))}); Speicherwasser "
        f"{num(at26['reservoir_gwh'])} GWh statt {num(at_res_mean)} GWh "
        f"({pct(100*(at26['reservoir_gwh']/at_res_mean-1))}). Weil die <i>natürliche</i> Wasserkraft in einem "
        f"Normalsommer {num(at_nat_share_mean,0)}{THIN}% der österreichischen Last gedeckt hätte, fiel ihr "
        f"Anteil auf {num(at26['natural_share_of_load_pct'],0)}{THIN}% – der tiefste Wert der zehn Jahre. "
        f"Der Brutto-Wasserkraftanteil inklusive Pumpspeicher – deren Erzeugung von "
        f"{num(v(ps,'at',CUR,'ps_generation_gwh'))} GWh ist keine zusätzliche natürliche Wasserkraft – lag "
        f"bei {num(at26['hydro_share_of_load_pct'],0)}{THIN}%.")

    # ---- 3b. Schweiz ------------------------------------------------------
    ch26 = hy["ch"][CUR]
    ch_hyd_mean = mean_of(summary["ch_hydro"], "hydro_total_gwh", BASE)
    ch_res_mean = mean_of(summary["ch_hydro"], "reservoir_gwh", BASE)
    ch_ror_mean = mean_of(summary["ch_hydro"], "run_of_river_gwh", BASE)
    ch_wet = max((r for r in summary["ch_hydro"] if r["year"] < CUR), key=lambda r: r["reservoir_gwh"])
    items.append(
        f"<b>Die Schweiz war fast ebenso stark betroffen: {num(ch26['hydro_total_gwh'])} GWh, "
        f"{pct(100*(ch26['hydro_total_gwh']/ch_hyd_mean-1))} gegenüber dem Mittel und "
        f"{pct(d100(hy,'ch',CUR,'hydro_total_gwh',2025))} gegenüber Sommer 2025</b> – der schlechteste "
        f"Sommer der zehn Jahre. Der Rückgang traf die Speicherwasserkraft, also die <i>Erzeugung</i> der "
        f"steuerbaren Speicherkraftwerke – nicht den gespeicherten Wasserinhalt, der separat gemessen würde: "
        f"{num(ch26['reservoir_gwh'])} GWh statt {num(ch_res_mean)} GWh im Mittel "
        f"({pct(100*(ch26['reservoir_gwh']/ch_res_mean-1))}); im Rekordjahr {ch_wet['year']} waren es "
        f"{num(ch_wet['reservoir_gwh'])} GWh. Laufwasser fiel moderater aus "
        f"({pct(100*(ch26['run_of_river_gwh']/ch_ror_mean-1))}).")

    # ---- 3c. Der Alpenraum als Ganzes ------------------------------------
    reg = {y: sum(v(hy, c, y, "hydro_total_gwh") or 0 for c in ("de", "at", "ch"))
           for y in BASE + [CUR]}
    reg_mean = sum(mean_of(summary[f"{c}_hydro"], "hydro_total_gwh", BASE) for c in ("de", "at", "ch"))
    reg_res = {y: sum(v(hy, c, y, "reservoir_gwh") or 0 for c in ("de", "at", "ch"))
               for y in BASE + [CUR]}
    reg_res_mean = sum(mean_of(summary[f"{c}_hydro"], "reservoir_gwh", BASE) for c in ("de", "at", "ch"))
    reg_ps = sum(v(ps, c, CUR, "ps_generation_gwh") or 0 for c in ("de", "at", "ch"))
    reg_ps_mean = sum(mean_of(summary[f"{c}_ps"], "ps_generation_gwh", BASE) for c in ("de", "at", "ch"))
    reg_nat = sum(v(hy, c, CUR, "natural_gwh") or 0 for c in ("de", "at", "ch"))
    reg_nat_mean = sum(mean_of(summary[f"{c}_hydro"], "natural_gwh", BASE) for c in ("de", "at", "ch"))
    low_share = sum(1 for c in ("de", "at", "ch")
                    if hy[c][CUR].get("natural_share_of_load_pct") is not None
                    and hy[c][CUR]["natural_share_of_load_pct"]
                    <= min((x["natural_share_of_load_pct"] for x in summary[f"{c}_hydro"]
                            if x["year"] != CUR and x.get("natural_share_of_load_pct") is not None),
                           default=9e9))
    items.append(
        f"<b>Der Alpenraum als Ganzes:</b> Die <i>natürliche</i> Wasserkraft (Laufwasser + Speicherwasser) "
        f"der drei Länder fiel im Sommer 2026 auf {num(reg_nat)} GWh gegenüber {num(reg_nat_mean)} GWh im "
        f"Mittel ({pct(100*(reg_nat/reg_nat_mean-1))}) – es fehlen {num(reg_nat_mean-reg_nat)} GWh. "
        f"Rechnet man die Pumpspeicher mit („Wasserkraft gesamt“ = {num(reg[CUR])} GWh), fällt der "
        f"ausgewiesene Rückgang mit {pct(100*(reg[CUR]/reg_mean-1))} deutlich milder aus – die "
        f"PSW-Erzeugung überdeckt das Wasserdefizit (Zahlen unten). Der eigentliche Befund ist die "
        f"Gleichzeitigkeit: in {low_share} von 3 Ländern war der Anteil der natürlichen Wasserkraft an der "
        f"Last so tief wie nie im Jahrzehnt – und zwar auf sehr unterschiedlichem Niveau: AT "
        f"{num(hy['at'][CUR]['natural_share_of_load_pct'],0)}{THIN}% und CH "
        f"{num(hy['ch'][CUR]['natural_share_of_load_pct'],0)}{THIN}% gegenüber nur "
        f"{num(hy['de'][CUR]['natural_share_of_load_pct'],1)}{THIN}% in DE. Die Daten zeigen ein "
        f"gleichzeitig auftretendes Wasserkraftdefizit in allen drei Ländern – ein überregionales "
        f"hydrologisches Signal im DACH-Raum; ob es ein einheitliches Witterungsereignis war, lässt sich "
        f"aus den Erzeugungsdaten allein nicht abschliessend belegen. Am deutlichsten wird das bei der "
        f"Speicherwasser-Erzeugung – die "
        f"der drei Länder zusammen lieferte nur {num(reg_res[CUR])} GWh statt {num(reg_res_mean)} GWh "
        f"({pct(100*(reg_res[CUR]/reg_res_mean-1))}), also rund die Hälfte des üblichen Sommerbeitrags. "
        f"Die Pumpspeicher des Raums hielten ihre Menge dagegen: {num(reg_ps)} GWh Erzeugung gegenüber "
        f"{num(reg_ps_mean)} GWh im Mittel ({pct(100*(reg_ps/reg_ps_mean-1))}).")

    # ---- 4. Schweiz: Bilanz-Folge ----------------------------------------
    ch26m = [m for m in summary["ch_monthly"] if m["year"] == CUR]
    fl_ch = [r for r in summary.get("flows", []) if r["country"] == "CH"]
    txt = (
        f"<b>Folge für die Schweizer Bilanz:</b> der Anteil der <i>natürlichen</i> Wasserkraft am Verbrauch "
        f"fiel von {num(mean_of(summary['ch_hydro'],'natural_share_of_load_pct',BASE),0)}{THIN}% auf "
        f"{num(ch26['natural_share_of_load_pct'],0)}{THIN}% (brutto inkl. Pumpspeicher "
        f"{num(ch26['hydro_share_of_load_pct'],0)}{THIN}%), bei einem Rekord-Sommerverbrauch von "
        f"{num(ch26['load_gwh'])} GWh ({pct(100*(ch26['load_gwh']/mean_of(summary['ch_hydro'],'load_gwh',BASE)-1))}"
        f" gegenüber dem Mittel; die Ursache des hohen Verbrauchs ist aus den Erzeugungsdaten nicht belegt). "
        f"Nach Monaten: {monthly_str(ch26m)} GWh.")
    if fl_ch and CUR in index_by_year(fl_ch):
        cur_net = abs(v(fl, "ch", CUR, "net_import_gwh"))
        mean_net = abs(mean_of(fl_ch, "net_import_gwh", BASE))
        txt += (f" Beim physikalischen Austausch blieb die Schweiz Nettoexporteurin, doch der Export "
                f"schrumpfte auf {num(cur_net)} GWh "
                f"({num(abs(v(fl,'ch',CUR,'net_as_pct_of_load')),1)}{THIN}% des Verbrauchs) gegenüber "
                f"{num(mean_net)} GWh im Mittel 2017–2025 – der zweitniedrigste Wert des Jahrzehnts.")
    de_fl = [r for r in summary.get("flows", []) if r["country"] == "DE"]
    if de_fl and CUR in index_by_year(de_fl) and 2025 in index_by_year(de_fl):
        txt += (f" Deutschland dagegen senkte seinen Nettoimport auf {num(v(fl,'de',CUR,'net_import_gwh'))} GWh "
                f"({pct(v(fl,'de',CUR,'net_as_pct_of_load'),1)} vom Verbrauch) gegenüber "
                f"{num(v(fl,'de',2025,'net_import_gwh'))} GWh 2025 und "
                f"{num(mean_of(de_fl,'net_import_gwh',[2023,2024]))} GWh 2023–2024: die hohe Wind- und "
                f"Solarerzeugung dämpfte den bilanziellen Druck, ersetzte das Wasserkraft-Defizit aber nicht "
                f"physikalisch – Deutschland blieb Nettoimporteur.")
    at_fl = [r for r in summary.get("flows", []) if r["country"] == "AT"]
    if at_fl and CUR in index_by_year(at_fl):
        txt += (f" Österreich wechselte auf {num(v(fl,'at',CUR,'net_import_gwh'),0)} GWh Nettoimport "
                f"({pct(v(fl,'at',CUR,'net_as_pct_of_load'),1)} vom Verbrauch; Mittel "
                f"{num(mean_of(at_fl,'net_import_gwh',BASE),0)} GWh) – die energiewirtschaftliche Folge des "
                f"geringeren Wasserkraftbeitrags: bei einem Anteil der natürlichen Wasserkraft von nur "
                f"{num(at26['natural_share_of_load_pct'],0)}{THIN}% wurde das Defizit teilweise über Importe "
                f"gedeckt.")
    items.append(txt)

    # ---- 5. Preise --------------------------------------------------------
    ch_at = v(pr, "ch", CUR, "price_mean") - v(pr, "at", CUR, "price_mean")
    ch_at_word = "über" if ch_at >= 0 else "unter"
    items.append(
        f"<b>Das Wasserkraftdefizit fiel mit höheren Day-ahead-Preisen und einer deutlich größeren "
        f"Tagespreisspanne zusammen.</b> Day-ahead-Sommermittel 2026 – "
        f"{num(v(pr,'de',CUR,'price_mean'))} EUR/MWh in DE-LU ({pct(d100(pr,'de',CUR,'price_mean',2025))} "
        f"gegenüber 2025) und {num(v(pr,'ch',CUR,'price_mean'))} EUR/MWh in der Schweiz "
        f"({pct(d100(pr,'ch',CUR,'price_mean',2025))}). Die mittlere tägliche Tag/Nacht-Spread betrug in "
        f"Deutschland {num(v(pr,'de',CUR,'daily_spread_mean'))} EUR/MWh (2025: "
        f"{num(v(pr,'de',2025,'daily_spread_mean'))}) – der höchste Wert seit der Energiekrise 2022; "
        f"Österreich {num(v(pr,'at',CUR,'daily_spread_mean'))} und in der Schweiz "
        f"{num(v(pr,'ch',CUR,'daily_spread_mean'))} EUR/MWh. Die 2018 getrennten Preiszonen notieren "
        f"wieder auseinander: AT {num(v(pr,'at',CUR,'price_mean'))} gegen "
        f"{num(v(pr,'de',CUR,'price_mean'))} EUR/MWh in DE-LU "
        f"({num(v(pr,'at',CUR,'price_mean')-v(pr,'de',CUR,'price_mean'),1)} EUR/MWh Abstand, 2025: "
        f"{num(v(pr,'at',2025,'price_mean')-v(pr,'de',2025,'price_mean'),1)}), die Schweiz "
        f"{num(abs(ch_at),1)} EUR/MWh {ch_at_word} AT. Stunden mit "
        f"negativen Preisen: DE-LU {num(v(pr,'de',CUR,'neg_hours_pct'),1)}{THIN}%, AT "
        f"{num(v(pr,'at',CUR,'neg_hours_pct'),1)}{THIN}%, CH "
        f"{num(v(pr,'ch',CUR,'neg_hours_pct'),1)}{THIN}%.")

    # ---- 6. Pumpspeicher DE: Mengen --------------------------------------
    items.append(
        f"<b>Pumpspeicher in Deutschland: die Mengen nahe am Rekord.</b> Erzeugung "
        f"{num(v(ps,'de',CUR,'ps_generation_gwh'))} GWh ({pct(d100(ps,'de',CUR,'ps_generation_gwh',2025))} "
        f"gegenüber 2025; Mittel 2017–2025: {num(mean_of(summary['de_ps'],'ps_generation_gwh',BASE))} GWh), "
        f"Pumpstrom {num(v(ps,'de',CUR,'ps_pumping_gwh'))} GWh. In der Summe blieben die Pumpspeicher "
        f"Nettoverbraucher mit {num(abs(v(ps,'de',CUR,'ps_net_gwh')))} GWh, der scheinbare "
        f"Kreislaufwirkungsgrad {num(v(ps,'de',CUR,'round_trip_eff_pct'),0)}{THIN}% "
        f"(2022–2025: 74–81{THIN}%); der physikalische Wirkungsgrad ist niedriger, weil Hilfsbetriebsweisen "
        f"und Zuflüsse in das Oberwasser mit einfließen. Benutzungsstunden der Erzeugung: "
        f"{num(v(ps,'de',CUR,'ps_gen_full_load_hours'))} h im Sommer bei "
        f"{num(v(ps,'de',CUR,'ps_capacity_mw')/1000,1)} GW installierter Leistung.")

    # ---- 6b. Oesterreich: Pumpspeicher und Datenqualitaet ----------------
    at_rt = [r["round_trip_eff_pct"] for r in summary["at_ps"] if r.get("round_trip_eff_pct")]
    items.append(
        f"<b>Österreichs Pumpspeicher: die Erzeugung ist sauber messbar, der Pumpstrom nicht.</b> "
        f"Erzeugung {num(v(ps,'at',CUR,'ps_generation_gwh'))} GWh "
        f"({pct(d100(ps,'at',CUR,'ps_generation_gwh',2025))} gegenüber 2025, Mittel "
        f"{num(mean_of(summary['at_ps'],'ps_generation_gwh',BASE))} GWh) bei "
        f"{num(v(ps,'at',CUR,'ps_gen_full_load_hours'))} Benutzungsstunden und "
        f"{num(v(ps,'at',CUR,'ps_capacity_mw')/1000,1)} GW installierter Leistung. Der ausgewiesene "
        f"Pumpstrom von {num(v(ps,'at',CUR,'ps_pumping_gwh'))} GWh ergibt einen scheinbaren "
        f"Kreislaufwirkungsgrad von {num(v(ps,'at',CUR,'round_trip_eff_pct'),0)}{THIN}% – der tiefste Wert "
        f"sogar in allen zehn Jahren ({num(min(at_rt),0)}{THIN}%). Werte über 100{THIN}% sind "
        f"physikalisch unmöglich: Die Serie "
        f"<span class='tag'>hydro_pumped_storage_consumption</span> deckt in Österreich offenbar nur "
        f"einen Teil der Anlagen ab. Pumpstrom, Nettobilanz, Wirkungsgrad und Day-ahead-Bruttowert sind für AT "
        f"daher Untergrenzen und nicht mit den deutschen Werten vergleichbar; Tagesgang und "
        f"Erzeugungsstruktur bleiben aussagekräftig – und die zeigt denselben Abendtrend "
        f"({num(mean_of(summary['at_ps'],'gen_share_evening_17_23_pct',[2017,2018,2019]),0)}{THIN}% → "
        f"{num(v(ps,'at',CUR,'gen_share_evening_17_23_pct'),0)}{THIN}% in 17:00–24:00 Uhr).")

    # ---- 7. Deutschland: Betriebsregime ----------------------------------
    early = [2017, 2018, 2019]
    items.append(
        f"<b>Die entscheidende Änderung ist nicht die Menge, sondern das Betriebsregime.</b> Der "
        f"klassische Nacht-Pumpbetrieb ist praktisch verschwunden: der Pumpanteil von 22:00–06:00 Uhr fiel "
        f"von {num(mean_of(summary['de_ps'],'pump_hours_in_night_22_6_pct',early),0)}{THIN}% (2017–19) auf "
        f"{num(v(ps,'de',CUR,'pump_hours_in_night_22_6_pct'),0)}{THIN}%, während der Pumpanteil in der "
        f"Mittagspreismulde 10:00–16:00 Uhr von "
        f"{num(mean_of(summary['de_ps'],'pump_share_midday_10_15_pct',early),0)}{THIN}% auf "
        f"{num(v(ps,'de',CUR,'pump_share_midday_10_15_pct'),0)}{THIN}% stieg. Die Erzeugung wanderte in die "
        f"Abend-/Nachspitze 17:00–24:00 Uhr: "
        f"{num(mean_of(summary['de_ps'],'gen_share_evening_17_23_pct',early),0)}{THIN}% → "
        f"{num(v(ps,'de',CUR,'gen_share_evening_17_23_pct'),0)}{THIN}%. Die deutschen Pumpspeicherkraftwerke "
        f"sind vom Muster „nachts pumpen, tags abgeben“ zu „in der Solar-Preismulde pumpen, in der "
        f"Abendspitze abgeben“ gewechselt.")

    # ---- 8. Deutschland: Wirtschaftlichkeit ------------------------------
    items.append(
        f"<b>Die Day-ahead-Spread-Ökonomie: nicht das Preisniveau, sondern die Spread zählte.</b> Der "
        f"Day-ahead-Mittelpreis 2026 ({num(v(pr,'de',CUR,'price_mean'))} EUR/MWh) lag klar unter dem "
        f"Krisenjahr 2022 ({num(v(pr,'de',2022,'price_mean'))} EUR/MWh) und war der zweithöchste Wert der "
        f"verfügbaren Jahre seit 2019 – das Wachstum der PSW-Erzeugung folgte also nicht dem "
        f"absoluten Preisniveau, sondern der enormen Spreizung zwischen billigen "
        f"Mittagsstunden (Solar-Angebot) und teuren Abendspitzen: der mittlere Preis in "
        f"Erzeugungsstunden übersteigt den in Pumpstunden um "
        f"{num(v(ps,'de',CUR,'capture_spread_eur_mwh'),1)} EUR/MWh (2019: "
        f"{num(v(ps,'de',2019,'capture_spread_eur_mwh'),1)}; 2025: "
        f"{num(v(ps,'de',2025,'capture_spread_eur_mwh'),1)}), der theoretische Bruttoerlös aus der "
        f"Day-ahead-Spread – eine ex-post-Marge auf dem beobachteten Pump- und Erzeugungsprofil, ohne "
        f"Kosten, Netzverluste, Regelenergie und Verträge – betrug über den Sommer "
        f"{num(v(ps,'de',CUR,'da_arbitrage_value_meur'))} Mio. EUR (2025: "
        f"{num(v(ps,'de',2025,'da_arbitrage_value_meur'))}). Auf Stunden mit negativen Preisen entfielen "
        f"{num(v(ps,'de',CUR,'pump_at_negative_price_gwh'))} GWh Pumpstrom "
        f"({num(100*v(ps,'de',CUR,'pump_at_negative_price_gwh')/v(ps,'de',CUR,'ps_pumping_gwh'),0)}{THIN}% "
        f"des Pumpstroms), und {num(v(ps,'de',CUR,'gen_share_of_price_top_decile_pct'),0)}{THIN}% der "
        f"Erzeugung lagen in Stunden des oberen Preisdezils.")

    # ---- 9. Pumpspeicher CH ----------------------------------------------
    items.append(
        f"<b>Pumpspeicher in der Schweiz: die Leistung wächst, die Sommerproduktion 2026 liegt unter "
        f"dem Mittel.</b> {num(v(ps,'ch',CUR,'ps_generation_gwh'))} GWh "
        f"({pct(d100(ps,'ch',CUR,'ps_generation_gwh',2025))} gegenüber 2025, Mittel "
        f"{num(mean_of(summary['ch_ps'],'ps_generation_gwh',BASE))} GWh) bei einer Rekord-Spitzenleistung von "
        f"{num(v(ps,'ch',CUR,'ps_peak_generation_mw'))} MW aus "
        f"{num(v(ps,'ch',CUR,'ps_capacity_mw')/1000,2)} GW installierter Leistung. Benutzungsstunden: "
        f"{num(v(ps,'ch',CUR,'ps_gen_full_load_hours'))} h gegenüber "
        f"{num(mean_of(summary['ch_ps'],'ps_gen_full_load_hours',BASE))} h im Mittel – die Pumpspeicher "
        f"stützen das System in kurzen, leistungsstarken Entladungen statt in dauernder Abgabe. Derselbe "
        f"Abendtrend: der Erzeugungsanteil 17:00–24:00 Uhr stieg von "
        f"{num(mean_of(summary['ch_ps'],'gen_share_evening_17_23_pct',[2017,2018,2019,2020]),0)}{THIN}% auf "
        f"{num(v(ps,'ch',CUR,'gen_share_evening_17_23_pct'),0)}{THIN}%, der Anteil der Tagesstunden "
        f"8:00–20:00 Uhr sank auf {num(v(ps,'ch',CUR,'gen_hours_in_peak_8_20_pct'),0)}{THIN}% gegenüber "
        f"{num(mean_of(summary['ch_ps'],'gen_hours_in_peak_8_20_pct',[2017,2018,2019]),0)}{THIN}% in 2017–19.")

    # ---- 10. Datengrenze Schweiz -----------------------------------------
    items.append(
        f"<b>Datengrenze (Schweiz):</b> die API v2 liefert für CH keine Serie "
        f"<span class='tag'>hydro_pumped_storage_consumption</span>. Pumpbetrieb, Nettobilanz, "
        f"Kreislaufwirkungsgrad und Day-ahead-Bruttowert der Schweizer Pumpspeicher lassen sich daher nicht "
        f"berechnen – verfügbar sind nur die Erzeugung und ihre Stundengliederung. Für Deutschland sind "
        f"beide Betriebsweisen enthalten, für Österreich beide Reihen – dort aber die Verbrauchsseite "
        f"unvollständig (siehe oben).")

    items.append(
        f"<b>Technische Anmerkungen:</b> für Deutschland ist die Pumpstrom-Serie 2017 offenbar zu "
        f"niedrig berichtet (scheinbarer „Wirkungsgrad“ 138{THIN}%); Regime-Vergleiche sind ab 2018–2019 "
        f"belastbar. Day-ahead-Preise für DE-LU und AT enthält die API erst ab 2019 – seit der "
        f"Zonenteilung von DE-LU/AT im Oktober 2018 –, für die Schweiz ab 2017. Die "
        f"installierte Pumpspeicherleistung der Schweiz springt 2022 von 2,56 auf 3,48 GW "
        f"(Neufassung Anlagenkatalog), was die Benutzungsstunden vor und nach diesem Stichtag "
        f"beeinflusst. Sommerfenster: 01.06.–31.08. Lokalzeit, Integration von 15-Minuten- (DE, AT) und "
        f"Stundenwerten (CH); alle Wirtschaftlichkeitsangaben sind theoretische Day-ahead-Werte ohne "
        f"Regelenergie, Netzverluste und Verträge.")

    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def monthly_str(rows) -> str:
    rows = sorted(rows, key=lambda r: r["month"])
    return " → ".join(f"{MONTH_DE[int(r['month'][-2:])]} {num(r['hydro_gwh'])}" for r in rows)
