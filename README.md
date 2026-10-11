# Local Disaster Alert System

A local-first flood + earthquake alert system. Runs fully offline;
automatically uses the internet as an *optional* accuracy boost the
moment it's available, and falls back to local-only logic the moment
it's gone.

## Project layout

```
disaster-alert-system/
├── main.py               entry point — the monitoring loop
├── requirements.txt
├── README.md
├── .gitignore
│
├── scripts/               one-click setup + launchers (Windows .bat, Mac/Linux .sh)
├── config/                settings.py — thresholds, mode switches, paths
├── sensors/               reader.py — "Watch": sensors + GPS (simulated by default)
├── network/               connectivity.py — online/offline detection
│                          weather.py — optional online weather cross-check
├── agents/                flood_agent.py — rule-based flood risk check
│                          earthquake_agent.py — STA/LTA earthquake check
│                          graph.py — "Decide": LangGraph agent combining both
├── alerts/                dispatcher.py — "Warn": buzzer, SMS, app push
├── database/              db.py — SQLite storage
├── backend/               server.py — FastAPI API + serves the web frontend
├── frontend/              index.html / mobile.css / mobile.js — the web UI
└── data/                  disaster_alert.db lives here once you run it
```

Each folder does exactly one job — open `agents/` without touching
`alerts/`, swap `sensors/reader.py` for real hardware without touching
the agents, etc.

## Setup (do this once)

**Windows:** double-click `scripts/setup.bat`
**Mac/Linux:** run `./scripts/setup.sh` in a terminal

Both create a virtual environment and install everything in
`requirements.txt`. No hardware needed to try it — sensors are
simulated by default (`sensors/reader.py`), including occasional
random "danger spikes" so you can actually see alerts fire.

## Run it

| Script | What it does |
|---|---|
| `scripts/run.bat` / `run.sh` | **Recommended.** Monitoring loop in auto mode — online when internet is available, offline the instant it isn't |
| `scripts/run_offline.bat` / `.sh` | Forces offline mode, useful for testing without Wi-Fi |
| `scripts/run_web.bat` / `.sh` | Full web UI (FastAPI) at http://localhost:5000 |

Or run the equivalent commands by hand, if you prefer:

```bash
python main.py                 # auto: online when available, offline otherwise
python main.py --mode offline  # force offline
python main.py --once          # single loop iteration, for debugging

python -m backend.server       # full web UI at http://localhost:5000
```

### The web UI

`python -m backend.server` starts a FastAPI app at http://localhost:5000
serving a mobile-first Disaster Connect page, all backed by the exact same
`agents/graph.py` pipeline `main.py` uses — a browser, a phone on the same
network, and the CLI loop never disagree with each other:

- **Home** — reads your device's GPS via the browser's Geolocation API,
  runs a live detection, and displays current weather, sensor readings,
  risk status, and alerts. Only `{lat, lon}` is sent to the local server.
- **Shelter** — finds nearby candidate safe houses from OpenStreetMap,
  caches results for offline fallback, and offers directions/call actions.
- **SOS** — provides emergency-call links and shares a location link.
- **Report** — shows the alert log from local SQLite storage.

For browser GPS testing from a device that cannot grant location to plain
HTTP, append coordinates to the local URL, for example
`http://<computer-ip>:5000/?lat=18.5204&lon=73.8567`.

## How "auto" actually behaves

`network/connectivity.py` checks the connection on **every single loop**
(not just once at startup), so the system reacts immediately either way:

| | No internet | Internet available |
|---|---|---|
| Sensors + GPS | local hardware | same |
| Risk decision | rule-based agents (STA/LTA + thresholds) | same rules, plus external weather cross-check |
| Buzzer + SMS alert | always fires | always fires |
| App push / cloud log | not available | bonus channel |
| Offline backlog | queued in SQLite | synced automatically the moment connection returns |
| LLM-written explanation | skipped | on by default, if `GROQ_API_KEY` is set (opt out with `USE_LLM_EXPLANATION=false`) |

The alert decision **never depends on the internet being up** — going
online only adds extra confirmation and extra notification channels,
never a requirement to function.

## Secrets (GROQ_API_KEY)

Copy `.env.example` to `.env` and fill in `GROQ_API_KEY` -- `config/settings.py`
loads it automatically via `python-dotenv` on startup, no shell exports
needed. `.env` is gitignored; never commit it.

## Moving to real hardware

Every file that touches hardware has a clearly marked `if USE_REAL_HARDWARE:`
block with commented-out real code to fill in:

- `sensors/reader.py` — GPS (NEO-6M), water level (HC-SR04), rain gauge, pressure (BME280), vibration (MPU6050)
- `alerts/dispatcher.py` — buzzer (GPIO), SMS (SIM800L GSM module)

Set `USE_REAL_HARDWARE=true` as an environment variable once wired up.

## Tuning the thresholds

All risk thresholds live in `config/settings.py` — adjust
`FLOOD_WATER_LEVEL_CM`, `FLOOD_RAIN_RATE_MM_HR`, and
`EARTHQUAKE_STA_LTA_RATIO` against real local data once sensors are
deployed.

## Adding a new hazard (e.g. wildfire, landslide)

1. Add `agents/wildfire_agent.py` with a `check_wildfire_risk(sensors)` function, same shape as the existing two agents.
2. Wire it into `agents/graph.py`: add a node, an edge, and a branch in `_node_combine_risk`.
3. Add any new sensor readings it needs to `sensors/reader.py`.

Nothing in `alerts/`, `database/`, `backend/`, or `frontend/` needs to change.