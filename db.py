from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "training.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_type TEXT NOT NULL,
                activity_date TEXT NOT NULL,
                title TEXT,
                distance REAL,
                calories INTEGER,
                duration TEXT,
                avg_hr INTEGER,
                max_hr INTEGER,
                aerobic_te REAL,
                avg_speed TEXT,
                max_speed TEXT,
                total_ascent REAL,
                total_descent REAL,
                steps INTEGER,
                total_sets INTEGER,
                body_battery_drain INTEGER,
                moving_time TEXT,
                elapsed_time TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS planned_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_no INTEGER NOT NULL,
                session_date TEXT NOT NULL,
                day_label TEXT NOT NULL,
                label TEXT NOT NULL,
                session_type TEXT NOT NULL,
                distance_km REAL,
                planned_calories INTEGER NOT NULL,
                planned_protein INTEGER NOT NULL,
                description TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '',
                has_strength INTEGER NOT NULL DEFAULT 0,
                has_leg_day INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ai_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS body_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                measured_at TEXT NOT NULL,
                weight_kg REAL NOT NULL,
                body_fat_percent REAL,
                bmr INTEGER,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
    seed_planned_sessions()
    seed_body_metrics()


def insert_activity(activity: dict[str, Any]) -> None:
    columns = [
        "activity_type", "activity_date", "title", "distance", "calories", "duration",
        "avg_hr", "max_hr", "aerobic_te", "avg_speed", "max_speed", "total_ascent",
        "total_descent", "steps", "total_sets", "body_battery_drain", "moving_time",
        "elapsed_time", "notes",
    ]
    values = [activity.get(c) for c in columns]
    placeholders = ",".join(["?"] * len(columns))
    with connect() as conn:
        conn.execute(
            f"INSERT INTO activities ({','.join(columns)}) VALUES ({placeholders})",
            values,
        )


def insert_body_metric(metric: dict[str, Any]) -> None:
    columns = [
        "measured_at", "weight_kg", "body_fat_percent", "bmr", "notes",
    ]
    values = [metric.get(c) for c in columns]
    placeholders = ",".join(["?"] * len(columns))
    with connect() as conn:
        conn.execute(
            f"INSERT INTO body_metrics ({','.join(columns)}) VALUES ({placeholders})",
            values,
        )


def seed_body_metrics() -> None:
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM body_metrics").fetchone()[0]
        if count:
            return
    insert_body_metric({
        "measured_at": "2026-06-02",
        "weight_kg": 70.0,
        "body_fat_percent": 20.5,
        "bmr": 1480,
        "notes": "Initial profile baseline",
    })


PLANNED = [
    (1, "2026-06-01", "Mon - Jun 1", "Easy 2k", "strength", 2.2, 2250, 140, "Strength 57 min + 2.2k treadmill. Logged.", "easy,strength", 1, 0),
    (1, "2026-06-02", "Tue - Jun 2", "Easy 5k", "easy", 5.04, 2150, 130, "5.04k treadmill. Avg HR 142, max 156.", "easy", 0, 0),
    (1, "2026-06-03", "Wed - Jun 3", "Easy 6k", "easy", 6, 2200, 130, "Pure Z2, treadmill ok.", "easy", 0, 0),
    (1, "2026-06-04", "Thu - Jun 4", "Easy 5k", "easy", 5, 2300, 140, "Full-body 40 min. Mon done = 2nd.", "easy,strength", 1, 0),
    (1, "2026-06-05", "Fri - Jun 5", "Rest", "rest", 0, 1850, 135, "Legs fresh for long run.", "rest", 0, 0),
    (1, "2026-06-06", "Sat - Jun 6", "Long 16k", "long", 16, 3050, 140, "Easy 9:1 + 40 min controlled leg day.", "long,legs", 0, 1),
    (1, "2026-06-07", "Sun - Jun 7", "Recover walk", "recovery", 0, 1950, 130, "30 min walk, optional 2k jog if fresh.", "easy", 0, 0),
]


def planned_rows() -> list[tuple[Any, ...]]:
    rows = list(PLANNED)
    definitions = [
        (2, "2026-06-08", [("Mon", "Strength", "strength", 0, 2000, 140, "Full-body strength + mobility.", "strength", 1, 0), ("Tue", "Easy 4k", "easy", 4, 2100, 130, "Z2, conversational. Keep it relaxed.", "easy", 0, 0), ("Wed", "Easy 4k", "easy", 4, 2250, 140, "Full-body strength. No strides this week.", "easy,strength", 1, 0), ("Thu", "Rest", "rest", 0, 1900, 135, "Extra rest before race weekend.", "rest", 0, 0), ("Fri", "Rest", "rest", 0, 1900, 135, "Pre-race. Hydrate, sleep.", "rest", 0, 0), ("Sat", "10K easy-steady", "race", 10, 2600, 130, "Steady only if fresh. Do not max.", "race", 0, 0), ("Sun", "HM easy", "race", 21.1, 3100, 130, "EASY/run-walk = long run. HR <150, finish relaxed.", "long,race", 0, 0)]),
        (3, "2026-06-15", [("Mon", "Rest", "rest", 0, 1900, 135, "Recover from race weekend.", "rest", 0, 0), ("Tue", "Easy 6k", "easy", 6, 2350, 140, "Very easy + full-body strength.", "easy,strength", 1, 0), ("Wed", "Easy 7k", "easy", 7, 2250, 130, "Z2, conversational.", "easy", 0, 0), ("Thu", "Easy 5k", "easy", 5, 2300, 140, "Full-body strength + 4x30s strides.", "easy,strength", 1, 0), ("Fri", "Rest", "rest", 0, 1900, 135, "Pre-race.", "rest", 0, 0), ("Sat", "Easy 4k", "easy", 4, 2100, 130, "Shakeout.", "easy", 0, 0), ("Sun", "HM steady", "race", 21.1, 3100, 130, "Marathon effort, run-walk ok.", "long,race", 0, 0)]),
        (4, "2026-06-22", [("Mon", "Rest", "rest", 0, 1850, 135, "Full rest.", "rest", 0, 0), ("Tue", "Easy 8k", "easy", 8, 2450, 140, "Z2 + full-body strength.", "easy,strength", 1, 0), ("Wed", "Steady 8k", "quality", 8, 2450, 135, "2k WU - 4k MP - 2k CD.", "quality", 0, 0), ("Thu", "Easy 6k", "easy", 6, 2350, 140, "Relaxed Z2 + full-body strength.", "easy,strength", 1, 0), ("Fri", "Rest", "rest", 0, 1850, 135, "Full rest.", "rest", 0, 0), ("Sat", "Long 22k", "long", 22, 3350, 140, "Easy run-walk + 40 min controlled leg day.", "long,legs", 0, 1), ("Sun", "Recover 4k", "recovery", 4, 2100, 130, "Jog or walk.", "easy", 0, 0)]),
        (5, "2026-06-29", [("Mon", "Rest", "rest", 0, 1850, 135, "Full rest.", "rest", 0, 0), ("Tue", "Easy 8k", "easy", 8, 2450, 140, "Z2 + full-body strength.", "easy,strength", 1, 0), ("Wed", "Steady 9k", "quality", 9, 2500, 135, "3k WU - 4k MP - 2k CD.", "quality", 0, 0), ("Thu", "Easy 6k", "easy", 6, 2350, 140, "Relaxed Z2 + full-body strength.", "easy,strength", 1, 0), ("Fri", "Rest", "rest", 0, 1850, 135, "Legs fresh.", "rest", 0, 0), ("Sat", "Long 25k", "long", 25, 3450, 140, "Easy run-walk + 40 min controlled leg day.", "long,legs", 0, 1), ("Sun", "Recover 5k", "recovery", 5, 2150, 130, "Easy.", "easy", 0, 0)]),
        (6, "2026-07-06", [("Mon", "Rest", "rest", 0, 1850, 135, "Full rest.", "rest", 0, 0), ("Tue", "Easy 9k", "easy", 9, 2500, 140, "Z2 + full-body strength.", "easy,strength", 1, 0), ("Wed", "Steady 10k", "quality", 10, 2550, 135, "3k WU - 5k MP - 2k CD.", "quality", 0, 0), ("Thu", "Easy 7k", "easy", 7, 2400, 140, "Relaxed Z2 + full-body strength.", "easy,strength", 1, 0), ("Fri", "Rest", "rest", 0, 1850, 135, "Full rest.", "rest", 0, 0), ("Sat", "LONG 28k", "long", 28, 3600, 140, "Dress rehearsal + 40 min controlled leg day.", "long,legs", 0, 1), ("Sun", "Recover 5k", "recovery", 5, 2150, 130, "Walk/jog.", "easy", 0, 0)]),
        (7, "2026-07-13", [("Mon", "Rest", "rest", 0, 1850, 135, "Full rest.", "rest", 0, 0), ("Tue", "Easy 7k", "easy", 7, 2400, 140, "Full-body strength.", "easy,strength", 1, 0), ("Wed", "Easy 7k", "easy", 7, 2250, 130, "+ 4x30s strides.", "easy", 0, 0), ("Thu", "Easy 5k", "easy", 5, 2300, 140, "Z2 + full-body strength.", "easy,strength", 1, 0), ("Fri", "Rest", "rest", 0, 1900, 135, "Pre-race.", "rest", 0, 0), ("Sat", "Easy 4k", "easy", 4, 2100, 130, "Shakeout.", "easy", 0, 0), ("Sun", "HM steady", "race", 21.1, 3100, 130, "Goal marathon pace. Do not redline.", "long,race", 0, 0)]),
        (8, "2026-07-20", [("Mon", "Rest", "rest", 0, 1900, 135, "Recover HM.", "rest", 0, 0), ("Tue", "Easy 8k", "easy", 8, 2450, 140, "Z2 + strength, prep hike legs.", "easy,strength", 1, 0), ("Wed", "Easy 7k", "easy", 7, 2250, 130, "Z2.", "easy", 0, 0), ("Thu", "Easy 5k", "easy", 5, 2300, 140, "Full-body strength + mobility.", "easy,strength", 1, 0), ("Fri", "Travel/Rest", "rest", 0, 2000, 135, "Pack, hydrate.", "rest", 0, 0), ("Sat-Sun", "Merbabu hike", "hike", 0, 3400, 140, "Big vert. Hydrate, eat, careful descent.", "hike", 0, 0)]),
        (9, "2026-07-27", [("Mon", "Rest", "rest", 0, 1950, 135, "Legs sore from hike.", "rest", 0, 0), ("Tue", "Easy 7k", "easy", 7, 2400, 140, "Loosener + light strength.", "easy,strength", 1, 0), ("Wed", "Steady 8k", "quality", 8, 2450, 135, "3k WU - 3k MP - 2k CD.", "quality", 0, 0), ("Thu", "Easy 8k", "easy", 8, 2450, 140, "Z2 + full-body strength.", "easy,strength", 1, 0), ("Fri", "Rest", "rest", 0, 1850, 135, "Legs fresh.", "rest", 0, 0), ("Sat", "LONG 30k", "long", 30, 3700, 145, "Longest run + 40 min controlled leg day.", "long,legs", 0, 1), ("Sun", "Recover 5k", "recovery", 5, 2150, 130, "Easy.", "easy", 0, 0)]),
        (10, "2026-08-03", [("Mon", "Rest", "rest", 0, 1850, 135, "Full rest.", "rest", 0, 0), ("Tue", "Easy 8k", "easy", 8, 2400, 140, "Z2 + light strength, hike prep.", "easy,strength", 1, 0), ("Wed", "Easy 6k", "easy", 6, 2200, 130, "+ 4x30s strides.", "easy", 0, 0), ("Thu", "Easy 4k", "easy", 4, 2250, 140, "Light full-body strength.", "easy,strength", 1, 0), ("Fri", "Travel/Rest", "rest", 0, 2000, 135, "Travel/rest.", "rest", 0, 0), ("Sat-Sun", "Sumbing hike", "hike", 0, 3300, 140, "Taper hike. Easy effort, careful descent.", "hike", 0, 0)]),
        (11, "2026-08-10", [("Mon", "Rest", "rest", 0, 1950, 135, "Recover hike.", "rest", 0, 0), ("Tue", "Easy 6k", "easy", 6, 2300, 140, "Light strength + 4x30s strides.", "easy,strength", 1, 0), ("Wed", "Easy 6k", "easy", 6, 2200, 130, "Z2.", "easy", 0, 0), ("Thu", "Easy 4k", "easy", 4, 2250, 140, "Light strength, then shakeout.", "easy,strength", 1, 0), ("Fri", "Rest", "rest", 0, 1900, 135, "Pre-race.", "rest", 0, 0), ("Sat", "10K steady", "race", 10, 2550, 130, "Controlled. If tired, jog it.", "race", 0, 0), ("Sun", "Easy 3k", "easy", 3, 2000, 130, "Loosen.", "easy", 0, 0)]),
        (12, "2026-08-17", [("Mon", "Light Strength", "strength", 0, 2100, 140, "Optional light full-body only.", "strength", 1, 0), ("Tue", "Easy 5k", "easy", 5, 2250, 130, "+ 4x30s strides. Fresh, not flat.", "easy", 0, 0), ("Wed", "Easy 4k", "easy", 4, 2150, 130, "Very easy.", "easy", 0, 0), ("Thu", "Rest", "rest", 0, 2500, 130, "Start carb-loading. Hydrate.", "rest", 0, 0), ("Fri", "Shakeout 3k", "easy", 3, 2700, 130, "Super easy + 2 strides. Prep kit.", "easy", 0, 0), ("Sat", "Rest", "rest", 0, 2800, 130, "Carb-load, hydrate, off legs.", "rest", 0, 0), ("Sun", "MARATHON", "race", 42.2, 3800, 130, "42.2k. Easy 9:1, fuel every 40 min.", "long,race", 0, 0)]),
    ]
    for week_no, start, days in definitions:
        base = datetime.fromisoformat(start).date()
        for idx, item in enumerate(days):
            day, label, stype, distance, kcal, protein, desc, tags, strength, legs = item
            rows.append((week_no, (base + timedelta(days=idx)).isoformat(), day, label, stype, distance, kcal, protein, desc, tags, strength, legs))
    return rows


def seed_planned_sessions() -> None:
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM planned_sessions").fetchone()[0]
        if count:
            return
        rows = planned_rows()
        for sort_order, row in enumerate(rows, start=1):
            conn.execute(
                """
                INSERT INTO planned_sessions
                (week_no, session_date, day_label, label, session_type, distance_km,
                 planned_calories, planned_protein, description, tags, has_strength, has_leg_day, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*row, sort_order),
            )


def list_activities(limit: int | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM activities ORDER BY activity_date DESC, id DESC"
    params: tuple[Any, ...] = ()
    if limit:
        query += " LIMIT ?"
        params = (limit,)
    with connect() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def list_planned_sessions() -> list[dict[str, Any]]:
    with connect() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM planned_sessions ORDER BY sort_order").fetchall()]


def list_body_metrics(limit: int | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM body_metrics ORDER BY measured_at DESC, id DESC"
    params: tuple[Any, ...] = ()
    if limit:
        query += " LIMIT ?"
        params = (limit,)
    with connect() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def latest_body_metric() -> dict[str, Any] | None:
    metrics = list_body_metrics(1)
    return metrics[0] if metrics else None


def latest_ai() -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM ai_recommendations ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None


def save_ai(prompt: str, response: str) -> None:
    with connect() as conn:
        conn.execute("INSERT INTO ai_recommendations (prompt, response) VALUES (?, ?)", (prompt, response))
