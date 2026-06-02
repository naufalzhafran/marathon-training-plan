from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any


RACE_DATE = date(2026, 8, 23)
TODAY = date(2026, 6, 2)
Z2_MAX = 150


def parse_float(value: Any) -> float | None:
    if value in (None, "", "--"):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    value = parse_float(value)
    return int(value) if value is not None else None


def parse_duration_seconds(value: str | None) -> int | None:
    if not value or value == "--":
        return None
    parts = str(value).split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + int(float(s))
        if len(parts) == 2:
            m, s = parts
            return int(m) * 60 + int(float(s))
    except ValueError:
        return None
    return None


def monday_for(dt: date) -> date:
    return dt - timedelta(days=dt.weekday())


def is_run(activity: dict[str, Any]) -> bool:
    return "Running" in (activity.get("activity_type") or "")


def is_strength(activity: dict[str, Any]) -> bool:
    return (activity.get("activity_type") or "") == "Strength Training"


def summarize_activities(activities: list[dict[str, Any]], planned_sessions: list[dict[str, Any]]) -> dict[str, Any]:
    run_activities = [a for a in activities if is_run(a)]
    strength_activities = [a for a in activities if is_strength(a)]
    total_run_distance = sum(a.get("distance") or 0 for a in run_activities)

    weekly: dict[date, dict[str, Any]] = defaultdict(lambda: {"run_km": 0.0, "runs": 0, "strength": 0, "longest": 0.0, "hr_sum": 0, "hr_n": 0})
    for activity in activities:
        activity_date = datetime.fromisoformat(activity["activity_date"]).date()
        week = monday_for(activity_date)
        bucket = weekly[week]
        if is_run(activity):
            distance = activity.get("distance") or 0
            bucket["run_km"] += distance
            bucket["runs"] += 1
            bucket["longest"] = max(bucket["longest"], distance)
            if activity.get("avg_hr") is not None:
                bucket["hr_sum"] += activity["avg_hr"]
                bucket["hr_n"] += 1
        if is_strength(activity):
            bucket["strength"] += 1

    peak_week = max((w["run_km"] for w in weekly.values()), default=0.0)
    current_week = weekly.get(monday_for(TODAY), {"run_km": 0.0, "runs": 0, "strength": 0, "longest": 0.0, "hr_sum": 0, "hr_n": 0})
    recent_cutoff = TODAY - timedelta(days=90)
    recent_runs = [
        a for a in run_activities
        if datetime.fromisoformat(a["activity_date"]).date() >= recent_cutoff
    ]
    longest_recent = max((a.get("distance") or 0 for a in recent_runs), default=0.0)
    longest_all = max((a.get("distance") or 0 for a in run_activities), default=0.0)
    easy_hr_runs = [a for a in recent_runs if a.get("avg_hr") is not None and (a.get("distance") or 0) <= 10]
    hot_easy_runs = [a for a in easy_hr_runs if a["avg_hr"] > Z2_MAX]
    current_avg_hr = round(current_week["hr_sum"] / current_week["hr_n"]) if current_week["hr_n"] else None

    next_session = next(
        (s for s in planned_sessions if date.fromisoformat(s["session_date"]) >= TODAY),
        None,
    )

    return {
        "total_run_distance": round(total_run_distance, 1),
        "run_count": len(run_activities),
        "strength_count": len(strength_activities),
        "peak_week": round(peak_week, 1),
        "current_week_run_km": round(current_week["run_km"], 1),
        "current_week_runs": current_week["runs"],
        "current_week_strength": current_week["strength"],
        "current_week_avg_hr": current_avg_hr,
        "longest_recent": round(longest_recent, 1),
        "longest_all": round(longest_all, 1),
        "days_to_race": (RACE_DATE - TODAY).days,
        "next_session": next_session,
        "hot_easy_count": len(hot_easy_runs),
    }


def readiness(summary: dict[str, Any]) -> list[dict[str, Any]]:
    endurance = min(100, round((summary["longest_recent"] / 30) * 100))
    volume = min(100, round((summary["peak_week"] / 46) * 100))
    strength = min(100, round((summary["strength_count"] / 52) * 85))
    aerobic = 75 if summary["hot_easy_count"] <= 2 else max(35, 75 - summary["hot_easy_count"] * 5)
    consistency = min(90, 50 + summary["current_week_runs"] * 8 + summary["current_week_strength"] * 6)
    return [
        {"label": "Endurance (long run)", "score": endurance, "kind": "warn" if endurance < 60 else "ok"},
        {"label": "Weekly volume base", "score": volume, "kind": "ok" if volume >= 60 else "warn"},
        {"label": "Strength / durability", "score": strength, "kind": "ok"},
        {"label": "Aerobic efficiency", "score": aerobic, "kind": "bad" if aerobic < 55 else "ok"},
        {"label": "Consistency", "score": consistency, "kind": "ok"},
    ]


def summarize_body_metrics(metrics: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not metrics:
        return None
    latest = dict(metrics[0])
    weight = latest.get("weight_kg")
    fat_percent = latest.get("body_fat_percent")
    fat_mass = weight * fat_percent / 100 if weight is not None and fat_percent is not None else None
    protein_floor = max(130, round(weight * 1.8)) if weight else 130
    protein_ceiling = max(140, round(weight * 2.0)) if weight else 140
    previous = metrics[1] if len(metrics) > 1 else None
    weight_delta = round(weight - previous["weight_kg"], 1) if previous and weight is not None and previous.get("weight_kg") is not None else None
    fat_delta = round(fat_percent - previous["body_fat_percent"], 1) if previous and fat_percent is not None and previous.get("body_fat_percent") is not None else None
    return {
        "measured_at": latest["measured_at"],
        "weight_kg": round(weight, 1) if weight is not None else None,
        "body_fat_percent": round(fat_percent, 1) if fat_percent is not None else None,
        "fat_mass_kg": round(fat_mass, 1) if fat_mass is not None else None,
        "bmr": latest.get("bmr"),
        "protein_floor": protein_floor,
        "protein_ceiling": protein_ceiling,
        "weight_delta": weight_delta,
        "fat_delta": fat_delta,
    }


def deterministic_recommendations(
    activities: list[dict[str, Any]],
    planned_sessions: list[dict[str, Any]],
    body_metrics: list[dict[str, Any]] | None = None,
) -> list[str]:
    summary = summarize_activities(activities, planned_sessions)
    body = summarize_body_metrics(body_metrics or [])
    recs: list[str] = []
    next_session = summary.get("next_session")
    if next_session:
        recs.append(
            f"Next: {next_session['day_label']} {next_session['session_date']} - {next_session['label']}. "
            f"Target HR <150 unless tagged steady/race."
        )
    if summary["hot_easy_count"] >= 3:
        recs.append("Easy HR has been drifting hot. Slow easy runs, use 9:1 run-walk, and keep avg HR under 150.")
    if summary["current_week_run_km"] > 32 and summary["longest_recent"] < 16:
        recs.append("Weekly volume is okay, but recent long-run durability is still the limiter. Protect the Saturday long run.")
    if summary["current_week_strength"] < 2:
        recs.append("Strength target is not complete yet. Add the planned full-body session if legs feel normal.")
    if body:
        recs.append(
            f"Body target: latest {body['weight_kg']} kg, {body['body_fat_percent']}% fat, "
            f"fat mass {body['fat_mass_kg']} kg, BMR {body['bmr']} kcal. "
            f"Keep protein around {body['protein_floor']}-{body['protein_ceiling']} g/day."
        )
    recs.append("Use the calorie/protein target shown on each planned day. Keep deficits on rest/easy days only.")
    return recs


def compute_session_fuel(session: dict[str, Any], weight_kg: float, bmr: int) -> tuple[int, int]:
    """Return (calories, protein_g) scaled to current body metrics.

    Formula anchored to real TDEE components:
      neat  = BMR * 1.20  (baseline daily movement)
      run   = distance * 60 kcal/km (≤20 km) or 55 kcal/km (>20 km, efficiency gain)
      extras added per session type
    """
    stype = session["session_type"]
    distance = float(session.get("distance_km") or 0)
    has_strength = bool(session.get("has_strength"))
    has_leg_day = bool(session.get("has_leg_day"))

    neat = round(bmr * 1.20)
    rate = 55 if distance > 20 else 60
    run_kcal = round(distance * rate)

    if stype == "rest":
        cal = round(bmr * 1.25)
    elif stype == "recovery":
        cal = neat + run_kcal
    elif stype == "strength":
        cal = neat + 300 + run_kcal
    elif stype in ("easy", "quality"):
        cal = neat + run_kcal
        if has_strength:
            cal += 200
        if stype == "quality":
            cal += 100
    elif stype == "long":
        cal = neat + run_kcal
        if has_leg_day:
            cal += 300
    elif stype == "race":
        if distance >= 40:
            cal = round(bmr * 2.55)  # full marathon: carb-loaded race day
        else:
            cal = neat + run_kcal + 200  # race intensity overhead
    elif stype == "hike":
        cal = round(bmr * 2.10)
    else:
        cal = neat + run_kcal

    calories = max(1800, round(cal / 50) * 50)

    heavy = stype in ("long", "race", "hike") or has_leg_day or (has_strength and distance >= 7)
    protein = round(weight_kg * (1.8 if heavy else 1.65))
    protein = max(110, min(145, protein))

    return calories, protein


def build_chart_data(activities: list[dict[str, Any]], planned_sessions: list[dict[str, Any]]) -> dict[str, Any]:
    run_acts = [a for a in activities if "Running" in (a.get("activity_type") or "")]

    # ── Weekly volume: planned vs actual ─────────────────────────────────────
    planned_km_by_week: dict[int, float] = defaultdict(float)
    for s in planned_sessions:
        if s["session_type"] != "rest":
            planned_km_by_week[s["week_no"]] += s.get("distance_km") or 0

    plan_start = date.fromisoformat(planned_sessions[0]["session_date"]) if planned_sessions else date.min
    plan_end = date.fromisoformat(planned_sessions[-1]["session_date"]) if planned_sessions else date.max
    session_date_to_week = {s["session_date"]: s["week_no"] for s in planned_sessions}

    actual_km_by_week: dict[int, float] = defaultdict(float)
    for a in run_acts:
        act_date = datetime.fromisoformat(a["activity_date"]).date()
        if not (plan_start <= act_date <= plan_end):
            continue
        week_no = session_date_to_week.get(act_date.isoformat())
        if week_no is None:
            # find the week whose range contains this date
            for s in planned_sessions:
                if date.fromisoformat(s["session_date"]) >= act_date:
                    week_no = s["week_no"]
                    break
        if week_no is not None:
            actual_km_by_week[week_no] += a.get("distance") or 0

    weeks = list(range(1, 13))
    volume_labels = [f"W{w}" for w in weeks]
    volume_planned = [round(planned_km_by_week.get(w, 0), 1) for w in weeks]
    volume_actual = [round(actual_km_by_week.get(w, 0), 1) for w in weeks]

    # ── Long run progression ──────────────────────────────────────────────────
    planned_long_by_week: dict[int, float] = {}
    for s in planned_sessions:
        if s["session_type"] in ("long", "race") and (s.get("distance_km") or 0) >= 10:
            w = s["week_no"]
            planned_long_by_week[w] = max(planned_long_by_week.get(w, 0), s.get("distance_km") or 0)

    actual_long_by_week: dict[int, float] = defaultdict(float)
    for a in run_acts:
        dist = a.get("distance") or 0
        act_date = datetime.fromisoformat(a["activity_date"]).date()
        if not (plan_start <= act_date <= plan_end):
            continue
        week_no = session_date_to_week.get(act_date.isoformat())
        if week_no is not None:
            actual_long_by_week[week_no] = max(actual_long_by_week[week_no], dist)

    long_planned = [round(planned_long_by_week.get(w, 0), 1) for w in weeks]
    long_actual = [round(actual_long_by_week.get(w, 0), 1) for w in weeks]

    return {
        "volume_labels": volume_labels,
        "volume_planned": volume_planned,
        "volume_actual": volume_actual,
        "long_planned": long_planned,
        "long_actual": long_actual,
    }


def build_ai_prompt(
    profile: str,
    activities: list[dict[str, Any]],
    planned_sessions: list[dict[str, Any]],
    body_metrics: list[dict[str, Any]] | None = None,
) -> str:
    summary = summarize_activities(activities, planned_sessions)
    body = summarize_body_metrics(body_metrics or [])
    recs = deterministic_recommendations(activities, planned_sessions, body_metrics)
    latest = activities[:12]
    latest_lines = [
        f"- {a['activity_date']} {a['activity_type']} {a.get('distance') or 0} km, "
        f"time {a.get('duration') or '-'}, avg HR {a.get('avg_hr') or '-'}"
        for a in latest
    ]
    plan_lines = [
        f"- W{s['week_no']} {s['day_label']} {s['session_date']}: {s['label']} "
        f"({s.get('distance_km') or 0} km), fuel {s['planned_calories']} kcal/{s['planned_protein']}g protein"
        for s in planned_sessions
    ]
    return "\n".join([
        "You are advising Naufal on a marathon training plan. Recommend only; do not rewrite the plan.",
        "",
        "Profile and rules:",
        profile.strip(),
        "",
        "Current computed summary:",
        str(summary),
        "",
        "Latest body composition summary:",
        str(body),
        "",
        "Deterministic app recommendation:",
        *[f"- {r}" for r in recs],
        "",
        "Latest activities:",
        *latest_lines,
        "",
        "Current planned sessions:",
        *plan_lines,
        "",
        "Return: 1) today/tomorrow action, 2) recovery/fuel notes, 3) whether the next long run should stay, reduce, or shift.",
    ])
