#!/usr/bin/env python3
"""Apply the documented item-level judgement contract to preserved outputs."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["BACKEND"] = "live"
os.environ["MODEL"] = "google/gemini-2.5-flash-lite"
os.environ["JUDGE_MODEL"] = "openai/gpt-4o-mini"
os.environ["PROMPT_VERSION"] = "v1"

import config
from analytics import generate_all
from result_io import load_raw, write_raw


def main():
    json_path = ROOT / "results" / "v1_raw_results.json"
    csv_path = ROOT / "results" / "v1_raw_results.csv"
    rows = load_raw(json_path)
    changed = 0
    for row in rows:
        judgement = row.get("judgement") or {}
        items = judgement.get("item_results") if isinstance(judgement.get("item_results"), list) else []
        criteria = (row.get("expected") or {}).get("must_record", [])
        old = judgement.get("verdict")
        new = bool(len(items) == len(criteria) and all(item.get("met") is True for item in items))
        judgement.setdefault("model_reported_verdict", old)
        judgement["verdict"] = new
        judgement["verdict_policy"] = "one item result per must_record criterion; all met must be true"
        row["judgement"] = judgement
        row["judgement_check_pass"] = new
        row["overall_pass"] = bool(row.get("code_check_pass") and new)
        changed += old != new
    snapshot = config.public_snapshot()
    if rows:
        snapshot["member_id"] = rows[0].get("member_id", snapshot["member_id"])
        snapshot["price_resolution"] = "OpenRouter /api/v1/models (resolved before formal live run)"
    write_raw(rows, json_path, csv_path, snapshot)
    generate_all(rows, ROOT / "results")
    print(f"normalised {len(rows)} judgements; {changed} top-level verdict(s) changed")


if __name__ == "__main__":
    main()
