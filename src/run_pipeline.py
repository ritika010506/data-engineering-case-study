"""Run the complete data engineering pipeline in sequence."""

import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"

PIPELINE_STEPS = [
    ("Generate mock data", "generate_data.py"),
    ("Validate records and load Bronze", "ingestion.py"),
    ("Transform Bronze to Silver", "transformations.py"),
    ("Build Gold star schema", "gold.py"),
    ("Execute analytical queries", "run_queries.py"),
]


def main():
    print("=" * 60)
    print("STARTING DATA ENGINEERING PIPELINE")
    print("=" * 60)

    for step_name, script_name in PIPELINE_STEPS:
        print(f"\n\n>>> {step_name}")
        print("-" * 60)

        script_path = SRC_DIR / script_name

        subprocess.run(
            [sys.executable, str(script_path)],
            cwd=BASE_DIR,
            check=True,
        )

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()
