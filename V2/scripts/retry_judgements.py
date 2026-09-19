#!/usr/bin/env python3
"""Retry pending judge calls without repeating paid V1 agent runs."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="google/gemini-2.5-flash-lite")
    parser.add_argument("--judge-model", default="openai/gpt-4o-mini")
    args = parser.parse_args()
    os.environ["BACKEND"] = "live"
    os.environ["MODEL"] = args.model
    os.environ["JUDGE_MODEL"] = args.judge_model
    os.environ["PROMPT_VERSION"] = "v1"

    import config
    from analytics import generate_all
    from harness import judgement_check
    from result_io import load_raw, write_raw

    path = ROOT / "results" / "v1_raw_results.json"
    rows = load_raw(path)
    pending = [row for row in rows if row.get("judgement_check_pass") is None]
    print(f"pending judgements={len(pending)}")
    for row in pending:
        judgement = judgement_check(row["record"], row["expected"], "live")
        row["judgement"] = judgement
        row["judgement_check_pass"] = judgement.get("verdict")
        row["judgement_cost_usd"] = judgement.get("cost_usd")
        row["overall_pass"] = bool(row.get("code_check_pass") and judgement.get("verdict") is True)
        write_raw(rows, path, ROOT / "results" / "v1_raw_results.csv", config.public_snapshot())
        print(f"judged {row['case_id']} trial {row['trial']}: {row['judgement_check_pass']}", flush=True)
    generate_all(rows, ROOT / "results")


if __name__ == "__main__":
    main()
