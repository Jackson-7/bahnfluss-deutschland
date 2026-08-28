import argparse
from pathlib import Path

from bahnfluss_deutschland.gtfs_static_map import (
    create_static_rail_map,
    parse_service_date,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
    return parser


def main() -> None:
    args = build_parser().parse_args()
    service_date = parse_service_date(args.date)
    output = (
        args.output
        or PROJECT_ROOT / f"outputs/active_rail_map_{service_date:%Y-%m-%d}.png"
    )
    summaries = create_static_rail_map(args.data_dir, service_date, output)

    print(f"Wrote {output}")
    for summary in summaries:
        shape_status = "has shapes.txt" if summary["uses_shapes"] else "no shapes.txt"
        print(
            f"{summary['label']}: {summary['active_services']:,} active services, "
            f"{summary['active_trips']:,} active trips, "
            f"{summary['stop_times']:,} stop times, "
            f"{summary['segments']:,} rendered segments, "
            f"{shape_status}"
        )
