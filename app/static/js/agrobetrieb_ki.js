/**
 * agrobetrieb_ki.js – Zentrale Browser-KI-Integration für AgroBetrieb
 *
 * Unterstützt Chrome Built-in AI (Gemini Nano, window.LanguageModel / window.ai)
 * mit automatischem Fallback auf regelbasierte JS-Logik.
 *
 * Module:
 *   AgroKI.ai        – Browser-KI-Wrapper (kein API-Key, lokal im Browser)
 *   AgroKI.buch      – Buchhaltung: Kontofindung, Textanalyse, Buchungsvorschlag
 *   AgroKI.lager     – Lager: Mindestbestand-Empfehlung, Einheitenvorschlag
 *   AgroKI.maschinen – Maschinen: Abschreibungsberechnung live
 *   AgroKI.faktura   – Fakturierung: Positionsvorschlag, Zahlungsziel
 *   AgroKI.legehennen– Legehennen: Legeleistung-Ampel, Verlust-Warnung
 *   AgroKI.ui        – Gemeinsame UI-Hilfen (Badge, Feedback, Debounce)
 *
 * Die milchvieh_ki.js bleibt daneben bestehen (wird separat geladen).
 */
'use strict';

// ─────────────────────────────────────────────────────────────────────────────
// AgroKI.ui – UI-Hilfen
// ─────────────────────────────────────────────────────────────────────────────

const _ui = {
    /**
     * Zeigt ein farbiges Feedback unterhalb eines Elements.
     * @param {string} containerId
     * @param {string} klasse  – Bootstrap-Alert-Klasse (success|warning|danger|info)
     * @param {string} html
     */
    feedback(containerId, klasse, html) {
        const el = document.getElementById(containerId);
        if (!el) return;
        el.innerHTML = `<div class="alert alert-${klasse} py-1 px-2 small mt-1 mb-0">${html}</div>`;
    },

    clear(containerId) {
        const el = document.getElementById(containerId);
        if (el) el.innerHTML = '';
    },

    setBadge(containerId, text, klasse = 'secondary') {
        const el = document.getElementById(containerId);
        if (el) el.innerHTML = `<span class="badge bg-${klasse} ms-2">${text}</span>`;
    },

    /**
     * Debounce: Callback erst nach `delay` ms ohne weiteren Aufruf ausführen.
     */
    debounce(fn, delay = 800) {
        let t;
        return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
    },
};


// ─────────────────────────────────────────────────────────────────────────────
// AgroKI.ai – Chrome Built-in AI Wrapper
// ─────────────────────────────────────────────────────────────────────────────

const _ai = {
    _supported: null,
    _session: null,

    async isSupported() {
        if (this._supported !== null) return this._supported;
        try {
            if (window.LanguageModel) {
                const c = await window.LanguageModel.availability();
                this._supported = c === 'available' || c === 'downloadable';
            } else if (window.ai?.languageModel) {
                const c = await window.ai.languageModel.capabilities();
                this._supported = c.available !== 'no';
            } else {
                this._supported = false;
            }
        } catch { this._supported = false; }
        return this._supported;
    },

    async getSession(systemPrompt) {
        // Neue Session wenn systemPrompt sich geändert hat
        if (this._lastSystem !== systemPrompt) {
            this.destroy();
            this._lastSystem = systemPrompt;
        }
        if (this._session) return this._session;
        try {
            if (window.LanguageModel) {
                this._session = await window.LanguageModel.create({ systemPrompt });
            } else if (window.ai?.languageModel) {
                this._session = await window.ai.languageModel.create({ systemPrompt });
            }
        } catch (e) { console.warn('[AgroKI]', e); }
        return this._session;
    },

    async prompt(userPrompt, systemPrompt = 'Du bist ein Assistent für österreichische Landwirte. Antworte kurz und präzise auf Deutsch.') {
        if (!await this.isSupported()) return null;
        try {
            const s = await this.getSession(systemPrompt);
            return s ? await s.prompt(userPrompt) : null;
        } catch (e) { console.warn('[AgroKI]', e); return null; }
    },

    destroy() {
        try { this._session?.destroy(); } catch {}
        this._session = null;
    },
};


// ─────────────────────────────────────────────────────────────────────────────
// AgroKI.buch – Buchhaltung
// ─────────────────────────────────────────────────────────────────────────────

const _buch = {
    /**
     * Initialisiert KI-Buchungsvorschlag im Neue-Buchung-Formular.
     * Bei Eingabe in Buchungstext: KI schlägt Soll/Haben-Konto vor.
     *
     * @param {string} buchungstextId
     * @param {string} sollSelectId
     * @param {string} habenSelectId
     * @param {string} feedbackId
     */
    initBuchungsvorschlag(buchungstextId, sollSelectId, habenSelectId, feedbackId) {
        const textEl = document.getElementById(buchungstextId);
        if (!textEl) return;

        // Konten aus den Select-Elementen extrahieren
        function getKonten(selectId) {
            const sel = document.getElementById(selectId);
            if (!sel) return [];
            return Array.from(sel.options)
                .filter(o => o.value)
                .map(o => ({ id: o.value, text: o.text }));
        }

        const onInput = _ui.debounce(async () => {
            const text = textEl.value.trim();
            if (text.length < 5) { _ui.clear(feedbackId); return; }

            const kontenListe = getKonten(sollSelectId)
                .slice(0, 30)
                .map(k => k.text)
                .join(', ');

            const system = `Du bist ein Buchhalter für österreichische Landwirte (Österreichischer Einheitskontenplan).
Antworte NUR mit: Soll: <Kontonummer> | Haben: <Kontonummer> | Grund: <1 Satz>
Verfügbare Konten (Auswahl): ${kontenListe}`;

            const prompt = `Buchungstext: "${text}". Welche Soll- und Habenkonten sind wahrscheinlich korrekt?`;

            _ui.feedback(feedbackId, 'light', '<i class="bi bi-hourglass-split"></i> KI analysiert Buchungstext...');
            const antwort = await _ai.prompt(prompt, system);
            if (!antwort) { _ui.clear(feedbackId); return; }

            // Kontonummer aus Antwort extrahieren und Select vorbelegen
            const sollMatch = antwort.match(/Soll:\s*(\d+)/i);
            const habenMatch = antwort.match(/Haben:\s*(\d+)/i);

            function selectByKontonr(selectId, nr) {
                const sel = document.getElementById(selectId);
                if (!sel || !nr) return false;
                const opt = Array.from(sel.options).find(o => o.text.startsWith(nr));
                if (opt) { sel.value = opt.value; return true; }
                return false;
            }

            const sollOk = sollMatch && selectByKontonr(sollSelectId, sollMatch[1]);
            const habenOk = habenMatch && selectByKontonr(habenSelectId, habenMatch[1]);

            _ui.feedback(feedbackId, sollOk || habenOk ? 'info' : 'light',
                `<i class="bi bi-robot text-primary"></i> <strong>KI-Vorschlag:</strong> ${antwort}`);
        }, 1200);

        textEl.addEventListener('input', onInput);
    },

    /**
     * Initialisiert die KI-Textanalyse für Bank-Import-Vorschau.
     * Nutzt Browser AI um unbekannte Buchungstexte einem Buchungsschlüssel zuzuordnen.
     *
     * @param {string} btnId         – Button "Texte analysieren"
     * @param {string} feedbackId    – Feedback-Container
     * @param {Array}  schluessel    – [{kuerzel, bezeichnung, buchungstext}, ...]
     * @param {Array}  zeilen        – [{text, betrag, datum, zugewiesen}, ...]
     * @param {function} onZuweisung – Callback(zeilenIdx, kuerzel) wenn KI zuweist
     */
    initBankImportKI(btnId, feedbackId, schluessel, zeilen, onZuweisung) {
        const btn = document.getElementById(btnId);
        if (!btn) return;

        btn.addEventListener('click', async () => {
            if (!await _ai.isSupported()) {
                _ui.feedback(feedbackId, 'warning',
                    '<i class="bi bi-exclamation-triangle"></i> Browser-KI nicht verfügbar. ' +
                    'Nur Chrome 127+ mit aktiviertem Gemini Nano unterstützt.');
                return;
            }

            btn.disabled = true;
            _ui.feedback(feedbackId, 'light', '<i class="bi bi-hourglass-split"></i> KI analysiert Buchungstexte...');

            const schluesselListe = schluessel
                .map(s => `${s.kuerzel}: ${s.bezeichnung}${s.buchungstext ? ' (z.B. ' + s.buchungstext + ')' : ''}`)
                .join('\n');

            const unzugewiesen = zeilen.filter(z => !z.zugewiesen && !z.fehler && !z.ausserhalb_gj);
            let zugewiesen = 0;

            for (let i = 0; i < Math.min(unzugewiesen.length, 20); i++) {
                const z = unzugewiesen[i];
                const prompt = `Buchungstext: "${z.text}" | Betrag: ${z.betrag > 0 ? '+' : ''}${z.betrag} EUR
Weise den Text einem dieser Buchungsschlüssel zu:
${schluesselListe}
Antworte NUR mit dem Kürzel (z.B. "LM") oder "?" wenn keiner passt.`;

                const antwort = await _ai.prompt(prompt,
                    'Du bist Buchhalter für österreichische Landwirte. Ordne Banktexte Buchungsschlüsseln zu. Antworte NUR mit dem Kürzel.');

                if (antwort && antwort.trim() !== '?' && antwort.length <= 10) {
                    const kuerzel = antwort.trim().toUpperCase();
                    if (schluessel.some(s => s.kuerzel === kuerzel)) {
                        onZuweisung(z.idx, kuerzel);
                        zugewiesen++;
                    }
                }
            }

            _ui.feedback(feedbackId, zugewiesen > 0 ? 'success' : 'info',
                `<i class="bi bi-robot"></i> KI hat <strong>${zugewiesen}</strong> von ${unzugewiesen.length} Zeilen zugewiesen.`);
            btn.disabled = false;
        });
    },
};


// ─────────────────────────────────────────────────────────────────────────────
// AgroKI.lager – Lager
// ─────────────────────────────────────────────────────────────────────────────

const _lager = {
    /**
     * Mindestbestand-Empfehlung basierend auf Artikelname + Einheit.
     * Regelbasiert (kein KI nötig) + KI-Erklärung falls verfügbar.
     */
    initMindestbestandHilfe(bezeichnungId, einheitId, mindestbestandId, feedbackId) {
        const bezEl = document.getElementById(bezeichnungId);
        const einheitEl = document.getElementById(einheitId);
        const mbEl = document.getElementById(mindestbestandId);
        if (!bezEl || !mbEl) return;

        // Regelbasierte Empfehlung
        function empfehle(bez, einheit) {
            const b = bez.toLowerCase();
            if (/impf|vakzin|medikament|antibiotika/i.test(b)) return { wert: 5, einheit: 'Dosen', tip: 'Tiermedizin: mind. 5 Einheiten Puffer' };
            if (/futter|schrot|heu|stroh|silage/i.test(b)) return { wert: 500, einheit: 'kg', tip: 'Futtermittel: mind. 500 kg Reserve' };
            if (/diesel|öl|kraft/i.test(b)) return { wert: 100, einheit: 'l', tip: 'Betriebsstoff: mind. 100 l' };
            if (/dünger|kalk/i.test(b)) return { wert: 200, einheit: 'kg', tip: 'Düngemittel: mind. 200 kg' };
            if (/sperma|besamung/i.test(b)) return { wert: 3, einheit: 'Portionen', tip: 'Besamung: mind. 3 Portionen' };
            if (/desinfektion|reinig/i.test(b)) return { wert: 10, einheit: 'l', tip: 'Reinigung: mind. 10 l' };
            return null;
        }

        const onInput = _ui.debounce(async () => {
            const bez = bezEl.value.trim();
            if (!bez) return;
            const einheit = einheitEl?.value || 'Stk';
            const r = empfehle(bez, einheit);
            if (r && !mbEl.value) {
                mbEl.value = r.wert;
                _ui.feedback(feedbackId, 'info',
                    `<i class="bi bi-lightbulb"></i> Empfehlung: ${r.wert} ${r.einheit} Mindestbestand. ${r.tip}`);
            } else if (!r && await _ai.isSupported()) {
                const antwort = await _ai.prompt(
                    `Artikel: "${bez}", Einheit: ${einheit}. Was ist ein sinnvoller Mindestbestand für einen österreichischen Landwirtschaftsbetrieb? Antworte mit: Zahl Einheit – Begründung (1 Satz).`,
                    'Du bist Lagerexperte für landwirtschaftliche Betriebe in Österreich. Antworte kurz auf Deutsch.'
                );
                if (antwort) _ui.feedback(feedbackId, 'info', `<i class="bi bi-robot"></i> ${antwort}`);
            }
        }, 1000);

        bezEl.addEventListener('input', onInput);
        if (einheitEl) einheitEl.addEventListener('change', onInput);
    },
};


// ─────────────────────────────────────────────────────────────────────────────
// AgroKI.maschinen – Maschinen
// ─────────────────────────────────────────────────────────────────────────────

const _maschinen = {
    /**
     * Zeigt Abschreibungsberechnung live (lineare AfA).
     * Österreich: Traktor ~15 J, PKW ~8 J, Mähdrescher ~15 J, etc.
     */
    initAbschreibung(anschaffungId, baujahrId, feedbackId) {
        const anschaffungEl = document.getElementById(anschaffungId);
        const baujahrEl = document.getElementById(baujahrId);
        if (!anschaffungEl || !feedbackId) return;

        function berechne() {
            const wert = parseFloat(anschaffungEl.value);
            const baujahr = parseInt(baujahrEl?.value);
            if (!wert || wert <= 0) { _ui.clear(feedbackId); return; }

            const aktuellesJahr = new Date().getFullYear();
            // Nutzungsdauer ermitteln (aus Maschinenname wenn möglich)
            const nameEl = document.getElementById('name');
            const name = nameEl?.value?.toLowerCase() || '';

            let nd = 10; // Standard 10 Jahre
            if (/traktor|schlepper|trecker/i.test(name)) nd = 15;
            else if (/mähdrescher|harvester/i.test(name)) nd = 15;
            else if (/pkw|auto|transporter/i.test(name)) nd = 8;
            else if (/pumpe|motor/i.test(name)) nd = 10;
            else if (/computer|software|it/i.test(name)) nd = 5;

            const jahrliche_afa = wert / nd;
            const alter = baujahr ? aktuellesJahr - baujahr : null;
            const restbuchwert = baujahr
                ? Math.max(0, wert - (jahrliche_afa * Math.min(alter, nd)))
                : null;

            let html = `<i class="bi bi-calculator"></i> <strong>AfA (linear):</strong> ` +
                `${jahrliche_afa.toLocaleString('de-AT', { style: 'currency', currency: 'EUR' })}/Jahr ` +
                `bei ${nd} Jahren Nutzungsdauer`;
            if (restbuchwert !== null) {
                html += ` | <strong>Restbuchwert ca.:</strong> ` +
                    `${restbuchwert.toLocaleString('de-AT', { style: 'currency', currency: 'EUR' })}`;
            }
            _ui.feedback(feedbackId, 'light', html);
        }

        anschaffungEl.addEventListener('input', berechne);
        if (baujahrEl) baujahrEl.addEventListener('input', berechne);
        if (document.getElementById('name')) {
            document.getElementById('name').addEventListener('input', _ui.debounce(berechne, 500));
        }
    },

    /**
     * KI-Wartungshinweis basierend auf Maschinenname.
     */
    initWartungshinweis(nameId, feedbackId) {
        const nameEl = document.getElementById(nameId);
        if (!nameEl) return;

        const onInput = _ui.debounce(async () => {
            const name = nameEl.value.trim();
            if (name.length < 4) return;
            if (!await _ai.isSupported()) return;

            const antwort = await _ai.prompt(
                `Maschine/Gerät: "${name}". Welche typischen Wartungsintervalle und Inspektionspunkte gibt es für österreichische Landwirte? Antworte in 2 Sätzen.`,
                'Du bist Landmaschinenmechaniker und Berater für österreichische Bauern. Antworte auf Deutsch, kurz und praktisch.'
            );
            if (antwort) _ui.feedback(feedbackId, 'light',
                `<i class="bi bi-robot"></i> <strong>Wartungshinweis:</strong> ${antwort}`);
        }, 1500);

        nameEl.addEventListener('input', onInput);
    },
};


// ─────────────────────────────────────────────────────────────────────────────
// AgroKI.faktura – Fakturierung
// ─────────────────────────────────────────────────────────────────────────────

const _faktura = {
    /**
     * KI-Positionsvorschlag: Tippt Benutzer einen Betreff, schlägt KI typische
     * Positionen für Landwirtschaft vor.
     */
    initPositionsvorschlag(betreffId, addPositionFn, feedbackId) {
        const betreffEl = document.getElementById(betreffId);
        if (!betreffEl) return;

        const onInput = _ui.debounce(async () => {
            const betreff = betreffEl.value.trim();
            if (betreff.length < 6 || !await _ai.isSupported()) return;

            const antwort = await _ai.prompt(
                `Rechnungsbetreff: "${betreff}". Schlage 2-3 typische Rechnungspositionen für eine österreichische Landwirtschaftsrechnung vor.
Format pro Zeile: Bezeichnung | Menge | Einheit | Einzelpreis EUR`,
                'Du kennst österreichische Landwirtschaftspreise 2024-2026. Antworte im exakten Format, keine Erklärungen.'
            );
            if (!antwort) return;

            const zeilen = antwort.split('\n').filter(z => z.includes('|'));
            if (!zeilen.length) return;

            _ui.feedback(feedbackId, 'info',
                `<i class="bi bi-robot"></i> <strong>KI-Vorschlag für "${betreff}":</strong> ` +
                `<button class="btn btn-sm btn-outline-primary ms-2" id="ki_pos_uebernehmen">Positionen übernehmen</button>` +
                `<div class="mt-1 small text-muted">${zeilen.map(z => z.trim()).join('<br>')}</div>`);

            document.getElementById('ki_pos_uebernehmen')?.addEventListener('click', () => {
                zeilen.forEach(z => {
                    const parts = z.split('|').map(p => p.trim());
                    if (parts.length >= 2) {
                        addPositionFn({
                            bezeichnung: parts[0] || '',
                            menge: parts[1] || '1',
                            einheit: parts[2] || 'Stk',
                            einzelpreis: parts[3]?.replace(/[^0-9.,]/g, '') || '',
                        });
                    }
                });
                _ui.clear(feedbackId);
            });
        }, 1500);

        betreffEl.addEventListener('input', onInput);
    },

    /**
     * Zahlungsziel-Ampel: Zeigt wie viele Tage Zahlungsziel gesetzt sind.
     */
    initZahlungszielAmpel(datumId, faelligId, feedbackId) {
        const datumEl = document.getElementById(datumId);
        const faelligEl = document.getElementById(faelligId);
        if (!datumEl || !faelligEl) return;

        function berechne() {
            const d = datumEl.value ? new Date(datumEl.value) : null;
            const f = faelligEl.value ? new Date(faelligEl.value) : null;
            if (!d || !f) return;
            const tage = Math.round((f - d) / 86400000);
            if (tage < 0) {
                _ui.feedback(feedbackId, 'danger', `⛔ Fälligkeitsdatum liegt vor Rechnungsdatum!`);
            } else if (tage === 0) {
                _ui.feedback(feedbackId, 'warning', `⚠️ Sofortige Zahlung (0 Tage Zahlungsziel)`);
            } else if (tage <= 14) {
                _ui.feedback(feedbackId, 'success', `✅ ${tage} Tage Zahlungsziel – kurzes Ziel (Standard: 14–30 Tage)`);
            } else if (tage <= 30) {
                _ui.feedback(feedbackId, 'success', `✅ ${tage} Tage Zahlungsziel`);
            } else {
                _ui.feedback(feedbackId, 'warning', `⚠️ ${tage} Tage – langes Zahlungsziel (Liquiditätsrisiko)`);
            }
        }

        datumEl.addEventListener('change', berechne);
        faelligEl.addEventListener('change', berechne);
        berechne();
    },
};


// ─────────────────────────────────────────────────────────────────────────────
// AgroKI.legehennen – Legehennen Stallbuch
// ─────────────────────────────────────────────────────────────────────────────

const _legehennen = {
    /**
     * Live-Legeleistungs-Ampel und Kennzahlen.
     * Zielwert Hennenleistung: ≥ 90% (Spitzenleistung), 85-90% gut, < 80% kritisch
     */
    initLegeleistungAmpel(eierGesamtId, tierbestandId, feedbackId) {
        const eierEl = document.getElementById(eierGesamtId);
        const bestandEl = document.getElementById(tierbestandId);
        if (!eierEl || !bestandEl) return;

        function berechne() {
            const eier = parseInt(eierEl.value) || 0;
            const bestand = parseInt(bestandEl.value) || 0;
            if (!eier || !bestand) { _ui.clear(feedbackId); return; }

            const ll = (eier / bestand * 100).toFixed(1);
            let klasse, text;
            if (ll >= 90) { klasse = 'success'; text = `✅ ${ll}% Legeleistung – ausgezeichnet!`; }
            else if (ll >= 85) { klasse = 'success'; text = `✅ ${ll}% Legeleistung – gut`; }
            else if (ll >= 75) { klasse = 'warning'; text = `⚠️ ${ll}% Legeleistung – beobachten (Ziel ≥ 85%)`; }
            else { klasse = 'danger'; text = `⛔ ${ll}% Legeleistung – kritisch! Ursache abklären`; }

            _ui.feedback(feedbackId, klasse, text);
        }

        eierEl.addEventListener('input', berechne);
        bestandEl.addEventListener('input', berechne);
    },

    /**
     * Verlust-Warnung + KI-Erklärung wenn Verluste ungewöhnlich hoch.
     */
    initVerlustWarnung(verlustId, bestandId, ursacheId, feedbackId) {
        const verlustEl = document.getElementById(verlustId);
        const bestandEl = document.getElementById(bestandId);
        const ursacheEl = document.getElementById(ursacheId);
        if (!verlustEl || !bestandEl) return;

        const onInput = _ui.debounce(async () => {
            const verlust = parseInt(verlustEl.value) || 0;
            const bestand = parseInt(bestandEl.value) || 1;
            if (!verlust) { _ui.clear(feedbackId); return; }

            const proz = (verlust / bestand * 100).toFixed(2);

            if (proz >= 0.5) {
                let html = `⛔ ${proz}% Tagesverlust – deutlich erhöht! Normwert: &lt; 0,2%/Tag.`;
                _ui.feedback(feedbackId, 'danger', html);

                if (await _ai.isSupported()) {
                    const ursache = ursacheEl?.value || '';
                    const antwort = await _ai.prompt(
                        `Legehennenherde: ${verlust} Verluste bei ${bestand} Tieren (${proz}%).${ursache ? ' Ursache: ' + ursache : ''} Was sind typische Ursachen und was sollte ein Landwirt jetzt prüfen?`,
                        'Du bist Geflügelberater für österreichische Betriebe. Antworte auf Deutsch, praktisch und knapp.'
                    );
                    if (antwort) _ui.feedback(feedbackId, 'danger', `⛔ ${proz}% Verlust – <i class="bi bi-robot"></i> ${antwort}`);
                }
            } else if (proz >= 0.2) {
                _ui.feedback(feedbackId, 'warning', `⚠️ ${proz}% Tagesverlust – leicht erhöht (Normwert: &lt; 0,2%/Tag)`);
            } else {
                _ui.feedback(feedbackId, 'success', `✅ ${proz}% Tagesverlust – normal`);
            }
        }, 800);

        verlustEl.addEventListener('input', onInput);
        bestandEl.addEventListener('input', onInput);
    },

    /**
     * Stallklima-Warnung: Temperatur + Luftfeuchtigkeit.
     * Optimum Legehenne: 15–25°C, 60–70% rel. Feuchte
     */
    initKlimaWarnung(tempId, luftId, feedbackId) {
        const tempEl = document.getElementById(tempId);
        const luftEl = document.getElementById(luftId);
        if (!tempEl) return;

        function berechne() {
            const temp = parseFloat(tempEl.value);
            const luft = parseFloat(luftEl?.value);
            const hinweise = [];

            if (!isNaN(temp)) {
                if (temp > 28) hinweise.push(`🌡️ ${temp}°C – Hitzestress! Kühlung und mehr Wasser!`);
                else if (temp > 25) hinweise.push(`⚠️ ${temp}°C – warm (Ziel: 15–25°C)`);
                else if (temp < 10) hinweise.push(`🥶 ${temp}°C – zu kalt (Legeleistung sinkt)`);
            }
            if (!isNaN(luft)) {
                if (luft > 80) hinweise.push(`💧 ${luft}% Luftfeuchte – zu hoch (Krankheitsrisiko)`);
                else if (luft < 50) hinweise.push(`🌵 ${luft}% Luftfeuchte – zu trocken`);
            }

            if (hinweise.length) {
                _ui.feedback(feedbackId, hinweise.some(h => h.includes('🌡️') || h.includes('🥶')) ? 'danger' : 'warning',
                    hinweise.join(' | '));
            } else if (!isNaN(temp) || !isNaN(luft)) {
                _ui.feedback(feedbackId, 'success', '✅ Stallklima im Normbereich');
            }
        }

        tempEl.addEventListener('input', berechne);
        if (luftEl) luftEl.addEventListener('input', berechne);
    },

    /**
     * Erzeugercode-Validator (AT-Format: Haltungsform-Land-Betriebsnr)
     * Format: [1-4]-AT-[7-stellige Zahl]
     */
    initErzeugerCodeValidator(erzeugerCodeId, feedbackId) {
        const el = document.getElementById(erzeugerCodeId);
        if (!el) return;

        el.addEventListener('input', () => {
            const val = el.value.trim();
            if (!val) { _ui.clear(feedbackId); return; }

            const match = val.match(/^([1-4])-([A-Z]{2})-(\d+)$/);
            if (!match) {
                _ui.feedback(feedbackId, 'warning',
                    `⚠️ Format: Haltung(1-4)-Land(AT)-Betriebsnr | Beispiel: 2-AT-1234567`);
                return;
            }

            const haltung = { '1': 'Käfig', '2': 'Bodenhaltung', '3': 'Freilandhaltung', '4': 'Bio' };
            _ui.feedback(feedbackId, 'success',
                `✅ Gültiger Erzeugercode | ${haltung[match[1]] || match[1]} | Land: ${match[2]}`);
        });
    },
};


// ─────────────────────────────────────────────────────────────────────────────
// AgroKI.betrieb – Betriebsformular-Hilfen
// ─────────────────────────────────────────────────────────────────────────────

const _betrieb = {
    /**
     * UID-Nummern-Validator (AT: ATU12345678, DE: DE123456789, ...)
     */
    initUidValidator(uidInputId, feedbackId) {
        const el = document.getElementById(uidInputId);
        if (!el) return;

        const muster = {
            AT: /^ATU\d{8}$/,
            DE: /^DE\d{9}$/,
            CH: /^CHE-\d{3}\.\d{3}\.\d{3}/,
        };

        el.addEventListener('input', () => {
            const val = el.value.trim().toUpperCase();
            if (!val) { _ui.clear(feedbackId); return; }

            const land = val.substring(0, 2);
            if (muster[land] && muster[land].test(val)) {
                _ui.feedback(feedbackId, 'success', `✅ Gültige UID-Nummer (${land})`);
            } else if (muster[land]) {
                const beispiel = { AT: 'ATU12345678', DE: 'DE123456789', CH: 'CHE-123.456.789' };
                _ui.feedback(feedbackId, 'warning', `⚠️ Format für ${land}: ${beispiel[land]}`);
            }
        });
    },
};


// ─────────────────────────────────────────────────────────────────────────────
// AgroKI – Globale Status-Anzeige in der Navbar
// ─────────────────────────────────────────────────────────────────────────────

async function _initKIStatusBadge() {
    const supported = await _ai.isSupported();
    // Badge in der Navbar einfügen (nach User-Menü)
    const navbar = document.querySelector('.navbar-nav.ms-auto');
    if (!navbar) return;

    const li = document.createElement('li');
    li.className = 'nav-item d-flex align-items-center px-2';
    if (supported) {
        li.innerHTML = `<span class="badge bg-success" title="Chrome Gemini Nano (lokal, kein API-Key)" style="font-size:0.7em">
            <i class="bi bi-robot"></i> KI aktiv
        </span>`;
    } else {
        li.innerHTML = `<span class="badge bg-secondary" title="Browser-KI nicht verfügbar (nur Chrome 127+ mit Gemini Nano)" style="font-size:0.7em;opacity:0.6">
            <i class="bi bi-robot"></i> KI inaktiv
        </span>`;
    }
    navbar.insertBefore(li, navbar.firstChild);
}


// ─────────────────────────────────────────────────────────────────────────────
// Public API
// ─────────────────────────────────────────────────────────────────────────────

window.AgroKI = {
    ai:         _ai,
    ui:         _ui,
    buch:       _buch,
    lager:      _lager,
    maschinen:  _maschinen,
    faktura:    _faktura,
    legehennen: _legehennen,
    betrieb:    _betrieb,
    initStatusBadge: _initKIStatusBadge,
};

// Status-Badge automatisch beim Laden aller Seiten einblenden
document.addEventListener('DOMContentLoaded', _initKIStatusBadge);
