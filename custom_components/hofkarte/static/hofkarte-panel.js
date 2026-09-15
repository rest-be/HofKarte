/**
 * HofKarte-Verwaltungspanel.
 *
 * Drei Ansichten: Liste (list), Bearbeiten (editor), Details (detail,
 * read-only). Kommuniziert ausschliesslich über die bestehenden
 * WebSocket-Befehle hofkarte/management/list|save|delete – keine neuen
 * Backend-Endpunkte nötig (die Detailansicht liest nur bereits
 * geladene Daten).
 *
 * LV95-Koordinaten: Das Backend/Datenmodell speichert weiterhin WGS84
 * (latitude/longitude), siehe custom_components/hofkarte/lv95.py für
 * die Begründung. Dieses Panel zeigt/erfasst LV95 und rechnet lokal um.
 * Die Umrechnungsformeln sind ein bewusstes, dokumentiertes Duplikat der
 * Python-Referenzimplementierung (lv95.py) - Browser und Backend teilen
 * keine gemeinsame Laufzeitumgebung, ein Build-Schritt wäre eine neue,
 * hier nicht gewünschte Abhängigkeit.
 */

// --- LV95 <-> WGS84 (swisstopo-Näherungsformeln, siehe lv95.py) -----------

function wgs84ToLv95(lat, lon) {
  const phi = (lat * 3600 - 169028.66) / 10000;
  const lam = (lon * 3600 - 26782.5) / 10000;
  const e = 2600072.37 + 211455.93 * lam - 10938.51 * lam * phi - 0.36 * lam * phi ** 2 - 44.54 * lam ** 3;
  const n = 1200147.07 + 308807.95 * phi + 3745.25 * lam ** 2 + 76.63 * phi ** 2 - 194.56 * lam ** 2 * phi + 119.79 * phi ** 3;
  return { easting: e, northing: n };
}

function lv95ToWgs84(easting, northing) {
  const y = (easting - 2600000) / 1000000;
  const x = (northing - 1200000) / 1000000;
  const lam = 2.6779094 + 4.728982 * y + 0.791484 * y * x + 0.1306 * y * x ** 2 - 0.0436 * y ** 3;
  const phi = 16.9023892 + 3.238272 * x - 0.270978 * y ** 2 - 0.002528 * x ** 2 - 0.0447 * y ** 2 * x - 0.0140 * x ** 3;
  return { lat: (phi * 100) / 36, lon: (lam * 100) / 36 };
}

const LV95_BOUNDS = { eMin: 2485000, eMax: 2834000, nMin: 1075000, nMax: 1296000 };
function isValidLv95(e, n) {
  return e >= LV95_BOUNDS.eMin && e <= LV95_BOUNDS.eMax && n >= LV95_BOUNDS.nMin && n <= LV95_BOUNDS.nMax;
}

const WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"];

// Konvention (bereits an anderer Stelle im Projekt verwendet, siehe
// Testsuite): "24 Stunden geöffnet" wird als einzelnes Intervall
// 00:00-23:59 gespeichert. Kein neues Datenmodell-Feld nötig.
const FULL_DAY = { beginn: "00:00", ende: "23:59" };
function isFullDay(row) { return row.beginn === FULL_DAY.beginn && row.ende === FULL_DAY.ende; }

class HofkartePanel extends HTMLElement {
  constructor() {
    super();
    this.hass = null;
    this.items = [];
    this.editing = null;
    this.viewing = null;
    this.message = "";
    this.error = "";
    this.showLv95Info = false;
    this.attachShadow({ mode: "open" });
  }

  set hass(value) {
    this._hass = value;
    if (this.isConnected && !this._loaded) this.load();
  }
  get hass() { return this._hass; }

  connectedCallback() { this.render(); if (this.hass) this.load(); }

  async call(type, payload = {}) {
    return this.hass.connection.sendMessagePromise({ type, ...payload });
  }

  async load() {
    if (!this.hass || this._loading) return;
    this._loading = true;
    try {
      const result = await this.call("hofkarte/management/list");
      this.items = result.hoflaeden || [];
      this._loaded = true;
      this.message = "";
      this.error = "";
      // Detailansicht mit aktualisierten Daten synchron halten, falls
      // gerade ein Hofladen betrachtet wird (z. B. nach externer Änderung).
      if (this.viewing) {
        const aktuell = this.items.find((x) => x.id === this.viewing.id);
        this.viewing = aktuell || null;
      }
      this.render();
    } catch (err) {
      this.error = err?.message || "Die Hofläden konnten nicht geladen werden.";
      this.render();
    } finally { this._loading = false; }
  }

  empty() {
    return { id: "", name: "", beschreibung: "", adresse: "", plz: "", ort: "", land: "", website: "", latitude: "", longitude: "", oeffnungszeiten: [], sonderoeffnungszeiten: [], produkte: [], kategorien: [], zahlungsarten: [], verkaufsarten: [], merkmale: [], bilder: [] };
  }

  clone(item) { return JSON.parse(JSON.stringify(item)); }

  async save() {
    const data = this.formData();
    try {
      this.validate(data);
      await this.call("hofkarte/management/save", { hofladen: data });
      this.message = "Änderungen gespeichert.";
      this.editing = null;
      await this.load();
    } catch (err) { this.error = err?.message || "Speichern fehlgeschlagen."; this.render(); }
  }

  validate(d) {
    if (!d.name.trim()) throw new Error("Name darf nicht leer sein.");
    if (d.latitude !== null && d.latitude !== "" && (d.latitude < -90 || d.latitude > 90)) throw new Error("Die umgerechnete Latitude liegt ausserhalb des gültigen Bereichs (-90 bis 90). Bitte LV95-Werte prüfen.");
    if (d.longitude !== null && d.longitude !== "" && (d.longitude < -180 || d.longitude > 180)) throw new Error("Die umgerechnete Longitude liegt ausserhalb des gültigen Bereichs (-180 bis 180). Bitte LV95-Werte prüfen.");
    for (const row of d.oeffnungszeiten) if (!row.beginn || !row.ende || row.beginn === row.ende) throw new Error("Öffnungszeiten enthalten ungültige oder unvollständige Zeiten.");
    if (d.website && d.website.trim() && !this.isPlausibleUrl(d.website.trim())) throw new Error("Die Webseite muss eine gültige http(s)-Adresse sein (z. B. https://www.beispiel.ch).");
  }

  isPlausibleUrl(value) {
    try {
      const url = new URL(value.match(/^https?:\/\//i) ? value : `https://${value}`);
      return url.protocol === "http:" || url.protocol === "https:";
    } catch { return false; }
  }

  /** LV95-Eingabefelder auslesen und für die Speicherung nach WGS84
   * umrechnen. Wurden die Felder gegenüber dem beim Öffnen des Formulars
   * berechneten Ausgangswert NICHT verändert, werden die ursprünglich
   * gespeicherten WGS84-Werte unverändert zurückgegeben (kein
   * "stilles" Neu-Runden bereits vorhandener Koordinaten bei jedem
   * Speichern, siehe lv95.py).
   */
  resolveCoordinates(f, original) {
    const eastingRaw = f.elements["lv95_easting"]?.value ?? "";
    const northingRaw = f.elements["lv95_northing"]?.value ?? "";
    if (eastingRaw === "" && northingRaw === "") return { latitude: null, longitude: null };

    const easting = Number(eastingRaw);
    const northing = Number(northingRaw);
    if (!Number.isFinite(easting) || !Number.isFinite(northing)) {
      throw new Error("LV95-Koordinaten müssen Zahlen sein.");
    }
    if (!isValidLv95(easting, northing)) {
      throw new Error("Die LV95-Koordinaten liegen ausserhalb des plausiblen Bereichs für die Schweiz/Liechtenstein (E: 2'485'000–2'834'000, N: 1'075'000–1'296'000). Bitte prüfen, ob evtl. E/N vertauscht oder WGS84-Werte eingegeben wurden.");
    }

    if (
      original?.latitude != null && original?.longitude != null &&
      Number(f.elements["lv95_original_easting"]?.value) === easting &&
      Number(f.elements["lv95_original_northing"]?.value) === northing
    ) {
      // Unverändert: ursprüngliche WGS84-Werte beibehalten (kein
      // zusätzlicher Rundungsschritt ohne Not).
      return { latitude: original.latitude, longitude: original.longitude };
    }

    const { lat, lon } = lv95ToWgs84(easting, northing);
    return { latitude: lat, longitude: lon };
  }

  /** Gemeinsame Kartenlogik für "Bearbeiten" und "Details" (siehe
   * Anforderung: identisches Verhalten in beiden Ansichten).
   *
   * map.geo.admin.ch (amtlicher Schweizer Kartendienst) akzeptiert
   * LV95-Koordinaten nativ über den URL-Parameter "center" – es ist
   * **keine** Umwandlung nach WGS84/EPSG:4326 nötig (bereits vorhandene
   * LV95-Werte werden unverändert in die URL übernommen). Öffnet in
   * einem neuen Tab, verändert keine Daten (rein lesender externer
   * Link), keine neue Abhängigkeit.
   */
  mapUrl(easting, northing) {
    const e = Math.round(easting);
    const n = Math.round(northing);
    return `https://map.geo.admin.ch/?center=${e},${n}&z=10&crosshair=marker`;
  }

  /** Karten-Button (bzw. deaktivierter Platzhalter ohne gültige
   * Koordinaten) – identische Darstellung in Bearbeiten und Details. */
  mapButton(lv95) {
    const gueltig = lv95 && isValidLv95(lv95.easting, lv95.northing);
    if (!gueltig) {
      return `<button type="button" class="map-btn" disabled title="Keine gültigen Koordinaten hinterlegt">🗺️ Auf Karte anzeigen</button>`;
    }
    const url = this.mapUrl(lv95.easting, lv95.northing);
    return `<a class="map-btn" href="${this.escAttr(url)}" target="_blank" rel="noopener noreferrer" title="Standort auf map.geo.admin.ch anzeigen (neuer Tab)">🗺️ Auf Karte anzeigen</a>`;
  }

  formData() {
    const f = this.shadowRoot.querySelector("form");
    const value = (name) => f.elements[name]?.value ?? "";
    const data = this.clone(this.editing || this.empty());
    data.name = value("name"); data.beschreibung = value("beschreibung") || null;
    data.adresse = value("adresse") || null; data.plz = value("plz") || null;
    data.ort = value("ort") || null; data.land = value("land") || null;
    data.website = value("website") || null;
    const koordinaten = this.resolveCoordinates(f, this.editing);
    data.latitude = koordinaten.latitude; data.longitude = koordinaten.longitude;
    data.oeffnungszeiten = this.readOpeningHours(f);
    data.sonderoeffnungszeiten = [...f.querySelectorAll("[data-special]")].map(row => ({ datum_von: row.querySelector("[name=datum_von]").value, datum_bis: row.querySelector("[name=datum_bis]").value, geschlossen: row.querySelector("[name=geschlossen]").checked, beginn: row.querySelector("[name=beginn]").value || null, ende: row.querySelector("[name=ende]").value || null }));
    for (const field of ["kategorien", "zahlungsarten", "verkaufsarten", "merkmale"]) data[field] = this.lines(f.elements[field]?.value);
    data.produkte = this.products(f.elements.produkte?.value);
    return data;
  }

  /** Öffnungszeiten aus den pro Wochentag gruppierten Eingabebereichen
   * auslesen (Modus "geschlossen"/"24h"/"zeiten" je Tag). */
  readOpeningHours(f) {
    const result = [];
    for (let day = 1; day <= 7; day++) {
      const modus = f.querySelector(`input[name="day_mode_${day}"]:checked`)?.value || "geschlossen";
      if (modus === "geschlossen") continue;
      if (modus === "24h") { result.push({ wochentag: day, beginn: FULL_DAY.beginn, ende: FULL_DAY.ende }); continue; }
      f.querySelectorAll(`[data-day-interval="${day}"]`).forEach((row) => {
        const beginn = row.querySelector("[name=beginn]").value;
        const ende = row.querySelector("[name=ende]").value;
        if (beginn && ende) result.push({ wochentag: day, beginn, ende });
      });
    }
    return result;
  }

  lines(text) { return String(text || "").split("\n").map(x => x.trim()).filter(Boolean).map(name => ({ id: this.slug(name), name })); }
  products(text) { return String(text || "").split("\n").map(x => x.trim()).filter(Boolean).map(line => { const [name, cats = ""] = line.split("|"); return { id: this.slug(name), name: name.trim(), kategorie_ids: cats.split(",").map(x => this.slug(x)).filter(Boolean) }; }); }
  slug(s) { return String(s).toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "eintrag"; }

  async remove(id) {
    if (!confirm("Möchtest du diesen Hofladen wirklich löschen?")) return;
    try { await this.call("hofkarte/management/delete", { hofladen_id: id }); this.message = "Hofladen gelöscht."; this.viewing = null; await this.load(); }
    catch (err) { this.error = err?.message || "Löschen fehlgeschlagen."; this.render(); }
  }

  start(item = null) { this.error = ""; this.viewing = null; this.showLv95Info = false; this.editing = item ? this.clone(item) : this.empty(); this.render(); }
  cancel() { this.editing = null; this.error = ""; this.render(); }
  view(item) { this.error = ""; this.editing = null; this.viewing = item; this.render(); }
  closeView() { this.viewing = null; this.render(); }

  // --- Rendering -----------------------------------------------------

  render() {
    if (!this.shadowRoot) return;
    this.shadowRoot.innerHTML = `<style>${this.styles()}</style><main>${this.currentView()}</main>`;
    this.bind();
  }

  currentView() {
    if (this.editing) return this.editor();
    if (this.viewing) return this.detail();
    return this.list();
  }

  styles() {
    return `
      :host{display:block;color:var(--primary-text-color);background:var(--primary-background-color);min-height:100%;font-family:var(--paper-font-body1_-_font-family,Roboto,sans-serif)}
      main{max-width:1200px;margin:0 auto;padding:24px}
      .top{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
      .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-top:20px}
      .card{background:var(--ha-card-background,var(--card-background-color));border-radius:12px;padding:16px;box-shadow:var(--ha-card-box-shadow,0 1px 3px #0002)}
      .card h2{margin-top:0}
      .actions{display:flex;gap:8px;justify-content:flex-end;margin-top:16px;flex-wrap:wrap}
      button{border:0;border-radius:8px;padding:9px 14px;background:var(--primary-color);color:var(--text-primary-color,#fff);cursor:pointer;font-size:.95em}
      button.secondary{background:var(--secondary-background-color);color:var(--primary-text-color)}
      button.danger{background:var(--error-color,#db4437);color:#fff}
      button.icon{padding:6px 10px;border-radius:50%;line-height:1;font-size:1.1em}
      label{display:block;margin:10px 0 5px;font-size:.9em}
      .fields{display:grid;grid-template-columns:1fr;gap:8px}
      .field-row{display:grid;grid-template-columns:1fr;gap:8px}
      .field-row.two{grid-template-columns:1fr 1fr}
      .field-row label{margin:0}
      input,textarea,select{box-sizing:border-box;width:100%;padding:9px;border:1px solid var(--divider-color);border-radius:7px;background:var(--primary-background-color);color:var(--primary-text-color);font-size:.95em}
      textarea{min-height:100px}
      @media(max-width:700px){main{padding:12px}.field-row.two{grid-template-columns:1fr}.grid{grid-template-columns:1fr}}
      .coord-row{display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap}
      .coord-row .field-row{flex:1;min-width:160px}
      .info-btn{flex:0 0 auto;width:34px;height:34px;border-radius:50%;background:var(--info-color,#2196f3);color:#fff;font-weight:bold;box-shadow:0 1px 3px #0003;border:2px solid transparent}
      .info-btn:hover,.info-btn:focus-visible{background:var(--info-color,#1976d2);outline:2px solid var(--info-color,#2196f3);outline-offset:2px}
      .map-btn{flex:0 0 auto;display:inline-flex;align-items:center;gap:6px;height:34px;padding:0 14px;border-radius:8px;background:var(--secondary-background-color);color:var(--primary-text-color);text-decoration:none;font-size:.95em;box-sizing:border-box}
      .map-btn[disabled],.map-btn.disabled{opacity:.5;cursor:not-allowed;pointer-events:none}
      .coord-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:2px}
      .info-box{margin-top:8px;padding:12px 14px;border-radius:8px;background:var(--secondary-background-color);font-size:.9em;line-height:1.5}
      .info-box code{background:var(--primary-background-color);padding:1px 5px;border-radius:4px}
      .day-block{border:1px solid var(--divider-color);border-radius:10px;padding:10px 12px;margin:8px 0}
      .day-block .day-title{font-weight:600;margin-bottom:6px}
      .day-mode{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:8px;font-size:.9em}
      .day-mode label{display:flex;align-items:center;gap:5px;margin:0;font-weight:normal}
      .interval-row{display:grid;grid-template-columns:1fr 1fr auto;gap:8px;align-items:end;margin:6px 0}
      .special{display:grid;grid-template-columns:1fr 1fr 1fr 1fr auto;gap:8px;align-items:end;margin:8px 0}
      @media(max-width:700px){.special{grid-template-columns:1fr 1fr}}
      .notice{padding:10px;margin:12px 0;border-radius:8px;background:var(--info-color,#2196f3);color:white}
      .notice.error{background:var(--error-color,#db4437)}
      .muted{color:var(--secondary-text-color)}
      h1,h2{font-weight:500}
      .pill{display:inline-block;padding:3px 10px;border-radius:12px;background:var(--secondary-background-color);margin:2px 4px 2px 0;font-size:.9em}
      .day{font-weight:500}
      .detail-section{margin-bottom:20px}
      .detail-section h3{margin:0 0 8px;font-size:1em;text-transform:uppercase;letter-spacing:.03em;color:var(--secondary-text-color)}
      .opening-table{width:100%;border-collapse:collapse}
      .opening-table td{padding:4px 8px 4px 0;vertical-align:top}
      .opening-table td:first-child{font-weight:500;width:120px}
      a.website-link{color:var(--primary-color);text-decoration:none;font-weight:500}
      a.website-link:hover{text-decoration:underline}
      .thumbs{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}
      .thumbs img{width:96px;height:96px;object-fit:cover;border-radius:8px}
    `;
  }

  // --- Liste -----------------------------------------------------------

  list() {
    return `<div class="top"><div><h1>HofKarte</h1><div class="muted">Hofläden verwalten</div></div><button data-new>+ Neuer Hofladen</button></div>${this.message ? `<div class="notice">${this.esc(this.message)}</div>` : ""}${this.error ? `<div class="notice error">${this.esc(this.error)}</div>` : ""}<div class="grid">${this.items.length ? this.items.map(item => this.listCard(item)).join("") : `<section class="card"><h2>Noch keine Hofläden</h2><p>Erstelle den ersten Hofladen.</p></section>`}</div>`;
  }

  listCard(item) {
    const lv95 = (item.latitude != null && item.longitude != null) ? wgs84ToLv95(item.latitude, item.longitude) : null;
    const koordText = lv95 ? `LV95 ${Math.round(lv95.easting).toLocaleString("de-CH")} / ${Math.round(lv95.northing).toLocaleString("de-CH")}` : "Keine Koordinaten";
    return `<section class="card">
      <h2>${this.esc(item.name)}</h2>
      <div>${this.esc([item.adresse, item.plz, item.ort, item.land].filter(Boolean).join(", ")) || "<span class=muted>Keine Adresse</span>"}</div>
      <div class="muted">${koordText}</div>
      ${item.website ? `<div class="muted">🔗 ${this.esc(item.website)}</div>` : ""}
      <div class="actions">
        <button class="secondary" data-view="${item.id}">Details</button>
        <button class="secondary" data-edit="${item.id}">Bearbeiten</button>
        <button class="danger" data-delete="${item.id}">Löschen</button>
      </div>
    </section>`;
  }

  // --- Detailansicht (read-only) ---------------------------------------

  detail() {
    const d = this.viewing;
    const adresse = [d.adresse, [d.plz, d.ort].filter(Boolean).join(" "), d.land].filter(Boolean).join(", ");
    const lv95 = (d.latitude != null && d.longitude != null) ? wgs84ToLv95(d.latitude, d.longitude) : null;

    return `<div class="top">
        <div><h1>${this.esc(d.name)}</h1><div class="muted">Detailansicht – nur Anzeige</div></div>
        <div class="actions"><button class="secondary" data-back>← Zurück zur Liste</button><button data-edit-from-detail="${d.id}">Bearbeiten</button></div>
      </div>
      ${this.error ? `<div class="notice error">${this.esc(this.error)}</div>` : ""}

      ${d.beschreibung ? `<section class="card detail-section"><h3>Allgemeine Informationen</h3><div>${this.esc(d.beschreibung)}</div></section>` : ""}

      <section class="card detail-section">
        <h3>Adresse</h3>
        <div>${adresse ? this.esc(adresse) : '<span class="muted">Keine Adresse hinterlegt</span>'}</div>
      </section>

      <section class="card detail-section">
        <h3>Standort / Koordinaten</h3>
        <div class="coord-row">
          <div class="muted">${lv95 ? `LV95: E ${Math.round(lv95.easting).toLocaleString("de-CH")} / N ${Math.round(lv95.northing).toLocaleString("de-CH")}` : "Keine Koordinaten hinterlegt"}</div>
        </div>
        <div class="coord-actions">${this.mapButton(lv95)}</div>
      </section>

      ${this.websiteLinkBlock(d.website)}

      <section class="card detail-section">
        <h3>Öffnungszeiten</h3>
        ${this.detailOpeningHours(d.oeffnungszeiten || [])}
        ${(d.sonderoeffnungszeiten || []).length ? `<h3 style="margin-top:14px">Sonderöffnungszeiten</h3>${this.detailSpecialHours(d.sonderoeffnungszeiten)}` : ""}
      </section>

      ${this.detailPillSection("Kategorien", d.kategorien)}
      ${this.detailProductsSection(d.produkte)}
      ${this.detailPillSection("Zahlungsarten", d.zahlungsarten)}
      ${this.detailPillSection("Verkaufsarten", d.verkaufsarten)}
      ${this.detailPillSection("Merkmale", d.merkmale)}

      ${(d.bilder || []).length ? `<section class="card detail-section"><h3>Bilder</h3><div class="thumbs">${d.bilder.map(b => `<img src="${this.escAttr(b.url)}" alt="${this.escAttr(b.beschreibung || d.name)}" loading="lazy">`).join("")}</div></section>` : ""}
    `;
  }

  /** Webseite als anklickbarer Link – kein UI-Block, wenn keine/keine
   * gültige URL hinterlegt ist (siehe Anforderung: kein leerer Bereich). */
  websiteLinkBlock(website) {
    if (!website || !website.trim()) return "";
    const trimmed = website.trim();
    const href = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
    if (!this.isPlausibleUrl(trimmed)) {
      return `<section class="card detail-section"><h3>Webseite</h3><div class="muted">Ungültige Webseiten-Adresse hinterlegt: ${this.esc(trimmed)}</div></section>`;
    }
    return `<section class="card detail-section"><h3>Webseite</h3><a class="website-link" href="${this.escAttr(href)}" target="_blank" rel="noopener noreferrer">🔗 ${this.esc(trimmed)}</a></section>`;
  }

  detailOpeningHours(rows) {
    const byDay = new Map();
    for (const row of rows) {
      const list = byDay.get(row.wochentag) || [];
      list.push(row);
      byDay.set(row.wochentag, list);
    }
    const lines = [];
    for (let day = 1; day <= 7; day++) {
      const dayRows = (byDay.get(day) || []).slice().sort((a, b) => a.beginn.localeCompare(b.beginn));
      let text;
      if (!dayRows.length) text = '<span class="muted">Geschlossen</span>';
      else if (dayRows.length === 1 && isFullDay(dayRows[0])) text = "24 Stunden geöffnet";
      else text = dayRows.map(r => `${r.beginn}–${r.ende} Uhr`).join(", ");
      lines.push(`<tr><td>${WEEKDAYS[day - 1]}</td><td>${text}</td></tr>`);
    }
    return `<table class="opening-table">${lines.join("")}</table>`;
  }

  detailSpecialHours(rows) {
    return `<table class="opening-table">${rows.map(r => {
      const zeitraum = r.datum_von === r.datum_bis ? this.formatDate(r.datum_von) : `${this.formatDate(r.datum_von)} – ${this.formatDate(r.datum_bis)}`;
      const text = r.geschlossen ? '<span class="muted">Geschlossen</span>' : `${r.beginn || "?"}–${r.ende || "?"} Uhr`;
      return `<tr><td>${this.esc(zeitraum)}</td><td>${text}</td></tr>`;
    }).join("")}</table>`;
  }

  formatDate(iso) {
    if (!iso) return "?";
    const [y, m, d] = iso.split("-");
    return `${d}.${m}.${y}`;
  }

  detailPillSection(label, entries) {
    if (!entries || !entries.length) return "";
    return `<section class="card detail-section"><h3>${label}</h3>${entries.map(e => `<span class="pill">${this.esc(e.name)}</span>`).join("")}</section>`;
  }

  detailProductsSection(produkte) {
    if (!produkte || !produkte.length) return "";
    return `<section class="card detail-section"><h3>Produkte</h3>${produkte.map(p => `<span class="pill">${this.esc(p.name)}</span>`).join("")}</section>`;
  }

  // --- Editor ------------------------------------------------------------

  editor() {
    const d = this.editing;
    const original = this.editing && this.editing.id ? this.items.find(x => x.id === this.editing.id) : null;
    const lv95 = (d.latitude != null && d.latitude !== "" && d.longitude != null && d.longitude !== "") ? wgs84ToLv95(Number(d.latitude), Number(d.longitude)) : null;
    const eastingValue = lv95 ? Math.round(lv95.easting * 100) / 100 : "";
    const northingValue = lv95 ? Math.round(lv95.northing * 100) / 100 : "";

    const specials = (d.sonderoeffnungszeiten || []).map(x => `<div class="special" data-special><label>Von<input type=date name=datum_von value="${x.datum_von || ""}"></label><label>Bis<input type=date name=datum_bis value="${x.datum_bis || ""}"></label><label>Beginn<input type=time name=beginn value="${x.beginn || ""}"></label><label>Ende<input type=time name=ende value="${x.ende || ""}"></label><label>Geschlossen<input type=checkbox name=geschlossen ${x.geschlossen ? "checked" : ""}></label><button type=button class=secondary data-remove-special>−</button></div>`).join("");
    const text = (field) => (d[field] || []).map(x => x.name).join("\n");
    const products = (d.produkte || []).map(x => `${x.name}${x.kategorie_ids?.length ? "|" + x.kategorie_ids.join(",") : ""}`).join("\n");

    return `<div class="top"><div><h1>${d.id ? "Hofladen bearbeiten" : "Neuen Hofladen erstellen"}</h1><div class="muted">${d.id ? this.esc(d.id) : "Neue stabile ID wird beim Speichern erzeugt."}</div></div></div>
      ${this.error ? `<div class="notice error">${this.esc(this.error)}</div>` : ""}
      <form>
        <section class=card>
          <h2>Allgemeine Informationen</h2>
          <div class="fields">
            <div class="field-row">${this.input("Name", "name", d.name, true)}</div>
            <div class="field-row">${this.input("Beschreibung", "beschreibung", d.beschreibung || "")}</div>
          </div>
        </section>

        <section class=card>
          <h2>Adresse</h2>
          <div class="fields">
            <div class="field-row">${this.input("Adresse", "adresse", d.adresse || "")}</div>
            <div class="field-row two">${this.input("PLZ", "plz", d.plz || "")}${this.input("Ort", "ort", d.ort || "")}</div>
            <div class="field-row">${this.input("Land", "land", d.land || "")}</div>
          </div>
        </section>

        <section class=card>
          <h2>Kontakt &amp; Webseite</h2>
          <div class="fields">
            <div class="field-row">${this.input("Webseite", "website", d.website || "")}</div>
          </div>
        </section>

        <section class=card>
          <h2>Standort / Koordinaten <span class="muted" style="font-weight:normal;font-size:.7em">(LV95 / EPSG:2056)</span></h2>
          <div class="coord-row">
            <div class="field-row two">
              <label>E (Ostwert)<input name="lv95_easting" type="number" step="any" value="${eastingValue}" placeholder="z. B. 2600980"></label>
              <label>N (Nordwert)<input name="lv95_northing" type="number" step="any" value="${northingValue}" placeholder="z. B. 1197450"></label>
            </div>
            <button type="button" class="info-btn" data-toggle-lv95-info title="Was ist LV95? (Erklärung anzeigen)" aria-label="Was ist LV95? Erklärung anzeigen">ⓘ</button>
          </div>
          <div class="coord-actions">${this.mapButton(lv95)}</div>
          <input type="hidden" name="lv95_original_easting" value="${eastingValue}">
          <input type="hidden" name="lv95_original_northing" value="${northingValue}">
          ${this.showLv95Info ? this.lv95InfoBox() : ""}
        </section>

        <section class=card>
          <h2>Öffnungszeiten</h2>
          ${this.openingHoursEditor(d.oeffnungszeiten || [])}
          <h3>Sonderöffnungszeiten</h3>
          <div id=specials>${specials}</div>
          <button type=button class=secondary data-add-special>+ Sonderzeit hinzufügen</button>
        </section>

        <section class=card>
          <h2>Sortiment und Eigenschaften</h2>
          <p class=muted>Ein Eintrag pro Zeile. Produkte können optional mit Kategorie-IDs als <code>Produkt|kategorie-id</code> angegeben werden.</p>
          ${this.area("Kategorien", "kategorien", text("kategorien"))}
          ${this.area("Produkte", "produkte", products)}
          ${this.area("Zahlungsarten", "zahlungsarten", text("zahlungsarten"))}
          ${this.area("Verkaufsarten", "verkaufsarten", text("verkaufsarten"))}
          ${this.area("Merkmale", "merkmale", text("merkmale"))}
        </section>

        <div class=actions>
          <button type=button class=secondary data-cancel>Abbrechen</button>
          <button type=submit>Speichern</button>
        </div>
      </form>`;
  }

  lv95InfoBox() {
    return `<div class="info-box">
      <strong>Was ist LV95?</strong><br>
      LV95 (Landesvermessung 1995) ist das amtliche Schweizer
      Koordinatensystem, technisch auch <code>EPSG:2056</code> genannt.
      Es besteht aus zwei Werten in Metern:<br>
      • <strong>E (Ostwert, auch „Easting“ oder „Y“)</strong> – ca.
      2'480'000 bis 2'834'000<br>
      • <strong>N (Nordwert, auch „Northing“ oder „X“)</strong> – ca.
      1'075'000 bis 1'296'000<br>
      Beide Werte findest du z. B. auf <a href="https://map.geo.admin.ch" target="_blank" rel="noopener noreferrer">map.geo.admin.ch</a>
      (Rechtsklick auf den gewünschten Ort → Koordinaten werden
      angezeigt).
    </div>`;
  }

  /** Öffnungszeiten-Editor: pro Wochentag ein Block mit Modus
   * Geschlossen / 24 Stunden / Zeiten festlegen (statt eines globalen
   * prompt()-Dialogs). */
  openingHoursEditor(rows) {
    const byDay = new Map();
    for (const row of rows) {
      const list = byDay.get(Number(row.wochentag)) || [];
      list.push(row);
      byDay.set(Number(row.wochentag), list);
    }

    const blocks = [];
    for (let day = 1; day <= 7; day++) {
      const dayRows = byDay.get(day) || [];
      let mode = "geschlossen";
      if (dayRows.length === 1 && isFullDay(dayRows[0])) mode = "24h";
      else if (dayRows.length > 0) mode = "zeiten";

      const intervalsHtml = (mode === "zeiten" ? dayRows : []).map(r => this.intervalRow(day, r)).join("");

      blocks.push(`<div class="day-block" data-day-block="${day}">
        <div class="day-title">${WEEKDAYS[day - 1]}</div>
        <div class="day-mode">
          <label><input type="radio" name="day_mode_${day}" value="geschlossen" ${mode === "geschlossen" ? "checked" : ""}> Geschlossen</label>
          <label><input type="radio" name="day_mode_${day}" value="24h" ${mode === "24h" ? "checked" : ""}> 24 Stunden geöffnet</label>
          <label><input type="radio" name="day_mode_${day}" value="zeiten" ${mode === "zeiten" ? "checked" : ""}> Zeiten festlegen</label>
        </div>
        <div class="day-intervals" data-day-intervals="${day}" style="${mode === "zeiten" ? "" : "display:none"}">
          ${intervalsHtml || this.intervalRow(day, { beginn: "", ende: "" })}
          <button type="button" class="secondary" data-add-interval="${day}">+ weiteres Intervall</button>
        </div>
      </div>`);
    }
    return blocks.join("");
  }

  intervalRow(day, x) {
    return `<div class="interval-row" data-day-interval="${day}">
      <label>Von<input type=time name=beginn value="${x.beginn || ""}"></label>
      <label>Bis<input type=time name=ende value="${x.ende || ""}"></label>
      <button type=button class=secondary data-remove-interval title="Intervall entfernen">−</button>
    </div>`;
  }

  input(label, name, value, required = false) { return `<label>${label}<input name="${name}" value="${this.escAttr(String(value))}" ${required ? "required" : ""}></label>`; }
  area(label, name, value) { return `<label>${label}<textarea name="${name}">${this.esc(value)}</textarea></label>`; }

  // --- Ereignisbindung -----------------------------------------------

  bind() {
    this.shadowRoot.querySelector("[data-new]")?.addEventListener("click", () => this.start());
    this.shadowRoot.querySelectorAll("[data-edit]").forEach(b => b.addEventListener("click", () => this.start(this.items.find(x => x.id === b.dataset.edit))));
    this.shadowRoot.querySelector("[data-edit-from-detail]")?.addEventListener("click", (e) => this.start(this.items.find(x => x.id === e.target.dataset.editFromDetail)));
    this.shadowRoot.querySelectorAll("[data-view]").forEach(b => b.addEventListener("click", () => this.view(this.items.find(x => x.id === b.dataset.view))));
    this.shadowRoot.querySelector("[data-back]")?.addEventListener("click", () => this.closeView());
    this.shadowRoot.querySelectorAll("[data-delete]").forEach(b => b.addEventListener("click", () => this.remove(b.dataset.delete)));
    this.shadowRoot.querySelector("[data-cancel]")?.addEventListener("click", () => this.cancel());
    this.shadowRoot.querySelector("form")?.addEventListener("submit", e => { e.preventDefault(); this.save(); });

    this.shadowRoot.querySelector('[data-toggle-lv95-info]')?.addEventListener("click", () => { this.showLv95Info = !this.showLv95Info; this.render(); });

    this.shadowRoot.querySelectorAll('input[name^="day_mode_"]').forEach(radio => radio.addEventListener("change", (e) => {
      const day = e.target.name.split("_")[2];
      const container = this.shadowRoot.querySelector(`[data-day-intervals="${day}"]`);
      if (container) container.style.display = e.target.value === "zeiten" ? "" : "none";
    }));
    this.shadowRoot.querySelectorAll("[data-add-interval]").forEach(b => b.addEventListener("click", () => {
      const day = b.dataset.addInterval;
      const container = this.shadowRoot.querySelector(`[data-day-intervals="${day}"]`);
      const el = document.createElement("div");
      el.innerHTML = this.intervalRow(day, { beginn: "", ende: "" });
      container.insertBefore(el.firstElementChild, b);
      this.bind();
    }));
    this.shadowRoot.querySelectorAll("[data-remove-interval]").forEach(b => b.addEventListener("click", () => b.parentElement.remove()));

    this.shadowRoot.querySelectorAll("[data-remove-special]").forEach(b => b.addEventListener("click", () => b.parentElement.remove()));
    this.shadowRoot.querySelector("[data-add-special]")?.addEventListener("click", () => {
      const el = document.createElement("div");
      el.innerHTML = `<div class="special" data-special><label>Von<input type=date name=datum_von></label><label>Bis<input type=date name=datum_bis></label><label>Beginn<input type=time name=beginn></label><label>Ende<input type=time name=ende></label><label>Geschlossen<input type=checkbox name=geschlossen></label><button type=button class=secondary data-remove-special>−</button></div>`;
      this.shadowRoot.querySelector("#specials").append(el.firstElementChild);
      this.bind();
    });
  }

  esc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[c])); }
  escAttr(s) { return this.esc(s).replace(/'/g, "&#39;"); }
}
customElements.define("hofkarte-panel", HofkartePanel);
