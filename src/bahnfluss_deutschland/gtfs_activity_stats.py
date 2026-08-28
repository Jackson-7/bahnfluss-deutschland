import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from bahnfluss_deutschland.gtfs_basemap import add_germany_watermark
from bahnfluss_deutschland.gtfs_categories import (
    CATEGORY_COLORS,
    CATEGORY_LABELS,
    CATEGORY_ORDER,
)
from bahnfluss_deutschland.gtfs_theme import (
    BACKGROUND,
    FOREGROUND,
    GRID,
    MUTED,
    PLOT_FILL_ALPHA,
    PLOT_LINE_ALPHA,
    SPINE,
    TOTAL,
    TOTAL_LINE_ALPHA,
)
from bahnfluss_deutschland.gtfs_timestamp_frame import (
    format_service_time,
    load_interpolation_data,
    parse_frame_time,
)


def _sample_seconds(start_seconds, end_seconds, step_minutes):
    if end_seconds <= start_seconds:
        raise ValueError("Stats end time must be after start time")
    if step_minutes <= 0:
        raise ValueError("Stats step minutes must be positive")
    return np.arange(start_seconds, end_seconds + 1, step_minutes * 60, dtype=np.int64)


def _counts_for_feed(movements, sample_seconds, step_seconds):
    counts = {}
    start_seconds = sample_seconds[0]
    sample_count = len(sample_seconds)

    for category, group in movements.groupby("category"):
        departures = group["departure_seconds"].to_numpy(dtype=float)
        arrivals = group["next_arrival_seconds"].to_numpy(dtype=float)

        start_indices = np.ceil((departures - start_seconds) / step_seconds).astype(np.int64)
        end_indices = np.floor((arrivals - start_seconds) / step_seconds).astype(np.int64)
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
        counts[str(category)] = np.cumsum(diff[:-1])

    return counts


def build_activity_stats(
    data_dir,
    service_date,
    start_time="00:00",
    end_time="24:00",
    step_minutes=1,
):
    start_seconds = parse_frame_time(start_time)
    end_seconds = parse_frame_time(end_time)
    samples = _sample_seconds(start_seconds, end_seconds, step_minutes)
    movements, _background_segments = load_interpolation_data(data_dir, service_date)
    counts = _counts_for_feed(movements, samples, step_minutes * 60)

    stats = pd.DataFrame(
        {
            "service_seconds": samples,
            "service_time": [format_service_time(value) for value in samples],
        }
    )
    category_columns = [category for category in CATEGORY_ORDER if category in counts]
    for category in category_columns:
        stats[category] = counts[category]

    stats["total"] = stats[category_columns].sum(axis=1) if category_columns else 0
    stats = stats[["service_seconds", "service_time", "total", *category_columns]]
    return stats


def summarize_activity_stats(stats, step_minutes):
    peak = stats.loc[stats["total"].idxmax()]
    low = stats.loc[stats["total"].idxmin()]
    feed_columns = [
        column
        for column in stats.columns
        if column not in {"service_seconds", "service_time", "total"}
    ]
    train_minutes = {
        column: int(stats[column].sum() * step_minutes) for column in feed_columns
    }
    total_train_minutes = sum(train_minutes.values())
    shares = {
        column: (
            train_minutes[column] / total_train_minutes
            if total_train_minutes
            else 0.0
        )
        for column in feed_columns
    }
    return {
        "rows": len(stats),
        "peak_time": peak["service_time"],
        "peak_total": int(peak["total"]),
        "low_time": low["service_time"],
        "low_total": int(low["total"]),
        "train_minutes": train_minutes,
        "shares": shares,
    }


def render_activity_plot(stats, service_date, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    feed_columns = [
        column
        for column in stats.columns
        if column not in {"service_seconds", "service_time", "total"}
    ]
    hours = stats["service_seconds"] / 3600

    fig, ax = plt.subplots(figsize=(12, 5.6), dpi=180)
    fig.subplots_adjust(top=0.72)
    fig.patch.set_facecolor(BACKGROUND)
    ax.set_facecolor(BACKGROUND)
    add_germany_watermark(ax)

    ax.plot(
        hours,
        stats["total"],
        color=TOTAL,
        linewidth=2.0,
        alpha=TOTAL_LINE_ALPHA,
        label="total",
    )
    for column in [category for category in CATEGORY_ORDER if category in feed_columns]:
        ax.fill_between(
            hours,
            stats[column],
            color=CATEGORY_COLORS[column],
            alpha=PLOT_FILL_ALPHA,
            linewidth=0,
        )
        ax.plot(
            hours,
            stats[column],
            color=CATEGORY_COLORS[column],
            linewidth=1.2,
            alpha=PLOT_LINE_ALPHA,
            label=CATEGORY_LABELS[column],
        )

    peak = stats.loc[stats["total"].idxmax()]
    peak_hour = peak["service_seconds"] / 3600
    ax.scatter([peak_hour], [peak["total"]], color=TOTAL, alpha=TOTAL_LINE_ALPHA, s=22, zorder=4)
    ax.annotate(
        f"Peak {peak['service_time']} ({int(peak['total']):,})",
        xy=(peak_hour, peak["total"]),
        xytext=(8, 10),
        textcoords="offset points",
        fontsize=8,
        color=FOREGROUND,
    )

    fig.suptitle(
        f"Scheduled German Rail Activity - {service_date:%Y-%m-%d}",
        fontsize=14,
        fontweight="bold",
        y=0.97,
        color=FOREGROUND,
    )
    ax.set_xlabel("Service-day hour")
    ax.set_ylabel("Active train movements")
    ax.xaxis.label.set_color(FOREGROUND)
    ax.yaxis.label.set_color(FOREGROUND)
    ax.tick_params(colors=MUTED)
    ax.grid(True, color=GRID, linewidth=0.6, alpha=0.72)
    legend = ax.legend(
        frameon=False,
        ncols=3,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.91),
        bbox_transform=fig.transFigure,
    )
    for text in legend.get_texts():
        text.set_color(FOREGROUND)
    for name, spine in ax.spines.items():
        if name in {"top", "right"}:
            spine.set_visible(False)
        else:
            spine.set_color(SPINE)

    fig.savefig(output_path, bbox_inches="tight", pad_inches=0.18, facecolor=fig.get_facecolor())
    plt.close(fig)


def create_activity_outputs(
    data_dir,
    service_date,
    csv_output_path,
    plot_output_path,
    start_time="00:00",
    end_time="24:00",
    step_minutes=1,
):
    stats = build_activity_stats(
        data_dir,
        service_date,
        start_time=start_time,
        end_time=end_time,
        step_minutes=step_minutes,
    )
    csv_output_path.parent.mkdir(parents=True, exist_ok=True)
    stats.to_csv(csv_output_path, index=False)
    render_activity_plot(stats, service_date, plot_output_path)
    return summarize_activity_stats(stats, step_minutes)
