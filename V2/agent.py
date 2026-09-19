"""The team's frozen single-agent V1 ReAct loop with evaluation telemetry."""
from __future__ import annotations

import importlib
import json
import time
from datetime import datetime, timezone

import config
import prompt as prompt_v1
import tools
from backends import make_backend
from guardrails import Guardrails, GuardrailStop


def _prompt_module():
    # The controlled V1 -> V2 change is the lookup_policy descriptor and
    # return shape, not the routing prompt.  Both versions therefore use the
    # same frozen prompt module; tools.py selects the reviewed interface by
    # PROMPT_VERSION.
    if config.PROMPT_VERSION in {"v1", "v2"}:
        return prompt_v1
    try:
        return importlib.import_module(f"prompt_{config.PROMPT_VERSION}")
    except ModuleNotFoundError as exc:
        raise SystemExit(
            f"PROMPT_VERSION={config.PROMPT_VERSION!r} was requested, but "
            f"prompt_{config.PROMPT_VERSION}.py is not present. Keep V1 frozen; "
            "add the separately reviewed V2 prompt module when it is ready."
        ) from exc


def _estimated_tokens(value) -> int:
    """Transparent char/4 estimate for tool-return text only.

    Provider input/output counts are measured. OpenRouter does not separately
    meter local tool observations, so that field is explicitly estimated.
    """
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return max(1, (len(text) + 3) // 4)


def run_case(
    case_id,
    problem=None,
    approve=None,
    verbose=False,
    request_text=None,
    decision_log_path=None,
):
    problem = problem or config.PROBLEM
    started_monotonic = time.monotonic()
    started_at = datetime.now(timezone.utc)
    guards = Guardrails(config.MAX_TURNS, config.MAX_TOKENS_PER_RUN, config.AUTONOMY)
    prompt_module = _prompt_module()
    system_prompt = prompt_module.build_system_prompt(problem)
    backend = make_backend(
        case_id,
        tool_descriptors=[tools.DESCRIPTORS[name] for name in tools.REGISTRY[problem] if name in tools.DESCRIPTORS],
        system_prompt=system_prompt,
    )

    transcript = [{"role": "user", "content": request_text or f"Process claim case {case_id}."}]
    evidence = []
    tool_calls = []
    observations = []
    trajectory = []
    turns = 0
    iterations = 0
    tokens_in = tokens_out = cached_tokens = reasoning_tokens = 0
    provider_reported_cost = 0.0
    stopped_by = None

    if approve is None and backend.name == "scripted":
        approve = lambda _action, _payload: True
    if decision_log_path is None:
        decision_log_path = str(config.HERE / "decision_logs" / f"{case_id}.jsonl")

    try:
        while True:
            iterations += 1
            if iterations > config.MAX_TURNS + 2:
                raise GuardrailStop("step_cap", "loop did not terminate")

            move = backend.next_move(transcript)
            ti, to = backend.token_estimate(transcript)
            tokens_in += ti
            tokens_out += to
            usage = dict(getattr(backend, "last_usage", {}) or {})
            cached_tokens += int(usage.get("cached_tokens") or 0)
            reasoning_tokens += int(usage.get("reasoning_tokens") or 0)
            if usage.get("reported_cost_usd") is not None:
                provider_reported_cost += float(usage["reported_cost_usd"])
            guards.check_budget(tokens_in + tokens_out)
            trajectory.append({"iteration": iterations, "move": move, "usage": usage})

            if verbose:
                label = "conclude" if "final" in move else f"turn {turns + 1}"
                print(f"  {label:<9} · {str(move.get('thought', ''))[:88]}")

            if "final" in move:
                record = dict(move["final"])
                stopped_by = "final_answer"
                break

            turns += 1
            guards.check_turns(turns)
            calls = move.get("calls") or [(move["tool"], move["args"])]
            turn_observations = []
            for name, args in calls:
                guards.check_duplicate(name, args)
                if name == tools.GATED_ACTION.get(problem):
                    if not guards.gate(name, args, approve):
                        raise GuardrailStop("gate_held", f"{name} awaits human approval (autonomy={config.AUTONOMY})")
                try:
                    result = tools.call(problem, name, args)
                except (KeyError, TypeError) as exc:
                    # Preserve a paid run and expose the interface mistake to
                    # the model as an observation.  The error still appears in
                    # the trajectory/tool log and can therefore fail grading;
                    # it no longer aborts the whole resumable battery.
                    result = {
                        "tool_error": type(exc).__name__,
                        "message": str(exc),
                    }
                if name == tools.GATED_ACTION.get(problem):
                    guards.record_gated_action(
                        action_name=name,
                        payload=args,
                        evidence=evidence,
                        result=result,
                        case_id=case_id,
                        log_path=decision_log_path,
                    )
                evidence.append(name)
                call_row = {"turn": turns, "tool": name, "args": args}
                tool_calls.append(call_row)
                observation_row = {
                    **call_row,
                    "observation": result,
                    "observation_characters": len(json.dumps(result, ensure_ascii=False, default=str)),
                    "observation_tokens_estimated": _estimated_tokens(result),
                    "is_target_tool": name == config.TARGET_TOOL,
                }
                observations.append(observation_row)
                turn_observations.append({"tool": name, "args": args, "observation": result})
                if verbose:
                    print(f"       {name:<26} args={args!r} -> {_short(result)}")

            transcript.append({"role": "assistant", "content": str(move.get("thought", ""))})
            transcript.append({"role": "user", "content": repr(turn_observations)})

    except GuardrailStop as stop:
        stopped_by = stop.reason
        record = {
            "decision": "escalate",
            "reason": f"halted by the {stop.reason} guardrail - {stop.detail}",
        }

    noncached = max(0, tokens_in - cached_tokens)
    calculated_cost = (
        noncached / 1_000_000 * config.PRICE_IN
        + cached_tokens / 1_000_000 * config.CACHED_INPUT_PRICE
        + tokens_out / 1_000_000 * config.PRICE_OUT
    )
    ended_at = datetime.now(timezone.utc)
    record.update({
        "case_id": case_id,
        "evidence": evidence,
        "tool_calls": tool_calls,
        "tool_observations": observations,
        "turns": turns,
        "iterations": iterations,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cached_tokens": cached_tokens,
        "reasoning_tokens": reasoning_tokens,
        "observation_tokens_estimated": sum(row["observation_tokens_estimated"] for row in observations),
        "target_tool_observation_tokens_estimated": sum(row["observation_tokens_estimated"] for row in observations if row["is_target_tool"]),
        "observation_token_method": "UTF-8 JSON characters divided by 4; estimate, not provider-metered",
        "calculated_cost_usd": round(calculated_cost, 10),
        "provider_reported_cost_usd": round(provider_reported_cost, 10) if provider_reported_cost else None,
        "cost_usd": round(provider_reported_cost or calculated_cost, 10),
        "seconds": round(time.monotonic() - started_monotonic, 3),
        "guardrails_fired": guards.fired,
        "stopped_by": stopped_by,
        "backend": backend.name,
        "token_counts_measured": bool(getattr(backend, "usage_is_measured", False)),
        "trajectory": trajectory,
        "raw_model_responses": list(getattr(backend, "raw_responses", [])),
        "response_metadata": list(getattr(backend, "response_metadata", [])),
        "run_started_at": started_at.isoformat(),
        "run_finished_at": ended_at.isoformat(),
        "system_prompt_sha256": _sha256(system_prompt),
    })
    return record


def _sha256(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _short(value, n=96):
    rendered = repr(value)
    return rendered if len(rendered) <= n else rendered[: n - 1] + "…"
