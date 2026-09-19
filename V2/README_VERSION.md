# V2 complete evaluator

Run scripted verification:

```bash
python3 -m unittest discover -s tests -v
python3 run_eval.py --backend scripted --prompt-version v2
```

Run live evaluation only after setting `OPENROUTER_API_KEY`:

```bash
python3 run_eval.py --backend live --model openai/gpt-4o-mini --prompt-version v2 --judge live --judge-model anthropic/claude-haiku-4.5
```

The package includes the fixtures, expected outcomes, guardrails, harness, graders, analytics and tests. It contains no API key and no old results.
