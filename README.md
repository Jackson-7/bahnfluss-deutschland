# Bahnfluss Deutschland

Scheduled German train movement analysis and visualization from GTFS timetable feeds.

## Current Status

Done:

- Service-date filtering from `calendar.txt` and `calendar_dates.txt`
- Rail-only trip filtering
- Static active rail map for a GTFS service date
- One timestamp frame showing active train movements at a chosen service-day time
- A first compressed GIF animation path for the service day
- Activity statistics CSV and plot

Still pending:

- MP4 rendering, once FFmpeg is available
- Shape-based interpolation, once a feed with `shapes.txt` is available

## Generate Everything

Run the root wrapper without flags to generate every output currently supported:

```bash
uv run python main.py
```

If you prefer running `main.py` directly from your editor, edit `RUN_ARGS` near
the top of `main.py`:

```python
RUN_ARGS = ["--date", "2026-08-22", "--animate", "--step-minutes", "30", "--fps", "8"]
```

Set it back to `None` when you want normal terminal arguments again.

This writes:

```text
outputs/active_rail_map_YYYY-MM-DD.png
outputs/train_positions_YYYY-MM-DD_07-12.png
outputs/train_animation_YYYY-MM-DD.gif
outputs/train_activity_stats_YYYY-MM-DD.csv
outputs/train_activity_plot_YYYY-MM-DD.png
```

You can still run individual outputs with the flags below.

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

## Rail Categories

The local GTFS feeds use `route_type=2` for rail services, so the five-way category split is inferred from `route_short_name` prefixes plus the source feed:

- `regional`: default regional rail services such as RB, RE, REX, MEX, and uncategorized regional-feed rail routes
- `s_bahn_local`: S-Bahn and local rail prefixes such as S, RS, RT, U, A, L, and similar local systems
- `intercity`: IC, EC, FLX, and related long-distance prefixes
- `high_speed`: ICE, ECE, RJ/RJX, TGV, THA, and GTFS extended high-speed rail route types when present
- `night_train`: EN, NJ, and GTFS extended sleeper rail route types when present

These rules live in `src/bahnfluss_deutschland/gtfs_categories.py` so they can be refined as more GTFS feeds are added.

## Milestone 2: Timestamp Frame

Render active train positions for a service-day timestamp:

```bash
uv run bahnfluss-deutschland --date 2026-08-22 --time 07:12
```

GTFS service-day times above 24 hours are supported:

```bash
uv run bahnfluss-deutschland --date 2026-08-22 --time 25:10:00
```

The frame output is written to:

```text
outputs/train_positions_YYYY-MM-DD_HH-MM-or-HH-MM-SS.png
```

## Milestone 3: Animation Preview

Render a compressed service-day GIF:

```bash
uv run bahnfluss-deutschland --date 2026-08-22 --animate
```

Useful preview settings:

```bash
uv run bahnfluss-deutschland --date 2026-08-22 --animate --step-minutes 30 --fps 8
```

Add longer or shorter fading motion trails:

```bash
uv run bahnfluss-deutschland --date 2026-08-22 --animate --trail-frames 9
```

The default animation uses 10-minute frame steps and 8 fading trail frames. For a smaller preview GIF, use a coarser step:

```bash
uv run bahnfluss-deutschland --date 2026-08-22 --animate --step-minutes 30
```

The local environment currently supports GIF output through Pillow. MP4 output should be added after FFmpeg is available.

## Milestone 4: Activity Statistics

Generate per-minute active train counts and a plot:

```bash
uv run bahnfluss-deutschland --date 2026-08-22 --stats
```

Outputs:

```text
outputs/train_activity_stats_YYYY-MM-DD.csv
outputs/train_activity_plot_YYYY-MM-DD.png
```

Use a coarser interval for quick experiments:

```bash
uv run bahnfluss-deutschland --date 2026-08-22 --stats --step-minutes 5
```
