import matplotlib.pyplot as plt
import numpy as np
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
    GRID,
    MUTED,
    NETWORK_LINE_ALPHA,
    POINT_ALPHA,
    TRAIL_ALPHA_MAX,
    TRAIL_ALPHA_MIN,
    TRAIL_FRAMES,
)


DISPLAY_LEGEND_CATEGORIES = ["regional", "s_bahn_local", "intercity", "high_speed"]
LONG_DISTANCE_CATEGORIES = {"intercity", "high_speed", "night_train"}


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


def format_short_service_time(seconds):
    hours, remainder = divmod(int(seconds), 3600)
    minutes = remainder // 60
    return f"{hours:02d}:{minutes:02d}"


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


def daily_peak_time(movement_segments, start_seconds=0, end_seconds=24 * 3600):
    sample_seconds = list(range(start_seconds, end_seconds + 1, 60))
    if not sample_seconds or movement_segments.empty:
        return None, 0

    departures = movement_segments["departure_seconds"].to_numpy(dtype=float)
    arrivals = movement_segments["next_arrival_seconds"].to_numpy(dtype=float)
    sample_count = len(sample_seconds)

    start_indices = np.ceil((departures - start_seconds) / 60).astype(np.int64)
    end_indices = np.floor((arrivals - start_seconds) / 60).astype(np.int64)
    valid = (
        (end_indices >= 0)
        & (start_indices < sample_count)
        & (end_indices >= start_indices)
        & (arrivals > departures)
    )

    start_indices = np.clip(start_indices[valid], 0, sample_count - 1)
    end_indices = np.clip(end_indices[valid], 0, sample_count - 1)

    diff = np.zeros(sample_count + 1, dtype=np.int64)
    np.add.at(diff, start_indices, 1)
    np.add.at(diff, end_indices + 1, -1)
    counts = np.cumsum(diff[:-1])
    peak_index = int(counts.argmax())
    return sample_seconds[peak_index], int(counts[peak_index])


def frame_summary_text(positions, peak_seconds):
    total = len(positions)
    if total:
        category_counts = positions["category"].value_counts()
        regional_share = category_counts.get("regional", 0) / total
        long_distance_share = (
            sum(category_counts.get(category, 0) for category in LONG_DISTANCE_CATEGORIES)
            / total
        )
    else:
        regional_share = 0.0
        long_distance_share = 0.0

    peak_text = format_short_service_time(peak_seconds) if peak_seconds is not None else "n/a"
    return (
        f"Active movements: {total:,}  |  Peak today: {peak_text}  |  "
        f"Regional share: {regional_share:.0%}  |  "
        f"Long-distance share: {long_distance_share:.0%}"
    )


def add_category_legend(fig):
    handles = [
        plt.Line2D(
            [0],
            [0],
            color=CATEGORY_COLORS[category],
            lw=2.5,
            label=CATEGORY_LABELS[category],
        )
        for category in DISPLAY_LEGEND_CATEGORIES
    ]
    legend = fig.legend(
        handles=handles,
        loc="upper center",
        ncols=len(handles),
        frameon=False,
        bbox_to_anchor=(0.5, 0.905),
        fontsize=8,
        handlelength=2.0,
        columnspacing=1.5,
    )
    for text in legend.get_texts():
        text.set_color(FOREGROUND)
    return legend


def add_time_progress_bar(ax, frame_seconds, start_seconds=0, end_seconds=24 * 3600):
    left, right, y = 0.22, 0.78, -0.125
    progress = (
        (frame_seconds - start_seconds) / (end_seconds - start_seconds)
        if end_seconds > start_seconds
        else 0
    )
    progress = min(max(progress, 0), 1)
    marker_x = left + (right - left) * progress

    ax.plot(
        [left, right],
        [y, y],
        transform=ax.transAxes,
        color=GRID,
        linewidth=2.2,
        alpha=0.9,
        solid_capstyle="round",
        clip_on=False,
    )
    progress_line = ax.plot(
        [left, marker_x],
        [y, y],
        transform=ax.transAxes,
        color=FOREGROUND,
        linewidth=2.2,
        alpha=0.72,
        solid_capstyle="round",
        clip_on=False,
    )[0]
    marker = ax.plot(
        [marker_x],
        [y],
        transform=ax.transAxes,
        marker="o",
        markersize=5,
        color=FOREGROUND,
        alpha=0.95,
        clip_on=False,
    )[0]
    ax.text(
        left - 0.025,
        y,
        format_short_service_time(start_seconds),
        transform=ax.transAxes,
        ha="right",
        va="center",
        fontsize=8,
        color=MUTED,
        clip_on=False,
    )
    ax.text(
        right + 0.025,
        y,
        format_short_service_time(end_seconds),
        transform=ax.transAxes,
        ha="left",
        va="center",
        fontsize=8,
        color=MUTED,
        clip_on=False,
    )
    time_label = ax.text(
        marker_x,
        y - 0.035,
        format_short_service_time(frame_seconds),
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=8,
        color=FOREGROUND,
        clip_on=False,
    )
    return progress_line, marker, time_label


def update_time_progress_bar(
    progress_artists,
    frame_seconds,
    start_seconds=0,
    end_seconds=24 * 3600,
):
    progress_line, marker, time_label = progress_artists
    left, right, y = 0.22, 0.78, -0.125
    progress = (
        (frame_seconds - start_seconds) / (end_seconds - start_seconds)
        if end_seconds > start_seconds
        else 0
    )
    progress = min(max(progress, 0), 1)
    marker_x = left + (right - left) * progress

    progress_line.set_data([left, marker_x], [y, y])
    marker.set_data([marker_x], [y])
    time_label.set_position((marker_x, y - 0.035))
    time_label.set_text(format_short_service_time(frame_seconds))


def render_timestamp_frame(
    positions,
    segments,
    service_date,
    frame_seconds,
    output_path,
    peak_seconds=None,
):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 12), dpi=180)
    fig.subplots_adjust(top=0.84, bottom=0.16)
    ax.set_facecolor(BACKGROUND)
    fig.patch.set_facecolor(BACKGROUND)
    add_germany_map_background(ax)
    add_network_background(ax, segments)

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

    style_germany_axis(ax)

    ax.set_title(
        f"Scheduled German Train Positions - {service_date:%Y-%m-%d} {format_service_time(frame_seconds)}",
        fontsize=15,
        fontweight="bold",
        pad=28,
        color=FOREGROUND,
    )
    add_category_legend(fig)
    ax.text(
        0.5,
        -0.055,
        frame_summary_text(positions, peak_seconds),
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=9,
        color=FOREGROUND,
        fontweight="bold",
    )
    add_time_progress_bar(ax, frame_seconds)
    ax.text(
        0.5,
        -0.175,
        "GTFS schedule data. Train positions use stop-to-stop interpolation because shapes.txt is missing.",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=8,
        color=MUTED,
    )

    fig.savefig(output_path, bbox_inches="tight", pad_inches=0.26, facecolor=fig.get_facecolor())
    plt.close(fig)


def create_timestamp_frame(data_dir, service_date, frame_time, output_path):
    frame_seconds = parse_frame_time(frame_time)
    movement_segments, background_segments = load_interpolation_data(
        data_dir, service_date
    )
    positions = positions_at_time(movement_segments, frame_seconds)
    peak_seconds, _peak_count = daily_peak_time(movement_segments)
    render_timestamp_frame(
        positions,
        background_segments,
        service_date,
        frame_seconds,
        output_path,
        peak_seconds=peak_seconds,
    )
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
    peak_seconds, _peak_count = daily_peak_time(movement_segments)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 12), dpi=120)
    fig.subplots_adjust(top=0.84, bottom=0.16)
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
    title = ax.set_title("", fontsize=15, fontweight="bold", pad=28, color=FOREGROUND)
    add_category_legend(fig)
    stats_strip = ax.text(
        0.5,
        -0.055,
        "",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=9,
        color=FOREGROUND,
        fontweight="bold",
    )
    progress_artists = add_time_progress_bar(ax, frame_seconds[0])
    caption = ax.text(
        0.5,
        -0.175,
        "GTFS schedule data. Stop-to-stop interpolation because shapes.txt is missing.",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=8,
        color=MUTED,
    )

    def update(frame_index):
        positions = sampled_positions[frame_index]
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

        title.set_text(
            f"Scheduled German Train Positions - {service_date:%Y-%m-%d} {format_service_time(frame_seconds[frame_index])}"
        )
        stats_strip.set_text(frame_summary_text(positions, peak_seconds))
        update_time_progress_bar(progress_artists, frame_seconds[frame_index])
        return [
            artist
            for category_collections in trail_lines.values()
            for artist in category_collections
        ] + [
            *current_scatters.values(),
            title,
            stats_strip,
            *progress_artists,
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
