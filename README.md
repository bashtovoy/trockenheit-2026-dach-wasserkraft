# Wasserkraft und Pumpspeicher: Schweiz und Deutschland, Sommer 2026

Analyse der Wasserkraft und der Pumpspeicherkraftwerke (PSW) in der **Schweiz** und in
**Deutschland** im Sommer 2026 (1. Juni – 31. August) im Vergleich zu 2017–2025.

Datenbasis: [energy-charts.info API v2](https://api.energy-charts.info/) (Fraunhofer ISE), Lizenz **CC BY 4.0**.

## Ergebnisse

Interaktiver Bericht: [`output/report.html`](output/report.html) – 18 Diagramme (Chart.js) und
vollständige Jahrestabellen. Alle Zahlen im Abschnitt „Fazit“ werden aus den Daten generiert und
können nicht von den Tabellen abweichen.

Wichtigste Befunde:

* **Deutschland**: Wasserkraft 6 754 GWh (−15 % gegenüber dem Mittel 2017–25); Laufwasser 3 557 GWh –
  **Tiefstwert des Jahrzehnts**, 22 % unter dem Dürrejahr 2018. Speicherwasser −35 %.
* **Schweiz**: Wasserkraft 9 137 GWh (−30 %, **schlimmster Sommer des Jahrzehnts**); Speicherwasser
  3 053 GWh gegenüber 5 901 GWh im Mittel (−48 %). Der Wasserkraftanteil an der Last fiel von 85 % auf
  53 %, bei Rekordverbrauch. Nettoexport nur 2 147 GWh gegenüber 4 175 GWh im Mittel.
* **Pumpspeicher**: Deutschland – Mengen nahe am Rekord (Erzeugung 2 819, Pumpstrom 3 635 GWh), aber
  **neues Betriebsregime**: Nacht-Pumpen 57 % → 4 %, Mittagspumpen (10–16 Uhr) 26 % → 71 %,
  Abend-Erzeugung (17–24 Uhr) 52 % → 74 %. 976 GWh Pumpstrom fielen in Stunden mit negativen Preisen.
  Capture-Spread 134,6 €/MWh, theoretischer Arbitragewert des Sommerzyklus ≈ 345 Mio. €.
  In der Schweiz derselbe Abendtrend (42 % → 58 %).
* **Preise**: DE-LU 114,0 €/MWh (+49 % gegenüber 2017–25), CH 119,6 €/MWh (+53 %); die mittlere
  tägliche Spread in Deutschland ist der höchste Wert seit der Energiekrise 2022 – der direkte Treiber
  des geänderten PSW-Regimes.

## Struktur

```
scripts/fetch_data.py     Abruf aus der API (fortsetzbarer gzip-Cache in data/raw, HTTP-429-Behandlung)
scripts/fetch_flows.py    ergänzender Abruf der Grenzüberschreitungsflüsse (/v2/cbpf)
scripts/analyze.py        Kennzahlen → CSV in output/ + summary.json
scripts/findings.py       automatisch generiertes „Fazit“ (Zahlen aus summary.json)
scripts/build_report.py   Zusammenstellung von output/report.html
data/raw/                 Cache der API-Antworten (nicht im Repository, wird vom Skript neu erzeugt)
output/                  Berechnete Tabellen und fertiger Bericht
```

## Ausführung

Python 3.10+ und pandas erforderlich (`pip install pandas certifi`).

```bash
# 1. Daten laden: 10 Jahre × (Erzeugung, Preise, installierte Leistung) × DE/CH
python3 scripts/fetch_data.py --years 2017-2026 --sleep 15

# 2. Grenzüberschreitende Flüsse (optional, für Abschnitt 4)
python3 scripts/fetch_flows.py 2017-2026

# 3. Berechnung und Bericht
python3 scripts/analyze.py
python3 scripts/build_report.py
open output/report.html
```

**Wichtig zur API:** die Endpunkte liefern 15-Minuten-Daten (DE) bzw. Stundenwerte (CH) für drei
Monate in einer Anfrage, drosseln aber aggressiv – etwa **eine Anfrage pro 10–15 Sekunden**
(HTTP 429 mit `retry-after`). Ein vollständiger Durchlauf (~60 Anfragen) dauert 10–20 Minuten; der
Cache in `data/raw/` erlaubt Abbruch und Fortsetzung ohne erneuten Download.

## Datengrenzen

* `hydro_pumped_storage_consumption` (Pumpstrom stündlich) wird nur für Deutschland publiziert; für die
  Schweiz ist nur die Erzeugung verfügbar, daher entfallen PSW-Wirkungsgrad und „Zyklen“ für CH.
* DE-LU-Preise ab 2019 verfügbar, CH-Preise (SHP) ab 2017.
* Der Pumpstrom 2017 in Deutschland ist offenbar unvollständig (scheinbarer Wirkungsgrad > 100 %) –
  im Bericht mit `pumping_data_suspect` gekennzeichnet.
* Installierte PSW-Leistung der Schweiz ist nur bis 2025 publiziert (für 2026 wird der letzte Wert genutzt).
* Der „Arbitragewert“ ist eine theoretische Day-ahead-Betrachtung ohne Wirkungsgradverluste,
  Regelenergie und Rahmenverträge konkreter Anlagen.

## Datenlizenz

Die Energie- und Preisreihen stammen von ihren jeweiligen Quellen (ENTSO-E, SMARD, Swissgrid, EEX u. a.)
und werden von Fraunhofer ISE über energy-charts.info unter CC BY 4.0 veröffentlicht. Bei Nutzung:
Quellenangabe `energy-charts.info — Fraunhofer ISE`.
