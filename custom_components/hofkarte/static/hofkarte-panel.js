/**
 * HofKarte-Verwaltungspanel.
 *
 * Drei Ansichten: Liste (list), Bearbeiten (editor), Details (detail,
 * read-only). Kommuniziert ausschliesslich über die bestehenden
 * WebSocket-Befehle hofkarte/management/list|save|delete – keine neuen
 * Backend-Endpunkte nötig (die Detailansicht liest nur bereits
 * geladene Daten).
 *
 * Koordinaten: Eingabe/Anzeige erfolgt direkt im selben Format, in dem
 * das Backend/Datenmodell speichert (WGS84-Dezimalgrad,
 * ``Hofladen.latitude``/``longitude``) – keine Umrechnung nötig.
 */

function isValidWgs84(lat, lon) {
  return Number.isFinite(lat) && Number.isFinite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
}

/** Google-Maps-Link für eine WGS84-Koordinate (offizielles URL-Schema,
 * siehe https://developers.google.com/maps/documentation/urls/get-started). */
function googleMapsUrl(lat, lon) {
  return `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`;
}

/** Grosskreisdistanz zwischen zwei WGS84-Koordinaten in Kilometern
 * (Haversine-Formel) – client-seitiges Äquivalent zu
 * distance.haversine_distance_km() in distance.py, für die Entfernung
 * vom aktuell verwendeten Gerät aus (siehe deviceDistanceBlock()).
 * Bewusst dupliziert statt im Backend berechnet: Der Gerätestandort
 * wird nicht an das Backend übertragen (Datenschutz), die Berechnung
 * muss daher im Browser erfolgen. */
function haversineDistanceKm(lat1, lon1, lat2, lon2) {
  const erdradiusKm = 6371.0088;
  const toRad = (grad) => (grad * Math.PI) / 180;
  const phi1 = toRad(lat1);
  const phi2 = toRad(lat2);
  const deltaPhi = toRad(lat2 - lat1);
  const deltaLambda = toRad(lon2 - lon1);
  const a = Math.sin(deltaPhi / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(deltaLambda / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return erdradiusKm * c;
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
    this.showCoordInfo = false;
    this.deviceDistance = null; // { km } - clientseitig ermittelte Entfernung vom aktuellen Gerät
    this.deviceDistanceStatus = ""; // Lade-/Fehlermeldung während der Ermittlung
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
    return { id: "", name: "", beschreibung: "", adresse: "", plz: "", ort: "", land: "", website: "", latitude: "", longitude: "", oeffnungszeiten: [], sonderoeffnungszeiten: [], angebote: [], zahlungsarten: [], verkaufsarten: [], merkmale: [], bilder: [] };
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
    if (d.latitude !== null && d.latitude !== "" && (d.latitude < -90 || d.latitude > 90)) throw new Error("Latitude muss zwischen -90 und 90 liegen.");
    if (d.longitude !== null && d.longitude !== "" && (d.longitude < -180 || d.longitude > 180)) throw new Error("Longitude muss zwischen -180 und 180 liegen.");
    for (const row of d.oeffnungszeiten) if (!row.beginn || !row.ende || row.beginn === row.ende) throw new Error("Öffnungszeiten enthalten ungültige oder unvollständige Zeiten.");
    if (d.website && d.website.trim() && !this.isPlausibleUrl(d.website.trim())) throw new Error("Die Webseite muss eine gültige http(s)-Adresse sein (z. B. https://www.beispiel.ch).");
  }

  isPlausibleUrl(value) {
    try {
      const url = new URL(value.match(/^https?:\/\//i) ? value : `https://${value}`);
      return url.protocol === "http:" || url.protocol === "https:";
    } catch { return false; }
  }

  /** WGS84-Koordinatenfelder auslesen. Da Eingabe und Speicherformat
   * identisch sind (beide WGS84-Dezimalgrad), ist keine Umrechnung
   * nötig – die Werte werden nur validiert. */
  resolveCoordinates(f) {
    const latRaw = f.elements["latitude"]?.value ?? "";
    const lonRaw = f.elements["longitude"]?.value ?? "";
    if (latRaw === "" && lonRaw === "") return { latitude: null, longitude: null };

    const lat = Number(latRaw);
    const lon = Number(lonRaw);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      throw new Error("Latitude/Longitude müssen Zahlen sein.");
    }
    if (!isValidWgs84(lat, lon)) {
      throw new Error("Latitude muss zwischen -90 und 90 und Longitude zwischen -180 und 180 liegen.");
    }
    return { latitude: lat, longitude: lon };
  }

  /** Gemeinsame Kartenlogik für "Bearbeiten" und "Details" (identisches
   * Verhalten in beiden Ansichten). Öffnet Google Maps anhand der
   * gespeicherten WGS84-Koordinaten in einem neuen Tab, verändert keine
   * Daten (rein lesender externer Link), keine neue Abhängigkeit. */
  mapButton(lat, lon) {
    if (!isValidWgs84(lat, lon)) {
      return `<button type="button" class="map-btn" disabled title="Keine gültigen Koordinaten hinterlegt">🗺️ Auf Google Maps anzeigen</button>`;
    }
    const url = googleMapsUrl(lat, lon);
    return `<a class="map-btn" href="${this.escAttr(url)}" target="_blank" rel="noopener noreferrer" title="Standort auf Google Maps anzeigen (neuer Tab)">🗺️ Auf Google Maps anzeigen</a>`;
  }

  /** Entfernung vom aktuell verwendeten Gerät (nicht vom
   * Home-Assistant-Server) zum Hofladen ermitteln – rein clientseitig
   * über die Browser-Geolocation-API. Der Gerätestandort wird
   * ausschliesslich lokal für diese Berechnung verwendet, nicht
   * gespeichert und nicht an das Backend übertragen (siehe
   * haversineDistanceKm-Kommentar). Ergänzt die bestehende,
   * serverseitige Entfernungs-Entity, ersetzt sie nicht.
   */
  ermittleGeraeteEntfernung() {
    const hofladen = this.viewing;
    if (!hofladen || !isValidWgs84(hofladen.latitude, hofladen.longitude)) return;

    if (!("geolocation" in navigator)) {
      this.deviceDistanceStatus = "Dieser Browser unterstützt keine Standortermittlung.";
      this.render();
      return;
    }

    this.deviceDistanceStatus = "Standort wird ermittelt …";
    this.deviceDistance = null;
    this.render();

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const km = haversineDistanceKm(
          position.coords.latitude, position.coords.longitude,
          hofladen.latitude, hofladen.longitude
        );
        this.deviceDistance = { km };
        this.deviceDistanceStatus = "";
        this.render();
      },
      (fehler) => {
        const meldungen = {
          1: "Standortzugriff wurde verweigert.", // PERMISSION_DENIED
          2: "Standort konnte nicht ermittelt werden.", // POSITION_UNAVAILABLE
          3: "Standortermittlung hat zu lange gedauert.", // TIMEOUT
        };
        this.deviceDistanceStatus = meldungen[fehler.code] || "Standort konnte nicht ermittelt werden.";
        this.render();
      },
      { timeout: 10000, maximumAge: 60000 }
    );
  }

  /** Anzeigeblock für die Geräte-Entfernung in der Detailansicht. */
  deviceDistanceBlock(hofladen) {
    if (!isValidWgs84(hofladen.latitude, hofladen.longitude)) return "";

    let inhalt;
    if (this.deviceDistance) {
      inhalt = `<span class="muted">Entfernung von diesem Gerät: <strong>${this.deviceDistance.km.toFixed(1)} km</strong></span>`;
    } else if (this.deviceDistanceStatus) {
      inhalt = `<span class="muted">${this.esc(this.deviceDistanceStatus)}</span>`;
    } else {
      inhalt = `<button type="button" class="secondary" data-geraete-entfernung title="Nutzt den Standort dieses Geräts/Browsers, nicht den des Home-Assistant-Servers">📍 Entfernung von diesem Gerät berechnen</button>`;
    }
    return `<div class="coord-row" style="margin-top:8px">${inhalt}</div>`;
  }

  // --- Bilder: geführter Upload -----------------------------------------
  //
  // Nutzt Home Assistants eigene image_upload-Komponente
  // (POST /api/image/upload, Serve unter /api/image/serve/<id>/original,
  // Löschen über den WebSocket-Befehl "image/delete") statt eines
  // eigenen Upload-Endpunkts. Die serverseitige Validierung (erlaubte
  // Formate, maximale Grösse) übernimmt diese Home-Assistant-Komponente
  // vollständig; die Prüfung hier dient nur dem sofortigen, direkten
  // Feedback vor dem eigentlichen Upload.

  static UPLOAD_MAX_BYTES = 10 * 1024 * 1024; // entspricht image_upload.MAX_SIZE
  static UPLOAD_ERLAUBTE_TYPEN = ["image/jpeg", "image/png", "image/gif"];

  extractImageId(url) {
    const treffer = /\/api\/image\/serve\/([^/]+)\//.exec(url || "");
    return treffer ? treffer[1] : null;
  }

  setUploadStatus(text, kind = "") {
    const el = this.shadowRoot.querySelector("[data-upload-status]");
    if (!el) return;
    el.textContent = text;
    el.className = `upload-status muted${kind ? " " + kind : ""}`;
  }

  async uploadBild(file) {
    if (!file) return;

    if (!HofkartePanel.UPLOAD_ERLAUBTE_TYPEN.includes(file.type)) {
      this.setUploadStatus("Nicht unterstütztes Dateiformat. Erlaubt: JPEG, PNG, GIF.", "error");
      return;
    }
    if (file.size > HofkartePanel.UPLOAD_MAX_BYTES) {
      this.setUploadStatus("Datei ist zu gross (maximal 10 MB erlaubt).", "error");
      return;
    }

    this.setUploadStatus(`„${file.name}“ wird hochgeladen …`);
    try {
      const formData = new FormData();
      formData.append("file", file);
      // Home Assistants /api/*-Endpunkte erfordern eine Authentifizierung
      // per Bearer-Token (kein Cookie-basiertes Login) – ohne den
      // Authorization-Header schlägt der Upload mit "invalid
      // authentication" fehl, obwohl man in der Oberfläche angemeldet
      // ist. this.hass.auth.accessToken wird vom Frontend automatisch
      // aktuell gehalten (Token-Refresh), siehe auch this.call(), das für
      // WebSocket-Befehle bereits über dieselbe hass-Verbindung läuft.
      const response = await fetch("/api/image/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${this.hass.auth.accessToken}` },
        body: formData,
      });
      if (response.status === 401) {
        throw new Error("Anmeldung abgelaufen. Bitte Seite neu laden und erneut versuchen.");
      }
      if (!response.ok) {
        throw new Error(response.status === 413 ? "Datei ist zu gross." : `Upload fehlgeschlagen (${response.status}).`);
      }
      const ergebnis = await response.json();
      const url = `${window.location.origin}/api/image/serve/${ergebnis.id}/original`;

      if (!this.editing.bilder) this.editing.bilder = [];
      this.editing.bilder.push({ url, beschreibung: null, hochgeladen: true });
      this.setUploadStatus(`„${file.name}“ erfolgreich hochgeladen.`, "success");
      this.render();
    } catch (err) {
      this.setUploadStatus(err?.message || "Upload fehlgeschlagen.", "error");
    }
  }

  async removeBild(index) {
    if (!this.editing.bilder) this.editing.bilder = [];
    const bild = this.editing.bilder[index];
    if (!bild) return;

    if (bild.hochgeladen) {
      const imageId = this.extractImageId(bild.url);
      if (imageId) {
        try {
          await this.call("image/delete", { image_id: imageId });
        } catch (err) {
          // Die zugrunde liegende Datei liess sich nicht bereinigen
          // (z. B. bereits anderweitig gelöscht) - das Bild wird trotzdem
          // aus dem Hofladen entfernt, um die Nutzerin/den Nutzer nicht
          // zu blockieren; kein Datenverlust an Hofladen-Seite dadurch.
          console.warn("Hochgeladenes Bild konnte nicht bereinigt werden:", err);
        }
      }
    }

    this.editing.bilder.splice(index, 1);
    this.render();
  }

  setHauptbild(index) {
    const bilder = this.editing.bilder || [];
    if (index <= 0 || index >= bilder.length) return;
    const [gewaehltes] = bilder.splice(index, 1);
    bilder.unshift(gewaehltes);
    this.render();
  }

  addExternalUrl(value) {
    const trimmed = (value || "").trim();
    if (!trimmed) return;
    if (!this.isPlausibleUrl(trimmed)) {
      this.setUploadStatus("Die Bild-Adresse muss eine gültige http(s)-Adresse sein.", "error");
      return;
    }
    if (!this.editing.bilder) this.editing.bilder = [];
    this.editing.bilder.push({ url: trimmed, beschreibung: null, hochgeladen: false });
    this.setUploadStatus("");
    this.render();
  }

  formData() {
    const f = this.shadowRoot.querySelector("form");
    const value = (name) => f.elements[name]?.value ?? "";
    const data = this.clone(this.editing || this.empty());
    data.name = value("name"); data.beschreibung = value("beschreibung") || null;
    data.adresse = value("adresse") || null; data.plz = value("plz") || null;
    data.ort = value("ort") || null; data.land = value("land") || null;
    data.website = value("website") || null;
    const koordinaten = this.resolveCoordinates(f);
    data.latitude = koordinaten.latitude; data.longitude = koordinaten.longitude;
    data.oeffnungszeiten = this.readOpeningHours(f);
    data.sonderoeffnungszeiten = [...f.querySelectorAll("[data-special]")].map(row => ({ datum_von: row.querySelector("[name=datum_von]").value, datum_bis: row.querySelector("[name=datum_bis]").value, geschlossen: row.querySelector("[name=geschlossen]").checked, beginn: row.querySelector("[name=beginn]").value || null, ende: row.querySelector("[name=ende]").value || null }));
    for (const field of ["zahlungsarten", "verkaufsarten", "merkmale"]) data[field] = this.lines(f.elements[field]?.value);
    data.angebote = this.angebote(f.elements.angebote?.value);
    // Bilder: Liste selbst lebt in this.editing.bilder (Upload/Entfernen/
    // Hauptbild-Wechsel mutieren sie direkt, siehe uploadBild/removeBild/
    // setHauptbild) – hier nur die live editierbaren Beschreibungsfelder
    // aus dem Formular übernehmen.
    data.bilder = (this.editing?.bilder || []).map((bild, i) => {
      const feld = f.querySelector(`[data-bild-index="${i}"] [data-bild-beschreibung]`);
      return { ...bild, beschreibung: feld ? (feld.value || null) : bild.beschreibung };
    });
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
  /** Ein "Angebote"-Textfeld (ein Eintrag pro Zeile, Syntax
   * "Name" oder "Name|Gruppe1,Gruppe2") in Angebot-Rohdaten überführen.
   * Ersetzt die früheren getrennten Felder "Kategorien"/"Produkte". */
  angebote(text) {
    return String(text || "").split("\n").map(x => x.trim()).filter(Boolean).map(line => {
      const [name, gruppenText = ""] = line.split("|");
      const gruppen = gruppenText.split(",").map(g => g.trim()).filter(Boolean);
      return { id: this.slug(name), name: name.trim(), gruppen };
    });
  }
  slug(s) { return String(s).toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "eintrag"; }

  async remove(id) {
    if (!confirm("Möchtest du diesen Hofladen wirklich löschen?")) return;
    try { await this.call("hofkarte/management/delete", { hofladen_id: id }); this.message = "Hofladen gelöscht."; this.viewing = null; await this.load(); }
    catch (err) { this.error = err?.message || "Löschen fehlgeschlagen."; this.render(); }
  }

  start(item = null) { this.error = ""; this.viewing = null; this.showCoordInfo = false; this.editing = item ? this.clone(item) : this.empty(); this.render(); }
  cancel() { this.editing = null; this.error = ""; this.render(); }
  view(item) { this.error = ""; this.editing = null; this.viewing = item; this.deviceDistance = null; this.deviceDistanceStatus = ""; this.render(); }
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
      .bild-row{display:flex;gap:10px;align-items:center;padding:8px;border:1px solid var(--divider-color);border-radius:8px;margin-bottom:8px}
      .bild-row img{width:64px;height:64px;object-fit:cover;border-radius:6px;flex:0 0 auto}
      .bild-row-fields{flex:1;min-width:0}
      .bild-row-fields input{width:100%}
      .bild-row-meta{margin-top:4px;font-size:.85em}
      .bild-row-actions{display:flex;gap:6px;flex:0 0 auto}
      .upload-row{display:flex;align-items:center;gap:12px;margin-top:10px;flex-wrap:wrap}
      .upload-start-btn{display:inline-flex;align-items:center;gap:6px;height:36px;padding:0 16px;border-radius:8px;background:var(--success-color,#43a047);color:#fff;cursor:pointer;font-size:.95em;font-weight:500;border:0;box-shadow:0 1px 3px #0003}
      .upload-start-btn:hover,.upload-start-btn:focus-visible{filter:brightness(0.95);outline:2px solid var(--success-color,#43a047);outline-offset:2px}
      .upload-status{font-size:.9em}
      .upload-status.error{color:var(--error-color,#db4437)}
      .upload-status.success{color:var(--success-color,#43a047)}
      .thumbs img{width:96px;height:96px;object-fit:cover;border-radius:8px}
    `;
  }

  // --- Liste -----------------------------------------------------------

  list() {
    return `<div class="top"><div><h1>HofKarte</h1><div class="muted">Hofläden verwalten</div></div><button data-new>+ Neuer Hofladen</button></div>${this.message ? `<div class="notice">${this.esc(this.message)}</div>` : ""}${this.error ? `<div class="notice error">${this.esc(this.error)}</div>` : ""}<div class="grid">${this.items.length ? this.items.map(item => this.listCard(item)).join("") : `<section class="card"><h2>Noch keine Hofläden</h2><p>Erstelle den ersten Hofladen.</p></section>`}</div>`;
  }

  listCard(item) {
    const koordText = (item.latitude != null && item.longitude != null) ? `${item.latitude.toFixed(5)}, ${item.longitude.toFixed(5)}` : "Keine Koordinaten";
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
    const hatKoordinaten = d.latitude != null && d.longitude != null;

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
          <div class="muted">${hatKoordinaten ? `Latitude ${d.latitude.toFixed(6)}, Longitude ${d.longitude.toFixed(6)}` : "Keine Koordinaten hinterlegt"}</div>
        </div>
        <div class="coord-actions">${this.mapButton(d.latitude, d.longitude)}</div>
        ${this.deviceDistanceBlock(d)}
      </section>

      ${this.websiteLinkBlock(d.website)}

      <section class="card detail-section">
        <h3>Öffnungszeiten</h3>
        ${this.detailOpeningHours(d.oeffnungszeiten || [])}
        ${(d.sonderoeffnungszeiten || []).length ? `<h3 style="margin-top:14px">Sonderöffnungszeiten</h3>${this.detailSpecialHours(d.sonderoeffnungszeiten)}` : ""}
      </section>

      ${this.detailAngeboteSection(d.angebote)}
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

  /** Angebote in der Detailansicht, nach Gruppen zusammengefasst (sofern
   * vorhanden) – ersetzt die früher getrennten Abschnitte
   * "Kategorien"/"Produkte". Angebote ohne Gruppe erscheinen gesammelt
   * unter "Ohne Gruppe". */
  detailAngeboteSection(angebote) {
    if (!angebote || !angebote.length) return "";

    const gruppenMap = new Map();
    const ohneGruppe = [];
    for (const angebot of angebote) {
      if (!angebot.gruppen || !angebot.gruppen.length) {
        ohneGruppe.push(angebot.name);
        continue;
      }
      for (const gruppe of angebot.gruppen) {
        if (!gruppenMap.has(gruppe)) gruppenMap.set(gruppe, []);
        gruppenMap.get(gruppe).push(angebot.name);
      }
    }

    const gruppenNamen = [...gruppenMap.keys()].sort((a, b) => a.localeCompare(b));
    const gruppenHtml = gruppenNamen.map(gruppe => `
      <div style="margin-bottom:8px">
        <div class="muted" style="font-size:.85em;margin-bottom:4px">${this.esc(gruppe)}</div>
        ${gruppenMap.get(gruppe).map(name => `<span class="pill">${this.esc(name)}</span>`).join("")}
      </div>
    `).join("");
    const ohneGruppeHtml = ohneGruppe.length ? `
      <div>
        ${gruppenNamen.length ? `<div class="muted" style="font-size:.85em;margin-bottom:4px">Ohne Gruppe</div>` : ""}
        ${ohneGruppe.map(name => `<span class="pill">${this.esc(name)}</span>`).join("")}
      </div>
    ` : "";

    return `<section class="card detail-section"><h3>Angebote</h3>${gruppenHtml}${ohneGruppeHtml}</section>`;
  }

  // --- Editor ------------------------------------------------------------

  editor() {
    const d = this.editing;
    const latValue = (d.latitude != null && d.latitude !== "") ? d.latitude : "";
    const lonValue = (d.longitude != null && d.longitude !== "") ? d.longitude : "";

    const specials = (d.sonderoeffnungszeiten || []).map(x => `<div class="special" data-special><label>Von<input type=date name=datum_von value="${x.datum_von || ""}"></label><label>Bis<input type=date name=datum_bis value="${x.datum_bis || ""}"></label><label>Beginn<input type=time name=beginn value="${x.beginn || ""}"></label><label>Ende<input type=time name=ende value="${x.ende || ""}"></label><label>Geschlossen<input type=checkbox name=geschlossen ${x.geschlossen ? "checked" : ""}></label><button type=button class=secondary data-remove-special>−</button></div>`).join("");
    const text = (field) => (d[field] || []).map(x => x.name).join("\n");
    const angeboteText = (d.angebote || []).map(x => `${x.name}${x.gruppen?.length ? "|" + x.gruppen.join(",") : ""}`).join("\n");

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
          <h2>Standort / Koordinaten <span class="muted" style="font-weight:normal;font-size:.7em">(WGS84)</span></h2>
          <div class="coord-row">
            <div class="field-row two">
              <label>Latitude<input name="latitude" type="number" step="any" value="${latValue}" placeholder="z. B. 46.9480"></label>
              <label>Longitude<input name="longitude" type="number" step="any" value="${lonValue}" placeholder="z. B. 7.4474"></label>
            </div>
            <button type="button" class="info-btn" data-toggle-coord-info title="Was sind Latitude/Longitude? (Erklärung anzeigen)" aria-label="Was sind Latitude/Longitude? Erklärung anzeigen">ⓘ</button>
          </div>
          <div class="coord-actions">${this.mapButton(latValue === "" ? NaN : Number(latValue), lonValue === "" ? NaN : Number(lonValue))}</div>
          ${this.showCoordInfo ? this.coordInfoBox() : ""}
        </section>

        <section class=card>
          <h2>Öffnungszeiten</h2>
          ${this.openingHoursEditor(d.oeffnungszeiten || [])}
          <h3>Sonderöffnungszeiten</h3>
          <div id=specials>${specials}</div>
          <button type=button class=secondary data-add-special>+ Sonderzeit hinzufügen</button>
        </section>

        <section class=card>
          <h2>Angebote und Eigenschaften</h2>
          <p class=muted>Ein Eintrag pro Zeile. Angebote können optional mit Gruppen als <code>Angebot|Gruppe1,Gruppe2</code> angegeben werden (z. B. <code>Kartoffeln|Gemüse</code>).</p>
          ${this.area("Angebote", "angebote", angeboteText)}
          ${this.area("Zahlungsarten", "zahlungsarten", text("zahlungsarten"))}
          ${this.area("Verkaufsarten", "verkaufsarten", text("verkaufsarten"))}
          ${this.area("Merkmale", "merkmale", text("merkmale"))}
        </section>

        <section class=card>
          <h2>Bilder</h2>
          <p class="muted">Das erste Bild in der Liste ist das Hauptbild. Bilder können hochgeladen oder per externer Adresse verlinkt werden.</p>
          <div id="bilder-liste">${this.bilderListe(d.bilder || [])}</div>
          <div class="upload-row">
            <button type="button" class="upload-start-btn" data-start-upload title="Bild-Upload starten" aria-label="Bild-Upload starten">📤 Bild hochladen</button>
            <input type="file" id="bild-upload-input" accept="image/jpeg,image/png,image/gif" style="display:none">
            <span class="upload-status muted" data-upload-status></span>
          </div>
          <details style="margin-top:10px">
            <summary class="muted" style="cursor:pointer">Oder externe Bild-Adresse manuell hinzufügen</summary>
            <div class="field-row two" style="margin-top:8px">
              <input type="text" data-external-url placeholder="https://beispiel.ch/bild.jpg">
              <button type="button" class="secondary" data-add-external-url>Hinzufügen</button>
            </div>
          </details>
        </section>

        <div class=actions>
          <button type=button class=secondary data-cancel>Abbrechen</button>
          <button type=submit>Speichern</button>
        </div>
      </form>`;
  }

  /** Liste der Bilder eines Hofladens im Editor – Vorschau, optionale
   * Beschreibung, "Als Hauptbild"/"Entfernen"-Aktionen. Das erste Bild
   * gilt als Hauptbild (bestehende Konvention, siehe images.py). */
  bilderListe(bilder) {
    if (!bilder.length) return `<p class="muted">Noch keine Bilder hinterlegt.</p>`;
    return bilder.map((bild, i) => `<div class="bild-row" data-bild-index="${i}">
      <img src="${this.escAttr(bild.url)}" alt="" loading="lazy">
      <div class="bild-row-fields">
        <input type="text" data-bild-beschreibung placeholder="Beschreibung (optional)" value="${this.escAttr(bild.beschreibung || "")}">
        <div class="bild-row-meta muted">${i === 0 ? "Hauptbild · " : ""}${bild.hochgeladen ? "hochgeladen" : "externe Adresse"}</div>
      </div>
      <div class="bild-row-actions">
        ${i !== 0 ? `<button type="button" class="secondary" data-bild-hauptbild="${i}" title="Als Hauptbild festlegen">⭐</button>` : ""}
        <button type="button" class="danger" data-bild-entfernen="${i}" title="Bild entfernen">🗑️</button>
      </div>
    </div>`).join("");
  }

  coordInfoBox() {
    return `<div class="info-box">
      <strong>Was sind Latitude/Longitude?</strong><br>
      Latitude und Longitude (WGS84, Dezimalgrad) sind das weltweit
      gebräuchliche Koordinatensystem, mit dem auch Home Assistant
      selbst Standorte angibt. Es besteht aus zwei Werten:<br>
      • <strong>Latitude (Breitengrad)</strong> – Wert zwischen -90 und
      90 (Schweiz: ca. 45.8 bis 47.8)<br>
      • <strong>Longitude (Längengrad)</strong> – Wert zwischen -180
      und 180 (Schweiz: ca. 5.9 bis 10.5)<br>
      Beide Werte findest du z. B. in Google Maps (Rechtsklick auf den
      gewünschten Ort → die angezeigten Zahlen sind Latitude,
      Longitude) oder über den Button „Auf Google Maps anzeigen“
      unten, sobald bereits Koordinaten hinterlegt sind.
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
    this.shadowRoot.querySelector("[data-geraete-entfernung]")?.addEventListener("click", () => this.ermittleGeraeteEntfernung());
    this.shadowRoot.querySelectorAll("[data-delete]").forEach(b => b.addEventListener("click", () => this.remove(b.dataset.delete)));
    this.shadowRoot.querySelector("[data-cancel]")?.addEventListener("click", () => this.cancel());
    this.shadowRoot.querySelector("form")?.addEventListener("submit", e => { e.preventDefault(); this.save(); });

    this.shadowRoot.querySelector('[data-toggle-coord-info]')?.addEventListener("click", () => { this.showCoordInfo = !this.showCoordInfo; this.render(); });

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

    // --- Bilder ---
    // Der Start-Button löst gezielt die Dateiauswahl des bestehenden,
    // versteckten Datei-Felds aus (input.click()); der eigentliche
    // Upload-Ablauf (Validierung, Upload, Rückmeldung) bleibt
    // unverändert an das "change"-Ereignis dieses Felds gebunden.
    this.shadowRoot.querySelector("[data-start-upload]")?.addEventListener("click", () => {
      this.shadowRoot.querySelector("#bild-upload-input")?.click();
    });
    this.shadowRoot.querySelector("#bild-upload-input")?.addEventListener("change", (e) => {
      const file = e.target.files?.[0];
      this.uploadBild(file);
      e.target.value = ""; // erlaubt erneutes Hochladen derselben Datei
    });
    this.shadowRoot.querySelectorAll("[data-bild-entfernen]").forEach(b =>
      b.addEventListener("click", () => this.removeBild(Number(b.dataset.bildEntfernen)))
    );
    this.shadowRoot.querySelectorAll("[data-bild-hauptbild]").forEach(b =>
      b.addEventListener("click", () => this.setHauptbild(Number(b.dataset.bildHauptbild)))
    );
    this.shadowRoot.querySelector("[data-add-external-url]")?.addEventListener("click", () => {
      const input = this.shadowRoot.querySelector("[data-external-url]");
      this.addExternalUrl(input?.value);
      if (input) input.value = "";
    });
  }

  esc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[c])); }
  escAttr(s) { return this.esc(s).replace(/'/g, "&#39;"); }
}
customElements.define("hofkarte-panel", HofkartePanel);
