"""Seed initial data for AgroBetrieb"""
import sys
from app import create_app, db
from app.models.buchhaltung import Konto, Kategorie
from app.models.user import User

app = create_app()

with app.app_context():
    # Starter-Konten für Buchhaltung
    konten_data = [
        # Aktiva
        ("1000", "Kasse", "aktiva"),
        ("1010", "Bankkonto", "aktiva"),
        ("1020", "Kunde Müller", "aktiva"),
        ("12 00", "Maschinen", "aktiva"),
        # Passiva
        ("2000", "Verbindlichkeiten", "passiva"),
        ("2010", "Bank-Darlehen", "passiva"),
        # Ertrag
        ("7000", "Eigenleistungen", "ertrag"),
        ("7010", "Pacht", "ertrag"),
        ("7020", "Verkauf Produkte", "ertrag"),
        ("7090", "Sonstige Einkünfte", "ertrag"),
        # Aufwand
        ("8000", "Futtermittel", "aufwand"),
        ("8010", "Dünger", "aufwand"),
        ("8020", "Pflanzenschutz", "aufwand"),
        ("8100", "Treibstoff", "aufwand"),
        ("8110", "Reparaturen", "aufwand"),
        ("8120", "Versicherungen", "aufwand"),
        ("8130", "Strom/Wasser", "aufwand"),
        ("8200", "Löhne", "aufwand"),
        ("8300", "Administration", "aufwand"),
    ]
    
    for nummer, bezeichnung, typ in konten_data:
        if not Konto.query.filter_by(nummer=nummer).first():
            konto = Konto(nummer=nummer, bezeichnung=bezeichnung, typ=typ)
            db.session.add(konto)
            print(f"✓ Konto erstellt: {nummer} - {bezeichnung}")

    # Starter-Kategorien
    kategorien_data = [
        ("Diesel", "#FF6B6B"),
        ("Reparaturen", "#4ECDC4"),
        ("Dünger", "#95E1D3"),
        ("Futtermittel", "#F38181"),
        ("Versicherung", "#AA96DA"),
        ("Löhne", "#FCBAD3"),
        ("Strom", "#FFFFD2"),
        ("Pacht", "#A8E6CF"),
        ("Verkauf", "#56AB91"),
        ("Sonstige", "#999"),
    ]
    
    for name, farbe in kategorien_data:
        if not Kategorie.query.filter_by(name=name).first():
            kategorie = Kategorie(name=name, farbe=farbe)
            db.session.add(kategorie)
            print(f"✓ Kategorie erstellt: {name}")

    db.session.commit()
    print("\n✅ Seed-Daten erfolgreich eingefügt!")
    sys.exit(0)
