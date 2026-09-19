#!/usr/bin/env python3
"""Create clean, runnable V1 and V2 evaluator snapshots without secrets/results."""
from __future__ import annotations

import shutil
import difflib
from pathlib import Path


PKG = Path(__file__).resolve().parents[1]
DEST = PKG.parent / "PE6201_A2_Final_Deliverables" / "code"
EXCLUDE_NAMES = {".env", ".DS_Store", "__pycache__", "results", "decision_logs"}
EXCLUDE_FILES = {"V1_CONFIG_SNAPSHOT.md", "V1_CONFIG_SNAPSHOT_PRE_RUN.md", "VALIDATION_REPORT.md", "PE6201_A2_DEMO.ipynb", "DEMO_RECORDING_GUIDE.md"}


def ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in EXCLUDE_NAMES or name in EXCLUDE_FILES or name.endswith(".pyc")}


def remove_v2_override(text: str) -> str:
    start = text.index("\nif config.PROMPT_VERSION == \"v2\":\n")
    end = text.index("\n\ndef call(problem, name, args):", start)
    return text[:start] + text[end:]


def make() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for version in ("V1", "V2"):
        target = DEST / version
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(PKG, target, ignore=ignore)

    v1_tools_path = DEST / "V1" / "tools.py"
    v1_tools = v1_tools_path.read_text(encoding="utf-8")
    v1_tools = v1_tools.replace(
        "    member = m\n    if config.PROMPT_VERSION == \"v2\":\n        member = {\"member_id\": m[\"member_id\"], \"policy_id\": m[\"policy_id\"]}\n    return {\"member\": member, \"policy\": p,\n",
        "    return {\"member\": m, \"policy\": p,\n",
    )
    v1_tools_path.write_text(remove_v2_override(v1_tools), encoding="utf-8")

    v2_tools_path = DEST / "V2" / "tools.py"
    v2_tools = v2_tools_path.read_text(encoding="utf-8")
    v2_tools = v2_tools.replace(
        "    member = m\n    if config.PROMPT_VERSION == \"v2\":\n        member = {\"member_id\": m[\"member_id\"], \"policy_id\": m[\"policy_id\"]}\n    return {\"member\": member, \"policy\": p,\n",
        "    member = {\"member_id\": m[\"member_id\"], \"policy_id\": m[\"policy_id\"]}\n    return {\"member\": member, \"policy\": p,\n",
    )
    v2_tools = v2_tools.replace("\nif config.PROMPT_VERSION == \"v2\":\n    # Reviewed V2:", "\n# Reviewed V2:")
    # Dedent the one descriptor assignment block by four spaces.
    block_start = v2_tools.index("\n# Reviewed V2:")
    block_end = v2_tools.index("\n\ndef call(problem, name, args):", block_start)
    before, block, after = v2_tools[:block_start], v2_tools[block_start:block_end], v2_tools[block_end:]
    lines = block.splitlines()
    lines = [line[4:] if line.startswith("    ") else line for line in lines]
    v2_tools_path.write_text(before + "\n".join(lines) + after, encoding="utf-8")

    v2_config = DEST / "V2" / "config.py"
    text = v2_config.read_text(encoding="utf-8").replace(
        'PROMPT_VERSION = os.environ.get("PROMPT_VERSION", "v1").strip().lower()',
        'PROMPT_VERSION = os.environ.get("PROMPT_VERSION", "v2").strip().lower()',
    )
    v2_config.write_text(text, encoding="utf-8")

    readme = """# {version} complete evaluator\n\nRun scripted verification:\n\n```bash\npython3 -m unittest discover -s tests -v\npython3 run_eval.py --backend scripted --prompt-version {lower}\n```\n\nRun live evaluation only after setting `OPENROUTER_API_KEY`:\n\n```bash\npython3 run_eval.py --backend live --model openai/gpt-4o-mini --prompt-version {lower} --judge live --judge-model anthropic/claude-haiku-4.5\n```\n\nThe package includes the fixtures, expected outcomes, guardrails, harness, graders, analytics and tests. It contains no API key and no old results.\n"""
    for version in ("V1", "V2"):
        (DEST / version / "README_VERSION.md").write_text(readme.format(version=version, lower=version.lower()), encoding="utf-8")

    patch_parts = []
    for filename in ("config.py", "tools.py"):
        a = (DEST / "V1" / filename).read_text(encoding="utf-8").splitlines(keepends=True)
        b = (DEST / "V2" / filename).read_text(encoding="utf-8").splitlines(keepends=True)
        patch_parts.extend(difflib.unified_diff(a, b, fromfile=f"V1/{filename}", tofile=f"V2/{filename}"))
    (DEST / "V1_to_V2.patch").write_text("".join(patch_parts), encoding="utf-8")

    explanation = """# V1 → V2 controlled code change\n\nThe runnable snapshots are identical except for:\n\n1. `config.py`: the separate V2 package defaults `PROMPT_VERSION` to `v2` (V1 defaults to `v1`). Model, temperature, turn cap, guardrails and prices are unchanged.\n2. `tools.py`: `lookup_policy` returns only `member_id` and `policy_id` in `member`, while preserving `policy` and `remaining`.\n3. `tools.py`: only the `lookup_policy` descriptor is rewritten to state inclusive policy dates, remaining-limit arithmetic, exact triggers, downstream dependency checks and final evidence recording.\n\nSee `V1_to_V2.patch` for the exact executable diff. Shared improvements that made V1 usable (structured final record requirements and recoverable unknown-tool handling) are present identically in both snapshots and therefore are not V2 treatment changes.\n"""
    (DEST / "V1_TO_V2_EXPLANATION.md").write_text(explanation, encoding="utf-8")

    print(f"Created {DEST / 'V1'} and {DEST / 'V2'}")


if __name__ == "__main__":
    make()
