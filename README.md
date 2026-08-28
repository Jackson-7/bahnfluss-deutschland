# Bahnfluss Deutschland

Scheduled German train movement analysis and visualisation from GTFS timetable feeds.

The project reads the local GTFS feed folders in `data/` and generates dark-theme rail maps, timestamp frames, a train-movement GIF, and activity statistics.

## Commands

Show all CLI options through the root wrapper.

```bash
uv run python main.py --help
```

Show all CLI options through the package command.

```bash
uv run bahnfluss-deutschland --help
```

Generate every currently supported output.

```bash
uv run python main.py
```

Generate only the static active rail map.

```bash
uv run python main.py --date 2026-08-22
```

Generate one timestamp frame.

```bash
uv run python main.py --time 07:12
```

Generate one after-midnight GTFS service-day timestamp frame.

```bash
uv run python main.py --time 25:10:00
```

Generate the train-movement GIF.

```bash
uv run python main.py --animate
```

Generate a faster, smaller GIF preview.

```bash
uv run python main.py --animate --step-minutes 30 --fps 8 --trail-frames 6
```

Generate a custom time interval GIF.

```bash
uv run python main.py --animate --start-time 06:00 --end-time 10:00 --step-minutes 5
```

Generate the activity CSV and activity plot.

```bash
uv run python main.py --stats
```

Generate stats with customised name and paths.

```bash
uv run python main.py --stats --output outputs/activity.csv --plot-output outputs/activity.png
```

# Outputs

With the default date `2026-08-22`, the full run writes:

```text
outputs/active_rail_map_2026-08-22.png
outputs/train_positions_2026-08-22_07-12.png
outputs/train_animation_2026-08-22.gif
outputs/train_activity_stats_2026-08-22.csv
outputs/train_activity_plot_2026-08-22.png
```

The GIF uses fading trails behind trains. The current local environment supports GIF output through Pillow; MP4 export should be added after FFmpeg is available.
Map-style outputs include a faint Germany outline from [Natural Earth 1:10m Admin 0 Countries](https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-0-countries/) as a visual reference layer.

## Arguments

| Argument                    | Use case                                                                                                                                 | Default                                  |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| `--data-dir DATA_DIR`     | Point to a different folder containing GTFS feed folders.                                                                                | `data/`                                |
| `--date YYYY-MM-DD`       | Select the GTFS service date.                                                                                                            | `2026-08-22`                           |
| `--output PATH`           | Set the main output path for the selected mode. For static/time/animation this is the image or GIF path; for stats this is the CSV path. | Mode-specific                            |
| `--all`                   | Generate static map, timestamp frame, GIF, stats CSV, and stats plot.`uv run python main.py` does this when no args are passed.        | Off                                      |
| `--time HH:MM[:SS]`       | Generate one timestamp frame. GTFS service-day times above 24 hours are supported, such as`25:10:00`.                                  | Off                                      |
| `--animate`               | Generate the train-movement GIF.                                                                                                         | Off                                      |
| `--stats`                 | Generate active-train counts as CSV plus an activity plot.                                                                               | Off                                      |
| `--plot-output PATH`      | Set the activity plot PNG path when using`--stats`.                                                                                    | `outputs/train_activity_plot_DATE.png` |
| `--start-time HH:MM[:SS]` | Start time for animation or stats.                                                                                                       | `00:00`                                |
| `--end-time HH:MM[:SS]`   | End time for animation or stats.                                                                                                         | `24:00`                                |
| `--step-minutes N`        | Time interval between animation frames or stats samples. Smaller values are smoother/finer but slower and larger.                        | Animation:`10`; stats: `1`           |
| `--fps N`                 | GIF playback speed.                                                                                                                      | `12`                                   |
| `--trail-frames N`        | Number of previous animation frames shown as fading train trails. Higher values create longer trails and denser GIFs.                    | `8`                                    |

## Time Format

GTFS service-day time can go beyond normal 24-hour clock time. For service date `2026-08-22`:

```text
01:10:00 = 2026-08-22 01:10
25:10:00 = 2026-08-23 01:10, still part of the 2026-08-22 GTFS service day
```

This matters for night trains and services continuing after midnight.

## Rail Categories

The local GTFS feeds use `route_type=2` for rail services, so the five-way category split is inferred from `route_short_name` prefixes and the source feed:

| Category         | Examples                                                      |
| ---------------- | ------------------------------------------------------------- |
| `regional`     | RB, RE, REX, MEX, and uncategorized regional-feed rail routes |
| `s_bahn_local` | S, RS, RT, U, A, L, and similar local systems                 |
| `intercity`    | IC, EC, FLX, and related long-distance prefixes               |
| `high_speed`   | ICE, ECE, RJ/RJX, TGV, THA                                    |
| `night_train`  | EN, NJ, and GTFS sleeper rail route types when present        |

The rules live in `src/bahnfluss_deutschland/gtfs_categories.py` and can be refined as more GTFS feeds are added.

## Data Sources and Notes

The GTFS feeds were downloaded from the [gtfs.de feed catalogue](https://gtfs.de/en/feeds/).
This project currently uses only:

- `Long Distance Rail Germany`
- `Regional Rail Germany`

The current local feeds include:

```text
calendar.txt
calendar_dates.txt
routes.txt
trips.txt
stop_times.txt
stops.txt
```

They do not include `shapes.txt`, so map geometry and animation movement use stop-to-stop interpolation. Shape-based interpolation should be added when a GTFS feed with `shapes.txt` is available.
The Germany outline in the background comes from [Natural Earth 1:10m Admin 0 Countries](https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-0-countries/), filtered to `ISO_A3=DEU`; it is not used for routing or measurement.
