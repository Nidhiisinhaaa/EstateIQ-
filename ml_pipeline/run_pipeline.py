"""
CLI entry point for the EstateIQ ML pipeline.

Usage:
    python ml_pipeline/run_pipeline.py --step clean
    python ml_pipeline/run_pipeline.py --step eda
    python ml_pipeline/run_pipeline.py --step features
    python ml_pipeline/run_pipeline.py --step train
    python ml_pipeline/run_pipeline.py --step all

Step modules are named with numeric prefixes (01_clean.py, 02_eda.py, ...) for readability in a
file listing, which makes them invalid Python module names -- they are loaded here via
importlib.util rather than a normal import statement.
"""

import argparse
import importlib.util
import sys
from pathlib import Path

STEPS_DIR = Path(__file__).resolve().parent / "steps"

STEP_FILES = {
    "clean": "01_clean.py",
    "eda": "02_eda.py",
    "features": "03_features.py",
    "train": "04_train.py",
}


def _load_step_module(step_name: str):
    filename = STEP_FILES[step_name]
    path = STEPS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Step module not found: {path}")
    spec = importlib.util.spec_from_file_location(f"ml_pipeline.steps.{step_name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_step(step_name: str):
    print(f"\n{'=' * 70}\nRUNNING STEP: {step_name}\n{'=' * 70}")
    module = _load_step_module(step_name)
    if not hasattr(module, "run"):
        raise AttributeError(f"Step '{step_name}' ({STEP_FILES[step_name]}) has no run() function")
    return module.run()


def main():
    parser = argparse.ArgumentParser(description="EstateIQ ML pipeline runner")
    parser.add_argument(
        "--step",
        choices=list(STEP_FILES.keys()) + ["all"],
        required=True,
        help="Pipeline step to run, or 'all' to run the full chain in order",
    )
    args = parser.parse_args()

    if args.step == "all":
        for step_name in STEP_FILES.keys():
            if not (STEPS_DIR / STEP_FILES[step_name]).exists():
                print(f"Skipping '{step_name}': {STEP_FILES[step_name]} not implemented yet")
                continue
            run_step(step_name)
    else:
        run_step(args.step)


if __name__ == "__main__":
    sys.exit(main())
