"""Runtime configuration for the portable PE6201 Problem A evaluator.

All values that teammates are expected to change are environment variables.
The committed default remains the free, deterministic scripted backend.
"""
from __future__ import annotations

import os
from pathlib import Path


HERE = Path(__file__).resolve().parent


def _load_dotenv() -> None:
    """Load a local .env without adding a runtime dependency."""
    path = HERE / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()

PROBLEM = "A"
BACKEND = os.environ.get("BACKEND", "scripted").strip().lower()
PROVIDER = os.environ.get("LLM_PROVIDER", "openrouter").strip().lower()
MODEL = os.environ.get("MODEL", "openai/gpt-4o-mini").strip()
MODEL_FAMILY = os.environ.get("MODEL_FAMILY", "OpenAI GPT-4o").strip()
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "anthropic/claude-haiku-4.5").strip()
BASE_URL = os.environ.get("BASE_URL", "https://openrouter.ai/api/v1").strip()
API_KEY_ENV = os.environ.get("API_KEY_ENV", "OPENROUTER_API_KEY").strip()
API_KEY = os.environ.get(API_KEY_ENV, "")

PROMPT_VERSION = os.environ.get("PROMPT_VERSION", "v2").strip().lower()
TEMPERATURE = float(os.environ.get("TEMPERATURE", "0"))
MAX_OUTPUT_TOKENS = int(os.environ.get("MAX_OUTPUT_TOKENS", "1200"))
REASONING_SETTING = os.environ.get("REASONING_SETTING", "disabled").strip().lower()
TIMEOUT_SECONDS = int(os.environ.get("TIMEOUT_SECONDS", "90"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "2"))
RETRY_BACKOFF_SECONDS = float(os.environ.get("RETRY_BACKOFF_SECONDS", "1"))

MAX_TURNS = int(os.environ.get("MAX_TURNS", "8"))
MAX_TOKENS_PER_RUN = int(os.environ.get("MAX_TOKENS_PER_RUN", "60000"))
AUTONOMY = os.environ.get("AUTONOMY", "confirm").strip().lower()
TARGET_TOOL = os.environ.get("TARGET_TOOL", "check_coverage").strip()

# USD per one million tokens. These are list-price costing inputs, not secrets.
PRICE_IN = float(os.environ.get("INPUT_PRICE_PER_MILLION", "0.15"))
PRICE_OUT = float(os.environ.get("OUTPUT_PRICE_PER_MILLION", "0.60"))
CACHED_INPUT_PRICE = float(os.environ.get("CACHED_INPUT_PRICE_PER_MILLION", "0.075"))
PRICE_SOURCE = os.environ.get(
    "PRICE_SOURCE",
    "https://openrouter.ai/openai/gpt-4o-mini/pricing",
).strip()
PRICE_AS_OF = os.environ.get("PRICE_AS_OF", "2026-09-18").strip()
PRICE_RESOLUTION = os.environ.get("PRICE_RESOLUTION", "environment/default").strip()

MONTHLY_VOLUME = 8000
FAILURE_COST_USD = 7.60
FIXED_MONTHLY_USD = os.environ.get("FIXED_MONTHLY_USD", "NOT_YET_PROVIDED")
MEMBER_ID = os.environ.get("EVAL_MEMBER_ID", "NOT_PROVIDED").strip()


def data_root() -> str:
    configured = os.environ.get("A2_DATA", "").strip()
    candidate = Path(configured).expanduser().resolve() if configured else HERE
    if (candidate / "data_A").is_dir() and (candidate / "expected_outcomes_A.json").is_file():
        return str(candidate)
    raise SystemExit(
        "A2 data not found. Set A2_DATA to a folder containing data_A/ "
        "and expected_outcomes_A.json."
    )


def validate(live: bool | None = None) -> None:
    is_live = BACKEND == "live" if live is None else live
    if BACKEND not in {"scripted", "live"}:
        raise SystemExit("BACKEND must be 'scripted' or 'live'.")
    if PROVIDER != "openrouter":
        raise SystemExit(
            "This frozen V1 backend is OpenRouter-compatible. Set "
            "LLM_PROVIDER=openrouter and use an OpenRouter model id."
        )
    if is_live and not API_KEY:
        raise SystemExit(
            f"Live backend requires {API_KEY_ENV}. Copy .env.example to .env "
            "and add your own key."
        )
    if AUTONOMY not in {"suggest", "confirm", "act"}:
        raise SystemExit("AUTONOMY must be suggest, confirm, or act.")
    if REASONING_SETTING not in {"disabled", "none", "off"}:
        raise SystemExit(
            "Formal V1 is frozen with reasoning disabled. Do not change "
            "REASONING_SETTING inside a controlled comparison."
        )


def refresh_openrouter_pricing() -> None:
    """Resolve the selected model's current list prices without exposing a key."""
    global PRICE_IN, PRICE_OUT, CACHED_INPUT_PRICE, PRICE_SOURCE, PRICE_AS_OF, PRICE_RESOLUTION
    if PROVIDER != "openrouter":
        return
    import json
    import urllib.request
    from datetime import date

    try:
        request = urllib.request.Request("https://openrouter.ai/api/v1/models")
        with urllib.request.urlopen(request, timeout=min(TIMEOUT_SECONDS, 30)) as response:
            models = json.load(response).get("data", [])
        item = next(model for model in models if model.get("id") == MODEL)
        pricing = item.get("pricing") or {}
        PRICE_IN = float(pricing["prompt"]) * 1_000_000
        PRICE_OUT = float(pricing["completion"]) * 1_000_000
        CACHED_INPUT_PRICE = float(pricing.get("input_cache_read") or PRICE_IN / 1_000_000) * 1_000_000
        PRICE_SOURCE = f"https://openrouter.ai/{MODEL}/pricing"
        PRICE_AS_OF = date.today().isoformat()
        PRICE_RESOLUTION = "OpenRouter /api/v1/models"
    except Exception as exc:
        PRICE_RESOLUTION = f"fallback to environment/default; automatic lookup failed: {type(exc).__name__}"


def summary() -> str:
    model = MODEL if BACKEND == "live" else "(scripted oracle; no live model)"
    return (
        f"BACKEND={BACKEND} | PROBLEM=A | provider={PROVIDER} | model={model} | "
        f"prompt={PROMPT_VERSION} | temperature={TEMPERATURE:g} | "
        f"max_output_tokens={MAX_OUTPUT_TOKENS} | reasoning={REASONING_SETTING} | "
        f"cap={MAX_TURNS} turns | autonomy={AUTONOMY}"
    )


def public_snapshot() -> dict:
    """Configuration safe to save in result files (never includes the key)."""
    return {
        "problem": PROBLEM,
        "backend": BACKEND,
        "provider": PROVIDER,
        "model": MODEL,
        "model_family": MODEL_FAMILY,
        "judge_model": JUDGE_MODEL,
        "base_url": BASE_URL,
        "api_key_env": API_KEY_ENV,
        "prompt_version": PROMPT_VERSION,
        "temperature": TEMPERATURE,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "reasoning_setting": REASONING_SETTING,
        "timeout_seconds": TIMEOUT_SECONDS,
        "max_retries": MAX_RETRIES,
        "retry_backoff_seconds": RETRY_BACKOFF_SECONDS,
        "max_turns": MAX_TURNS,
        "max_tokens_per_run": MAX_TOKENS_PER_RUN,
        "autonomy": AUTONOMY,
        "target_tool": TARGET_TOOL,
        "input_price_per_million": PRICE_IN,
        "output_price_per_million": PRICE_OUT,
        "cached_input_price_per_million": CACHED_INPUT_PRICE,
        "price_source": PRICE_SOURCE,
        "price_as_of": PRICE_AS_OF,
        "price_resolution": PRICE_RESOLUTION,
        "member_id": MEMBER_ID,
    }
