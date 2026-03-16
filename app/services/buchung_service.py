"""Buchungs-Service: Buchungen erstellen, stornieren, Salden berechnen."""
from datetime import datetime
from decimal import Decimal
from app.extensions import db
from app.models.buchhaltung import Buchung, Konto, KontoSaldo


def naechste_buchungsnummer(geschaeftsjahr):
    """Ermittelt die nächste fortlaufende Buchungsnummer."""
    letzte = Buchung.query.filter_by(
        geschaeftsjahr=geschaeftsjahr,
    ).order_by(Buchung.id.desc()).first()

    if not letzte:
        return f'{geschaeftsjahr}-0001'

    try:
        nummer = int(letzte.buchungsnummer.split('-')[1])
    except (IndexError, ValueError):
        nummer = 0
    return f'{geschaeftsjahr}-{nummer + 1:04d}'


def buchung_erstellen(geschaeftsjahr, datum, soll_konto_id, haben_konto_id,
                      betrag, buchungstext, erstellt_von,
                      beleg_nummer=None, beleg_datum=None, buchungsart='manuell',
                      einsatz_id=None, bank_transaktion_id=None):
    """Validiert und speichert eine neue Buchung. Aktualisiert Salden."""
    betrag = Decimal(str(betrag))
    if betrag <= 0:
        raise ValueError('Betrag muss größer als 0 sein.')

    if soll_konto_id == haben_konto_id:
        raise ValueError('Soll- und Haben-Konto dürfen nicht identisch sein.')

    soll_konto = db.session.get(Konto, soll_konto_id)
    haben_konto = db.session.get(Konto, haben_konto_id)
    if not soll_konto or not haben_konto:
        raise ValueError('Ungültiges Konto.')

    buchungsnr = naechste_buchungsnummer(geschaeftsjahr)

    buchung = Buchung(
        geschaeftsjahr=geschaeftsjahr,
        buchungsnummer=buchungsnr,
        datum=datum,
        soll_konto_id=soll_konto_id,
        haben_konto_id=haben_konto_id,
        betrag=betrag,
        buchungstext=buchungstext,
        beleg_nummer=beleg_nummer,
        beleg_datum=beleg_datum,
        buchungsart=buchungsart,
        einsatz_id=einsatz_id,
        bank_transaktion_id=bank_transaktion_id,
        erstellt_von=erstellt_von,
    )
    db.session.add(buchung)
    db.session.flush()

    saldo_aktualisieren(soll_konto_id, geschaeftsjahr)
    saldo_aktualisieren(haben_konto_id, geschaeftsjahr)

    db.session.commit()
    return buchung


def saldo_aktualisieren(konto_id, geschaeftsjahr):
    """Berechnet KontoSaldo aus Buchungen neu."""
    konto = db.session.get(Konto, konto_id)
    if not konto:
        return

    summe_soll_result = db.session.query(
        db.func.coalesce(db.func.sum(Buchung.betrag), 0)
    ).filter(
        Buchung.soll_konto_id == konto_id,
        Buchung.geschaeftsjahr == geschaeftsjahr,
        Buchung.storniert == False,
    ).scalar()

    summe_haben_result = db.session.query(
        db.func.coalesce(db.func.sum(Buchung.betrag), 0)
    ).filter(
        Buchung.haben_konto_id == konto_id,
        Buchung.geschaeftsjahr == geschaeftsjahr,
        Buchung.storniert == False,
    ).scalar()

    summe_soll = Decimal(str(summe_soll_result))
    summe_haben = Decimal(str(summe_haben_result))

    saldo = KontoSaldo.query.filter_by(
        konto_id=konto_id, geschaeftsjahr=geschaeftsjahr
    ).first()

    if not saldo:
        saldo = KontoSaldo(
            konto_id=konto_id,
            geschaeftsjahr=geschaeftsjahr,
            saldo_beginn=Decimal('0'),
        )
        db.session.add(saldo)

    saldo.summe_soll = summe_soll
    saldo.summe_haben = summe_haben

    saldo_beginn = Decimal(str(saldo.saldo_beginn or 0))
    if konto.kontotyp in ('aktiv', 'aufwand'):
        saldo.saldo_aktuell = saldo_beginn + summe_soll - summe_haben
    else:
        saldo.saldo_aktuell = saldo_beginn + summe_haben - summe_soll

    saldo.aktualisiert_am = datetime.utcnow()


def salden_neu_berechnen():
    """Berechnet alle KontoSalden vollständig neu."""
    konten = Konto.query.all()
    konto_ids = [k.id for k in konten]

    if not konto_ids:
        return 0

    KontoSaldo.query.filter(KontoSaldo.konto_id.in_(konto_ids)).delete(
        synchronize_session='fetch'
    )
    db.session.flush()

    jahre = db.session.query(Buchung.geschaeftsjahr).filter(
        Buchung.storniert == False,
    ).distinct().all()
    jahre = [j[0] for j in jahre]

    if not jahre:
        db.session.commit()
        return 0

    anzahl = 0
    for konto_id in konto_ids:
        for jahr in jahre:
            saldo_aktualisieren(konto_id, jahr)
            anzahl += 1

    db.session.commit()
    return anzahl


def sammelbuchung_erstellen(geschaeftsjahr, datum, gegenkonto_id, zeilen,
                            beleg_nummer, erstellt_von,
                            richtung='ausgabe', beleg_datum=None):
    """Erstellt mehrere Buchungen als Sammelbuchung."""
    if not zeilen:
        raise ValueError('Mindestens eine Zeile erforderlich.')

    erstellte = []
    sammel_id = None
    berechnete_konto_ids = set()

    for zeile in zeilen:
        betrag = Decimal(str(zeile['betrag']))
        if betrag <= 0:
            raise ValueError('Betrag muss größer als 0 sein.')

        if richtung == 'ausgabe':
            soll_konto_id = zeile['konto_id']
            haben_konto_id = gegenkonto_id
        else:
            soll_konto_id = gegenkonto_id
            haben_konto_id = zeile['konto_id']

        if soll_konto_id == haben_konto_id:
            raise ValueError('Soll- und Haben-Konto dürfen nicht identisch sein.')

        buchungsnr = naechste_buchungsnummer(geschaeftsjahr)
        buchung = Buchung(
            geschaeftsjahr=geschaeftsjahr,
            buchungsnummer=buchungsnr,
            datum=datum,
            soll_konto_id=soll_konto_id,
            haben_konto_id=haben_konto_id,
            betrag=betrag,
            buchungstext=zeile.get('text', '')[:200] or 'Sammelbuchung',
            beleg_nummer=beleg_nummer,
            beleg_datum=beleg_datum,
            buchungsart='sammel',
            erstellt_von=erstellt_von,
        )
        db.session.add(buchung)
        db.session.flush()

        if sammel_id is None:
            sammel_id = buchung.id

        buchung.sammel_id = sammel_id
        berechnete_konto_ids.add(soll_konto_id)
        berechnete_konto_ids.add(haben_konto_id)
        erstellte.append(buchung)

    for konto_id in berechnete_konto_ids:
        saldo_aktualisieren(konto_id, geschaeftsjahr)

    db.session.commit()
    return erstellte


def gegenkonto_aendern(buchung_id, neues_konto_id):
    """Ändert das Gegenkonto einer Import-Buchung direkt."""
    buchung = db.session.get(Buchung, buchung_id)
    if not buchung:
        raise ValueError('Buchung nicht gefunden.')
    if buchung.storniert:
        raise ValueError('Stornierte Buchungen können nicht geändert werden.')
    if buchung.buchungsart != 'import':
        raise ValueError('Nur Import-Buchungen können so geändert werden.')

    neues_konto = db.session.get(Konto, neues_konto_id)
    if not neues_konto:
        raise ValueError('Ungültiges Konto.')

    soll_konto = db.session.get(Konto, buchung.soll_konto_id)
    haben_konto = db.session.get(Konto, buchung.haben_konto_id)

    alte_konto_ids = {buchung.soll_konto_id, buchung.haben_konto_id}

    soll_ist_bank = soll_konto and (soll_konto.ist_importkonto or soll_konto.kontenklasse == 3)
    haben_ist_bank = haben_konto and (haben_konto.ist_importkonto or haben_konto.kontenklasse == 3)

    if soll_ist_bank and not haben_ist_bank:
        buchung.haben_konto_id = neues_konto_id
    elif haben_ist_bank and not soll_ist_bank:
        buchung.soll_konto_id = neues_konto_id
    else:
        buchung.haben_konto_id = neues_konto_id

    neue_konto_ids = {buchung.soll_konto_id, buchung.haben_konto_id}
    alle_betroffenen = alte_konto_ids | neue_konto_ids

    db.session.flush()

    for konto_id in alle_betroffenen:
        saldo_aktualisieren(konto_id, buchung.geschaeftsjahr)

    db.session.commit()
    return buchung


def buchung_stornieren(buchung_id, storniert_von, grund=''):
    """Erstellt Gegenbuchung und setzt storniert-Flag."""
    buchung = db.session.get(Buchung, buchung_id)
    if not buchung:
        raise ValueError('Buchung nicht gefunden.')
    if buchung.storniert:
        raise ValueError('Buchung ist bereits storniert.')

    buchung.storniert = True
    buchung.storniert_am = datetime.utcnow()
    buchung.storniert_von = storniert_von
    db.session.flush()

    storno_text = f'STORNO: {buchung.buchungstext}'
    if grund:
        storno_text += f' ({grund})'

    gegenbuchung = buchung_erstellen(
        geschaeftsjahr=buchung.geschaeftsjahr,
        datum=buchung.datum,
        soll_konto_id=buchung.haben_konto_id,
        haben_konto_id=buchung.soll_konto_id,
        betrag=buchung.betrag,
        buchungstext=storno_text,
        erstellt_von=storniert_von,
        buchungsart='manuell',
    )
    return gegenbuchung


# ============================================================
# Jahresabschluss / Saldenübertrag
# ============================================================

def jahresabschluss_durchfuehren(von_jahr, nach_jahr):
    """
    Überträgt Schlusssalden der Bilanzkonten (Klasse 0–5) als
    Anfangssalden ins Folgejahr.

    GuV-Konten (Klasse 6, 7, 9) werden NICHT übertragen –
    sie beginnen jedes Jahr bei 0.

    Bestehende saldo_beginn-Einträge im Zieljahr werden überschrieben
    (idempotent – mehrfaches Ausführen sicher).

    Returns:
        dict mit 'uebertragen' (Anzahl Konten), 'uebersprungen' (Anzahl)
    """
    # Nur Bilanzkonten übertragen
    bilanzkonten = Konto.query.filter(
        Konto.kontenklasse.in_([0, 1, 2, 3, 4, 5]),
        Konto.aktiv == True,
    ).all()

    uebertragen = 0
    uebersprungen = 0

    for konto in bilanzkonten:
        # Endsaldo des Vorjahres holen
        vorjahr_saldo = KontoSaldo.query.filter_by(
            konto_id=konto.id, geschaeftsjahr=von_jahr
        ).first()

        if vorjahr_saldo is None:
            uebersprungen += 1
            continue

        endsaldo = Decimal(str(vorjahr_saldo.saldo_aktuell or 0))

        # KontoSaldo für Folgejahr holen oder anlegen
        folge_saldo = KontoSaldo.query.filter_by(
            konto_id=konto.id, geschaeftsjahr=nach_jahr
        ).first()

        if not folge_saldo:
            folge_saldo = KontoSaldo(
                konto_id=konto.id,
                geschaeftsjahr=nach_jahr,
                saldo_beginn=Decimal('0'),
                summe_soll=Decimal('0'),
                summe_haben=Decimal('0'),
                saldo_aktuell=Decimal('0'),
            )
            db.session.add(folge_saldo)

        folge_saldo.saldo_beginn = endsaldo
        folge_saldo.aktualisiert_am = datetime.utcnow()

        # Saldo_aktuell neu berechnen (saldo_beginn + Bewegungen des Folgejahres)
        summe_soll = Decimal(str(folge_saldo.summe_soll or 0))
        summe_haben = Decimal(str(folge_saldo.summe_haben or 0))
        if konto.kontotyp in ('aktiv', 'aufwand'):
            folge_saldo.saldo_aktuell = endsaldo + summe_soll - summe_haben
        else:
            folge_saldo.saldo_aktuell = endsaldo + summe_haben - summe_soll

        uebertragen += 1

    db.session.commit()
    return {'uebertragen': uebertragen, 'uebersprungen': uebersprungen}


def jahresabschluss_vorschau(von_jahr, nach_jahr):
    """
    Gibt eine Vorschau der zu übertragenden Salden zurück,
    ohne etwas zu speichern.
    """
    bilanzkonten = Konto.query.filter(
        Konto.kontenklasse.in_([0, 1, 2, 3, 4, 5]),
        Konto.aktiv == True,
    ).order_by(Konto.kontonummer).all()

    positionen = []
    for konto in bilanzkonten:
        vorjahr_saldo = KontoSaldo.query.filter_by(
            konto_id=konto.id, geschaeftsjahr=von_jahr
        ).first()
        endsaldo = Decimal(str(vorjahr_saldo.saldo_aktuell or 0)) if vorjahr_saldo else Decimal('0')

        folge_saldo = KontoSaldo.query.filter_by(
            konto_id=konto.id, geschaeftsjahr=nach_jahr
        ).first()
        aktueller_beginn = Decimal(str(folge_saldo.saldo_beginn or 0)) if folge_saldo else Decimal('0')

        positionen.append({
            'konto': konto,
            'endsaldo_vorjahr': endsaldo,
            'aktueller_beginn_folgejahr': aktueller_beginn,
            'aenderung': endsaldo != aktueller_beginn,
        })

    return positionen


# ============================================================
# Bilanz & GuV
# ============================================================

def bilanz_berechnen(geschaeftsjahr):
    """Berechnet Bilanz: Aktiva (Klasse 0-3) und Passiva (Klasse 4-5)."""
    konten = Konto.query.filter(
        Konto.kontenklasse.in_([0, 1, 2, 3, 4, 5]),
        Konto.aktiv == True,
    ).order_by(Konto.kontonummer).all()

    aktiva = []
    passiva = []
    summe_aktiva = Decimal('0')
    summe_passiva = Decimal('0')

    for konto in konten:
        saldo_record = KontoSaldo.query.filter_by(
            konto_id=konto.id, geschaeftsjahr=geschaeftsjahr
        ).first()
        saldo = Decimal(str(saldo_record.saldo_aktuell)) if saldo_record else Decimal('0')

        eintrag = {'konto': konto, 'saldo': saldo}

        if konto.kontenklasse <= 3:
            aktiva.append(eintrag)
            summe_aktiva += saldo
        else:
            passiva.append(eintrag)
            summe_passiva += saldo

    return {
        'aktiva': aktiva,
        'passiva': passiva,
        'summe_aktiva': summe_aktiva,
        'summe_passiva': summe_passiva,
        'differenz': summe_aktiva - summe_passiva,
    }


def guv_berechnen(geschaeftsjahr):
    """Berechnet GuV: Aufwendungen (Klasse 6+9) und Erträge (Klasse 7)."""
    konten = Konto.query.filter(
        Konto.kontenklasse.in_([6, 7, 9]),
        Konto.aktiv == True,
    ).order_by(Konto.kontonummer).all()

    aufwendungen = []
    ertraege = []
    summe_aufwendungen = Decimal('0')
    summe_ertraege = Decimal('0')

    for konto in konten:
        saldo_record = KontoSaldo.query.filter_by(
            konto_id=konto.id, geschaeftsjahr=geschaeftsjahr
        ).first()
        saldo = Decimal(str(saldo_record.saldo_aktuell)) if saldo_record else Decimal('0')

        if saldo == 0:
            continue

        eintrag = {'konto': konto, 'saldo': abs(saldo)}

        if konto.kontenklasse in (6, 9):
            aufwendungen.append(eintrag)
            summe_aufwendungen += abs(saldo)
        else:
            ertraege.append(eintrag)
            summe_ertraege += abs(saldo)

    return {
        'aufwendungen': aufwendungen,
        'ertraege': ertraege,
        'summe_aufwendungen': summe_aufwendungen,
        'summe_ertraege': summe_ertraege,
        'jahresergebnis': summe_ertraege - summe_aufwendungen,
    }
