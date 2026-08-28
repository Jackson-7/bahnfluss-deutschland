import argparse
from pathlib import Path

from bahnfluss_deutschland.gtfs_categories import CATEGORY_LABELS
from bahnfluss_deutschland.gtfs_activity_stats import create_activity_outputs
from bahnfluss_deutschland.gtfs_static_map import (
    create_static_rail_map,
    parse_service_date,
)
from bahnfluss_deutschland.gtfs_timestamp_frame import (
    create_animation,
    create_timestamp_frame,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FRAME_TIME = "07:12"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bahnfluss-deutschland",
        description="Build scheduled German rail visualizations from GTFS feeds.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "data",
        help="Directory containing GTFS feed folders.",
    )
    parser.add_argument(
        "--date",
        default="2026-08-22",
        help="Service date to render in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path for the generated static map image.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate all currently supported outputs.",
    )
    parser.add_argument(
        "--time",
        default=None,
        help="Optional service-day timestamp to render, for example 07:12 or 25:10:00.",
    )
    parser.add_argument(
        "--animate",
        action="store_true",
        help="Render a compressed service-day train movement GIF.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Write active train counts over time as CSV plus an activity plot.",
    )
    parser.add_argument(
        "--plot-output",
        type=Path,
        default=None,
        help="Path for the generated activity plot when using --stats.",
    )
    parser.add_argument(
        "--start-time",
        default="00:00",
        help="Animation or stats start service-day time. Default: 00:00.",
    )
    parser.add_argument(
        "--end-time",
        default="24:00",
        help="Animation or stats end service-day time. Default: 24:00.",
    )
    parser.add_argument(
        "--step-minutes",
        type=int,
        default=None,
        help="Minutes between animation frames or stats samples. Defaults: 10 for animation, 1 for stats.",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=12,
        help="Animation frames per second. Default: 12.",
    )
    parser.add_argument(
        "--trail-frames",
        type=int,
        default=None,
        help="Number of previous animation frames to show as a fading trail. Default: 8.",
    )
    return parser


def _print_static_summary(summaries):
    for summary in summaries:
        shape_status = "has shapes.txt" if summary["uses_shapes"] else "no shapes.txt"
        print(
            f"{summary['label']}: {summary['active_services']:,} active services, "
            f"{summary['active_trips']:,} active trips, "
            f"{summary['stop_times']:,} stop times, "
            f"{summary['segments']:,} rendered segments, "
            f"{shape_status}"
        )


def run_static_map(data_dir, service_date, output):
    output = (
        output or PROJECT_ROOT / f"outputs/active_rail_map_{service_date:%Y-%m-%d}.png"
    )
    summaries = create_static_rail_map(data_dir, service_date, output)
    print(f"Wrote {output}")
    _print_static_summary(summaries)


def run_timestamp_frame(data_dir, service_date, frame_time, output):
    safe_time = frame_time.replace(":", "-")
    output = (
        output
        or PROJECT_ROOT
        / f"outputs/train_positions_{service_date:%Y-%m-%d}_{safe_time}.png"
    )
    positions = create_timestamp_frame(data_dir, service_date, frame_time, output)
    print(f"Wrote {output}")
    print(f"{len(positions):,} active train movements at service time {frame_time}")


def run_animation(
    data_dir,
    service_date,
    output,
    start_time,
    end_time,
    step_minutes,
    fps,
    trail_frames,
):
    output = (
        output or PROJECT_ROOT / f"outputs/train_animation_{service_date:%Y-%m-%d}.gif"
    )
    summary = create_animation(
        data_dir,
        service_date,
        output,
        start_time=start_time,
        end_time=end_time,
        step_minutes=step_minutes,
        fps=fps,
        trail_frames=trail_frames,
    )
    print(f"Wrote {output}")
    print(
        f"{summary['frames']:,} frames from {summary['start_time']} to "
        f"{summary['end_time']} every {summary['step_minutes']} minutes "
        f"at {summary['fps']} fps with {summary['trail_frames']} trail frames"
    )


def run_activity_stats(
    data_dir, service_date, output, plot_output, start_time, end_time, step_minutes
):
    output = (
        output
        or PROJECT_ROOT / f"outputs/train_activity_stats_{service_date:%Y-%m-%d}.csv"
    )
    plot_output = (
        plot_output
        or PROJECT_ROOT / f"outputs/train_activity_plot_{service_date:%Y-%m-%d}.png"
    )
    summary = create_activity_outputs(
        data_dir,
        service_date,
        output,
        plot_output,
        start_time=start_time,
        end_time=end_time,
        step_minutes=step_minutes,
    )
    print(f"Wrote {output}")
    print(f"Wrote {plot_output}")
    print(
        f"{summary['rows']:,} samples. Peak {summary['peak_total']:,} at "
        f"{summary['peak_time']}; low {summary['low_total']:,} at "
        f"{summary['low_time']}."
    )
    for label, train_minutes in summary["train_minutes"].items():
        share = summary["shares"][label] * 100
        print(
            f"{CATEGORY_LABELS[label]}: {train_minutes:,} train-minutes ({share:.1f}%)"
        )


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    service_date = parse_service_date(args.date)

    if args.all:
        frame_time = args.time or DEFAULT_FRAME_TIME
        animation_step = args.step_minutes or 10
        print(f"Generating all outputs for {service_date:%Y-%m-%d}")
        run_static_map(args.data_dir, service_date, None)
        run_timestamp_frame(args.data_dir, service_date, frame_time, None)
        run_animation(
            args.data_dir,
            service_date,
            None,
            args.start_time,
            args.end_time,
            animation_step,
            args.fps,
            args.trail_frames,
        )
        run_activity_stats(
            args.data_dir,
            service_date,
            None,
            None,
            args.start_time,
            args.end_time,
            1,
        )
    elif args.animate:
        run_animation(
            args.data_dir,
            service_date,
            args.output,
            args.start_time,
            args.end_time,
            args.step_minutes or 10,
            args.fps,
            args.trail_frames,
        )
    elif args.stats:
        run_activity_stats(
            args.data_dir,
            service_date,
            args.output,
            args.plot_output,
            args.start_time,
            args.end_time,
            args.step_minutes or 1,
        )
    elif args.time:
        run_timestamp_frame(args.data_dir, service_date, args.time, args.output)
    else:
        run_static_map(args.data_dir, service_date, args.output)
