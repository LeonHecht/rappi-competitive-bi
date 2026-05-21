"""CLI runner for the competitive intelligence analysis pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from analysis.processing import run_analysis_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run competitive intelligence analysis.")
    parser.add_argument("--input", default="data/raw/scrape.csv", help="Raw scraper CSV path.")
    parser.add_argument("--processed-dir", default="data/processed", help="Processed output directory.")
    parser.add_argument("--figures-dir", default="reports/figures", help="Chart output directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_analysis_pipeline(
        raw_path=Path(args.input),
        processed_dir=Path(args.processed_dir),
        figures_dir=Path(args.figures_dir),
    )
    for name, path in outputs.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()

