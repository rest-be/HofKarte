class HofkartePanel extends HTMLElement {
  constructor() {
    super();
    this.hass = null;
    this.items = [];
    this.editing = null;
    this.message = "";
    this.error = "";
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
    if (d.latitude !== null && d.latitude !== "" && (d.latitude < -90 || d.latitude > 90)) throw new Error("Latitude muss zwischen -90 und 90 liegen.");
    if (d.longitude !== null && d.longitude !== "" && (d.longitude < -180 || d.longitude > 180)) throw new Error("Longitude muss zwischen -180 und 180 liegen.");
    for (const row of d.oeffnungszeiten) if (!row.beginn || !row.ende || row.beginn === row.ende) throw new Error("Öffnungszeiten enthalten ungültige Zeiten.");
  }

  formData() {
    const f = this.shadowRoot.querySelector("form");
    const value = (name) => f.elements[name]?.value ?? "";
    const number = (name) => value(name) === "" ? null : Number(value(name));
    const data = this.clone(this.editing || this.empty());
    data.name = value("name"); data.beschreibung = value("beschreibung") || null;
    data.adresse = value("adresse") || null; data.plz = value("plz") || null;
    data.ort = value("ort") || null; data.land = value("land") || null;
    data.website = value("website") || null;
    data.latitude = number("latitude"); data.longitude = number("longitude");
    data.oeffnungszeiten = [...f.querySelectorAll("[data-opening]")].map(row => ({ wochentag: Number(row.dataset.day), beginn: row.querySelector("[name=beginn]").value, ende: row.querySelector("[name=ende]").value }));
    data.sonderoeffnungszeiten = [...f.querySelectorAll("[data-special]")].map(row => ({ datum_von: row.querySelector("[name=datum_von]").value, datum_bis: row.querySelector("[name=datum_bis]").value, geschlossen: row.querySelector("[name=geschlossen]").checked, beginn: row.querySelector("[name=beginn]").value || null, ende: row.querySelector("[name=ende]").value || null }));
    for (const field of ["kategorien", "zahlungsarten", "verkaufsarten", "merkmale"]) data[field] = this.lines(f.elements[field]?.value);
    data.produkte = this.products(f.elements.produkte?.value);
    return data;
  }

  lines(text) { return String(text || "").split("\n").map(x => x.trim()).filter(Boolean).map(name => ({ id: this.slug(name), name })); }
  products(text) { return String(text || "").split("\n").map(x => x.trim()).filter(Boolean).map(line => { const [name, cats = ""] = line.split("|"); return { id: this.slug(name), name: name.trim(), kategorie_ids: cats.split(",").map(x => this.slug(x)).filter(Boolean) }; }); }
  slug(s) { return String(s).toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "eintrag"; }

  async remove(id) {
    if (!confirm("Möchtest du diesen Hofladen wirklich löschen?")) return;
    try { await this.call("hofkarte/management/delete", { hofladen_id: id }); this.message = "Hofladen gelöscht."; await this.load(); }
    catch (err) { this.error = err?.message || "Löschen fehlgeschlagen."; this.render(); }
  }

  start(item = null) { this.error = ""; this.editing = item ? this.clone(item) : this.empty(); this.render(); }
  cancel() { this.editing = null; this.error = ""; this.render(); }

  openingRows() {
    const days = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"];
    const rows = this.editing?.oeffnungszeiten || [];
    return days.map((day, i) => rows.filter(x => Number(x.wochentag) === i + 1).map(x => ({ ...x, day: i + 1, label: day }))).flat();
  }

  render() {
    if (!this.shadowRoot) return;
    this.shadowRoot.innerHTML = `<style>
      :host{display:block;color:var(--primary-text-color);background:var(--primary-background-color);min-height:100%;font-family:var(--paper-font-body1_-_font-family,Roboto,sans-serif)}
      main{max-width:1200px;margin:0 auto;padding:24px}.top{display:flex;justify-content:space-between;align-items:center;gap:16px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-top:20px}.card{background:var(--ha-card-background,var(--card-background-color));border-radius:12px;padding:16px;box-shadow:var(--ha-card-box-shadow,0 1px 3px #0002)}.actions{display:flex;gap:8px;justify-content:flex-end;margin-top:16px}button{border:0;border-radius:8px;padding:9px 14px;background:var(--primary-color);color:var(--text-primary-color,#fff);cursor:pointer}button.secondary{background:var(--secondary-background-color);color:var(--primary-text-color)}button.danger{background:var(--error-color,#db4437)}label{display:block;margin:10px 0 5px;font-size:.9em}.fields{display:grid;grid-template-columns:1fr;gap:8px}.field-row{display:grid;grid-template-columns:1fr;gap:8px}.field-row.two{grid-template-columns:1fr 1fr}.field-row.two-wide{grid-template-columns:1fr 1fr}.field-row label{margin:0}input,textarea,select{box-sizing:border-box;width:100%;padding:9px;border:1px solid var(--divider-color);border-radius:7px;background:var(--primary-background-color);color:var(--primary-text-color)}textarea{min-height:100px}@media(max-width:700px){.field-row.two{grid-template-columns:1fr 1fr}.field-row.two-wide{grid-template-columns:1fr 1fr}}.opening{display:grid;grid-template-columns:120px 1fr 1fr auto;gap:8px;align-items:end;margin:8px 0}.special{display:grid;grid-template-columns:1fr 1fr 1fr 1fr auto;gap:8px;align-items:end;margin:8px 0}.notice{padding:10px;margin:12px 0;border-radius:8px;background:var(--info-color,#2196f3);color:white}.error{background:var(--error-color,#db4437)}.muted{color:var(--secondary-text-color)}h1,h2{font-weight:500}.pill{display:inline-block;padding:3px 8px;border-radius:12px;background:var(--secondary-background-color);margin:2px}.day{font-weight:500}
    </style><main>${this.editing ? this.editor() : this.list()}</main>`;
    this.bind();
  }

  list() {
    return `<div class="top"><div><h1>HofKarte</h1><div class="muted">Hofläden verwalten</div></div><button data-new>+ Neuer Hofladen</button></div>${this.message ? `<div class="notice">${this.message}</div>` : ""}${this.error ? `<div class="notice error">${this.error}</div>` : ""}<div class="grid">${this.items.length ? this.items.map(item => `<section class="card"><h2>${this.esc(item.name)}</h2><div>${this.esc([item.adresse,item.plz,item.ort,item.land].filter(Boolean).join(", "))}</div><div class="muted">${item.latitude ?? "–"}, ${item.longitude ?? "–"}</div><div class="actions"><button class="secondary" data-edit="${item.id}">Bearbeiten</button><button class="danger" data-delete="${item.id}">Löschen</button></div></section>`).join("") : `<section class="card"><h2>Noch keine Hofläden</h2><p>Erstelle den ersten Hofladen.</p></section>`}</div>`;
  }

  editor() {
    const d=this.editing; const o=this.openingRows();
    const days=["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"];
    const openings=days.map((day,i)=>{const rows=o.filter(x=>x.day===i+1); return rows.length?rows.map(x=>this.opening(x)):this.opening({day:i+1,label:day,beginn:"",ende:""})}).join("");
    const specials=(d.sonderoeffnungszeiten||[]).map(x=>`<div class="special" data-special><label>Von<input type=date name=datum_von value="${x.datum_von||""}"></label><label>Bis<input type=date name=datum_bis value="${x.datum_bis||""}"></label><label>Beginn<input type=time name=beginn value="${x.beginn||""}"></label><label>Ende<input type=time name=ende value="${x.ende||""}"></label><label>Geschlossen<input type=checkbox name=geschlossen ${x.geschlossen?"checked":""}></label><button type=button class=secondary data-remove-special>−</button></div>`).join("");
    const text=(field)=> (d[field]||[]).map(x=>x.name).join("\n"); const products=(d.produkte||[]).map(x=>`${x.name}${x.kategorie_ids?.length?"|"+x.kategorie_ids.join(","):""}`).join("\n");
    return `<div class="top"><div><h1>${d.id?"Hofladen bearbeiten":"Neuen Hofladen erstellen"}</h1><div class="muted">${d.id?this.esc(d.id):"Neue stabile ID wird beim Speichern erzeugt."}</div></div></div>${this.error?`<div class="notice error">${this.esc(this.error)}</div>`:""}<form><section class=card><h2>Stammdaten</h2><div class="fields"><div class="field-row">${this.input("Name","name",d.name,true)}</div><div class="field-row">${this.input("Beschreibung","beschreibung",d.beschreibung||"")}</div><div class="field-row">${this.input("Adresse","adresse",d.adresse||"")}</div><div class="field-row two">${this.input("PLZ","plz",d.plz||"")}${this.input("Ort","ort",d.ort||"")}</div><div class="field-row">${this.input("Land","land",d.land||"")}</div><div class="field-row two">${this.input("Latitude","latitude",d.latitude??"")} ${this.input("Longitude","longitude",d.longitude??"")}</div><div class="field-row">${this.input("Webseite","website",d.website||"")}</div></div></section><section class=card><h2>Öffnungszeiten</h2>${openings}<button type=button class=secondary data-add-opening>+ Intervall hinzufügen</button><h3>Sonderöffnungszeiten</h3><div id=specials>${specials}</div><button type=button class=secondary data-add-special>+ Sonderzeit hinzufügen</button></section><section class=card><h2>Sortiment und Eigenschaften</h2><p class=muted>Ein Eintrag pro Zeile. Produkte können optional mit Kategorie-IDs als <code>Produkt|kategorie-id</code> angegeben werden.</p>${this.area("Kategorien","kategorien",text("kategorien"))}${this.area("Produkte","produkte",products)}${this.area("Zahlungsarten","zahlungsarten",text("zahlungsarten"))}${this.area("Verkaufsarten","verkaufsarten",text("verkaufsarten"))}${this.area("Merkmale","merkmale",text("merkmale"))}</section><div class=actions><button type=button class=secondary data-cancel>Abbrechen</button><button type=submit>Speichern</button></div></form>`;
  }
  input(label,name,value,required=false){return `<label>${label}<input name="${name}" value="${this.esc(String(value))}" ${required?"required":""} ${name.includes("latitude")||name.includes("longitude")?"type=number step=any":""}></label>`}
  area(label,name,value){return `<label>${label}<textarea name="${name}">${this.esc(value)}</textarea></label>`}
  opening(x){return `<div class=opening data-opening data-day="${x.day}"><div class=day>${x.label}</div><label>Von<input type=time name=beginn value="${x.beginn||""}"></label><label>Bis<input type=time name=ende value="${x.ende||""}"></label><button type=button class=secondary data-remove-opening>−</button></div>`}
  bind(){
    this.shadowRoot.querySelector("[data-new]")?.addEventListener("click",()=>this.start());
    this.shadowRoot.querySelectorAll("[data-edit]").forEach(b=>b.addEventListener("click",()=>this.start(this.items.find(x=>x.id===b.dataset.edit))));
    this.shadowRoot.querySelectorAll("[data-delete]").forEach(b=>b.addEventListener("click",()=>this.remove(b.dataset.delete)));
    this.shadowRoot.querySelector("[data-cancel]")?.addEventListener("click",()=>this.cancel());
    this.shadowRoot.querySelector("form")?.addEventListener("submit",e=>{e.preventDefault();this.save()});
    this.shadowRoot.querySelectorAll("[data-remove-opening]").forEach(b=>b.addEventListener("click",()=>b.parentElement.remove()));
    this.shadowRoot.querySelectorAll("[data-remove-special]").forEach(b=>b.addEventListener("click",()=>b.parentElement.remove()));
    this.shadowRoot.querySelector("[data-add-opening]")?.addEventListener("click",()=>{const day=prompt("Wochentag 1=Montag … 7=Sonntag", "1"); const n=Number(day); if(n>=1&&n<=7){const names=["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"]; const el=document.createElement("div");el.innerHTML=this.opening({day:n,label:names[n-1],beginn:"",ende:""});this.shadowRoot.querySelector("form .card:nth-of-type(2)").append(el.firstElementChild);this.bind()}});
    this.shadowRoot.querySelector("[data-add-special]")?.addEventListener("click",()=>{const el=document.createElement("div");el.innerHTML=`<div class="special" data-special><label>Von<input type=date name=datum_von></label><label>Bis<input type=date name=datum_bis></label><label>Beginn<input type=time name=beginn></label><label>Ende<input type=time name=ende></label><label>Geschlossen<input type=checkbox name=geschlossen></label><button type=button class=secondary data-remove-special>−</button></div>`;this.shadowRoot.querySelector("#specials").append(el.firstElementChild);this.bind()});
  }
  esc(s){return String(s??"").replace(/[&<>\"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]))}
}
customElements.define("hofkarte-panel", HofkartePanel);
