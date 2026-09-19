#!/usr/bin/env python3
"""Merge teammate raw files without discarding any run."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics import d6_rows, summary_rows
from result_io import CSV_FIELDS, _cell, load_raw


def write_csv(path, rows, fields=None):
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _cell(row.get(field)) for field in fields})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("result_files", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    rows = []
    for path in args.result_files:
        rows.extend(load_raw(path))
    ids = [row.get("run_id") for row in rows]
    duplicates = sorted({run_id for run_id in ids if run_id and ids.count(run_id) > 1})
    if duplicates:
        raise SystemExit(f"Duplicate run_id values found: {duplicates}")
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "all_models_raw.json").write_text(json.dumps({"raw_runs": rows}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(out / "all_models_raw.csv", rows, CSV_FIELDS)
    write_csv(out / "model_battery_summary.csv", summary_rows(rows))
    write_csv(out / "D6_ALL_MODELS_HANDOFF.csv", d6_rows(rows))
    print(f"Merged {len(rows)} raw runs from {len(args.result_files)} file(s).")


if __name__ == "__main__":
    main()
