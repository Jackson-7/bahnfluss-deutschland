import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgba
from tqdm import tqdm

from bahnfluss_deutschland.gtfs_basemap import add_germany_map_background
from bahnfluss_deutschland.gtfs_categories import (
    CATEGORY_COLORS,
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    classify_route,
)
from bahnfluss_deutschland.gtfs_static_map import (
    RAIL_ROUTE_TYPES,
    active_service_ids,
    build_stop_to_stop_segments,
)
from bahnfluss_deutschland.gtfs_theme import (
    ANIMATION_NETWORK_LINE_ALPHA,
    BACKGROUND,
    FOREGROUND,
    MUTED,
    NETWORK_LINE_ALPHA,
    POINT_ALPHA,
    TRAIL_ALPHA_MAX,
    TRAIL_ALPHA_MIN,
    TRAIL_FRAMES,
)


def parse_gtfs_time(value):
    parts = str(value).split(":")
    if len(parts) != 3:
        raise ValueError(f"Expected GTFS time HH:MM:SS, got {value!r}")
    hours, minutes, seconds = (int(part) for part in parts)
    return hours * 3600 + minutes * 60 + seconds


def parse_frame_time(value):
    parts = str(value).split(":")
    if len(parts) == 2:
        hours, minutes = (int(part) for part in parts)
        seconds = 0
    elif len(parts) == 3:
        hours, minutes, seconds = (int(part) for part in parts)
    else:
        raise ValueError(f"Expected frame time HH:MM or HH:MM:SS, got {value!r}")

    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"Invalid frame time {value!r}")
    return hours * 3600 + minutes * 60 + seconds


def format_service_time(seconds):
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def default_feeds(data_dir):
    return [
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


def _load_active_trip_stop_times(feed, service_date):
    feed_path = feed["path"]
    service_ids = active_service_ids(feed_path, service_date)

    routes = pd.read_csv(
        feed_path / "routes.txt",
        dtype={"route_id": "string", "route_type": "string", "route_short_name": "string"},
        usecols=lambda column: column
        in {"route_id", "route_type", "route_short_name", "route_long_name"},
    )
    routes = routes[routes["route_type"].isin(RAIL_ROUTE_TYPES)]
    routes["category"] = routes.apply(
        lambda row: classify_route(
            row.get("route_short_name"),
            route_type=row.get("route_type"),
            feed_label=feed["label"],
        ),
        axis=1,
    )
    routes["color"] = routes["category"].map(CATEGORY_COLORS)

    trips = pd.read_csv(
        feed_path / "trips.txt",
        dtype={"route_id": "string", "service_id": "string", "trip_id": "string"},
    )
    trips = trips[trips["service_id"].isin(service_ids)]
    trips = trips.merge(routes, on="route_id", how="inner")

    stop_times = pd.read_csv(
        feed_path / "stop_times.txt",
        dtype={"trip_id": "string", "stop_id": "string"},
        usecols=["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
    )
    stop_times = stop_times.merge(
        trips[["trip_id", "route_id", "route_type", "route_short_name", "category", "color"]],
        on="trip_id",
        how="inner",
    )

    stops = pd.read_csv(
        feed_path / "stops.txt",
        dtype={"stop_id": "string"},
        usecols=["stop_id", "stop_name", "stop_lat", "stop_lon"],
    )
    stop_times = stop_times.merge(stops, on="stop_id", how="inner")
    stop_times["stop_sequence"] = pd.to_numeric(stop_times["stop_sequence"], errors="coerce")
    stop_times = stop_times.dropna(subset=["stop_sequence", "stop_lat", "stop_lon"])
    stop_times = stop_times.sort_values(["trip_id", "stop_sequence"])
    stop_times["arrival_seconds"] = stop_times["arrival_time"].map(parse_gtfs_time)
    stop_times["departure_seconds"] = stop_times["departure_time"].map(parse_gtfs_time)
    stop_times["feed"] = feed["label"]
    return stop_times


def load_interpolation_data(data_dir, service_date):
    movement_segments = []
    background_segments = []

    for feed in tqdm(default_feeds(data_dir), desc="Preparing active trips"):
        stop_times = _load_active_trip_stop_times(feed, service_date)
        background_segments.append(build_stop_to_stop_segments(stop_times))
        next_rows = stop_times.groupby("trip_id", sort=False)[
            [
                "arrival_seconds",
                "departure_seconds",
                "stop_lat",
                "stop_lon",
                "stop_id",
                "stop_name",
            ]
        ].shift(-1)

        segments = stop_times.assign(
            next_arrival_seconds=next_rows["arrival_seconds"],
            next_departure_seconds=next_rows["departure_seconds"],
            next_stop_lat=next_rows["stop_lat"],
            next_stop_lon=next_rows["stop_lon"],
            next_stop_id=next_rows["stop_id"],
            next_stop_name=next_rows["stop_name"],
        ).dropna(
            subset=[
                "departure_seconds",
                "next_arrival_seconds",
                "next_stop_lat",
                "next_stop_lon",
            ]
        )

        movement_segments.append(
            segments[
                [
                    "feed",
                    "category",
                    "color",
                    "trip_id",
                    "route_id",
                    "route_type",
                    "route_short_name",
                    "departure_seconds",
                    "next_arrival_seconds",
                    "stop_lon",
                    "stop_lat",
                    "next_stop_lon",
                    "next_stop_lat",
                    "stop_id",
                    "stop_name",
                    "next_stop_id",
                    "next_stop_name",
                ]
            ]
        )

    movements = (
        pd.concat(movement_segments, ignore_index=True)
        if movement_segments
        else pd.DataFrame(columns=["feed", "category", "color", "lon", "lat"])
    )
    segments = pd.concat(background_segments, ignore_index=True)
    return movements, segments


def positions_at_time(movement_segments, frame_seconds):
    moving = movement_segments[
        (movement_segments["departure_seconds"] <= frame_seconds)
        & (movement_segments["next_arrival_seconds"] >= frame_seconds)
        & (
            movement_segments["next_arrival_seconds"]
            > movement_segments["departure_seconds"]
        )
    ].copy()
    if moving.empty:
        return pd.DataFrame(columns=["feed", "category", "color", "lon", "lat"])

    duration = moving["next_arrival_seconds"] - moving["departure_seconds"]
    progress = (frame_seconds - moving["departure_seconds"]) / duration
    moving["lon"] = moving["stop_lon"] + (
        moving["next_stop_lon"] - moving["stop_lon"]
    ) * progress
    moving["lat"] = moving["stop_lat"] + (
        moving["next_stop_lat"] - moving["stop_lat"]
    ) * progress
    return moving


def load_frame_positions(data_dir, service_date, frame_seconds):
    movement_segments, background_segments = load_interpolation_data(
        data_dir, service_date
    )
    return positions_at_time(movement_segments, frame_seconds), background_segments


def style_germany_axis(ax):
    ax.set_xlim(5.4, 15.3)
    ax.set_ylim(47.1, 55.2)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def add_network_background(ax, segments, alpha=NETWORK_LINE_ALPHA):
    link_columns = [
        "category",
        "color",
        "stop_lon",
        "stop_lat",
        "next_stop_lon",
        "next_stop_lat",
    ]
    unique_links = segments.groupby(link_columns, as_index=False).size()

    category_groups = dict(tuple(unique_links.groupby("category")))
    for category in tqdm(CATEGORY_ORDER, desc="Rendering network"):
        if category not in category_groups:
            continue
        group = category_groups[category]
        color = group["color"].iloc[0]
        lines = [
            ((row.stop_lon, row.stop_lat), (row.next_stop_lon, row.next_stop_lat))
            for row in group.itertuples(index=False)
        ]
        collection = LineCollection(
            lines,
            colors=[to_rgba(color, alpha=alpha)] * len(group),
            linewidths=0.18,
            capstyle="round",
        )
        ax.add_collection(collection)


def render_timestamp_frame(positions, segments, service_date, frame_seconds, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 12), dpi=180)
    fig.subplots_adjust(bottom=0.09)
    ax.set_facecolor(BACKGROUND)
    fig.patch.set_facecolor(BACKGROUND)
    add_germany_map_background(ax)
    add_network_background(ax, segments)

    legend_handles = []
    position_groups = dict(tuple(positions.groupby("category")))
    for category in CATEGORY_ORDER:
        if category not in position_groups:
            continue
        group = position_groups[category]
        color = group["color"].iloc[0]
        ax.scatter(
            group["lon"],
            group["lat"],
            s=8 if category in {"regional", "s_bahn_local"} else 13,
            c=color,
            alpha=POINT_ALPHA,
            linewidths=0,
            label=CATEGORY_LABELS[category],
        )
        legend_handles.append(
            plt.Line2D(
                [0],
                [0],
                marker="o",
                linestyle="",
                color=color,
                label=f"{CATEGORY_LABELS[category]}: {len(group):,}",
                markersize=5,
            )
        )

    style_germany_axis(ax)

    ax.set_title(
        f"Scheduled German Train Positions - {service_date:%Y-%m-%d} {format_service_time(frame_seconds)}",
        fontsize=15,
        fontweight="bold",
        pad=14,
        color=FOREGROUND,
    )
    ax.text(
        0.5,
        -0.055,
        "GTFS schedule data. Train positions use stop-to-stop interpolation because shapes.txt is missing.\n"
        f"{len(positions):,} active train movements in frame.",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=8,
        color=MUTED,
    )
    if legend_handles:
        legend = ax.legend(handles=legend_handles, loc="upper left", frameon=False, fontsize=9)
        for text in legend.get_texts():
            text.set_color(FOREGROUND)

    fig.savefig(output_path, bbox_inches="tight", pad_inches=0.26, facecolor=fig.get_facecolor())
    plt.close(fig)


def create_timestamp_frame(data_dir, service_date, frame_time, output_path):
    frame_seconds = parse_frame_time(frame_time)
    positions, segments = load_frame_positions(data_dir, service_date, frame_seconds)
    render_timestamp_frame(positions, segments, service_date, frame_seconds, output_path)
    return positions


def create_animation(
    data_dir,
    service_date,
    output_path,
    start_time="00:00",
    end_time="24:00",
    step_minutes=10,
    fps=12,
    trail_frames=None,
):
    start_seconds = parse_frame_time(start_time)
    end_seconds = parse_frame_time(end_time)
    if end_seconds <= start_seconds:
        raise ValueError("Animation end time must be after start time")
    if step_minutes <= 0:
        raise ValueError("Animation step minutes must be positive")
    trail_frames = trail_frames or TRAIL_FRAMES
    if trail_frames <= 0:
        raise ValueError("Animation trail frames must be positive")

    frame_seconds = list(range(start_seconds, end_seconds + 1, step_minutes * 60))
    movement_segments, background_segments = load_interpolation_data(
        data_dir, service_date
    )
    sampled_positions = [
        positions_at_time(movement_segments, frame_second)
        for frame_second in tqdm(frame_seconds, desc="Sampling animation frames")
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 12), dpi=120)
    fig.subplots_adjust(bottom=0.09)
    ax.set_facecolor(BACKGROUND)
    fig.patch.set_facecolor(BACKGROUND)
    add_germany_map_background(ax)
    add_network_background(ax, background_segments, alpha=ANIMATION_NETWORK_LINE_ALPHA)
    style_germany_axis(ax)

    trail_alphas = [
        TRAIL_ALPHA_MAX
        - (TRAIL_ALPHA_MAX - TRAIL_ALPHA_MIN) * (age / max(trail_frames - 1, 1))
        for age in range(trail_frames)
    ]
    trail_lines = {}
    current_scatters = {}
    for category in CATEGORY_ORDER:
        base_size = 8 if category in {"regional", "s_bahn_local"} else 13
        trail_lines[category] = [
            LineCollection(
                [],
                colors=[to_rgba(CATEGORY_COLORS[category], alpha=trail_alphas[age] * 0.7)],
                linewidths=max(1.0 - age * 0.08, 0.35),
                capstyle="round",
                zorder=7 + trail_frames - age,
            )
            for age in range(trail_frames)
        ]
        for collection in trail_lines[category]:
            ax.add_collection(collection)
        current_scatters[category] = ax.scatter(
            [],
            [],
            s=base_size,
            c=CATEGORY_COLORS[category],
            alpha=POINT_ALPHA,
            linewidths=0,
            zorder=20,
        )
    title = ax.set_title("", fontsize=15, fontweight="bold", pad=14, color=FOREGROUND)
    caption = ax.text(
        0.5,
        -0.055,
        "",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=8,
        color=MUTED,
    )

    def update(frame_index):
        positions = sampled_positions[frame_index]
        caption_parts = []
        for category in CATEGORY_ORDER:
            current_group = positions[positions["category"] == category]
            current_scatters[category].set_offsets(current_group[["lon", "lat"]].to_numpy())

            for age, collection in enumerate(trail_lines[category]):
                older_index = frame_index - age - 1
                newer_index = frame_index - age
                if older_index < 0:
                    collection.set_segments([])
                    continue

                older = sampled_positions[older_index]
                newer = sampled_positions[newer_index]
                older = older[older["category"] == category][["trip_id", "lon", "lat"]]
                newer = newer[newer["category"] == category][["trip_id", "lon", "lat"]]
                trail = older.merge(
                    newer,
                    on="trip_id",
                    how="inner",
                    suffixes=("_older", "_newer"),
                )
                collection.set_segments(
                    [
                        (
                            (row.lon_older, row.lat_older),
                            (row.lon_newer, row.lat_newer),
                        )
                        for row in trail.itertuples(index=False)
                    ]
                )

            if not current_group.empty:
                caption_parts.append(f"{CATEGORY_LABELS[category]} {len(current_group):,}")
        title.set_text(
            f"Scheduled German Train Positions - {service_date:%Y-%m-%d} {format_service_time(frame_seconds[frame_index])}"
        )
        caption.set_text(
            "GTFS schedule data. Stop-to-stop interpolation because shapes.txt is missing.\n"
            f"{len(positions):,} active movements | {' | '.join(caption_parts)}"
        )
        return [
            artist
            for category_collections in trail_lines.values()
            for artist in category_collections
        ] + [
            *current_scatters.values(),
            title,
            caption,
        ]

    animation = FuncAnimation(fig, update, frames=tqdm(range(len(frame_seconds)), desc="Animating"))
    animation.save(output_path, writer=PillowWriter(fps=fps))
    plt.close(fig)
    return {
        "frames": len(frame_seconds),
        "start_time": format_service_time(start_seconds),
        "end_time": format_service_time(end_seconds),
        "step_minutes": step_minutes,
        "fps": fps,
        "trail_frames": trail_frames,
    }
