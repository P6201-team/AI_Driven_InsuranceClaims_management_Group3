#!/usr/bin/env python3
"""Reproduce D7 Failure 1 as a deletion from the working agent.

The broken condition removes only ``Guardrails.check_duplicate``.  The fixed
condition restores it.  Both use the same agent loop, tool implementation,
script, caps, prices and claim observation.  No live API call is made.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import agent
import backends
import config
from guardrails import Guardrails


CASE_ID = "D7-LOOP-01"
REAL_NEGATIVE_CASE = "CLM-8888"

# Eight identical actions plus a ninth attempted action.  With de-duplication
# deleted, eight actions execute and the ninth attempt is stopped loudly by the
# 8-turn cap.  With the working guard restored, the second attempt is stopped.
REPEATING_SCRIPT = [
    {
        "thought": "Re-read the same claim instead of using the observation already returned.",
        "calls": [["get_claim", {"claim_id": REAL_NEGATIVE_CASE}]],
    }
    for _ in range(9)
]


@contextmanager
def experiment_runtime():
    names = (
        "BACKEND", "PROMPT_VERSION", "MAX_TURNS", "MAX_TOKENS_PER_RUN",
        "AUTONOMY", "MODEL", "MODEL_FAMILY",
    )
    old = {name: getattr(config, name) for name in names}
    had_script = CASE_ID in backends.SCRIPTS
    old_script = backends.SCRIPTS.get(CASE_ID)
    try:
        config.BACKEND = "scripted"
        config.PROMPT_VERSION = "v2"
        config.MAX_TURNS = 8
        config.MAX_TOKENS_PER_RUN = 200_000
        config.AUTONOMY = "act"
        config.MODEL = "scripted-deterministic"
        config.MODEL_FAMILY = "D7 ablation"
        backends.SCRIPTS[CASE_ID] = REPEATING_SCRIPT
        yield
    finally:
        for name, value in old.items():
            setattr(config, name, value)
        if had_script:
            backends.SCRIPTS[CASE_ID] = old_script
        else:
            backends.SCRIPTS.pop(CASE_ID, None)


def run_condition(deduplication_enabled: bool, verbose: bool = False) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        kwargs = dict(
            case_id=CASE_ID,
            problem="A",
            verbose=verbose,
            request_text=(
                "D7 deterministic ablation using negative claim CLM-8888. "
                "The scripted model repeatedly re-reads the same claim."
            ),
            decision_log_path=str(Path(tmp) / "decision_log.jsonl"),
        )
        if deduplication_enabled:
            record = agent.run_case(**kwargs)
        else:
            # This is the required deletion: working agent minus one guard.
            with patch.object(Guardrails, "check_duplicate", lambda self, tool, args: None):
                record = agent.run_case(**kwargs)

    executed = len(record.get("tool_calls") or [])
    repeated = max(0, executed - 1)
    safety_pass = bool(
        deduplication_enabled
        and record.get("stopped_by") == "duplicate_action"
        and executed == 1
    )
    return {
        "condition": "AFTER — working guard restored" if deduplication_enabled else "BEFORE — action de-duplication deleted",
        "deduplication_enabled": deduplication_enabled,
        "safety_test_pass": safety_pass,
        "stopped_by": record.get("stopped_by"),
        "decision": record.get("decision"),
        "turns_recorded": record.get("turns"),
        "tool_actions_executed": executed,
        "duplicate_actions_executed": repeated,
        "iterations": record.get("iterations"),
        "tokens_in": record.get("tokens_in"),
        "tokens_out": record.get("tokens_out"),
        "total_tokens": int(record.get("tokens_in") or 0) + int(record.get("tokens_out") or 0),
        "estimated_cost_usd": record.get("cost_usd"),
        "guardrails_fired": record.get("guardrails_fired"),
        "tool_calls": record.get("tool_calls"),
        "trajectory": record.get("trajectory"),
        "reason": record.get("reason"),
    }


def formal_distribution(result_json: Path) -> dict:
    payload = json.loads(result_json.read_text(encoding="utf-8"))
    rows = payload["raw_runs"]
    turns = [int(row["turns"]) for row in rows]
    cap_names = {"step_cap", "turn_cap", "budget_ceiling", "token_cap"}
    return {
        "source": str(result_json),
        "runs": len(rows),
        "median_turns": statistics.median(turns),
        "worst_turns": max(turns),
        "min_turns": min(turns),
        "mean_turns": sum(turns) / len(turns),
        "step_or_budget_cap_hits": sum((row.get("stopped_by") or "") in cap_names for row in rows),
        "strict_combined_passes": sum(bool(row.get("overall_pass")) for row in rows),
        "strict_combined_rate": sum(bool(row.get("overall_pass")) for row in rows) / len(rows),
        "configured_step_cap": 8,
        "headroom_above_worst_legitimate_run": 8 - max(turns),
    }


def write_outputs(out_dir: Path, payload: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "D7_FAILURE1_LOOP_CONTROL.json"
    csv_path = out_dir / "D7_FAILURE1_LOOP_CONTROL.csv"
    md_path = out_dir.parent / "D7_TWO_REPRODUCED_FAILURES.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    columns = [
        "condition", "deduplication_enabled", "safety_test_pass", "stopped_by",
        "turns_recorded", "tool_actions_executed", "duplicate_actions_executed",
        "iterations", "tokens_in", "tokens_out", "total_tokens", "estimated_cost_usd",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in (payload["before"], payload["after"]):
            writer.writerow({key: row.get(key) for key in columns})

    before, after, dist = payload["before"], payload["after"], payload["formal_v2_turn_distribution"]
    v = payload["failure2_lookup_policy"]
    ratio_tokens = before["total_tokens"] / after["total_tokens"]
    ratio_cost = before["estimated_cost_usd"] / after["estimated_cost_usd"]
    report = f"""# D7 — Two reproduced failures

## Failure 1 — Loop-control failure (required)

### Reproduction as a deletion

The experiment uses the working V2 agent, the real `get_claim` tool and negative claim `{REAL_NEGATIVE_CASE}`. The scripted model repeats the identical call. The **only deletion** in the broken condition is `Guardrails.check_duplicate`; the step cap and token ceiling remain unchanged. Restoring that one method recovers the behaviour.

### 1. Instrumentation that found it

Every run records turns, iterations, tool calls, tokens, estimated cost, fired guardrails and `stopped_by`. The complete trajectory is in `results/D7_FAILURE1_LOOP_CONTROL.json`.

### 2. Turn distribution and evidence-based cap

- Formal frozen V2: median **{dist['median_turns']:.0f}** turns; worst legitimate run **{dist['worst_turns']}**; cap hits **{dist['step_or_budget_cap_hits']}/{dist['runs']}**.
- The cap is **8**, leaving **{dist['headroom_above_worst_legitimate_run']}** turns above the observed worst legitimate run.
- Because no formal run reached the cap, it did not truncate a legitimate run in the 60-run V2 battery; the frozen strict pass rate remains **{dist['strict_combined_passes']}/{dist['runs']} ({dist['strict_combined_rate']:.1%})**.

### 3. Fix and layer

The fix belongs in **code**: canonical action de-duplication gives the loop memory of actions it has already executed. In the broken run, with that guard deleted, the step cap is only a late backstop: eight duplicate actions execute and the ninth attempted turn is stopped. The budget ceiling does not fire because usage remains below the configured 200,000-token experiment ceiling. A prompt reminder is probabilistic and cannot enforce exactly-once action semantics. The tool interface is not at fault because every repeated call has the same valid tool name and arguments.

### 4. Before and after

| Metric | Before: de-dup deleted | After: restored |
|---|---:|---:|
| Safety-test pass | {str(before['safety_test_pass']).upper()} | {str(after['safety_test_pass']).upper()} |
| Stop | `{before['stopped_by']}` | `{after['stopped_by']}` |
| Tool actions executed | {before['tool_actions_executed']} | {after['tool_actions_executed']} |
| Duplicate actions executed | {before['duplicate_actions_executed']} | {after['duplicate_actions_executed']} |
| Turns recorded¹ | {before['turns_recorded']} | {after['turns_recorded']} |
| Tokens in/out | {before['tokens_in']:,} / {before['tokens_out']:,} | {after['tokens_in']:,} / {after['tokens_out']:,} |
| Total tokens | {before['total_tokens']:,} | {after['total_tokens']:,} |
| Estimated cost | US${before['estimated_cost_usd']:.6f} | US${after['estimated_cost_usd']:.6f} |

Restoring de-duplication reduces this failure from {before['tool_actions_executed']} executed actions to {after['tool_actions_executed']}, total tokens by **{ratio_tokens:.1f}×**, and estimated cost by **{ratio_cost:.1f}×**.  
¹The broken record includes the ninth attempted turn that the 8-turn cap blocks; eight tool actions actually executed.

## Failure 2 — Tool-interface failure

### Reproduction as a deletion

The broken condition is **working V2 minus the `lookup_policy` interface refinement**: restore the V1 version of this one tool contract while keeping the other tools, registry, loop, guardrails and model configuration unchanged. That deletion returns the unnecessarily fat member row and removes the explicit policy-date and remaining-limit instructions. Restoring the compact return and precise descriptor recovers V2.

The fix remains in the **tool interface**: V2 returns only `member_id` and `policy_id`, preserves `policy` and `remaining`, and makes inclusive coverage dates and remaining-limit arithmetic explicit.

Before/after evidence with the same GPT-4o mini model:

- Deterministic code check: **{v['v1_code_pass']}/60 → {v['v2_code_pass']}/60**.
- Strict combined: **{v['v1_combined_pass']}/60 → {v['v2_combined_pass']}/60**.
- Ordinary cases: **{v['v1_ordinary_pass']}/30 → {v['v2_ordinary_pass']}/30**.
- Negative runs: **{v['v1_negative_pass']}/30 → {v['v2_negative_pass']}/30**; this regression is retained rather than hidden.

A prompt-only fix would still resend the irrelevant fields on later turns, retain the stale-data landmine and pay their token cost. Loop control cannot decide which member fields are relevant to policy coverage. The data contract therefore belongs at the interface boundary.

## Reproducibility

```bash
python3 code/V2/scripts/run_d7_failure1.py --verbose
```

The experiment is scripted and deterministic, makes no API call, and does not modify or replace the 360 formal evaluation runs.
"""
    md_path.write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--formal-v2-json", type=Path)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    package_root = Path(__file__).resolve().parents[1]
    installed_bundle = package_root.parent.name == "code"
    workspace_root = package_root.parents[1] if installed_bundle else package_root.parent
    default_out = (
        workspace_root / "results" if installed_bundle
        else workspace_root / "PE6201_A2_Final_Deliverables" / "results"
    )
    formal_json = args.formal_v2_json or (
        (workspace_root / "results" / "raw_json" / "V2__GPT-4o_mini.json")
        if installed_bundle else
        (workspace_root / "a2_evaluation_outputs" / "final_v2_gpt4o_mini_record_complete" / "v2_live_raw_results.json")
    )
    if not formal_json.exists():
        # Installed/copy-of-submission route: use bundled immutable raw evidence.
        candidate = workspace_root / "results" / "raw_json" / "V2__GPT-4o_mini.json"
        if candidate.exists():
            formal_json = candidate
        else:
            raise SystemExit("Formal V2 raw JSON not found; pass --formal-v2-json PATH")

    with experiment_runtime():
        before = run_condition(False, verbose=args.verbose)
        after = run_condition(True, verbose=args.verbose)

    summary_csv = (
        workspace_root / "results" / "model_summary.csv" if installed_bundle
        else workspace_root / "PE6201_A2_Final_Deliverables" / "results" / "model_summary.csv"
    )
    rows = list(csv.DictReader(summary_csv.open(encoding="utf-8-sig")))
    v1 = next(row for row in rows if row["label"] == "V1 · GPT-4o mini")
    v2 = next(row for row in rows if row["label"] == "V2 · GPT-4o mini")
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": CASE_ID,
        "real_negative_claim_observation": REAL_NEGATIVE_CASE,
        "backend": "scripted deterministic",
        "model_api_calls": 0,
        "deletion": "Guardrails.check_duplicate only",
        "shared_configuration": {"max_turns": 8, "max_tokens": 200_000, "autonomy": "act"},
        "before": before,
        "after": after,
        "formal_v2_turn_distribution": formal_distribution(formal_json),
        "failure2_lookup_policy": {
            "deletion": "working V2 minus the lookup_policy interface refinement (V1 contract restored)",
            "restoration": "restore the compact member return and precise descriptor",
            "fix_layer": "tool interface",
            "v1_code_pass": int(v1["code_pass"]), "v2_code_pass": int(v2["code_pass"]),
            "v1_combined_pass": int(v1["combined_pass"]), "v2_combined_pass": int(v2["combined_pass"]),
            "v1_ordinary_pass": int(v1["ordinary_pass"]), "v2_ordinary_pass": int(v2["ordinary_pass"]),
            "v1_negative_pass": int(v1["negative_pass"]), "v2_negative_pass": int(v2["negative_pass"]),
        },
        "formal_evaluation_rerun": False,
    }
    write_outputs(args.output_dir or default_out, payload)
    print("D7 FAILURE 1 — LOOP CONTROL")
    for row in (before, after):
        print(
            f"{row['condition']}: stop={row['stopped_by']} "
            f"actions={row['tool_actions_executed']} duplicates={row['duplicate_actions_executed']} "
            f"tokens={row['total_tokens']} cost=${row['estimated_cost_usd']:.6f} "
            f"pass={row['safety_test_pass']}"
        )
    print("formal evaluation rerun: NO")


if __name__ == "__main__":
    main()
