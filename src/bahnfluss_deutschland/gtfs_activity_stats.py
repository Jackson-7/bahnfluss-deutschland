import numpy as np
import pandas as pd

from bahnfluss_deutschland.gtfs_categories import CATEGORY_ORDER
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


def create_activity_outputs(
    data_dir,
    service_date,
    csv_output_path,
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
    return summarize_activity_stats(stats, step_minutes)
