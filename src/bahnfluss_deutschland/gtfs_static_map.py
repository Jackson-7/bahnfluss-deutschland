from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgba
from tqdm import tqdm


RAIL_ROUTE_TYPES = {"2", "100", "101", "102", "103", "105", "106", "107", "109"}


def parse_service_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def gtfs_date(value):
    return int(value.strftime("%Y%m%d"))


def active_service_ids(feed_dir, service_date):
    calendar_path = feed_dir / "calendar.txt"
    calendar_dates_path = feed_dir / "calendar_dates.txt"
    service_ids = set()
    yyyymmdd = gtfs_date(service_date)
    weekday = service_date.strftime("%A").lower()

    if calendar_path.exists():
        calendar = pd.read_csv(
            calendar_path,
            dtype={"service_id": "string"},
        )
        active_calendar = calendar[
            (calendar["start_date"] <= yyyymmdd)
            & (calendar["end_date"] >= yyyymmdd)
            & (calendar[weekday] == 1)
        ]
        service_ids.update(active_calendar["service_id"].dropna().astype(str))

    if calendar_dates_path.exists():
        calendar_dates = pd.read_csv(
            calendar_dates_path,
            dtype={"service_id": "string"},
        )
        service_date_rows = calendar_dates[calendar_dates["date"] == yyyymmdd]
        additions = service_date_rows[service_date_rows["exception_type"] == 1]
        removals = service_date_rows[service_date_rows["exception_type"] == 2]
        service_ids.update(additions["service_id"].dropna().astype(str))
        service_ids.difference_update(removals["service_id"].dropna().astype(str))

    return service_ids


def load_active_rail_stop_times(feed, service_date):
    feed_path = feed["path"]
    service_ids = active_service_ids(feed_path, service_date)

    routes = pd.read_csv(
        feed_path / "routes.txt",
        dtype={"route_id": "string", "route_type": "string", "route_short_name": "string"},
        usecols=lambda column: column
        in {"route_id", "route_type", "route_short_name", "route_long_name"},
    )
    routes = routes[routes["route_type"].isin(RAIL_ROUTE_TYPES)]

    trips = pd.read_csv(
        feed_path / "trips.txt",
        dtype={"route_id": "string", "service_id": "string", "trip_id": "string"},
    )
    trips = trips[trips["service_id"].isin(service_ids)]
    trips = trips.merge(routes[["route_id", "route_type"]], on="route_id", how="inner")

    stop_times = pd.read_csv(
        feed_path / "stop_times.txt",
        dtype={"trip_id": "string", "stop_id": "string"},
        usecols=["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
    )
    stop_times = stop_times.merge(trips[["trip_id", "route_id"]], on="trip_id", how="inner")

    stops = pd.read_csv(
        feed_path / "stops.txt",
        dtype={"stop_id": "string"},
        usecols=["stop_id", "stop_lat", "stop_lon"],
    )
    stop_times = stop_times.merge(stops, on="stop_id", how="inner")
    stop_times["stop_sequence"] = pd.to_numeric(stop_times["stop_sequence"], errors="coerce")
    stop_times = stop_times.dropna(subset=["stop_sequence", "stop_lat", "stop_lon"])
    stop_times = stop_times.sort_values(["trip_id", "stop_sequence"])
    stop_times["feed"] = feed["label"]
    stop_times["color"] = feed["color"]

    summary = {
        "label": feed["label"],
        "active_services": len(service_ids),
        "active_trips": trips["trip_id"].nunique(),
        "stop_times": len(stop_times),
        "segments": 0,
        "uses_shapes": (feed_path / "shapes.txt").exists(),
    }
    return stop_times, summary


def build_stop_to_stop_segments(stop_times):
    next_rows = stop_times.groupby("trip_id", sort=False)[["stop_lat", "stop_lon"]].shift(-1)
    segments = stop_times.assign(
        next_stop_lat=next_rows["stop_lat"],
        next_stop_lon=next_rows["stop_lon"],
    ).dropna(subset=["next_stop_lat", "next_stop_lon"])

    return segments[
        [
            "feed",
            "color",
            "trip_id",
            "route_id",
            "stop_lon",
            "stop_lat",
            "next_stop_lon",
            "next_stop_lat",
        ]
    ]


def render_static_map(segments, summaries, service_date, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    link_columns = ["feed", "color", "stop_lon", "stop_lat", "next_stop_lon", "next_stop_lat"]
    unique_links = segments.groupby(link_columns, as_index=False).size()

    fig, ax = plt.subplots(figsize=(10, 12), dpi=180)
    fig.subplots_adjust(bottom=0.09)
    ax.set_facecolor("#f7f7f4")
    fig.patch.set_facecolor("#f7f7f4")

    legend_handles = []
    for label, group in tqdm(unique_links.groupby("feed"), desc="Rendering feeds"):
        color = group["color"].iloc[0]
        lines = [
            ((row.stop_lon, row.stop_lat), (row.next_stop_lon, row.next_stop_lat))
            for row in group.itertuples(index=False)
        ]
        weights = group["size"].clip(upper=60)
        collection = LineCollection(
            lines,
            colors=[to_rgba(color, alpha=0.04 + min(weight / 60, 1) * 0.22) for weight in weights],
            linewidths=0.15 + (weights / 60) * 0.7,
            capstyle="round",
        )
        ax.add_collection(collection)
        legend_handles.append(plt.Line2D([0], [0], color=color, linewidth=2, label=label))

    ax.set_xlim(5.4, 15.3)
    ax.set_ylim(47.1, 55.2)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    summary_text = " | ".join(
        f"{summary['label']}: {summary['active_trips']:,} trips, {summary['segments']:,} segments"
        for summary in summaries
    )
    ax.set_title(
        f"Scheduled German Rail Activity - {service_date:%Y-%m-%d}",
        fontsize=16,
        fontweight="bold",
        pad=14,
    )
    ax.text(
        0.5,
        -0.055,
        "GTFS schedule data. Stop-to-stop fallback geometry because shapes.txt is missing.\n"
        f"{summary_text}",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=8,
        color="#424242",
    )
    ax.legend(handles=legend_handles, loc="upper left", frameon=False, fontsize=9)

    fig.savefig(output_path, bbox_inches="tight", pad_inches=0.26)
    plt.close(fig)


def create_static_rail_map(data_dir, service_date, output_path):
    feeds = [
        {
            "path": data_dir / "intercity_de-aug22_2026",
            "label": "intercity",
            "color": "#d73027",
        },
        {
            "path": data_dir / "regional_de-aug22_2026",
            "label": "regional",
            "color": "#1a9850",
        },
    ]

    all_segments = []
    summaries = []
    for feed in tqdm(feeds, desc="Processing GTFS feeds"):
        stop_times, summary = load_active_rail_stop_times(feed, service_date)
        segments = build_stop_to_stop_segments(stop_times)
        all_segments.append(segments)
        summary["segments"] = len(segments)
        summaries.append(summary)

    combined_segments = pd.concat(all_segments, ignore_index=True)
    render_static_map(combined_segments, summaries, service_date, output_path)
    return summaries
