from datetime import datetime
from decimal import Decimal
from app.extensions import db


class Kunde(db.Model):
    """Kunde / Gutschrift-Empfänger."""
    __tablename__ = 'kunde'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    adresse = db.Column(db.Text)
    ort = db.Column(db.Text)
    plz = db.Column(db.Text)
    email = db.Column(db.Text)
    telefon = db.Column(db.Text)
    uid_nummer = db.Column(db.Text)
    iban = db.Column(db.Text)
    notizen = db.Column(db.Text)
    aktiv = db.Column(db.Boolean, default=True, nullable=False)
    konto_id = db.Column(db.Integer,
                         db.ForeignKey('konto.id', ondelete='SET NULL'),
                         nullable=True)

    konto = db.relationship('Konto')
    fakturen = db.relationship('Faktura', back_populates='kunde',
                               order_by='Faktura.datum.desc()')
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Kunde {self.name}>'

    @property
    def adresse_vollstaendig(self):
        teile = []
        if self.adresse:
            teile.append(self.adresse)
        ort_teil = ' '.join(filter(None, [self.plz, self.ort]))
        if ort_teil:
            teile.append(ort_teil)
        return '\n'.join(teile)


FAKTURA_ARTEN = {
    'dienstleistung': 'Dienstleistung',
    'materialverkauf': 'Materialverkauf',
    'maschinenarbeit': 'Maschinenarbeit',
    'holzverkauf': 'Holzverkauf',
    'pacht': 'Pacht / Miete',
    'sonstiges': 'Sonstiges',
}

GUTSCHRIFT_ARTEN = {
    'dienstleistung': 'Dienstleistung',
    'materialverkauf': 'Materialverkauf',
    'maschinenarbeit': 'Maschinenarbeit',
    'holzverkauf': 'Holzverkauf',
    'sonstiges': 'Sonstige Auszahlung',
}

FAKTURA_STATUS = {
    'erstellt': 'Erstellt',
    'versendet': 'Versendet',
    'bezahlt': 'Bezahlt',
    'storniert': 'Storniert',
}

DOKUMENT_TYPEN = {
    'rechnung': 'Rechnung',
    'gutschrift': 'Gutschrift',
}


class Faktura(db.Model):
    """Rechnung oder Gutschrift."""
    __tablename__ = 'faktura'

    id = db.Column(db.Integer, primary_key=True)
    kunde_id = db.Column(db.Integer,
                         db.ForeignKey('kunde.id', ondelete='RESTRICT'),
                         nullable=False)
    geschaeftsjahr = db.Column(db.Integer, nullable=False)
    fakturanummer = db.Column(db.Text, nullable=False, unique=True)
    datum = db.Column(db.Date, nullable=False)
    faellig_am = db.Column(db.Date)
    art = db.Column(db.Text, nullable=False)
    betreff = db.Column(db.Text)
    betrag_netto = db.Column(db.Numeric(12, 2), nullable=False)

    haben_konto_id = db.Column(db.Integer,
                               db.ForeignKey('konto.id', ondelete='RESTRICT'),
                               nullable=True)
    forderung_konto_id = db.Column(db.Integer,
                                   db.ForeignKey('konto.id', ondelete='RESTRICT'),
                                   nullable=True)
    buchung_id = db.Column(db.Integer,
                           db.ForeignKey('buchung.id', ondelete='SET NULL'),
                           nullable=True)
    bezahlt_buchung_id = db.Column(db.Integer,
                                   db.ForeignKey('buchung.id', ondelete='SET NULL'),
                                   nullable=True)

    status = db.Column(db.Text, default='erstellt', nullable=False)
    ist_vorlage = db.Column(db.Boolean, default=False, nullable=False)
    vorlage_name = db.Column(db.Text)
    notizen = db.Column(db.Text)
    erstellt_von = db.Column(db.Integer,
                             db.ForeignKey('user.id', ondelete='SET NULL'),
                             nullable=True)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    dokument_typ = db.Column(db.Text, nullable=False, default='rechnung')
    storno_von_id = db.Column(db.Integer,
                              db.ForeignKey('faktura.id', ondelete='SET NULL'),
                              nullable=True)

    # Relationships
    kunde = db.relationship('Kunde', back_populates='fakturen')
    haben_konto = db.relationship('Konto', foreign_keys=[haben_konto_id])
    forderung_konto = db.relationship('Konto', foreign_keys=[forderung_konto_id])
    buchung = db.relationship('Buchung', foreign_keys=[buchung_id])
    bezahlt_buchung = db.relationship('Buchung', foreign_keys=[bezahlt_buchung_id])
    erstellt_von_user = db.relationship('User', foreign_keys=[erstellt_von])
    storno_von = db.relationship('Faktura', foreign_keys=[storno_von_id],
                                 remote_side='Faktura.id',
                                 backref=db.backref('gutschriften', lazy='dynamic'))
    positionen = db.relationship('FakturaPosition', back_populates='faktura',
                                 order_by='FakturaPosition.sortierung',
                                 cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Faktura {self.fakturanummer} {self.betrag_netto}>'

    @property
    def art_bezeichnung(self):
        return FAKTURA_ARTEN.get(self.art, self.art)

    @property
    def status_bezeichnung(self):
        return FAKTURA_STATUS.get(self.status, self.status)

    @property
    def ist_offen(self):
        return self.status in ('erstellt', 'versendet')

    @property
    def ist_gutschrift(self):
        return self.dokument_typ == 'gutschrift'

    @property
    def dokument_typ_bezeichnung(self):
        return DOKUMENT_TYPEN.get(self.dokument_typ, self.dokument_typ)

    @classmethod
    def naechste_gutschrift_nummer(cls, geschaeftsjahr):
        """Nächste Gutschrift-Nummer: GS-YYYY-NNN."""
        letzte = cls.query.filter_by(
            geschaeftsjahr=geschaeftsjahr,
            dokument_typ='gutschrift',
            ist_vorlage=False,
        ).order_by(cls.id.desc()).first()

        if not letzte:
            return f'GS-{geschaeftsjahr}-001'
        try:
            nr = int(letzte.fakturanummer.split('-')[2])
        except (IndexError, ValueError):
            nr = 0
        return f'GS-{geschaeftsjahr}-{nr + 1:03d}'

    @classmethod
    def naechste_nummer(cls, geschaeftsjahr):
        """Nächste Rechnungs-Nummer: YYYY-NNN."""
        letzte = cls.query.filter_by(
            geschaeftsjahr=geschaeftsjahr,
            dokument_typ='rechnung',
            ist_vorlage=False,
        ).order_by(cls.id.desc()).first()

        if not letzte:
            return f'{geschaeftsjahr}-001'
        try:
            nr = int(letzte.fakturanummer.split('-')[1])
        except (IndexError, ValueError):
            nr = 0
        return f'{geschaeftsjahr}-{nr + 1:03d}'


class FakturaPosition(db.Model):
    """Position auf einer Faktura."""
    __tablename__ = 'faktura_position'

    id = db.Column(db.Integer, primary_key=True)
    faktura_id = db.Column(db.Integer,
                           db.ForeignKey('faktura.id', ondelete='CASCADE'),
                           nullable=False)
    bezeichnung = db.Column(db.Text, nullable=False)
    menge = db.Column(db.Numeric(10, 3))
    einheit = db.Column(db.Text)
    einzelpreis = db.Column(db.Numeric(12, 2))
    betrag = db.Column(db.Numeric(12, 2), nullable=False)
    sortierung = db.Column(db.Integer, default=0, nullable=False)

    faktura = db.relationship('Faktura', back_populates='positionen')

    def __repr__(self):
        return f'<FakturaPosition {self.bezeichnung} {self.betrag}>'

    @property
    def betrag_berechnet(self):
        if self.menge and self.einzelpreis:
            return Decimal(str(self.menge)) * Decimal(str(self.einzelpreis))
        return Decimal(str(self.betrag))
