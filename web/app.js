// What camwall's pages share: talking to the server, the theme, the bar along the top, the camera list, places.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(props)) {
    if (name === 'dataset') Object.assign(node.dataset, value);
    else if (name.startsWith('aria') || name === 'role' || name === 'for') node.setAttribute(name.replace(/^aria(\w)/, (_, c) => `aria-${c.toLowerCase()}`), value);
    else node[name] = value;
  }
  node.append(...children.filter((c) => c !== null && c !== undefined && c !== false));
  return node;
}

const KINDS = { police: 'Police', ambulance: 'Ambulance', fire: 'Fire' };
const KIND_HELP = { police: 'a police car', ambulance: 'an ambulance', fire: 'a fire truck' };
const STATE_NAMES = {
  AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California', CO: 'Colorado', CT: 'Connecticut',
  DE: 'Delaware', DC: 'District of Columbia', FL: 'Florida', GA: 'Georgia', HI: 'Hawaii', ID: 'Idaho', IL: 'Illinois',
  IN: 'Indiana', IA: 'Iowa', KS: 'Kansas', KY: 'Kentucky', LA: 'Louisiana', ME: 'Maine', MD: 'Maryland',
  MA: 'Massachusetts', MI: 'Michigan', MN: 'Minnesota', MS: 'Mississippi', MO: 'Missouri', MT: 'Montana',
  NE: 'Nebraska', NV: 'Nevada', NH: 'New Hampshire', NJ: 'New Jersey', NM: 'New Mexico', NY: 'New York',
  NC: 'North Carolina', ND: 'North Dakota', OH: 'Ohio', OK: 'Oklahoma', OR: 'Oregon', PA: 'Pennsylvania',
  PR: 'Puerto Rico', RI: 'Rhode Island', SC: 'South Carolina', SD: 'South Dakota', TN: 'Tennessee', TX: 'Texas',
  UT: 'Utah', VT: 'Vermont', VA: 'Virginia', WA: 'Washington', WV: 'West Virginia', WI: 'Wisconsin', WY: 'Wyoming',
};
const US_BOUNDS = [[24.4, -125], [49.4, -66.9]];  // the lower 48, for a first look

// ---- the server ----

async function api(path, body) {
  const res = body === undefined ? await fetch(path, { cache: 'no-store' })
    : await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!res.ok) throw new Error((await res.text().catch(() => '')) || `The app answered ${res.status}`);
  return res.json();
}

// Every camera: [{ key, name, lat, lon, media (1 picture, 2 video, 3 both), state, online }].
async function loadCameras() {
  const { cameras, version } = await api('/api/cameras');
  const list = cameras.map(([key, name, lat, lon, media, state, online]) => ({ key, name, lat, lon, media, state, online: online === 1 }));
  list.version = version;
  return list;
}

const camUrl = (key) => `/cam/${encodeURIComponent(key)}`;
const hlsUrl = (key) => `/hls/${encodeURIComponent(key)}/index.m3u8`;
const mjpegUrl = (key) => `/mjpeg/${encodeURIComponent(key)}`;

// ---- the theme: as the settings say, remembered here so a page opens in it without a flash ----

function applyTheme(theme) {
  if (theme === 'dark' || theme === 'light') document.documentElement.dataset.theme = theme;
  else if (matchMedia('(prefers-color-scheme: dark)').matches) document.documentElement.dataset.theme = 'dark';
  else document.documentElement.dataset.theme = 'light';
  try { localStorage.setItem('camwall-theme', theme); } catch {}
}
try { applyTheme(localStorage.getItem('camwall-theme') || 'auto'); } catch { applyTheme('auto'); }
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
  let theme = 'auto';
  try { theme = localStorage.getItem('camwall-theme') || 'auto'; } catch {}
  if (theme === 'auto') applyTheme('auto');
});

// ---- the bar along the top ----

function topbar(current, ...extra) {
  const link = (href, text, page) => el('a', { href, textContent: text, ...(page === current ? { ariaCurrent: 'page' } : {}) });
  const bar = el('header', { className: 'topbar' },
    el('a', { className: 'brand', href: '/' }, el('img', { src: '/icon.svg', alt: '' }), 'camwall'),
    el('nav', {}, link('/', 'Wall', 'wall'), link('/cameras.html', 'Cameras', 'cameras'), link('/mine.html', 'My cameras', 'mine'),
      link('/settings.html', 'Settings', 'settings')),
    el('div', { className: 'grow' }), ...extra);
  document.body.prepend(bar);
  return bar;
}

function toast(text, ms = 3500) {
  const t = el('div', { className: 'toast', textContent: text, role: 'status' });
  document.body.append(t);
  setTimeout(() => t.remove(), ms);
}

// ---- distances ----

function kmBetween(lat1, lon1, lat2, lon2) {
  const r = Math.PI / 180;
  const a = Math.sin((lat2 - lat1) * r / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin((lon2 - lon1) * r / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(a));
}

function distanceText(km, units = 'mi') {
  const d = units === 'km' ? km : km / 1.609344;
  return `${d < 10 ? d.toFixed(1) : Math.round(d).toLocaleString()} ${units}`;
}

// ---- places: ZIP codes, towns and counties (Census gazetteer) ----

let placesData = null;
async function loadPlaces() {
  placesData ??= await api('/api/places');
  return placesData;
}

// The places matching what's been typed, best first: [{ label, state, lat, lon, kind }].
function findPlaces(text, limit = 8) {
  const q = text.trim().toLowerCase();
  if (!placesData || !q) return [];
  if (/^\d{5}$/.test(q)) {
    const zip = placesData.zips[q];
    if (!zip) return [];
    const state = zipState(q);
    const near = nearestPlace(zip[0], zip[1], state);
    return [{ label: `ZIP ${q}${near ? ` · ${near[0]}, ${near[1]}` : ''}`, short: near ? `${near[0]}, ${near[1]}` : `ZIP ${q}`,
      state: state ?? near?.[1] ?? null, lat: zip[0], lon: zip[1], kind: 'zip' }];
  }
  const [name, st] = q.split(/,\s*/);
  const state = st && st.length === 2 ? st.toUpperCase() : null;
  const rank = { c: 0, k: 1, p: 2 };
  const found = [];
  for (const p of placesData.places) {
    const lower = p[0].toLowerCase();
    if (!lower.startsWith(name) || (state && p[1] !== state)) continue;
    found.push(p);
  }
  found.sort((a, b) => (a[0].length === name.length ? 0 : 1) - (b[0].length === name.length ? 0 : 1) || rank[a[4]] - rank[b[4]] || a[0].localeCompare(b[0]));
  return found.slice(0, limit).map(([n, s, lat, lon, kind]) => ({ label: `${n}, ${s}`, short: `${n}, ${s}`, state: s, lat, lon, kind }));
}

// The state of a ZIP code, from its first three digits (the Postal Service's ranges).
const ZIP3 = [[5, 5, 'NY'], [6, 9, 'PR'], [10, 27, 'MA'], [28, 29, 'RI'], [30, 38, 'NH'], [39, 49, 'ME'], [50, 59, 'VT'],
  [60, 69, 'CT'], [70, 89, 'NJ'], [100, 149, 'NY'], [150, 196, 'PA'], [197, 199, 'DE'], [200, 205, 'DC'], [206, 219, 'MD'],
  [220, 246, 'VA'], [247, 268, 'WV'], [270, 289, 'NC'], [290, 299, 'SC'], [300, 319, 'GA'], [320, 349, 'FL'],
  [350, 369, 'AL'], [370, 385, 'TN'], [386, 397, 'MS'], [398, 399, 'GA'], [400, 427, 'KY'], [430, 459, 'OH'],
  [460, 479, 'IN'], [480, 499, 'MI'], [500, 528, 'IA'], [530, 549, 'WI'], [550, 567, 'MN'], [569, 569, 'DC'],
  [570, 577, 'SD'], [580, 588, 'ND'], [590, 599, 'MT'], [600, 629, 'IL'], [630, 658, 'MO'], [660, 679, 'KS'],
  [680, 693, 'NE'], [700, 714, 'LA'], [716, 729, 'AR'], [730, 749, 'OK'], [750, 799, 'TX'], [800, 816, 'CO'],
  [820, 831, 'WY'], [832, 838, 'ID'], [840, 847, 'UT'], [850, 865, 'AZ'], [870, 884, 'NM'], [885, 885, 'TX'],
  [889, 898, 'NV'], [900, 961, 'CA'], [967, 968, 'HI'], [970, 979, 'OR'], [980, 994, 'WA'], [995, 999, 'AK']];
function zipState(zip) {
  const n = Number(zip.slice(0, 3));
  return ZIP3.find(([from, to]) => n >= from && n <= to)?.[2] ?? null;
}

function nearestPlace(lat, lon, state = null) {
  // A town or city if there's one near; else any named place (Honolulu and San Juan aren't incorporated, nor is DC).
  for (const kinds of ['c', 'cpk']) {
    let best = null, bestD = Infinity;
    for (const p of placesData.places) {
      if (!kinds.includes(p[4]) || Math.abs(p[2] - lat) > 0.5 || (state && p[1] !== state)) continue;
      const d = (p[2] - lat) ** 2 + ((p[3] - lon) * Math.cos(lat * Math.PI / 180)) ** 2;
      if (d < bestD) { bestD = d; best = p; }
    }
    if (best && (kinds === 'cpk' || bestD < 0.25)) return best;
  }
  return null;
}

// A search box that suggests places as you type; onPick({ label, short, state, lat, lon }).
function placeSearch(input, onPick) {
  const wrap = input.parentElement;
  wrap.classList.add('suggest');
  const list = el('ul', { role: 'listbox', hidden: true });
  wrap.append(list);
  let items = [], chosen = 0;
  const render = () => {
    list.replaceChildren(...items.map((p, i) => {
      const li = el('li', { role: 'option', ariaSelected: String(i === chosen) },
        el('span', { textContent: p.label }), el('span', { textContent: { c: 'Town', k: 'County', p: 'Place', zip: 'ZIP code' }[p.kind] }));
      li.addEventListener('mousedown', (event) => { event.preventDefault(); pick(i); });
      return li;
    }));
    list.hidden = !items.length;
  };
  const pick = (i) => {
    const p = items[i];
    if (!p) return;
    input.value = p.short;
    items = [];
    render();
    onPick(p);
  };
  input.addEventListener('input', async () => {
    await loadPlaces();
    items = findPlaces(input.value);
    chosen = 0;
    render();
  });
  input.addEventListener('keydown', (event) => {
    if (list.hidden) return;
    if (event.key === 'ArrowDown') { chosen = Math.min(items.length - 1, chosen + 1); render(); event.preventDefault(); }
    else if (event.key === 'ArrowUp') { chosen = Math.max(0, chosen - 1); render(); event.preventDefault(); }
    else if (event.key === 'Enter') { pick(chosen); event.preventDefault(); }
    else if (event.key === 'Escape') { items = []; render(); }
  });
  input.addEventListener('blur', () => { items = []; render(); });
}

// Where the browser says this computer is (with the user's permission): { lat, lon } or an Error.
function locate() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('This browser can\'t tell where it is'));
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      (err) => reject(new Error(err.code === 1 ? 'Location permission was turned down' : 'Couldn\'t find where this computer is')),
      { timeout: 15000, maximumAge: 600000 });
  });
}

// A place's label and state from where it is (the nearest town).
async function placeAt(lat, lon) {
  await loadPlaces();
  let zip = null, bestD = Infinity;  // (the nearest ZIP code says the state: a town's middle can be across a border)
  for (const [code, [zlat, zlon]] of Object.entries(placesData.zips)) {
    const d = (zlat - lat) ** 2 + ((zlon - lon) * Math.cos(lat * Math.PI / 180)) ** 2;
    if (d < bestD) { bestD = d; zip = code; }
  }
  const state = zip && zipState(zip);
  const near = nearestPlace(lat, lon, state);
  return near ? { label: `${near[0]}, ${near[1]}`, state: state ?? near[1] } : { label: 'My location', state };
}

// ---- the map's camera layer: tens of thousands of dots, drawn on one canvas ----

const CameraLayer = window.L && L.Layer.extend({  // (pages without a map don't load Leaflet)
  // cameras: [{ key, lat, lon, ... }]; style(camera) -> null (not drawn) or { r, fill, stroke, width, top }
  initialize(cameras, style) {
    this.cameras = cameras;
    this.style = style;
    this.project();
  },
  project() {  // (where each camera is on the map at zoom 0, worked out once)
    this.px = new Float64Array(this.cameras.length);
    this.py = new Float64Array(this.cameras.length);
    this.cameras.forEach((c, i) => {
      const s = Math.sin(c.lat * Math.PI / 180);
      this.px[i] = (c.lon + 180) / 360;
      this.py[i] = 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI);
    });
  },
  setCameras(cameras) {
    this.cameras = cameras;
    this.project();
    this.redraw();
  },
  onAdd(map) {
    this.canvas = L.DomUtil.create('canvas', 'leaflet-zoom-hide');
    this.canvas.style.pointerEvents = 'none';
    map.getPane('overlayPane').append(this.canvas);
    this.ctx = this.canvas.getContext('2d');
    map.on('move resize zoomend viewreset', this.redraw, this);
    this.redraw();
  },
  onRemove(map) {
    this.canvas.remove();
    map.off('move resize zoomend viewreset', this.redraw, this);
  },
  radius(zoom) { return zoom <= 4 ? 1.3 : zoom <= 6 ? 1.8 : zoom <= 8 ? 2.6 : zoom <= 10 ? 3.4 : zoom <= 12 ? 4.4 : 5.5; },
  redraw() {
    const map = this._map;
    if (!map) return;
    const size = map.getSize(), ratio = devicePixelRatio || 1;
    if (this.canvas.width !== size.x * ratio || this.canvas.height !== size.y * ratio) {
      this.canvas.width = size.x * ratio;
      this.canvas.height = size.y * ratio;
      this.canvas.style.width = `${size.x}px`;
      this.canvas.style.height = `${size.y}px`;
    }
    L.DomUtil.setPosition(this.canvas, map.containerPointToLayerPoint([0, 0]));
    const ctx = this.ctx, zoom = map.getZoom(), scale = 256 * 2 ** zoom, origin = map.getPixelBounds().min;
    const base = this.radius(zoom);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, size.x, size.y);
    this.shown = [];  // [x, y, r, index] of each dot drawn, for hit tests
    const top = [];
    const groups = new Map();  // look -> [x, y, r]
    for (let i = 0; i < this.cameras.length; i++) {
      const x = this.px[i] * scale - origin.x, y = this.py[i] * scale - origin.y;
      if (x < -20 || y < -20 || x > size.x + 20 || y > size.y + 20) continue;
      const look = this.style(this.cameras[i], base);
      if (!look) continue;
      this.shown.push([x, y, look.r, i]);
      if (look.top) { top.push([x, y, look]); continue; }
      const id = `${look.fill}|${look.stroke ?? ''}|${look.width ?? 0}|${look.r}`;
      if (!groups.has(id)) groups.set(id, { look, points: [] });
      groups.get(id).points.push(x, y);
    }
    for (const { look, points } of groups.values()) {  // (one path per look: fast enough for 50,000 dots)
      ctx.beginPath();
      for (let j = 0; j < points.length; j += 2) {
        ctx.moveTo(points[j] + look.r, points[j + 1]);
        ctx.arc(points[j], points[j + 1], look.r, 0, 2 * Math.PI);
      }
      ctx.fillStyle = look.fill;
      ctx.fill();
      if (look.stroke) { ctx.strokeStyle = look.stroke; ctx.lineWidth = look.width ?? 1; ctx.stroke(); }
    }
    for (const [x, y, look] of top) {
      ctx.beginPath();
      ctx.arc(x, y, look.r, 0, 2 * Math.PI);
      ctx.fillStyle = look.fill;
      ctx.fill();
      if (look.stroke) { ctx.strokeStyle = look.stroke; ctx.lineWidth = look.width ?? 1; ctx.stroke(); }
    }
    this.grid = new Map();  // 24-px cells -> dots in them
    for (const dot of this.shown) {
      const id = `${Math.floor(dot[0] / 24)},${Math.floor(dot[1] / 24)}`;
      if (!this.grid.has(id)) this.grid.set(id, []);
      this.grid.get(id).push(dot);
    }
  },
  // The camera under a point on the map (container pixels), or null.
  hit(point) {
    if (!this.grid) return null;
    const cx = Math.floor(point.x / 24), cy = Math.floor(point.y / 24);
    let best = null, bestD = Infinity;
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
      for (const [x, y, r, i] of this.grid.get(`${cx + dx},${cy + dy}`) ?? []) {
        const d = Math.hypot(x - point.x, y - point.y);
        if (d <= Math.max(r + 4, 7) && d < bestD) { bestD = d; best = this.cameras[i]; }
      }
    }
    return best;
  },
});

// The map's tiles: the provider set in Settings › Map, else OpenStreetMap's, with the credit each asks for.
async function baseMap(map) {
  const tiles = await api('/api/map');
  const credit = tiles.link
    ? el('a', { href: tiles.link, target: '_blank', rel: 'noopener', textContent: tiles.credit }).outerHTML
    : el('span', { textContent: tiles.credit }).innerHTML;
  L.tileLayer(`/tiles/${tiles.id}/{z}/{x}/{y}`, { maxZoom: 19, attribution: credit }).addTo(map);  // (tiles.py)
}

// A tooltip that follows the pointer over the camera layer, and clicks on its dots.
function hoverCameras(map, layer, label, onClick) {
  const tip = el('div', { className: 'map-tip', hidden: true });
  map.getContainer().append(tip);
  map.on('mousemove', (event) => {
    const cam = layer.hit(event.containerPoint);
    map.getContainer().style.cursor = cam ? 'pointer' : '';
    tip.hidden = !cam;
    if (cam) {
      tip.textContent = label(cam);
      tip.style.left = `${event.containerPoint.x}px`;
      tip.style.top = `${event.containerPoint.y}px`;
    }
  });
  map.on('mouseout movestart zoomstart', () => { tip.hidden = true; });
  map.on('click', (event) => {
    const cam = layer.hit(event.containerPoint);
    if (cam) onClick(cam);
  });
}

// A camera's live picture or video in a box, kept fresh while it's shown. Returns { node, stop() }.
function preview(camera, { every = 8000 } = {}) {
  const note = el('div', { className: 'note', textContent: 'Loading…' });
  const box = el('div', { className: 'picture' }, note);
  let timer = null, hls = null, stopped = false;
  if (camera.media & 1) {
    const img = el('img', { alt: camera.name });
    img.onload = () => { note.hidden = true; };
    img.onerror = () => { note.textContent = 'No picture from this camera right now'; note.hidden = false; };
    box.append(img);
    const load = () => {
      if (stopped) return;
      img.src = `${camUrl(camera.key)}?t=${Date.now()}`;
      timer = setTimeout(load, every);
    };
    load();
  } else if (camera.video === 'mjpeg') {
    const img = el('img', { alt: camera.name, src: mjpegUrl(camera.key) });
    img.onload = () => { note.hidden = true; };
    img.onerror = () => { note.textContent = 'No video from this camera right now'; };
    box.append(img);
  } else {
    const video = el('video', { muted: true, autoplay: true, playsInline: true });
    box.append(video);
    video.addEventListener('playing', () => { note.hidden = true; });
    if (video.canPlayType('application/vnd.apple.mpegurl')) video.src = hlsUrl(camera.key);
    else if (window.Hls?.isSupported()) {
      hls = new Hls({ liveDurationInfinity: true });
      hls.loadSource(hlsUrl(camera.key));
      hls.attachMedia(video);
      hls.on(Hls.Events.ERROR, (_, data) => { if (data.fatal) note.textContent = 'No video from this camera right now'; });
    } else note.textContent = 'This browser can\'t play this camera\'s video';
  }
  return {
    node: box,
    stop() {
      stopped = true;
      clearTimeout(timer);
      hls?.destroy();
      for (const media of box.querySelectorAll('img, video')) { media.removeAttribute('src'); media.load?.(); }
    },
  };
}
