#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
import prompt
import tools


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    prompt_text = prompt.build_system_prompt("A")
    names = sorted(tools.REGISTRY["A"])
    signatures = {name: f"{name}{inspect.signature(tools.REGISTRY['A'][name])}" for name in names}
    returns = {name: tools.DESCRIPTORS[name]["returns"] for name in names}
    data_hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT / "data_A").glob("*.json"))}
    data_hashes["expected_outcomes_A.json"] = sha(ROOT / "expected_outcomes_A.json")
    data_hashes["make_fixtures_A.py"] = sha(ROOT / "make_fixtures_A.py")
    code_hashes = {name: sha(ROOT / name) for name in ("agent.py", "backends.py", "config.py", "guardrails.py", "harness.py", "prompt.py", "tools.py")}
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False).stdout.strip() or "NOT_IN_GIT_REPOSITORY"
    except OSError:
        commit = "GIT_UNAVAILABLE"
    cfg = config.public_snapshot()
    lines = [
        "# V1 Configuration Snapshot",
        "",
        "> The model, prompt, tools, guardrails, fixtures and answer key were frozen before the formal live battery. Evaluation-only checkpoint/error handling and judgement-contract normalization were finalized after provider timeout and judge-consistency audits; no V1 behaviour or ground truth changed. No API secret is included.",
        "",
        "## Model and runtime",
        "",
    ]
    for key, value in cfg.items():
        lines.append(f"- {key}: `{value}`")
    lines += [
        f"- harness_git_commit: `{commit}`",
        "",
        "## Guardrails",
        "",
        f"- Step cap: {config.MAX_TURNS} tool-calling turns",
        f"- Budget ceiling: {config.MAX_TOKENS_PER_RUN} provider-metered input + output tokens",
        f"- Action de-duplication: canonical JSON arguments",
        f"- Autonomy: {config.AUTONOMY}; `issue_decision_letter` is the gated action",
        "",
        "## Exact V1 tool signatures",
        "",
        "```json",
        json.dumps(signatures, indent=2),
        "```",
        "",
        "## Exact V1 return shapes",
        "",
        "```json",
        json.dumps(returns, indent=2),
        "```",
        "",
        "## Exact V1 tool descriptors",
        "",
        "```json",
        json.dumps({name: tools.DESCRIPTORS[name] for name in names}, indent=2),
        "```",
        "",
        "## Exact V1 system prompt",
        "",
        "```text",
        prompt_text,
        "```",
        "",
        "## Evaluation-set and answer-key hashes (SHA-256)",
        "",
        "```json",
        json.dumps(data_hashes, indent=2),
        "```",
        "",
        "## Harness/code hashes (SHA-256)",
        "",
        "```json",
        json.dumps(code_hashes, indent=2),
        "```",
    ]
    (ROOT / "V1_CONFIG_SNAPSHOT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(ROOT / "V1_CONFIG_SNAPSHOT.md")


if __name__ == "__main__":
    main()
