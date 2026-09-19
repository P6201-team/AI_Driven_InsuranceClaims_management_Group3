#!/usr/bin/env python3
"""One-command portable evaluator. Defaults to the free scripted sanity run."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("scripted", "live"), default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--model-family", default=None)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--prompt-version", default=None)
    parser.add_argument("--member-id", default=None)
    parser.add_argument("--judge", choices=("scripted", "live", "skip"), default=None)
    parser.add_argument("--case", action="append", dest="cases")
    parser.add_argument("--max-runs", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--prompt", action="store_true")
    parser.add_argument("--guardrails", action="store_true")
    parser.add_argument("--output-dir", default=None)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.backend:
        os.environ["BACKEND"] = args.backend
    if args.model:
        os.environ["MODEL"] = args.model
    if args.model_family:
        os.environ["MODEL_FAMILY"] = args.model_family
    if args.judge_model:
        os.environ["JUDGE_MODEL"] = args.judge_model
    if args.prompt_version:
        os.environ["PROMPT_VERSION"] = args.prompt_version
    if args.member_id:
        os.environ["EVAL_MEMBER_ID"] = args.member_id

    import config
    config.validate()
    if config.BACKEND == "live":
        config.refresh_openrouter_pricing()
    if args.prompt:
        from agent import _prompt_module
        print(_prompt_module().build_system_prompt("A"))
        return 0
    if args.guardrails:
        from tests.guardrail_runner import run_checklist
        summary = run_checklist(output_path=str(config.HERE / "results" / "guardrail_results.json"), verbose=True)
        return 0 if summary["failed"] == 0 else 1

    from analytics import generate_all
    from harness import run_set, trial_plan
    from result_io import load_raw, write_raw

    results_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else config.HERE / "results"
    is_live = config.BACKEND == "live"
    stem = "v1_raw_results" if is_live and config.PROMPT_VERSION == "v1" else f"{config.PROMPT_VERSION}_{config.BACKEND}_raw_results"
    json_path = results_dir / f"{stem}.json"
    csv_path = results_dir / f"{stem}.csv"
    rows = load_raw(json_path) if args.resume and json_path.exists() else []
    completed = {(row["case_id"], int(row["trial"])) for row in rows}
    plan = [item for item in trial_plan(args.cases) if item not in completed]
    if args.max_runs is not None:
        plan = plan[: args.max_runs]
        allowed = set(plan)
        selected_cases = sorted({case for case, _trial in plan})
    else:
        allowed = None
        selected_cases = args.cases

    print(config.summary())
    print(f"data={config.data_root()}")
    print(f"planned new runs={len(plan)}; existing preserved={len(rows)}")

    def save(row):
        if allowed is not None and (row["case_id"], int(row["trial"])) not in allowed:
            return
        rows.append(row)
        write_raw(rows, json_path, csv_path, config.public_snapshot())
        status = "PASS" if row["overall_pass"] else "FAIL"
        print(f"{status:4} {row['case_id']} trial {row['trial']} turns={row['turns']} tokens={row['tokens_in']}/{row['tokens_out']} cost=${row['cost_usd']:.6f}", flush=True)

    if allowed is None:
        run_set(case_ids=selected_cases, judge_mode=args.judge, verbose=args.verbose, on_result=save, completed=completed)
    else:
        # Preserve arbitrary max-runs slicing without re-running excluded trials.
        from harness import load_key, run_trial
        key = load_key()
        mode = args.judge or ("scripted" if config.BACKEND == "scripted" else "live")
        for case_id, trial in plan:
            save(run_trial(case_id, trial, key[case_id], mode, verbose=args.verbose))

    write_raw(rows, json_path, csv_path, config.public_snapshot())
    if is_live and config.PROMPT_VERSION == "v1":
        generate_all(rows, results_dir)
    else:
        # Scripted summaries keep a distinct name and can never be mistaken for formal V1.
        from analytics import write_summary, write_d6
        write_summary(rows, results_dir / f"{config.PROMPT_VERSION}_{config.BACKEND}_summary.csv")
        write_d6(rows, results_dir / f"D6_{config.BACKEND.upper()}_HANDOFF.csv", results_dir / f"D6_{config.BACKEND.upper()}_HANDOFF.md")
    print(f"wrote {json_path.name} and {csv_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
