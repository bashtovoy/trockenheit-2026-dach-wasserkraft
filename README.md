# Wasserkraft und Pumpspeicher im DACH-Raum: Deutschland, Österreich, Schweiz, Sommer 2026

Analyse der Wasserkraft und der Pumpspeicherkraftwerke (PSW) im **Alpenraum (DACH)** –
**Deutschland**, **Österreich** und die **Schweiz** – im Sommer 2026 (1. Juni – 31. August) im
Vergleich zu 2017–2025. Ziel ist ein einheitliches Bild des alpinen Wasserkraft- und
Pumpspeichersystems über alle drei Länder.

Datenbasis: [energy-charts.info API v2](https://api.energy-charts.info/) (Fraunhofer ISE), Lizenz **CC BY 4.0**.
Unabhängige Wetterdaten für Abschnitt 5: [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
mit dem Reanalyse-Datensatz **ERA5** (Copernicus Climate Change Service, C3S) – Tageswerte für
2-m-Temperatur, Niederschlag und Kurzwellenstrahlung. ERA5 wird vom ECMWF/C3S bereitgestellt und ist
frei unter einer Namensnennungs-Lizenz nutzbar; die hier verwendeten Werte werden über Open-Meteo bezogen
(kein API-Schlüssel erforderlich).

**Trockenheits-Indikator (energiestatistisch):** die *natürliche Wasserkraft* = Laufwasser +
Speicherwasser. Pumpspeicher (PSW) hängen nicht vom Abfluss ab – sie sind ein Speicher, der zuerst
Strom aufnimmt – und werden daher getrennt ausgewiesen, statt das Trockenheitssignal zu maskieren.
Es ist ein Maß für die **energetische Wirkung** des Wasserdefizits, kein meteorologischer Dürreindex
(die Speicherwasser-Erzeugung hängt neben dem Zufluss auch von Speicherstand und Bewirtschaftung ab).
Alle Last-Anteile sind **energiegewichtet** (Σ Erzeugung / Σ Last), nicht das zeitliche Mittel der
Intervall-Percentwerte.

## Datenstand und Reproduzierbarkeit

| | |
|---|---|
| Data retrieval (Snapshot) | **2026-10-02** |
| Energy-Charts API | **v2** |
| Analysefenster | **01.06 – 31.08** (Sommer) |
| Referenzperiode | **2017 – 2025** (Mittel) |
| Vergleichsjahr | **2026** |

Die API aktualisiert historische Reihen fortlaufend (aktuell bis Ende September 2026). Die
Kennzahlen dieses Berichts wurden auf dem oben genannten Snapshot berechnet; ein späterer
Durchlauf kann daher leicht abweichende Werte liefern.

## Ergebnisse

Interaktiver Bericht: [`output/report.html`](output/report.html) – 27 Diagramme (Chart.js) und
vollständige Jahrestabellen für alle drei Länder. Alle Zahlen im Abschnitt „Fazit“ werden aus den
Daten generiert und können nicht von den Tabellen abweichen.

Wichtigste Befunde:

* **Dürre-Maßstab, natürliche Wasserkraft:** DE + AT + CH erzeugten im Sommer 2026 zusammen
  18 415 GWh Lauf- und Speicherwasser gegenüber 27 345 GWh im Mittel (−32,7 %) – rund ein Drittel.
  Alle drei Länder lagen gleichzeitig auf dem tiefsten Stand des Jahrzehnts (DE −30,8 %, AT −34,7 %,
  CH −31,9 %). Rechnet man die Pumpspeicher hinzu („Wasserkraft gesamt“ = 23 342 GWh, −27,2 %),
  fällt der ausgewiesene Rückgang milder aus – die überdurchschnittliche PSW-Erzeugung (4 928 GWh,
  +4,8 %) maskiert den eigentlichen Wassermangel, besonders in Deutschland.
* **Gleichzeitigkeit:** Die Daten zeigen ein gleichzeitig auftretendes Wasserkraftdefizit über alle
  drei Länder – ein überregionales hydrologisches Signal; ob es ein einheitliches Witterungsereignis
  war, lässt sich aus den Erzeugungsdaten allein nicht abschließend belegen.
* **Österreich** – der stärkste Rückgang: 7 452 GWh gesamt (−33 %); zuerst traf es das Laufwasser
  (−33 %), Speicherwasser −45 %. Der Anteil der *natürlichen* Wasserkraft an der Last fiel auf
  47,7 % (brutto inkl. PSW 55,5 %) – so tief wie nie im Jahrzehnt – und Österreich wechselte vom
  Nettoexport zum Nettoimport (1 430 GWh).
* **Schweiz**: 9 137 GWh gesamt (−30 %, ebenfalls schlechtester Sommer des Jahrzehnts); die
  Erzeugung aus Speicherwasserkraft sank auf 3 053 GWh gegenüber 5 901 GWh im Mittel (−48 %). Der
  Anteil der natürlichen Wasserkraft an der Last fiel auf 47,0 % (brutto 53,2 %); der Nettoexport
  schrumpfte auf 2 147 GWh gegenüber 4 175 GWh im Mittel.
* **Deutschland**: 6 754 GWh gesamt (−15 %, Platz 9 von zehn), aber natürliche Wasserkraft −30,8 %
  (Tiefstwert, Platz 1 von 10) – der milde Gesamtwert ist der hohen PSW-Erzeugung geschuldet. Da
  Wind (inkl. Offshore, 27 252 GWh) und Solar hoch liefen (EE-Anteil 68,5 %, energiegewichtet), war der
  bilanzielle Druck gering; ein Ersatz des Defizits ist das aber nicht, denn Deutschland blieb Nettoimporteur.
* **Pumpspeicher**: Deutschland – Mengen nahe am Rekord (Erzeugung 2 819, Pumpstrom 3 635 GWh), aber
  **neues Betriebsregime**: Nacht-Pumpen 57 % → 4 %, Mittagspumpen (10–16 Uhr) 26 % → 71 %,
  Abend-Erzeugung (17–24 Uhr) 52 % → 74 %. Capture-Spread 134,6 €/MWh, theoretischer Day-ahead-Bruttowert des
  Sommerzyklus ≈ 345 Mio. €. Derselbe Abendtrend in Österreich (50 % → 74 %) und der Schweiz (43 % → 58 %).
* **Preise**: DE-LU 114,0 €/MWh, AT 124,2 €/MWh, CH 119,6 €/MWh (alle deutlich über 2025). Die 2018
  getrennten Preiszonen DE-LU und AT notieren wieder auseinander (AT +10,2 €/MWh über DE-LU).
* **Meteorologisch → Wasserbilanz → Energie (Abschnitt 5, ERA5-unabhängig):** Die unabhängige
  Wetterprüfung ist als physikalische Kette aufgebaut. Kernstück ist die **Sommerwasserbilanz
  D = Niederschlag − ET₀** (ET₀ = FAO-56-Referenzverdunstung); Temperatur und Strahlung gehen damit als
  *verdunstungswirksame Nachfrage* ein, statt als separate Grob-Proxies. Über die zehn Sommer (n = 10)
  zeigt D die **stärkste beobachtete bikivariate Kopplung** mit der natürlichen Wasserkraft: **DE
  r = +0,78 (p = 0,008), AT r = +0,72 / Spearman ρ = +0,76 (p = 0,011)** – als zusammengesetzter Wert
  (P − ET₀) ist das die stärkste *Korrelation*, kein ursächlicher Top-Treiber; in DE bleibt der Rangtest
  knapp unter 0,05 (ρ = +0,62, p(ρ) = 0,054). Am direktesten kovoariert D mit dem **Laufwasser** (abflussnah;
  DE r = +0,81, AT r = +0,73) – der Speicherwasser-Anteil folgt zusätzlich der Bewirtschaftung. Die
  **Schweiz** bleibt im selben Sommer schwach gepuffert (D r = +0,24, p > 0,05), doch der
  **Frühlingsniederschlag** (Mär–Mai) als Vorlaufsignal erreicht **r = +0,70 (p = 0,024)** – konsistent mit
  der alpinen Speicher-/Schneepufferung. Monatsanomalien bestätigen das DE/AT-Muster auch im
  **Year-Block-Permutationstest** (DE r = +0,62, p_B = 0,002; AT r = +0,54, p_B = 0,006). Der gegen die
  **Klimanormal 1991–2020** standardisierte D ist als **Saisonaler Wasserbilanz-Index Z_JJA** ausgewiesen
  (μ/σ aus den 30 Sommer-Summen 1991–2020; transparente z-Transformierte, **bewusst kein SPEI** – keine
  log-logistic-Wahrscheinlichkeitstransformation). Es bleibt eine **explorative Korrelation, kein
  Kausalnachweis**; die p-Werte sind **nicht auf Mehrfachvergleiche adjustiert**, bei kleinem Stichprobenumfang.

## Methode des Wetter-Blocks (Abschnitt 5)

* **Raster statt Schwerpunkt:** Pro Land wird ein **alpin fokussiertes Raster** repräsentativer Zellen
  (dort läuft die Wasserkraft) definiert; die Tageswerte aller Zellen werden pro Land **unkewichtet**
  gemittelt. (Als grobe Näherung für die vom Audit empfohlene Becken-Gewichtung; es ist *keine* echte
  Einzugsgebiets-/Kapazitätsgewichtung, echte Shapefiles werden nicht aufgelöst.)
* **Wasserbilanz als integrierter Treiber:** D = P − ET₀ (mm über Juni–August), dazu die Rohdriver
  Temperatur, Niederschlag, Globstrahlung und ET₀ einzeln. D ist ein *meteorologischer*
  Wasserbilanz-Proxy für den atmosphärischen Wasserhaushalt – **nicht** die tatsächliche
  Beckenabfluss-Bilanz (zwischen P−ET₀ und Abfluss liegen Schnee-/Gletscher- und
  Boden-/Grundwasserspeicher). Primäre Kopplung: D → **Laufwasser**
  (abflussnah); sekundär: D → natürliche Wasserkraft; separat: D → Speicherwasser (Bewirtschaftung).
* **Zwei Baselines (getrennt, wie vom Audit empfohlen):** (1) **Klimabasis 1991–2020** (feste
  WMO-Normal) für die Standardisierung der Wettervariablen zu z-Werten / dem **Saisonalen
  Wasserbilanz-Index Z_JJA** (μ/σ aus den 30 *Sommer-Summen*, nicht aus Einzelmonaten); (2)
  **Energiebasis 2017–2025** für die Erzeugungsanomalie, weil energy-charts keine frühere
  Erzeugungsreihe führt. Diese Asymmetrie ist Absicht und dokumentiert. Auch die y-Achse des
  Scatter-Diagramms (% natürliche Wasserkraft) bezieht sich auf das **2017–2025**-Mittel, damit der
  Punkt 2026 nicht gegen eine Norm gesetzt wird, die 2026 selbst enthält. Es wird bewusst **kein echter
  SPEI** gerechnet (keine log-logistic-Anpassung/Wahrscheinlichkeitstransformation).
* **Zwei Korrelations-Körner:** (1) **jährlich** über zehn aufeinanderfolgende Sommer (n = 10;
  wegen der kurzen Zeitreihe nur **explorativ** – Inter-Jahres-Autokorrelation wird nicht modelliert);
  (2) **monatlich** als **Binnen-Monats-Anomalie** – Wert minus Klimatologie derselben Land-Monat-Zelle –,
  damit der saisonale Gang (Juni > August) nicht als Korrelation durchgeht. Die Monatsbeobachtungen sind
  binnen einer Saison **nicht unabhängig** (Juni–August + Autokorrelation), deshalb ist der Student-t-p
  dort zu optimistisch; zusätzlich wird ein **Year-Block-Permutationstest (p_B)** ausgewiesen,
  der ganze Sommer vertauscht (~10 000 Permutationen, fester Seed).
* **Vorlaufsignal:** Frühlingsniederschlag (Mär–Mai) → Sommer-Wasserkraft als Ersatz für den
  Schnee-/Vorlaufspeicher (SWE liegt in der gewählten langen ERA5-Tagesreihe nicht vor, s. Datengrenzen).
* **Zwei Koeffizienten:** **Pearson r** (linear) und **Spearman ρ** (monoton, robust bei kleinem n),
  je mit zweiseitigem p-Wert über die Student-t-Verteilung (Freiheitsgrad n − 2), ohne scipy – die
  reguläre unvollständige Beta wird per Kettenbruch (Lentz) ausgewertet. Die p-Werte über das gesamte
  Testfeld (3 Länder × mehrere Treiber × 2 Körner) sind **explorativ und nicht auf Mehrfachvergleiche
  adjustiert** (kein FDR). Eine multivariate Regression H ~ P+T+Solar wird bei n = 10 und kollinearen
  Fahrern bewusst **nicht** als robust ausgewiesen.
* **Modellkonstanz:** durchgehend **ERA5** (single reanalysis) über `archive-api.open-meteo.com`, kein
  „Best-Match“-Modelmixing – wichtig, damit kein Modellwechsel als Klimateffekt durchgeht.
* **Skript:** `scripts/fetch_weather.py` (Abruf + gzip-Cache in `data/raw/`, inkl. ET₀),
  `scripts/weather_analysis.py` (Kennzahlen → `summary["weather"]`, von `analyze.py` automatisch
  aufgerufen, wenn Wetter-Cache vorhanden ist).

## Struktur

```
scripts/fetch_data.py     Abruf aus der API (fortsetzbarer gzip-Cache in data/raw, HTTP-429-Behandlung)
scripts/fetch_flows.py    ergänzender Abruf der Grenzüberschreitungsflüsse (/v2/cbpf)
scripts/fetch_weather.py  ERA5-Tageswetter (Open-Meteo Archive) über alpine Rasterzellen, gzip-Cache
scripts/analyze.py        Kennzahlen → CSV in output/ + summary.json (ruft weather_analysis.py auf)
scripts/weather_analysis.py  Korrelation Wetter × Wasserkraft → summary["weather"]
scripts/findings.py       automatisch generiertes „Fazit“ (Zahlen aus summary.json)
scripts/build_report.py   Zusammenstellung von output/report.html
data/raw/                 Cache der API-Antworten (nicht im Repository, wird vom Skript neu erzeugt)
output/                  Berechnete Tabellen und fertiger Bericht
```

## Ausführung

Python 3.10+ und pandas erforderlich (`pip install pandas certifi`).

```bash
# 1. Daten laden: 10 Jahre × (Erzeugung, Preise, installierte Leistung) × DE/AT/CH
python3 scripts/fetch_data.py --years 2017-2026 --sleep 15

# 2. Grenzüberschreitende Flüsse (optional, für Abschnitt 4)
python3 scripts/fetch_flows.py 2017-2026

# 2b. Unabhängiges Wetter ERA5 (optional, für Abschnitt 5) – Open-Meteo, kein Schlüssel
python3 scripts/fetch_weather.py

# 3. Berechnung und Bericht
python3 scripts/analyze.py
python3 scripts/build_report.py
open output/report.html
```

**Wichtig zur API:** die Endpunkte liefern 15-Minuten-Daten (DE, AT) bzw. Stundenwerte (CH) für drei
Monate in einer Anfrage, drosseln aber aggressiv – etwa **eine Anfrage pro 10–15 Sekunden**
(HTTP 429 mit `retry-after`). Ein vollständiger Durchlauf über die drei Länder dauert 15–25 Minuten;
der Cache in `data/raw/` erlaubt Abbruch und Fortsetzung ohne erneuten Download.

## Datengrenzen

* Die Länder sind nicht in allen Reihen gleich tief abtastbar:
    * `hydro_pumped_storage_consumption` (Pumpstrom) existiert für DE und AT, für die **Schweiz nur die
      Erzeugung** – dort entfallen PSW-Wirkungsgrad, Netto und „Zyklen“.
    * Für **Österreich** ist die Verbrauchsseite unvollständig: der scheinbare
      Kreislaufwirkungsgrad liegt in allen zehn Jahren über 100 % (physikalisch unmöglich). Pumpstrom,
      Netto und Wirkungsgrad sind für AT daher **Untergrenzen** und nicht mit DE vergleichbar;
      Tagesgang und Erzeugungsstruktur bleiben aussagekräftig.
* Day-ahead-Preise: DE-LU und AT erst ab 2019 (Zonenteilung DE-LU/AT im Oktober 2018), CH ab 2017.
* Die installierte Wasserkraft-Leistung publiziert die API nur für Deutschland vollständig; für AT und
  CH fehlen einzelne Kategorien, daher ist dort die Benutzungsstundenspalte in der Wasserkraft-Tabelle
  leer.
* Der Pumpstrom 2017 in Deutschland ist offenbar unvollständig (scheinbarer Wirkungsgrad > 100 %) –
  im Bericht mit `pumping_data_suspect` gekennzeichnet.
* Der „theoretische Day-ahead-Bruttowert“ (beobachtetes Pump-/Erzeugungsprofil) ist eine rein
  theoretische Day-ahead-Betrachtung ohne Wirkungsgradverluste, Regelenergie, Netzengpässe,
 Opportunitätskosten des Wassers, Bietstrategien und Rahmenverträge konkreter Anlagen – er ist nicht die
  tatsächliche kommerzielle Rendite. Die 15-Minuten-Erzeugung wird dabei dem nächstliegenden
  Stundenpreis zugeordnet; die Bruttowerte sind richtungsgebend, nicht auf die letzte Dezimalstelle
  reproduzierbar.
* **Wetterkorrelation (Abschnitt 5):** ERA5 ist eine Reanalyse mit ca. 25–31 km Rasterauflösung; das
  alpin fokussierte, **unkewichtete** Raster ist eine grobe Näherung für das reale Einzugsgebiet der
  Kraftwerke (keine echte Becken-/Kapazitätsgewichtung). Der Jahres-Korrelationsumfang ist klein (n = 10),
  daher werden r und ρ immer mit p-Wert und n ausgewiesen und die Analyse ist **explorativ** – ein
  statistischer Zusammenhang, kein Kausalbeweis; die p-Werte sind **nicht auf Mehrfachvergleiche
  adjustiert**. Es wird kein expliziter Abfluss-/Hydrologiemodell gerechnet, sondern die Korrelation
  zwischen Wasserbilanz (D = P − ET₀) bzw. Wettervariablen und der beobachteten Erzeugung. Der
  standardisierte D ist ein **Saisonaler Wasserbilanz-Index Z_JJA** (einheitliche z-Transformierte der
  Sommer-Wasserbilanz gegen die 30 Sommer-Summen 1991–2020), **bewusst kein SPEI** (keine
  Verteilungsanpassung/Wahrscheinlichkeitstransformation). Die **Monatsanomalien** sind binnen einer
  Saison nicht unabhängig (Juni–August, Autokorrelation); der Student-t-p ist dort zu optimistisch, darum
  wird zusätzlich ein **Year-Block-Permutationstest (p_B)** angegeben (austauschbare ganze Jahresblöcke;
  keine Inter-Jahres-Abhängigkeit). **Snow Water Equivalent (SWE)**
  liegt in der gewählten langen ERA5-Tagesreihe **nicht** vor (Schneevariablen gibt es bei Open-Meteo nur
  in anderen Produkten wie ERA5-Land `snow_depth` oder CERRA `snow_depth_water_equivalent`, dessen Reihe
  Mitte 2021 endet); der alpine Vorlaufspeicher wird deshalb nur indirekt über den Frühlingsniederschlag
  (Mär–Mai) als Vorlaufsignal abgebildet.

## Datenlizenz

Die Energie- und Preisreihen stammen von ihren jeweiligen Quellen (ENTSO-E, SMARD, APG, Swissgrid,
EEX u. a.) und werden von Fraunhofer ISE über energy-charts.info unter CC BY 4.0 veröffentlicht. Bei
Nutzung: Quellenangabe `energy-charts.info — Fraunhofer ISE`.

Die Wetterdaten (Abschnitt 5) stammen aus dem Copernicus-ERA5-Reanalyse-Datensatz (ECMWF /
Copernicus Climate Change Service), bezogen über die Open-Meteo Historical Weather API. Bei Nutzung:
Quellenangabe `ERA5 (Copernicus Climate Change Service) via open-meteo.com`.
