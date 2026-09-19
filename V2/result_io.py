"""Stable JSON/CSV output helpers; raw rows are never averaged away."""
from __future__ import annotations

import csv
import json
from pathlib import Path


CSV_FIELDS = [
    "run_id", "case_id", "family", "source", "trial", "model", "model_family",
    "provider", "prompt_version", "backend", "member_id", "expected_decision",
    "actual_decision", "expected_trigger_missing", "actual_trigger_missing",
    "code_check_pass", "judgement_check_pass", "overall_pass", "turns", "tokens_in",
    "tokens_out", "cached_tokens", "reasoning_tokens", "observation_tool_return_tokens",
    "target_tool_observation_tokens", "observation_token_method", "token_counts_measured",
    "input_token_price_per_million", "output_token_price_per_million",
    "cached_input_price_per_million", "cost_usd", "calculated_cost_usd",
    "provider_reported_cost_usd", "judgement_cost_usd", "seconds", "tools_called",
    "evidence_used", "guardrails_fired", "stopped_by", "negative_case", "run_timestamp",
    "code_check_failures", "judgement",
]


def _cell(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def write_raw(rows: list[dict], json_path: Path, csv_path: Path, config_snapshot: dict):
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps({"config": config_snapshot, "raw_runs": rows}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _cell(row.get(field)) for field in CSV_FIELDS})


def load_raw(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("raw_runs", payload if isinstance(payload, list) else [])
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for key in ("trial", "turns", "tokens_in", "tokens_out", "cached_tokens", "reasoning_tokens", "observation_tool_return_tokens", "target_tool_observation_tokens"):
            if row.get(key) not in (None, ""):
                row[key] = int(float(row[key]))
        for key in ("cost_usd", "seconds", "input_token_price_per_million", "output_token_price_per_million", "cached_input_price_per_million"):
            if row.get(key) not in (None, ""):
                row[key] = float(row[key])
        for key in ("overall_pass", "negative_case", "code_check_pass", "judgement_check_pass"):
            if row.get(key) not in (None, ""):
                row[key] = str(row[key]).lower() == "true"
    return rows
