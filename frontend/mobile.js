// Disaster Connect — mobile front end for the Local Disaster Watch backend.
// Vanilla JS, no libraries. Every piece of server/OSM text goes in with
// textContent, never innerHTML.

"use strict";

const API = "";  // same-origin — FastAPI serves this file too

// Edit for your country. Shown on the SOS screen; the big button calls the first one.
const EMERGENCY_NUMBERS = [
  { label: "National emergency", hint: "Police, fire, ambulance", number: "112" },
  { label: "Police", number: "100" },
  { label: "Fire", number: "101" },
  { label: "Ambulance", number: "108" },
];

const LS_LAST = "dc:last";
const LS_SHELTERS = "dc:shelters";
const VIEWS = ["home", "shelter", "sos", "prediction", "report", "chat"];
const SVG_NS = "http://www.w3.org/2000/svg";

const $ = id => document.getElementById(id);
const state = { lat: null, lon: null, busy: false };

// ───────────────────────────── Helpers ─────────────────────────────
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

function icon(name) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "i");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", `#i-${name}`);
  svg.appendChild(use);
  return svg;
}

function load(key) {
  try { return JSON.parse(localStorage.getItem(key) || "null"); } catch (e) { return null; }
}
function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* storage disabled — non-critical */ }
}

const cap = s => (s ? s[0].toUpperCase() + s.slice(1) : "");
const num1 = v => (v == null || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(1));
const stamp = iso => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString("sv-SE"); // 2026-09-19 14:02:11
};
const coordText = (lat, lon) =>
  `${Math.abs(lat).toFixed(4)}° ${lat >= 0 ? "N" : "S"}, ${Math.abs(lon).toFixed(4)}° ${lon >= 0 ? "E" : "W"}`;

function haversineKm(lat1, lon1, lat2, lon2) {
  const r = Math.PI / 180;
  const a = Math.sin(((lat2 - lat1) * r) / 2) ** 2 +
    Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(((lon2 - lon1) * r) / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(a));
}

function currentLoc() {
  if (state.lat != null) return { lat: state.lat, lon: state.lon };
  const last = load(LS_LAST);
  return last && last.location ? last.location : null;
}

function setNotice(msg, node = $("notice")) {
  node.hidden = !msg;
  node.textContent = msg || "";
}

function directionsUrl(lat, lon) {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}`;
}

// ───────────────────────────── Home ─────────────────────────────
function renderHome(d, { stale = false } = {}) {
  const online = !!d.online;

  $("status").className = "status" + (stale ? " error" : online ? "" : " offline");
  $("connLabel").textContent = stale ? "Server unreachable" : online ? "Connected" : "Offline mode";
  $("connSub").textContent = stale ? "Showing last saved data" : online ? "Live data & updates" : "Running on local sensors only";

  const { lat, lon } = d.location;
  $("city").textContent = d.city || "Your location";
  $("coords").textContent = coordText(lat, lon);
  $("locName").textContent = d.city || coordText(lat, lon);

  // Weather: online snapshot, or local sensor rain gauge when offline
  const wx = d.weather;
  const s = d.sensors || {};
  $("wxIcon").firstElementChild.setAttribute("href", `#i-${{ clear: "sun", cloud: "cloud", fog: "fog", rain: "rain", snow: "snow", storm: "storm" }[wx && wx.icon] || "cloud"}`);
  if (wx && wx.temp_c != null) {
    $("temp").textContent = `${num1(wx.temp_c)}°C`;
    $("cond").textContent = wx.condition;
    $("wxMeta1").textContent = `Rain: ${num1(wx.rain_mm)} mm`;
    $("wxMeta2").textContent = `Precipitation: ${num1(wx.precip_mm)} mm`;
  } else {
    $("temp").textContent = "—";
    $("cond").textContent = "Forecast needs internet";
    $("wxMeta1").textContent = `Rain gauge: ${num1(s.rain_rate_mm_hr)} mm/hr`;
    $("wxMeta2").textContent = "";
  }
  $("sWater").textContent = s.water_level_cm != null ? `${num1(s.water_level_cm)} cm` : "—";
  $("sRain").textContent = s.rain_rate_mm_hr != null ? `${num1(s.rain_rate_mm_hr)} mm/hr` : "—";
  $("sPressure").textContent = s.pressure_hpa != null ? `${num1(s.pressure_hpa)} hPa` : "—";
  $("sVibration").textContent = s.vibration_g != null ? `${Number(s.vibration_g).toFixed(3)} g` : "—";
  $("sWind").textContent = s.wind_speed_kmh != null ? `${num1(s.wind_speed_kmh)} km/h` : "—";
  $("sSeaLevel").textContent = s.sea_level_change_cm != null ? `${num1(s.sea_level_change_cm)} cm` : "—";

  // Risk
  const risk = d.risk;
  const level = risk.level;
  const high = level === "high";
  const badge = $("riskBadge");
  badge.className = `badge ${level}`;
  badge.textContent = cap(level);
  $("riskIco").className = `ico ${high ? "red" : level === "medium" ? "amber" : "green"}`;
  $("riskIco").firstElementChild.firstElementChild.setAttribute("href", high ? "#i-warn" : "#i-shield");
  $("riskSub").textContent = high ? `${cap(risk.hazard)} alert is active.` : "No immediate threat detected.";
  $("reason").textContent = cap(risk.reason);
  $("floodRisk").textContent = cap(risk.flood);
  $("quakeRisk").textContent = cap(risk.earthquake);
  $("stormRisk").textContent = cap(risk.storm);
  $("tsunamiRisk").textContent = cap(risk.tsunami);

  // ---------------------------------------------------------
  // Enhanced Emergency Alert
  // ---------------------------------------------------------

  const alert = d.alert || {};

  const alertActive = !!alert.active && alert.risk_level === "high";

  const emergencyCard = $("emergencyCard");
  const alertDetails = $("alertDetails");
  const alertPriority = $("alertPriority");

  emergencyCard.classList.toggle("active", alertActive);
  $("bell").classList.toggle("has-alert", alertActive);

  if (alertActive) {

    $("alertTitle").textContent =
      alert.title || `${cap(risk.hazard)} Emergency Alert`;

    $("alertSub").textContent =
      alert.message || risk.reason || "Emergency risk detected.";

    alertPriority.textContent =
      alert.priority || "HIGH";

    $("alertRisk").textContent =
      cap(alert.risk_level || "high");

    if (alert.lat != null && alert.lon != null) {
      $("alertLocation").textContent =
        `${Number(alert.lat).toFixed(4)}, ${Number(alert.lon).toFixed(4)}`;
    } else {
      $("alertLocation").textContent =
        coordText(d.location.lat, d.location.lon);
    }

    $("alertTime").textContent =
      alert.timestamp
        ? stamp(alert.timestamp)
        : stamp(d.updated);

    $("alertMode").textContent =
      alert.mode === "online"
        ? "Online"
        : "Offline Cache";

    $("alertAction").textContent =
      alert.recommended_action ||
      "Move to a safe location and follow local emergency instructions.";

    alertDetails.hidden = false;

  } else {

    // -------------------------------------------------------
    // SAFE STATE
    // Keep the alert card minimal when there is no emergency
    // -------------------------------------------------------

    emergencyCard.classList.remove("active");

    $("alertTitle").textContent =
      "Emergency Alert";

    $("alertSub").textContent =
      "No immediate threat detected.";

    alertPriority.textContent =
      "SAFE";

    // Hide all emergency-specific information
    alertDetails.hidden = true;
  }

  $("updated").textContent = `${stamp(d.updated)} · tap to refresh`;
}

function getPosition() {
  return new Promise((resolve, reject) => {
    // ?lat=..&lon=.. lets you test from another device, where browsers block GPS on plain http
    const q = new URLSearchParams(location.search);
    const qLat = parseFloat(q.get("lat")), qLon = parseFloat(q.get("lon"));
    if (Number.isFinite(qLat) && Number.isFinite(qLon)) return resolve({ lat: qLat, lon: qLon });
    if (!("geolocation" in navigator)) return reject(new Error("no geolocation"));
    navigator.geolocation.getCurrentPosition(
      p => resolve({ lat: p.coords.latitude, lon: p.coords.longitude }),
      reject,
      { enableHighAccuracy: true, maximumAge: 30000, timeout: 10000 }
    );
  });
}

// Each check saves a reading and, if risk is high, fires the real alert
// (buzzer/SMS) — same as /api/location. So it only runs on page load and
// when you tap "Last Updated", never on a timer.
async function refresh() {
  if (state.busy) return;
  state.busy = true;
  $("updated").textContent = "Updating…";
  setNotice("");

  const last = load(LS_LAST);
  let pos;
  try {
    pos = await getPosition();
  } catch (err) {
    if (last && last.location) {
      pos = last.location;
    } else {
      $("connLabel").textContent = "Location needed";
      $("connSub").textContent = "Allow location access to run a check";
      $("coords").textContent = "Location unavailable";
      $("updated").textContent = "—";
      setNotice("Browsers only allow GPS on https or localhost. To test from another device, add ?lat=18.52&lon=73.86 to the address.");
      state.busy = false;
      return;
    }
  }

  try {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 20000);
    const res = await fetch(`${API}/api/dashboard`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(pos),
      signal: ctl.signal,
    });
    clearTimeout(timer);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    state.lat = data.location.lat;
    state.lon = data.location.lon;
    save(LS_LAST, data);
    renderHome(data);
    notifyHighRisk(data);
  } catch (err) {
    if (last) {
      renderHome(last, { stale: true });
      setNotice("Couldn't reach the local server. Tap Last Updated to try again.");
    } else {
      $("connLabel").textContent = "Server unreachable";
      $("connSub").textContent = "Is backend.server running?";
      $("updated").textContent = "—";
    }
  }
  state.busy = false;
}

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ AI prediction (transparent local trend estimate) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function svgEl(tag, attrs = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
  return node;
}

function drawPredictionChart(id, samples, field, threshold, color, label) {
  const chart = $(id);
  chart.replaceChildren();
  chart.setAttribute("viewBox", "0 0 340 150");
  const values = samples.map(s => Number(s[field])).filter(Number.isFinite);
  if (values.length < 2) {
    const text = svgEl("text", { x: 170, y: 75, "text-anchor": "middle", fill: "#5f6f86", "font-size": 13 });
    text.textContent = "More readings are needed for a trend.";
    chart.appendChild(text);
    return;
  }
  const allValues = threshold == null ? values : [...values, threshold];
  let min = Math.min(...allValues), max = Math.max(...allValues);
  if (min === max) { min -= 1; max += 1; }
  const pad = (max - min) * 0.15;
  min -= pad;
  max += pad;
  const x = index => 18 + index * (304 / (values.length - 1));
  const y = value => 128 - ((value - min) / (max - min)) * 108;
  chart.appendChild(svgEl("line", { x1: 18, y1: 128, x2: 322, y2: 128, stroke: "#dbe5f2" }));
  if (threshold != null) {
    const line = svgEl("line", { x1: 18, y1: y(threshold), x2: 322, y2: y(threshold), stroke: "#d93a3a", "stroke-dasharray": "5 4" });
    const text = svgEl("text", { x: 320, y: y(threshold) - 5, "text-anchor": "end", fill: "#d93a3a", "font-size": 11 });
    text.textContent = `Alert ${threshold}`;
    chart.append(line, text);
  }
  chart.appendChild(svgEl("polyline", { points: values.map((value, index) => `${x(index)},${y(value)}`).join(" "), fill: "none", stroke: color, "stroke-width": 3, "stroke-linecap": "round", "stroke-linejoin": "round" }));
  const caption = svgEl("text", { x: 18, y: 145, fill: "#5f6f86", "font-size": 11 });
  caption.textContent = label;
  chart.appendChild(caption);
}

function renderPrediction(data) {
  const flood = data.flood;
  const quake = data.earthquake;
  $("floodPredictionBadge").className = `tag ${flood.level === "high" ? "high" : ""}`;
  $("floodPredictionBadge").textContent = cap(flood.level);
  $("floodPredictionText").textContent = flood.reason;
  $("quakePredictionBadge").className = `tag ${quake.level === "high" ? "high" : ""}`;
  $("quakePredictionBadge").textContent = cap(quake.level);
  $("quakePredictionText").textContent = quake.reason;
  $("predictionWhy").textContent = data.explanation;
  drawPredictionChart("floodPredictionChart", data.samples, "water_level_cm", data.thresholds.flood_water_level_cm, "#2d6cdf", "Water distance from sensor (lower means higher water)");
  drawPredictionChart("quakePredictionChart", data.samples, "vibration_g", data.thresholds.vibration_attention_g, "#d93a3a", "Vibration (g) — activity monitoring, not earthquake prediction");
}

async function loadPrediction() {
  setNotice("", $("predictionNote"));
  try {
    const res = await fetch(`${API}/api/prediction?limit=24`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    renderPrediction(await res.json());
  } catch (err) {
    setNotice("Couldn't load the local prediction data. Run a Home check and try again.", $("predictionNote"));
  }
}

// ───────────────────────────── Notifications ─────────────────────────────
function updateBell() {
  const on = "Notification" in window && Notification.permission === "granted";
  $("bell").classList.toggle("on", on);
  $("bell").setAttribute("aria-label", on ? "Browser alerts are on" : "Turn on browser alerts");
}

$("bell").addEventListener("click", async () => {

  // ------------------------------------------------------
  // First: open the emergency alert inside the app
  // ------------------------------------------------------

  const card =
    $("emergencyCard");

  if (card) {

    card.scrollIntoView({
      behavior: "smooth",
      block: "center"
    });

    // Small visual highlight
    card.classList.add("notification-focus");

    setTimeout(() => {
      card.classList.remove(
        "notification-focus"
      );
    }, 1500);
  }


  // ------------------------------------------------------
  // Second: request browser notification permission
  // ------------------------------------------------------

  if (!("Notification" in window)) {

    setNotice(
      "Browser notifications are not supported."
    );

    return;
  }


  if (
    Notification.permission ===
    "default"
  ) {

    try {

      await Notification.requestPermission();

    } catch (e) {

      console.log(
        "Notification permission request failed.",
        e
      );
    }
  }


  if (
    Notification.permission ===
    "denied"
  ) {

    setNotice(
      "Browser notifications are blocked. " +
      "You can enable them from browser site settings."
    );

  } else if (
    Notification.permission ===
    "granted"
  ) {

    setNotice(
      "Browser notifications are enabled."
    );
  }


  updateBell();
});


function notifyHighRisk(d) {

  const alert = d.alert;

  if (!alert || !alert.active) return;

  if (
    !("Notification" in window) ||
    Notification.permission !== "granted"
  ) {
    return;
  }

  const title =
    alert.title ||
    `${String(alert.hazard_type || d.risk.hazard).toUpperCase()} ALERT`;

  const body = [
    alert.message || d.risk.reason,
    alert.recommended_action
      ? `Action: ${alert.recommended_action}`
      : ""
  ]
    .filter(Boolean)
    .join("\n");

  try {

    new Notification(title, {
      body,
      tag: `disaster-${alert.hazard_type || d.risk.hazard}`,
      requireInteraction: alert.risk_level === "high"
    });

  } catch (e) {
    // Some browsers require a service worker for notifications.
  }
}

// ───────────────────────────── Shelter ─────────────────────────────

function shelterCard(s, nearest) {
  const card = el("article", "item");
  const h = el("h3", null, s.name);
  if (nearest) h.appendChild(el("span", "tag", "Nearest"));
  card.appendChild(h);
  card.appendChild(el("p", null, `${cap(String(s.type).replace(/_/g, " "))} · ${s.distance_km} km`));
  if (s.address) card.appendChild(el("p", null, s.address));
  if (s.opening_hours) card.appendChild(el("p", null, `Hours: ${s.opening_hours}`));


  const actions = el("div", "actions");

  const dir = el("button", "btn", "Directions");
  dir.type = "button";

  dir.addEventListener("click", () => {
    openDirections(s);
  });

  actions.appendChild(dir);

  const tel = s.phone ? String(s.phone).replace(/[^\d+]/g, "") : "";
  if (tel) {
    const call = el("a", "btn ghost", "Call");
    call.href = `tel:${tel}`;
    actions.appendChild(call);
  }
  card.appendChild(actions);
  return card;
}


async function showOfflineRoute(destinationLat, destinationLon, shelterName) {
  const mapContainer = document.getElementById("offlineMapContainer");
  const map = document.getElementById("offlineMap");
  const mapLoading = document.getElementById("mapLoading");
  const routeStatus = document.getElementById("routeStatus");
  const routeInfo = document.getElementById("routeInfo");
  const routeDistance = document.getElementById("routeDistance");

  mapContainer.hidden = false;
  routeInfo.hidden = true;
  mapLoading.hidden = false;
  mapLoading.textContent = "Finding your location...";
  routeStatus.textContent = "Offline route";
// Use the SAME location that the shelter list uses.
// This keeps shelter distance and offline route consistent.

const loc = currentLoc();

if (!loc) {
  mapLoading.textContent =
    "Your location is not available.";

  routeStatus.textContent =
    "Location unavailable";

  return;
}

const startLat = loc.lat;
const startLon = loc.lon;
  mapLoading.textContent = "Calculating offline route...";

  try {
    const url =
      `/api/route?start_lat=${encodeURIComponent(startLat)}` +
      `&start_lon=${encodeURIComponent(startLon)}` +
      `&destination_lat=${encodeURIComponent(destinationLat)}` +
      `&destination_lon=${encodeURIComponent(destinationLon)}`;

    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`Route request failed: ${response.status}`);
    }

    const data = await response.json();

    if (!data.route || data.route.length < 2) {
      throw new Error("No route returned.");
    }

    drawOfflineRoute(
      map,
      data.route,
      startLat,
      startLon,
      destinationLat,
      destinationLon
    );

    mapLoading.hidden = true;
    routeInfo.hidden = false;

    routeDistance.textContent =
      `${data.distance_km} km · Offline`;

    routeStatus.textContent =
      `Route to ${shelterName}`;

  } catch (error) {
    console.error("Offline routing error:", error);

    mapLoading.textContent =
      "Unable to calculate offline route.";

    routeStatus.textContent = "Route unavailable";
  }
}

async function checkInternet() {
  try {
    const response = await fetch("/api/status", {
      cache: "no-store"
    });

    if (!response.ok) {
      return false;
    }

    const data = await response.json();

    return data.online === true;

  } catch (error) {
    console.log("Connectivity check failed:", error);
    return false;
  }
}

async function openDirections(s) {
  const online = await checkInternet();

  if (online) {
    // Internet available → Google Maps
    window.open(
      directionsUrl(s.lat, s.lon),
      "_blank"
    );
  } else {
    // Internet unavailable → Disaster Connect offline route
    showOfflineRoute(
      s.lat,
      s.lon,
      s.name
    );
  }
}

function drawOfflineRoute(
  container,
  route,
  startLat,
  startLon,
  destinationLat,
  destinationLon
) {
  const width = 600;
  const height = 320;

  // Fixed map scale:
  // 1 pixel represents approximately 8 metres.
  // This means routes are NOT stretched to fill the map.
  const metersPerPixel = 8;

  const centerLat =
    (startLat + destinationLat) / 2;

  const centerLon =
    (startLon + destinationLon) / 2;

  const metersPerDegreeLat = 111320;

  const metersPerDegreeLon =
    111320 * Math.cos(centerLat * Math.PI / 180);

  function project(lat, lon) {
    const x =
      width / 2 +
      ((lon - centerLon) * metersPerDegreeLon) /
        metersPerPixel;

    const y =
      height / 2 -
      ((lat - centerLat) * metersPerDegreeLat) /
        metersPerPixel;

    return { x, y };
  }

  // Convert route coordinates into screen coordinates
  let projected = route.map(point =>
    project(point.lat, point.lon)
  );

  /*
   * If the route is too large for the map,
   * automatically zoom out just enough to fit it.
   */
  const xs = projected.map(p => p.x);
  const ys = projected.map(p => p.y);

  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);

  const routeWidth = maxX - minX;
  const routeHeight = maxY - minY;

  const availableWidth = width - 70;
  const availableHeight = height - 70;

  let zoomFactor = 1;

  if (routeWidth > availableWidth) {
    zoomFactor = Math.min(
      zoomFactor,
      availableWidth / routeWidth
    );
  }

  if (routeHeight > availableHeight) {
    zoomFactor = Math.min(
      zoomFactor,
      availableHeight / routeHeight
    );
  }

  // Center the route after any required zoom-out
  const routeCenterX = (minX + maxX) / 2;
  const routeCenterY = (minY + maxY) / 2;

  projected = projected.map(p => ({
    x:
      width / 2 +
      (p.x - routeCenterX) * zoomFactor,

    y:
      height / 2 +
      (p.y - routeCenterY) * zoomFactor
  }));

  const routePoints = projected
    .map(p => `${p.x},${p.y}`)
    .join(" ");

  const start = project(startLat, startLon);
  const destination = project(
    destinationLat,
    destinationLon
  );

  // Apply the same zoom and centering to markers
  const screenPoint = p => ({
    x:
      width / 2 +
      (p.x - routeCenterX) * zoomFactor,

    y:
      height / 2 +
      (p.y - routeCenterY) * zoomFactor
  });

  const startPoint = screenPoint(start);
  const destinationPoint = screenPoint(destination);

  container.innerHTML = `
    <svg
      viewBox="0 0 ${width} ${height}"
      class="offline-route-svg"
      role="img"
      aria-label="Offline emergency route"
    >

      <!-- Map background -->
      <rect
        x="0"
        y="0"
        width="${width}"
        height="${height}"
        class="map-background"
      />

      <!-- Simple road background -->
      <g class="offline-roads">

        <path d="M0 70 L150 90 L300 65 L450 100 L600 80" />
        <path d="M0 145 L140 125 L280 155 L430 135 L600 165" />
        <path d="M0 230 L130 200 L270 235 L420 215 L600 250" />
        <path d="M0 295 L150 265 L300 285 L450 270 L600 300" />

        <path d="M80 0 L110 320" />
        <path d="M220 0 L235 320" />
        <path d="M360 0 L340 320" />
        <path d="M500 0 L515 320" />

      </g>

      <!-- White outline makes route easier to see -->
      <polyline
        points="${routePoints}"
        class="offline-route-shadow"
        fill="none"
      />

      <!-- Actual offline route -->
      <polyline
        points="${routePoints}"
        class="offline-route-line"
        fill="none"
      />

      <!-- You -->
      <circle
        cx="${startPoint.x}"
        cy="${startPoint.y}"
        r="13"
        class="route-start-outer"
      />

      <circle
        cx="${startPoint.x}"
        cy="${startPoint.y}"
        r="7"
        class="route-start"
      />

      <!-- Shelter -->
      <circle
        cx="${destinationPoint.x}"
        cy="${destinationPoint.y}"
        r="14"
        class="route-end-outer"
      />

      <circle
        cx="${destinationPoint.x}"
        cy="${destinationPoint.y}"
        r="8"
        class="route-end"
      />

      <!-- You label -->
      <rect
        x="${startPoint.x + 14}"
        y="${startPoint.y - 14}"
        width="50"
        height="24"
        rx="6"
        class="label-background"
      />

      <text
        x="${startPoint.x + 25}"
        y="${startPoint.y + 3}"
        class="route-label"
      >
        You
      </text>

      <!-- Shelter label -->
      <rect
        x="${destinationPoint.x + 15}"
        y="${destinationPoint.y - 14}"
        width="70"
        height="24"
        rx="6"
        class="label-background"
      />

      <text
        x="${destinationPoint.x + 25}"
        y="${destinationPoint.y + 3}"
        class="route-label"
      >
        Shelter
      </text>

      <!-- Offline badge -->
      <rect
        x="15"
        y="15"
        width="115"
        height="28"
        rx="8"
        class="offline-badge"
      />

      <text
        x="28"
        y="34"
        class="offline-badge-text"
      >
        OFFLINE MAP
      </text>

    </svg>
  `;
}

function renderShelters(shelters, note) {
  const list = $("shelterList");
  list.replaceChildren();
  setNotice(note, $("shelterNote"));
  if (!shelters.length) {
    list.appendChild(el("p", "empty", "No shelters found nearby, or the lookup needs internet."));
    return;
  }
  shelters.forEach((s, i) => list.appendChild(shelterCard(s, i === 0)));
}

async function loadShelters() {
  const list = $("shelterList");
  const loc = currentLoc();

  setNotice("", $("shelterNote"));

  if (!loc) {
    list.replaceChildren(
      el(
        "p",
        "empty",
        "Location isn't available yet. Open Home and allow location access."
      )
    );
    return;
  }

  const cached = load(LS_SHELTERS);

  const cacheIsClose =
    cached &&
    haversineKm(
      loc.lat,
      loc.lon,
      cached.lat,
      cached.lon
    ) < 5;

  // ─────────────────────────────
  // Check internet first
  // ─────────────────────────────

  const online = await checkInternet();

  // ─────────────────────────────
  // OFFLINE → show cache immediately
  // ─────────────────────────────

  if (!online) {
    if (cacheIsClose && cached.shelters.length) {
      renderShelters(
        cached.shelters,
        ""
      );
    } else {
      renderShelters(
        [],
        ""
      );
    }

    return;
  }

  // ─────────────────────────────
  // ONLINE → get fresh shelters
  // ─────────────────────────────

  list.replaceChildren(
    el("p", "empty", "Searching nearby…")
  );

  try {
    const res = await fetch(
      `${API}/api/safe-houses?lat=${loc.lat}&lon=${loc.lon}`
    );

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const data = await res.json();

    if (data.shelters.length) {

      save(LS_SHELTERS, {
        lat: loc.lat,
        lon: loc.lon,
        at: Date.now(),
        shelters: data.shelters
      });

      renderShelters(
        data.shelters,
        data.expanded
          ? `Nothing in the default radius, so the search widened to ${data.radius_km} km.`
          : ""
      );

    } else if (
      cacheIsClose &&
      cached.shelters.length
    ) {

      renderShelters(
        cached.shelters,
        ""
      );

    } else {

      renderShelters(
        [],
        ""
      );
    }

  } catch (err) {

    console.error(
      "Shelter lookup failed:",
      err
    );

    // If online lookup fails unexpectedly,
    // fall back to cached data without
    // showing the old warning message.

    if (
      cacheIsClose &&
      cached.shelters.length
    ) {

      renderShelters(
        cached.shelters,
        ""
      );

    } else {

      renderShelters(
        [],
        ""
      );
    }
  }
}

// ───────────────────────────── SOS ─────────────────────────────
function renderSos() {
  const wrap = $("sosList");
  if (wrap.childElementCount) return;
  EMERGENCY_NUMBERS.forEach(n => {
    const item = el("div", "item number");
    const left = el("div");
    left.appendChild(el("h3", null, n.label));
    if (n.hint) left.appendChild(el("p", null, n.hint));
    const call = el("a", null, n.number);
    call.href = `tel:${n.number}`;
    call.setAttribute("aria-label", `Call ${n.label} on ${n.number}`);
    item.append(left, call);
    wrap.appendChild(item);
  });
  document.querySelector(".sos-call span").textContent = `Call ${EMERGENCY_NUMBERS[0].number}`;
  document.querySelector(".sos-call").href = `tel:${EMERGENCY_NUMBERS[0].number}`;
}

$("shareBtn").addEventListener("click", async () => {
  const note = $("sosNote");
  const loc = currentLoc();
  if (!loc) { note.textContent = "Your location isn't available yet. Open Home and allow location access."; return; }
  const text = `I need help. My location: https://maps.google.com/?q=${loc.lat},${loc.lon}`;
  if (navigator.share) {
    try { await navigator.share({ text }); return; } catch (e) { if (e.name === "AbortError") return; }
  }
  try {
    await navigator.clipboard.writeText(text);
    note.textContent = "Location link copied. Paste it into a message.";
  } catch (e) {
    note.textContent = text;
  }
});

// ───────────────────────────── Report (alert history) ─────────────────────────────
async function loadReport() {
  const list = $("reportList");
  list.replaceChildren(el("p", "empty", "Loading…"));
  try {
    const res = await fetch(`${API}/api/alerts?limit=30`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const alerts = await res.json();
    list.replaceChildren();
    if (!alerts.length) {
      list.appendChild(el("p", "empty", "No alerts recorded yet."));
      return;
    }

    alerts.forEach(a => {

      const card = el("article", "item");

      const hazard =
        cap(String(a.hazard_type || "unknown").replace(/_/g, " "));

      const priority =
        cap(a.priority || a.risk_level || "info");

      const h = el("h3", null, hazard);

      h.appendChild(
        el(
          "span",
          `tag ${a.risk_level === "high" ? "high" : ""}`,
          priority
        )
      );

      card.appendChild(h);

      if (a.title) {
        card.appendChild(
          el("p", null, a.title)
        );
      }

      card.appendChild(
        el(
          "p",
          null,
          a.message || a.reasoning || "No additional details."
        )
      );

      if (a.recommended_action) {

        const action = el(
          "p",
          null,
          `Recommended action: ${a.recommended_action}`
        );

        card.appendChild(action);
      }

      const where =
        a.lat != null && a.lon != null
          ? ` · ${coordText(a.lat, a.lon)}`
          : "";

      card.appendChild(
        el(
          "p",
          null,
          `${stamp(a.timestamp)} · ${a.mode || "—"}${where}`
        )
      );

      list.appendChild(card);
    });
    } catch (err) {

    console.error(
      "Alert history failed:",
      err
    );

    list.replaceChildren(
      el(
        "p",
        "empty",
        "Couldn't load alert history. Please try again."
      )
    );
  }
}

  


// ───────────────────────────── Routing + wiring ─────────────────────────────
function route() {
  const name = (location.hash || "#home").slice(1);
  const view = VIEWS.includes(name) ? name : "home";
  VIEWS.forEach(v => { $(`view-${v}`).hidden = v !== view; });
  document.querySelectorAll("nav a").forEach(a => {
    if (a.getAttribute("href") === `#${view}`) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  if (view === "shelter") loadShelters();
  if (view === "report") loadReport();
  if (view === "sos") renderSos();
  if (view === "prediction") loadPrediction();
  window.scrollTo(0, 0);
}

document.addEventListener("click", e => {
  const toggle = e.target.closest("[data-toggle]");
  if (!toggle) return;
  const panel = $(toggle.dataset.toggle);
  const open = panel.hidden;
  panel.hidden = !open;
  toggle.setAttribute("aria-expanded", String(open));
});

$("refreshRow").addEventListener("click", refresh);
window.addEventListener("hashchange", route);

// ───────────────────────────── Emergency Chat ─────────────────────────────

function addChatMessage(message, sender = "bot") {
  const messages = $("chatMessages");
  if (!messages) return;

  const row = el("div", `chat-message ${sender}`);
  const bubble = el("div", "chat-bubble", message);

  row.appendChild(bubble);
  messages.appendChild(row);

  messages.scrollTop = messages.scrollHeight;
}

function getChatReply(question) {
  const q = question.toLowerCase().trim().replace(/\s+/g, " ");

  // ─────────────────────────────
  // Greeting
  // ─────────────────────────────
  if (
    q === "hi" ||
    q === "hello" ||
    q === "hey"
  ) {
    return "Hello! 👋 I'm your Disaster Connect Safety Assistant. Ask me about earthquake, flood, fire, cyclone, heavy rain, emergency preparation or safety precautions.";
  }


  // ─────────────────────────────
  // EARTHQUAKE
  // ─────────────────────────────
  if (
    q.includes("earthquake") ||
    q.includes("earth quake") ||
    q.includes("shaking") ||
    q.includes("ground shaking")
  ) {
    return `🏚️ EARTHQUAKE SAFETY

During an earthquake:
• Drop, Cover and Hold On.
• Get under a sturdy table or desk if one is nearby.
• Stay away from windows, glass and heavy objects that may fall.
• Do not use elevators.
• Do not run outside while the ground is shaking.
• Protect your head and neck.

After the shaking stops:
• Move carefully to a safer open area if necessary.
• Stay away from damaged buildings.
• Watch for aftershocks.
• Check yourself and others for injuries.
• Avoid damaged electrical wires and possible gas leaks.
• Keep your phone available for emergency communication.

🆘 If someone is seriously injured or trapped, use the SOS section.`;
  }


  // ─────────────────────────────
  // FLOOD
  // ─────────────────────────────
  if (
    q.includes("flood") ||
    q.includes("flooding") ||
    q.includes("water rising") ||
    q.includes("water is rising")
  ) {
    return `🌊 FLOOD SAFETY

• Move to higher and safer ground.
• Never walk or drive through moving floodwater.
• Stay away from drains, bridges and submerged roads.
• Keep children away from floodwater.
• Keep important documents and medicines protected in waterproof bags.
• Keep your phone and power bank charged.
• If it is safe to do so, switch off electricity before entering a flooded area.
• Follow official evacuation instructions.
• Avoid unnecessary travel during severe flooding.

🗺️ If you need to evacuate, use the Safe Route feature to find a safer route.`;
  }


  // ─────────────────────────────
  // HEAVY RAIN
  // ─────────────────────────────
  if (
    q.includes("rain") ||
    q.includes("raining") ||
    q.includes("rainning") ||
    q.includes("rainfall") ||
    q.includes("heavy rain") ||
    q.includes("heavy rainfall") ||
    q.includes("raining heavily") ||
    q.includes("raining a lot") ||
    q.includes("pouring") ||
    q.includes("downpour")
  ) {
    return `🌧️ HEAVY RAIN SAFETY

• Stay indoors if possible.
• Avoid low-lying and waterlogged areas.
• Do not walk or drive through moving water.
• Stay away from open drains and flooded roads.
• Keep important documents, medicines and electronic devices protected from water.
• Keep your phone and power bank charged.
• Monitor Disaster Connect alerts and your current risk.
• Avoid unnecessary travel during severe rainfall.
• If evacuation becomes necessary, use the Safe Route feature.

⚠️ Heavy rain can quickly lead to flooding, especially in low-lying areas.`;
  }


  // ─────────────────────────────
  // FIRE
  // ─────────────────────────────
  if (
    q.includes("fire") ||
    q.includes("burning") ||
    q.includes("smoke") ||
    q.includes("fire accident")
  ) {
    return `🔥 FIRE SAFETY

• Raise the alarm and leave the building if it is safe to do so.
• Use stairs instead of elevators.
• Stay low if there is heavy smoke.
• Do not go back inside to collect belongings.
• Stay away from burning or damaged structures.
• If your clothes catch fire: Stop, Drop and Roll.
• Do not use electrical switches if you suspect an electrical fire.
• Call emergency services immediately.

🆘 Use the SOS section for emergency contacts.`;
  }


  // ─────────────────────────────
  // CYCLONE / STORM
  // ─────────────────────────────
  if (
    q.includes("cyclone") ||
    q.includes("storm") ||
    q.includes("strong wind") ||
    q.includes("thunderstorm")
  ) {
    return `🌪️ CYCLONE / STORM SAFETY

Before the storm:
• Charge your phone and power bank.
• Keep drinking water and basic food ready.
• Keep medicines and important documents safe.
• Secure loose objects around your home.
• Follow official warnings and evacuation instructions.

During the storm:
• Stay indoors.
• Stay away from windows and glass.
• Avoid going outside unnecessarily.
• Do not touch fallen electrical wires.
• Keep monitoring emergency alerts.

After the storm:
• Watch for fallen wires and damaged buildings.
• Avoid flooded roads.
• Do not enter damaged structures until they are considered safe.`;
  }


  // ─────────────────────────────
  // EMERGENCY KIT
  // ─────────────────────────────
  if (
    q.includes("emergency kit") ||
    q.includes("emergency bag") ||
    q.includes("what should i keep") ||
    q.includes("what should i carry") ||
    q.includes("emergency supplies")
  ) {
    return `🎒 EMERGENCY KIT

Keep these items ready:

📄 Important documents
• ID cards
• Important certificates
• Insurance and essential records
• Emergency contact information

💊 Health
• Essential medicines
• First-aid kit
• Necessary medical supplies

🔦 Basic supplies
• Torch
• Extra batteries
• Power bank
• Charged phone
• Drinking water
• Basic food
• Masks

🔑 Other useful items
• Emergency cash
• Important keys
• Basic clothing
• Hygiene items

💡 Keep important documents protected from water and stored somewhere that is easy to access during an emergency.`;
  }


  // ─────────────────────────────
  // DOCUMENTS
  // ─────────────────────────────
  if (
    q.includes("document") ||
    q.includes("documents") ||
    q.includes("certificates") ||
    q.includes("id card") ||
    q.includes("important papers")
  ) {
    return `📄 IMPORTANT DOCUMENT SAFETY

Keep important documents such as:

• ID cards
• Educational certificates
• Insurance documents
• Medical records
• Property-related documents
• Emergency contact information

For disaster preparation:
• Keep physical copies in a waterproof folder.
• Keep secure digital copies where appropriate.
• Store them somewhere easy to access during evacuation.
• Do not risk your life to retrieve documents during an active disaster.`;
  }


  // ─────────────────────────────
  // BEFORE A DISASTER
  // ─────────────────────────────
  if (
    q.includes("before a disaster") ||
    q.includes("prepare for disaster") ||
    q.includes("disaster preparation") ||
    q.includes("how should i prepare")
  ) {
    return `🧰 DISASTER PREPARATION

Before a disaster:

• Keep an emergency kit ready.
• Keep important documents protected.
• Keep essential medicines available.
• Charge your phone and power bank.
• Save emergency contact numbers.
• Know the safest exits from your building.
• Know where you can go if evacuation is required.
• Keep some drinking water and basic food ready.
• Follow official disaster warnings.
• Check Disaster Connect regularly for risk and alerts.`;
  }


  // ─────────────────────────────
  // AFTER A DISASTER
  // ─────────────────────────────
  if (
    q.includes("after a disaster") ||
    q.includes("after disaster") ||
    q.includes("what should i do after")
  ) {
    return `🛡️ AFTER A DISASTER

• Check yourself and others for injuries.
• Move away from damaged buildings.
• Watch for aftershocks or additional hazards.
• Avoid fallen electrical wires.
• Do not enter damaged buildings without confirmation that they are safe.
• Follow official instructions.
• Keep your phone available for emergency communication.
• Use SOS if emergency assistance is required.
• Use Safe Route if you need to move to a safer location.`;
  }


  // ─────────────────────────────
  // ELECTRICITY / POWER
  // ─────────────────────────────
  if (
    q.includes("switch off electricity") ||
    q.includes("switch off power") ||
    q.includes("electricity") ||
    q.includes("power")
  ) {
    return `⚡ ELECTRICAL SAFETY

• Stay away from damaged electrical wires.
• Never touch electrical equipment with wet hands.
• During flooding, switch off electricity only if you can do so safely without entering water or touching damaged equipment.
• Do not use electrical appliances that have been exposed to water.
• If there is an electrical hazard, leave the area and contact the appropriate emergency service.`;
  }


  // ─────────────────────────────
  // TRAPPED
  // ─────────────────────────────
  if (
    q.includes("trapped") ||
    q.includes("stuck") ||
    q.includes("rescue")
  ) {
    return `🆘 IF YOU ARE TRAPPED

• Stay as calm as possible.
• Avoid unnecessary movement if the surrounding structure is unstable.
• Protect your nose and mouth from dust if possible.
• Make noise or use your phone to signal rescuers.
• Conserve your phone battery.
• Do not attempt dangerous escape routes.

📞 Use the SOS section to contact emergency services and share your location if possible.`;
  }


  // ─────────────────────────────
  // EVACUATION
  // ─────────────────────────────
  if (
    q.includes("evacuation") ||
    q.includes("evacuate") ||
    q.includes("evacuating")
  ) {
    return `🚨 EVACUATION SAFETY

• Follow official evacuation instructions.
• Take your emergency kit.
• Carry essential medicines.
• Protect important documents.
• Keep your phone charged.
• Do not use unsafe or flooded roads.
• Stay with your family or group when possible.
• Follow the designated safe route.

🗺️ Use the Safe Route feature in Disaster Connect when you need navigation.`;
  }


  // ─────────────────────────────
  // DEFAULT
  // ─────────────────────────────
  return `💬 I can help you with disaster safety and preparation.

You can ask me things like:

• "What should I do during an earthquake?"
• "What should I do during heavy rain?"
• "What should I keep in my emergency kit?"
• "How should I protect important documents?"
• "What should I do during a flood?"
• "How should I prepare for a cyclone?"
• "What should I do after a disaster?"

For shelters, routes and emergency calls, use the Shelter, Safe Route and SOS features.`;
}

function sendChatMessage(question = null) {
  const input = $("chatInput");

  const text = question != null
    ? question.trim()
    : input.value.trim();

  if (!text) return;

  addChatMessage(text, "user");

  if (input) {
    input.value = "";
  }

  setTimeout(() => {

    const lower = text.toLowerCase();

    // Find shelter
    if (
      lower.includes("find a safe shelter") ||
      lower.includes("find a shelter")
    ) {
      addChatMessage(
        "🏠 I'm opening nearby shelters for you. You can choose a shelter and view its route.",
        "bot"
      );

      setTimeout(() => {
        location.hash = "#shelter";
      }, 500);

      return;
    }


    // Find route
    if (
      lower.includes("find a safe route") ||
      lower.includes("find a route")
    ) {
      addChatMessage(
        "🗺️ I'm opening the Shelter section so you can select a safe destination and get directions.",
        "bot"
      );

      setTimeout(() => {
        location.hash = "#shelter";
      }, 500);

      return;
    }


    // Hospital
    if (lower.includes("find a hospital")) {
      addChatMessage(
        "🏥 For medical emergencies, I'm opening the SOS section where emergency contacts are available.",
        "bot"
      );

      setTimeout(() => {
        location.hash = "#sos";
      }, 500);

      return;
    }


    // Trapped
    if (lower.includes("i'm trapped") || lower.includes("im trapped")) {
      addChatMessage(
        "🆘 I'm opening SOS. Use the emergency contact and location-sharing options immediately.",
        "bot"
      );

      setTimeout(() => {
        location.hash = "#sos";
      }, 500);

      return;
    }


    // Normal chatbot response
    const reply = getChatReply(text);

    addChatMessage(reply, "bot");

  }, 300);
}

function initChat() {
  const input = $("chatInput");
  const send = $("chatSend");

  if (!input || !send) return;

  send.addEventListener("click", () => {
    sendChatMessage();
  });

  input.addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      sendChatMessage();
    }
  });

  document.querySelectorAll(".chat-action").forEach(button => {
    button.addEventListener("click", () => {
      sendChatMessage(button.textContent);
    });
  });
}

updateBell();
initChat();
route();
refresh();
