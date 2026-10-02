# Wasserkraft und Pumpspeicher im DACH-Raum: Deutschland, Österreich, Schweiz, Sommer 2026

Analyse der Wasserkraft und der Pumpspeicherkraftwerke (PSW) im **Alpenraum (DACH)** –
**Deutschland**, **Österreich** und die **Schweiz** – im Sommer 2026 (1. Juni – 31. August) im
Vergleich zu 2017–2025. Ziel ist ein einheitliches Bild des alpinen Wasserkraft- und
Pumpspeichersystems über alle drei Länder.

Datenbasis: [energy-charts.info API v2](https://api.energy-charts.info/) (Fraunhofer ISE), Lizenz **CC BY 4.0**.

## Ergebnisse

Interaktiver Bericht: [`output/report.html`](output/report.html) – 24 Diagramme (Chart.js) und
vollständige Jahrestabellen für alle drei Länder. Alle Zahlen im Abschnitt „Fazit“ werden aus den
Daten generiert und können nicht von den Tabellen abweichen.

Wichtigste Befunde:

* **Gleichzeitigkeit des Trockenjahres:** DE + AT + CH erzeugten im Sommer 2026 zusammen 23 342 GWh
  Wasserkraft gegenüber 32 049 GWh im Mittel (−27 %) – es fehlen rund 8 700 GWh. Die
  Speicherwasserkraft (der steuerbare Bestand) halbierte sich beinahe (−47 %). Die Trockenheit war
  kein nationales, sondern ein alpines Ereignis.
* **Österreich** – der stärkste Rückgang: 7 452 GWh (−33 %, **Tiefstwert des Jahrzehnts**); zuerst traf
  es das Laufwasser (−33 %), Speicherwasser −45 %. Der Wasserkraftanteil an der Last fiel von 79 % auf
  55 % (so tief wie nie im Jahrzehnt) und Österreich wechselte vom Nettoexport zum Nettoimport
  (1 430 GWh, +10,6 % des Verbrauchs).
* **Schweiz**: 9 137 GWh (−30 %, ebenfalls schlechtester Sommer des Jahrzehnts); Speicherwasser
  3 053 GWh gegenüber 5 901 GWh im Mittel (−48 %). Anteil an der Last 85 % → 53 % bei Rekordverbrauch;
  Nettoexport schrumpfte auf 2 147 GWh gegenüber 4 175 GWh im Mittel.
* **Deutschland**: 6 754 GWh (−15 %, Platz 9 von zehn); Laufwasser 3 557 GWh – Tiefstwert des Fensters,
  22 % unter dem Dürrejahr 2018. Da Wind und Solar hoch liefen (EE-Anteil 67,8 %), fiel das
  Wasserkraft-Defizit bilanziell kaum auf – ein Puffer, den die Schweiz und Österreich nicht haben.
* **Pumpspeicher**: Deutschland – Mengen nahe am Rekord (Erzeugung 2 819, Pumpstrom 3 635 GWh), aber
  **neues Betriebsregime**: Nacht-Pumpen 57 % → 4 %, Mittagspumpen (10–16 Uhr) 26 % → 71 %,
  Abend-Erzeugung (17–24 Uhr) 52 % → 74 %. Capture-Spread 134,6 €/MWh, theoretischer Arbitragewert des
  Sommerzyklus ≈ 345 Mio. €. Derselbe Abendtrend in Österreich (50 % → 74 %) und der Schweiz (43 % → 58 %).
* **Preise**: DE-LU 114,0 €/MWh, AT 124,2 €/MWh, CH 119,6 €/MWh (alle deutlich über 2025). Die 2018
  getrennten Preiszonen DE-LU und AT notieren wieder auseinander (AT +10,2 €/MWh über DE-LU).

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
# 1. Daten laden: 10 Jahre × (Erzeugung, Preise, installierte Leistung) × DE/AT/CH
python3 scripts/fetch_data.py --years 2017-2026 --sleep 15

# 2. Grenzüberschreitende Flüsse (optional, für Abschnitt 4)
python3 scripts/fetch_flows.py 2017-2026

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
* Der „Arbitragewert“ ist eine theoretische Day-ahead-Betrachtung ohne Wirkungsgradverluste,
  Regelenergie und Rahmenverträge konkreter Anlagen.

## Datenlizenz

Die Energie- und Preisreihen stammen von ihren jeweiligen Quellen (ENTSO-E, SMARD, APG, Swissgrid,
EEX u. a.) und werden von Fraunhofer ISE über energy-charts.info unter CC BY 4.0 veröffentlicht. Bei
Nutzung: Quellenangabe `energy-charts.info — Fraunhofer ISE`.
