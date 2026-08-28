# Bahnfluss Deutschland

Scheduled German train movement analysis and visualization from GTFS timetable feeds.

## Milestone 1: Static Active Rail Map

Generate a static map of rail services active on a chosen GTFS service date:

```bash
uv run bahnfluss-deutschland --date 2026-08-22
```

You can also run the root wrapper directly:

```bash
uv run python main.py --date 2026-08-22
```

The first version uses the available DELFI/GTFS tables:

- `calendar.txt`
- `calendar_dates.txt`
- `routes.txt`
- `trips.txt`
- `stop_times.txt`
- `stops.txt`

The current local feeds do not include `shapes.txt`, so this milestone renders fallback stop-to-stop geometry. That is enough to validate service-date filtering and activity coverage before building timestamp frames and animation.
