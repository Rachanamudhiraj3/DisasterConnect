# Project Summary — Local Disaster Alert System ("Disaster Connect")

_Updated 2026-09-20 after reading every source, config, script, CI and doc file in the repo._

## What it is

A **local-first, offline-first multi-hazard alert system**. It polls (simulated) sensors + GPS every 5 s, decides whether a **flood, earthquake, storm/thunderstorm or tsunami** risk is high using **rule-based agents**, and fires a buzzer + GSM SMS (always) plus an app push (only when online). The internet only ever *adds* things (weather cross-check, push, LLM-written sentence) — it is never required. Every network call fails safe (returns `None`/`[]`).

## Architecture

```
main.py  ──► sensors/reader.py   (GPS + 6 simulated readings)
   │         network/connectivity.py (raw socket to 8.8.8.8:53)
   │         network/weather.py      (Open-Meteo, no key)
   │         network/earthquakes.py  (USGS + data/earthquake_catalog.json)
   ├──────► agents/graph.py  (LangGraph chain)
   │            flood → earthquake → storm → tsunami → combine_risk → explain
   ├──────► alerts/dispatcher.py (buzzer, SMS, push, save alert)
   └──────► database/db.py (SQLite: readings, alerts)

backend/server.py (FastAPI, port 5000) ──► same pipeline + serves frontend/
frontend/index.html + mobile.css + mobile.js  (mobile UI "Disaster Connect")
```

## File-by-file

| File | Role |
|---|---|
| `main.py` | Entry point. `run_loop()` (connectivity check → GPS/sensors → save → weather → agent → dispatch → sleep 5 s; back-online triggers `sync_unsynced_readings`) and `run_once()` (single cycle, optional location/date/country for historical replay). CLI: `--mode auto/online/offline`, `--once`. |
| `config/settings.py` | All thresholds/switches; loads `.env` via python-dotenv. Flood: water < 80 cm, rain > 30 mm/h. Quake STA/LTA ≥ 3.0. Storm: wind ≥ 70 km/h, rain ≥ 50 mm/h. Tsunami: sea-level change ≥ 50 cm. Flood map radius 2 km, shelter search 5 km, poll 5 s, connectivity timeout 2 s. `USE_REAL_HARDWARE`, `USE_LLM_EXPLANATION` (default true), `GROQ_API_KEY`. |
| `sensors/reader.py` | Simulated GPS (Pune ± jitter) and sensors: water level, rain rate, pressure, vibration, wind speed, sea-level change, with random danger spikes. Real-hardware code (NEO-6M, HC-SR04, BME280, MPU6050) is commented out and raises `NotImplementedError` if enabled. |
| `network/connectivity.py` | `is_online()` — honours forced modes, else a fast TCP connect. |
| `network/weather.py` | Open-Meteo current weather → temp, rain, precip, pressure, wind, weather code, readable condition + icon. Returns `None` on failure. |
| `network/earthquakes.py` | Historical quake lookup: USGS (M ≥ 4.5, 1500 km radius, ±1 day padding) merged/deduped with the offline JSON catalog. `find_historical_earthquakes` (range) and `find_historical_earthquake` (strongest single). |
| `network/shelters.py` | OpenStreetMap Overpass lookup of candidate safe houses (shelters, assembly points, community centres, hospitals, fire/police, stadiums); nearest 30 with distance/address/phone/hours. Not an official registry. |
| `agents/flood_agent.py` | Water level, rain rate, or external precipitation > 10 mm → high. |
| `agents/earthquake_agent.py` | STA/LTA on a 200-sample rolling deque (5-sample short window); historical event short-circuits to high. `check_earthquake_risk_isolated` scores against a fixed quiet baseline for repeatable manual tests. |
| `agents/storm_agent.py` | Thunderstorm weather codes 95/96/99, wind or extreme-rain thresholds. |
| `agents/tsunami_agent.py` | Only rapid *coastal* sea-level change (river level is deliberately not evidence). |
| `agents/graph.py` | LangGraph `StateGraph` chain. Priority in `combine_risk`: **tsunami > earthquake > storm > flood**. `explain` node optionally rewrites the reasoning via Groq (`openai/gpt-oss-20b`, 4 s timeout) — can never change the risk. `run_agent` and `run_agent_isolated` (used by manual test, bypasses shared quake history). |
| `alerts/dispatcher.py` | Buzzer + GSM SMS always; app push only online; saves alert to SQLite. SMS contact hardcoded to `+917620622761`. Only acts on `overall_risk == "high"`. |
| `database/db.py` | SQLite (`data/disaster_alert.db`): `readings` (incl. wind, sea-level, `synced` flag; auto-migrates old DBs) and `alerts`. Helpers for save/recent/unsynced/mark_synced. |
| `backend/server.py` | FastAPI app. Endpoints: `GET /api/status`, `/api/config`, `/api/countries`, `/api/readings`, `/api/alerts`, `/api/safe-houses` (auto-widens radius up to 20 km), `/api/prediction` (linear-trend flood estimate + vibration activity, explicitly *not* quake prediction); `POST /api/location`, `/api/dashboard` (compact mobile payload), `/api/manual-test`, `/api/historical-test`. Serves `frontend/` at `/`. Runs on `0.0.0.0:5000`. |
| `frontend/index.html`, `mobile.css`, `mobile.js` | **The active UI.** Vanilla JS mobile app with views Home, Shelter, SOS, AI Prediction, Report. Uses browser Geolocation (or `?lat=&lon=`), caches last location/shelters in localStorage, browser notifications, call/share/direction links, SVG charts. Uses `textContent` only (no innerHTML for server data). |
| `frontend/app.js`, `style.css` | Older desktop dashboard (Leaflet maps, history, historical-event test, manual test UI). **No longer referenced by `index.html`** — leftover. |
| `frontend/dashboard.py`, `test_simulator.py` | Legacy Streamlit views, kept for reference (their docstrings say so). |
| `data/` | SQLite DB (gitignored) and `earthquake_catalog.json`. |
| `scripts/` | `setup`, `run`, `run_offline`, `run_web`, `run_dashboard` in `.bat` and `.sh` form. |
| `requirements.txt` | langgraph, langchain-core, fastapi, uvicorn, requests, python-dotenv, groq, streamlit (legacy). |
| `.env.example`, `.gitignore` | `GROQ_API_KEY`, `USE_LLM_EXPLANATION`, `DISASTER_APP_MODE`; ignores venv, pycache, `data/*.db`, `.env`. |
| `.github/workflows/ci.yml` | 3 jobs: `main.py --once` offline; start server and curl `/api/status`, `/api/readings`, `/api/alerts`; import check of core modules. |
| `README.md`, `PROJECT_WALKTHROUGH.md` | Human docs (see "Doc drift" below). |

## Ways to run

| Command | Result |
|---|---|
| `python main.py [--mode offline] [--once]` | Monitoring loop |
| `python -m backend.server` | Web UI at http://localhost:5000 |
| `streamlit run frontend/dashboard.py` / `test_simulator.py` | Legacy views |

## Online vs offline

| | Offline | Online |
|---|---|---|
| Risk decision | Local rules | Same rules + weather cross-check (flood, storm code) |
| Buzzer + SMS | Yes | Yes |
| App push | No | Yes |
| Readings | Queued (`synced=0`) | Synced on reconnect |
| LLM explanation | Skipped | If `GROQ_API_KEY` set |

## Known gaps / risks

- All sensors and GPS are simulated; thresholds are untuned against real hardware.
- Single hardcoded SMS number in `dispatcher.py`.
- `_vibration_history` is in-memory (resets on restart, not shared across processes).
- No authentication; server binds `0.0.0.0`.
- `/api/manual-test` accepts only 4 sensor values, so wind/sea-level default to 0 (storm/tsunami can't be tested there).
- `sync_unsynced_readings` only marks rows synced; the real upload call is a commented stub.
- LangGraph is a straight chain with no branching — more framework than the pipeline needs.
- `frontend/app.js` + `style.css` are dead code; Streamlit files are legacy.
- `is_online()` in `online` mode returns True without checking.

## Doc drift (docs to fix)

- `PROJECT_WALKTHROUGH.md` still describes only **flood + earthquake** (storm and tsunami agents are missing), a 4-node graph diagram, "Flask" (it's FastAPI), a `test.py` file that no longer exists, and `.env` not being handled (now loaded by python-dotenv).
- `README.md` says the graph combines "both" agents and its layout omits `storm_agent.py`, `tsunami_agent.py`, `shelters.py`, `earthquakes.py`, `mobile.*` files.
- `ci.yml` job is named "Flask server health check" but the server is FastAPI; its import check does not cover the storm/tsunami agents.
- `dashboard.py` footer mentions `python -m app.main`, which is stale (should be `python main.py`).
