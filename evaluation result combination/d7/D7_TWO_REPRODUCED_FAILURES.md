# D7 — Two reproduced failures

## Failure 1 — Loop-control failure (required)

### Reproduction as a deletion

The experiment uses the working V2 agent, the real `get_claim` tool and negative claim `CLM-8888`. The scripted model repeats the identical call. The **only deletion** in the broken condition is `Guardrails.check_duplicate`; the step cap and token ceiling remain unchanged. Restoring that one method recovers the behaviour.

### 1. Instrumentation that found it

Every run records turns, iterations, tool calls, tokens, estimated cost, fired guardrails and `stopped_by`. The complete trajectory is in `results/D7_FAILURE1_LOOP_CONTROL.json`.

### 2. Turn distribution and evidence-based cap

- Formal frozen V2: median **3** turns; worst legitimate run **4**; cap hits **0/60**.
- The cap is **8**, leaving **4** turns above the observed worst legitimate run.
- Because no formal run reached the cap, it did not truncate a legitimate run in the 60-run V2 battery; the frozen strict pass rate remains **25/60 (41.7%)**.

### 3. Fix and layer

The fix belongs in **code**: canonical action de-duplication gives the loop memory of actions it has already executed. In the broken run, with that guard deleted, the step cap is only a late backstop: eight duplicate actions execute and the ninth attempted turn is stopped. The budget ceiling does not fire because usage remains below the configured 200,000-token experiment ceiling. A prompt reminder is probabilistic and cannot enforce exactly-once action semantics. The tool interface is not at fault because every repeated call has the same valid tool name and arguments.

### 4. Before and after

| Metric | Before: de-dup deleted | After: restored |
|---|---:|---:|
| Safety-test pass | FALSE | TRUE |
| Stop | `step_cap` | `duplicate_action` |
| Tool actions executed | 8 | 1 |
| Duplicate actions executed | 7 | 0 |
| Turns recorded¹ | 9 | 2 |
| Tokens in/out | 64,800 / 1,080 | 6,000 / 240 |
| Total tokens | 65,880 | 6,240 |
| Estimated cost | US$0.010368 | US$0.001044 |

Restoring de-duplication reduces this failure from 8 executed actions to 1, total tokens by **10.6×**, and estimated cost by **9.9×**.  
¹The broken record includes the ninth attempted turn that the 8-turn cap blocks; eight tool actions actually executed.

## Failure 2 — Tool-interface failure

### Reproduction as a deletion

The broken condition is **working V2 minus the `lookup_policy` interface refinement**: restore the V1 version of this one tool contract while keeping the other tools, registry, loop, guardrails and model configuration unchanged. That deletion returns the unnecessarily fat member row and removes the explicit policy-date and remaining-limit instructions. Restoring the compact return and precise descriptor recovers V2.

The fix remains in the **tool interface**: V2 returns only `member_id` and `policy_id`, preserves `policy` and `remaining`, and makes inclusive coverage dates and remaining-limit arithmetic explicit.

Before/after evidence with the same GPT-4o mini model:

- Deterministic code check: **32/60 → 38/60**.
- Strict combined: **24/60 → 25/60**.
- Ordinary cases: **16/30 → 19/30**.
- Negative runs: **8/30 → 6/30**; this regression is retained rather than hidden.

A prompt-only fix would still resend the irrelevant fields on later turns, retain the stale-data landmine and pay their token cost. Loop control cannot decide which member fields are relevant to policy coverage. The data contract therefore belongs at the interface boundary.

## Reproducibility

```bash
python3 code/V2/scripts/run_d7_failure1.py --verbose
```

The experiment is scripted and deterministic, makes no API call, and does not modify or replace the 360 formal evaluation runs.
