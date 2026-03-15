/**
 * milchvieh_ki.js – Browser-KI-Integration für Milchvieh-Formulare
 *
 * Unterstützt:
 *  1. Chrome Built-in AI (Prompt API, window.ai / LanguageModel API) – Gemini Nano, lokal
 *  2. Fallback: regelbasierte JS-Logik (überall verfügbar)
 *
 * Kein externer API-Key notwendig. Datenschutzkonform: alle Daten bleiben im Browser.
 */

'use strict';

// ─── Browser AI Capability Check ──────────────────────────────────────────────

const BrowserAI = {
    _session: null,
    _supported: null,

    /**
     * Prüft ob Chrome Built-in AI verfügbar ist (Chrome 127+ mit Gemini Nano).
     * @returns {Promise<boolean>}
     */
    async isSupported() {
        if (this._supported !== null) return this._supported;
        try {
            // Chrome Prompt API (Origin Trial / Canary)
            if (window.LanguageModel) {
                const caps = await window.LanguageModel.availability();
                this._supported = (caps === 'available' || caps === 'downloadable');
                return this._supported;
            }
            // Ältere window.ai API
            if (window.ai && window.ai.languageModel) {
                const caps = await window.ai.languageModel.capabilities();
                this._supported = caps.available !== 'no';
                return this._supported;
            }
        } catch (e) {
            // ignore
        }
        this._supported = false;
        return false;
    },

    /**
     * Erstellt oder gibt eine KI-Session zurück.
     * @param {string} systemPrompt
     * @returns {Promise<object|null>}
     */
    async getSession(systemPrompt) {
        if (this._session) return this._session;
        try {
            if (window.LanguageModel) {
                this._session = await window.LanguageModel.create({ systemPrompt });
            } else if (window.ai && window.ai.languageModel) {
                this._session = await window.ai.languageModel.create({ systemPrompt });
            }
        } catch (e) {
            console.warn('[BrowserAI] Session creation failed:', e);
        }
        return this._session;
    },

    /**
     * Sendet einen Prompt an die KI, gibt Text zurück (oder null bei Fehler).
     * @param {string} prompt
     * @param {string} [systemPrompt]
     * @returns {Promise<string|null>}
     */
    async prompt(prompt, systemPrompt = '') {
        const supported = await this.isSupported();
        if (!supported) return null;
        try {
            const session = await this.getSession(systemPrompt);
            if (!session) return null;
            const result = await session.prompt(prompt);
            return result || null;
        } catch (e) {
            console.warn('[BrowserAI] Prompt failed:', e);
            return null;
        }
    },

    /** Session schließen (Speicher freigeben). */
    destroy() {
        if (this._session) {
            try { this._session.destroy(); } catch (e) {}
            this._session = null;
        }
    }
};


// ─── Tier-Autocomplete ─────────────────────────────────────────────────────────

/**
 * Initialisiert Ohrmarke/Name-Autocomplete für ein Input-Feld.
 * Lädt Tierliste einmalig von /milchvieh/api/tiere (JSON).
 *
 * @param {string} inputId   – Element-ID des Eingabefeldes
 * @param {function} onSelect – Callback(tier) wenn ein Tier ausgewählt wird
 */
async function initTierAutocomplete(inputId, onSelect) {
    const input = document.getElementById(inputId);
    if (!input) return;

    let tiere = [];
    try {
        const resp = await fetch('/milchvieh/api/tiere');
        tiere = await resp.json();
    } catch (e) {
        return; // Autocomplete deaktiviert wenn API nicht erreichbar
    }

    // Dropdown-Container
    const wrapper = document.createElement('div');
    wrapper.style.position = 'relative';
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    const dropdown = document.createElement('ul');
    dropdown.className = 'list-group position-absolute w-100 shadow-sm';
    dropdown.style.cssText = 'z-index:1000;max-height:220px;overflow-y:auto;top:100%;left:0;display:none;';
    wrapper.appendChild(dropdown);

    function fuzzyFilter(query) {
        const q = query.toLowerCase();
        return tiere.filter(t =>
            t.ohrmarke.toLowerCase().includes(q) ||
            t.name.toLowerCase().includes(q)
        ).slice(0, 8);
    }

    function renderDropdown(matches) {
        dropdown.innerHTML = '';
        if (!matches.length) { dropdown.style.display = 'none'; return; }
        matches.forEach(t => {
            const li = document.createElement('li');
            li.className = 'list-group-item list-group-item-action py-1 px-2 small';
            li.style.cursor = 'pointer';
            li.innerHTML = `<code>${t.ohrmarke}</code>${t.name ? ' · ' + t.name : ''}` +
                           `<span class="text-muted ms-2">${t.rasse || ''}</span>`;
            li.addEventListener('mousedown', e => {
                e.preventDefault();
                input.value = t.ohrmarke;
                dropdown.style.display = 'none';
                if (onSelect) onSelect(t);
            });
            dropdown.appendChild(li);
        });
        dropdown.style.display = 'block';
    }

    input.addEventListener('input', () => {
        const q = input.value.trim();
        if (q.length < 2) { dropdown.style.display = 'none'; return; }
        renderDropdown(fuzzyFilter(q));
    });
    input.addEventListener('blur', () => {
        setTimeout(() => { dropdown.style.display = 'none'; }, 200);
    });
    input.addEventListener('focus', () => {
        const q = input.value.trim();
        if (q.length >= 2) renderDropdown(fuzzyFilter(q));
    });
}


// ─── Harnstoff-Ampel ──────────────────────────────────────────────────────────

/**
 * Live-Ampel für Harnstoff-Eingabe (LFZ Raumberg-Gumpenstein Richtwerte).
 * Richtwerte: < 150 Energie-/Proteinmangel, 150–300 optimal, > 300 Überversorgung
 *
 * @param {string} inputId   – Element-ID der Harnstoff-Eingabe
 * @param {string} feedbackId – Element-ID für Ampel-Feedback
 */
function initHarnstoffAmpel(inputId, feedbackId) {
    const input = document.getElementById(inputId);
    const feedback = document.getElementById(feedbackId);
    if (!input || !feedback) return;

    function bewerte(val) {
        if (!val || isNaN(val)) return null;
        const v = parseFloat(val);
        if (v < 100) return { klasse: 'danger', text: `⛔ ${v} mg/l – kritisch niedrig (Energiemangel/Proteinmangel)` };
        if (v < 150) return { klasse: 'warning', text: `⚠️ ${v} mg/l – etwas niedrig (Ziel: 150–300 mg/l)` };
        if (v <= 300) return { klasse: 'success', text: `✅ ${v} mg/l – optimal (Richtwert: 150–300 mg/l)` };
        if (v <= 400) return { klasse: 'warning', text: `⚠️ ${v} mg/l – erhöht (Proteinüberversorgung möglich)` };
        return { klasse: 'danger', text: `⛔ ${v} mg/l – stark erhöht! Leberbelastung prüfen` };
    }

    input.addEventListener('input', () => {
        const r = bewerte(input.value);
        if (!r) { feedback.innerHTML = ''; return; }
        feedback.innerHTML = `<div class="alert alert-${r.klasse} py-1 px-2 small mt-1 mb-0">${r.text}</div>`;
    });
}


// ─── Zellzahl-Ampel ───────────────────────────────────────────────────────────

/**
 * Live-Ampel für Zellzahl-Eingabe (Tsd./ml).
 * @param {string} inputId
 * @param {string} feedbackId
 */
function initZellzahlAmpel(inputId, feedbackId) {
    const input = document.getElementById(inputId);
    const feedback = document.getElementById(feedbackId);
    if (!input || !feedback) return;

    function bewerte(val) {
        if (!val || isNaN(val)) return null;
        const v = parseFloat(val);
        if (v < 100) return { klasse: 'success', text: `✅ ${v} Tsd./ml – eutergesund` };
        if (v < 200) return { klasse: 'warning', text: `⚠️ ${v} Tsd./ml – grenzwertig (beobachten)` };
        if (v < 400) return { klasse: 'danger', text: `⛔ ${v} Tsd./ml – erhöht! Subklinische Mastitis möglich` };
        return { klasse: 'danger', text: `🚨 ${v} Tsd./ml – kritisch! Klinische Mastitis-Abklärung dringend` };
    }

    input.addEventListener('input', () => {
        const r = bewerte(input.value);
        if (!r) { feedback.innerHTML = ''; return; }
        feedback.innerHTML = `<div class="alert alert-${r.klasse} py-1 px-2 small mt-1 mb-0">${r.text}</div>`;
    });
}


// ─── ECM Live-Berechnung ──────────────────────────────────────────────────────

/**
 * Zeigt ECM live während Eingabe (Sjaunja-Formel).
 * @param {string} mengeId
 * @param {string} fettId
 * @param {string} eiweissId
 * @param {string} ecmResultId
 */
function initEcmLive(mengeId, fettId, eiweissId, ecmResultId) {
    const ids = [mengeId, fettId, eiweissId];
    const result = document.getElementById(ecmResultId);
    if (!result) return;

    function berechne() {
        const kg = parseFloat(document.getElementById(mengeId)?.value) || 0;
        const f = parseFloat(document.getElementById(fettId)?.value) || 0;
        const e = parseFloat(document.getElementById(eiweissId)?.value) || 0;
        if (!kg || !f || !e) { result.textContent = '–'; return; }
        const ecm = kg * (0.383 * f + 0.242 * e + 0.7832) / 3.1138;
        result.textContent = ecm.toFixed(1) + ' kg ECM';
        // FE-Quotient
        const fe = f / e;
        const feEl = document.getElementById(ecmResultId + '_fe');
        if (feEl) {
            const klasse = fe >= 1.1 && fe <= 1.5 ? 'text-success' : 'text-warning';
            feEl.innerHTML = ` | <span class="${klasse}">F:E = ${fe.toFixed(2)}</span>`;
        }
    }

    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('input', berechne);
    });
}


// ─── Brunst-Prognose ──────────────────────────────────────────────────────────

/**
 * Berechnet und zeigt Brunst-Prognose basierend auf letzter Besamung.
 * Brunstzykluslänge Rind: ~21 Tage (±2 Tage Beobachtungsfenster)
 *
 * @param {Date} letzteBesamungDatum
 * @param {string} containerId – ID des Containers für Prognose-Anzeige
 */
function zeigeBrunstPrognose(letzteBesamungDatum, containerId) {
    const container = document.getElementById(containerId);
    if (!container || !letzteBesamungDatum) return;

    const heute = new Date();
    heute.setHours(0, 0, 0, 0);
    const basis = new Date(letzteBesamungDatum);
    basis.setHours(0, 0, 0, 0);

    const prognosen = [];
    for (let z = 1; z <= 3; z++) {
        const brunst = new Date(basis);
        brunst.setDate(brunst.getDate() + z * 21);
        const start = new Date(brunst); start.setDate(start.getDate() - 2);
        const ende = new Date(brunst); ende.setDate(ende.getDate() + 2);
        const tageBis = Math.round((brunst - heute) / 86400000);
        prognosen.push({ zyklus: z, datum: brunst, start, ende, tageBis });
    }

    let html = '<div class="alert alert-info small mt-2 mb-0"><strong><i class="bi bi-arrow-repeat"></i> Brunst-Prognose (21-Tage-Zyklus):</strong><ul class="mb-0 mt-1">';
    prognosen.forEach(p => {
        const fmt = d => d.toLocaleDateString('de-AT', { day: '2-digit', month: '2-digit', year: 'numeric' });
        const aktiv = p.tageBis >= -2 && p.tageBis <= 2;
        const klasse = aktiv ? 'fw-bold text-danger' : (p.tageBis < 0 ? 'text-muted' : '');
        html += `<li class="${klasse}">${fmt(p.start)} – ${fmt(p.ende)}` +
                (p.tageBis > 0 ? ` (in ${p.tageBis} Tagen)` : (p.tageBis < 0 ? ` (vor ${-p.tageBis} Tagen)` : ' ← <strong>HEUTE!</strong>')) +
                `${aktiv ? ' 🔴' : ''}</li>`;
    });
    html += '</ul></div>';
    container.innerHTML = html;
}


// ─── Browser AI: TAMG Arzneimittel-Assistent ─────────────────────────────────

/**
 * Initialisiert den KI-Assistenten für das TAMG-Formular.
 * Nutzt Chrome Built-in AI (Gemini Nano) falls verfügbar,
 * sonst Fallback auf betriebseigene History (Autocomplete + Wartezeiten).
 *
 * @param {object} opts
 * @param {string} opts.nameInputId       – Arzneimittel-Name Input
 * @param {string} opts.wirkstoffInputId  – Wirkstoff Input
 * @param {string} opts.wz_milchInputId   – Wartezeit Milch Input
 * @param {string} opts.wz_fleischInputId – Wartezeit Fleisch Input
 * @param {string} opts.antibiotikumId    – Antibiotikum Checkbox
 * @param {string} opts.aiFeedbackId      – Container für KI-Feedback
 * @param {string} opts.historyApiUrl     – URL zu /milchvieh/api/arzneimittel_history
 */
async function initTamgAssistent(opts) {
    const nameEl = document.getElementById(opts.nameInputId);
    const wirkstoffEl = document.getElementById(opts.wirkstoffInputId);
    const wz_milchEl = document.getElementById(opts.wz_milchInputId);
    const wz_fleischEl = document.getElementById(opts.wz_fleischInputId);
    const abEl = document.getElementById(opts.antibiotikumId);
    const feedbackEl = document.getElementById(opts.aiFeedbackId);
    if (!nameEl || !feedbackEl) return;

    // 1. Betriebseigene History laden
    let history = [];
    try {
        const resp = await fetch(opts.historyApiUrl);
        history = await resp.json();
    } catch (e) {}

    // 2. Browser AI prüfen
    const kiVerfuegbar = await BrowserAI.isSupported();
    if (kiVerfuegbar) {
        feedbackEl.innerHTML = '<div class="badge bg-success mb-1"><i class="bi bi-robot"></i> Browser-KI aktiv (Gemini Nano)</div>';
    } else {
        feedbackEl.innerHTML = '<div class="badge bg-secondary mb-1"><i class="bi bi-list-ul"></i> Betriebseigene History</div>';
    }

    // 3. Autocomplete aus betriebseigener History
    const historyNames = history.map(h => h.name);
    const listId = 'tamg_am_list_' + Math.random().toString(36).slice(2);
    const datalist = document.createElement('datalist');
    datalist.id = listId;
    historyNames.forEach(n => {
        const opt = document.createElement('option');
        opt.value = n;
        datalist.appendChild(opt);
    });
    nameEl.setAttribute('list', listId);
    nameEl.parentNode.appendChild(datalist);

    // 4. Bei Auswahl aus History: Felder vorausfüllen
    function fuellAusHistory(name) {
        const found = history.find(h => h.name.toLowerCase() === name.toLowerCase());
        if (!found) return;
        if (wirkstoffEl && !wirkstoffEl.value) wirkstoffEl.value = found.wirkstoff;
        if (wz_milchEl && !wz_milchEl.value) wz_milchEl.value = found.wz_milch;
        if (wz_fleischEl && !wz_fleischEl.value) wz_fleischEl.value = found.wz_fleisch;
        if (abEl) abEl.checked = found.antibiotikum;
    }

    // 5. KI-Analyse bei Eingabe (nach 1.5s Pause)
    let debounceTimer;
    const SYSTEM_PROMPT = `Du bist ein Veterinär-Assistent für österreichische Landwirte (TAMG-Dokumentation).
Antworte immer auf Deutsch, kurz und präzise.
Du kennst typische Rinderarzneimittel, deren Wirkstoffe und Wartezeiten gemäß EMEA/EMA-Zulassungen.
Wenn du ein Arzneimittel nicht kennst, sage das klar.
Format: Wirkstoff: ... | Wartezeit Milch: X Tage | Wartezeit Fleisch: Y Tage | Antibiotikum: Ja/Nein`;

    nameEl.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        const name = nameEl.value.trim();
        if (!name || name.length < 3) return;

        // Sofort aus History füllen
        fuellAusHistory(name);

        // KI-Analyse nach Pause
        debounceTimer = setTimeout(async () => {
            if (!kiVerfuegbar) return;

            const historyContext = history.length > 0
                ? `Betriebseigene History: ${history.slice(0, 5).map(h => h.name).join(', ')}.`
                : '';

            const kiPrompt = `Arzneimittel: "${name}". ${historyContext}
Was ist der Wirkstoff? Wie lange sind die Wartezeiten (Milch, Fleisch) nach österreichischem/EU-Recht? Ist es ein Antibiotikum?
Antworte im Format: Wirkstoff: ... | Wartezeit Milch: X Tage | Wartezeit Fleisch: Y Tage | Antibiotikum: Ja/Nein`;

            feedbackEl.innerHTML = '<div class="text-muted small"><i class="bi bi-hourglass-split"></i> KI analysiert...</div>';
            const antwort = await BrowserAI.prompt(kiPrompt, SYSTEM_PROMPT);
            if (!antwort) return;

            // Werte aus KI-Antwort parsen und Felder füllen (nur wenn leer)
            const wirkstoffMatch = antwort.match(/Wirkstoff:\s*([^|]+)/i);
            const milchMatch = antwort.match(/Wartezeit Milch:\s*(\d+)/i);
            const fleischMatch = antwort.match(/Wartezeit Fleisch:\s*(\d+)/i);
            const abMatch = antwort.match(/Antibiotikum:\s*(Ja|Nein)/i);

            if (wirkstoffEl && !wirkstoffEl.value && wirkstoffMatch)
                wirkstoffEl.value = wirkstoffMatch[1].trim();
            if (wz_milchEl && !wz_milchEl.value && milchMatch)
                wz_milchEl.value = milchMatch[1];
            if (wz_fleischEl && !wz_fleischEl.value && fleischMatch)
                wz_fleischEl.value = fleischMatch[1];
            if (abEl && abMatch)
                abEl.checked = abMatch[1].toLowerCase() === 'ja';

            feedbackEl.innerHTML = `<div class="alert alert-light border small py-1 px-2 mt-1">
                <i class="bi bi-robot text-success"></i> <strong>KI-Vorschlag:</strong> ${antwort}
                <div class="text-muted" style="font-size:0.75em">Bitte Wartezeiten immer mit Beipackzettel/AGES verifizieren.</div>
            </div>`;
        }, 1500);
    });
}


// ─── Browser AI: MLP Anomalie-Erklärung ──────────────────────────────────────

/**
 * KI-gestützte Erklärung von MLP-Werten in verständlichem Deutsch.
 * Wird aufgerufen wenn alle Werte ausgefüllt sind.
 *
 * @param {object} werte  – { milchmenge, fett, eiweiss, zellzahl, harnstoff, laktNr }
 * @param {string} containerId – Element-ID für Ausgabe
 */
async function erklaereMLPWerte(werte, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const kiVerfuegbar = await BrowserAI.isSupported();
    if (!kiVerfuegbar) {
        // Fallback: regelbasierte Erklärung
        const hinweise = [];
        if (werte.zellzahl >= 400) hinweise.push('Zellzahl kritisch erhöht – Mastitis-Abklärung notwendig!');
        else if (werte.zellzahl >= 200) hinweise.push('Zellzahl erhöht – subklinische Mastitis möglich.');
        if (werte.harnstoff < 150) hinweise.push('Harnstoff zu niedrig – Energie- oder Proteinmangel?');
        else if (werte.harnstoff > 300) hinweise.push('Harnstoff erhöht – Proteinüberversorgung prüfen.');
        const feQ = werte.fett && werte.eiweiss ? werte.fett / werte.eiweiss : null;
        if (feQ && (feQ < 1.1 || feQ > 1.5)) hinweise.push(`F:E-Quotient ${feQ.toFixed(2)} außerhalb Richtwert (1,1–1,5).`);
        if (hinweise.length) {
            container.innerHTML = `<div class="alert alert-warning small py-1 px-2 mt-1">
                <i class="bi bi-exclamation-triangle"></i> ${hinweise.join(' ')}
            </div>`;
        }
        return;
    }

    container.innerHTML = '<div class="text-muted small"><i class="bi bi-hourglass-split"></i> KI wertet aus...</div>';

    const prompt = `MLP-Prüfungswerte einer Milchkuh (Laktation ${werte.laktNr || '?'}):
- Tagesgemelk: ${werte.milchmenge || '?'} kg
- Fett: ${werte.fett || '?'} %
- Eiweiß: ${werte.eiweiss || '?'} %
- Zellzahl: ${werte.zellzahl || '?'} Tsd./ml
- Harnstoff: ${werte.harnstoff || '?'} mg/l

Erkläre diese Werte in 2-3 Sätzen auf Deutsch für einen österreichischen Landwirt.
Weise auf Auffälligkeiten hin und gib eine praktische Empfehlung.`;

    const system = `Du bist ein Milchvieh-Fachberater für österreichische Landwirte.
Antworte immer auf Deutsch, verständlich, ohne Fachjargon.
Richtwerte: Zellzahl < 100 Tsd. = gesund, 100-200 = beobachten, > 200 = Mastitis-Verdacht, > 400 = kritisch.
Harnstoff 150-300 mg/l = optimal. F:E-Quotient 1,1-1,5 = ideal.`;

    const antwort = await BrowserAI.prompt(prompt, system);
    if (antwort) {
        container.innerHTML = `<div class="alert alert-info small py-1 px-2 mt-1">
            <i class="bi bi-robot text-primary"></i> <strong>KI-Auswertung:</strong> ${antwort}
        </div>`;
    }
}


// ─── GVE-Widget ───────────────────────────────────────────────────────────────

/**
 * Lädt und zeigt GVE-Berechnung für das ÖPUL-Weidebuch.
 * @param {string} containerId
 * @param {string} apiUrl
 */
async function ladeGveWidget(containerId, apiUrl) {
    const container = document.getElementById(containerId);
    if (!container) return;

    try {
        const resp = await fetch(apiUrl);
        const data = await resp.json();
        container.innerHTML = `<span class="badge bg-secondary fs-6">${data.gve_total} GVE</span>
            <div class="text-muted small">${data.n_tiere} Tiere</div>`;
    } catch (e) {
        container.innerHTML = '<span class="text-muted small">GVE nicht verfügbar</span>';
    }
}


// ─── Export ───────────────────────────────────────────────────────────────────

window.MilchviehKI = {
    BrowserAI,
    initTierAutocomplete,
    initHarnstoffAmpel,
    initZellzahlAmpel,
    initEcmLive,
    zeigeBrunstPrognose,
    initTamgAssistent,
    erklaereMLPWerte,
    ladeGveWidget,
};
