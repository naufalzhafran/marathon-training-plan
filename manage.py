#!/usr/bin/env python3
"""
Training schedule CLI — for Claude Code / Codex CLI use.

Usage examples:
  python manage.py weeks
  python manage.py sessions --week 3
  python manage.py show --date 2026-06-15
  python manage.py update --date 2026-06-15 --distance 18 --label "Long easy" --calories 2800 --protein 135
  python manage.py set-type --date 2026-06-15 --type long
  python manage.py swap --date1 2026-06-10 --date2 2026-06-11
  python manage.py add --date 2026-06-30 --type easy --label "Easy 8k" --distance 8 --calories 2200 --protein 130
  python manage.py delete --date 2026-06-30
  python manage.py activities --limit 10
  python manage.py body
  python manage.py schema
"""

import argparse
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).parent / "training.db"

VALID_TYPES = {"rest", "easy", "quality", "long", "race", "hike", "strength", "recovery"}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def fmt_row(r: sqlite3.Row) -> str:
    d = dict(r)
    parts = [
        f"{d['session_date']}  [{d['session_type']:10}]  {d['label']:20}",
        f"  dist={d['distance_km'] or '-':>5}km  cal={d['planned_calories']}  prot={d['planned_protein']}g",
        f"  strength={'Y' if d['has_strength'] else 'N'}  legday={'Y' if d['has_leg_day'] else 'N'}  tags={d['tags']}",
    ]
    if d.get("description"):
        parts.append(f"  desc: {d['description']}")
    return "\n".join(parts)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_weeks(args: argparse.Namespace) -> None:
    with connect() as conn:
        rows = conn.execute(
            "SELECT week_no, MIN(session_date) start, MAX(session_date) end, "
            "COUNT(*) sessions, ROUND(SUM(CASE WHEN session_type != 'rest' THEN distance_km ELSE 0 END),1) total_km "
            "FROM planned_sessions GROUP BY week_no ORDER BY week_no"
        ).fetchall()
    print(f"{'Wk':>3}  {'Start':>12}  {'End':>12}  {'Sessions':>8}  {'~km':>6}")
    print("-" * 52)
    for r in rows:
        print(f"{r['week_no']:>3}  {r['start']:>12}  {r['end']:>12}  {r['sessions']:>8}  {r['total_km']:>6}")


def cmd_sessions(args: argparse.Namespace) -> None:
    with connect() as conn:
        if args.week:
            rows = conn.execute(
                "SELECT * FROM planned_sessions WHERE week_no=? ORDER BY sort_order", (args.week,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM planned_sessions ORDER BY session_date"
            ).fetchall()
    if not rows:
        print("No sessions found.")
        return
    for r in rows:
        print(fmt_row(r))
        print()


def cmd_show(args: argparse.Namespace) -> None:
    with connect() as conn:
        r = conn.execute(
            "SELECT * FROM planned_sessions WHERE session_date=?", (args.date,)
        ).fetchone()
    if not r:
        die(f"No session on {args.date}")
    print(fmt_row(r))


def cmd_update(args: argparse.Namespace) -> None:
    with connect() as conn:
        r = conn.execute(
            "SELECT * FROM planned_sessions WHERE session_date=?", (args.date,)
        ).fetchone()
        if not r:
            die(f"No session on {args.date}")

        fields: dict = {}
        if args.label is not None:
            fields["label"] = args.label
        if args.distance is not None:
            fields["distance_km"] = args.distance
        if args.calories is not None:
            fields["planned_calories"] = args.calories
        if args.protein is not None:
            fields["planned_protein"] = args.protein
        if args.description is not None:
            fields["description"] = args.description
        if args.tags is not None:
            fields["tags"] = args.tags
        if args.strength is not None:
            fields["has_strength"] = 1 if args.strength else 0
        if args.legday is not None:
            fields["has_leg_day"] = 1 if args.legday else 0

        if not fields:
            die("Nothing to update — pass at least one field flag.")

        set_clause = ", ".join(f"{k}=?" for k in fields)
        conn.execute(
            f"UPDATE planned_sessions SET {set_clause} WHERE session_date=?",
            (*fields.values(), args.date),
        )
        conn.commit()
    print(f"Updated {args.date}: {list(fields.keys())}")


def cmd_set_type(args: argparse.Namespace) -> None:
    if args.type not in VALID_TYPES:
        die(f"Invalid type '{args.type}'. Valid: {', '.join(sorted(VALID_TYPES))}")
    with connect() as conn:
        r = conn.execute(
            "SELECT id FROM planned_sessions WHERE session_date=?", (args.date,)
        ).fetchone()
        if not r:
            die(f"No session on {args.date}")
        conn.execute(
            "UPDATE planned_sessions SET session_type=? WHERE session_date=?",
            (args.type, args.date),
        )
        conn.commit()
    print(f"Set {args.date} session_type → {args.type}")


def cmd_swap(args: argparse.Namespace) -> None:
    with connect() as conn:
        a = conn.execute(
            "SELECT * FROM planned_sessions WHERE session_date=?", (args.date1,)
        ).fetchone()
        b = conn.execute(
            "SELECT * FROM planned_sessions WHERE session_date=?", (args.date2,)
        ).fetchone()
        if not a:
            die(f"No session on {args.date1}")
        if not b:
            die(f"No session on {args.date2}")

        swap_cols = ["label", "session_type", "distance_km", "planned_calories",
                     "planned_protein", "description", "tags", "has_strength", "has_leg_day"]

        conn.execute(
            f"UPDATE planned_sessions SET {','.join(f'{c}=?' for c in swap_cols)} WHERE session_date=?",
            (*[b[c] for c in swap_cols], args.date1),
        )
        conn.execute(
            f"UPDATE planned_sessions SET {','.join(f'{c}=?' for c in swap_cols)} WHERE session_date=?",
            (*[a[c] for c in swap_cols], args.date2),
        )
        conn.commit()
    print(f"Swapped session content: {args.date1} ↔ {args.date2}")


def cmd_add(args: argparse.Namespace) -> None:
    if args.type not in VALID_TYPES:
        die(f"Invalid type '{args.type}'. Valid: {', '.join(sorted(VALID_TYPES))}")
    with connect() as conn:
        exists = conn.execute(
            "SELECT id FROM planned_sessions WHERE session_date=?", (args.date,)
        ).fetchone()
        if exists:
            die(f"Session already exists on {args.date}. Use 'update' instead.")

        week = conn.execute(
            "SELECT week_no FROM planned_sessions WHERE session_date <= ? ORDER BY session_date DESC LIMIT 1",
            (args.date,),
        ).fetchone()
        week_no = week["week_no"] if week else 99

        from datetime import datetime
        day_label = datetime.strptime(args.date, "%Y-%m-%d").strftime("%a - %b %-d")

        conn.execute(
            "INSERT INTO planned_sessions "
            "(week_no, session_date, day_label, label, session_type, distance_km, "
            "planned_calories, planned_protein, description, tags, has_strength, has_leg_day, sort_order) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?, (SELECT COALESCE(MAX(sort_order),0)+1 FROM planned_sessions))",
            (
                week_no, args.date, day_label,
                args.label or args.type.title(),
                args.type,
                args.distance or 0,
                args.calories or 2000,
                args.protein or 130,
                args.description or "",
                args.tags or args.type,
                1 if args.strength else 0,
                1 if args.legday else 0,
            ),
        )
        conn.commit()
    print(f"Added session on {args.date} ({args.type})")


def cmd_delete(args: argparse.Namespace) -> None:
    with connect() as conn:
        r = conn.execute(
            "SELECT * FROM planned_sessions WHERE session_date=?", (args.date,)
        ).fetchone()
        if not r:
            die(f"No session on {args.date}")
        print(f"Deleting: {fmt_row(r)}")
        confirm = input("Confirm delete? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return
        conn.execute("DELETE FROM planned_sessions WHERE session_date=?", (args.date,))
        conn.commit()
    print(f"Deleted session on {args.date}")


def cmd_activities(args: argparse.Namespace) -> None:
    limit = args.limit or 20
    with connect() as conn:
        rows = conn.execute(
            "SELECT activity_date, activity_type, distance, avg_hr, calories, duration, title "
            "FROM activities ORDER BY activity_date DESC LIMIT ?", (limit,)
        ).fetchall()
    if not rows:
        print("No activities logged.")
        return
    print(f"{'Date':>22}  {'Type':>18}  {'km':>6}  {'HR':>5}  {'kcal':>6}  Title")
    print("-" * 80)
    for r in rows:
        print(
            f"{r['activity_date']:>22}  {r['activity_type']:>18}  "
            f"{r['distance'] or 0:>6.1f}  {r['avg_hr'] or '-':>5}  "
            f"{r['calories'] or '-':>6}  {r['title'] or ''}"
        )


def cmd_body(args: argparse.Namespace) -> None:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM body_metrics ORDER BY measured_at DESC LIMIT 10"
        ).fetchall()
    if not rows:
        print("No body metrics logged.")
        return
    print(f"{'Date':>12}  {'Weight':>8}  {'Fat%':>6}  {'BMR':>6}")
    print("-" * 40)
    for r in rows:
        print(
            f"{r['measured_at']:>12}  {r['weight_kg']:>7}kg  "
            f"{r['body_fat_percent'] or '-':>5}%  {r['bmr'] or '-':>6}"
        )


def cmd_schema(args: argparse.Namespace) -> None:
    with connect() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        for t in tables:
            name = t["name"]
            cols = conn.execute(f"PRAGMA table_info({name})").fetchall()
            count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            print(f"\n{name} ({count} rows)")
            for c in cols:
                pk = " PK" if c["pk"] else ""
                nn = " NOT NULL" if c["notnull"] else ""
                print(f"  {c['name']:30} {c['type']:10}{pk}{nn}")


# ── Arg parser ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Marathon training schedule CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("weeks", help="List all weeks with volume summary")

    p = sub.add_parser("sessions", help="List sessions (all or by week)")
    p.add_argument("--week", type=int, help="Filter by week number")

    p = sub.add_parser("show", help="Show one session by date")
    p.add_argument("--date", required=True, help="YYYY-MM-DD")

    p = sub.add_parser("update", help="Update fields on a session")
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--label")
    p.add_argument("--distance", type=float)
    p.add_argument("--calories", type=int)
    p.add_argument("--protein", type=int)
    p.add_argument("--description")
    p.add_argument("--tags")
    p.add_argument("--strength", type=lambda x: x.lower() in ("1","true","yes"), metavar="true/false")
    p.add_argument("--legday", type=lambda x: x.lower() in ("1","true","yes"), metavar="true/false")

    p = sub.add_parser("set-type", help="Change session_type")
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--type", required=True, choices=sorted(VALID_TYPES))

    p = sub.add_parser("swap", help="Swap session content between two dates")
    p.add_argument("--date1", required=True, help="YYYY-MM-DD")
    p.add_argument("--date2", required=True, help="YYYY-MM-DD")

    p = sub.add_parser("add", help="Add a new session")
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--type", required=True, choices=sorted(VALID_TYPES))
    p.add_argument("--label")
    p.add_argument("--distance", type=float)
    p.add_argument("--calories", type=int)
    p.add_argument("--protein", type=int)
    p.add_argument("--description")
    p.add_argument("--tags")
    p.add_argument("--strength", action="store_true")
    p.add_argument("--legday", action="store_true")

    p = sub.add_parser("delete", help="Delete a session (interactive confirm)")
    p.add_argument("--date", required=True, help="YYYY-MM-DD")

    p = sub.add_parser("activities", help="List recent logged activities")
    p.add_argument("--limit", type=int, default=20)

    sub.add_parser("body", help="List body metric history")
    sub.add_parser("schema", help="Print DB schema with row counts")

    args = parser.parse_args()

    dispatch = {
        "weeks": cmd_weeks,
        "sessions": cmd_sessions,
        "show": cmd_show,
        "update": cmd_update,
        "set-type": cmd_set_type,
        "swap": cmd_swap,
        "add": cmd_add,
        "delete": cmd_delete,
        "activities": cmd_activities,
        "body": cmd_body,
        "schema": cmd_schema,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
