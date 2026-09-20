"""Summaries, D6 handoff, and V1 failure analysis."""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

import config


def _mean(values):
    return statistics.mean(values) if values else None


def _median(values):
    return statistics.median(values) if values else None


def _rate(rows):
    return sum(bool(row.get("overall_pass")) for row in rows) / len(rows) if rows else None


def _failed_ids(rows):
    return sorted({row["case_id"] for row in rows if not row.get("overall_pass")})


def summary_rows(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[(row["model"], row["provider"], row["prompt_version"], row["backend"])].append(row)
    output = []
    for (model, provider, prompt_version, backend), group in groups.items():
        ordinary = [r for r in group if not r.get("negative_case")]
        negative = [r for r in group if r.get("negative_case")]
        base = {
            "model": model,
            "provider": provider,
            "prompt_version": prompt_version,
            "backend": backend,
            "scope": "overall",
            "family": "ALL",
            "passing_trials": sum(bool(r.get("overall_pass")) for r in group),
            "total_trials": len(group),
            "success_rate": _rate(group),
            "ordinary_trials": len(ordinary),
            "ordinary_passes": sum(bool(r.get("overall_pass")) for r in ordinary),
            "ordinary_pass_rate": _rate(ordinary),
            "negative_trials": len(negative),
            "negative_passes": sum(bool(r.get("overall_pass")) for r in negative),
            "negative_pass_rate": _rate(negative),
            "failed_negative_case_ids": ";".join(_failed_ids(negative)),
            "failed_negative_families": ";".join(sorted({r["family"] for r in negative if not r.get("overall_pass")})),
        }
        output.append(base)
        for family in sorted({r["family"] for r in group}):
            family_rows = [r for r in group if r["family"] == family]
            output.append({
                **base,
                "scope": "family",
                "family": family,
                "passing_trials": sum(bool(r.get("overall_pass")) for r in family_rows),
                "total_trials": len(family_rows),
                "success_rate": _rate(family_rows),
                "ordinary_trials": "",
                "ordinary_passes": "",
                "ordinary_pass_rate": "",
                "negative_trials": "",
                "negative_passes": "",
                "negative_pass_rate": "",
                "failed_negative_case_ids": "",
                "failed_negative_families": "",
            })
    return output


def write_summary(rows: list[dict], path: Path):
    data = summary_rows(rows)
    fields = list(data[0]) if data else ["model", "provider", "prompt_version", "backend", "scope"]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)


def d6_rows(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[(row["model"], row["provider"], row["prompt_version"], row["backend"])].append(row)
    output = []
    for (model, provider, prompt_version, backend), group in groups.items():
        negative = [r for r in group if r.get("negative_case")]
        ordinary = [r for r in group if not r.get("negative_case")]
        tokens_in = [int(r.get("tokens_in") or 0) for r in group]
        tokens_out = [int(r.get("tokens_out") or 0) for r in group]
        costs = [float(r.get("cost_usd") or 0) for r in group]
        turns = [int(r.get("turns") or 0) for r in group]
        seconds = [float(r.get("seconds") or 0) for r in group]
        obs = [int(r.get("observation_tool_return_tokens") or 0) for r in group]
        target_obs = [int(r.get("target_tool_observation_tokens") or 0) for r in group]
        p = _rate(group) or 0.0
        family_rates = {
            family: {
                "passes": sum(bool(r.get("overall_pass")) for r in group if r["family"] == family),
                "trials": sum(1 for r in group if r["family"] == family),
                "pass_rate": _rate([r for r in group if r["family"] == family]),
            }
            for family in sorted({r["family"] for r in group})
        }
        fallback = (1 - p) * config.FAILURE_COST_USD
        variable = _mean(costs) or 0.0
        row = {
            "model": model,
            "provider": provider,
            "prompt_version": prompt_version,
            "backend": backend,
            "passing_trials": sum(bool(r.get("overall_pass")) for r in group),
            "total_trials": len(group),
            "measured_success_rate_P": p,
            "ordinary_passes": sum(bool(r.get("overall_pass")) for r in ordinary),
            "ordinary_trials": len(ordinary),
            "ordinary_pass_rate": _rate(ordinary),
            "negative_passes": sum(bool(r.get("overall_pass")) for r in negative),
            "negative_trials": len(negative),
            "negative_pass_rate": _rate(negative),
            "pass_rate_by_family_json": json.dumps(family_rates, sort_keys=True),
            "failed_negative_case_ids": ";".join(_failed_ids(negative)),
            "failed_negative_families": ";".join(sorted({r["family"] for r in negative if not r.get("overall_pass")})),
            "avg_tokens_in_per_run": _mean(tokens_in),
            "median_tokens_in_per_run": _median(tokens_in),
            "total_tokens_in": sum(tokens_in),
            "avg_tokens_out_per_run": _mean(tokens_out),
            "median_tokens_out_per_run": _median(tokens_out),
            "total_tokens_out": sum(tokens_out),
            "input_token_price_per_million": group[0].get("input_token_price_per_million"),
            "output_token_price_per_million": group[0].get("output_token_price_per_million"),
            "cached_input_price_per_million": group[0].get("cached_input_price_per_million"),
            "total_live_token_cost_usd": sum(costs),
            "avg_live_token_cost_per_run_usd": variable,
            "median_live_token_cost_per_run_usd": _median(costs),
            "failure_rate_1_minus_P": 1 - p,
            "failure_handling_cost_usd": config.FAILURE_COST_USD,
            "failure_cost_basis": "US$38/hour x 12 minutes",
            "expected_fallback_cost_per_task_usd": fallback,
            "variable_model_cost_per_task_usd": variable,
            "cost_to_serve_excluding_fixed_usd": variable + fallback,
            "fixed_monthly_usd": config.FIXED_MONTHLY_USD,
            "monthly_volume_claims": config.MONTHLY_VOLUME,
            "monthly_variable_model_cost_usd": variable * config.MONTHLY_VOLUME,
            "monthly_expected_fallback_cost_usd": fallback * config.MONTHLY_VOLUME,
            "monthly_all_in_cost_usd": "NOT_CALCULABLE_UNTIL_FIXED_MONTHLY_PROVIDED",
            "break_even_C_cheap_variable_cost": "NOT_YET_MEASURED",
            "break_even_E_comparison_cost_to_serve": "NOT_YET_MEASURED",
            "break_even_F_failure_cost": config.FAILURE_COST_USD,
            "break_even_success_rate": "NOT_YET_MEASURED; calculate as 1-(E-C)/F",
            "mean_turns": _mean(turns),
            "median_turns": _median(turns),
            "min_turns": min(turns) if turns else None,
            "max_turns": max(turns) if turns else None,
            "mean_seconds": _mean(seconds),
            "median_seconds": _median(seconds),
            "avg_observation_tokens_estimated": _mean(obs),
            "median_observation_tokens_estimated": _median(obs),
            "avg_target_tool_observation_tokens_estimated": _mean(target_obs),
            "median_target_tool_observation_tokens_estimated": _median(target_obs),
            "target_tool": config.TARGET_TOOL,
            "observation_measurement_note": "Estimated chars/4; provider does not meter local tool returns separately",
            "B_tool_block_tokens_before": "NOT_YET_MEASURED",
            "B_tool_block_tokens_after": "NOT_YET_MEASURED",
            "T_sequential_turns": "NOT_YET_MEASURED",
            "T_parallel_turns": _mean(turns),
            "T_sequential_input_tokens": "NOT_YET_MEASURED",
            "T_parallel_input_tokens": _mean(tokens_in),
            "T_sequential_cost_usd": "NOT_YET_MEASURED",
            "T_parallel_cost_usd": variable,
            "T_sequential_pass_rate": "NOT_YET_MEASURED",
            "T_parallel_pass_rate": p,
            "D_v1_target_observation_tokens": _mean(target_obs),
            "D_v2_target_observation_tokens": "NOT_YET_MEASURED",
        }
        output.append(row)
    return output


def write_d6(rows: list[dict], csv_path: Path, md_path: Path):
    data = d6_rows(rows)
    fields = list(data[0]) if data else ["model", "provider", "prompt_version"]
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)
    lines = ["# D6 Cost-to-Serve Handoff", "", "This file is generated from raw per-run results. Scripted rows are plumbing checks, not live measurements.", ""]
    for row in data:
        lines += [
            f"## {row['model']} / {row['prompt_version']} ({row['backend']})",
            "",
            f"- Success: {row['passing_trials']}/{row['total_trials']} = {row['measured_success_rate_P']:.2%}",
            f"- Ordinary: {row['ordinary_passes']}/{row['ordinary_trials']} = {row['ordinary_pass_rate']:.2%}" if row['ordinary_trials'] else "- Ordinary: no trials",
            f"- Negative: {row['negative_passes']}/{row['negative_trials']} = {row['negative_pass_rate']:.2%}" if row['negative_trials'] else "- Negative: no trials",
            f"- Tokens in/out: {row['total_tokens_in']:,} / {row['total_tokens_out']:,}; median per run {row['median_tokens_in_per_run']} / {row['median_tokens_out_per_run']}",
            f"- Variable model cost/run: US${row['avg_live_token_cost_per_run_usd']:.8f}; total US${row['total_live_token_cost_usd']:.6f}",
            f"- Expected fallback/task: (1 - {row['measured_success_rate_P']:.6f}) x US$7.60 = US${row['expected_fallback_cost_per_task_usd']:.6f}",
            f"- Cost-to-serve excluding fixed: US${row['cost_to_serve_excluding_fixed_usd']:.6f}/task",
            f"- Monthly volume: 8,000; variable US${row['monthly_variable_model_cost_usd']:.2f}; fallback US${row['monthly_expected_fallback_cost_usd']:.2f}",
            f"- Fixed monthly: {row['fixed_monthly_usd']}; monthly all-in is not calculable until supplied.",
            f"- Turns mean/median/min/max: {row['mean_turns']:.2f} / {row['median_turns']} / {row['min_turns']} / {row['max_turns']}",
            f"- Latency mean/median: {row['mean_seconds']:.3f}s / {row['median_seconds']:.3f}s",
            f"- Target tool `{row['target_tool']}` observation size: {row['avg_target_tool_observation_tokens_estimated']} estimated tokens/run (chars/4, not provider-metered).",
            "- B (tool-block before/after), sequential D2(c) results, V2 D, fixed monthly cost, and cross-model break-even E/C remain placeholders until those measurements arrive.",
            "",
        ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _failure_layer(row: dict) -> str:
    record = row.get("record") or {}
    if record.get("stopped_by") not in (None, "final_answer"):
        return "guardrail problem"
    reason = str(record.get("reason", ""))
    if record.get("parse_error") or "parseable JSON" in reason or "invalid move shape" in reason:
        return "prompt/reasoning problem"
    failures = row.get("code_check_failures") or []
    if row.get("actual_decision") != row.get("expected_decision"):
        return "prompt/reasoning problem"
    if any("trigger" in item or "missing" in item for item in failures):
        return "return-shape problem"
    if row.get("code_check_pass") and not row.get("judgement_check_pass"):
        return "prompt/reasoning problem (decision-record completeness)"
    return "prompt/reasoning problem"


def write_failure_analysis(rows: list[dict], path: Path):
    failed = [row for row in rows if not row.get("overall_pass")]
    lines = ["# V1 Failure Analysis", "", f"Failed trials: {len(failed)} of {len(rows)}.", "", "Likely layers are triage classifications, not automatic fixes. V1 remains frozen.", ""]
    for row in failed:
        lines += [
            f"## {row['case_id']} - trial {row['trial']}",
            "",
            f"- Expected: `{row.get('expected_decision')}`; trigger/missing: `{row.get('expected_trigger_missing')}`",
            f"- Actual: `{row.get('actual_decision')}`; trigger/missing: `{row.get('actual_trigger_missing')}`",
            f"- Code check: {'PASS' if row.get('code_check_pass') else 'FAIL'} - {row.get('code_check_failures')}",
            f"- Judgement check: {'PASS' if row.get('judgement_check_pass') else 'FAIL'} - {(row.get('judgement') or {}).get('reason')}",
            f"- Likely failure layer: **{_failure_layer(row)}**",
            "",
        ]
    if not failed:
        lines.append("No failed trials.\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_judgement_audit(rows: list[dict], csv_path: Path, md_path: Path):
    fields = [
        "run_id", "case_id", "trial", "criteria_count", "judge_model",
        "model_reported_verdict", "contract_verdict", "graded_by", "reason",
        "item_results_json",
    ]
    audit = []
    for row in rows:
        judgement = row.get("judgement") or {}
        audit.append({
            "run_id": row.get("run_id"),
            "case_id": row.get("case_id"),
            "trial": row.get("trial"),
            "criteria_count": len((row.get("expected") or {}).get("must_record", [])),
            "judge_model": judgement.get("judge_model"),
            "model_reported_verdict": judgement.get("model_reported_verdict"),
            "contract_verdict": row.get("judgement_check_pass"),
            "graded_by": judgement.get("graded_by"),
            "reason": judgement.get("reason"),
            "item_results_json": json.dumps(judgement.get("item_results") or [], ensure_ascii=False, sort_keys=True),
        })
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(audit)
    passed = sum(row["contract_verdict"] is True for row in audit)
    contradictory = sum(row["model_reported_verdict"] != row["contract_verdict"] for row in audit)
    md_path.write_text(
        "# Judgement Check Audit\n\n"
        f"All {len(audit)} trials required judgement because every answer-key row contains `must_record` criteria.\n\n"
        f"- Separate judge: `openai/gpt-4o-mini` through OpenRouter\n"
        f"- Judgement passes: {passed}/{len(audit)}\n"
        f"- Model-reported/item-contract disagreements: {contradictory}\n"
        "- Contract: exactly one item result per criterion, and every `met` value must be `true`.\n"
        "- Code checks remained separate and were not delegated to the judge.\n\n"
        "The CSV beside this file preserves every criterion result, the judge's original top-level verdict, the normalized contract verdict, and the judge's explanation.\n",
        encoding="utf-8",
    )


def generate_all(rows: list[dict], results_dir: Path):
    results_dir.mkdir(parents=True, exist_ok=True)
    write_summary(rows, results_dir / "v1_summary.csv")
    write_d6(rows, results_dir / "D6_COST_HANDOFF.csv", results_dir / "D6_COST_HANDOFF.md")
    write_failure_analysis(rows, results_dir / "V1_FAILURE_ANALYSIS.md")
    write_judgement_audit(rows, results_dir / "JUDGEMENT_AUDIT.csv", results_dir / "JUDGEMENT_AUDIT.md")
