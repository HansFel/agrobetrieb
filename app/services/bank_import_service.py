import csv
import io
import zlib
from datetime import date
from decimal import Decimal, InvalidOperation

from app.extensions import db
from app.models.buchhaltung import Buchung, Konto, Buchungsschluessel
from app.services.buchung_service import buchung_erstellen


def zeilen_hash(datum, betrag, text):
    raw = f'{datum.isoformat()}|{betrag}|{text}'.encode()
    return zlib.crc32(raw) & 0x7FFFFFFF


def _parse_betrag(wert_str, dezimaltrennzeichen=',', vorzeichen_umkehren=False):
    wert_str = (wert_str or '').strip()
    if dezimaltrennzeichen == ',':
        wert_str = wert_str.replace('.', '').replace(',', '.')
    else:
        wert_str = wert_str.replace(',', '')
    for token in ['EUR', 'CHF', '€', '$']:
        wert_str = wert_str.replace(token, '').strip()
    betrag = Decimal(wert_str)
    return -betrag if vorzeichen_umkehren else betrag


def _parse_datum(wert_str, datumsformat='%d.%m.%Y'):
    from datetime import datetime

    return datetime.strptime((wert_str or '').strip(), datumsformat).date()


def _finde_gegenkonto(buchungstext, betrag_positiv):
    schluessel = Buchungsschluessel.query.filter(
        Buchungsschluessel.aktiv == True,
        Buchungsschluessel.suchbegriffe.isnot(None),
        Buchungsschluessel.suchbegriffe != '',
    ).order_by(Buchungsschluessel.sortierung, Buchungsschluessel.kuerzel).all()

    text_lower = (buchungstext or '').lower()
    for bs in schluessel:
        begriffe = [teil.strip() for teil in (bs.suchbegriffe or '').split(',') if teil.strip()]
        for begriff in begriffe:
            if begriff.lower() in text_lower:
                if betrag_positiv and bs.haben_konto_id:
                    return bs.haben_konto_id, bs.kuerzel
                if not betrag_positiv and bs.soll_konto_id:
                    return bs.soll_konto_id, bs.kuerzel
                return None, bs.kuerzel

    return None, None


def csv_vorschau(dateiinhalt, config, geschaeftsjahr=None):
    if isinstance(dateiinhalt, bytes):
        dateiinhalt = dateiinhalt.decode(config.encoding or 'utf-8-sig')

    reader = csv.reader(io.StringIO(dateiinhalt), delimiter=config.trennzeichen or ';')
    zeilen = list(reader)
    datenzeilen = zeilen[config.kopfzeilen_ueberspringen or 0:]

    ergebnis = []
    for index, row in enumerate(datenzeilen):
        eintrag = {
            'zeilen_nr': (config.kopfzeilen_ueberspringen or 0) + index + 1,
            'roh_zeile': (config.trennzeichen or ';').join(row),
            'fehler': None,
            'datum': None,
            'valuta': None,
            'betrag': None,
            'text': '',
            'referenz': None,
            'gegenkonto_id': None,
            'schluessel_kuerzel': None,
            'hash': None,
        }

        try:
            eintrag['datum'] = _parse_datum(row[config.spalte_datum], config.datumsformat or '%d.%m.%Y')
        except (IndexError, ValueError) as exc:
            eintrag['fehler'] = f'Datum: {exc}'

        if config.spalte_valuta is not None:
            try:
                eintrag['valuta'] = _parse_datum(row[config.spalte_valuta], config.datumsformat or '%d.%m.%Y')
            except (IndexError, ValueError):
                eintrag['valuta'] = None

        try:
            eintrag['betrag'] = _parse_betrag(
                row[config.spalte_betrag],
                config.dezimaltrennzeichen or ',',
                config.vorzeichen_umkehren or False,
            )
        except (IndexError, ValueError, InvalidOperation) as exc:
            eintrag['fehler'] = f'Betrag: {exc}'

        try:
            eintrag['text'] = row[config.spalte_text].strip()
        except IndexError:
            eintrag['fehler'] = 'Text-Spalte fehlt'

        if config.spalte_referenz is not None:
            try:
                eintrag['referenz'] = row[config.spalte_referenz].strip()
            except IndexError:
                eintrag['referenz'] = None

        if eintrag['datum'] and eintrag['betrag'] is not None and eintrag['text']:
            eintrag['hash'] = zeilen_hash(eintrag['datum'], eintrag['betrag'], eintrag['text'])
            gk_id, kuerzel = _finde_gegenkonto(eintrag['text'], eintrag['betrag'] > 0)
            eintrag['gegenkonto_id'] = gk_id
            eintrag['schluessel_kuerzel'] = kuerzel

        # GJ-Prüfung: Datum muss im gewählten Geschäftsjahr liegen
        if geschaeftsjahr and eintrag['datum'] and eintrag['datum'].year != geschaeftsjahr:
            eintrag['ausserhalb_gj'] = True
        else:
            eintrag['ausserhalb_gj'] = False

        ergebnis.append(eintrag)

    return ergebnis


def csv_importieren(dateiinhalt, config, bank_konto_id, geschaeftsjahr, erstellt_von, manuelle_gegenkonten=None):
    manuelle_gegenkonten = manuelle_gegenkonten or {}
    if isinstance(dateiinhalt, bytes):
        dateiinhalt = dateiinhalt.decode(config.encoding or 'utf-8-sig')

    konto_ertrag = Konto.query.filter_by(kontonummer='7900', aktiv=True).first()
    konto_aufwand = Konto.query.filter_by(kontonummer='6900', aktiv=True).first()
    bank_konto = db.session.get(Konto, bank_konto_id)

    if not bank_konto:
        return {'importiert': 0, 'uebersprungen': 0, 'fehler': ['Ungueltiges Bank-Konto.'], 'erster_import': False}
    if not konto_ertrag or not konto_aufwand:
        return {
            'importiert': 0,
            'uebersprungen': 0,
            'fehler': ['Konten 7900 und 6900 fehlen. Bitte zuerst den Standard-Kontenplan anlegen.'],
            'erster_import': False,
        }

    bestehende_hashes = {
        buchung.bank_transaktion_id
        for buchung in Buchung.query.filter(Buchung.bank_transaktion_id.isnot(None), Buchung.storniert == False).all()
    }
    erster_import = not bestehende_hashes

    importiert = 0
    uebersprungen = 0
    fehler = []

    for eintrag in csv_vorschau(dateiinhalt, config):
        if eintrag['fehler']:
            fehler.append(f"Zeile {eintrag['zeilen_nr']}: {eintrag['fehler']}")
            continue
        if eintrag['datum'].year != geschaeftsjahr:
            uebersprungen += 1
            continue
        if eintrag['hash'] in bestehende_hashes:
            uebersprungen += 1
            continue

        gegenkonto_id = manuelle_gegenkonten.get(str(eintrag['hash'])) or eintrag['gegenkonto_id']
        if not gegenkonto_id:
            gegenkonto_id = konto_ertrag.id if eintrag['betrag'] > 0 else konto_aufwand.id

        try:
            betrag_abs = abs(Decimal(str(eintrag['betrag'])))
            if eintrag['betrag'] > 0:
                soll_konto_id = bank_konto.id
                haben_konto_id = int(gegenkonto_id)
            else:
                soll_konto_id = int(gegenkonto_id)
                haben_konto_id = bank_konto.id

            buchung_erstellen(
                geschaeftsjahr=geschaeftsjahr,
                datum=eintrag['datum'],
                soll_konto_id=soll_konto_id,
                haben_konto_id=haben_konto_id,
                betrag=betrag_abs,
                buchungstext=eintrag['text'][:200] or 'Bank-Import',
                erstellt_von=erstellt_von,
                beleg_nummer=eintrag.get('referenz') or None,
                beleg_datum=eintrag.get('valuta') or eintrag['datum'],
                buchungsart='import',
                bank_transaktion_id=eintrag['hash'],
            )
            bestehende_hashes.add(eintrag['hash'])
            importiert += 1
        except Exception as exc:
            db.session.rollback()
            fehler.append(f"Zeile {eintrag['zeilen_nr']}: {exc}")

    return {
        'importiert': importiert,
        'uebersprungen': uebersprungen,
        'fehler': fehler,
        'erster_import': erster_import,
    }