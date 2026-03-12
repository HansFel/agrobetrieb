"""
Rollensystem für AgroBetrieb.

Rollen und deren Berechtigungen:
- betriebsadmin: Vollständiger Zugriff, verwaltet Benutzer und Betrieb
- buchhaltung: Nur Buchhaltung (Journal, Kontenplan, Bank-Import, Rechnungen)
- mitglied: Vollständiger Zugriff (Default-Member)
- gelegentlich: Nur Arbeitsdaten (Einsätze, Maschinen-Belegung)
- praktikand: Lesezugriff + Arbeitsdaten eingeben
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
    
    return aktion in modul_perms


def hat_modul_zugriff(user, modul):
    """Prüft ob Benutzer irgendwelche Berechtigungen im Modul hat."""
    if not user or not user.aktiv:
        return False
    rolle_perms = BERECHTIGUNGEN.get(user.rolle, {})
    modul_perms = rolle_perms.get(modul, [])
    return len(modul_perms) > 0


def ist_betriebsadmin(user):
    """Ist Betriebsadmin?"""
    return user and user.aktiv and user.rolle == 'betriebsadmin'


def ist_buchhaltung(user):
    """Ist Buchhaltung?"""
    return user and user.aktiv and user.rolle == 'buchhaltung'


def kann_arbeitsdaten_eingeben(user):
    """Kann Arbeitsdaten eingeben (gelegentlich+)?"""
    return user and user.aktiv and user.rolle in ('betriebsadmin', 'mitglied', 'gelegentlich', 'praktikand')
