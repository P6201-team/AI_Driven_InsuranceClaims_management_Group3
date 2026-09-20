# PE6201 A2 — Insurance Claims Agent (Group 3)

This repository contains a tool-using insurance claims agent, two versions of its policy lookup interface, an evaluation harness, guardrail checks, and archived live-model results. The instructions below refer to the actual layout of this submission.

## 1. Start here

For marking, first run the **offline verification** in Section 3. It needs no API key, network connection, or third-party Python packages. Then inspect the archived live results in Section 5. Live API execution is optional and incurs provider charges.

Verified on macOS with Python 3.9 on 20 September 2026, using an isolated copy of this submission. Use Python 3.9 or newer; other platforms were not independently tested.

| Component | Location |
|---|---|
| Runnable V1 baseline | Repository root: `run_eval.py`, `agent.py`, `tools.py`, etc. |
| Runnable V2 refinement | `V2/` |
| Shared evaluation inputs | `Evaluation_Data/` |
| Guardrail unit tests and checklist | `tests/` and `V2/tests/` |
| Archived live-model runs and summaries | `evaluation result combination/` |
| Consolidated workbook | `PE6201_A2_Evaluation_Results.xlsx` |
| Contributions | `CONTRIBUTIONS.md` |

**The `V1/` subfolder contains only an additional `analytics.py`; it is not the runnable baseline. Run V1 from the repository root.**

V2 refines `lookup_policy` (the function's actual name): the returned `member` object contains only `member_id` and `policy_id`, rather than the full V1 member row. The `policy` and `remaining` objects are retained. Its descriptor clarifies policy dates and remaining-limit interpretation. The main agent loop, other tools, and guardrails are shared in design. The default version label is also changed in V2's configuration.

**`--prompt-version` sets the version label; it does not swap tool implementations. To execute V2, change into `V2/`.**

## 2. Setup

Download and extract the repository, or clone it:

```bash
git clone https://github.com/P6201-team/AI_Driven_InsuranceClaims_management_Group3.git
cd AI_Driven_InsuranceClaims_management_Group3
```

If using a ZIP, instead open a terminal in the extracted folder containing this README and the root `run_eval.py`.

The following commands use macOS/Linux shell syntax. Start from a clean terminal without custom model, budget, autonomy, or version overrides. A local `.env` file may also change configuration; no `.env` or API key is needed for offline verification.

```bash
python3 --version
export A2_DATA="$PWD/Evaluation_Data"
export BACKEND=scripted
mkdir -p results V2/results
```

Keep this terminal open for the remaining steps. `A2_DATA` must be an **absolute path to `Evaluation_Data`**, which contains both `data_A/` and `expected_outcomes_A.json`. The absolute path continues to work after changing into `V2/`.

Windows PowerShell equivalent setup (use `python` in place of `python3` below):

```powershell
python --version
$env:A2_DATA = (Resolve-Path .\Evaluation_Data).Path
$env:BACKEND = "scripted"
New-Item -ItemType Directory -Force results, V2/results | Out-Null
```

## 3. Offline verification — recommended marking route

Run these commands from the repository root:

```bash
python3 Evaluation_Data/check_my_data.py
python3 -m unittest discover -s tests -v
python3 run_eval.py --backend scripted --guardrails
python3 run_eval.py --backend scripted --prompt-version v1 --output-dir results/offline_v1
```

Then run V2:

```bash
cd V2
python3 -m unittest discover -s tests -v
python3 run_eval.py --backend scripted --guardrails
python3 run_eval.py --backend scripted --prompt-version v2 --output-dir results/offline_v2
cd ..
```

Observed results with the submitted files:

| Check | V1 | V2 |
|---|---:|---:|
| Unit tests | 5/5 passed | 5/5 passed |
| Guardrail checklist | 12/12 passed | 12/12 passed |
| Scripted evaluation runs | 60/60 passed | 60/60 passed |

The shared fixture integrity check also passed. The checklist includes four hostile-request-text cases. The unit tests that refer to a live backend use mocks and do not contact a provider.

The evaluation battery contains 40 claims: 30 ordinary cases run once, and 10 negative cases run three times, giving 60 runs per version/model.

**Interpretation:** scripted evaluation verifies local execution, result generation, and deterministic behavior. The scripted backend uses canned actions and, for many cases, expected answers; its scripted judge is not an independent live-model judge. Therefore, 60/60 is a smoke-test result, not evidence of 100% real-model accuracy. Scripted token/cost fields are estimates, not actual API charges.

### Generated output

- V1: `results/offline_v1/v1_scripted_raw_results.json` and `.csv`, plus summary and D6 handoff files.
- V2: `V2/results/offline_v2/v2_scripted_raw_results.json` and `.csv`, plus summary and D6 handoff files.
- Guardrails: `results/guardrail_results.json` and `V2/results/guardrail_results.json`.
- Per-run decision logs are generated under the corresponding code directory.

These output directories keep new verification results separate from the archived live experiments. Check per-run `overall_pass` and the summary; the evaluator's process exit code alone does not mean all evaluation cases passed.

## 4. Reproduce the D7 loop-control demonstration

The bundled `scripts/run_d7_failure1.py` CLI still assumes the original author's directory layout when locating archived JSON and a summary CSV. Running it directly in this repository can fail. The following verified command calls its existing experiment functions without those legacy report-generation paths and without changing source code.

From the repository root, after Section 2 setup, run in a macOS/Linux shell:

```bash
cd V2
python3 - <<'PYCODE'
import json
from pathlib import Path
from scripts.run_d7_failure1 import experiment_runtime, run_condition

with experiment_runtime():
    results = {"before": run_condition(False), "after": run_condition(True)}

output = Path("results/d7_local.json")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(results, indent=2), encoding="utf-8")
fields = ["stopped_by", "tool_actions_executed", "duplicate_actions_executed",
          "total_tokens", "safety_test_pass"]
print(json.dumps({k: {f: v[f] for f in fields} for k, v in results.items()}, indent=2))
print("Saved:", output)
PYCODE
cd ..
```

On Windows, save the Python block between the `PYCODE` markers as `reproduce_d7.py` inside `V2/`, then run `python reproduce_d7.py` from `V2/` after the same environment setup.

Expected observations:

| Metric | Duplicate-action guard removed | Guard restored |
|---|---:|---:|
| Stop reason | `step_cap` | `duplicate_action` |
| Executed tool actions | 8 | 1 |
| Repeated actions | 7 | 0 |
| Estimated total tokens | 65,880 | 6,240 |
| Safety check | false | true |

This is an intentional broken-versus-working comparison. The `false` result in the first condition is expected. It uses the existing agent and guard implementation with a deterministic repeated-action script; no live model is called. This command reproduces Failure 1 only. The archived D7 report also discusses the policy-interface comparison using the saved V1/V2 live experiments.

## 5. Inspect the archived live results

The following are historical results included with the submission, not outputs of the offline checks above:

| Version / model | Strict passes | Rate |
|---|---:|---:|
| V1 / GPT-4o mini | 24/60 | 40.0% |
| V2 / GPT-4o mini | 25/60 | 41.7% |
| V2 / Gemini 2.5 Flash-Lite | 18/60 | 30.0% |
| V2 / Mistral Small 3.2 24B | 26/60 | 43.3% |
| V2 / DeepSeek V3.1 | 22/60 | 36.7% |
| V2 / Qwen3 235B | 31/60 | 51.7% |

Strict pass means the deterministic code check and the judge check both pass (`overall_pass`). The six archived files contain 360 runs in total. These counts were rechecked from the included JSON files.

Evidence locations under `evaluation result combination/`:

- `live_runs/`: six individual raw JSON files, including `V1__GPT-4o_mini.json` and `V2__GPT-4o_mini.json`.
- `all_results.json` and `all_runs_detailed.csv`: combined run records.
- `model_summary.csv`, `case_summary.csv`, and `v1_v2_case_delta.csv`: aggregate and case-level comparisons.
- `guardrails/GUARDRAIL_RESULTS.json`: archived guardrail checklist.
- `d7/`: archived loop-control output and `D7_TWO_REPRODUCED_FAILURES.md`.

The same-model V1-to-V2 strict result improves by one run (24 to 25 of 60). This is a small observed difference in this battery, not proof of a general improvement across models. The cost model retains a `NOT_YET_PROVIDED` fixed-monthly-cost input; it should not be presented as a complete production cost estimate.

## 6. Optional live execution

Live execution requires internet access, an OpenRouter API key, and sufficient credits. Current provider model availability and prices may differ from the archived experiment. This submission check did not rerun live APIs.

From the repository root, in the same shell with `A2_DATA` already set, supply your key locally as `OPENROUTER_API_KEY`. Do not place a real key in committed files. Then run a one-case V2 trial:

```bash
cd V2
python3 run_eval.py --backend live --prompt-version v2 \
  --model openai/gpt-4o-mini --model-family "OpenAI GPT-4o" \
  --judge live --judge-model anthropic/claude-haiku-4.5 \
  --case CLM-8888 --max-runs 1 --output-dir results/live_gpt4o_mini_trial
cd ..
```

To run the full 60-run battery, remove `--case` and `--max-runs` and choose a new output directory. For V1, execute the root `run_eval.py` with `--prompt-version v1`. Use a distinct output directory for every version/model experiment because result filenames do not encode the model name. Agent and live judge both make provider calls. Use the archived results for grading when paid reruns are unnecessary.

## 7. Troubleshooting and scope

- **“A2 data not found”**: set `A2_DATA` to the absolute shared `Evaluation_Data` path; do not point it directly at `data_A`.
- **Guardrail `FileNotFoundError`**: create `results` at the root and inside `V2` before running `--guardrails`. This option does not create its output parent directory and does not use `--output-dir`.
- **Missing V1 entry point**: the baseline entry point is at the repository root, not inside `V1/`.
- **Wrong V1/V2 behavior**: select the actual code directory; changing only `--prompt-version` does not change `lookup_policy`.
- **D7 missing archived files**: use the function-based reproduction in Section 4 or inspect the supplied D7 outputs. The original CLI's report assembly is not portable to this layout.
- **Unexpected offline results**: check inherited environment variables and local `.env` settings, particularly autonomy, turn/token limits, and version labels.

The main offline evaluation and guardrail checks are reproducible with the setup above. The known D7 CLI path limitation remains in source; this README provides a tested way to reproduce its core experiment. Archived live results show substantial remaining claim-decision failures. A runnable submission should not be interpreted as a production-ready claims adjudication system or a guarantee that every assignment rubric item has been satisfied.
