/**
 * agrobetrieb_voice.js – Formular-Spracheingabe für AgroBetrieb
 *
 * Kernidee: Mikrofon-Button im Formular startet einen geführten Durchlauf.
 * Die App geht Feld für Feld durch, liest den Feldnamen vor, wartet auf
 * Spracheingabe, trägt den Wert ein, springt automatisch zum nächsten Feld.
 *
 * Modi:
 *  1. GEFÜHRT  – Feld für Feld, App sagt welches Feld dran ist
 *  2. FREI     – Benutzer sagt "Fett vier Komma zwei" jederzeit → richtiges Feld
 *  3. DIKTAT   – Einzelnes Feld per Klick auf Mikrofon-Symbol neben dem Feld
 *
 * Sprachbefehle während Eingabe:
 *  "weiter" / "nächstes"  → nächstes Feld überspringen
 *  "zurück"               → vorheriges Feld
 *  "leer" / "überspringen"→ Feld leer lassen, weiter
 *  "löschen"              → aktuelles Feld leeren
 *  "speichern"            → Formular abschicken
 *  "stop" / "beenden"     → Spracheingabe beenden
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
        // Bereits numerisch
        const num = text.trim().replace(',', '.');
        if (!isNaN(parseFloat(num)) && num.match(/^-?[\d.]+$/)) return num;

        // "X komma Y" / "X punkt Y"
        const km = text.match(/^(.+?)\s+(?:komma|punkt)\s+(.+)$/i);
        if (km) {
            const v = this.zahl(km[1]);
            const n = this.zahl(km[2]);
            if (v !== null && n !== null) return `${v}.${n}`;
        }

        const lower = text.toLowerCase().trim()
            .replace(/\s*euro\s*/,'').replace(/\s*kilogramm\s*/,'')
            .replace(/\s*kilo\s*/,'').replace(/\s*prozent\s*/,'')
            .replace(/\s*tage?\s*/,'').replace(/\s*stunden?\s*/,'');

        if (this.WORTE[lower] !== undefined) return String(this.WORTE[lower]);

        // "dreiundzwanzig" → 23
        for (const [w, v] of Object.entries(this.WORTE)) {
            if (lower.endsWith('und' + w)) {
                const vor = this.zahl(lower.slice(0, -('und'+w).length));
                if (vor !== null) return String(Number(vor) + v);
            }
        }
        // "hundertzwanzig" → 120
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

        // "12.03.2026" / "12.03." / "12 3"
        const pm = t.match(/^(\d{1,2})[.\s-]+(\d{1,2})[.\s-]*(\d{2,4})?$/);
        if (pm) {
            const tag = pm[1].padStart(2,'0'), monat = pm[2].padStart(2,'0');
            const jahr = pm[3] ? (pm[3].length===2?'20'+pm[3]:pm[3]) : h.getFullYear();
            return `${jahr}-${monat}-${tag}`;
        }
        // "12. März" / "12 März 2026"
        const wm = t.match(/^(\d{1,2})\.\s*([a-zä]+)\s*(\d{4})?$/);
        if (wm) {
            const monat = MONATE[wm[2].slice(0,3)];
            if (monat) return `${wm[3]||h.getFullYear()}-${String(monat).padStart(2,'0')}-${wm[1].padStart(2,'0')}`;
        }
        return null;
    },

    // Wert für ein Feld normalisieren je nach Typ
    fuerFeld(text, el) {
        if (!el) return text;
        const typ = el.type?.toLowerCase() || el.tagName?.toLowerCase();
        if (typ === 'date')   return this.datum(text) ?? text;
        if (typ === 'number') return this.zahl(text)  ?? text;
        if (el.tagName?.toLowerCase() === 'select') return text; // Optionssuche separat
        return text;
    },
};


// ─── Sprach-Engine ────────────────────────────────────────────────────────────

const VoiceEngine = {
    _rec: null,
    _aktiv: false,
    _callbacks: {},

    isSupported: () => !!(window.SpeechRecognition || window.webkitSpeechRecognition),

    _init() {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        this._rec = new SR();
        this._rec.lang = 'de-AT';
        this._rec.continuous = false;   // EINZEL-Aufnahme pro Feld – zuverlässiger!
        this._rec.interimResults = true;
        this._rec.maxAlternatives = 2;

        this._rec.onresult = e => {
            let interim = '', final = '';
            for (let i = e.resultIndex; i < e.results.length; i++) {
                const t = e.results[i][0].transcript;
                e.results[i].isFinal ? (final += t) : (interim += t);
            }
            if (interim) this._emit('interim', interim.trim());
            if (final)   this._emit('final', final.trim());
        };
        this._rec.onerror = e => {
            if (e.error === 'not-allowed')
                this._emit('error', 'Mikrofonzugriff verweigert – bitte in den Browser-Einstellungen erlauben.');
            else if (e.error !== 'no-speech')
                this._emit('error', `Fehler: ${e.error}`);
            this._emit('end');
        };
        this._rec.onend = () => this._emit('end');
    },

    /** Startet EINE Aufnahme. Gibt Promise<string> zurück (finaler Text). */
    einmalAufnehmen() {
        return new Promise((resolve, reject) => {
            if (!this.isSupported()) { reject('nicht unterstützt'); return; }
            if (!this._rec) this._init();

            let finalText = '';
            const onFinal  = t => { finalText = t; };
            const onEnd    = () => {
                this.off('final', onFinal);
                this.off('end', onEnd);
                resolve(finalText);
            };
            const onError  = msg => {
                this.off('final', onFinal);
                this.off('end', onEnd);
                reject(msg);
            };

            this.on('final', onFinal);
            this.on('end', onEnd);
            this.on('error', onError);

            try { this._rec.start(); this._aktiv = true; }
            catch { resolve(''); }
        });
    },

    stop() {
        this._aktiv = false;
        try { this._rec?.stop(); } catch {}
    },

    on(ev, fn) {
        if (!this._callbacks[ev]) this._callbacks[ev] = [];
        this._callbacks[ev].push(fn);
    },
    off(ev, fn) {
        this._callbacks[ev] = (this._callbacks[ev]||[]).filter(f => f !== fn);
    },
    _emit(ev, data) {
        (this._callbacks[ev]||[]).forEach(fn => fn(data));
    },
};


// ─── Text-to-Speech (Ansage welches Feld dran ist) ───────────────────────────

const VoiceSprech = {
    _synth: window.speechSynthesis || null,
    _aktiv: true,   // kann deaktiviert werden

    sag(text) {
        if (!this._aktiv || !this._synth) return;
        this._synth.cancel();
        const utt = new SpeechSynthesisUtterance(text);
        utt.lang = 'de-AT';
        utt.rate = 1.1;
        utt.pitch = 1.0;
        this._synth.speak(utt);
    },

    async sagUndWarte(text) {
        if (!this._aktiv || !this._synth) return;
        return new Promise(resolve => {
            this._synth.cancel();
            const utt = new SpeechSynthesisUtterance(text);
            utt.lang = 'de-AT';
            utt.rate = 1.15;
            utt.onend = resolve;
            utt.onerror = resolve;
            this._synth.speak(utt);
        });
    },

    stop() { this._synth?.cancel(); },
};


// ─── Formular-Walker: geht Feld für Feld durch ───────────────────────────────

const FormularWalker = {
    _felder: [],       // [{el, label, typ}, ...]
    _index: -1,
    _laufend: false,
    _abbrechen: false,

    /** Alle ausfüllbaren Felder des Formulars erfassen. */
    _felderErmitteln() {
        const form = document.querySelector('form');
        const container = form || document.body;

        const alle = container.querySelectorAll(
            'input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=checkbox]):not([type=radio]):not([name=csrf_token]),' +
            'input[type=checkbox], input[type=radio], textarea, select'
        );

        const gefiltert = Array.from(alle).filter(el => {
                if (el.disabled || el.readOnly) return false;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') return false;
                return true;
            });

        console.log('[AgroVoice] Rohelemente:', alle.length, '→ nach Filter:', gefiltert.length,
            gefiltert.map(e => (e.tagName + (e.id?'#'+e.id:'') + '[' + (e.type||e.tagName) + '][name=' + e.name + ']')));

        return gefiltert
            .map(el => {
                // Label-Text ermitteln
                let label = '';
                if (el.id) {
                    const lbl = document.querySelector(`label[for="${el.id}"]`);
                    if (lbl) label = lbl.textContent.trim().replace(/\s*\*\s*$/, '');
                }
                if (!label) label = el.placeholder || el.name || el.id || 'Feld';
                label = label.replace(/_/g, ' ');
                return { el, label, typ: el.type || el.tagName.toLowerCase() };
            });
    },

    /** Startet den geführten Durchlauf. */
    async starten() {
        this._felder = this._felderErmitteln();
        console.log('[AgroVoice] starten(): Felder=', this._felder.length, 'panel=', VoiceUI._panel, 'init=', !!VoiceUI._panel);
        if (!this._felder.length) {
            alert('[AgroVoice DEBUG] Keine Felder gefunden!\nForm: ' + !!document.querySelector('form') + '\nAlle inputs: ' + document.querySelectorAll('input,select,textarea').length);
            VoiceUI.zeige('Keine Eingabefelder auf dieser Seite gefunden.', 'warning', 3000);
            VoiceSprech.sag('Keine Eingabefelder gefunden.');
            return;
        }
        this._index = 0;
        this._laufend = true;
        this._abbrechen = false;

        VoiceUI.zeige('Geführte Spracheingabe gestartet. Sagen Sie "stop" zum Beenden.', 'info', 0);
        await this._feldDurchlauf();
    },

    /** Verarbeitet ein einzelnes Feld. */
    async _feldDurchlauf() {
        if (this._abbrechen || this._index >= this._felder.length) {
            this._beenden();
            return;
        }

        const { el, label, typ } = this._felder[this._index];

        // Feld hervorheben
        this._felderHervorheben(el);

        // Ansage
        VoiceUI.zeigeFeldInfo(label, this._index + 1, this._felder.length);
        let ansage = label;
        if (el.tagName.toLowerCase() === 'select') {
            const opts = Array.from(el.options).filter(o => o.value !== '').slice(0, 5);
            if (opts.length) ansage += `. Optionen: ${opts.map(o => o.text).join(', ')}`;
        }
        await VoiceSprech.sagUndWarte(ansage);

        if (this._abbrechen) { this._beenden(); return; }

        // Aufnahme starten
        VoiceUI.zeigeMikrofonAktiv(true, label);
        let gehört = '';
        try {
            gehört = await VoiceEngine.einmalAufnehmen();
        } catch (err) {
            VoiceUI.zeige(`Fehler: ${err}`, 'danger');
            this._beenden();
            return;
        }
        VoiceUI.zeigeMikrofonAktiv(false, label);

        if (this._abbrechen) { this._beenden(); return; }

        // Steuerbefehle prüfen
        const cmd = gehört.toLowerCase().trim();
        if (/^(stop|stopp|beenden|fertig|abbruch|abbrechen)$/.test(cmd)) {
            this._beenden();
            return;
        }
        if (/^(weiter|nächstes|nächste|überspringen|skip)$/.test(cmd)) {
            this._index++;
            await this._feldDurchlauf();
            return;
        }
        if (/^(zurück|vorher|voriges)$/.test(cmd)) {
            this._index = Math.max(0, this._index - 1);
            await this._feldDurchlauf();
            return;
        }
        if (/^(leer|löschen|leeren|leer lassen)$/.test(cmd)) {
            el.value = '';
            el.dispatchEvent(new Event('input', { bubbles: true }));
            this._index++;
            await this._feldDurchlauf();
            return;
        }
        if (/^(speichern|absenden|bestätigen)$/.test(cmd)) {
            document.querySelector('form')?.requestSubmit();
            return;
        }

        // Wert eintragen
        if (gehört) {
            this._werteintragen(el, typ, gehört);
            VoiceUI.zeige(`✅ ${label}: "${el.value}"`, 'success', 2000);
        }

        this._index++;
        // Kurze Pause dann nächstes Feld
        await new Promise(r => setTimeout(r, 400));
        await this._feldDurchlauf();
    },

    /** Trägt einen Wert in das Feld ein. */
    _werteintragen(el, typ, text) {
        if (typ === 'date') {
            const d = VoiceNorm.datum(text);
            if (d) { el.value = d; el.dispatchEvent(new Event('change', { bubbles: true })); return; }
        }
        if (typ === 'number') {
            const z = VoiceNorm.zahl(text);
            if (z !== null) { el.value = z; el.dispatchEvent(new Event('input', { bubbles: true })); return; }
        }
        if (el.tagName.toLowerCase() === 'select') {
            const lower = text.toLowerCase().trim();
            const opts = Array.from(el.options).filter(o => o.value !== '');

            // 1. Exakter Treffer
            let treffer = opts.find(o => o.text.toLowerCase() === lower);
            // 2. Gesprochen ist Teilstring der Option
            if (!treffer) treffer = opts.find(o => o.text.toLowerCase().includes(lower));
            // 3. Option ist Teilstring des Gesagten
            if (!treffer) treffer = opts.find(o => lower.includes(o.text.toLowerCase()));
            // 4. Erste 4 Zeichen der Option im Gesagten
            if (!treffer) treffer = opts.find(o => {
                const anfang = o.text.toLowerCase().slice(0, 4);
                return anfang.length >= 3 && lower.includes(anfang);
            });
            // 5. Levenshtein-ähnlich: >=60% der Zeichen stimmen überein
            if (!treffer) {
                treffer = opts.find(o => {
                    const a = o.text.toLowerCase().replace(/\s+/g,'');
                    const b = lower.replace(/\s+/g,'');
                    if (!a || !b) return false;
                    let match = 0;
                    for (const c of b) if (a.includes(c)) match++;
                    return match / Math.max(a.length, b.length) >= 0.6;
                });
            }

            if (treffer) {
                el.value = treffer.value;
                el.dispatchEvent(new Event('change', { bubbles: true }));
                VoiceUI.zeige(`✅ Ausgewählt: "${treffer.text}"`, 'success', 2000);
                return;
            }
            // Nicht gefunden → Optionen vorlesen
            const liste = opts.slice(0, 6).map(o => o.text).join(', ');
            VoiceSprech.sag(`Nicht gefunden. Mögliche Optionen: ${liste}`);
            VoiceUI.zeige(`⚠️ "${text}" nicht in Liste. Optionen: ${liste}`, 'warning', 4000);
            return;
        }
        if (typ === 'checkbox') {
            const ja = /ja|ja|wahr|true|ein|an|positiv/i.test(text);
            const nein = /nein|falsch|false|aus|negativ/i.test(text);
            if (ja) el.checked = true;
            if (nein) el.checked = false;
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return;
        }
        // Text / Textarea
        el.value = text;
        el.dispatchEvent(new Event('input', { bubbles: true }));
    },

    /** Hebt das aktive Feld visuell hervor. */
    _felderHervorheben(aktiv) {
        // Vorherige Hervorhebungen entfernen
        document.querySelectorAll('.voice-aktiv-feld').forEach(el => {
            el.classList.remove('voice-aktiv-feld');
            el.style.outline = '';
            el.style.boxShadow = '';
        });
        if (aktiv) {
            aktiv.classList.add('voice-aktiv-feld');
            aktiv.style.outline = '3px solid #0d6efd';
            aktiv.style.boxShadow = '0 0 0 4px rgba(13,110,253,0.25)';
            aktiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
            aktiv.focus();
        }
    },

    _beenden() {
        this._laufend = false;
        this._abbrechen = false;
        this._felderHervorheben(null);
        VoiceSprech.stop();
        VoiceEngine.stop();
        VoiceUI.zeige('Spracheingabe beendet.', 'secondary', 2500);
        setTimeout(() => VoiceUI.verstecken(), 2600);
    },

    abbrechen() {
        this._abbrechen = true;
        this._beenden();
    },
};


// ─── Freie Spracheingabe (kein Feld-Durchlauf, jederzeit sprechen) ───────────

const FreieSprache = {
    _laufend: false,

    // Schlüsselwörter → Feld-IDs (mehrere IDs als komma-sep. Fallback-Kette)
    FELD_MAP: [
        { re:/datum|am |vom |date/i,                    ids:['datum','beginn','beleg_datum'] },
        { re:/beginn/i,                                 ids:['beginn'] },
        { re:/ende/i,                                   ids:['ende'] },
        { re:/morgen\w*gemelk|morgen/i,                 ids:['probenahme_morgen_kg'] },
        { re:/abend\w*gemelk|abend/i,                   ids:['probenahme_abend_kg'] },
        { re:/milch\w*menge|tages\w*gemelk|gemelk/i,    ids:['milchmenge_kg'] },
        { re:/fett/i,                                   ids:['fett_prozent'] },
        { re:/eiwei[sß]/i,                              ids:['eiweiss_prozent'] },
        { re:/laktose/i,                                ids:['laktose_prozent'] },
        { re:/harnstoff/i,                              ids:['harnstoff_mg_dl'] },
        { re:/zellzahl|zell/i,                          ids:['zellzahl_tsd','zellzahl_tank'] },
        { re:/keimzahl|keim/i,                          ids:['gesamtkeimzahl'] },
        { re:/betrag|summe/i,                           ids:['betrag'] },
        { re:/buchungs\w*text|text/i,                   ids:['buchungstext'] },
        { re:/betreff/i,                                ids:['betreff'] },
        { re:/bezeichnung/i,                            ids:['bezeichnung'] },
        { re:/arzneimittel|medikament|mittel/i,         ids:['arzneimittel_name'] },
        { re:/wirkstoff/i,                              ids:['wirkstoff'] },
        { re:/diagnose/i,                               ids:['diagnose'] },
        { re:/charge/i,                                 ids:['charge'] },
        { re:/tierarzt/i,                               ids:['tierarzt_name'] },
        { re:/wartezeit\s*milch/i,                      ids:['wartezeit_milch_tage'] },
        { re:/wartezeit\s*fleisch/i,                    ids:['wartezeit_fleisch_tage'] },
        { re:/dauer/i,                                  ids:['behandlungsdauer_tage'] },
        { re:/ohrmarke/i,                               ids:['ohrmarke'] },
        { re:/stier|bulle/i,                            ids:['stier_name'] },
        { re:/molkerei/i,                               ids:['molkerei'] },
        { re:/eier\s*gesamt|eier/i,                     ids:['eier_gesamt'] },
        { re:/verluste?/i,                              ids:['verluste'] },
        { re:/futter/i,                                 ids:['futterverbrauch_kg'] },
        { re:/temperatur/i,                             ids:['temperatur_stall'] },
        { re:/bemerkung|notiz/i,                        ids:['bemerkung'] },
        { re:/menge/i,                                  ids:['milchmenge_kg','mengekg','menge'] },
        { re:/preis|auszahlung/i,                       ids:['auszahlungspreis_ct_kg','letzter_einkaufspreis'] },
        { re:/mindest\w*bestand/i,                      ids:['mindestbestand'] },
        { re:/monat/i,                                  ids:['monat'] },
        { re:/jahr/i,                                   ids:['jahr','geschaeftsjahr'] },
        { re:/anschaffung/i,                            ids:['anschaffungswert'] },
        { re:/name/i,                                   ids:['name'] },
    ],

    /** Startet dauerhaftes Zuhören (kein Feld-Durchlauf). */
    async starten() {
        if (this._laufend) { this.stoppen(); return; }
        if (!VoiceEngine.isSupported()) {
            VoiceUI.zeige('Spracheingabe wird von diesem Browser nicht unterstützt.', 'danger'); return;
        }
        this._laufend = true;
        VoiceUI.zeige('Freie Spracheingabe aktiv. Sprechen Sie z.B. "Fett vier Komma zwei"', 'info', 0);
        this._schleife();
    },

    async _schleife() {
        while (this._laufend) {
            VoiceUI.zeigeMikrofonAktiv(true, null);
            let text = '';
            try { text = await VoiceEngine.einmalAufnehmen(); }
            catch { break; }
            VoiceUI.zeigeMikrofonAktiv(false, null);

            if (!text || !this._laufend) break;

            const cmd = text.toLowerCase().trim();
            if (/^(stop|stopp|beenden|fertig)$/.test(cmd)) break;
            if (/^(speichern|absenden)$/.test(cmd)) {
                document.querySelector('form')?.requestSubmit(); break;
            }
            if (/^(zurück|back)$/.test(cmd)) { history.back(); break; }

            this._verarbeite(text);
        }
        this.stoppen();
    },

    /** Parst Text und füllt Felder. */
    _verarbeite(text) {
        // Segmente durch Komma / "und" trennen
        const segmente = text.split(/,|;\s*|\s+und\s+/i);
        let gefuellt = 0;

        for (const seg of segmente) {
            const s = seg.trim();
            if (!s) continue;

            for (const { re, ids } of this.FELD_MAP) {
                if (!re.test(s)) continue;

                // Wert = alles nach dem Schlüsselwort
                const wert = s.replace(re, '').trim();
                if (!wert) continue;

                for (const id of ids) {
                    const el = document.getElementById(id);
                    if (!el) continue;

                    FormularWalker._werteintragen(el, el.type || el.tagName.toLowerCase(), wert);

                    // Visuelles Highlight
                    el.style.outline = '3px solid #198754';
                    el.style.boxShadow = '0 0 0 3px rgba(25,135,84,0.3)';
                    setTimeout(() => { el.style.outline=''; el.style.boxShadow=''; }, 1500);
                    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    gefuellt++;
                    break;
                }
                break;
            }
        }

        if (gefuellt > 0) {
            VoiceUI.zeige(`✅ ${gefuellt} Feld${gefuellt>1?'er':''} ausgefüllt: "${text}"`, 'success', 2500);
        } else {
            VoiceUI.zeige(`⚠️ Nicht erkannt: "${text}"`, 'warning', 2500);
        }
    },

    stoppen() {
        this._laufend = false;
        VoiceEngine.stop();
        VoiceUI.zeige('Spracheingabe beendet.', 'secondary', 2000);
        setTimeout(() => VoiceUI.verstecken(), 2100);
    },
};


// ─── Diktat für einzelnes Feld ───────────────────────────────────────────────

const FeldDiktat = {
    async starten(el) {
        if (!VoiceEngine.isSupported()) return;
        const label = document.querySelector(`label[for="${el.id}"]`)?.textContent?.trim() || el.id;
        VoiceUI.zeige(`🎤 Sprechen Sie "${label}"…`, 'info', 0);
        el.style.outline = '3px solid #0d6efd';

        let text = '';
        try { text = await VoiceEngine.einmalAufnehmen(); }
        catch {}

        el.style.outline = '';
        if (text && !/^(stop|stopp)$/i.test(text)) {
            FormularWalker._werteintragen(el, el.type || el.tagName.toLowerCase(), text);
            VoiceUI.zeige(`✅ ${label}: "${el.value}"`, 'success', 2000);
        } else {
            VoiceUI.verstecken();
        }
    },
};


// ─── Voice UI ─────────────────────────────────────────────────────────────────

const VoiceUI = {
    _panel: null,
    _timer: null,

    init() {
        if (!VoiceEngine.isSupported()) return;
        this._erstellePanel();
        this._erstelleNavbarMikrofon();
        this._erstelleFormularButton();
        this._erstelleFeldMikrofone();
        this._hotkey();

        // Interim-Text anzeigen
        VoiceEngine.on('interim', t => {
            const el = document.getElementById('voice-interim');
            if (el) el.textContent = t + '…';
        });
        VoiceEngine.on('end', () => {
            const el = document.getElementById('voice-interim');
            if (el) el.textContent = '';
        });
    },

    /** Großes Panel am unteren Bildschirmrand. */
    _erstellePanel() {
        const p = document.createElement('div');
        p.id = 'voice-panel';
        p.style.cssText = `
            position:fixed; bottom:0; left:0; right:0; z-index:9998;
            background:#fff; border-top:3px solid #0d6efd;
            box-shadow:0 -4px 20px rgba(0,0,0,.15);
            display:none; padding:10px 20px;`;
        p.innerHTML = `
            <div class="d-flex align-items-center gap-3 flex-wrap">
                <div id="voice-mic-anim" style="font-size:1.8em;line-height:1">🎤</div>
                <div class="flex-grow-1">
                    <div id="voice-feld-info" class="fw-bold text-primary" style="font-size:0.9em"></div>
                    <div id="voice-interim" class="text-muted fst-italic" style="font-size:0.85em;min-height:1.2em"></div>
                    <div id="voice-msg" class="small"></div>
                </div>
                <div class="d-flex gap-2">
                    <button class="btn btn-sm btn-outline-secondary" id="voice-ton-btn" title="Ansage ein/aus">
                        <i class="bi bi-volume-up"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" id="voice-stop-btn">
                        <i class="bi bi-x-lg"></i> Stop
                    </button>
                </div>
            </div>
            <div class="text-muted mt-1" style="font-size:0.72em">
                <strong>Befehle:</strong>
                "weiter" | "zurück" | "leer" | "löschen" | "speichern" | "stop"
            </div>`;
        document.body.appendChild(p);
        this._panel = p;

        document.getElementById('voice-stop-btn').addEventListener('click', () => {
            FormularWalker.abbrechen();
            FreieSprache.stoppen();
        });

        let tonAn = true;
        document.getElementById('voice-ton-btn').addEventListener('click', () => {
            tonAn = !tonAn;
            VoiceSprech._aktiv = tonAn;
            document.getElementById('voice-ton-btn').innerHTML =
                tonAn ? '<i class="bi bi-volume-up"></i>' : '<i class="bi bi-volume-mute"></i>';
        });
    },

    /** Großer Mikrofon-Button direkt im/über dem Formular. */
    _erstelleFormularButton() {
        const form = document.querySelector('form');
        if (!form) return;

        const wrapper = document.createElement('div');
        wrapper.className = 'd-flex gap-2 mb-3 align-items-center';
        wrapper.innerHTML = `
            <button type="button" id="voice-gefuehrt-btn"
                    class="btn btn-primary btn-sm d-flex align-items-center gap-2"
                    title="Geführte Spracheingabe: Feld für Feld (Alt+G)">
                <i class="bi bi-mic-fill"></i>
                <span>Spracheingabe geführt</span>
            </button>
            <button type="button" id="voice-frei-btn"
                    class="btn btn-outline-primary btn-sm d-flex align-items-center gap-2"
                    title="Freie Spracheingabe: jederzeit sprechen (Alt+F)">
                <i class="bi bi-mic"></i>
                <span>Frei sprechen</span>
            </button>
            <span class="text-muted small ms-1">z.B. <em>"Fett vier Komma zwei, Milch dreißig Kilo"</em></span>`;

        // Vor dem ersten Formular-Element einfügen
        form.insertBefore(wrapper, form.firstChild);

        document.getElementById('voice-gefuehrt-btn').addEventListener('click', () => {
            FormularWalker.starten();
        });
        document.getElementById('voice-frei-btn').addEventListener('click', () => {
            FreieSprache.starten();
        });
    },

    /** Kleines Mikrofon-Icon neben jedem Eingabefeld. */
    _erstelleFeldMikrofone() {
        const form = document.querySelector('form');
        if (!form) return;

        form.querySelectorAll(
            'input[type=text], input[type=number], input[type=date], textarea, select'
        ).forEach(el => {
            if (el.dataset.voiceMic) return;
            el.dataset.voiceMic = '1';

            const btn = document.createElement('button');
            btn.type = 'button';
            btn.title = 'Dieses Feld per Sprache ausfüllen';
            btn.style.cssText = `
                position:absolute; right:6px; top:50%; transform:translateY(-50%);
                background:none; border:none; color:#6c9bd2; cursor:pointer;
                font-size:1em; padding:2px 4px; transition:color .15s;
                z-index:5;`;
            btn.innerHTML = '<i class="bi bi-mic"></i>';
            btn.addEventListener('click', e => { e.preventDefault(); FeldDiktat.starten(el); });
            btn.addEventListener('mouseenter', () => btn.style.color = '#0d6efd');
            btn.addEventListener('mouseleave', () => btn.style.color = '#6c9bd2');

            // Padding rechts damit Text nicht unter Icon läuft
            el.style.paddingRight = '2rem';

            const par = el.parentNode;
            const cs = getComputedStyle(par);
            if (cs.position === 'static') par.style.position = 'relative';
            par.appendChild(btn);
        });
    },

    _erstelleNavbarMikrofon() {
        const navRight = document.querySelector('.navbar-nav.ms-auto');
        if (!navRight) return;
        const li = document.createElement('li');
        li.className = 'nav-item';
        li.innerHTML = `
            <button id="voice-navbar-btn" class="btn btn-link nav-link px-2"
                    title="Spracheingabe starten (Alt+G)"
                    style="color:rgba(255,255,255,.85)">
                <i class="bi bi-mic-fill" style="font-size:1.1em"></i>
            </button>`;
        navRight.insertBefore(li, navRight.firstChild);
        document.getElementById('voice-navbar-btn').addEventListener('click', () => {
            FormularWalker.starten();
        });
    },

    _hotkey() {
        document.addEventListener('keydown', e => {
            if (e.altKey && e.key === 'g') { e.preventDefault(); FormularWalker.starten(); }
            if (e.altKey && e.key === 'f') { e.preventDefault(); FreieSprache.starten(); }
            if (e.altKey && e.key === 'm') { e.preventDefault(); FreieSprache.starten(); }
        });
    },

    zeigeFeldInfo(label, nr, gesamt) {
        this._panel.style.display = '';
        const fi = document.getElementById('voice-feld-info');
        if (fi) fi.innerHTML =
            `<i class="bi bi-arrow-right-circle-fill"></i> Feld ${nr}/${gesamt}: <strong>${label}</strong>`;
    },

    zeigeMikrofonAktiv(aktiv, label) {
        const mic = document.getElementById('voice-mic-anim');
        if (!mic) return;
        if (aktiv) {
            mic.innerHTML = '🔴';
            mic.style.animation = 'voice-pulse 0.8s ease-in-out infinite';
        } else {
            mic.innerHTML = '🎤';
            mic.style.animation = '';
        }
    },

    zeige(html, klasse = 'info', dauer = 3000) {
        this._panel.style.display = '';
        const msg = document.getElementById('voice-msg');
        if (msg) {
            const farben = { success:'#198754', danger:'#dc3545', warning:'#856404',
                             info:'#0c63e4', secondary:'#6c757d', light:'#333', 'default':'#333' };
            msg.style.color = farben[klasse] || farben.default;
            msg.innerHTML = html;
        }
        clearTimeout(this._timer);
        if (dauer > 0) this._timer = setTimeout(() => this.verstecken(), dauer);
    },

    verstecken() {
        if (!FormularWalker._laufend && !FreieSprache._laufend)
            this._panel.style.display = 'none';
    },
};


// ─── CSS für Mikrofon-Animation ───────────────────────────────────────────────

const style = document.createElement('style');
style.textContent = `
@keyframes voice-pulse {
    0%, 100% { transform: scale(1); opacity: 1; }
    50%       { transform: scale(1.3); opacity: 0.7; }
}`;
document.head.appendChild(style);


// ─── Start ────────────────────────────────────────────────────────────────────

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => VoiceUI.init());
} else {
    VoiceUI.init();
}

window.AgroVoice = { FormularWalker, FreieSprache, FeldDiktat, VoiceSprech, VoiceNorm, VoiceUI };
