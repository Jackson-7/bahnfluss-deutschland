import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from bahnfluss_deutschland.cli import main as cli_main


# Set this when you prefer running main.py directly from your editor.
# Leave it as None to use terminal args, or default to --all when no args are passed.
# RUN_ARGS: list[str] | None = None

# Examples:
# RUN_ARGS = ["--all"]
# RUN_ARGS = ["--date", "2026-08-22", "--time", "07:12"]
# RUN_ARGS = ["--date", "2026-08-22", "--animate", "--step-minutes", "30", "--fps", "8"]
# RUN_ARGS = ["--date", "2026-08-22", "--stats", "--step-minutes", "5"]
RUN_ARGS = None


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cli_main()
    elif RUN_ARGS is not None:
        cli_main(RUN_ARGS)
    else:
        cli_main(["--all"])
