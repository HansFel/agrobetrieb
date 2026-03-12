"""Fakturierung-Service: Rechnungen/Gutschriften erstellen & PDF."""
import io
from datetime import datetime, timedelta
from decimal import Decimal

from app.extensions import db
from app.models.fakturierung import Faktura, FakturaPosition, Kunde
from app.models.buchhaltung import Konto
from app.services.buchung_service import buchung_erstellen, buchung_stornieren


# Konten-Zuordnung nach Rechnungsart
ART_HABEN_KONTO = {
    'dienstleistung': '7900',
    'materialverkauf': '7900',
    'maschinenarbeit': '7100',
    'holzverkauf': '7300',
    'pacht': '7700',
    'sonstiges': '7900',
}

FORDERUNG_KONTO_NR = '2900'


def _konto_by_nr(kontonummer):
    """Gibt Konto-ID für eine Kontonummer zurück."""
    k = Konto.query.filter_by(kontonummer=kontonummer, aktiv=True).first()
    return k.id if k else None


def faktura_erstellen(kunde_id, geschaeftsjahr, art, datum,
                      positionen_daten, haben_konto_id, forderung_konto_id,
                      betreff, faellig_am, notizen, erstellt_von,
                      ist_vorlage=False, vorlage_name=None):
    """Erstellt eine neue Faktura mit Positionen und automatischer Buchung."""
    betrag_gesamt = Decimal('0')
    for p in positionen_daten:
        betrag_gesamt += Decimal(str(p['betrag']))

    if betrag_gesamt <= 0:
        raise ValueError('Gesamtbetrag muss größer als 0 sein.')

    if not haben_konto_id:
        konto_nr = ART_HABEN_KONTO.get(art)
        if konto_nr:
            haben_konto_id = _konto_by_nr(konto_nr)

    if not forderung_konto_id:
        forderung_konto_id = _konto_by_nr(FORDERUNG_KONTO_NR)

    if ist_vorlage:
        fakturanummer = f'V-{vorlage_name or "Vorlage"}'
    else:
        fakturanummer = Faktura.naechste_nummer(geschaeftsjahr)

    faktura = Faktura(
        kunde_id=kunde_id,
        geschaeftsjahr=geschaeftsjahr,
        fakturanummer=fakturanummer,
        datum=datum,
        faellig_am=faellig_am,
        art=art,
        betreff=betreff,
        betrag_netto=betrag_gesamt,
        haben_konto_id=haben_konto_id,
        forderung_konto_id=forderung_konto_id,
        status='erstellt',
        ist_vorlage=ist_vorlage,
        vorlage_name=vorlage_name,
        notizen=notizen,
        erstellt_von=erstellt_von,
    )
    db.session.add(faktura)
    db.session.flush()

    for i, p in enumerate(positionen_daten):
        pos = FakturaPosition(
            faktura_id=faktura.id,
            bezeichnung=p['bezeichnung'],
            menge=Decimal(str(p['menge'])) if p.get('menge') else None,
            einheit=p.get('einheit'),
            einzelpreis=Decimal(str(p['einzelpreis'])) if p.get('einzelpreis') else None,
            betrag=Decimal(str(p['betrag'])),
            sortierung=p.get('sortierung', i),
        )
        db.session.add(pos)

    if not ist_vorlage and haben_konto_id and forderung_konto_id:
        buchungstext = f'Rechnung {fakturanummer}'
        if betreff:
            buchungstext += f' - {betreff}'
        buchung = buchung_erstellen(
            geschaeftsjahr=geschaeftsjahr,
            datum=datum,
            soll_konto_id=forderung_konto_id,
            haben_konto_id=haben_konto_id,
            betrag=betrag_gesamt,
            buchungstext=buchungstext,
            erstellt_von=erstellt_von,
            beleg_nummer=fakturanummer,
            beleg_datum=datum,
            buchungsart='manuell',
        )
        faktura.buchung_id = buchung.id
    else:
        db.session.commit()

    return faktura


def faktura_als_bezahlt_markieren(faktura_id, bezahlt_datum, bank_konto_id,
                                   erstellt_von):
    """Markiert Faktura als bezahlt und erstellt Zahlungsbuchung."""
    faktura = Faktura.query.get_or_404(faktura_id)

    if faktura.status == 'bezahlt':
        raise ValueError('Rechnung ist bereits als bezahlt markiert.')
    if faktura.status == 'storniert':
        raise ValueError('Stornierte Rechnung kann nicht als bezahlt markiert werden.')

    forderung_konto_id = faktura.forderung_konto_id
    if not forderung_konto_id:
        forderung_konto_id = _konto_by_nr(FORDERUNG_KONTO_NR)

    if bank_konto_id and forderung_konto_id:
        buchungstext = f'Zahlung {faktura.fakturanummer}'
        if faktura.kunde:
            buchungstext += f' - {faktura.kunde.name}'

        bezahlt_buchung = buchung_erstellen(
            geschaeftsjahr=faktura.geschaeftsjahr,
            datum=bezahlt_datum,
            soll_konto_id=bank_konto_id,
            haben_konto_id=forderung_konto_id,
            betrag=faktura.betrag_netto,
            buchungstext=buchungstext,
            erstellt_von=erstellt_von,
            beleg_nummer=faktura.fakturanummer,
            beleg_datum=bezahlt_datum,
            buchungsart='manuell',
        )
        faktura.bezahlt_buchung_id = bezahlt_buchung.id

    faktura.status = 'bezahlt'
    db.session.commit()
    return faktura


def faktura_stornieren(faktura_id, user_id):
    """Storniert eine Faktura und die zugehörige Buchung."""
    faktura = Faktura.query.get_or_404(faktura_id)

    if faktura.status == 'storniert':
        raise ValueError('Rechnung ist bereits storniert.')
    if faktura.status == 'bezahlt':
        raise ValueError('Bezahlte Rechnung kann nicht storniert werden.')

    if faktura.buchung_id:
        buchung_stornieren(
            buchung_id=faktura.buchung_id,
            storniert_von=user_id,
            grund=f'Storno Rechnung {faktura.fakturanummer}',
        )

    faktura.status = 'storniert'
    db.session.commit()
    return faktura


def faktura_aus_vorlage(vorlage_id, datum, geschaeftsjahr, erstellt_von):
    """Erstellt eine neue Faktura aus einer Vorlage."""
    vorlage = Faktura.query.get_or_404(vorlage_id)
    if not vorlage.ist_vorlage:
        raise ValueError('Ausgewählte Rechnung ist keine Vorlage.')

    positionen_daten = []
    for pos in vorlage.positionen:
        positionen_daten.append({
            'bezeichnung': pos.bezeichnung,
            'menge': pos.menge,
            'einheit': pos.einheit,
            'einzelpreis': pos.einzelpreis,
            'betrag': pos.betrag,
            'sortierung': pos.sortierung,
        })

    faellig_am = datum + timedelta(days=14)

    return faktura_erstellen(
        kunde_id=vorlage.kunde_id,
        geschaeftsjahr=geschaeftsjahr,
        art=vorlage.art,
        datum=datum,
        positionen_daten=positionen_daten,
        haben_konto_id=vorlage.haben_konto_id,
        forderung_konto_id=vorlage.forderung_konto_id,
        betreff=vorlage.betreff,
        faellig_am=faellig_am,
        notizen=None,
        erstellt_von=erstellt_von,
    )


def gutschrift_empfaenger_sicherstellen(empfaenger_typ, kunde_id=None,
                                        name=None, adresse=None, ort=None,
                                        plz=None, iban=None):
    if empfaenger_typ == 'kunde':
        if not kunde_id:
            raise ValueError('Kein Kunde ausgewählt.')
        return int(kunde_id)

    if empfaenger_typ == 'dritter':
        if not name or not name.strip():
            raise ValueError('Name des Empfängers ist erforderlich.')

        kunde = Kunde(
            name=name.strip(),
            adresse=adresse.strip() if adresse else None,
            ort=ort.strip() if ort else None,
            plz=plz.strip() if plz else None,
            iban=iban.strip() if iban else None,
            aktiv=True,
        )
        db.session.add(kunde)
        db.session.flush()
        return kunde.id

    raise ValueError(f'Unbekannter Empfänger-Typ: {empfaenger_typ}')


def gutschrift_erstellen(kunde_id, geschaeftsjahr, art, datum,
                          positionen_daten, haben_konto_id, forderung_konto_id,
                          betreff, notizen, erstellt_von, storno_von_id=None):
    """Erstellt eine Gutschrift mit Gegenbuchung (Soll/Haben vertauscht)."""
    betrag_gesamt = Decimal('0')
    for p in positionen_daten:
        betrag_gesamt += Decimal(str(p['betrag']))

    if betrag_gesamt <= 0:
        raise ValueError('Gesamtbetrag muss größer als 0 sein.')

    if not haben_konto_id:
        konto_nr = ART_HABEN_KONTO.get(art)
        if konto_nr:
            haben_konto_id = _konto_by_nr(konto_nr)

    if not forderung_konto_id:
        forderung_konto_id = _konto_by_nr(FORDERUNG_KONTO_NR)

    gutschrift_nummer = Faktura.naechste_gutschrift_nummer(geschaeftsjahr)

    gutschrift = Faktura(
        kunde_id=kunde_id,
        geschaeftsjahr=geschaeftsjahr,
        fakturanummer=gutschrift_nummer,
        datum=datum,
        faellig_am=datum,
        art=art,
        betreff=betreff,
        betrag_netto=betrag_gesamt,
        haben_konto_id=haben_konto_id,
        forderung_konto_id=forderung_konto_id,
        status='erstellt',
        ist_vorlage=False,
        notizen=notizen,
        erstellt_von=erstellt_von,
        dokument_typ='gutschrift',
        storno_von_id=storno_von_id,
    )
    db.session.add(gutschrift)
    db.session.flush()

    for i, p in enumerate(positionen_daten):
        pos = FakturaPosition(
            faktura_id=gutschrift.id,
            bezeichnung=p['bezeichnung'],
            menge=Decimal(str(p['menge'])) if p.get('menge') else None,
            einheit=p.get('einheit'),
            einzelpreis=Decimal(str(p['einzelpreis'])) if p.get('einzelpreis') else None,
            betrag=Decimal(str(p['betrag'])),
            sortierung=p.get('sortierung', i),
        )
        db.session.add(pos)

    if haben_konto_id and forderung_konto_id:
        buchungstext = f'Gutschrift {gutschrift_nummer}'
        if betreff:
            buchungstext += f' - {betreff}'
        buchung = buchung_erstellen(
            geschaeftsjahr=geschaeftsjahr,
            datum=datum,
            soll_konto_id=haben_konto_id,
            haben_konto_id=forderung_konto_id,
            betrag=betrag_gesamt,
            buchungstext=buchungstext,
            erstellt_von=erstellt_von,
            beleg_nummer=gutschrift_nummer,
            beleg_datum=datum,
            buchungsart='manuell',
        )
        gutschrift.buchung_id = buchung.id
    else:
        db.session.commit()

    return gutschrift


def faktura_pdf(faktura_id):
    """Erzeugt PDF-Bytes für eine Faktura."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib.enums import TA_RIGHT
    from app.models.betrieb import Betrieb

    faktura = Faktura.query.get_or_404(faktura_id)
    betrieb = Betrieb.query.first()
    kunde = faktura.kunde

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=15 * mm, bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    style_normal = styles['Normal']
    style_normal.fontSize = 9
    style_bold = ParagraphStyle('bold', parent=style_normal, fontName='Helvetica-Bold')
    style_right = ParagraphStyle('right', parent=style_normal, alignment=TA_RIGHT)

    elements = []

    # Absender
    absender_zeilen = []
    if betrieb:
        absender_zeilen.append(betrieb.name)
        if betrieb.strasse:
            absender_zeilen.append(betrieb.strasse)
        ort_teil = ' '.join(filter(None, [betrieb.plz, betrieb.ort]))
        if ort_teil:
            absender_zeilen.append(ort_teil)
        if betrieb.telefon:
            absender_zeilen.append(f'Tel: {betrieb.telefon}')
        if betrieb.email:
            absender_zeilen.append(f'E-Mail: {betrieb.email}')

    empfaenger_zeilen = []
    if kunde:
        empfaenger_zeilen.append(f'<b>{kunde.name}</b>')
        if kunde.adresse:
            empfaenger_zeilen.append(kunde.adresse)
        ort = ' '.join(filter(None, [kunde.plz, kunde.ort]))
        if ort:
            empfaenger_zeilen.append(ort)

    dok_typ_label = 'Gutschrift Nr.:' if faktura.ist_gutschrift else 'Rechnung Nr.:'
    rechnungs_info = [
        [dok_typ_label, faktura.fakturanummer],
        ['Datum:', faktura.datum.strftime('%d.%m.%Y')],
        ['Fällig bis:', faktura.faellig_am.strftime('%d.%m.%Y') if faktura.faellig_am else '-'],
        ['Art:', faktura.art_bezeichnung],
    ]
    if faktura.ist_gutschrift and faktura.storno_von:
        rechnungs_info.append(['Bezug Rechnung:', faktura.storno_von.fakturanummer])

    absender_text = '<br/>'.join(absender_zeilen)
    empfaenger_text = '<br/>'.join(empfaenger_zeilen)

    kopf_data = [
        [Paragraph(absender_text, style_normal),
         Paragraph(empfaenger_text, style_normal)],
    ]
    kopf_table = Table(kopf_data, colWidths=[90 * mm, 80 * mm])
    kopf_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(kopf_table)
    elements.append(Spacer(1, 6 * mm))

    info_table = Table(rechnungs_info, colWidths=[40 * mm, 130 * mm])
    info_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 6 * mm))
    elements.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#343a40')))
    elements.append(Spacer(1, 4 * mm))

    if faktura.betreff:
        elements.append(Paragraph(f'<b>Betreff: {faktura.betreff}</b>', style_normal))
        elements.append(Spacer(1, 4 * mm))

    # Währung
    waehrung = '€'
    if betrieb and betrieb.waehrung:
        waehrung = betrieb.waehrung

    # Positionen
    pos_data = [['Pos.', 'Bezeichnung', 'Menge', 'Einheit', 'Einzelpreis', 'Betrag']]
    for i, pos in enumerate(faktura.positionen, 1):
        menge_str = f'{pos.menge:,.3f}'.replace(',', 'X').replace('.', ',').replace('X', '.') if pos.menge else ''
        ep_str = f'{pos.einzelpreis:,.2f} {waehrung}'.replace(',', 'X').replace('.', ',').replace('X', '.') if pos.einzelpreis else ''
        betrag_str = f'{pos.betrag:,.2f} {waehrung}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        pos_data.append([str(i), pos.bezeichnung, menge_str, pos.einheit or '', ep_str, betrag_str])

    gesamt_str = f'{faktura.betrag_netto:,.2f} {waehrung}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    pos_data.append(['', '', '', '', Paragraph('<b>Gesamt:</b>', style_normal),
                     Paragraph(f'<b>{gesamt_str}</b>', style_normal)])

    pos_table = Table(pos_data, colWidths=[10*mm, 75*mm, 20*mm, 15*mm, 30*mm, 20*mm], repeatRows=1)
    pos_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#343a40')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
        ('ALIGN', (4, 1), (5, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#dee2e6')),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#343a40')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f8f9fa')),
    ]))
    elements.append(pos_table)
    elements.append(Spacer(1, 8 * mm))

    # Zahlungsinformationen
    if not faktura.ist_gutschrift and betrieb:
        elements.append(HRFlowable(width='100%', thickness=0.5, color=colors.grey))
        elements.append(Spacer(1, 3 * mm))
        elements.append(Paragraph('<b>Zahlungsinformationen</b>', style_bold))

        bank_info = []
        if betrieb.name:
            bank_info.append(f'Kontoinhaber: {betrieb.name}')
        if betrieb.iban:
            bank_info.append(f'IBAN: {betrieb.iban}')
        if betrieb.bic:
            bank_info.append(f'BIC: {betrieb.bic}')
        if betrieb.bank_name:
            bank_info.append(f'Bank: {betrieb.bank_name}')
        if faktura.faellig_am:
            bank_info.append(f'Zahlungsziel: {faktura.faellig_am.strftime("%d.%m.%Y")}')
        bank_info.append(f'Verwendungszweck: {faktura.fakturanummer}')

        for zeile in bank_info:
            elements.append(Paragraph(zeile, style_normal))

    if faktura.notizen:
        elements.append(Spacer(1, 4 * mm))
        elements.append(Paragraph(f'<i>Hinweis: {faktura.notizen}</i>', style_normal))

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()
