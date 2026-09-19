"""Frozen V1 scripted and OpenRouter live backends."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import config


# Guardrail tests add temporary entries here. The two genuine team scripts are
# retained; other evaluation cases use an explicitly labelled smoke-test oracle.
SCRIPTS = {
    "CLM-8842": [
        {"thought": "Fetch the claim first.", "calls": [["get_claim", {"claim_id": "CLM-8842"}]]},
        {"thought": "Run independent checks together.", "calls": [
            ["lookup_policy", {"member_id": "M-2214"}],
            ["check_coverage", {"code": "47120", "policy_id": "POL-3310"}],
            ["check_coverage", {"code": "31255", "policy_id": "POL-3310"}],
            ["check_coverage", {"code": "62480", "policy_id": "POL-3310"}],
            ["lookup_hospital", {"hospital_id": "H-114"}],
            ["check_duplicate_claim", {"member_id": "M-2214", "hospital_id": "H-114", "date_of_service": "2026-09-02", "lines": [{"code": "47120", "amount": 1400}, {"code": "62480", "amount": 780}, {"code": "31255", "amount": 300}]}],
        ]},
        {"thought": "Only 62480 needs pre-authorisation.", "calls": [["get_preauthorisation", {"member_id": "M-2214", "procedure_code": "62480", "date_of_service": "2026-09-02"}]]},
        {"thought": "Write the resolved decision through the gate.", "calls": [["issue_decision_letter", {"claim_id": "CLM-8842", "decision": "approve_in_principle", "lines_resolved": 3, "approved_total": 2180, "refused_total": 300}]]},
        {"thought": "Conclude.", "final": {"decision": "approve_in_principle", "reason": "3 lines resolved; 31255 refused under EX-14 cosmetic dermatology; PA-5521 cited for line 62480; approved_total 2180; refused_total 300."}},
    ],
    # Curated negative-case replay used by PE6201_A2_DEMO.ipynb.
    "CLM-8888": [
        {"thought": "Fetch the claim and its line items.", "calls": [["get_claim", {"claim_id": "CLM-8888"}]]},
        {"thought": "Run the independent policy, hospital, duplicate and per-line coverage checks together.", "calls": [
            ["lookup_policy", {"member_id": "M-6118"}],
            ["lookup_hospital", {"hospital_id": "H-114"}],
            ["check_coverage", {"code": "47120", "policy_id": "POL-7220"}],
            ["check_coverage", {"code": "62480", "policy_id": "POL-7220"}],
            ["check_coverage", {"code": "31255", "policy_id": "POL-7220"}],
            ["check_duplicate_claim", {"member_id": "M-6118", "hospital_id": "H-114", "date_of_service": "2026-09-08", "lines": [{"code": "47120", "amount": 900}, {"code": "62480", "amount": 1200}, {"code": "31255", "amount": 300}]}],
        ]},
        {"thought": "Line 62480 requires pre-authorisation; check for one valid on the service date.", "calls": [["get_preauthorisation", {"member_id": "M-6118", "procedure_code": "62480", "date_of_service": "2026-09-08"}]]},
        {"thought": "The specific evidence is missing, so request it.", "final": {
            "decision": "request_document",
            "missing": "pre-authorisation reference for line 62480, valid on 2026-09-08",
            "reason": "Request the pre-authorisation reference for line 62480 valid on 2026-09-08. Line 47120 is covered; line 31255 is refused under EX-14 cosmetic dermatology.",
        }},
    ],
}


def _oracle_final(case_id: str) -> dict:
    """Return a labelled smoke-test result; never used as a live result."""
    key_path = Path(config.data_root()) / "expected_outcomes_A.json"
    rows = json.loads(key_path.read_text(encoding="utf-8"))
    expected = next((row for row in rows if row["case_id"] == case_id), None)
    if expected is None:
        raise SystemExit(f"No scripted case or answer-key row for {case_id!r}.")
    final = {
        "decision": expected["expected_decision"],
        "reason": "; ".join(expected.get("must_record") or [expected.get("note") or "oracle smoke result"]),
        "scripted_oracle": True,
    }
    for field in ("trigger", "missing", "booked"):
        if field in expected:
            final[field] = expected[field]
    return {"thought": "Scripted oracle used only for harness sanity.", "final": final}


class ScriptedBackend:
    name = "scripted"
    usage_is_measured = False

    def __init__(self, case_id, *_args, **_kwargs):
        self.case_id = case_id
        self.steps = SCRIPTS.get(case_id) or [_oracle_final(case_id)]
        self.i = 0
        self.last_usage = {}
        self.raw_responses = []
        self.response_metadata = []

    def next_move(self, transcript):
        if self.i >= len(self.steps):
            return {"thought": "Script exhausted.", "final": {"decision": "escalate", "reason": "script ended without a conclusion"}}
        move = self.steps[self.i]
        self.i += 1
        return move

    def token_estimate(self, transcript):
        # Preserved scaffold estimate for deterministic guardrail tests only.
        self.last_usage = {
            "prompt_tokens": 1800 + 600 * len(transcript),
            "completion_tokens": 120,
            "cached_tokens": 0,
            "reasoning_tokens": 0,
            "reported_cost_usd": None,
        }
        return self.last_usage["prompt_tokens"], self.last_usage["completion_tokens"]


class LiveBackend:
    name = "live"
    usage_is_measured = True

    def __init__(self, case_id, tool_descriptors, system_prompt):
        self.case_id = case_id
        self.tools = tool_descriptors
        self.system_prompt = system_prompt
        self.last_usage = {}
        self.raw_responses = []
        self.response_metadata = []

    def next_move(self, transcript):
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend({"role": row["role"], "content": row["content"]} for row in transcript)
        raw, usage, metadata = _live_call(messages)
        self.last_usage = usage
        self.raw_responses.append(raw)
        self.response_metadata.append(metadata)
        return _parse_move(raw)

    def token_estimate(self, _transcript):
        return (
            int(self.last_usage.get("prompt_tokens") or 0),
            int(self.last_usage.get("completion_tokens") or 0),
        )


def _parse_move(text: str) -> dict:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.removeprefix("```json").removeprefix("```")
        candidate = candidate.removesuffix("```").strip()
    try:
        move = json.loads(candidate)
    except json.JSONDecodeError:
        return {
            "thought": f"unparseable model response: {candidate[:500]}",
            "final": {"decision": "escalate", "reason": "model did not return parseable JSON", "parse_error": True},
        }
    if not isinstance(move, dict) or not ("calls" in move or "tool" in move or "final" in move):
        return {
            "thought": "model returned JSON with no calls or final",
            "final": {"decision": "escalate", "reason": "model returned an invalid move shape", "parse_error": True},
        }
    return move


def _request_body(messages: list[dict], model: str | None = None) -> bytes:
    body = {
        "model": model or config.MODEL,
        "messages": messages,
        "temperature": config.TEMPERATURE,
        "max_tokens": config.MAX_OUTPUT_TOKENS,
        "response_format": {"type": "json_object"},
        "reasoning": {"enabled": False},
    }
    return json.dumps(body).encode("utf-8")


def _live_call(messages: list[dict], model: str | None = None):
    """The only vendor-aware function in the V1 runtime."""
    config.validate(live=True)
    request = urllib.request.Request(
        config.BASE_URL.rstrip("/") + "/chat/completions",
        data=_request_body(messages, model=model),
        headers={
            "Authorization": "Bearer " + config.API_KEY,
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ntu.edu.sg/",
            "X-Title": "PE6201 A2 V1 Evaluation",
        },
        method="POST",
    )
    last_error = None
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
                payload = json.load(response)
            usage_raw = payload.get("usage") or {}
            prompt_details = usage_raw.get("prompt_tokens_details") or {}
            completion_details = usage_raw.get("completion_tokens_details") or {}
            cost_details = usage_raw.get("cost_details") or {}
            usage = {
                "prompt_tokens": int(usage_raw.get("prompt_tokens") or 0),
                "completion_tokens": int(usage_raw.get("completion_tokens") or 0),
                "cached_tokens": int(prompt_details.get("cached_tokens") or 0),
                "reasoning_tokens": int(completion_details.get("reasoning_tokens") or 0),
                "reported_cost_usd": usage_raw.get("cost"),
                "upstream_inference_cost_usd": cost_details.get("upstream_inference_cost"),
            }
            metadata = {
                "request_id": payload.get("id"),
                "resolved_model": payload.get("model"),
                "resolved_provider": payload.get("provider"),
                "finish_reason": (payload.get("choices") or [{}])[0].get("finish_reason"),
            }
            raw = payload["choices"][0]["message"]["content"]
            return raw, usage, metadata
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, KeyError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt >= config.MAX_RETRIES:
                raise RuntimeError(f"Live API call failed after {attempt + 1} attempt(s): {exc}") from exc
            time.sleep(config.RETRY_BACKOFF_SECONDS * (2 ** attempt))
    raise RuntimeError(f"Live API call failed: {last_error}")


def make_backend(case_id, tool_descriptors=None, system_prompt=""):
    if config.BACKEND == "scripted":
        return ScriptedBackend(case_id, tool_descriptors, system_prompt)
    if config.BACKEND == "live":
        return LiveBackend(case_id, tool_descriptors or [], system_prompt)
    raise SystemExit(f"Unsupported BACKEND={config.BACKEND!r}")
