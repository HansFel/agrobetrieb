# Rollensystem in AgroBetrieb

## Übersicht der Rollen

| Rolle | Beschreibung | Priorität |
|-------|-------------|-----------|
| **betriebsadmin** | Administrator mit vollständigem Zugriff einschließlich Benutzerverwaltung | 1000 |
| **mitglied** | Genosse mit vollem Zugriff (außer Benutzerverwaltung) | 500 |
| **buchhaltung** | Nur Zugriff auf Buchhaltungs-Module (Journal, Konten, Bank-Import, Rechnungen) | 300 |
| **gelegentlich** | Gelegentlicher Mitarbeiter - nur Arbeitsdaten eingeben | 100 |
| **praktikand** | Praktikand - Lesezugriff + Arbeitsdaten eingeben | 50 |

## Modul-Zugriffe pro Rolle

### Betriebsadmin
- ✅ Dashboard (view)
- ✅ Betrieb (view, edit)
- ✅ Benutzer (view, create, edit, delete)
- ✅ Maschinen (view, create, edit, delete)
- ✅ Einsätze (view, create, edit, delete)
- ✅ Buchhaltung (view, create, edit, delete)
- ✅ Fakturierung (view, create, edit, delete)
- ✅ Lager (view, create, edit, delete)

### Mitglied
- ✅ Dashboard (view)
- ✅ Betrieb (view)
- ❌ Benutzer
- ✅ Maschinen (view, create, edit)
- ✅ Einsätze (view, create, edit, delete)
- ✅ Buchhaltung (view, create, edit, delete)
- ✅ Fakturierung (view, create, edit, delete)
- ✅ Lager (view, create, edit, delete)

### Buchhaltung
- ✅ Dashboard (view)
- ✅ Betrieb (view)
- ❌ Benutzer
- ✅ Maschinen (view)
- ❌ Einsätze
- ✅ Buchhaltung (view, create, edit, delete)
- ✅ Fakturierung (view, create, edit, delete)
- ❌ Lager

### Gelegentlicher Mitarbeiter
- ✅ Dashboard (view)
- ❌ Betrieb
- ❌ Benutzer
- ✅ Maschinen (view)
- ✅ Einsätze (view, create, edit)
- ❌ Buchhaltung
- ❌ Fakturierung
- ❌ Lager

### Praktikand
- ✅ Dashboard (view)
- ❌ Betrieb
- ❌ Benutzer
- ✅ Maschinen (view)
- ✅ Einsätze (view, create)
- ✅ Buchhaltung (view)
- ✅ Fakturierung (view)
- ✅ Lager (view)

## Verwendung in Code

### In Routes mit Decorator

```python
from app.auth_decorators import requires_permission, requires_role, requires_admin

# Modul + Aktion prüfen
@app.route('/buchhaltung/journal')
@requires_permission('buchhaltung', 'view')
def journal():
    ...

# Eine bestimmte Rolle prüfen
@app.route('/benutzer')
@requires_role('betriebsadmin')
def benutzer_verwaltung():
    ...

# Nur Admin
@app.route('/admin')
@requires_admin()
def admin_panel():
    ...
```

### Im Code

```python
from app.models.rollen import hat_berechtigung, hat_modul_zugriff, ist_betriebsadmin

# Berechtigung prüfen
if hat_berechtigung(current_user, 'buchhaltung', 'create'):
    # Benutzer darf Buchung erstellen
    ...

# Modul-Zugriff prüfen
if hat_modul_zugriff(current_user, 'buchhaltung'):
    # Benutzer hat Zugriff auf Buchhaltung
    ...

# Rol-Check
if ist_betriebsadmin(current_user):
    # Nur Admin
    ...
```

### In Templates

```jinja2
{% if current_user.rolle == 'betriebsadmin' %}
    <a href="/benutzer">Benutzer verwalten</a>
{% endif %}

{% if hat_berechtigung(current_user, 'buchhaltung', 'create') %}
    <button>Neue Buchung</button>
{% endif %}
```

## Standard-Admin beim ersten Start

Beim ersten Start (leere Datenbank) wird automatisch ein Admin-Benutzer angelegt:
- Username: `admin`
- Passwort: `admin`
- Rolle: `betriebsadmin`

**⚠️ Passwort nach dem Login ändern!**
