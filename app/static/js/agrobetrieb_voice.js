/**
 * agrobetrieb_voice.js – Push-to-Talk Spracheingabe
 *
 * Bedienung:
 *  1. Mikrofon-Button (Navbar oder Panel) EIN drücken → Mikrofon aktiv (rot)
 *  2. Feldname sagen z.B. "Kontonummer" → Feld wird markiert
 *  3. Nochmal Mikrofon drücken (oder kurz warten) → Wert sagen z.B. "4001"
 *  4. Wert wird eingetragen
 *
 *  Alternativ in einem Satz: "Kontonummer 4001" → Feld + Wert sofort
 *
 *  Befehle: "speichern", "löschen", "weiter" (nächstes Feld), "zurück"
 */
'use strict';

// ─── Zahlen & Datum Normalisierung ───────────────────────────────────────────

const VoiceNorm = {
    WORTE: {
        'null':0,'ein':1,'eine':1,'einen':1,'eins':1,'zwei':2,'zwo':2,
        'drei':3,'vier':4,'fünf':5,'sechs':6,'sieben':7,'acht':8,'neun':9,
        'zehn':10,'elf':11,'zwölf':12,'dreizehn':13,'vierzehn':14,
        'fünfzehn':15,'sechzehn':16,'siebzehn':17,'achtzehn':18,'neunzehn':19,
        'zwanzig':20,'dreißig':30,'vierzig':40,'fünfzig':50,'sechzig':60,
        'siebzig':70,'achtzig':80,'neunzig':90,'hundert':100,'tausend':1000,
    },

    zahl(text) {
        if (!text) return null;
        const num = text.trim().replace(',', '.');
        if (!isNaN(parseFloat(num)) && /^-?[\d.]+$/.test(num)) return num;

        const km = text.match(/^(.+?)\s+(?:komma|punkt)\s+(.+)$/i);
        if (km) {
            const v = this.zahl(km[1]), n = this.zahl(km[2]);
            if (v !== null && n !== null) return `${v}.${n}`;
        }

        const lower = text.toLowerCase().trim()
            .replace(/\s*(euro|kilogramm|kilo|prozent|tage?|stunden?)\s*/g, '');

        if (this.WORTE[lower] !== undefined) return String(this.WORTE[lower]);

        for (const [w, v] of Object.entries(this.WORTE)) {
            if (lower.endsWith('und' + w)) {
                const vor = this.zahl(lower.slice(0, -('und'+w).length));
                if (vor !== null) return String(Number(vor) + v);
            }
        }
        if (lower.includes('hundert')) {
            const [v, n] = lower.split('hundert');
            const vorH = v ? (this.WORTE[v.trim()] ?? null) : 1;
            const nachH = n ? (this.zahl(n.trim()) ?? 0) : 0;
            if (vorH !== null) return String(vorH * 100 + Number(nachH));
        }
        return null;
    },

    datum(text) {
        if (!text) return null;
        const t = text.toLowerCase().trim();
        const h = new Date();
        const fmt = d => d.toISOString().split('T')[0];
        if (/^heute$/i.test(t))      return fmt(h);
        if (/^gestern$/i.test(t))    { h.setDate(h.getDate()-1); return fmt(h); }
        if (/^vorgestern$/i.test(t)) { h.setDate(h.getDate()-2); return fmt(h); }

        const MONATE = {jan:1,feb:2,'mär':3,mar:3,apr:4,mai:5,jun:6,
                        jul:7,aug:8,sep:9,okt:10,nov:11,dez:12};
        const pm = t.match(/^(\d{1,2})[.\s-]+(\d{1,2})[.\s-]*(\d{2,4})?$/);
        if (pm) {
            const tag = pm[1].padStart(2,'0'), monat = pm[2].padStart(2,'0');
            const jahr = pm[3] ? (pm[3].length===2?'20'+pm[3]:pm[3]) : h.getFullYear();
            return `${jahr}-${monat}-${tag}`;
        }
        const wm = t.match(/^(\d{1,2})\.\s*([a-zä]+)\s*(\d{4})?$/);
        if (wm) {
            const monat = MONATE[wm[2].slice(0,3)];
            if (monat) return `${wm[3]||h.getFullYear()}-${String(monat).padStart(2,'0')}-${wm[1].padStart(2,'0')}`;
        }
        return null;
    },

    fuerFeld(text, el) {
        if (!el) return text;
        const typ = el.type?.toLowerCase() || el.tagName?.toLowerCase();
        if (typ === 'date')   return this.datum(text) ?? text;
        if (typ === 'number') return this.zahl(text)  ?? text;
        return text;
    },
};


// ─── Feld-Suche: findet Formularfeld anhand gesprochenen Namens ──────────────

const FeldSuche = {
    // Alle Felder des Hauptformulars (mit den meisten sichtbaren Feldern)
    alleFelder() {
        const forms = Array.from(document.querySelectorAll('form'));
        const form = forms.reduce((best, f) => {
            const n = f.querySelectorAll('input:not([type=hidden]),select,textarea').length;
            const b = best ? best.querySelectorAll('input:not([type=hidden]),select,textarea').length : 0;
            return n > b ? f : best;
        }, null);
        if (!form) return [];
        return Array.from(form.querySelectorAll(
            'input:not([type=hidden]):not([type=submit]):not([type=button]):not([name=csrf_token]),' +
            'select, textarea'
        )).filter(el => !el.disabled);
    },

    // Label-Text für ein Element
    labelFor(el) {
        if (el.id) {
            const lbl = document.querySelector(`label[for="${el.id}"]`);
            if (lbl) return lbl.textContent.trim().replace(/\s*\*$/, '');
        }
        const parent = el.closest('.form-group, .mb-3, .col-md-4, .col-md-6, .col-md-8');
        if (parent) {
            const lbl = parent.querySelector('label');
            if (lbl) return lbl.textContent.trim().replace(/\s*\*$/, '');
        }
        return el.placeholder || el.name || el.id || '';
    },

    // Findet bestes Feld für gesprochenen Text
    suchen(text) {
        const felder = this.alleFelder();
        const t = text.toLowerCase().trim();

        // 1. Exakt per name oder id
        for (const el of felder) {
            if (el.name?.toLowerCase() === t || el.id?.toLowerCase() === t) return el;
        }
        // 2. Label enthält Text
        for (const el of felder) {
            const lbl = this.labelFor(el).toLowerCase();
            if (lbl.includes(t) || t.includes(lbl.slice(0,5))) return el;
        }
        // 3. Name enthält Text
        for (const el of felder) {
            const name = (el.name || '').toLowerCase().replace(/_/g,' ');
            if (name.includes(t) || t.includes(name.split(' ')[0])) return el;
        }
        // 4. Erste Wörter matchen
        const worte = t.split(/\s+/);
        for (const el of felder) {
            const lbl = this.labelFor(el).toLowerCase();
            if (worte.some(w => w.length > 3 && lbl.includes(w))) return el;
            const name = (el.name || '').toLowerCase();
            if (worte.some(w => w.length > 3 && name.includes(w))) return el;
        }
        return null;
    },
};


// ─── Wert eintragen ──────────────────────────────────────────────────────────

function wertEintragen(el, text) {
    const typ = el.type?.toLowerCase() || el.tagName?.toLowerCase();

    if (typ === 'date') {
        const d = VoiceNorm.datum(text);
        if (d) { el.value = d; el.dispatchEvent(new Event('change', {bubbles:true})); return true; }
    }
    if (typ === 'number') {
        const z = VoiceNorm.zahl(text);
        if (z !== null) { el.value = z; el.dispatchEvent(new Event('input', {bubbles:true})); return true; }
        // Fallback: direkt eintragen wenn es eine Zahl ist
        if (!isNaN(text.replace(',','.'))) {
            el.value = text.replace(',','.'); el.dispatchEvent(new Event('input', {bubbles:true})); return true;
        }
    }
    if (el.tagName?.toLowerCase() === 'select') {
        const lower = text.toLowerCase();
        const opts = Array.from(el.options).filter(o => o.value !== '');
        const treffer =
            opts.find(o => o.text.toLowerCase() === lower) ||
            opts.find(o => o.text.toLowerCase().includes(lower)) ||
            opts.find(o => lower.includes(o.text.toLowerCase())) ||
            opts.find(o => o.text.toLowerCase().slice(0,4) === lower.slice(0,4));
        if (treffer) { el.value = treffer.value; el.dispatchEvent(new Event('change', {bubbles:true})); return true; }
        return false;
    }
    if (typ === 'checkbox') {
        el.checked = /^(ja|an|ein|wahr|true|yes)$/i.test(text);
        el.dispatchEvent(new Event('change', {bubbles:true}));
        return true;
    }
    el.value = text;
    el.dispatchEvent(new Event('input', {bubbles:true}));
    return true;
}

function feldHervorheben(el, farbe = '#0d6efd') {
    document.querySelectorAll('.voice-aktiv').forEach(e => {
        e.classList.remove('voice-aktiv');
        e.style.outline = '';
        e.style.boxShadow = '';
    });
    if (!el) return;
    el.classList.add('voice-aktiv');
    el.style.outline = `3px solid ${farbe}`;
    el.style.boxShadow = `0 0 0 4px ${farbe}33`;
    el.scrollIntoView({behavior:'smooth', block:'center'});
    el.focus();
}


// ─── Haupt-Controller ────────────────────────────────────────────────────────

const Voice = {
    _aktiv: false,      // Mikrofon läuft
    _rec: null,
    _aktivFeld: null,   // zuletzt markiertes Feld
    _btn: null,         // Navbar-Button

    isSupported: () => !!(window.SpeechRecognition || window.webkitSpeechRecognition),

    // Mikrofon umschalten (EIN/AUS)
    toggle() {
        if (this._aktiv) {
            this._stoppen();
        } else {
            this._starten();
        }
    },

    _starten() {
        if (!this.isSupported()) {
            this._status('Spracheingabe wird von diesem Browser nicht unterstützt.', 'danger');
            return;
        }
        this._aktiv = true;
        this._btnAktiv(true);
        this._status('🎤 Mikrofon aktiv – Feldname oder "Feldname Wert" sprechen', 'info');
        this._aufnehmen();
    },

    _stoppen() {
        this._aktiv = false;
        try { this._rec?.stop(); } catch {}
        this._rec = null;
        this._btnAktiv(false);
        feldHervorheben(null);
        this._aktivFeld = null;
        this._panelVerstecken();
    },

    _aufnehmen() {
        if (!this._aktiv) return;

        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        const rec = new SR();
        rec.lang = 'de-AT';
        rec.continuous = false;
        rec.interimResults = true;
        rec.maxAlternatives = 1;
        this._rec = rec;

        rec.onresult = e => {
            let interim = '', final = '';
            for (let i = e.resultIndex; i < e.results.length; i++) {
                const t = e.results[i][0].transcript;
                e.results[i].isFinal ? (final += t) : (interim += t);
            }
            if (interim) this._statusInterim(interim);
            if (final)   this._verarbeite(final.trim());
        };

        rec.onerror = e => {
            if (e.error === 'not-allowed') {
                this._status('Mikrofonzugriff verweigert!', 'danger');
                this._stoppen();
            }
            // no-speech: einfach neu starten
        };

        rec.onend = () => {
            if (this._aktiv) {
                // Kurze Pause dann nochmal aufnehmen
                setTimeout(() => this._aufnehmen(), 150);
            }
        };

        try { rec.start(); }
        catch { setTimeout(() => this._aufnehmen(), 300); }
    },

    _verarbeite(text) {
        if (!text) return;
        const t = text.toLowerCase().trim();

        // Globale Befehle
        if (/^(stop|stopp|beenden|fertig)$/.test(t)) { this._stoppen(); return; }
        if (/^(speichern|absenden|bestätigen)$/.test(t)) {
            document.querySelector('form')?.requestSubmit();
            this._stoppen(); return;
        }
        if (/^(löschen|leeren)$/.test(t) && this._aktivFeld) {
            this._aktivFeld.value = '';
            this._aktivFeld.dispatchEvent(new Event('input', {bubbles:true}));
            this._status(`🗑️ "${FeldSuche.labelFor(this._aktivFeld)}" geleert`, 'warning', 2000);
            return;
        }
        if (/^(weiter|nächstes?)$/.test(t)) {
            this._naechstesFeld(); return;
        }
        if (/^(zurück|voriges?)$/.test(t)) {
            this._vorigesFeld(); return;
        }

        // Versuch 1: Ganzer Text = Wert für aktives Feld
        if (this._aktivFeld) {
            const ok = wertEintragen(this._aktivFeld, text);
            if (ok) {
                feldHervorheben(this._aktivFeld, '#198754');
                const lbl = FeldSuche.labelFor(this._aktivFeld);
                this._status(`✅ ${lbl}: "${this._aktivFeld.value}"`, 'success', 3000);
                // Nach Eintragen Feld-Markierung auf grün kurz, dann nächstes
                setTimeout(() => {
                    if (this._aktivFeld) feldHervorheben(this._aktivFeld, '#198754');
                }, 100);
                return;
            }
        }

        // Versuch 2: Erstes Wort/Phrase = Feldname, Rest = Wert
        // z.B. "Kontonummer 4001" oder "Bezeichnung Hauskonto"
        const felder = FeldSuche.alleFelder();
        for (let wortAnzahl = 3; wortAnzahl >= 1; wortAnzahl--) {
            const worte = text.split(/\s+/);
            if (worte.length <= wortAnzahl) continue;
            const feldName = worte.slice(0, wortAnzahl).join(' ');
            const wert = worte.slice(wortAnzahl).join(' ');
            const el = FeldSuche.suchen(feldName);
            if (el && wert) {
                this._aktivFeld = el;
                feldHervorheben(el, '#198754');
                wertEintragen(el, wert);
                this._status(`✅ ${FeldSuche.labelFor(el)}: "${el.value}"`, 'success', 3000);
                return;
            }
        }

        // Versuch 3: Ganzer Text = Feldname → Feld markieren, auf Wert warten
        const el = FeldSuche.suchen(text);
        if (el) {
            this._aktivFeld = el;
            feldHervorheben(el, '#0d6efd');
            const lbl = FeldSuche.labelFor(el);
            this._status(`➡️ "${lbl}" – jetzt Wert sprechen`, 'info');
            return;
        }

        // Nichts erkannt
        this._status(`⚠️ Nicht erkannt: "${text}"`, 'warning', 2500);
    },

    _naechstesFeld() {
        const felder = FeldSuche.alleFelder();
        const idx = this._aktivFeld ? felder.indexOf(this._aktivFeld) : -1;
        const next = felder[idx + 1];
        if (next) {
            this._aktivFeld = next;
            feldHervorheben(next);
            this._status(`➡️ "${FeldSuche.labelFor(next)}" – Wert sprechen`, 'info');
        }
    },

    _vorigesFeld() {
        const felder = FeldSuche.alleFelder();
        const idx = this._aktivFeld ? felder.indexOf(this._aktivFeld) : felder.length;
        const prev = felder[Math.max(0, idx - 1)];
        if (prev) {
            this._aktivFeld = prev;
            feldHervorheben(prev);
            this._status(`⬅️ "${FeldSuche.labelFor(prev)}" – Wert sprechen`, 'info');
        }
    },

    // ── UI ──────────────────────────────────────────────────────────────────

    _panel: null,
    _timer: null,

    init() {
        this._erstellePanel();
        this._erstelleNavbarBtn();
        this._erstelleFeldMikrofone();
        this._hotkeys();

        // CSS
        const s = document.createElement('style');
        s.textContent = `
        @keyframes voice-puls { 0%,100%{opacity:1} 50%{opacity:.4} }
        .voice-mic-aktiv { animation: voice-puls .7s ease-in-out infinite; color: #dc3545 !important; }
        `;
        document.head.appendChild(s);
    },

    _erstellePanel() {
        const p = document.createElement('div');
        p.id = 'voice-panel';
        p.style.cssText = `
            position:fixed;bottom:0;left:0;right:0;z-index:9998;
            background:#fff;border-top:3px solid #0d6efd;
            box-shadow:0 -4px 20px rgba(0,0,0,.15);
            display:none;padding:10px 20px;`;
        p.innerHTML = `
            <div class="d-flex align-items-center gap-3">
                <button id="voice-panel-btn" class="btn btn-outline-danger btn-sm d-flex align-items-center gap-2">
                    <i class="bi bi-mic-fill"></i> <span>Mikrofon EIN</span>
                </button>
                <div class="flex-grow-1">
                    <div id="voice-status" class="small"></div>
                    <div id="voice-interim" class="text-muted fst-italic" style="font-size:.8em;min-height:1em"></div>
                </div>
                <div class="text-muted" style="font-size:.72em;max-width:300px">
                    Sagen Sie: <em>"Kontonummer"</em> → Feld wählen<br>
                    dann: <em>"4001"</em> → Wert eintragen<br>
                    oder: <em>"Kontonummer 4001"</em> in einem Satz
                </div>
                <button class="btn btn-sm btn-outline-secondary" id="voice-close-btn">✕</button>
            </div>`;
        document.body.appendChild(p);
        this._panel = p;

        document.getElementById('voice-panel-btn').addEventListener('click', () => this.toggle());
        document.getElementById('voice-close-btn').addEventListener('click', () => {
            this._stoppen();
            p.style.display = 'none';
        });
    },

    _erstelleNavbarBtn() {
        const nav = document.querySelector('.navbar-nav.ms-auto');
        if (!nav) return;
        const li = document.createElement('li');
        li.className = 'nav-item';
        li.innerHTML = `
            <button id="voice-navbar-btn" class="btn btn-link nav-link px-2"
                    title="Spracheingabe (Alt+M)"
                    style="color:rgba(255,255,255,.85)">
                <i class="bi bi-mic" style="font-size:1.2em"></i>
            </button>`;
        nav.insertBefore(li, nav.firstChild);
        this._btn = document.getElementById('voice-navbar-btn');
        this._btn.addEventListener('click', () => {
            this._panel.style.display = '';
            this.toggle();
        });
    },

    _erstelleFeldMikrofone() {
        const felder = FeldSuche.alleFelder();
        felder.forEach(el => {
            if (el.dataset.voiceMic || el.type === 'checkbox' || el.type === 'radio') return;
            el.dataset.voiceMic = '1';

            const btn = document.createElement('button');
            btn.type = 'button';
            btn.title = 'Dieses Feld per Sprache ausfüllen';
            btn.style.cssText = `
                position:absolute;right:6px;top:50%;transform:translateY(-50%);
                background:none;border:none;color:#6c9bd2;cursor:pointer;
                font-size:.95em;padding:2px 4px;z-index:5;`;
            btn.innerHTML = '<i class="bi bi-mic"></i>';
            btn.addEventListener('click', e => {
                e.preventDefault();
                this._aktivFeld = el;
                feldHervorheben(el);
                this._panel.style.display = '';
                if (!this._aktiv) this._starten();
                this._status(`➡️ "${FeldSuche.labelFor(el)}" – Wert sprechen`, 'info');
            });

            el.style.paddingRight = '2rem';
            const par = el.parentNode;
            if (getComputedStyle(par).position === 'static') par.style.position = 'relative';
            par.appendChild(btn);
        });
    },

    _btnAktiv(an) {
        // Navbar-Button
        if (this._btn) {
            const icon = this._btn.querySelector('i');
            if (an) {
                icon.className = 'bi bi-mic-fill voice-mic-aktiv';
                icon.style.fontSize = '1.2em';
                this._btn.style.color = '#dc3545';
            } else {
                icon.className = 'bi bi-mic';
                icon.style.fontSize = '1.2em';
                this._btn.style.color = 'rgba(255,255,255,.85)';
            }
        }
        // Panel-Button
        const pb = document.getElementById('voice-panel-btn');
        if (pb) {
            pb.className = an ? 'btn btn-danger btn-sm d-flex align-items-center gap-2'
                              : 'btn btn-outline-danger btn-sm d-flex align-items-center gap-2';
            pb.querySelector('span').textContent = an ? 'Mikrofon AUS' : 'Mikrofon EIN';
        }
    },

    _hotkeys() {
        document.addEventListener('keydown', e => {
            if (e.altKey && e.key.toLowerCase() === 'm') {
                e.preventDefault();
                this._panel.style.display = '';
                this.toggle();
            }
        });
    },

    _statusInterim(text) {
        const el = document.getElementById('voice-interim');
        if (el) el.textContent = text + '…';
    },

    _status(html, klasse = 'info', dauer = 0) {
        if (this._panel) this._panel.style.display = '';
        const el = document.getElementById('voice-status');
        if (!el) return;
        const farben = {success:'#198754',danger:'#dc3545',warning:'#856404',info:'#0c63e4',secondary:'#6c757d'};
        el.style.color = farben[klasse] || '#333';
        el.innerHTML = html;
        const interim = document.getElementById('voice-interim');
        if (interim) interim.textContent = '';
        clearTimeout(this._timer);
        if (dauer > 0) this._timer = setTimeout(() => {
            if (el) el.innerHTML = this._aktiv ? '🎤 Mikrofon aktiv – sprechen Sie…' : '';
        }, dauer);
    },

    _panelVerstecken() {
        setTimeout(() => {
            if (!this._aktiv && this._panel) this._panel.style.display = 'none';
        }, 1500);
    },
};

// ─── Start ────────────────────────────────────────────────────────────────────

if (!Voice.isSupported()) {
    console.warn('[AgroVoice] SpeechRecognition nicht unterstützt.');
} else {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => Voice.init());
    } else {
        Voice.init();
    }
}

window.AgroVoice = { Voice, FeldSuche, VoiceNorm, wertEintragen };
