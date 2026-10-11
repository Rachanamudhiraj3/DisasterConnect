"""
Local SQLite storage. Works fully offline -- this is the system's memory.

Two tables:
- readings: every sensor snapshot, tagged with whether it was later synced
  to the cloud (used for the "sync on reconnect" behaviour).
- alerts: every alert an agent decided to raise, with its reasoning.
"""

import sqlite3
from datetime import datetime, timezone

from config.settings import DB_PATH


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            lat REAL,
            lon REAL,
            water_level_cm REAL,
            rain_rate_mm_hr REAL,
            pressure_hpa REAL,
            vibration_g REAL,
            wind_speed_kmh REAL,
            sea_level_change_cm REAL,
            synced INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            hazard_type TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            reasoning TEXT,
            lat REAL,
            lon REAL,
            mode TEXT,

            title TEXT,
            message TEXT,
            recommended_action TEXT,
            priority TEXT
        );
        """
    )

    # -----------------------------------------------------
    # Reading table migration
    # -----------------------------------------------------

    reading_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(readings)")
    }

    for name in ("wind_speed_kmh", "sea_level_change_cm"):
        if name not in reading_columns:
            conn.execute(
                f"ALTER TABLE readings ADD COLUMN {name} REAL"
            )

    # -----------------------------------------------------
    # Alert table migration
    # -----------------------------------------------------

    alert_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(alerts)")
    }

    new_alert_columns = {
        "title": "TEXT",
        "message": "TEXT",
        "recommended_action": "TEXT",
        "priority": "TEXT",
    }

    for name, column_type in new_alert_columns.items():
        if name not in alert_columns:
            conn.execute(
                f"ALTER TABLE alerts ADD COLUMN {name} {column_type}"
            )

    conn.commit()
    conn.close()

def save_reading(reading: dict) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO readings
           (timestamp, lat, lon, water_level_cm, rain_rate_mm_hr, pressure_hpa, vibration_g, wind_speed_kmh, sea_level_change_cm)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now(timezone.utc).isoformat(),
            reading.get("lat"),
            reading.get("lon"),
            reading.get("water_level_cm"),
            reading.get("rain_rate_mm_hr"),
            reading.get("pressure_hpa"),
            reading.get("vibration_g"),
            reading.get("wind_speed_kmh"),
            reading.get("sea_level_change_cm"),
        ),
    )
    conn.commit()
    reading_id = cur.lastrowid
    conn.close()
    return reading_id


def save_alert(
    hazard_type: str,
    risk_level: str,
    reasoning: str,
    lat,
    lon,
    mode: str,
    title: str = "",
    recommended_action: str = "",
    priority: str = "",
    message: str = "",
):
    conn = get_connection()

    conn.execute(
        """
        INSERT INTO alerts (
            timestamp,
            hazard_type,
            risk_level,
            reasoning,
            lat,
            lon,
            mode,
            title,
            message,
            recommended_action,
            priority
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            hazard_type,
            risk_level,
            reasoning,
            lat,
            lon,
            mode,
            title,
            message,
            recommended_action,
            priority,
        ),
    )

    conn.commit()
    conn.close()

def recent_similar_alert(
    hazard_type: str,
    lat: float,
    lon: float,
    minutes: int = 10,
) -> bool:
    """
    Check whether the same hazard was recently raised
    near the same location.

    This prevents repeated SMS/buzzer alerts when the
    dashboard is refreshed multiple times.
    """

    conn = get_connection()

    row = conn.execute(
        """
        SELECT timestamp
        FROM alerts
        WHERE hazard_type = ?
        AND lat BETWEEN ? AND ?
        AND lon BETWEEN ? AND ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            hazard_type,
            lat - 0.01,
            lat + 0.01,
            lon - 0.01,
            lon + 0.01,
        ),
    ).fetchone()

    conn.close()

    if not row:
        return False

    try:
        last_time = datetime.fromisoformat(row["timestamp"])

        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)

        elapsed = (
            datetime.now(timezone.utc) - last_time
        ).total_seconds() / 60

        return elapsed < minutes

    except Exception:
        return False

def recent_readings(limit: int = 50):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM readings ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def recent_alerts(limit: int = 20):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def unsynced_readings():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM readings WHERE synced = 0").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_synced(reading_id: int):
    conn = get_connection()
    conn.execute("UPDATE readings SET synced = 1 WHERE id = ?", (reading_id,))
    conn.commit()
    conn.close()
