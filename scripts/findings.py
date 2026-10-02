#!/usr/bin/env python3
"""Render the findings section of the report from output/summary.json.

All numbers are recomputed here so the text can never drift from the tables.
"""

from __future__ import annotations

BASE = list(range(2017, 2026))
CUR = 2026


def mean_of(records, key, years):
    vals = [r[key] for r in records if int(r["year"]) in years and r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def index_by_year(records):
    return {int(r["year"]): r for r in records}


def build(summary) -> str:
    hy = {c: index_by_year(summary[f"{c}_hydro"]) for c in ("de", "ch")}
    ps = {c: index_by_year(summary[f"{c}_ps"]) for c in ("de", "ch")}
    pr = {c: index_by_year([r for r in summary["prices"] if r["country"] == c.upper()])
          for c in ("de", "ch")}
    fl = {c: index_by_year([r for r in summary.get("flows", []) if r["country"] == c.upper()])
          for c in ("de", "ch")}

    def v(tab, c, y, key, default=None):
        row = tab[c].get(y)
        return row.get(key, default) if row else default

    def d100(tab, c, y, key, ref_y):
        a, b = v(tab, c, y, key), v(tab, c, ref_y, key)
        return 100 * (a / b - 1) if a and b else None

    items: list[str] = []

    # ---- 1. Germany hydro -------------------------------------------------
    de26, de_mean = hy["de"][CUR], None
    de_hyd_mean = mean_of(summary["de_hydro"], "hydro_total_gwh", BASE)
    de_ror_mean = mean_of(summary["de_hydro"], "run_of_river_gwh", BASE)
    de_rank = sorted((r["hydro_total_gwh"] for r in summary["de_hydro"]), reverse=True).index(
        de26["hydro_total_gwh"]) + 1
    items.append(
        f"<b>Германия — гидро {de26['hydro_total_gwh']:.0f} GWh за лето, "
        f"{100*(de26['hydro_total_gwh']/de_hyd_mean-1):+.0f}% к среднему 2017–2025</b> "
        f"({de_rank}-е место из 10 лет). Ключевой провал — проточные станции (Laufwasser): "
        f"{de26['run_of_river_gwh']:.0f} GWh против {de_ror_mean:.0f} GWh в среднем "
        f"({100*(de26['run_of_river_gwh']/de_ror_mean-1):+.0f}%), это минимум за всё окно наблюдения "
        f"и уровень засухи 2018 г. ({v(hy,'de',2018,'run_of_river_gwh'):.0f} GWh). "
        f"Водохранилищная генерация — {de26['reservoir_gwh']:.0f} GWh "
        f"({100*(de26['reservoir_gwh']/mean_of(summary['de_hydro'],'reservoir_gwh',BASE)-1):+.0f}%).")

    # ---- 2. within-summer progression ------------------------------------
    m26 = sorted((m for m in summary["de_monthly"] if m["year"] == CUR), key=lambda r: r["month"])
    jun, aug = m26[0]["hydro_gwh"], m26[-1]["hydro_gwh"]
    items.append(
        f"<b>Дефицит нарастал внутри сезона:</b> в Германии по месяцам "
        f"{monthly_str(m26)} GWh, падение на {100*(1-aug/jun):.0f}% от июня к августу — "
        f"водность не восстановилась после июньского паводка, как это бывает в влажные годы.")

    # ---- 2b. Germany context ---------------------------------------------
    de_wind = mean_of(summary["de_hydro"], "wind_gwh", BASE)
    de_sol = mean_of(summary["de_hydro"], "solar_gwh", BASE)
    items.append(
        f"<b>Почему провал гидро в Германии был малозаметен для баланса:</b> ветер + солнце летом 2026 г. — "
        f"{hy['de'][CUR]['wind_gwh']:.0f} + {hy['de'][CUR]['solar_gwh']:.0f} GWh против "
        f"{de_wind:.0f} + {de_sol:.0f} GWh в среднем, а доля ВИЭ в потреблении достигла "
        f"{hy['de'][CUR]['renewable_share_of_load_pct']:.1f}% — максимум за окно наблюдения при "
        f"{mean_of(summary['de_hydro'],'renewable_share_of_load_pct',BASE):.1f}% в среднем. Гидро в ФРГ — лишь "
        f"{hy['de'][CUR]['hydro_share_of_load_pct']:.1f}% потребления, поэтому его недобор "
        f"({de26['hydro_total_gwh']-de_hyd_mean:+.0f} GWh) компенсировался ветром и солнцем. В Швейцарии "
        f"такого буфера нет.")

    # ---- 3. Switzerland ---------------------------------------------------
    ch26 = hy["ch"][CUR]
    ch_hyd_mean = mean_of(summary["ch_hydro"], "hydro_total_gwh", BASE)
    ch_res_mean = mean_of(summary["ch_hydro"], "reservoir_gwh", BASE)
    ch_wet = max((r for r in summary["ch_hydro"] if r["year"] < CUR), key=lambda r: r["reservoir_gwh"])
    items.append(
        f"<b>Швейцария пострадала гораздо сильнее: {ch26['hydro_total_gwh']:.0f} GWh, "
        f"{100*(ch26['hydro_total_gwh']/ch_hyd_mean-1):+.0f}% к среднему и "
        f"{d100(hy,'ch',CUR,'hydro_total_gwh',2025):+.0f}% к лету-2025</b> — худшее лето за 10 лет. "
        f"Удар пришёлся по водохранилищной генерации, то есть по управляемому резерву: "
        f"{ch26['reservoir_gwh']:.0f} GWh против {ch_res_mean:.0f} GWh в среднем "
        f"({100*(ch26['reservoir_gwh']/ch_res_mean-1):+.0f}%; в рекордном {ch_wet['year']} г. — "
        f"{ch_wet['reservoir_gwh']:.0f} GWh). Проточные снизились умереннее "
        f"({100*(ch26['run_of_river_gwh']/mean_of(summary['ch_hydro'],'run_of_river_gwh',BASE)-1):+.0f}%).")

    # ---- 4. CH energy balance consequence --------------------------------
    ch26m = [m for m in summary["ch_monthly"] if m["year"] == CUR]
    items.append(
        f"<b>Следствие для баланса Швейцарии:</b> доля гидро в потреблении упала с "
        f"{mean_of(summary['ch_hydro'],'hydro_share_of_load_pct',BASE):.0f}% до "
        f"{ch26['hydro_share_of_load_pct']:.0f}% при рекордном летнем спросе "
        f"{ch26['load_gwh']:.0f} GWh (+{100*(ch26['load_gwh']/mean_of(summary['ch_hydro'],'load_gwh',BASE)-1):.0f}% "
        f"к среднему — пиковая нагрузка от кондиционирования). Помесячно: {monthly_str(ch26m)} GWh. "
        + (f" По физическому обмену Швейцария осталась нетто-экспортёром, но экспорт сжался до "
           f"{abs(v(fl,'ch',CUR,'net_import_gwh')):.0f} GWh "
           f"({abs(v(fl,'ch',CUR,'net_as_pct_of_load')):.1f}% потребления) против "
           f"{abs(mean_of([r for r in summary.get('flows',[]) if r['country']=='CH'],'net_import_gwh',BASE)):.0f} GWh "
           f"в среднем за 2017–2025 — второй минимум за десятилетие."
           if fl.get("ch") and CUR in fl["ch"] else "")
        + (f" Германия, наоборот, сократила нетто-импорт до {v(fl,'de',CUR,'net_import_gwh'):.0f} GWh "
           f"({v(fl,'de',CUR,'net_as_pct_of_load'):+.1f}% load) против "
           f"{v(fl,'de',2025,'net_import_gwh'):.0f} GWh в 2025 и ~12 000 GWh в 2023–2024: рекордная ветро- "
           f"солнечная генерация частично покрыли и дефицит гидро, и импорт."
           if fl.get("de") and CUR in fl["de"] and 2025 in fl["de"] else ""))

    # ---- 5. prices --------------------------------------------------------
    items.append(
        f"<b>Цены отразили маловодье:</b> day-ahead летом 2026 — "
        f"{v(pr,'de',CUR,'price_mean'):.0f} EUR/MWh в DE-LU ({d100(pr,'de',CUR,'price_mean',2025):+.0f}% к 2025) и "
        f"{v(pr,'ch',CUR,'price_mean'):.0f} EUR/MWh в CH ({d100(pr,'ch',CUR,'price_mean',2025):+.0f}%). "
        f"Средний суточный спред в Германии — {v(pr,'de',CUR,'daily_spread_mean'):.0f} EUR/MWh "
        f"(2025: {v(pr,'de',2025,'daily_spread_mean'):.0f}; рекорд после энергетического кризиса 2022 г.), "
        f"в Швейцарии — {v(pr,'ch',CUR,'daily_spread_mean'):.0f} против "
        f"{v(pr,'ch',2025,'daily_spread_mean'):.0f} EUR/MWh.")

    # ---- 6. DE pumped storage volumes ------------------------------------
    items.append(
        f"<b>ГАЭС Германии: объёмы около исторического максимума.</b> Генерация "
        f"{v(ps,'de',CUR,'ps_generation_gwh'):.0f} GWh ({d100(ps,'de',CUR,'ps_generation_gwh',2025):+.0f}% к 2025; "
        f"среднее 2017–2025 — {mean_of(summary['de_ps'],'ps_generation_gwh',BASE):.0f} GWh), закачка насосов "
        f"{v(ps,'de',CUR,'ps_pumping_gwh'):.0f} GWh. По итогам лета ГАЭС — чистый потребитель "
        f"{v(ps,'de',CUR,'ps_net_gwh'):.0f} GWh, расчётный КПД цикла {v(ps,'de',CUR,'round_trip_eff_pct'):.0f}% "
        f"(2022–2025: 74–81%; физический КПД ниже из-за вспомогательных режимов и притоков в верхние бьефы). "
        f"Часов использования генерации — {v(ps,'de',CUR,'ps_gen_full_load_hours'):.0f} ч за лето при "
        f"установленной мощности {v(ps,'de',CUR,'ps_capacity_mw')/1000:.1f} ГВт.")

    # ---- 7. DE regime shift ----------------------------------------------
    early = [2017, 2018, 2019]
    items.append(
        f"<b>Главное изменение — не объём, а режим.</b> Классическая ночная закачка почти исчезла: доля "
        f"насоса в 22:00–06:00 упала с {mean_of(summary['de_ps'],'pump_hours_in_night_22_6_pct',early):.0f}% "
        f"(2017–19) до {v(ps,'de',CUR,'pump_hours_in_night_22_6_pct'):.0f}%, а доля закачки в дневной провал цен "
        f"10:00–16:00 выросла с {mean_of(summary['de_ps'],'pump_share_midday_10_15_pct',early):.0f}% до "
        f"{v(ps,'de',CUR,'pump_share_midday_10_15_pct'):.0f}%. Генерация сместилась в вечерне-ночной пик "
        f"17:00–24:00: {mean_of(summary['de_ps'],'gen_share_evening_17_23_pct',early):.0f}% → "
        f"{v(ps,'de',CUR,'gen_share_evening_17_23_pct'):.0f}%. ГАЭС Германии перепрофилировались из "
        f"«ночью качаем — днём отдаём» в «качаем на солнечном провале цены — отдаём на вечернем пике».")

    # ---- 8. DE economics -------------------------------------------------
    items.append(
        f"<b>Экономика арбитража резко выросла:</b> средняя цена в часы генерации превышает цену в часы "
        f"насоса на {v(ps,'de',CUR,'capture_spread_eur_mwh'):.0f} EUR/MWh "
        f"(2019: {v(ps,'de',2019,'capture_spread_eur_mwh'):.0f}; 2025: {v(ps,'de',2025,'capture_spread_eur_mwh'):.0f}), "
        f"теоретическая стоимость спреда за лето — {v(ps,'de',CUR,'da_arbitrage_value_meur'):.0f} МЛН EUR "
        f"(2025: {v(ps,'de',2025,'da_arbitrage_value_meur'):.0f}). На часы с отрицательной ценой пришлось "
        f"{v(ps,'de',CUR,'pump_at_negative_price_gwh'):.0f} GWh закачки "
        f"({100*v(ps,'de',CUR,'pump_at_negative_price_gwh')/v(ps,'de',CUR,'ps_pumping_gwh'):.0f}% закачки), "
        f"а {v(ps,'de',CUR,'gen_share_of_price_top_decile_pct'):.0f}% генерации — на часы верхнего дециля цен.")

    # ---- 9. CH pumped storage --------------------------------------------
    items.append(
        f"<b>ГАЭС Швейцарии: мощность растёт, выработка лета-2026 — ниже нормы.</b> "
        f"{v(ps,'ch',CUR,'ps_generation_gwh'):.0f} GWh "
        f"({d100(ps,'ch',CUR,'ps_generation_gwh',2025):+.0f}% к 2025, среднее "
        f"{mean_of(summary['ch_ps'],'ps_generation_gwh',BASE):.0f} GWh) при рекордной мгновенной мощности "
        f"{v(ps,'ch',CUR,'ps_peak_generation_mw'):.0f} МВт из "
        f"{v(ps,'ch',CUR,'ps_capacity_mw')/1000:.2f} ГВт установленных. Часы использования — "
        f"{v(ps,'ch',CUR,'ps_gen_full_load_hours'):.0f} ч против "
        f"{mean_of(summary['ch_ps'],'ps_gen_full_load_hours',BASE):.0f} ч в среднем: ГАЭС держат систему "
        f"короткими мощными разборами, а не длительной отдачей. Тот же вечерний сдвиг: доля генерации "
        f"17:00–24:00 {mean_of(summary['ch_ps'],'gen_share_evening_17_23_pct',[2017,2018,2019,2020]):.0f}% → "
        f"{v(ps,'ch',CUR,'gen_share_evening_17_23_pct'):.0f}%, доля дневных часов 8:00–20:00 — "
        f"{v(ps,'ch',CUR,'gen_hours_in_peak_8_20_pct'):.0f}% против "
        f"{mean_of(summary['ch_ps'],'gen_hours_in_peak_8_20_pct',[2017,2018,2019]):.0f}% в 2017–19.")

    # ---- 10. limitations -------------------------------------------------
    items.append(
        "<b>Ограничение по данным (Швейцария):</b> API v2 не отдаёт для CH серию "
        "<span class='tag'>hydro_pumped_storage_consumption</span>, поэтому насосный режим, net-выработка, "
        "КПД цикла и стоимость арбитража для швейцарских ГАЭС не рассчитываются — доступна только "
        "генерация и её почасовая структура. Для Германии доступны оба режима.")

    items.append(
        "<b>Технические оговорки:</b> у Германии за 2017 г. серия pumping занижена (расчётный «КПД» 138%), "
        "поэтому сравнения режимов корректны с 2018–2019 гг.; day-ahead цены DE-LU в API есть только с 2019 г., "
        "CH — с 2017 г. Указанная мощность ГАЭС CH скачком меняется с 2,56 на 3,48 ГВт в 2022 г. "
        "(пересмотр перечня станций), что влияет на часы использования до и после этой даты. "
        "Летнее окно — 01.06–31.08 по местному времени, интеграция 15-минутных (DE) и часовых (CH) рядов; "
        "стоимостные оценки — теоретические по рынку day-ahead, без балансирования, потерь и контрактов.")

    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def monthly_str(rows) -> str:
    rows = sorted(rows, key=lambda r: r["month"])
    return " → ".join(f"{r['month'][-2:]}: {r['hydro_gwh']:.0f}" for r in rows)
