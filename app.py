from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import db
from training_logic import build_ai_prompt, build_chart_data, compute_session_fuel, deterministic_recommendations, readiness, summarize_activities, summarize_body_metrics


BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Naufal Marathon Training")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def profile_text() -> str:
    return (BASE_DIR / "AGENTS.md").read_text()


@app.on_event("startup")
def startup() -> None:
    db.init_db()


def session_description(session: dict) -> str:
    session_type = session["session_type"]
    label = session.get("label", "").lower()
    distance = session.get("distance_km") or 0
    tags = set(tag for tag in session.get("tags", "").split(",") if tag)
    parts: list[str] = []

    if session_type == "rest":
        parts.append("Rest day. Keep steps easy and protect recovery.")
    elif session_type == "hike":
        parts.append("Hike replaces run load. Keep effort easy and descend carefully.")
    elif session_type == "race":
        if distance >= 40:
            parts.append("Race day. Start easy with 9:1 run-walk and fuel every 40 min.")
        elif distance >= 20:
            if "steady" in label:
                parts.append("HM steady: marathon-effort practice. Controlled Z2-Z3, run-walk allowed, finish relaxed.")
            else:
                parts.append("HM easy: treat as a long run. Conversational effort, run-walk allowed, finish fresh.")
        else:
            parts.append("10K steady: strong but controlled. Short phrases ok, no redline.")
    elif session_type == "long":
        parts.append(f"{distance:g} km easy long run. Use 9:1 run-walk and stay conversational.")
    elif session_type == "quality":
        parts.append(f"{distance:g} km steady session. Warm up, hold comfortable marathon effort, cool down.")
    elif session_type == "strength":
        parts.append("Strength focus. Full-body, controlled load, no grinding.")
    elif session_type == "recovery":
        if distance > 0:
            parts.append(f"{distance:g} km recovery or walk. Keep it very easy.")
        else:
            parts.append("Recovery walk. Keep it very easy.")
    else:
        if distance > 0:
            parts.append(f"{distance:g} km easy. Conversational Z2 effort.")
        else:
            parts.append("Easy walk or mobility. Keep HR under 150.")

    if session.get("has_strength"):
        parts.append("Add full-body strength.")
    if session.get("has_leg_day"):
        parts.append("Add 40 min controlled leg day after the run.")
    if "race" not in tags and session_type in {"easy", "long", "recovery"}:
        parts.append("HR target <150.")
    return " ".join(parts)


def actual_summary_for_date(activities: list[dict], session_date: str) -> str:
    actuals = [
        activity for activity in activities
        if activity["activity_date"].startswith(session_date)
    ]
    if not actuals:
        return ""
    parts = []
    for activity in actuals:
        distance = activity.get("distance") or 0
        if "Running" in activity["activity_type"]:
            hr = f", HR {activity['avg_hr']}" if activity.get("avg_hr") else ""
            parts.append(f"{distance:g} km run{hr}")
        elif activity["activity_type"] == "Strength Training":
            parts.append("strength")
        else:
            parts.append(activity["activity_type"].lower())
    return "Logged: " + " + ".join(parts) + "."


def grouped_sessions(activities: list[dict] | None = None) -> list[dict]:
    activities = activities or db.list_activities()
    latest_body = db.latest_body_metric()
    weight_kg: float = (latest_body or {}).get("weight_kg") or 70.0
    bmr: int = (latest_body or {}).get("bmr") or 1480
    groups: dict[int, list[dict]] = defaultdict(list)
    for session in db.list_planned_sessions():
        session["tag_list"] = [tag for tag in session["tags"].split(",") if tag]
        session["dynamic_description"] = session_description(session)
        cal, prot = compute_session_fuel(session, weight_kg, bmr)
        session["planned_calories"] = cal
        session["planned_protein"] = prot
        session["completed"] = any(
            activity["activity_date"].startswith(session["session_date"])
            for activity in activities
        )
        session["actual_summary"] = actual_summary_for_date(activities, session["session_date"])
        groups[session["week_no"]].append(session)
    result = []
    for week_no in sorted(groups):
        sessions = groups[week_no]
        start = sessions[0]["session_date"]
        end = sessions[-1]["session_date"]
        total_km = sum(s["distance_km"] or 0 for s in sessions if s["session_type"] != "race" or s["distance_km"] < 30)
        result.append({
            "week_no": week_no,
            "start": start,
            "end": end,
            "summary": f"~{round(total_km)} km",
            "sessions": sessions,
        })
    return result


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    activities = db.list_activities()
    planned = db.list_planned_sessions()
    body_metrics = db.list_body_metrics()
    summary = summarize_activities(activities, planned)
    import json
    charts = build_chart_data(activities, planned)
    context = {
        "request": request,
        "summary": summary,
        "body_summary": summarize_body_metrics(body_metrics),
        "readiness": readiness(summary),
        "recommendations": deterministic_recommendations(activities, planned, body_metrics),
        "weeks": grouped_sessions(activities),
        "latest_activities": activities[:8],
        "latest_body_metrics": body_metrics[:5],
        "latest_ai": db.latest_ai(),
        "charts_json": json.dumps(charts),
    }
    return templates.TemplateResponse("dashboard.html", context)


@app.get("/activities/new", response_class=HTMLResponse)
def new_activity(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("activity_form.html", {"request": request, "prefill": {}, "csv_text": "", "parse_error": None})


def normalize_datetime(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    return parsed.replace(second=0, microsecond=0).isoformat(sep=" ")


def parse_garmin_csv_activity(csv_text: str) -> dict:
    from training_logic import parse_float, parse_int

    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    row = next(reader, None)
    if not row:
        raise ValueError("Paste the CSV header and one activity row.")
    date_value = row.get("Date")
    if not date_value:
        raise ValueError("CSV row is missing Date.")
    activity_date = datetime.strptime(date_value, "%Y-%m-%d %H:%M:%S").isoformat(sep=" ")
    return {
        "activity_type": row.get("Activity Type") or "Other",
        "activity_date": activity_date,
        "title": row.get("Title") or row.get("Activity Type") or "",
        "distance": parse_float(row.get("Distance")),
        "calories": parse_int(row.get("Calories")),
        "duration": row.get("Time") or "",
        "avg_hr": parse_int(row.get("Avg HR")),
        "max_hr": parse_int(row.get("Max HR")),
        "aerobic_te": parse_float(row.get("Aerobic TE")),
        "avg_speed": row.get("Avg Pace") or row.get("Avg Speed") or "",
        "max_speed": row.get("Best Pace") or row.get("Max Speed") or "",
        "total_ascent": parse_float(row.get("Total Ascent")),
        "total_descent": parse_float(row.get("Total Descent")),
        "steps": parse_int(row.get("Steps")),
        "total_sets": parse_int(row.get("Total Sets")),
        "body_battery_drain": parse_int(row.get("Body Battery Drain")),
        "moving_time": row.get("Moving Time") or row.get("Time") or "",
        "elapsed_time": row.get("Elapsed Time") or row.get("Time") or "",
        "notes": "Imported from pasted Garmin CSV row",
    }


def datetime_local_value(activity_date: str | None) -> str:
    if not activity_date:
        return ""
    return datetime.fromisoformat(activity_date).strftime("%Y-%m-%dT%H:%M")


@app.post("/activities")
def create_activity(
    activity_type: Annotated[str, Form()],
    activity_date: Annotated[str, Form()],
    title: Annotated[str, Form()] = "",
    distance: Annotated[str, Form()] = "",
    calories: Annotated[str, Form()] = "",
    duration: Annotated[str, Form()] = "",
    avg_hr: Annotated[str, Form()] = "",
    max_hr: Annotated[str, Form()] = "",
    aerobic_te: Annotated[str, Form()] = "",
    avg_speed: Annotated[str, Form()] = "",
    total_ascent: Annotated[str, Form()] = "",
    total_descent: Annotated[str, Form()] = "",
    steps: Annotated[str, Form()] = "",
    total_sets: Annotated[str, Form()] = "",
    body_battery_drain: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
) -> RedirectResponse:
    from training_logic import parse_float, parse_int

    db.insert_activity({
        "activity_type": activity_type,
        "activity_date": normalize_datetime(activity_date),
        "title": title or activity_type,
        "distance": parse_float(distance),
        "calories": parse_int(calories),
        "duration": duration,
        "avg_hr": parse_int(avg_hr),
        "max_hr": parse_int(max_hr),
        "aerobic_te": parse_float(aerobic_te),
        "avg_speed": avg_speed,
        "max_speed": "",
        "total_ascent": parse_float(total_ascent),
        "total_descent": parse_float(total_descent),
        "steps": parse_int(steps),
        "total_sets": parse_int(total_sets),
        "body_battery_drain": parse_int(body_battery_drain),
        "moving_time": duration,
        "elapsed_time": duration,
        "notes": notes,
    })
    return RedirectResponse("/", status_code=303)


@app.post("/activities/preview-csv", response_class=HTMLResponse)
def preview_activity_csv(
    request: Request,
    csv_text: Annotated[str, Form()],
) -> HTMLResponse:
    try:
        activity = parse_garmin_csv_activity(csv_text)
        prefill = {
            **activity,
            "activity_date_local": datetime_local_value(activity["activity_date"]),
        }
        error = None
    except Exception as exc:
        prefill = {}
        error = str(exc)
    return templates.TemplateResponse("activity_form.html", {
        "request": request,
        "prefill": prefill,
        "csv_text": csv_text,
        "parse_error": error,
    })


@app.post("/activities/import-csv")
def import_activity_csv(
    csv_text: Annotated[str, Form()],
) -> RedirectResponse:
    activity = parse_garmin_csv_activity(csv_text)
    db.insert_activity(activity)
    return RedirectResponse("/", status_code=303)


@app.get("/body/new", response_class=HTMLResponse)
def new_body_metric(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("body_form.html", {
        "request": request,
        "latest": db.latest_body_metric(),
        "history": db.list_body_metrics(8),
    })


@app.post("/body")
def create_body_metric(
    measured_at: Annotated[str, Form()],
    weight_kg: Annotated[str, Form()],
    body_fat_percent: Annotated[str, Form()] = "",
    bmr: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
) -> RedirectResponse:
    from training_logic import parse_float, parse_int

    weight = parse_float(weight_kg)
    fat = parse_float(body_fat_percent)
    db.insert_body_metric({
        "measured_at": measured_at,
        "weight_kg": weight,
        "body_fat_percent": fat,
        "bmr": parse_int(bmr),
        "notes": notes,
    })
    return RedirectResponse("/", status_code=303)


@app.get("/ai", response_class=HTMLResponse)
def ai_page(request: Request) -> HTMLResponse:
    activities = db.list_activities()
    planned = db.list_planned_sessions()
    body_metrics = db.list_body_metrics()
    prompt = build_ai_prompt(profile_text(), activities, planned, body_metrics)
    return templates.TemplateResponse("ai.html", {
        "request": request,
        "prompt": prompt,
        "latest_ai": db.latest_ai(),
    })


@app.get("/ai/prompt.txt", response_class=PlainTextResponse)
def ai_prompt_txt() -> str:
    return build_ai_prompt(profile_text(), db.list_activities(), db.list_planned_sessions(), db.list_body_metrics())


@app.post("/ai")
def save_ai_recommendation(
    prompt: Annotated[str, Form()],
    response: Annotated[str, Form()],
) -> RedirectResponse:
    db.save_ai(prompt, response)
    return RedirectResponse("/", status_code=303)
