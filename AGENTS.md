# Marathon Training Dashboard — Dev Context

## Project

Local FastAPI + SQLite dashboard for tracking marathon training.
Goal race: **Maybank Virgin Marathon · 23 Aug 2026 · 42.2 km**

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI (Python), Jinja2 templates |
| Database | SQLite via `training.db` |
| Styles | `/static/style.css` — light mode, Strava-inspired, Inter + Barlow Condensed |
| Server | `uvicorn app:app --reload` |
| Venv | `.venv/` |

## File Map

```
app.py               # Routes, CSV parsing, template context
db.py                # SQLite read/write helpers
training_logic.py    # Summaries, readiness scores, AI prompt builder
training.db          # SQLite source of truth
static/style.css     # All styles — single file, no build step
templates/
  base.html          # Layout, sticky nav
  dashboard.html     # Main dashboard (KPIs, schedule, readiness)
  activity_form.html # Log activity + Garmin CSV import
  body_form.html     # Log weight/fat/BMR
  ai.html            # AI prompt generator + paste-back
```

## Data Model (SQLite tables)

- `activities` — runs, strength, hikes logged by user
- `planned_sessions` — 12-week schedule seeded at startup
- `body_metrics` — weight, body_fat_percent, BMR over time
- `ai_recommendations` — prompt + response pairs

## Key Behaviors

- Dashboard recalculates on every page load (no caching layer)
- `training_logic.py` computes readiness, recommendations, and AI prompt deterministically from DB state
- Garmin CSV import: paste header + one row → parse → prefill form or direct import
- Planned sessions have `session_type`, `distance_km`, `planned_calories`, `planned_protein`, `has_strength`, `has_leg_day`
- Body metrics drive protein/calorie targets shown on each session card

## Schedule CLI (`manage.py`)

Works with Claude Code, Codex CLI, or any shell. Always use `.venv/bin/python3`.

```bash
# Read
python manage.py weeks                              # all weeks + volume summary
python manage.py sessions --week 3                  # all sessions in week 3
python manage.py show --date 2026-06-15             # one session detail
python manage.py activities --limit 10              # recent logged activities
python manage.py body                               # body metric history
python manage.py schema                             # DB schema + row counts

# Edit
python manage.py update --date 2026-06-15 \
  --label "Long easy" --distance 18 \
  --calories 2800 --protein 135 \
  --description "Z2 run-walk" --tags "long,easy" \
  --strength false --legday true

python manage.py set-type --date 2026-06-15 \
  --type long                                       # rest|easy|quality|long|race|hike|strength|recovery

python manage.py swap --date1 2026-06-10 \
  --date2 2026-06-11                                # swap full session content between two dates

python manage.py add --date 2026-06-30 \
  --type easy --label "Easy 8k" \
  --distance 8 --calories 2200 --protein 130

python manage.py delete --date 2026-06-30           # prompts confirmation
```

**Rules to respect when editing:**
- Strength sessions must be ≥48h apart (Tue + Thu pattern)
- Long run always Saturday, rest on Friday before it
- Taper weeks (W11–W12): cut strength load, no new hard sessions
- `has_leg_day=true` only on non-race/non-hike Saturdays after long run

## Design Conventions

- Light mode only — `#f4f4f4` page bg, white cards
- Primary accent: Strava orange `#fc4c02`
- No gradients, no colored border accents on cards
- Pill-shaped buttons (`border-radius: 999px`)
- Barlow Condensed for numbers/headings, Inter for body text
- Responsive: 7-col week grid → 4-col → 2-col on mobile
