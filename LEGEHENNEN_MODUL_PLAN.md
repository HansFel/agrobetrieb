# Legehennen Pro-Modul – Planungsdokument

## Übersicht

Professionelles Herdenmanagement-Modul für Legehennenhalter. Deckt alle gesetzlichen Dokumentationspflichten ab und bietet umfassende Produktions- und Leistungsanalyse.

---

## 1. Gesetzliche Grundlagen & Dokumentationspflichten

### 1.1 Bestandsregister (Viehverkehrsverordnung / ViehVerkV)
- **Pflicht**: Jeder Geflügelhalter muss ein Bestandsregister führen
- Zu dokumentieren:
  - Nutzungsart (Legehennen)
  - Anzahl der Tiere (Zugang/Abgang/Bestand)
  - Datum jedes Zugangs/Abgangs
  - Name & Anschrift des Vorbesitzers/Empfängers
  - Herkunft der Tiere (Brüterei, Aufzuchtbetrieb)
  - Registriernummer des Betriebs (VVVO-Nr.)
- **Aufbewahrungspflicht**: 3 Jahre

### 1.2 Stallbuch / Betriebstagebuch
- **Pflicht**: Tägliche Aufzeichnungen
- Zu dokumentieren:
  - Tierbestand (Anfangs-/Endbestand pro Durchgang)
  - Tägliche Verluste (Mortalität) mit Ursache wenn bekannt
  - Futterverbrauch und Wasserverbrauch
  - Legeleistung (Eizahl, Eigewicht)
  - Stallklima (Temperatur, Luftfeuchtigkeit) – optional aber empfohlen
  - Besondere Vorkommnisse (Kannibalismus, Federpicken, Störungen)

### 1.3 Tierarzneimittel-Dokumentation (TAMG – Tierarzneimittelgesetz)
- **Pflicht**: Dokumentation JEDER Behandlung (seit 2023 verschärft durch EU VO 2019/6)
- Zu dokumentieren:
  - Datum der Anwendung
  - Bezeichnung des Arzneimittels
  - Menge/Dosierung
  - Anwendungsdauer (von–bis)
  - Wartezeit (Eier! → wichtig für Legehennen)
  - Diagnose/Indikation
  - Name des verordnenden Tierarztes
  - Behandelte Tiergruppe/Anzahl
  - Chargen-Nr. des Arzneimittels
- **Aufbewahrungspflicht**: 5 Jahre
- **Antibiotika**: Meldepflicht an TAM-HIT-Datenbank (Therapiehäufigkeit)

### 1.4 Impfungen (Pflichtimpfungen)
- **Newcastle Disease (ND)**: Gesetzliche Impfpflicht in DE (Geflügelpest-VO)
- **Salmonellen**: Pflichtimpfung für Betriebe >350 Hennen (Hühner-Salmonellen-VO)
- Übliche weitere Impfungen (empfohlen):
  - Marek-Krankheit (in Brüterei)
  - Infektiöse Bronchitis (IB)
  - Egg Drop Syndrome (EDS)
  - Aviäre Enzephalomyelitis (AE)
  - Infektiöse Bursitis (Gumboro)
  - Mykoplasmen (MG)
  - Kokzidiose

### 1.5 Salmonellen-Monitoring
- **Pflicht** für Betriebe ≥1.000 Hennen
- Eigenkontrollen + amtliche Proben
- Dokumentation der Probenahme und Ergebnisse

### 1.6 Eierkennzeichnung & KAT
- Erzeugercode: Haltungsform-Land-Betriebsnr. (z.B. 1-DE-1234567)
- Packstellennummer
- Mindesthaltbarkeitsdatum (MHD = Legedatum + 28 Tage)
- KAT-Systemteilnahme (wenn zutreffend)

### 1.7 Haltungsform-Dokumentation
- Haltungsform: 0=Bio, 1=Freiland, 2=Boden, 3=Kleingruppe
- Stallgröße, nutzbare Fläche, Nestzahl
- Auslauffläche (bei Freiland/Bio: min. 4m² pro Henne)
- Besatzdichte (max. 9 Hennen/m² nutzbare Fläche bei Boden/Freiland)

---

## 2. Datenmodell (SQLAlchemy Models)

### 2.1 `Herde` (Kern-Entity)
```
herde
├── id                     : Integer, PK
├── betrieb_id             : FK → betrieb
├── name                   : String(100)        # z.B. "Herde 2024-A"
├── rasse                  : String(100)        # z.B. "Lohmann Brown", "Dekalb White"
├── haltungsform           : Integer            # 0=Bio, 1=Freiland, 2=Boden, 3=Kleingruppe
├── schlupfdatum           : Date               # Schlupfdatum der Küken
├── lieferdatum            : Date               # Einstallung / Lieferung in den Stall
├── lieferant              : String(200)        # Aufzuchtbetrieb / Brüterei
├── lieferant_vvvo         : String(50)         # VVVO-Nr. des Lieferanten
├── anfangsbestand         : Integer            # Anzahl Tiere bei Einstallung
├── aktueller_bestand      : Integer            # Wird durch Abgänge/Zugänge aktualisiert
├── stall_nr               : String(50)         # Stallnummer
├── stall_flaeche_m2       : Numeric(10,2)      # Nutzbare Stallfläche
├── auslauf_flaeche_m2     : Numeric(10,2)      # Auslauffläche (Freiland/Bio)
├── nest_plaetze           : Integer            # Anzahl Nestplätze
├── erzeuger_code          : String(20)         # Eierkennzeichnung z.B. "1-DE-1234567"
├── legebeginn             : Date               # Datum erstes Ei (ca. 18.-20. Lebenswoche)
├── erwartetes_ende        : Date               # Geplantes Ausstalldatum
├── ausstalldatum          : Date               # Tatsächliches Ausstalldatum / Schlachtung
├── ist_aktiv              : Boolean            # Default True, False nach Ausstallung
├── bemerkung              : Text
├── erstellt_am            : DateTime
├── aktualisiert_am        : DateTime
```

### 2.2 `Tagesleistung` (Tägliche Produktion)
```
tagesleistung
├── id                     : Integer, PK
├── herde_id               : FK → herde
├── datum                  : Date               # Tagesdatum
├── lebenstag              : Integer            # Auto-berechnet aus Schlupfdatum
├── lebenswoche            : Integer            # Auto-berechnet
├── eier_gesamt            : Integer            # Gesamtzahl gelegter Eier
├── eier_verkaufsfaehig    : Integer            # Verkaufsfähige Eier
├── eier_knick             : Integer            # Knickeier
├── eier_bruch             : Integer            # Brucheier
├── eier_schmutzig         : Integer            # Schmutzeier
├── eier_wind              : Integer            # Windeier (schalenlos)
├── eier_boden             : Integer            # Bodeneier (außerhalb Nest)
├── eigewicht_durchschnitt : Numeric(5,2)       # Durchschnittliches Eigewicht in g
├── tierbestand            : Integer            # Bestand an diesem Tag
├── verluste               : Integer            # Tierverluste an diesem Tag
├── verlust_ursache        : String(200)        # Todesursache falls bekannt
├── futterverbrauch_kg     : Numeric(8,2)       # Futterverbrauch in kg
├── wasserverbrauch_l      : Numeric(8,2)       # Wasserverbrauch in Litern
├── temperatur_stall       : Numeric(4,1)       # Stalltemperatur °C
├── luftfeuchtigkeit       : Numeric(4,1)       # Relative Luftfeuchtigkeit %
├── lichtprogramm_std      : Numeric(4,1)       # Lichtstunden
├── bemerkung              : Text               # Besondere Vorkommnisse
├── erstellt_am            : DateTime
├── aktualisiert_am        : DateTime
│
├── → legerate_prozent     : computed           # (eier_gesamt / tierbestand) × 100
├── → futter_pro_tier_g    : computed           # (futterverbrauch_kg × 1000) / tierbestand
├── → futter_pro_ei_g      : computed           # (futterverbrauch_kg × 1000) / eier_gesamt
```

### 2.3 `Sortierergebnis` (Packstellen-Sortierung)
```
sortierergebnis
├── id                     : Integer, PK
├── herde_id               : FK → herde
├── datum                  : Date
├── eier_gesamt            : Integer            # Gesamtzahl sortiert
├── groesse_s              : Integer            # < 53g (S)
├── groesse_m              : Integer            # 53-63g (M)
├── groesse_l              : Integer            # 63-73g (L)
├── groesse_xl             : Integer            # > 73g (XL)
├── aussortiert            : Integer            # Aussortierte Eier
├── anteil_braun           : Numeric(5,2)       # Prozent braune Eier (bei Mischherden)
├── anteil_weiss           : Numeric(5,2)       # Prozent weiße Eier
├── bemerkung              : Text
├── erstellt_am            : DateTime
├── aktualisiert_am        : DateTime
```

### 2.4 `TierarztBesuch`
```
tierarzt_besuch
├── id                     : Integer, PK
├── herde_id               : FK → herde
├── datum                  : Date
├── tierarzt_name          : String(200)
├── tierarzt_praxis        : String(200)
├── grund                  : String(200)        # Routinekontrolle, Krankheit, Impfung, etc.
├── diagnose               : Text
├── massnahmen             : Text               # Durchgeführte Maßnahmen
├── naechster_besuch       : Date               # Follow-up-Termin
├── kosten                 : Numeric(10,2)
├── bemerkung              : Text
├── erstellt_am            : DateTime
├── aktualisiert_am        : DateTime
```

### 2.5 `Impfung`
```
impfung
├── id                     : Integer, PK
├── herde_id               : FK → herde
├── datum                  : Date
├── impfstoff              : String(200)        # Bezeichnung des Impfstoffs
├── krankheit              : String(100)        # Gegen welche Krankheit (ND, IB, EDS, etc.)
├── charge                 : String(100)        # Chargen-Nummer
├── verabreichungsart      : String(50)         # Trinkwasser, Spray, Injektion, Augentropfen
├── tierarzt               : String(200)
├── naechste_impfung       : Date               # Wiederholungsimpfung
├── bemerkung              : Text
├── erstellt_am            : DateTime
├── aktualisiert_am        : DateTime
```

### 2.6 `Medikament` (Tierarzneimittel-Dokumentation gemäß TAMG)
```
medikament_behandlung
├── id                     : Integer, PK
├── herde_id               : FK → herde
├── beginn                 : Date               # Behandlungsbeginn
├── ende                   : Date               # Behandlungsende
├── medikament_name        : String(200)        # Bezeichnung
├── wirkstoff              : String(200)        # Wirkstoff
├── typ                    : String(50)         # Antibiotikum, Antiparasitikum, Vitamine, Sonstiges
├── charge                 : String(100)        # Chargen-Nr.
├── dosierung              : String(100)        # z.B. "0,5 ml/Tier" oder "1g/l Trinkwasser"
├── verabreichungsart      : String(50)         # Trinkwasser, Futter, Injektion, Spray
├── diagnose               : String(200)        # Indikation / Diagnose
├── tierarzt               : String(200)        # Verordnender Tierarzt
├── anzahl_tiere           : Integer            # Behandelte Tieranzahl
├── wartezeit_tage         : Integer            # Wartezeit Eier (in Tagen)
├── wartezeit_ende         : Date               # Auto-berechnet: ende + wartezeit_tage
├── ist_antibiotikum       : Boolean            # Für Antibiotika-Meldepflicht
├── beleg_nr               : String(50)         # AUA-Beleg-Nr.
├── bemerkung              : Text
├── erstellt_am            : DateTime
├── aktualisiert_am        : DateTime
```

### 2.7 `FutterLieferung` (Futtermittel-Dokumentation)
```
futter_lieferung
├── id                     : Integer, PK
├── herde_id               : FK → herde (optional, bei mehreren Herden zuweisbar)
├── datum                  : Date
├── futtermittel           : String(200)        # Art des Futters
├── lieferant              : String(200)
├── menge_kg               : Numeric(10,2)
├── charge                 : String(100)
├── preis                  : Numeric(10,2)
├── bemerkung              : Text
├── erstellt_am            : DateTime
├── aktualisiert_am        : DateTime
```

### 2.8 `SalmonellenProbe`
```
salmonellen_probe
├── id                     : Integer, PK
├── herde_id               : FK → herde
├── datum                  : Date
├── probenart              : String(50)         # Sockentupfer, Kot, Staub, Eier
├── labor                  : String(200)        # Untersuchendes Labor
├── ergebnis               : String(20)         # positiv / negativ / ausstehend
├── serotyp                : String(100)        # Bei positivem Befund
├── beleg_nr               : String(100)
├── bemerkung              : Text
├── erstellt_am            : DateTime
├── aktualisiert_am        : DateTime
```

### 2.9 `HerdeEreignis` (Allgemeines Stallbuch-Ereignis)
```
herde_ereignis
├── id                     : Integer, PK
├── herde_id               : FK → herde
├── datum                  : Date
├── kategorie              : String(50)         # Desinfektion, Entwesung, Stromausfall,
│                                               # Stallpflicht (Vogelgrippe), Kontrolle,
│                                               # Futterwechsel, Lichtwechsel, Sonstiges
├── beschreibung           : Text
├── erstellt_am            : DateTime
├── aktualisiert_am        : DateTime
```

---

## 3. Blueprint-Struktur

### Blueprint: `legehennen` (url_prefix: `/legehennen`)

#### 3.1 Herden-Verwaltung
| Route | Methode | Funktion |
|---|---|---|
| `/` | GET | Dashboard/Übersicht aller aktiven Herden |
| `/herde/neu` | GET/POST | Neue Herde anlegen |
| `/herde/<id>` | GET | Herden-Detail (Übersicht mit KPIs) |
| `/herde/<id>/bearbeiten` | GET/POST | Herde bearbeiten |
| `/herde/<id>/abschliessen` | POST | Herde abschließen (Ausstallung) |

#### 3.2 Tagesleistung (Stallbuch)
| Route | Methode | Funktion |
|---|---|---|
| `/herde/<id>/stallbuch` | GET | Stallbuch-Übersicht (Tabelle + Filter) |
| `/herde/<id>/stallbuch/neu` | GET/POST | Tageseintrag erfassen |
| `/herde/<id>/stallbuch/<t_id>/bearbeiten` | GET/POST | Tageseintrag bearbeiten |
| `/herde/<id>/stallbuch/import` | GET/POST | CSV-Import Tagesleistungen |

#### 3.3 Sortierergebnisse (Packstelle)
| Route | Methode | Funktion |
|---|---|---|
| `/herde/<id>/sortierung` | GET | Sortierergebnis-Übersicht |
| `/herde/<id>/sortierung/neu` | GET/POST | Neues Sortierergebnis |
| `/herde/<id>/sortierung/<s_id>/bearbeiten` | GET/POST | Bearbeiten |

#### 3.4 Medizinische Dokumentation
| Route | Methode | Funktion |
|---|---|---|
| `/herde/<id>/tierarzt` | GET | Alle Tierarztbesuche |
| `/herde/<id>/tierarzt/neu` | GET/POST | Neuer Tierarztbesuch |
| `/herde/<id>/impfungen` | GET | Impfübersicht + Impfplan |
| `/herde/<id>/impfungen/neu` | GET/POST | Neue Impfung eintragen |
| `/herde/<id>/medikamente` | GET | Medikamenten-Übersicht + Wartezeiten |
| `/herde/<id>/medikamente/neu` | GET/POST | Neue Behandlung eintragen |
| `/herde/<id>/salmonellen` | GET | Salmonellen-Monitoring |
| `/herde/<id>/salmonellen/neu` | GET/POST | Neue Probe eintragen |

#### 3.5 Futter
| Route | Methode | Funktion |
|---|---|---|
| `/herde/<id>/futter` | GET | Futterlieferungen |
| `/herde/<id>/futter/neu` | GET/POST | Neue Lieferung |

#### 3.6 Ereignisse
| Route | Methode | Funktion |
|---|---|---|
| `/herde/<id>/ereignisse` | GET | Stallbuch-Ereignisse |
| `/herde/<id>/ereignisse/neu` | GET/POST | Neues Ereignis |

#### 3.7 Auswertungen & Grafiken
| Route | Methode | Funktion |
|---|---|---|
| `/herde/<id>/legekurve` | GET | Legekurve (Chart.js) |
| `/herde/<id>/eigroessen` | GET | Eigrößen-Entwicklung (Chart.js) |
| `/herde/<id>/auswertung` | GET | Gesamtauswertung (KPIs, Tabellen) |
| `/herde/<id>/vergleich` | GET | Soll/Ist-Vergleich mit Rassestandard |
| `/api/legehennen/herde/<id>/legekurve.json` | GET | JSON-API für Chart-Daten |
| `/api/legehennen/herde/<id>/eigroessen.json` | GET | JSON-API für Eigrößen-Daten |

#### 3.8 Berichte & Export
| Route | Methode | Funktion |
|---|---|---|
| `/herde/<id>/bericht/stallbuch` | GET | Stallbuch-PDF für Behörden |
| `/herde/<id>/bericht/arzneimittel` | GET | Arzneimittel-Nachweis PDF |
| `/herde/<id>/bericht/bestandsregister` | GET | Bestandsregister PDF |
| `/herde/<id>/export/csv` | GET | Datenexport CSV |

---

## 4. Templates

```
templates/legehennen/
├── index.html                    # Dashboard: aktive Herden, Quick-KPIs
├── herde_form.html               # Herde anlegen/bearbeiten
├── herde_detail.html             # Herden-Übersicht mit Tabs/Cards
├── stallbuch.html                # Tagesleistung-Tabelle
├── stallbuch_form.html           # Tageseintrag erfassen
├── sortierung.html               # Sortierergebnis-Liste
├── sortierung_form.html          # Sortierergebnis-Formular
├── tierarzt.html                 # Tierarztbesuche
├── tierarzt_form.html            # Tierarztbesuch-Formular
├── impfungen.html                # Impfübersicht + Impfkalender
├── impfung_form.html             # Impfung-Formular
├── medikamente.html              # Medikamenten-Übersicht + Wartezeit-Anzeige
├── medikament_form.html          # Medikament-Formular
├── salmonellen.html              # Salmonellen-Monitoring
├── salmonellen_form.html         # Probe-Formular
├── futter.html                   # Futterlieferungen
├── futter_form.html              # Futter-Formular
├── ereignisse.html               # Ereignis-Liste
├── ereignis_form.html            # Ereignis-Formular
├── legekurve.html                # Legekurve (mit Chart.js Canvas)
├── eigroessen.html               # Eigrößen-Chart
├── auswertung.html               # Gesamtauswertung
└── vergleich.html                # Soll/Ist-Vergleich
```

---

## 5. Legekurve & Grafiken (Chart.js)

### 5.1 Legekurve
- **X-Achse**: Lebenswoche (oder Legewoche ab Legebeginn)
- **Y-Achse links**: Legerate in % (0–100%)
- **Y-Achse rechts**: Kumulierte Eizahl pro Anfangshenne
- **Linien**:
  - Ist-Legerate (tatsächlich) → Hauptlinie
  - Soll-Legerate (Rassestandard z.B. Lohmann Brown) → gestrichelt
  - Mortalität kumuliert (%) → sekundär
- **Interaktiv**: Hover-Tooltip mit Tagesdetails

### 5.2 Eigrößen-Entwicklung
- **X-Achse**: Lebenswoche
- **Y-Achse**: Durchschnittsgewicht in g
- **Zusätzlich**: Gestapeltes Balkendiagramm mit Anteil S/M/L/XL pro Woche
- **Vergleichslinie**: Soll-Eigewicht laut Rassestandard

### 5.3 Weitere Diagramme
- Futterverbrauch pro Tier/Tag → Linie
- Wasser-Futter-Verhältnis → Linie
- Mortalitätskurve → Balken
- Sortierungsanteile → Gestapelte Balken/Torte

---

## 6. Dashboard-KPIs (Herden-Übersicht)

Für jede aktive Herde auf einen Blick:

| KPI | Berechnung |
|---|---|
| **Alter** | Lebenswochen seit Schlupf |
| **Aktueller Bestand** | Anfangsbestand − Σ Verluste |
| **Legerate heute** | (Eier heute / Bestand) × 100 |
| **Ø Legerate 7 Tage** | Mittelwert letzte 7 Tage |
| **Kumulierte Eier/Anfangshenne** | Σ Eier / Anfangsbestand |
| **Ø Eigewicht** | Letzter erfasster Durchschnitt |
| **Mortalität gesamt** | ((Anfangsbestand − Bestand) / Anfangsbestand) × 100 |
| **Futterverwertung** | g Futter pro Ei |
| **Wartezeit aktiv?** | ⚠ Wenn Medikamenten-Wartezeit läuft |
| **Nächste Impfung** | Datum + Tage bis fällig |

---

## 7. Impfplan-Vorlage (Konfigurierbar)

Standard-Impfplan als Vorlage, den der Betrieb anpassen kann:

| Lebenswoche | Impfung | Methode |
|---|---|---|
| 1 | Marek (HVT+Rispens) | Injektion (Brüterei) |
| 1 | IB (Infektiöse Bronchitis) | Spray |
| 2 | Gumboro (IBD) | Trinkwasser |
| 3 | IB Booster | Trinkwasser |
| 4 | Gumboro Booster | Trinkwasser |
| 6 | Newcastle Disease (ND) | Trinkwasser |
| 7 | IB Variant | Trinkwasser |
| 8 | Kokzidiose | Trinkwasser |
| 10 | AE + Pocken | Flügelstichmethode |
| 12 | IB + ND Booster | Trinkwasser |
| 14 | EDS (Egg Drop Syndrome) | Injektion |
| 15 | Salmonellen (SE) | Injektion |
| 16 | ND + IB Booster | Trinkwasser |
| → wiederholt | ND alle 6–8 Wochen | Trinkwasser |
| → wiederholt | IB alle 6–8 Wochen | Trinkwasser |

---

## 8. Rassestandard-Daten (Soll-Werte)

Hinterlegte Referenzdaten für Soll/Ist-Vergleich:

### 8.1 Unterstützte Rassen/Linien
- **Lohmann Brown Classic** (braun, meistverbreitet DE)
- **Lohmann LSL Classic** (weiß)
- **Dekalb White**
- **Dekalb Brown**
- **Hy-Line Brown**
- **Hy-Line W-36** (weiß)
- **NOVOgen Brown**
- **NOVOgen White**
- **Benutzerdefiniert** (eigene Soll-Kurve)

### 8.2 Referenzdaten pro Rasse (Lebenswoche 18–80)
- Soll-Legerate (%)
- Soll-Eigewicht (g)
- Soll-Futterverbrauch (g/Tier/Tag)
- Soll-Mortalität kumuliert (%)

→ Können als JSON/CSV importiert oder manuell gepflegt werden.

---

## 9. Technische Umsetzung

### 9.1 Neue Dateien
```
app/
├── models/
│   └── legehennen.py              # Alle Models (Herde, Tagesleistung, etc.)
├── blueprints/
│   └── legehennen.py              # Blueprint mit allen Routes
├── services/
│   └── legehennen_service.py      # Berechnungen, Legekurve, PDF-Export
├── templates/
│   └── legehennen/
│       └── (siehe Template-Liste oben)
├── static/
│   └── js/
│       └── legehennen_charts.js   # Chart.js Konfigurationen
```

### 9.2 Migrations
- Neue Alembic-Migration für alle Legehennen-Tabellen

### 9.3 Abhängigkeiten (bereits vorhanden oder hinzuzufügen)
- **Chart.js** (CDN oder lokal) – für Legekurve und Diagramme
- **ReportLab** oder **WeasyPrint** – für PDF-Export (optional, Phase 2)

### 9.4 Berechtigungen
- Neues Modul `legehennen` im Rollensystem
- Aktionen: `view`, `create`, `edit`, `delete`, `berichte`
- Neue Rolle **`packstelle`** (siehe Abschnitt 12)

---

## 10. Implementierungs-Phasen

### Phase 1 – Kernfunktionalität
1. Models erstellen (alle Tabellen)
2. Migration erstellen und anwenden
3. Blueprint mit Herden-CRUD
4. Tagesleistung (Stallbuch) CRUD
5. Dashboard mit Herden-Übersicht und KPIs
6. Basis-Legekurve (Chart.js)

### Phase 2 – Medizinische Dokumentation
7. Tierarztbesuche CRUD
8. Impfungen CRUD + Impfplan-Vorlagen
9. Medikamenten-Dokumentation CRUD + Wartezeit-Berechnung
10. Salmonellen-Monitoring
11. Warnung bei aktiven Wartezeiten (Header-Badge)

### Phase 3 – Erweiterte Auswertung
12. Sortierergebnisse CRUD
13. Eigrößen-Entwicklung (Chart)
14. Soll/Ist-Vergleich mit Rassestandard
15. Futterverwertungs-Analyse
16. Mortalitätskurve

### Phase 4 – Berichte & Export
17. Stallbuch-PDF
18. Arzneimittel-Nachweis PDF
19. Bestandsregister-PDF
20. CSV-Export
21. Ereignis-Dokumentation

---

## 11. Besonderheiten & Hinweise

### Wartezeiten-Ampel
- Wenn eine Medikamenten-Wartezeit läuft: **Rote Warnung** im Dashboard und Herden-Detail
- Eier dürfen während Wartezeit NICHT als Konsumeier verkauft werden
- Auto-Berechnung: `wartezeit_ende = behandlung_ende + wartezeit_tage`

### Multi-Herden-Fähigkeit
- Ein Betrieb kann mehrere Herden gleichzeitig haben (verschiedene Ställe/Durchgänge)
- Herden-Archiv für abgeschlossene Durchgänge (historische Vergleiche)

### Stallpflicht-Handling
- Wenn eine Stallpflicht (Vogelgrippe) angeordnet wird:
  - Freiland-Betriebe können nach 16 Wochen Stallpflicht auf Code "2" (Boden) umstufen müssen
  - Dokumentation als HerdeEreignis

### Mobil-Optimierung
- Tagesleistung muss einfach auf dem Handy erfassbar sein (im Stall)
- Große Buttons, wenig Scrollen, Quick-Entry-Modus

---

## Zusammenfassung der Tabellen

| Nr. | Tabelle | Zweck |
|---|---|---|
| 1 | `herde` | Kern: Herden-/Durchgangsverwaltung |
| 2 | `tagesleistung` | Tägliche Produktion + Stallbuch |
| 3 | `sortierergebnis` | Packstellen-Sortierung (S/M/L/XL) |
| 4 | `tierarzt_besuch` | Tierarztbesuche |
| 5 | `impfung` | Impfungen + Impfplan |
| 6 | `medikament_behandlung` | Arzneimittel (TAMG-konform) |
| 7 | `futter_lieferung` | Futtermittel-Dokumentation |
| 8 | `salmonellen_probe` | Salmonellen-Monitoring |
| 9 | `herde_ereignis` | Allgemeine Stallbuch-Ereignisse |

---

## 12. Rolle: Packstelle (externer Zugang)

### 12.1 Konzept

Bedienstete einer **Packstelle** (Sortier-/Packbetrieb) erhalten einen eigenen Benutzerzugang,
um **ausschließlich Sortierergebnisse** einzutragen. Sie sind externe Personen, die keinen
Zugriff auf andere Betriebsdaten haben.

- Jeder Packstelle-Mitarbeiter bekommt einen **eigenen Account** (Name + Passwort)
- Der Betriebsadmin legt diese Benutzer an und weist die Rolle `packstelle` zu
- Optional: Zuordnung zu einer bestimmten Packstelle (Name, PLZ, Ort)

### 12.2 Neue Rolle: `packstelle`

```python
# In rollen.py → ROLLEN
'packstelle': {
    'name': 'Packstelle',
    'beschreibung': 'Externer Zugang: Nur Sortierergebnisse eintragen',
    'prioritaet': 75,
}
```

### 12.3 Berechtigungen

```python
# In rollen.py → BERECHTIGUNGEN
'packstelle': {
    'dashboard': ['view'],           # Nur Mini-Dashboard (zugewiesene Herden)
    'betrieb': [],
    'benutzer': [],
    'maschinen': [],
    'einsaetze': [],
    'buchhaltung': [],
    'fakturierung': [],
    'lager': [],
    'legehennen': ['view'],          # Nur Herden sehen (Name, Bestand)
    'sortierergebnis': ['view', 'create', 'edit'],  # KERN: Sortierung eintragen
}
```

### 12.4 Erweiterung User-Model

```
user (bestehende Tabelle)
├── ...bestehende Felder...
├── packstelle_name        : String(200)   # Name der Packstelle (nur bei Rolle packstelle)
├── packstelle_ort         : String(200)   # PLZ + Ort
├── packstelle_nr          : String(50)    # Packstellennummer
```

### 12.5 Zugriffs-Einschränkungen

- **Sieht nur**: Herden-Liste (Name, Stall-Nr., Bestand) + eigene Sortierergebnisse
- **Kann**: Sortierergebnis anlegen (Datum, S/M/L/XL, Aussortiert) und bearbeiten
- **Kann NICHT**: Stallbuch, Medikamente, Impfungen, Tierarzt, Finanzdaten, andere Module
- **Navigation**: Reduziertes Menü – nur "Sortierergebnisse" sichtbar
- **Dashboard**: Nur zugewiesene Herden mit Basisdaten (kein KPI-Vollzugriff)

### 12.6 Packstelle-Workflow

1. **Admin** legt Benutzer an mit Rolle `packstelle`
   - Felder: Name, Email/Username, Passwort, Packstelle-Name, Packstelle-Nr.
2. **Packstelle-Mitarbeiter** meldet sich an
3. Sieht vereinfachtes Dashboard: nur aktive Herden des Betriebs
4. Wählt Herde → "Sortierergebnis eintragen"
5. Erfasst: Datum, Eier gesamt, S/M/L/XL, Aussortiert, Bemerkung
6. Speichert → wird im System dem Betrieb zugeordnet

### 12.7 Sicherheit

- Packstelle-Benutzer können **keine anderen Benutzer** sehen oder verwalten
- Packstelle-Benutzer können **kein eigenes Passwort** ändern (nur Admin)
  → Oder: eingeschränkte Profil-Seite nur für Passwortänderung
- Login-Audit: Letzte Anmeldung wird protokolliert
- Admin kann Packstelle-Zugang jederzeit **deaktivieren**
