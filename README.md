# AgroBetrieb – Einzelbetrieb-Verwaltungssoftware

Freie Open-Source Webanwendung für die Verwaltung landwirtschaftlicher Einzelbetriebe.

## Features

- **Maschinen & Einsätze** – Einsatzprotokoll mit Kosten, Zählerstände
- **Buchhaltung** – Einnahmen/Ausgaben, Konten, Jahresabschlüsse
- **Fakturierung** – Rechnungen, Kundenverwaltung, PDF-Export
- **Lager** – Vorräte, Lagerbewegungen, Warnungen
- **Schlagkartei** – Felder, Kulturen, Maßnahmen
- **Berichte** – PDF-Exporte, Auswertungen
- **PWA** – Offline-fähig, auf Handy installierbar

## Tech

- **Backend**: Flask 3.0, SQLAlchemy 2.x
- **Datenbank**: SQLite (lokal), PostgreSQL (Server)
- **Frontend**: Bootstrap 5.3, Jinja2
- **Deployment**: Docker + Caddy
- **Migrations**: Alembic

## Installation (lokal)

```bash
git clone https://github.com/HansFel/agrobetrieb.git
cd agrobetrieb

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
flask db upgrade
flask seed-db

python run.py
# → http://localhost:5000
# Login: admin / admin
```

## Lizenzierung

Die Grundmodule sind **kostenlos**. Zusätzliche Pro-Module erfordern eine Lizenz:
- Milchwirtschaft
- Forst
- Lohnabrechnung
- Tierhaltung

## Repository

- `agrobetrieb` – Hauptanwendung
- `agrobetrieb-pro` – Pro-Module

## Autor

Hans Felhofer, 2026
