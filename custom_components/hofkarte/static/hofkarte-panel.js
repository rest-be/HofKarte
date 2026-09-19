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

// --- Kartenansicht (Issue #2): Leaflet + OpenStreetMap ------------------
//
// Home Assistant bietet keine offizielle, für Custom Panels vorgesehene
// Möglichkeit, eine interaktive Karte mit beliebigen eigenen Markern
// einzubetten (nur die Lovelace-eigene, dashboard-interne Kartenkarte).
// Für eine eingebettete Karte mit mehreren gleichzeitig sichtbaren
// Markern wurde daher bewusst Leaflet + OpenStreetMap gewählt – eine
// dokumentierte, minimal-invasive Ausnahme vom Projektgrundsatz „keine
// neuen Abhängigkeiten“ (siehe docs/architecture.md):
// - keine Build-Pipeline/npm-Abhängigkeit im Repository nötig (reines
//   <script>/<link> von einem CDN, fest gepinnte Version, kein
//   „latest“);
// - kein API-Schlüssel und kein Kartendienst-Konto nötig
//   (OpenStreetMap-Kacheln sind ohne Registrierung nutzbar);
// - BSD-2-Clause-Lizenz, seit vielen Jahren aktiv gewartet, sehr
//   verbreitet (u. a. in zahlreichen Home-Assistant-HACS-Karten bereits
//   im Einsatz), kompakt (~40 KB gzip für JS und CSS zusammen).
// Wird bewusst erst beim ersten Öffnen der Kartenansicht nachgeladen
// (nicht beim Start des Panels), damit Nutzer:innen, die die
// Kartenansicht nie öffnen, auch nie eine Verbindung zum
// CDN/Kachel-Anbieter auslösen (siehe Datenschutz-Hinweise im Handbuch).
const LEAFLET_VERSION = "1.9.4";
const LEAFLET_JS_URL = `https://cdn.jsdelivr.net/npm/leaflet@${LEAFLET_VERSION}/dist/leaflet.js`;
const LEAFLET_CSS_URL = `https://cdn.jsdelivr.net/npm/leaflet@${LEAFLET_VERSION}/dist/leaflet.css`;

let leafletLoadPromise = null;

/** Leaflet (globale ``L``-Schnittstelle) einmalig per <script>-Tag von
 * einem CDN nachladen. Mehrfache Aufrufe (z. B. mehrfaches Öffnen der
 * Kartenansicht) liefern dasselbe Promise – kein doppeltes Nachladen.
 * Schlägt das Laden fehl (z. B. CDN nicht erreichbar), wird das
 * Promise verworfen, damit ein erneuter Versuch beim nächsten Öffnen
 * der Kartenansicht möglich ist, statt dauerhaft fehlzuschlagen. */
function ladeLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  if (leafletLoadPromise) return leafletLoadPromise;

  leafletLoadPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = LEAFLET_JS_URL;
    script.async = true;
    script.onload = () => (window.L ? resolve(window.L) : reject(new Error("Kartenbibliothek wurde geladen, stellt aber keine gültige Schnittstelle bereit.")));
    script.onerror = () => reject(new Error("Kartenbibliothek konnte nicht geladen werden (CDN nicht erreichbar?)."));
    document.head.appendChild(script);
  }).catch((err) => {
    leafletLoadPromise = null;
    throw err;
  });
  return leafletLoadPromise;
}

// Eigenes Marker-Icon statt Leaflets Standardbild (Issue #4): Leaflets
// automatische Pfaderkennung (Icon.Default._detectIconPath) erzeugt ein
// Sondierungselement im echten (globalen) document.body und fragt sonst
// document.querySelector('link[href$="leaflet.css"]') ab – beides sieht
// das <link rel="stylesheet"> nicht, das karteAnsicht() innerhalb des
// Shadow DOM dieser Komponente einbindet, da Shadow-DOM-Grenzen für
// Style-Zuordnung wie für querySelector() nicht durchquert werden.
// Ergebnis: Icon.Default.imagePath bleibt leer, das Marker-<img> zeigt
// eine defekte Bildkachel ("?"). Statt Leaflets Bild-basiertes
// Standard-Icon zu reparieren (z. B. über einen absoluten CDN-Bildpfad),
// wird hier bewusst ein eigenes, reines Inline-SVG-Icon (kein zusätzliches
// Bild, kein weiterer Netzwerk-Request) über L.divIcon() erzeugt – analog
// zum bereits im Panel verwendeten Symbolstil (vgl. Sidebar-Icon
// "mdi:store-edit"). Da das erzeugte Markup als Kind des Karten-Containers
// im selben Shadow Root landet, greifen die in styles() definierten
// Regeln (.karte-marker-*) zuverlässig – ganz ohne Shadow-DOM-Falle.
const KARTE_MARKER_GLYPH_PATH = "M20 4H4v2h16V4zm1 10v-2l-1-5H4l-1 5v2h1v6h10v-6h4v6h2v-6h1zm-9 4H6v-4h6v4z";

function erzeugeKarteMarkerIcon(L) {
  const html = `<svg class="karte-marker-svg" viewBox="0 0 32 42" width="32" height="42" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path class="karte-marker-pin" d="M16 0C7.163 0 0 7.163 0 16c0 11 16 26 16 26s16-15 16-26C32 7.163 24.837 0 16 0z"/>
    <g transform="translate(8,7) scale(0.8)"><path class="karte-marker-glyph" d="${KARTE_MARKER_GLYPH_PATH}"/></g>
  </svg>`;
  return L.divIcon({
    html,
    className: "karte-marker-icon",
    iconSize: [32, 42],
    iconAnchor: [16, 42],
    popupAnchor: [0, -38],
  });
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
    this.uebersichtsAnsicht = "kacheln"; // "kacheln" | "liste" | "karte" (Issue #1/#2)
    this.listenSortSpalte = null; // "name" | "adresse" | "geoeffnet"
    this.listenSortRichtung = "asc"; // "asc" | "desc"
    this.listenFilter = ""; // Freitextfilter in der Listenansicht
    this.karteNurGeoeffnet = false; // Checkbox "nur aktuell geöffnete Hofläden" (Issue #2)
    this.karteFehler = ""; // Fehlermeldung beim Laden der Kartenbibliothek (Issue #2)
    this._leafletMap = null; // aktive Leaflet-Karteninstanz, ausserhalb des normalen Render-Zyklus verwaltet
    this._leafletResizeHandler = null;
    this.auswahl = new Set(); // ausgewählte Hofladen-IDs für den Export (Issue #5)
    this.importDialog = null; // { eintraege, entscheidungen: Map<bestehende_id, "aktualisieren"|"ueberspringen"> } - nicht null während der Duplikat-Konfliktlösung eines Imports (Issue #5)
    this.attachShadow({ mode: "open" });
  }

  set hass(value) {
    this._hass = value;
    if (this.isConnected && !this._loaded) this.load();
  }
  get hass() { return this._hass; }

  connectedCallback() { this.render(); if (this.hass) this.load(); }
  disconnectedCallback() { this.teardownKarte(); }

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
    return { id: "", name: "", beschreibung: "", bemerkung: "", adresse: "", plz: "", ort: "", land: "", website: "", latitude: "", longitude: "", oeffnungszeiten: [], sonderoeffnungszeiten: [], angebote: [], zahlungsarten: [], bilder: [] };
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

    // Browser gewähren Geolocation-Zugriff ausschliesslich in einem
    // "sicheren Kontext" (HTTPS oder localhost). Wird Home Assistant
    // wie im lokalen Netzwerk üblich über einfaches http:// aufgerufen
    // (z. B. http://192.168.1.50:8123), lehnt der Browser den Zugriff
    // automatisch als PERMISSION_DENIED ab, OHNE jemals einen
    // Freigabe-Dialog anzuzeigen. Das führte bisher fälschlich zur
    // Meldung "Standortzugriff wurde verweigert", obwohl der Nutzer nie
    // gefragt wurde und in seinem Browser ganz allgemein
    // Standortzugriffe erlaubt haben kann. Diese Prüfung unterscheidet
    // den Fall klar von einer tatsächlichen Ablehnung durch die
    // Nutzerin/den Nutzer.
    if (!window.isSecureContext) {
      this.deviceDistanceStatus = "Standortermittlung erfordert eine sichere Verbindung (HTTPS) oder den Aufruf über localhost.";
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
    data.bemerkung = value("bemerkung") || null;
    data.adresse = value("adresse") || null; data.plz = value("plz") || null;
    data.ort = value("ort") || null; data.land = value("land") || null;
    data.website = value("website") || null;
    const koordinaten = this.resolveCoordinates(f);
    data.latitude = koordinaten.latitude; data.longitude = koordinaten.longitude;
    data.oeffnungszeiten = this.readOpeningHours(f);
    data.sonderoeffnungszeiten = [...f.querySelectorAll("[data-special]")].map(row => ({ datum_von: row.querySelector("[name=datum_von]").value, datum_bis: row.querySelector("[name=datum_bis]").value, geschlossen: row.querySelector("[name=geschlossen]").checked, beginn: row.querySelector("[name=beginn]").value || null, ende: row.querySelector("[name=ende]").value || null }));
    for (const field of ["angebote", "zahlungsarten"]) data[field] = this.lines(f.elements[field]?.value);
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
    // Eine bestehende Leaflet-Karteninstanz muss vor dem Ersetzen von
    // innerHTML explizit entfernt werden (map.remove()) – sie hält
    // sonst weiterhin Referenzen/Event-Listener (z. B. auf window)
    // gegen einen bereits aus dem DOM entfernten Container. Wird die
    // Kartenansicht danach erneut aufgebaut, übernimmt initKarte() das.
    this.teardownKarte();
    this.shadowRoot.innerHTML = `<style>${this.styles()}</style><main>${this.currentView()}</main>`;
    this.bind();
    if (!this.editing && !this.viewing && this.uebersichtsAnsicht === "karte" && this.items.length) {
      this.initKarte();
    }
  }

  /** Aktive Leaflet-Karteninstanz und den zugehörigen Resize-Handler
   * sauber entfernen (siehe render()/disconnectedCallback()). */
  teardownKarte() {
    if (this._leafletResizeHandler) {
      window.removeEventListener("resize", this._leafletResizeHandler);
      this._leafletResizeHandler = null;
    }
    if (this._leafletMap) {
      this._leafletMap.remove();
      this._leafletMap = null;
    }
  }

  /** Leaflet-Karte in den zuvor von karteAnsicht() gerenderten Container
   * einhängen. Wird bei jedem Render der Kartenansicht neu aufgebaut, da
   * render() den gesamten Shadow-DOM-Inhalt ersetzt (siehe teardownKarte(),
   * das die vorherige Instanz zuvor bereits entfernt hat). Popups nutzen
   * bewusst direkte Leaflet-Events statt der generischen bind()-Delegation
   * (Marker/Popups liegen ausserhalb des von render() erzeugten Markups). */
  async initKarte() {
    const container = this.shadowRoot.querySelector("[data-karte-container]");
    if (!container) return; // z. B. "keine Koordinaten"-Meldung statt Karte

    let L;
    try {
      L = await ladeLeaflet();
    } catch (err) {
      this.karteFehler = err?.message || "Kartenbibliothek konnte nicht geladen werden.";
      this.render();
      return;
    }

    // Zwischenzeitlich könnte die Ansicht gewechselt oder neu gerendert
    // worden sein, während die Bibliothek geladen wurde – dann diesen
    // (veralteten) Container nicht mehr verwenden.
    if (!this.shadowRoot.contains(container) || this.uebersichtsAnsicht !== "karte" || this.editing || this.viewing) return;
    this.karteFehler = "";

    const alleMitKoordinaten = this.items.filter((item) => isValidWgs84(item.latitude, item.longitude));
    const markerItems = this.karteNurGeoeffnet ? alleMitKoordinaten.filter((item) => item.geoeffnet === true) : alleMitKoordinaten;

    const map = L.map(container, { scrollWheelZoom: true });
    this._leafletMap = map;
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>-Mitwirkende',
    }).addTo(map);

    const markerIcon = erzeugeKarteMarkerIcon(L);
    for (const item of markerItems) {
      const marker = L.marker([item.latitude, item.longitude], { icon: markerIcon }).addTo(map);
      marker.bindPopup(`<div class="karte-popup"><strong>${this.esc(item.name)}</strong><br><button type="button" class="link-button" data-karte-view>Zur Detailansicht</button></div>`);
      marker.on("popupopen", (e) => {
        e.popup.getElement()?.querySelector("[data-karte-view]")?.addEventListener("click", () => this.view(item));
      });
    }

    if (markerItems.length === 1) {
      map.setView([markerItems[0].latitude, markerItems[0].longitude], 14);
    } else if (markerItems.length > 1) {
      map.fitBounds(markerItems.map((item) => [item.latitude, item.longitude]), { padding: [24, 24] });
    } else {
      // Der Geöffnet-Filter ergibt keine Treffer, es gibt aber
      // grundsätzlich Hofläden mit Koordinaten – sinnvollen Ausschnitt
      // über alle vorhandenen Koordinaten zeigen statt einer
      // Default-Weltkarte.
      map.fitBounds(alleMitKoordinaten.map((item) => [item.latitude, item.longitude]), { padding: [24, 24] });
    }

    this._leafletResizeHandler = () => map.invalidateSize();
    window.addEventListener("resize", this._leafletResizeHandler);
    // Absicherung für die erstmalige Grössenberechnung (z. B. bei einer
    // noch laufenden Sidebar-/Layout-Animation im selben Moment).
    setTimeout(() => map.invalidateSize(), 0);
  }

  currentView() {
    if (this.importDialog) return this.importKonflikte();
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
      .view-toggle{display:flex;gap:8px;margin-top:16px}
      .tile-card{display:flex;flex-direction:column;gap:6px}
      .tile-image{width:100%;height:140px;object-fit:cover;border-radius:8px;margin-bottom:4px}
      .tile-image-placeholder{display:flex;align-items:center;justify-content:center;background:var(--secondary-background-color);font-size:2.5em}
      .link-button{background:none;border:0;padding:0;color:var(--primary-color);font:inherit;font-weight:500;cursor:pointer;text-align:left}
      .link-button:hover{text-decoration:underline}
      .status-badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:.9em}
      .status-open{background:var(--success-color,#43a047);color:#fff}
      .status-closed{background:var(--error-color,#db4437);color:#fff}
      .status-unknown{background:var(--secondary-background-color);color:var(--secondary-text-color)}
      .export-import-row{display:flex;align-items:center;gap:10px;margin-top:16px;flex-wrap:wrap}
      .auswahl-checkbox{display:flex;align-items:center;gap:6px;font-size:.9em;margin-bottom:4px}
      .auswahl-checkbox input{width:auto;padding:0}
      .import-konflikt{margin-top:16px}
      .import-diff{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:8px}
      .import-diff-spalte h4{margin:0 0 6px}
      .import-diff-feld{display:flex;justify-content:space-between;gap:8px;padding:4px 0;border-bottom:1px solid var(--divider-color);font-size:.9em}
      .import-diff-feld .diff-label{color:var(--secondary-text-color);flex:0 0 auto}
      .diff-alt{background:color-mix(in srgb, var(--error-color,#db4437) 12%, transparent)}
      .diff-neu{background:color-mix(in srgb, var(--success-color,#43a047) 12%, transparent)}
      @media(max-width:700px){.import-diff{grid-template-columns:1fr}}
      .list-filter{margin-top:16px}
      .list-filter input{max-width:360px}
      .table-scroll{overflow-x:auto;margin-top:12px}
      .hoflaeden-table{width:100%;border-collapse:collapse;background:var(--ha-card-background,var(--card-background-color));border-radius:12px;overflow:hidden}
      .hoflaeden-table th,.hoflaeden-table td{padding:10px 14px;text-align:left;border-bottom:1px solid var(--divider-color)}
      .hoflaeden-table tr:last-child td{border-bottom:0}
      .table-sort{background:none;border:0;padding:0;font:inherit;font-weight:600;color:var(--primary-text-color);cursor:pointer;white-space:nowrap}
      .karte-filter-row{margin-top:16px}
      .karte-filter-row label{display:flex;align-items:center;gap:8px;margin:0;font-size:.95em;font-weight:normal}
      .karte-filter-row input[type=checkbox]{width:auto;padding:0}
      .karte-container{height:480px;border-radius:12px;margin-top:12px;background:var(--secondary-background-color)}
      .karte-empty{margin-top:20px}
      .karte-marker-icon{background:transparent;border:0}
      .karte-marker-svg{display:block}
      .karte-marker-pin{fill:var(--primary-color,#db4437);filter:drop-shadow(0 1px 2px rgba(0,0,0,.35))}
      .karte-marker-glyph{fill:#fff}
      .karte-popup{font-size:.95em}
      .karte-popup button{margin-top:6px}
      @media(max-width:700px){.karte-container{height:360px}}
      .card{background:var(--ha-card-background,var(--card-background-color));border-radius:12px;padding:16px;box-shadow:var(--ha-card-box-shadow,0 1px 3px #0002)}
      form > section.card{margin-bottom:20px}
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
      .interval-row input[type=time]{max-width:140px}
      .special input[type=time]{max-width:140px}
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

  /** Einheitliche Statusanzeige "geöffnet/geschlossen/unbekannt" – nutzt
   * das serverseitig berechnete Feld `geoeffnet` (siehe management.py),
   * keine eigene Öffnungszeiten-Berechnung in JavaScript (Issue #1). */
  geoeffnetBadge(geoeffnet) {
    if (geoeffnet === true) return `<span class="status-badge status-open">🟢 Geöffnet</span>`;
    if (geoeffnet === false) return `<span class="status-badge status-closed">🔴 Geschlossen</span>`;
    return `<span class="status-badge status-unknown">Unbekannt</span>`;
  }

  list() {
    const umschalter = `<div class="view-toggle">
      <button type="button" class="${this.uebersichtsAnsicht === "kacheln" ? "" : "secondary"}" data-ansicht="kacheln">🔲 Kacheln</button>
      <button type="button" class="${this.uebersichtsAnsicht === "liste" ? "" : "secondary"}" data-ansicht="liste">📋 Liste</button>
      <button type="button" class="${this.uebersichtsAnsicht === "karte" ? "" : "secondary"}" data-ansicht="karte">🗺️ Karte</button>
    </div>`;
    const inhalt = !this.items.length
      ? `<section class="card"><h2>Noch keine Hofläden</h2><p>Erstelle den ersten Hofladen.</p></section>`
      : (this.uebersichtsAnsicht === "liste" ? this.listTable() : this.uebersichtsAnsicht === "karte" ? this.karteAnsicht() : this.listGrid());
    // Mehrfachauswahl (Checkboxen) sowie Export/Import gibt es bewusst
    // nur in Kacheln- und Listenansicht (Issue #5) - in der Kartenansicht
    // fehlt dafür ein sinnvoller Anwendungsfall.
    const exportImportLeiste = this.items.length && this.uebersichtsAnsicht !== "karte"
      ? `<div class="export-import-row">
          <span class="muted">${this.auswahl.size} ausgewählt</span>
          <button type="button" class="secondary" data-auswahl-alle>Alle auswählen</button>
          <button type="button" class="secondary" data-auswahl-keine>Auswahl aufheben</button>
          <button type="button" class="secondary" data-export ${this.auswahl.size ? "" : "disabled"}>⬇️ Export</button>
          <button type="button" class="secondary" data-import-start>⬆️ Import</button>
          <input type="file" accept="application/json" data-import-input hidden>
        </div>`
      : "";

    return `<div class="top"><div><h1>HofKarte</h1><div class="muted">Hofläden verwalten</div></div><button data-new>+ Neuer Hofladen</button></div>${this.message ? `<div class="notice">${this.esc(this.message)}</div>` : ""}${this.error ? `<div class="notice error">${this.esc(this.error)}</div>` : ""}${this.items.length ? umschalter : ""}${exportImportLeiste}${inhalt}`;
  }

  listGrid() {
    return `<div class="grid">${this.items.map(item => this.listCard(item)).join("")}</div>`;
  }

  listCard(item) {
    const adresse = [item.adresse, item.plz, item.ort, item.land].filter(Boolean).join(", ");
    const bildHtml = item.hauptbild_url
      ? `<img class="tile-image" src="${this.escAttr(item.hauptbild_url)}" alt="${this.escAttr(item.name)}" loading="lazy">`
      : `<div class="tile-image tile-image-placeholder" aria-hidden="true">🏬</div>`;

    return `<section class="card tile-card">
      <label class="auswahl-checkbox"><input type="checkbox" data-auswahl="${item.id}" ${this.auswahl.has(item.id) ? "checked" : ""}> Auswählen</label>
      ${bildHtml}
      <h2><button type="button" class="link-button" data-view="${item.id}">${this.esc(item.name)}</button></h2>
      ${adresse ? `<div>${this.esc(adresse)}</div>` : ""}
      ${this.websiteLinkHtml(item.website)}
      <div>${this.geoeffnetBadge(item.geoeffnet)}</div>
      <div class="coord-actions">${this.mapButton(item.latitude, item.longitude)}</div>
      <div class="actions">
        <button class="secondary" data-view="${item.id}">Details</button>
        <button class="secondary" data-edit="${item.id}">Bearbeiten</button>
        <button class="danger" data-delete="${item.id}">Löschen</button>
      </div>
    </section>`;
  }

  /** Sortierte, gefilterte Zeilen für die Listenansicht (rein
   * clientseitig – kein neuer Backend-Endpunkt nötig, siehe Issue #1). */
  sortierteGefilterteItems() {
    const filterText = this.listenFilter.trim().toLowerCase();
    let ergebnis = !filterText ? this.items : this.items.filter(item => {
      const adresse = [item.adresse, item.plz, item.ort, item.land].filter(Boolean).join(", ");
      return item.name.toLowerCase().includes(filterText) || adresse.toLowerCase().includes(filterText);
    });

    if (this.listenSortSpalte) {
      const spalte = this.listenSortSpalte;
      const richtung = this.listenSortRichtung === "asc" ? 1 : -1;
      const wert = (item) => {
        if (spalte === "adresse") return [item.adresse, item.plz, item.ort, item.land].filter(Boolean).join(", ").toLowerCase();
        if (spalte === "geoeffnet") return item.geoeffnet === true ? 2 : item.geoeffnet === false ? 1 : 0;
        return String(item[spalte] || "").toLowerCase();
      };
      ergebnis = [...ergebnis].sort((a, b) => {
        const wa = wert(a), wb = wert(b);
        return wa < wb ? -richtung : wa > wb ? richtung : 0;
      });
    }
    return ergebnis;
  }

  listTable() {
    const zeilen = this.sortierteGefilterteItems();
    const pfeil = (spalte) => this.listenSortSpalte === spalte ? (this.listenSortRichtung === "asc" ? " ▲" : " ▼") : "";

    return `<div class="list-filter">
        <input type="text" data-listen-filter placeholder="Nach Name oder Adresse filtern …" value="${this.escAttr(this.listenFilter)}">
      </div>
      <div class="table-scroll">
        <table class="hoflaeden-table">
          <thead>
            <tr>
              <th>Auswahl</th>
              <th><button type="button" class="table-sort" data-sort="name">Name${pfeil("name")}</button></th>
              <th><button type="button" class="table-sort" data-sort="adresse">Adresse${pfeil("adresse")}</button></th>
              <th><button type="button" class="table-sort" data-sort="geoeffnet">Status${pfeil("geoeffnet")}</button></th>
              <th>Karte</th>
            </tr>
          </thead>
          <tbody>
            ${zeilen.length ? zeilen.map(item => {
              const adresse = [item.adresse, item.plz, item.ort, item.land].filter(Boolean).join(", ");
              return `<tr>
                <td><input type="checkbox" data-auswahl="${item.id}" ${this.auswahl.has(item.id) ? "checked" : ""} aria-label="${this.escAttr(item.name)} auswählen"></td>
                <td><button type="button" class="link-button" data-view="${item.id}">${this.esc(item.name)}</button></td>
                <td>${this.esc(adresse) || '<span class="muted">–</span>'}</td>
                <td>${this.geoeffnetBadge(item.geoeffnet)}</td>
                <td>${this.mapButton(item.latitude, item.longitude)}</td>
              </tr>`;
            }).join("") : `<tr><td colspan="5" class="muted">Keine Treffer für diesen Filter.</td></tr>`}
          </tbody>
        </table>
      </div>`;
  }

  /** Markup der Kartenansicht (Issue #2). Die eigentliche Leaflet-Karte
   * wird erst nach dem Rendern in initKarte() in den hier erzeugten,
   * noch leeren Container eingehängt (siehe render()). Ohne einen
   * einzigen Hofladen mit gültigen Koordinaten wird gar nicht erst
   * versucht, eine Karte aufzubauen – stattdessen eine klare Meldung. */
  karteAnsicht() {
    const alleMitKoordinaten = this.items.filter((item) => isValidWgs84(item.latitude, item.longitude));
    if (!alleMitKoordinaten.length) {
      return `<section class="card karte-empty"><p class="muted">Keine Hofläden mit hinterlegten Koordinaten vorhanden – es kann keine Karte angezeigt werden.</p></section>`;
    }

    const gefiltert = this.karteNurGeoeffnet ? alleMitKoordinaten.filter((item) => item.geoeffnet === true) : alleMitKoordinaten;

    return `<link rel="stylesheet" href="${LEAFLET_CSS_URL}">
      <div class="karte-filter-row">
        <label><input type="checkbox" data-karte-nur-geoeffnet ${this.karteNurGeoeffnet ? "checked" : ""}> Nur aktuell geöffnete Hofläden anzeigen</label>
      </div>
      ${this.karteFehler ? `<div class="notice error">${this.esc(this.karteFehler)}</div>` : ""}
      <div class="karte-container" data-karte-container></div>
      ${!gefiltert.length ? `<p class="muted" style="margin-top:8px">Kein Hofladen entspricht aktuell diesem Filter.</p>` : ""}`;
  }

  // --- Export/Import (Issue #5) ------------------------------------------
  //
  // Export läuft vollständig clientseitig über einen Blob-Download - kein
  // neuer Server-Endpunkt nötig. Import ist zweistufig: zuerst eine rein
  // lesende Vorschau ("import_preview"), die Struktur validiert und
  // mögliche Duplikate ermittelt (serverseitig, siehe management.py -
  // Name/Adresse-Abgleich sowie die Validierungslogik sollen nicht ein
  // zweites Mal in JavaScript nachgebaut werden), danach - nach
  // Entscheidung über jedes gefundene Duplikat - der eigentliche Import
  // ("import_commit"). Das hält jegliche Fachlogik serverseitig; das
  // Frontend übernimmt hier bewusst nur Dateiauswahl/-lesen und die
  // Diff-/Dialog-Darstellung.

  /** Vom Server ergänzte, rein berechnete Felder (kein Teil von
   * models.Hofladen, siehe management.py:_serialize_hofladen) vor dem
   * Export entfernen - der Export soll exakt das interne Datenmodell
   * widerspiegeln, keine flüchtigen, zur Exportzeit gültigen Werte. */
  bereinigtFuerExport(item) {
    const { geoeffnet, hauptbild_url, ...rest } = item;
    return rest;
  }

  exportZeitstempel() {
    const jetzt = new Date();
    return jetzt.toISOString().slice(0, 19).replace(/[:T]/g, "-");
  }

  exportAuswahl() {
    if (!this.auswahl.size) return;
    const ausgewaehlt = this.items.filter((item) => this.auswahl.has(item.id));
    const bereinigt = ausgewaehlt.map((item) => this.bereinigtFuerExport(item));

    const blob = new Blob([JSON.stringify(bereinigt, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    try {
      const link = document.createElement("a");
      link.href = url;
      link.download = `hoflaeden-export-${this.exportZeitstempel()}.json`;
      link.click();
    } finally {
      URL.revokeObjectURL(url);
    }

    this.message = `${ausgewaehlt.length} Hofladen/Hofläden exportiert.`;
    this.error = "";
    this.render();
  }

  /** Datei-Auswahl für den Import verarbeiten: lesen, als JSON parsen und
   * strukturell auf oberster Ebene prüfen (muss eine nicht-leere Liste
   * von Objekten sein) - alles Weitere (Feldvalidierung je Hofladen,
   * Duplikaterkennung) übernimmt der Server (ws_import_preview). */
  async importDatei(file) {
    if (!file) return;
    this.error = "";
    this.message = "";

    let inhalt;
    try {
      inhalt = await file.text();
    } catch {
      this.error = "Die Datei konnte nicht gelesen werden.";
      this.render();
      return;
    }

    let daten;
    try {
      daten = JSON.parse(inhalt);
    } catch {
      this.error = "Die Datei enthält kein gültiges JSON.";
      this.render();
      return;
    }

    if (!Array.isArray(daten) || !daten.length) {
      this.error = "Die Datei muss eine JSON-Liste mit mindestens einem Hofladen enthalten.";
      this.render();
      return;
    }
    if (!daten.every((eintrag) => eintrag && typeof eintrag === "object" && !Array.isArray(eintrag))) {
      this.error = "Die Datei enthält ungültige Einträge (jeder Hofladen muss ein Objekt sein).";
      this.render();
      return;
    }

    try {
      const antwort = await this.call("hofkarte/management/import_preview", { hoflaeden: daten });
      this.starteKonfliktloesung(antwort.eintraege || []);
    } catch (err) {
      this.error = err?.message || "Die Datei konnte nicht importiert werden.";
      this.render();
    }
  }

  /** Entscheiden, ob überhaupt eine Konfliktlösung nötig ist: ohne
   * erkannte Duplikate wird direkt importiert, ohne unnötigen Dialog. */
  starteKonfliktloesung(eintraege) {
    const duplikate = eintraege.filter((eintrag) => eintrag.duplikat_von);
    if (!duplikate.length) {
      this.commitImport(eintraege.map((eintrag) => ({ hofladen: eintrag.hofladen, aktion: "neu" })));
      return;
    }
    this.importDialog = { eintraege, entscheidungen: new Map() };
    this.render();
  }

  /** Feldweiser Vergleich zwischen bestehendem und importiertem
   * Hofladen für die Diff-Darstellung im Konfliktdialog. Sammlungsfelder
   * (Öffnungszeiten, Angebote, ...) werden bewusst nur über ihre Anzahl
   * verglichen statt vollständig aufgelistet - genug, um auf einen
   * Blick zu erkennen, ob sich etwas geändert hat, ohne den Dialog mit
   * verschachtelten Detailtabellen zu überladen. */
  diffFelder(bestehend, importiert) {
    const skalar = [
      ["name", "Name"], ["adresse", "Adresse"], ["plz", "PLZ"], ["ort", "Ort"], ["land", "Land"],
      ["website", "Website"], ["beschreibung", "Beschreibung"], ["bemerkung", "Bemerkung"],
      ["latitude", "Latitude"], ["longitude", "Longitude"],
    ];
    const sammlungen = [
      ["oeffnungszeiten", "Öffnungszeiten"], ["sonderoeffnungszeiten", "Sonderöffnungszeiten"],
      ["angebote", "Angebote"], ["zahlungsarten", "Zahlungsarten"], ["bilder", "Bilder"],
    ];

    const zeile = (label, altWert, neuWert) => ({
      label,
      alt: altWert === null || altWert === undefined || altWert === "" ? "–" : String(altWert),
      neu: neuWert === null || neuWert === undefined || neuWert === "" ? "–" : String(neuWert),
      unterschiedlich: String(altWert ?? "") !== String(neuWert ?? ""),
    });

    return [
      ...skalar.map(([feld, label]) => zeile(label, bestehend[feld], importiert[feld])),
      ...sammlungen.map(([feld, label]) => zeile(
        label,
        `${(bestehend[feld] || []).length} Einträge`,
        `${(importiert[feld] || []).length} Einträge`,
      )),
    ];
  }

  importKonfliktEintrag(eintrag) {
    const bestehend = eintrag.bestehend;
    const importiert = eintrag.hofladen;
    const entscheidung = this.importDialog.entscheidungen.get(eintrag.duplikat_von) || "";
    const felder = this.diffFelder(bestehend, importiert);
    const feldZeile = (spalte) => felder.map((f) => `<div class="import-diff-feld${f.unterschiedlich ? ` diff-${spalte}` : ""}"><span class="diff-label">${this.esc(f.label)}</span><span>${this.esc(spalte === "alt" ? f.alt : f.neu)}</span></div>`).join("");

    return `<section class="card import-konflikt">
      <h3>Mögliches Duplikat: ${this.esc(importiert.name)}</h3>
      <div class="import-diff">
        <div class="import-diff-spalte"><h4>Bestehend</h4>${feldZeile("alt")}</div>
        <div class="import-diff-spalte"><h4>Importiert</h4>${feldZeile("neu")}</div>
      </div>
      <div class="actions">
        <button type="button" class="${entscheidung === "aktualisieren" ? "" : "secondary"}" data-import-entscheidung="${eintrag.duplikat_von}" data-import-aktion="aktualisieren">Aktualisieren</button>
        <button type="button" class="${entscheidung === "ueberspringen" ? "" : "secondary"}" data-import-entscheidung="${eintrag.duplikat_von}" data-import-aktion="ueberspringen">Beibehalten</button>
      </div>
    </section>`;
  }

  importKonflikte() {
    const { eintraege, entscheidungen } = this.importDialog;
    const duplikate = eintraege.filter((eintrag) => eintrag.duplikat_von);
    const neue = eintraege.filter((eintrag) => !eintrag.duplikat_von);
    const alleEntschieden = duplikate.every((eintrag) => entscheidungen.has(eintrag.duplikat_von));

    return `<div class="top"><div><h1>Import: Duplikate prüfen</h1><div class="muted">${neue.length} neue${neue.length === 1 ? "r Hofladen wird" : " Hofläden werden"} direkt importiert, ${duplikate.length} ${duplikate.length === 1 ? "bestehender Hofladen wurde" : "bestehende Hofläden wurden"} als mögliches Duplikat erkannt.</div></div></div>
      ${this.error ? `<div class="notice error">${this.esc(this.error)}</div>` : ""}
      <div class="actions" style="margin:16px 0">
        <button type="button" class="secondary" data-import-alle="aktualisieren">Alle aktualisieren</button>
        <button type="button" class="secondary" data-import-alle="ueberspringen">Alle beibehalten</button>
      </div>
      ${duplikate.map((eintrag) => this.importKonfliktEintrag(eintrag)).join("")}
      <div class="actions" style="margin-top:20px">
        <button type="button" class="secondary" data-import-abbrechen>Abbrechen</button>
        <button type="button" data-import-abschliessen>Import abschliessen${alleEntschieden ? "" : " (unentschiedene Duplikate werden beibehalten)"}</button>
      </div>`;
  }

  schliesseImportAb() {
    const { eintraege, entscheidungen } = this.importDialog;
    const eintraegeFuerCommit = eintraege.map((eintrag) => {
      if (!eintrag.duplikat_von) return { hofladen: eintrag.hofladen, aktion: "neu" };
      // Unentschiedene Duplikate werden nicht stillschweigend
      // überschrieben, sondern sicher beibehalten (kein Datenverlust
      // ohne explizite Bestätigung).
      const aktion = entscheidungen.get(eintrag.duplikat_von) || "ueberspringen";
      return { hofladen: eintrag.hofladen, aktion, bestehende_id: eintrag.duplikat_von };
    });
    this.commitImport(eintraegeFuerCommit);
  }

  async commitImport(eintraege) {
    try {
      const antwort = await this.call("hofkarte/management/import_commit", { eintraege });
      this.importDialog = null;
      this.auswahl.clear();
      this.error = "";
      this.message = `Import abgeschlossen: ${antwort.importiert} neu, ${antwort.aktualisiert} aktualisiert, ${antwort.uebersprungen} übersprungen.`;
      await this.load();
    } catch (err) {
      this.error = err?.message || "Der Import konnte nicht abgeschlossen werden.";
      this.render();
    }
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
      ${d.bemerkung ? `<section class="card detail-section"><h3>Bemerkung</h3><div>${this.esc(d.bemerkung)}</div></section>` : ""}

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

      ${(d.bilder || []).length ? `<section class="card detail-section"><h3>Bilder</h3><div class="thumbs">${d.bilder.map(b => `<img src="${this.escAttr(b.url)}" alt="${this.escAttr(b.beschreibung || d.name)}" loading="lazy">`).join("")}</div></section>` : ""}
    `;
  }

  /** Webseite als anklickbarer Link – kein UI-Block, wenn keine/keine
   * gültige URL hinterlegt ist (siehe Anforderung: kein leerer Bereich). */
  /** Kernlogik für die Website-Darstellung (nur der Link/Hinweis selbst,
   * ohne umgebende Sektion) – wird sowohl von der Detailansicht als auch
   * von Kacheln/Tabellenzeilen verwendet, um Validierung/Linkaufbau
   * nicht zu duplizieren. */
  websiteLinkHtml(website) {
    if (!website || !website.trim()) return "";
    const trimmed = website.trim();
    const href = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
    if (!this.isPlausibleUrl(trimmed)) {
      return `<span class="muted">Ungültige Webseiten-Adresse: ${this.esc(trimmed)}</span>`;
    }
    return `<a class="website-link" href="${this.escAttr(href)}" target="_blank" rel="noopener noreferrer">🔗 ${this.esc(trimmed)}</a>`;
  }

  websiteLinkBlock(website) {
    const inhalt = this.websiteLinkHtml(website);
    if (!inhalt) return "";
    return `<section class="card detail-section"><h3>Webseite</h3>${inhalt}</section>`;
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

  /** Angebote in der Detailansicht – ersetzt die früher getrennten
   * Abschnitte "Kategorien"/"Produkte". Seit der Vereinfachung auf eine
   * schlichte Namensliste ohne Gruppierung reduziert (siehe CHANGELOG)
   * - daher eine einfache Weiterleitung an detailPillSection. */
  detailAngeboteSection(angebote) {
    return this.detailPillSection("Angebote", angebote);
  }

  // --- Editor ------------------------------------------------------------

  editor() {
    const d = this.editing;
    const latValue = (d.latitude != null && d.latitude !== "") ? d.latitude : "";
    const lonValue = (d.longitude != null && d.longitude !== "") ? d.longitude : "";

    const specials = (d.sonderoeffnungszeiten || []).map(x => `<div class="special" data-special><label>Von<input type=date name=datum_von value="${x.datum_von || ""}"></label><label>Bis<input type=date name=datum_bis value="${x.datum_bis || ""}"></label><label>Beginn<input type=time name=beginn value="${x.beginn || ""}"></label><label>Ende<input type=time name=ende value="${x.ende || ""}"></label><label>Geschlossen<input type=checkbox name=geschlossen ${x.geschlossen ? "checked" : ""}></label><button type=button class=secondary data-remove-special>−</button></div>`).join("");
    const text = (field) => (d[field] || []).map(x => x.name).join("\n");
    const angeboteText = (d.angebote || []).map(x => x.name).join("\n");

    return `<div class="top"><div><h1>${d.id ? "Hofladen bearbeiten" : "Neuen Hofladen erstellen"}</h1><div class="muted">${d.id ? this.esc(d.id) : "Neue stabile ID wird beim Speichern erzeugt."}</div></div></div>
      ${this.error ? `<div class="notice error">${this.esc(this.error)}</div>` : ""}
      <form>
        <section class=card>
          <h2>Allgemeine Informationen</h2>
          <div class="fields">
            <div class="field-row">${this.input("Name", "name", d.name, true)}</div>
            <div class="field-row">${this.input("Beschreibung", "beschreibung", d.beschreibung || "")}</div>
            ${this.area("Bemerkung", "bemerkung", d.bemerkung || "")}
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
          <h2>Kontakt &amp; Webseite</h2>
          <div class="fields">
            <div class="field-row">${this.input("Webseite", "website", d.website || "")}</div>
          </div>
        </section>

        <section class=card>
          <h2>Öffnungszeiten</h2>
          ${this.openingHoursEditor(d.oeffnungszeiten || [])}
          <h3>Sonderöffnungszeiten</h3>
          <div id=specials>${specials}</div>
          <button type=button class=secondary data-add-special>+ Sonderzeit hinzufügen</button>
        </section>

        <section class=card>
          <h2>Angebote und Zahlungsarten</h2>
          <p class=muted>Ein Eintrag pro Zeile.</p>
          ${this.area("Angebote", "angebote", angeboteText)}
          ${this.area("Zahlungsarten", "zahlungsarten", text("zahlungsarten"))}
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
    this.shadowRoot.querySelectorAll("[data-ansicht]").forEach(b =>
      b.addEventListener("click", () => { this.uebersichtsAnsicht = b.dataset.ansicht; this.render(); })
    );
    this.shadowRoot.querySelectorAll("[data-sort]").forEach(b =>
      b.addEventListener("click", () => {
        const spalte = b.dataset.sort;
        if (this.listenSortSpalte === spalte) {
          this.listenSortRichtung = this.listenSortRichtung === "asc" ? "desc" : "asc";
        } else {
          this.listenSortSpalte = spalte;
          this.listenSortRichtung = "asc";
        }
        this.render();
      })
    );
    this.shadowRoot.querySelector("[data-karte-nur-geoeffnet]")?.addEventListener("change", (e) => {
      this.karteNurGeoeffnet = e.target.checked;
      this.render();
    });
    // --- Export/Import (Issue #5) ---
    this.shadowRoot.querySelectorAll("[data-auswahl]").forEach((cb) => cb.addEventListener("change", (e) => {
      const id = cb.dataset.auswahl;
      if (e.target.checked) this.auswahl.add(id); else this.auswahl.delete(id);
      this.render();
    }));
    this.shadowRoot.querySelector("[data-auswahl-alle]")?.addEventListener("click", () => {
      this.items.forEach((item) => this.auswahl.add(item.id));
      this.render();
    });
    this.shadowRoot.querySelector("[data-auswahl-keine]")?.addEventListener("click", () => {
      this.auswahl.clear();
      this.render();
    });
    this.shadowRoot.querySelector("[data-export]")?.addEventListener("click", () => this.exportAuswahl());
    this.shadowRoot.querySelector("[data-import-start]")?.addEventListener("click", () => {
      this.shadowRoot.querySelector("[data-import-input]")?.click();
    });
    this.shadowRoot.querySelector("[data-import-input]")?.addEventListener("change", (e) => {
      const file = e.target.files?.[0];
      this.importDatei(file);
      e.target.value = ""; // erlaubt erneuten Import derselben Datei
    });
    this.shadowRoot.querySelectorAll("[data-import-entscheidung]").forEach((b) => b.addEventListener("click", () => {
      this.importDialog.entscheidungen.set(b.dataset.importEntscheidung, b.dataset.importAktion);
      this.render();
    }));
    this.shadowRoot.querySelectorAll("[data-import-alle]").forEach((b) => b.addEventListener("click", () => {
      const aktion = b.dataset.importAlle;
      for (const eintrag of this.importDialog.eintraege) {
        if (eintrag.duplikat_von) this.importDialog.entscheidungen.set(eintrag.duplikat_von, aktion);
      }
      this.render();
    }));
    this.shadowRoot.querySelector("[data-import-abbrechen]")?.addEventListener("click", () => {
      this.importDialog = null;
      this.render();
    });
    this.shadowRoot.querySelector("[data-import-abschliessen]")?.addEventListener("click", () => this.schliesseImportAb());

    this.shadowRoot.querySelector("[data-listen-filter]")?.addEventListener("input", (e) => {
      this.listenFilter = e.target.value;
      this.render();
      // Fokus geht beim Re-Render verloren (innerHTML wird neu aufgebaut) -
      // direkt danach wiederherstellen, damit Weitertippen ohne erneuten
      // Klick möglich ist.
      const neuesFeld = this.shadowRoot.querySelector("[data-listen-filter]");
      if (neuesFeld) { neuesFeld.focus(); neuesFeld.selectionStart = neuesFeld.selectionEnd = neuesFeld.value.length; }
    });
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
      const neueZeile = el.firstElementChild;
      container.insertBefore(neueZeile, b);
      // Bewusst KEIN erneuter bind()-Aufruf: render() wird hier
      // nicht durchlaufen (Formularzustand/Fokus soll erhalten bleiben,
      // siehe Klassenkommentar oben), der restliche DOM existiert also
      // unverändert weiter. Ein erneuter bind()-Aufruf würde auf allen
      // bereits vorhandenen Elementen - u. a. diesem "+ weiteres
      // Intervall"-Button selbst sowie dem Formular-submit-Handler -
      // einen zusätzlichen, doppelten Listener registrieren (bind()
      // entfernt keine bestehenden Listener). Behobener Bug: Jeder
      // weitere Klick verdoppelte dadurch die Anzahl neu eingefügter
      // Zeilen, und beim Abschicken des Formulars löste der mehrfach
      // gebundene submit-Handler this.save() ebenso mehrfach aus - was
      // bei einem neuen, noch ungespeicherten Hofladen (ohne id) zu
      // mehreren, inhaltlich identischen Hofladen-Einträgen führte, da
      // ws_save() für jeden Aufruf ohne id eine eigene, neue id vergibt.
      // Stattdessen wird hier gezielt nur der "entfernen"-Button der
      // neu eingefügten Zeile selbst verkabelt.
      neueZeile.querySelector("[data-remove-interval]")?.addEventListener("click", () => neueZeile.remove());
    }));
    this.shadowRoot.querySelectorAll("[data-remove-interval]").forEach(b => b.addEventListener("click", () => b.parentElement.remove()));

    this.shadowRoot.querySelectorAll("[data-remove-special]").forEach(b => b.addEventListener("click", () => b.parentElement.remove()));
    this.shadowRoot.querySelector("[data-add-special]")?.addEventListener("click", () => {
      const el = document.createElement("div");
      el.innerHTML = `<div class="special" data-special><label>Von<input type=date name=datum_von></label><label>Bis<input type=date name=datum_bis></label><label>Beginn<input type=time name=beginn></label><label>Ende<input type=time name=ende></label><label>Geschlossen<input type=checkbox name=geschlossen></label><button type=button class=secondary data-remove-special>−</button></div>`;
      const neueZeile = el.firstElementChild;
      this.shadowRoot.querySelector("#specials").append(neueZeile);
      // Derselbe Grund wie beim "+ weiteres Intervall"-Handler oben:
      // gezielt nur den neu eingefügten "entfernen"-Button verkabeln,
      // statt erneut bind() über den gesamten, unverändert
      // bestehenden DOM laufen zu lassen (kein doppeltes Binden des
      // "+ Sonderzeit hinzufügen"-Buttons bzw. des Formular-submit-
      // Handlers).
      neueZeile.querySelector("[data-remove-special]")?.addEventListener("click", () => neueZeile.remove());
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
