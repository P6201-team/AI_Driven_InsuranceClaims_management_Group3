# PE6201 A2 — AI-Driven Insurance Claims Management

**Problem A: Health-insurance claim first response**  
**Team:** Group 3  
**Repository:** `P6201-team/AI_Driven_InsuranceClaims_management_Group3`

This repository contains the team's single-agent ReAct system, tool layer, guardrails, evaluation data and harness, live-model results, D7 failure evidence, and D6 cost analysis for PE6201 A2.

The system produces one of three first-response outcomes for a claim:

- `approve_in_principle`
- `request_document`
- `escalate`

The reproducible evaluation entry point in the current repository is **`V2/run_eval.py`**. The `V2/` package supports both the frozen V1 and V2 interfaces through `--prompt-version v1` and `--prompt-version v2`.

---

## Quick start — reproduce the scripted run

The scripted backend is deterministic, requires **no API key**, and makes **no network call**.

### Requirements

- Python **3.10+**
- Git
- No third-party Python package is required by the submitted runtime (`V2/requirements.txt` contains standard-library code only).

### 1. Clone the repository

```bash
git clone https://github.com/P6201-team/AI_Driven_InsuranceClaims_management_Group3.git
cd AI_Driven_InsuranceClaims_management_Group3
```

### 2. Validate the fixture data

```bash
python3 Evaluation_Data/check_my_data.py
```

A valid package ends with:

```text
Your data hangs together.
```

### 3. Enter the runnable evaluation package

```bash
cd V2
```

The evaluator needs to know where the shared Problem A fixture data lives.

**macOS / Linux**

```bash
export A2_DATA="../Evaluation_Data"
```

**Windows PowerShell**

```powershell
$env:A2_DATA = "../Evaluation_Data"
```

### 4. Run the regression/unit tests

```bash
python3 -m unittest discover -s tests -v
```

On Windows, if `python3` is not available, use:

```powershell
python -m unittest discover -s tests -v
```

### 5. Run the D3(b) guardrail checklist

```bash
python3 run_eval.py --guardrails
```

This exercises the executable guardrail checklist on the scripted backend and writes:

```text
V2/results/guardrail_results.json
```

The committed guardrail evidence used by the team is also available at:

```text
evaluation result combination/guardrails/GUARDRAIL_RESULTS.json
```

### 6. Run the full scripted V2 evaluation

From inside `V2/`:

```bash
python3 run_eval.py --backend scripted --prompt-version v2
```

This uses the final evaluation data in `../Evaluation_Data/` and writes new local outputs under:

```text
V2/results/
```

including:

```text
v2_scripted_raw_results.json
v2_scripted_raw_results.csv
v2_scripted_summary.csv
D6_SCRIPTED_HANDOFF.csv
D6_SCRIPTED_HANDOFF.md
```

These scripted results validate the end-to-end evaluation plumbing. They are **not** the team's live-model performance measurements.

### Optional: run one scripted case first

For a faster sanity check:

```bash
python3 run_eval.py --backend scripted --prompt-version v2 --case CLM-8888
```

---

## Reproduce V1 using the same evaluator

`V1/` is **not** a second standalone evaluator. In the current repository, the controlled V1/V2 behavior is selected from the complete `V2/` package.

From inside `V2/` with `A2_DATA` already set:

```bash
python3 run_eval.py --backend scripted --prompt-version v1
```

This keeps the evaluation pipeline fixed while selecting the V1 tool-interface behavior.

---

## Repository structure

```text
.
├── Evaluation_Data/
│   ├── README.md
│   ├── check_my_data.py
│   ├── make_fixtures_A.py
│   ├── expected_outcomes_A.json
│   ├── data_dictionary.json
│   └── data_A/
│
├── V1/
│   └── analytics.py
│
├── V2/                         # Complete runnable evaluation package
│   ├── agent.py
│   ├── tools.py
│   ├── prompt.py
│   ├── guardrails.py
│   ├── backends.py
│   ├── config.py
│   ├── harness.py
│   ├── result_io.py
│   ├── analytics.py
│   ├── run_eval.py
│   ├── requirements.txt
│   ├── README_EVAL.md
│   ├── README_VERSION.md
│   ├── tests/
│   └── scripts/
│
├── evaluation result combination/
│   ├── all_results.json
│   ├── all_runs_detailed.csv
│   ├── case_summary.csv
│   ├── model_summary.csv
│   ├── v1_v2_case_delta.csv
│   ├── live_runs/
│   │   ├── V1__GPT-4o_mini.json
│   │   ├── V2__DeepSeek_V3.1.json
│   │   ├── V2__GPT-4o_mini.json
│   │   ├── V2__Gemini_2.5_Flash-Lite.json
│   │   ├── V2__Mistral_Small_3.2_24B.json
│   │   └── V2__Qwen3_235B.json
│   ├── guardrails/
│   │   └── GUARDRAIL_RESULTS.json
│   └── d7/
│       ├── D7_FAILURE1_LOOP_CONTROL.csv
│       ├── D7_FAILURE1_LOOP_CONTROL.json
│       └── D7_TWO_REPRODUCED_FAILURES.md
│
├── agent.py                    # Root-level integration/source copy
├── backends.py
├── config.py
├── guardrails.py
├── prompt.py
├── result_io.py
├── tools.py
├── tests/                      # Root guardrail-test copy
├── scripts/
│   └── run_d7_failure1.py
│
├── model_summary.csv
├── cost_model.csv
├── PE6201_A2_Evaluation_Results.xlsx
└── PE6201_A2_V1_V2_Evaluation_Data.zip
```

The root-level Python files are retained as project/integration artefacts. Because the root does not contain the complete `harness.py` + `run_eval.py` evaluator pair, the commands in this README intentionally use the complete **`V2/`** package.

---

## Evaluation data

`Evaluation_Data/` contains the final Problem A fixture set and ground truth.

The current package contains:

- **40 evaluation claims**
- **15 instructor-supplied claims**
- **25 team-added claims**
- **10 non-approval / negative cases**

Key files:

| File | Purpose |
|---|---|
| `Evaluation_Data/make_fixtures_A.py` | Reproducible fixture generator |
| `Evaluation_Data/data_A/` | Claim, member, policy, hospital, procedure and related fixture tables |
| `Evaluation_Data/expected_outcomes_A.json` | Ground-truth outcomes used by the harness |
| `Evaluation_Data/check_my_data.py` | Data integrity checker |
| `Evaluation_Data/data_dictionary.json` | Field definitions and relationships |

If fixture data is regenerated or changed, run:

```bash
python3 Evaluation_Data/make_fixtures_A.py
python3 Evaluation_Data/check_my_data.py
```

Do not manually alter instructor-supplied records.

---

## Guardrails — D3

The active guardrail layer implements code-level controls for:

- step cap
- token-budget ceiling
- action de-duplication
- autonomy / irreversible-action gate

The executable D3(b) checklist is under:

```text
V2/tests/
```

with the main artefacts:

```text
guardrail_cases.json
guardrail_runner.py
test_guardrails.py
guardrail_case_mapping.md
```

Run it with:

```bash
cd V2
python3 run_eval.py --guardrails
```

The checklist includes hostile-request-text cases and records the wrong behaviour being tested, expected behavior, observed result, and pass/fail outcome.

---

## V1 → V2 controlled comparison — D2(b)

The controlled rewrite is implemented through the tool interface while keeping the same overall agent/evaluation framework.

Use the same evaluator and switch only the prompt/interface version:

```bash
# V1
python3 run_eval.py --backend scripted --prompt-version v1

# V2
python3 run_eval.py --backend scripted --prompt-version v2
```

The committed comparison evidence is available at:

```text
evaluation result combination/v1_v2_case_delta.csv
PE6201_A2_V1_V2_Evaluation_Data.zip
```

The scripted backend is used for deterministic plumbing checks. Formal performance comparisons reported by the team come from the frozen live runs.

---

## Live-model evaluation — D5

Live runs use OpenRouter-compatible model IDs. An API key is required **only** for live mode.

From inside `V2/`:

**macOS / Linux**

```bash
export A2_DATA="../Evaluation_Data"
export OPENROUTER_API_KEY="YOUR_KEY_HERE"

python3 run_eval.py \
  --backend live \
  --model openai/gpt-4o-mini \
  --prompt-version v2 \
  --member-id YOUR_MEMBER_ID
```

**Windows PowerShell**

```powershell
$env:A2_DATA = "../Evaluation_Data"
$env:OPENROUTER_API_KEY = "YOUR_KEY_HERE"

python run_eval.py --backend live --model openai/gpt-4o-mini --prompt-version v2 --member-id YOUR_MEMBER_ID
```

Do **not** commit `.env` files or API keys.

The evaluator uses a separate judge model for live grading. The evaluated model and judge model must be different.

The submitted raw live evidence is preserved under:

```text
evaluation result combination/live_runs/
```

Current committed model/version runs are:

| Version | Model |
|---|---|
| V1 | GPT-4o mini |
| V2 | GPT-4o mini |
| V2 | Gemini 2.5 Flash-Lite |
| V2 | Mistral Small 3.2 24B |
| V2 | DeepSeek V3.1 |
| V2 | Qwen3 235B |

---

## Consolidated evaluation evidence

The main consolidated result files are:

| File | Purpose |
|---|---|
| `evaluation result combination/all_results.json` | Combined raw evaluation result payload |
| `evaluation result combination/all_runs_detailed.csv` | Per-run detailed measurements |
| `evaluation result combination/case_summary.csv` | Case-level summary |
| `evaluation result combination/model_summary.csv` | Model/version summary |
| `evaluation result combination/v1_v2_case_delta.csv` | V1/V2 case-level comparison |
| `model_summary.csv` | Top-level model summary used by analysis/cost work |
| `PE6201_A2_Evaluation_Results.xlsx` | Final consolidated evaluation workbook |

The repository currently preserves six model/version result sets with the raw run evidence retained separately.

---

## D7 — reproduced failures

The submitted D7 evidence is stored at:

```text
evaluation result combination/d7/
```

The report contains:

1. **Loop-control failure:** working V2 minus action de-duplication, followed by restoration.
2. **Tool-interface failure:** working V2 minus the `lookup_policy` interface refinement, followed by restoration.

Primary evidence:

```text
D7_FAILURE1_LOOP_CONTROL.csv
D7_FAILURE1_LOOP_CONTROL.json
D7_TWO_REPRODUCED_FAILURES.md
```

The experiment source is retained at:

```text
V2/scripts/run_d7_failure1.py
```

The quick-start path above does not need to rerun D7; the required no-key reproducibility path for marking is the scripted evaluator and guardrail checklist.

---

## D6 — cost model

Top-level D6 artefacts include:

```text
cost_model.csv
model_summary.csv
V1/analytics.py
V2/analytics.py
PE6201_A2_Evaluation_Results.xlsx
```

The cost analysis is derived from measured model results and includes model-variable cost, expected fallback cost, monthly-volume calculations, sensitivity scenarios, and break-even fields.

Scripted-backend cost files generated during the quick-start run are **plumbing checks only** and should not be interpreted as live production-cost measurements.

---

## Output isolation and reproducibility

Each evaluation trial creates a fresh agent run. Raw per-run evidence is retained rather than only reporting averages.

For local experiments, generated outputs are written under `V2/results/`. The committed formal evidence remains under `evaluation result combination/` and the top-level result files.

To avoid confusing a local rerun with the frozen submitted evidence:

- do not overwrite files under `evaluation result combination/` unless intentionally regenerating the formal battery;
- use `V2/results/` for local scripted checks;
- keep API keys outside Git;
- keep the same fixtures, answer key, harness, tool interface, and parameters when making controlled model comparisons.

---

## Troubleshooting

### `A2 data not found`

Set `A2_DATA` before running the evaluator:

```bash
cd V2
export A2_DATA="../Evaluation_Data"
```

PowerShell:

```powershell
cd V2
$env:A2_DATA = "../Evaluation_Data"
```

### `Live backend requires OPENROUTER_API_KEY`

You selected `--backend live`. Either provide your own key locally or switch back to:

```bash
python3 run_eval.py --backend scripted --prompt-version v2
```

### Judge model equals evaluated model

The live evaluator forbids self-grading. Use a different `--judge-model` if the selected evaluated model matches the configured judge.

### Data integrity failure

Re-run:

```bash
python3 Evaluation_Data/check_my_data.py
```

and fix the fixture/link/label issue before trusting evaluation results.

---

## Contribution record

Team responsibilities and repository artefact mapping are documented separately in `CONTRIBUTIONS.md` for the final submission. GitHub upload history is supporting evidence only; collaborative integration, consolidation, and file movement may mean the uploader is not the sole author or owner of an artefact.

---

## Reproducibility summary

For the minimum no-key reproduction expected from a fresh clone:

```bash
git clone https://github.com/P6201-team/AI_Driven_InsuranceClaims_management_Group3.git
cd AI_Driven_InsuranceClaims_management_Group3

python3 Evaluation_Data/check_my_data.py

cd V2
export A2_DATA="../Evaluation_Data"

python3 -m unittest discover -s tests -v
python3 run_eval.py --guardrails
python3 run_eval.py --backend scripted --prompt-version v2
```

No API key or network access is required after the repository has been cloned.
