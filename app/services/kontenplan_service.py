"""Kontenplan-Service: Standard-Konten und Buchungsschlüssel anlegen."""
from app.extensions import db
from app.models.buchhaltung import Konto, Buchungsschluessel


# Standard-Kontenplan für Einzelbetrieb
STANDARD_KONTEN = [
    # Klasse 0 - Anlagevermögen
    ('0100', 'Grundstücke', 0, 'aktiv', True, False),
    ('0200', 'Gebäude', 0, 'aktiv', True, False),
    ('0300', 'Maschinen und Geräte', 0, 'aktiv', True, True),
    ('0400', 'Betriebs- und Geschäftsausstattung', 0, 'aktiv', True, False),
    ('0800', 'Geringwertige Wirtschaftsgüter', 0, 'aktiv', True, False),
    # Klasse 2 - Forderungen
    ('2000', 'Forderungen (Sammelkonto)', 2, 'aktiv', True, True),
    ('2900', 'Sonstige Forderungen', 2, 'aktiv', True, False),
    # Klasse 3 - Bank & Kassa
    ('3100', 'Bank (Hauptkonto)', 3, 'aktiv', True, False),
    ('3200', 'Sparkonto', 3, 'aktiv', True, False),
    ('3300', 'Kassa (Bargeld)', 3, 'aktiv', True, False),
    # Klasse 4 - Verbindlichkeiten
    ('4000', 'Verbindlichkeiten Lieferanten', 4, 'passiv', True, False),
    ('4300', 'Darlehen', 4, 'passiv', True, False),
    ('4900', 'Sonstige Verbindlichkeiten', 4, 'passiv', True, False),
    # Klasse 5 - Eigenkapital
    ('5000', 'Grundkapital / Rücklagen', 5, 'passiv', True, False),
    ('5100', 'Gewinnvortrag', 5, 'passiv', True, False),
    ('5200', 'Jahresergebnis', 5, 'passiv', True, False),
    # Klasse 6 - Aufwendungen
    ('6000', 'Reparaturen und Instandhaltung', 6, 'aufwand', False, False),
    ('6100', 'Treibstoff und Betriebsmittel', 6, 'aufwand', False, False),
    ('6200', 'Versicherungen', 6, 'aufwand', False, False),
    ('6300', 'Steuern und Abgaben', 6, 'aufwand', False, False),
    ('6400', 'Abschreibungen', 6, 'aufwand', False, False),
    ('6500', 'Zinsaufwand', 6, 'aufwand', False, False),
    ('6600', 'Bankspesen', 6, 'aufwand', False, False),
    ('6700', 'Futtermittel', 6, 'aufwand', False, False),
    ('6800', 'Fremdleistungen', 6, 'aufwand', False, False),
    ('6900', 'Sonstige Aufwendungen', 6, 'aufwand', False, False),
    # Klasse 7 - Erträge
    ('7000', 'Einnahmen Landwirtschaft', 7, 'ertrag', False, False),
    ('7100', 'Maschinenarbeit (Einnahmen)', 7, 'ertrag', False, False),
    ('7200', 'Zinserträge', 7, 'ertrag', False, False),
    ('7300', 'Holzverkauf', 7, 'ertrag', False, False),
    ('7400', 'Förderungen (AMA)', 7, 'ertrag', False, False),
    ('7500', 'Agrardieselvergütung', 7, 'ertrag', False, False),
    ('7600', 'Viehverkauf', 7, 'ertrag', False, False),
    ('7700', 'Pachteinnahmen', 7, 'ertrag', False, False),
    ('7900', 'Sonstige Erträge', 7, 'ertrag', False, False),
    # Klasse 8 - Eröffnung / Abschluss
    ('8000', 'Eröffnungsbilanzkonto (EBK)', 8, 'aktiv', False, False),
    ('8010', 'Schlussbilanzkonto (SBK)', 8, 'aktiv', False, False),
    ('8020', 'Gewinn- und Verlustkonto (GuV)', 8, 'aktiv', False, False),
    # Klasse 9 - Maschinen-Aufwand (Detail)
]

KLASSEN_NAMEN = {
    0: 'Anlagevermögen',
    1: 'Vorräte',
    2: 'Forderungen',
    3: 'Bank & Kassa',
    4: 'Verbindlichkeiten',
    5: 'Eigenkapital',
    6: 'Aufwendungen',
    7: 'Erträge',
    8: 'Eröffnung / Abschluss',
    9: 'Maschinen-Aufwand (Detail)',
}

# (kuerzel, bezeichnung, soll_klassen, haben_klassen, sortierung, suchbegriffe, soll_konto_nr, haben_konto_nr)
STANDARD_BUCHUNGSSCHLUESSEL = [
    ('ab',  'Allgemeine Buchung',      '',    '',    0,   '', None, None),
    ('re',  'Rechnungs-Eingang',       '6,9', '4',   10,  '', None, None),
    ('ra',  'Rechnungs-Ausgang',       '2',   '7',   20,  '', None, None),
    ('za',  'Zahlungs-Ausgang',        '4',   '3',   30,  '', None, None),
    ('ze',  'Zahlungs-Eingang',        '3',   '2',   40,  '', None, None),
    ('be',  'Bar-Einkauf',             '6,9', '3',   50,  '', None, None),
    ('bv',  'Bar-Verkauf',             '3',   '7',   60,  '', None, None),
    ('afa', 'Abschreibung',            '6',   '0',   70,  '', None, None),
    ('ak',  'Anlagen-Kauf',            '0',   '4',   80,  '', None, None),
    # Bank-Import Schluessel mit Suchbegriffen
    ('bk',  'Bankspesen',              '6',   '',    200,
     'Pauschale Elba,Buchungsentgelt,Umsatzprovision,Kontoführung',
     '6600', None),
    ('hv',  'Holzverkauf',             '',    '7',   210,
     'Holz,Papierholz', None, '7300'),
    ('foe', 'Förderungen (AMA)',       '',    '7',   220,
     'EU - AMA,AMA', None, '7400'),
    ('adv', 'Agrardieselvergütung',    '',    '7',   230,
     'Agrardieselvergütung,Zollstelle Wien', None, '7500'),
    ('vs',  'Versicherung',            '6',   '',    270,
     'UNIQA,Versicherung', '6200', None),
]


def standard_kontenplan_erstellen():
    """Legt Standard-Konten an. Überspringt existierende."""
    bestehend = {k.kontonummer for k in Konto.query.all()}

    anzahl = 0
    for nummer, bezeichnung, klasse, typ, jahresuebertrag, ist_sammelkonto in STANDARD_KONTEN:
        if nummer in bestehend:
            continue
        konto = Konto(
            kontonummer=nummer,
            bezeichnung=bezeichnung,
            kontenklasse=klasse,
            kontotyp=typ,
            jahresuebertrag=jahresuebertrag,
            ist_sammelkonto=ist_sammelkonto,
            aktiv=True,
        )
        db.session.add(konto)
        anzahl += 1

    db.session.commit()

    standard_buchungsschluessel_erstellen()
    return anzahl


def maschinen_konten_erstellen(maschine_id, maschine_name):
    """Legt Klasse-9-Aufwandskonten und ein Ertragskonto für eine Maschine an."""
    erstellt = []

    # Aufwandskonten Klasse 9
    vorhandene = Konto.query.filter_by(kontenklasse=9).all()
    belegte_gruppen = set()
    for k in vorhandene:
        if len(k.kontonummer) == 4 and k.kontonummer.startswith('9'):
            try:
                belegte_gruppen.add(int(k.kontonummer[1:3]))
            except ValueError:
                pass

    naechste_gruppe = 1
    while naechste_gruppe in belegte_gruppen:
        naechste_gruppe += 1

    prefix = f'9{naechste_gruppe:02d}'
    unterkonten = [
        (f'{prefix}1', f'{maschine_name} - Reparaturen'),
        (f'{prefix}2', f'{maschine_name} - Wartung'),
        (f'{prefix}3', f'{maschine_name} - Versicherung'),
        (f'{prefix}4', f'{maschine_name} - Sonstige Kosten'),
    ]

    for nummer, bezeichnung in unterkonten:
        konto = Konto(
            kontonummer=nummer,
            bezeichnung=bezeichnung,
            kontenklasse=9,
            kontotyp='aufwand',
            maschine_id=maschine_id,
            jahresuebertrag=False,
            aktiv=True,
        )
        db.session.add(konto)
        erstellt.append(konto)

    # Ertragskonto 71xx
    vorhandene_71 = Konto.query.filter(
        Konto.kontonummer.like('71%'),
        Konto.kontonummer != '7100',
    ).all()
    belegte_71 = set()
    for k in vorhandene_71:
        try:
            belegte_71.add(int(k.kontonummer))
        except ValueError:
            pass

    naechste_71 = 7101
    while naechste_71 in belegte_71:
        naechste_71 += 1

    konto_ertrag = Konto(
        kontonummer=str(naechste_71),
        bezeichnung=f'Einnahmen {maschine_name}',
        kontenklasse=7,
        kontotyp='ertrag',
        maschine_id=maschine_id,
        jahresuebertrag=False,
        aktiv=True,
    )
    db.session.add(konto_ertrag)
    erstellt.append(konto_ertrag)

    db.session.commit()
    return erstellt


def standard_buchungsschluessel_erstellen():
    """Legt Standard-Buchungsschlüssel an."""
    bestehend = {bs.kuerzel for bs in Buchungsschluessel.query.all()}

    konten = Konto.query.all()
    konto_by_nr = {k.kontonummer: k.id for k in konten}

    anzahl = 0
    for eintrag in STANDARD_BUCHUNGSSCHLUESSEL:
        kuerzel, bezeichnung, soll_kl, haben_kl, sortierung = eintrag[:5]
        suchbegriffe = eintrag[5] if len(eintrag) > 5 else ''
        soll_konto_nr = eintrag[6] if len(eintrag) > 6 else None
        haben_konto_nr = eintrag[7] if len(eintrag) > 7 else None

        if kuerzel in bestehend:
            continue

        bs = Buchungsschluessel(
            kuerzel=kuerzel,
            bezeichnung=bezeichnung,
            soll_klassen=soll_kl or None,
            haben_klassen=haben_kl or None,
            suchbegriffe=suchbegriffe or None,
            soll_konto_id=konto_by_nr.get(soll_konto_nr) if soll_konto_nr else None,
            haben_konto_id=konto_by_nr.get(haben_konto_nr) if haben_konto_nr else None,
            sortierung=sortierung,
            aktiv=True,
        )
        db.session.add(bs)
        anzahl += 1

    db.session.commit()
    return anzahl
