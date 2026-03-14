"""
Rollensystem für AgroBetrieb.

Rollen und deren Berechtigungen:
- betriebsadmin: Vollständiger Zugriff, verwaltet Benutzer und Betrieb
- buchhaltung: Nur Buchhaltung (Journal, Kontenplan, Bank-Import, Rechnungen)
- mitglied: Vollständiger Zugriff (Default-Member)
- gelegentlich: Nur Arbeitsdaten (Einsätze, Maschinen-Belegung)
- praktikand: Lesezugriff + Arbeitsdaten eingeben
- packstelle: Externer Zugang: Nur Sortierergebnisse eintragen
"""

# Rollenübersicht
ROLLEN = {
    'betriebsadmin': {
        'name': 'Betriebsadmin',
        'beschreibung': 'Vollzugriff, verwaltet Benutzer und Betriebsdaten',
        'prioritaet': 1000,
    },
    'mitglied': {
        'name': 'Mitglied',
        'beschreibung': 'Vollzugriff wie Admin (außer Benutzerverwaltung)',
        'prioritaet': 500,
    },
    'buchhaltung': {
        'name': 'Buchhaltung',
        'beschreibung': 'Nur Buchhaltung: Journal, Konten, Bank-Import, Rechnungen',
        'prioritaet': 300,
    },
    'gelegentlich': {
        'name': 'Gelegentlicher Mitarbeiter',
        'beschreibung': 'Nur Arbeitsdaten: Einsätze, Maschinen-Belegung',
        'prioritaet': 100,
    },
    'praktikand': {
        'name': 'Praktikand',
        'beschreibung': 'Lesezugriff + Arbeitsdaten eingeben',
        'prioritaet': 50,
    },
    'packstelle': {
        'name': 'Packstelle',
        'beschreibung': 'Externer Zugang: Nur Sortierergebnisse eintragen',
        'prioritaet': 75,
    },
}

# Detaillierte Berechtigungen pro Modul
BERECHTIGUNGEN = {
    'betriebsadmin': {
        'dashboard': ['view'],
        'betrieb': ['view', 'edit'],
        'benutzer': ['view', 'create', 'edit', 'delete'],
        'maschinen': ['view', 'create', 'edit', 'delete'],
        'einsaetze': ['view', 'create', 'edit', 'delete'],
        'buchhaltung': ['view', 'create', 'edit', 'delete'],
        'fakturierung': ['view', 'create', 'edit', 'delete'],
        'lager': ['view', 'create', 'edit', 'delete'],
        'legehennen': ['view', 'create', 'edit', 'delete'],
        'milchvieh': ['view', 'create', 'edit', 'delete'],
    },
    'mitglied': {
        'dashboard': ['view'],
        'betrieb': ['view'],
        'benutzer': [],  # Kein Zugriff
        'maschinen': ['view', 'create', 'edit'],
        'einsaetze': ['view', 'create', 'edit', 'delete'],
        'buchhaltung': ['view', 'create', 'edit', 'delete'],
        'fakturierung': ['view', 'create', 'edit', 'delete'],
        'lager': ['view', 'create', 'edit', 'delete'],
        'legehennen': ['view', 'create', 'edit', 'delete'],
        'milchvieh': ['view', 'create', 'edit', 'delete'],
    },
    'buchhaltung': {
        'dashboard': ['view'],
        'betrieb': ['view'],
        'benutzer': [],
        'maschinen': ['view'],
        'einsaetze': [],
        'buchhaltung': ['view', 'create', 'edit', 'delete'],
        'fakturierung': ['view', 'create', 'edit', 'delete'],
        'lager': [],
    },
    'gelegentlich': {
        'dashboard': ['view'],
        'betrieb': [],
        'benutzer': [],
        'maschinen': ['view'],
        'einsaetze': ['view', 'create', 'edit'],
        'buchhaltung': [],
        'fakturierung': [],
        'lager': [],
    },
    'praktikand': {
        'dashboard': ['view'],
        'betrieb': [],
        'benutzer': [],
        'maschinen': ['view'],
        'einsaetze': ['view', 'create'],
        'buchhaltung': ['view'],
        'fakturierung': ['view'],
        'lager': ['view'],
        'legehennen': ['view'],
        'milchvieh': ['view'],
    },
    'packstelle': {
        'dashboard': ['view'],
        'betrieb': [],
        'benutzer': [],
        'maschinen': [],
        'einsaetze': [],
        'buchhaltung': [],
        'fakturierung': [],
        'lager': [],
        'legehennen': ['view'],
        'sortierergebnis': ['view', 'create', 'edit'],
    },
}


def hat_berechtigung(user, modul, aktion):
    """
    Prüft, ob Benutzer Berechtigung für Modul+Aktion hat.
    
    Args:
        user: User-Objekt
        modul: String (z.B. 'buchhaltung', 'einsaetze')
        aktion: String (z.B. 'view', 'create', 'edit', 'delete')
    
    Returns:
        True wenn Berechtigung vorhanden
    """
    if not user or not user.aktiv:
        return False
    
    rolle_perms = BERECHTIGUNGEN.get(user.rolle, {})
    modul_perms = rolle_perms.get(modul, [])

    if aktion not in modul_perms:
        return False
    return ist_modul_lizenziert(modul)


def hat_modul_zugriff(user, modul):
    """Prüft ob Benutzer irgendwelche Berechtigungen im Modul hat
    UND das Modul im Betrieb lizenziert ist."""
    if not user or not user.aktiv:
        return False
    rolle_perms = BERECHTIGUNGEN.get(user.rolle, {})
    modul_perms = rolle_perms.get(modul, [])
    if not modul_perms:
        return False
    return ist_modul_lizenziert(modul)


# Module die eine explizite Betrieb-Lizenz benötigen
LIZENZPFLICHTIGE_MODULE = {'legehennen', 'sortierergebnis', 'milchvieh'}

# Mapping: Modul-Name → Betrieb-Feld (wenn abweichend)
_MODUL_FELD_MAP = {
    'sortierergebnis': 'modul_legehennen',
}


def ist_modul_lizenziert(modul):
    """Prüft ob ein Modul im aktuellen Betrieb freigeschaltet ist."""
    if modul not in LIZENZPFLICHTIGE_MODULE:
        return True  # Basis-Module sind immer verfügbar
    from app.models.betrieb import Betrieb
    betrieb = Betrieb.query.first()
    if not betrieb:
        return False
    if betrieb.ist_testbetrieb:
        return True
    modul_feld = _MODUL_FELD_MAP.get(modul, f'modul_{modul}')
    return bool(getattr(betrieb, modul_feld, False))


def ist_betriebsadmin(user):
    """Ist Betriebsadmin?"""
    return user and user.aktiv and user.rolle == 'betriebsadmin'


def ist_buchhaltung(user):
    """Ist Buchhaltung?"""
    return user and user.aktiv and user.rolle == 'buchhaltung'


def kann_arbeitsdaten_eingeben(user):
    """Kann Arbeitsdaten eingeben (gelegentlich+)?"""
    return user and user.aktiv and user.rolle in ('betriebsadmin', 'mitglied', 'gelegentlich', 'praktikand')
