# PE6201 A2 Problem A - Portable Evaluation Package

This package runs the team's frozen V1 agent against the final reviewed 40-case Problem A set. It preserves all 60 raw trials: one trial for each case plus two additional trials for each of the 10 negative cases.

## What is frozen

- Evaluation fixtures and answer key: 40 reviewed cases (15 instructor-shipped, 25 team-added).
- V1 prompt: `prompt.py`.
- V1 tools, descriptors, signatures and return shapes: `tools.py`.
- Grading logic and trial schedule.
- Temperature 0, 4,096 maximum output tokens, reasoning disabled, 90-second timeout, two retries.

The submitted default is `BACKEND=scripted`, so a marker needs no key or network.

## Setup

```bash
cd evaluation_package
python3 -m pip install -r requirements.txt
cp .env.example .env
```

Add your own `OPENROUTER_API_KEY` to `.env`. Never share or commit `.env`.

## Free scripted sanity run

```bash
python3 check_my_data.py
python3 -m unittest discover -s tests -v
python3 run_eval.py --guardrails
python3 run_eval.py --backend scripted --prompt-version v1
```

The all-case scripted path is an explicitly labelled answer-key oracle. It validates fixture loading, case isolation, trial scheduling, grading, logging and output generation; it is not a live performance result.

## Formal V1 live run

Set only your key, member identifier and assigned model in `.env`, then run:

```bash
python3 run_eval.py \
  --backend live \
  --model google/gemini-2.5-flash-lite \
  --prompt-version v1 \
  --member-id YOUR_NAME_OR_ID
```

The live run checkpoints `results/v1_raw_results.json` and `.csv` after every trial. If interrupted, run the same command with `--resume`; already completed case/trial pairs are not billed again.

Every trial includes a judgement invocation using the separately configured `JUDGE_MODEL` (default `openai/gpt-4o-mini`). The judge must differ from the evaluated model. Agent serving tokens/cost and judgement tokens/cost are stored separately; D6 uses only agent serving cost. This model-as-judge method is transparent but remains a limitation compared with named human review.

## Later V2 controlled comparison

Do not edit `prompt.py`. When the team has approved V2, add the frozen module as `prompt_v2.py` with the same `build_system_prompt(problem)` interface. Then every teammate runs:

```bash
python3 run_eval.py --backend live --model ASSIGNED_MODEL_ID --prompt-version v2 --member-id YOUR_NAME_OR_ID
```

For the V2 model battery, keep the package, fixtures, answer key, V2 prompt, tools, return shapes, harness, trial schedule and comparable parameters unchanged. Change the OpenRouter model id and your own key only. OpenRouter pricing metadata is resolved automatically; provider-reported cost is also retained.

## Outputs

- `results/v1_raw_results.csv` and `.json`: all formal V1 trials, including full records and trajectories in JSON.
- `results/v1_summary.csv`: overall and family pass rates with trial counts.
- `results/V1_FAILURE_ANALYSIS.md`: each failed trial and likely failure layer.
- `results/D6_COST_HANDOFF.csv` and `.md`: success, tokens, cost, fallback, monthly, negative, turns, latency, B/T/D placeholders.
- `results/JUDGEMENT_AUDIT.csv` and `.md`: separate-judge identity and per-criterion verdicts.
- `V1_CONFIG_SNAPSHOT.md`: exact prompt/tools/config/hashes, without secrets.

## Demo notebook

Open `PE6201_A2_DEMO.ipynb` in Jupyter. Its default `DEMO_BACKEND = "scripted"` runs the curated negative case `CLM-8888` without network access, then reads the headline and cost metrics from the real formal live result files. See `DEMO_RECORDING_GUIDE.md` for the five-minute recording flow.

Observation/tool-return token counts are a transparent characters/4 estimate because the provider meters complete prompts but not local tool returns separately. Input/output counts are API-measured on live runs.

## Merge teammate model runs

Each teammate sends the raw JSON or CSV file. From this package run:

```bash
python3 scripts/merge_results.py member1.json member2.json member3.json member4.json member5.json
```

This writes `all_models_raw.csv`, `all_models_raw.json`, `model_battery_summary.csv`, and `D6_ALL_MODELS_HANDOFF.csv`. Raw runs are preserved.

## Values intentionally left open

- Fixed monthly cost is `NOT_YET_PROVIDED`, never assumed to be zero.
- D2(a) before/after tool-block size B.
- D2(c) sequential before-measurements for turns, input tokens, cost and correctness.
- V2 target-tool observation size D and V2/model-battery results.
- Cross-model break-even C/E inputs until comparison model results arrive.
