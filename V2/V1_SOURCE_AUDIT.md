# V1 Source Audit

This table resolves the supplied sources before integration. The later-dated D3(b) guardrail patch is treated as a team-authored extension to the team V1, while the instructor scaffold is reference material only.

| File | Role | Classification | Used in formal V1? | Reason |
|---|---|---|---|---|
| `V1 model/agent.py` | Team ReAct loop | Team V1 | Yes, with telemetry/guardrail integration only | Contains the team-added initial user message and real V1 loop behaviour. |
| `V1 model/prompt.py` | Exact V1 routing prompt and JSON answer instructions | Team V1 | Yes, byte-for-byte copy | It differs materially from the instructor prompt; changing it would optimise V1. |
| `V1 model/tools.py` | Problem A tool implementations, descriptors, signatures and return shapes | Team V1 | Yes, byte-for-byte copy | These are the team's actual ACI and must not be replaced by scaffold defaults. |
| `V1 model/backends.py` | Scripted/OpenRouter backend | Team V1 | Yes, with interface-only changes | OpenRouter route is retained; usage, retries and external configuration were added for valid measurement. |
| `V1 model/config.py` | Model, backend, limits and pricing | Team V1 | Yes, externalised | Original live route was OpenRouter with `openai/gpt-4o-mini`; the backend has no model-specific dependency, so the requested `google/gemini-2.5-flash-lite` is safe without changing V1 behaviour. |
| `V1 model/guardrails.py` | Step, token, de-duplication and autonomy guards | Team V1 | Superseded by later team patch | The supplied guardrail patch fixes canonical nested arguments and logs gated actions without changing business routing. |
| `Add guardrail checklist and guardrail tests/agent.py` | Loop integration for D3(b) | Evaluation/guardrail integration | Yes | Latest team-supplied guardrail integration; preserves the V1 prompt/tools. |
| `Add guardrail checklist and guardrail tests/backends.py` | Provider usage capture | Evaluation infrastructure | Yes | Captures API-reported token counts required by D6. |
| `Add guardrail checklist and guardrail tests/guardrails.py` | Hardened guards and structured gate log | Team guardrail extension | Yes | Latest team guardrail implementation. |
| `Add guardrail checklist and guardrail tests/tests/*` | 12-case scripted checklist | Evaluation infrastructure | Yes, as separate scripted tests | D3(b) is required to run free and deterministically. |
| `PE6201_A2_Evaluation_Data/make_fixtures_A.py` | Final reproducible fixtures | Final evaluation data | Yes | Reviewed 40-case generator; hashes match the workspace copy. |
| `PE6201_A2_Evaluation_Data/data_A/*` | Final Problem A fixtures | Final evaluation data | Yes | 40 selected cases; no reserve cases. |
| `PE6201_A2_Evaluation_Data/expected_outcomes_A.json` | Final ground truth | Final evaluation data | Yes | 40 reviewed labels; never derived from model output. |
| `PE6201_A2_Evaluation_Data/check_my_data.py` | Instructor integrity checker | Evaluation infrastructure | Yes | Confirms shipped-row integrity and referential consistency. |
| `A2_scaffold/*.py` | Starter architecture and examples | Instructor scaffold | No | Used only to understand required structure; not substituted for team V1. |
| Assignment PDFs | Requirements and source priority | Instructor requirements | Yes, as specification | Latest document update controls trial arithmetic and scripted/live split. |

Formal V1 is therefore: **team `prompt.py` + team `tools.py` + team loop/backend behaviour + latest supplied team guardrails + final reviewed 40-case fixtures/key + new evaluation-only telemetry and reporting**.
