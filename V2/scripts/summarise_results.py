#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics import generate_all
from result_io import load_raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("result_file", type=Path)
    args = parser.parse_args()
    rows = load_raw(args.result_file)
    generate_all(rows, ROOT / "results")
    print(f"Summarised {len(rows)} raw runs into {ROOT / 'results'}")


if __name__ == "__main__":
    main()
