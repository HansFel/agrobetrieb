/**
 * agrobetrieb_voice.js – Spracheingabe für AgroBetrieb
 *
 * Nutzt Web Speech API (SpeechRecognition) – kostenlos, lokal, kein API-Key.
 * Unterstützte Browser: Chrome, Edge (Chromium), Safari 14.1+
 *
 * Features:
 *  1. Globale Mikrofon-Taste in der Navbar (Hotkey: Alt+M)
 *  2. Sprachbefehle für Navigation ("gehe zu Milchvieh", "öffne Dashboard")
 *  3. Formular-Diktiermodus: fokussiertes Feld per Sprache ausfüllen
 *  4. Intelligente Feldausfüllung: ganze Formulare per Satz ausfüllen
 *     z.B. "Datum heute, Menge 28,5 Kilo, Fett 4,1 Prozent"
 *  5. Zahlen-Normalisierung: "acht Komma drei" → "8.3", "zwanzig" → "20"
 *  6. Österreichische Datumsformeln: "heute", "gestern", "vorgestern"
 *  7. Browser-KI (Gemini Nano) für Freitext-Formulierung wenn verfügbar
 */
'use strict';

// ─── Spracherkennungs-Wrapper ─────────────────────────────────────────────────

const Voice = {
    _rec: null,
    _aktiv: false,
    _modus: 'diktat',   // 'diktat' | 'befehl' | 'formular'
    _zielfeld: null,    // HTMLElement – aktuell fokussiertes Eingabefeld
    _callbacks: {},     // Listener: { transcript, start, stop, error }
    _letzteErgebnisse: [],

    /** Prüft ob Web Speech API verfügbar ist. */
    isSupported() {
        return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
    },

    /** Initialisiert SpeechRecognition. */
    _init() {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        this._rec = new SR();
        this._rec.lang = 'de-AT';   // Österreichisches Deutsch
        this._rec.continuous = true;
        this._rec.interimResults = true;
        this._rec.maxAlternatives = 3;

        this._rec.onresult = (event) => {
            let interim = '';
            let final = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const text = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    final += text;
                } else {
                    interim += text;
                }
            }
            if (interim) this._emit('interim', interim);
            if (final)   this._verarbeite(final.trim());
        };

        this._rec.onerror = (e) => {
            if (e.error === 'not-allowed') {
                this._emit('error', 'Mikrofonzugriff verweigert. Bitte in den Browser-Einstellungen erlauben.');
            } else if (e.error === 'no-speech') {
                // Kein Fehler – einfach nichts gesprochen
            } else {
                this._emit('error', `Sprachfehler: ${e.error}`);
            }
        };

        this._rec.onend = () => {
            if (this._aktiv) {
                // Automatisch neu starten (continuous bleibt aktiv)
                try { this._rec.start(); } catch {}
            } else {
                this._emit('stop');
            }
        };
    },

    /** Startet die Spracherkennung. */
    start(modus = 'formular') {
        if (!this.isSupported()) {
            this._emit('error', 'Spracheingabe wird von diesem Browser nicht unterstützt. Bitte Chrome oder Edge verwenden.');
            return false;
        }
        if (this._aktiv) return true;
        if (!this._rec) this._init();
        this._modus = modus;
        this._aktiv = true;
        try {
            this._rec.start();
            this._emit('start');
            return true;
        } catch (e) {
            this._aktiv = false;
            this._emit('error', 'Mikrofon konnte nicht gestartet werden.');
            return false;
        }
    },

    /** Stoppt die Spracherkennung. */
    stop() {
        this._aktiv = false;
        try { this._rec?.stop(); } catch {}
        this._emit('stop');
    },

    toggle(modus) {
        if (this._aktiv) this.stop();
        else this.start(modus);
    },

    /** Event-Listener registrieren. */
    on(event, fn) { this._callbacks[event] = fn; return this; },
    _emit(event, data) { this._callbacks[event]?.(data); },

    /** Verarbeitet finalen Sprachtext. */
    _verarbeite(text) {
        this._letzteErgebnisse.push(text);
        this._emit('transcript', text);

        // Stop-Befehle
        if (/^(stop|stopp|beenden|fertig|abbrechen)$/i.test(text.trim())) {
            this.stop();
            return;
        }

        switch (this._modus) {
            case 'befehl':   VoiceBefehl.verarbeite(text); break;
            case 'diktat':   VoiceDiktat.schreibeInFeld(this._zielfeld, text); break;
            case 'formular': VoiceFormular.verarbeite(text); break;
        }
    },

    /** Setzt das Zielfeld für Diktat (fokussiertes Element). */
    setZielfeld(el) { this._zielfeld = el; },
};


// ─── Zahlen & Datum Normalisierung ───────────────────────────────────────────

const VoiceNorm = {
    /**
     * Wandelt gesprochene Zahlen in numerische Strings um.
     * "acht Komma drei" → "8.3"
     * "zwanzig" → "20"
     * "drei Punkt fünf" → "3.5"
     */
    zahl(text) {
        const worteMap = {
            'null': 0, 'ein': 1, 'eine': 1, 'einen': 1, 'eins': 1,
            'zwei': 2, 'zwo': 2, 'drei': 3, 'vier': 4, 'fünf': 5,
            'sechs': 6, 'sieben': 7, 'acht': 8, 'neun': 9, 'zehn': 10,
            'elf': 11, 'zwölf': 12, 'dreizehn': 13, 'vierzehn': 14,
            'fünfzehn': 15, 'sechzehn': 16, 'siebzehn': 17, 'achtzehn': 18,
            'neunzehn': 19, 'zwanzig': 20, 'dreißig': 30, 'vierzig': 40,
            'fünfzig': 50, 'sechzig': 60, 'siebzig': 70, 'achtzig': 80,
            'neunzig': 90, 'hundert': 100, 'tausend': 1000,
        };

        // Bereits numerisch mit Komma/Punkt?
        const numMatch = text.trim().replace(',', '.').match(/^[\d.]+$/);
        if (numMatch) return numMatch[0];

        // "X Komma Y" / "X Punkt Y"
        const kommaMatch = text.match(/^(.+?)\s+(?:komma|punkt|Komma|Punkt)\s+(.+)$/i);
        if (kommaMatch) {
            const vorKomma = this.zahl(kommaMatch[1]);
            const nachKomma = this.zahl(kommaMatch[2]);
            if (vorKomma && nachKomma) return `${vorKomma}.${nachKomma}`;
        }

        const lower = text.toLowerCase().trim();
        if (worteMap[lower] !== undefined) return String(worteMap[lower]);

        // "dreiundzwanzig" etc. – einfache Zusammensetzung
        for (const [wort, wert] of Object.entries(worteMap)) {
            if (lower.endsWith('und' + wort)) {
                const vorTeil = lower.slice(0, lower.length - ('und' + wort).length);
                const vorWert = this.zahl(vorTeil);
                if (vorWert) return String(Number(vorWert) + wert);
            }
        }

        // Bereits in Ziffern? Komma → Punkt
        const cleaned = text.trim().replace(',', '.');
        if (!isNaN(parseFloat(cleaned))) return cleaned;

        return null;
    },

    /**
     * Österreichische Datumsformeln → ISO-Datum.
     * "heute" → "2026-03-15", "gestern" → "2026-03-14"
     */
    datum(text) {
        const t = text.toLowerCase().trim();
        const h = new Date();
        const fmt = (d) => d.toISOString().split('T')[0];

        if (/^heute$/i.test(t)) return fmt(h);
        if (/^gestern$/i.test(t)) { h.setDate(h.getDate() - 1); return fmt(h); }
        if (/^vorgestern$/i.test(t)) { h.setDate(h.getDate() - 2); return fmt(h); }

        // "12. März" / "12 März" / "12.03." / "12.03.2026"
        const monatNamen = { jan: 1, feb: 2, 'mär': 3, mar: 3, apr: 4, mai: 5, jun: 6,
            jul: 7, aug: 8, sep: 9, okt: 10, nov: 11, dez: 12 };

        const punktMatch = t.match(/^(\d{1,2})\.?\s*(\d{1,2})\.?\s*(\d{2,4})?$/);
        if (punktMatch) {
            const tag = punktMatch[1].padStart(2, '0');
            const monat = punktMatch[2].padStart(2, '0');
            const jahr = punktMatch[3] ? (punktMatch[3].length === 2 ? '20' + punktMatch[3] : punktMatch[3]) : new Date().getFullYear();
            return `${jahr}-${monat}-${tag}`;
        }

        const wortMatch = t.match(/^(\d{1,2})\.\s*(\w+)\s*(\d{4})?$/);
        if (wortMatch) {
            const tag = wortMatch[1].padStart(2, '0');
            const monatStr = wortMatch[2].toLowerCase().slice(0, 3);
            const monat = monatNamen[monatStr];
            if (monat) {
                const jahr = wortMatch[3] || new Date().getFullYear();
                return `${jahr}-${String(monat).padStart(2, '0')}-${tag}`;
            }
        }

        return null;
    },

    /** Bereinigt Einheiten-Schlüsselwörter aus Zahlentext. */
    zahlOhneEinheit(text) {
        const bereinigt = text
            .replace(/\s*(kilo(gramm)?|kg|liter|prozent|%|euro|€|cent|stück|stk|tage?|jahre?|monate?)\s*/gi, '')
            .trim();
        return this.zahl(bereinigt) || bereinigt;
    },
};


// ─── Diktat-Modus: Text in fokussiertes Feld schreiben ───────────────────────

const VoiceDiktat = {
    schreibeInFeld(el, text) {
        if (!el) return;
        const tag = el.tagName?.toLowerCase();
        if (tag === 'input' || tag === 'textarea') {
            const typ = el.type?.toLowerCase() || 'text';
            if (typ === 'date') {
                const datum = VoiceNorm.datum(text);
                if (datum) { el.value = datum; el.dispatchEvent(new Event('change', { bubbles: true })); }
            } else if (typ === 'number') {
                const zahl = VoiceNorm.zahlOhneEinheit(text);
                if (zahl) { el.value = zahl; el.dispatchEvent(new Event('input', { bubbles: true })); }
            } else {
                // Text: anhängen oder ersetzen
                el.value = text;
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }
        } else if (tag === 'select') {
            // Option suchen die dem Text ähnelt
            const lower = text.toLowerCase();
            for (const opt of el.options) {
                if (opt.text.toLowerCase().includes(lower) || lower.includes(opt.text.toLowerCase().slice(0, 4))) {
                    el.value = opt.value;
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    break;
                }
            }
        }
    },
};


// ─── Befehlsmodus: Navigation & Aktionen ─────────────────────────────────────

const VoiceBefehl = {
    _routen: [
        { muster: /milchvieh|kuh|rind|milch/i,    url: '/milchvieh/' },
        { muster: /dashboard|übersicht|start/i,    url: '/dashboard' },
        { muster: /legehennen|henne|ei/i,          url: '/legehennen/' },
        { muster: /buchhaltung|buchung|konto/i,    url: '/buchhaltung/journal' },
        { muster: /lager|artikel|bestand/i,        url: '/lager/' },
        { muster: /maschinen?|traktor|gerät/i,     url: '/maschinen/' },
        { muster: /faktur|rechnung|kunde/i,        url: '/fakturierung/' },
        { muster: /bank.?import|import/i,          url: '/buchhaltung/bank-import' },
        { muster: /neue\s+buchung/i,               url: '/buchhaltung/buchung/neu' },
        { muster: /neue\s+rechnung/i,              url: '/fakturierung/neu' },
        { muster: /weidebuch|weide/i,              url: '/milchvieh/weidebuch' },
        { muster: /tankmilch|tank/i,               url: '/milchvieh/tankmilch' },
        { muster: /tamg|behandlung|arzneimittel/i, url: null }, // kontext-abhängig
    ],

    verarbeite(text) {
        // Navigation
        const t = text.toLowerCase();
        if (/geh|öffne|zeige|navigiere|gehe/i.test(t)) {
            for (const r of this._routen) {
                if (r.muster.test(t) && r.url) {
                    VoiceUI.zeigeFeedback(`Navigiere zu ${r.url}…`, 'info');
                    setTimeout(() => { window.location.href = r.url; }, 800);
                    return;
                }
            }
        }

        // Zurück
        if (/zurück|back/i.test(t)) { history.back(); return; }

        // Speichern / Absenden
        if (/speicher|senden|bestätigen|absenden/i.test(t)) {
            const form = document.querySelector('form');
            if (form) {
                VoiceUI.zeigeFeedback('Formular wird gespeichert…', 'success');
                setTimeout(() => form.requestSubmit(), 600);
            }
            return;
        }

        // Neu anlegen Buttons
        if (/neu(es|er|en)?|anlegen|hinzufügen|erstell/i.test(t)) {
            const btn = document.querySelector('a[href*="/neu"], button[data-bs-toggle="modal"]');
            if (btn) { btn.click(); return; }
        }

        VoiceUI.zeigeFeedback(`Unbekannter Befehl: "${text}"`, 'warning');
    },
};


// ─── Formular-Modus: ganzen Satz → Felder füllen ─────────────────────────────

const VoiceFormular = {
    /**
     * Erkennt welche Formularsektions auf der aktuellen Seite sind
     * und füllt die passenden Felder aus.
     *
     * Beispielsätze:
     *  MLP:       "Datum heute, Milch dreißig Kilo, Fett vier Komma zwei, Zellzahl hundert"
     *  Besamung:  "Datum gestern, Stier Amadeus, Rasse Fleckvieh"
     *  Buchung:   "Datum heute, Betrag fünfhundert, Text Dieseleinkauf"
     *  Tankmilch: "Monat drei, Jahr 2026, Menge 12000, Fett vier Komma eins"
     *  Lager:     "Bezeichnung Dieselkraftstoff, Menge hundert, Mindestbestand fünfzig"
     */

    // Feld-Muster: [RegExp für Schlüsselwörter, Feld-ID oder Selektor, Typ]
    _feldMuster: [
        // Datum / Zeit
        { re: /datum|am|vom?|date/i,            id: 'datum',                  typ: 'datum' },
        { re: /beginn|start/i,                   id: 'beginn',                 typ: 'datum' },
        { re: /ende/i,                           id: 'ende',                   typ: 'datum' },
        { re: /belegdatum/i,                     id: 'beleg_datum',            typ: 'datum' },

        // Zahlen / Mengen
        { re: /milch\w*\s*menge|tages\w*gemelk|gesamt\w*menge/i, id: 'milchmenge_kg',    typ: 'zahl' },
        { re: /morgen\w*gemelk|morgen/i,          id: 'probenahme_morgen_kg',  typ: 'zahl' },
        { re: /abend\w*gemelk|abend/i,            id: 'probenahme_abend_kg',   typ: 'zahl' },
        { re: /fett/i,                            id: 'fett_prozent',          typ: 'zahl' },
        { re: /eiwei[sß]/i,                       id: 'eiweiss_prozent',       typ: 'zahl' },
        { re: /laktose/i,                         id: 'laktose_prozent',       typ: 'zahl' },
        { re: /harnstoff/i,                       id: 'harnstoff_mg_dl',       typ: 'zahl' },
        { re: /zellzahl|zell/i,                   id: 'zellzahl_tsd',          typ: 'zahl' },
        { re: /betrag|summe|preis/i,              id: 'betrag',                typ: 'zahl' },
        { re: /menge|kilogramm|kilogram|kilo/i,   id: 'milchmenge_kg,mengekg,menge', typ: 'zahl' },
        { re: /mindest\w*bestand|mindest/i,       id: 'mindestbestand',        typ: 'zahl' },
        { re: /anfangs\w*bestand/i,               id: 'anfangsbestand',        typ: 'zahl' },
        { re: /eier\s*gesamt|eier/i,              id: 'eier_gesamt',           typ: 'zahl' },
        { re: /verluste?/i,                       id: 'verluste',              typ: 'zahl' },
        { re: /futterverbrauch|futter/i,          id: 'futterverbrauch_kg',    typ: 'zahl' },
        { re: /anschaffungs\w*wert/i,             id: 'anschaffungswert',      typ: 'zahl' },
        { re: /baujahr/i,                         id: 'baujahr',               typ: 'zahl' },
        { re: /wartezeit\s*milch/i,               id: 'wartezeit_milch_tage',  typ: 'zahl' },
        { re: /wartezeit\s*fleisch/i,             id: 'wartezeit_fleisch_tage',typ: 'zahl' },
        { re: /dauer/i,                           id: 'behandlungsdauer_tage', typ: 'zahl' },
        { re: /monat/i,                           id: 'monat',                 typ: 'zahl' },
        { re: /jahr/i,                            id: 'jahr,geschaeftsjahr',   typ: 'zahl' },
        { re: /keimzahl|keim/i,                   id: 'gesamtkeimzahl',        typ: 'zahl' },
        { re: /tank\w*zellzahl/i,                 id: 'zellzahl_tank',         typ: 'zahl' },
        { re: /auszahlungs\w*preis|milchpreis/i,  id: 'auszahlungspreis_ct_kg',typ: 'zahl' },

        // Text-Felder
        { re: /name|tier|kuh/i,                  id: 'name',                  typ: 'text' },
        { re: /ohrmarke/i,                        id: 'ohrmarke',              typ: 'text' },
        { re: /stier|bulle/i,                     id: 'stier_name',            typ: 'text' },
        { re: /buchungs\w*text|text/i,            id: 'buchungstext',          typ: 'text' },
        { re: /betreff/i,                         id: 'betreff',               typ: 'text' },
        { re: /bezeichnung/i,                     id: 'bezeichnung',           typ: 'text' },
        { re: /arzneimittel|medikament/i,         id: 'arzneimittel_name',     typ: 'text' },
        { re: /wirkstoff/i,                       id: 'wirkstoff',             typ: 'text' },
        { re: /diagnose/i,                        id: 'diagnose',              typ: 'text' },
        { re: /charge/i,                          id: 'charge',                typ: 'text' },
        { re: /tierarzt/i,                        id: 'tierarzt_name',         typ: 'text' },
        { re: /molkerei/i,                        id: 'molkerei',              typ: 'text' },
        { re: /bemerkung|notiz|anmerkung/i,       id: 'bemerkung',             typ: 'text' },
        { re: /techniker|besamungs\w*techniker/i, id: 'besamungstechniker',    typ: 'text' },
        { re: /lieferant/i,                       id: 'lieferant',             typ: 'text' },
    ],

    /**
     * Parst einen Sprachsatz und füllt passende Felder.
     * Format: "schlüsselwort WERT, schlüsselwort WERT, ..."
     */
    verarbeite(text) {
        // Text in Segmente aufteilen: Komma, "und", "sowie"
        const segmente = text.split(/,|;\s*|\s+und\s+|\s+sowie\s+/i);
        let gefuellt = 0;

        for (const seg of segmente) {
            const s = seg.trim();
            if (!s) continue;

            for (const muster of this._feldMuster) {
                if (!muster.re.test(s)) continue;

                // Wert ist der Rest nach dem Schlüsselwort
                const wert = s.replace(muster.re, '').trim();
                if (!wert) continue;

                // IDs als komma-sep. Liste behandeln
                const ids = muster.id.split(',');
                for (const id of ids) {
                    const el = document.getElementById(id.trim());
                    if (!el) continue;

                    if (muster.typ === 'datum') {
                        const d = VoiceNorm.datum(wert);
                        if (d) {
                            el.value = d;
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                            gefuellt++;
                        }
                    } else if (muster.typ === 'zahl') {
                        const z = VoiceNorm.zahlOhneEinheit(wert);
                        if (z) {
                            el.value = z;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            gefuellt++;
                        }
                    } else {
                        el.value = wert;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        gefuellt++;
                    }
                    break; // erste gefundene ID reicht
                }
                break; // nächstes Segment
            }
        }

        // Fallback: Browser-KI für Freitext-Formulierungen
        if (gefuellt === 0) {
            this._kiFormular(text);
        } else {
            VoiceUI.zeigeFeedback(`✅ ${gefuellt} Feld${gefuellt > 1 ? 'er' : ''} ausgefüllt`, 'success');
        }
    },

    /** KI-Fallback: Freitext → Feldwerte via Gemini Nano */
    async _kiFormular(text) {
        if (!window.AgroKI) return;
        const supported = await AgroKI.ai.isSupported();
        if (!supported) {
            VoiceUI.zeigeFeedback(`Nicht erkannt: "${text}" – Bitte konkret sprechen (z.B. "Fett vier Komma zwei")`, 'warning');
            return;
        }

        // Verfügbare Felder auf der Seite erfassen
        const felder = Array.from(document.querySelectorAll('input[id], textarea[id], select[id]'))
            .filter(el => el.id && !el.type?.includes('hidden') && !el.name?.includes('csrf'))
            .map(el => `${el.id}(${el.type || el.tagName})`)
            .slice(0, 20)
            .join(', ');

        const prompt = `Gesprochener Satz: "${text}"
Verfügbare Formularfelder auf der Seite: ${felder}
Extrahiere Feldname-Wert-Paare als JSON: {"feldname": "wert", ...}
Nur Felder die im Satz erwähnt wurden. Zahlen als Dezimalzahl (Punkt statt Komma). Datum als YYYY-MM-DD.`;

        VoiceUI.zeigeFeedback('KI analysiert Spracheingabe…', 'light');
        const antwort = await AgroKI.ai.prompt(prompt,
            'Du extrahierst Formularwerte aus gesprochenen Sätzen für österreichische Landwirte. Antworte NUR mit gültigem JSON.');

        try {
            const json = JSON.parse(antwort?.match(/\{[^}]+\}/)?.[0] || '{}');
            let gefuellt = 0;
            for (const [id, wert] of Object.entries(json)) {
                const el = document.getElementById(id);
                if (el && wert) {
                    el.value = wert;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    gefuellt++;
                }
            }
            if (gefuellt > 0) {
                VoiceUI.zeigeFeedback(`✅ KI hat ${gefuellt} Feld${gefuellt > 1 ? 'er' : ''} ausgefüllt`, 'success');
            } else {
                VoiceUI.zeigeFeedback(`Nicht erkannt: "${text}"`, 'warning');
            }
        } catch {
            VoiceUI.zeigeFeedback(`Nicht erkannt: "${text}" – Bitte konkreter sprechen`, 'warning');
        }
    },
};


// ─── Voice UI: Mikrofon-Button, Feedback, Zwischentext ───────────────────────

const VoiceUI = {
    _btn: null,
    _feedback: null,
    _interimEl: null,
    _feedbackTimer: null,

    /**
     * Initialisiert UI: Mikrofon-Button in Navbar + globaler Feedback-Toast.
     */
    init() {
        if (!Voice.isSupported()) return;

        // Mikrofon-Button in Navbar einfügen
        const navRight = document.querySelector('.navbar-nav.ms-auto');
        if (navRight) {
            const li = document.createElement('li');
            li.className = 'nav-item d-flex align-items-center px-1';
            li.innerHTML = `
                <button id="voice-btn" class="btn btn-sm btn-outline-light border-0 position-relative"
                        title="Spracheingabe (Alt+M)" style="min-width:36px">
                    <i class="bi bi-mic" id="voice-icon"></i>
                    <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger d-none"
                          id="voice-badge" style="font-size:0.55em">●</span>
                </button>`;
            navRight.insertBefore(li, navRight.firstChild);
            this._btn = document.getElementById('voice-btn');
            this._btn.addEventListener('click', () => this._toggle());
        }

        // Feedback-Toast am unteren Rand
        const toast = document.createElement('div');
        toast.id = 'voice-toast';
        toast.style.cssText = `
            position: fixed; bottom: 1rem; left: 50%; transform: translateX(-50%);
            z-index: 9999; min-width: 320px; max-width: 600px;
            display: none; pointer-events: none;`;
        toast.innerHTML = `
            <div class="card shadow-lg border-0">
                <div class="card-body py-2 px-3">
                    <div class="d-flex align-items-center gap-2">
                        <span id="voice-status-icon" class="fs-5">🎤</span>
                        <div class="flex-grow-1">
                            <div id="voice-interim" class="text-muted small fst-italic" style="min-height:1.2em"></div>
                            <div id="voice-feedback" class="small fw-bold"></div>
                        </div>
                        <button class="btn btn-sm btn-outline-secondary py-0 px-1" id="voice-stop-btn"
                                style="pointer-events:auto" title="Sprache beenden">
                            <i class="bi bi-x-lg"></i>
                        </button>
                    </div>
                    <div class="mt-1 text-muted" style="font-size:0.72em">
                        <strong>Befehle:</strong> "stop" | "speichern" |
                        "Datum heute, Fett vier Komma zwei, Milch dreißig Kilo" |
                        "gehe zu Milchvieh"
                    </div>
                </div>
            </div>`;
        document.body.appendChild(toast);
        this._feedback  = document.getElementById('voice-feedback');
        this._interimEl = document.getElementById('voice-interim');
        document.getElementById('voice-stop-btn').addEventListener('click', () => Voice.stop());

        // Voice-Events
        Voice
            .on('start', () => this._onStart())
            .on('stop',  () => this._onStop())
            .on('interim', t => this._onInterim(t))
            .on('transcript', t => this._onTranscript(t))
            .on('error', msg => this.zeigeFeedback(msg, 'danger'));

        // Fokus-Tracking für Diktat-Modus
        document.addEventListener('focusin', (e) => {
            const el = e.target;
            if (['input', 'textarea', 'select'].includes(el.tagName?.toLowerCase())) {
                Voice.setZielfeld(el);
            }
        });

        // Hotkey Alt+M
        document.addEventListener('keydown', (e) => {
            if (e.altKey && e.key === 'm') {
                e.preventDefault();
                this._toggle();
            }
        });

        // Modus-Auswahl: Wenn Formular auf Seite → Formular-Modus, sonst Befehl
        this._modus = document.querySelector('form') ? 'formular' : 'befehl';
    },

    _modus: 'formular',

    _toggle() {
        Voice.toggle(this._modus);
    },

    _onStart() {
        if (this._btn) {
            this._btn.classList.replace('btn-outline-light', 'btn-danger');
            document.getElementById('voice-icon').className = 'bi bi-mic-fill';
            document.getElementById('voice-badge').classList.remove('d-none');
        }
        document.getElementById('voice-toast').style.display = '';
        document.getElementById('voice-status-icon').textContent = '🎤';
        this.zeigeFeedback('Sprechen Sie jetzt…', 'info');
    },

    _onStop() {
        if (this._btn) {
            this._btn.classList.replace('btn-danger', 'btn-outline-light');
            document.getElementById('voice-icon').className = 'bi bi-mic';
            document.getElementById('voice-badge').classList.add('d-none');
        }
        document.getElementById('voice-status-icon').textContent = '🔇';
        this.zeigeFeedback('Spracheingabe beendet.', 'secondary');
        setTimeout(() => { document.getElementById('voice-toast').style.display = 'none'; }, 2000);
    },

    _onInterim(text) {
        if (this._interimEl) this._interimEl.textContent = text + '…';
    },

    _onTranscript(text) {
        if (this._interimEl) this._interimEl.textContent = '';
        this.zeigeFeedback(`"${text}"`, 'light', 3000);
    },

    zeigeFeedback(text, klasse = 'info', dauer = 4000) {
        if (!this._feedback) return;
        this._feedback.className = `small fw-bold text-${klasse === 'light' ? 'dark' : klasse}`;
        this._feedback.innerHTML = text;
        document.getElementById('voice-toast').style.display = '';
        clearTimeout(this._feedbackTimer);
        if (dauer > 0) {
            this._feedbackTimer = setTimeout(() => {
                if (!Voice._aktiv) document.getElementById('voice-toast').style.display = 'none';
            }, dauer);
        }
    },
};


// ─── Mikrofon-Buttons in einzelnen Formularfeldern ───────────────────────────

/**
 * Fügt jedem Formularfeld (input/textarea) ein kleines Mikrofon-Symbol hinzu.
 * Klick → startet Diktat direkt in dieses Feld.
 */
function initFeldMikrofone() {
    if (!Voice.isSupported()) return;

    const felder = document.querySelectorAll(
        'input[type="text"], input[type="number"], input[type="date"], textarea'
    );

    felder.forEach(el => {
        if (el.dataset.voiceInit) return;
        el.dataset.voiceInit = '1';

        // Wrapper mit relative positioning
        const parent = el.parentNode;
        if (!parent || parent.style.position === 'absolute') return;

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.title = 'Diktat für dieses Feld (Alt+M)';
        btn.style.cssText = `
            position: absolute; right: 4px; top: 50%; transform: translateY(-50%);
            background: none; border: none; color: #6c757d; cursor: pointer;
            padding: 0 2px; font-size: 0.85em; opacity: 0; transition: opacity 0.15s;
            z-index: 10;`;
        btn.innerHTML = '<i class="bi bi-mic"></i>';

        // Nur bei Hover/Fokus sichtbar
        el.addEventListener('focusin',  () => { btn.style.opacity = '0.8'; });
        el.addEventListener('focusout', () => { setTimeout(() => btn.style.opacity = '0', 200); });
        el.addEventListener('mouseenter', () => btn.style.opacity = '0.8');
        el.addEventListener('mouseleave', () => {
            if (document.activeElement !== el) btn.style.opacity = '0';
        });

        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            el.focus();
            Voice.setZielfeld(el);
            Voice.start('diktat');
            VoiceUI.zeigeFeedback(`Diktat für Feld "${el.labels?.[0]?.textContent?.trim() || el.id}"`, 'info');
        });

        // Parent braucht relative positioning für absolute button
        const cs = window.getComputedStyle(parent);
        if (cs.position === 'static') parent.style.position = 'relative';
        parent.appendChild(btn);
    });
}


// ─── Initialisierung ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    VoiceUI.init();
    // Kurze Verzögerung damit Formulare vollständig geladen sind
    setTimeout(initFeldMikrofone, 300);
});

// Public API
window.AgroVoice = { Voice, VoiceNorm, VoiceDiktat, VoiceBefehl, VoiceFormular, VoiceUI, initFeldMikrofone };
