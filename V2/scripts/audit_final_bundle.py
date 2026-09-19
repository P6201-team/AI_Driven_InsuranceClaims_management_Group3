#!/usr/bin/env python3
"""Three independent compliance audits for the PE6201 A2 final bundle."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "evaluation_package"
OUT = ROOT / "PE6201_A2_Final_Deliverables"
SOURCE_DATA = Path("/Users/wendys/Desktop/01-A2/Evaluation_Data")

RESULT_FILES = [
    ROOT / "a2_evaluation_outputs/final_v1_gpt4o_mini/v1_raw_results.json",
    ROOT / "a2_evaluation_outputs/final_v2_gpt4o_mini_record_complete/v2_live_raw_results.json",
    ROOT / "a2_evaluation_outputs/battery_v2_gemini_2_5_flash_lite/v2_live_raw_results.json",
    ROOT / "a2_evaluation_outputs/battery_v2_mistral_small_3_2_24b/v2_live_raw_results.json",
    ROOT / "a2_evaluation_outputs/battery_v2_deepseek_chat_v3_1/v2_live_raw_results.json",
    ROOT / "a2_evaluation_outputs/battery_v2_qwen3_235b_a22b_2507/v2_live_raw_results.json",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(condition: bool, message: str) -> str:
    if not condition:
        raise AssertionError(message)
    return message


def pass_one(payloads: list[dict]) -> list[str]:
    notes = []
    for payload in payloads:
        runs = payload["raw_runs"]
        notes.append(check(len(runs) == 60, f"{payload['config']['model']}: 60 planned runs present"))
        notes.append(check(len({r['case_id'] for r in runs}) == 40, f"{payload['config']['model']}: 40 unique cases present"))
        notes.append(check(sum(not r['negative_case'] for r in runs) == 30, f"{payload['config']['model']}: 30 ordinary runs"))
        notes.append(check(sum(r['negative_case'] for r in runs) == 30, f"{payload['config']['model']}: 10 negative cases ×3 = 30 runs"))
    v1, v2 = payloads[0], payloads[1]
    notes.append(check(v1["config"]["model"] == v2["config"]["model"] == "openai/gpt-4o-mini", "V1 and V2 use only openai/gpt-4o-mini for the controlled comparison"))
    notes.append(check(sum(r["overall_pass"] for r in v2["raw_runs"]) > sum(r["overall_pass"] for r in v1["raw_runs"]), "V2 strict combined pass count is higher than V1"))
    v2_models = {p["config"]["model"] for p in payloads[1:]}
    notes.append(check(len(v2_models) == 5, "V2 evaluated on GPT-4o mini plus four additional model families"))
    notes.append(check("anthropic/claude-haiku-4.5" not in v2_models and "qwen/qwen3-235b-a22b-2507" in v2_models, "Failed Claude agent group is replaced by Qwen3 235B; no Claude agent remains"))
    prices = {float(p["config"]["input_price_per_million"]) for p in payloads[1:]}
    notes.append(check(len(prices) >= 2, "Selected models span at least two price tiers"))
    guardrail_cases = json.loads((PKG / "tests/guardrail_cases.json").read_text(encoding="utf-8"))
    notes.append(check(len(guardrail_cases) >= 10, f"Scripted guardrail checklist has {len(guardrail_cases)} cases (requirement ≥10)"))
    return notes


def pass_two() -> list[str]:
    notes = []
    v1 = OUT / "code/V1"
    v2 = OUT / "code/V2"
    files1 = {p.relative_to(v1) for p in v1.rglob("*") if p.is_file()}
    files2 = {p.relative_to(v2) for p in v2.rglob("*") if p.is_file()}
    notes.append(check(files1 == files2, "V1 and V2 code snapshots contain the same file set"))
    different = sorted(str(rel) for rel in files1 if sha(v1 / rel) != sha(v2 / rel))
    notes.append(check(different == ["README_VERSION.md", "config.py", "tools.py"], f"Only version README, config default, and tools.py differ: {different}"))
    notes.append(check(sha(v1 / "prompt.py") == sha(v2 / "prompt.py"), "Shared prompt.py is byte-identical"))
    notes.append(check(sha(v1 / "agent.py") == sha(v2 / "agent.py"), "Loop/agent.py is byte-identical"))
    notes.append(check(sha(v1 / "guardrails.py") == sha(v2 / "guardrails.py"), "Guardrails are byte-identical"))
    notes.append(check(sha(v1 / "backends.py") == sha(v2 / "backends.py"), "Backend/model invocation architecture is byte-identical"))
    tools2 = (v2 / "tools.py").read_text(encoding="utf-8")
    notes.append(check('member = {"member_id": m["member_id"], "policy_id": m["policy_id"]}' in tools2, "V2 member return contains only member_id and policy_id"))
    notes.append(check('"policy": p' in tools2 and '"remaining": p["annual_limit"] - p["used_to_date"]' in tools2, "V2 preserves policy and remaining structure"))
    notes.append(check("BOTH endpoints are included" in tools2 and "remaining, not annual_limit" in tools2, "V2 descriptor explicitly states inclusive dates and remaining-limit rule"))
    return notes


def pass_three(payloads: list[dict]) -> list[str]:
    notes = []
    source_files = ["data_A/hospitals.json", "data_A/policies.json", "data_A/procedures.json", "data_A/members.json", "data_A/required_documents.json", "data_A/preauthorisations.json", "data_A/decided_claims.json", "data_A/claims.json", "data_dictionary.json", "expected_outcomes_A.json"]
    for rel in source_files:
        notes.append(check(sha(SOURCE_DATA / rel) == sha(PKG / rel), f"Source data hash matches: {rel}"))
    for payload in payloads:
        runs = payload["raw_runs"]
        notes.append(check(len({r["run_id"] for r in runs}) == len(runs), f"{payload['config']['model']}: run IDs are unique"))
        notes.append(check(all(r.get("token_counts_measured") for r in runs), f"{payload['config']['model']}: provider token counts measured for all runs"))
        notes.append(check(all(float(r.get("cost_usd") or 0) >= 0 for r in runs), f"{payload['config']['model']}: all agent costs are non-negative"))
        notes.append(check(all(r.get("record") and "trajectory" in r["record"] for r in runs), f"{payload['config']['model']}: every run preserves detailed trajectory"))
    combined = json.loads((OUT / "results/all_results.json").read_text(encoding="utf-8"))
    notes.append(check(len(combined["runs"]) == 360, "Consolidated detail contains all 360 runs"))
    notebook = json.loads((OUT / "PE6201_A2_Evaluation_Demo.ipynb").read_text(encoding="utf-8"))
    notes.append(check(notebook.get("nbformat") == 4 and len(notebook.get("cells", [])) >= 10, "Recording notebook is valid nbformat 4 and has ≥10 cells"))
    for index, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") == "code":
            compile("".join(cell.get("source", [])), f"notebook-cell-{index}", "exec")
    notes.append("All notebook code cells pass Python syntax compilation")
    workbook = OUT / "PE6201_A2_Evaluation_Results.xlsx"
    notes.append(check(workbook.exists() and workbook.stat().st_size > 50_000, "Editable Excel workbook exists and is non-empty"))
    with zipfile.ZipFile(workbook) as archive:
        workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
    notes.append(check('name="D7 Failures"' in workbook_xml, "Excel workbook includes the D7 Failures evidence sheet"))
    d7 = json.loads((OUT / "results/D7_FAILURE1_LOOP_CONTROL.json").read_text(encoding="utf-8"))
    before, after = d7["before"], d7["after"]
    notes.append(check(d7["formal_evaluation_rerun"] is False, "D7 is isolated targeted evidence; formal 360-run evaluation was not rerun"))
    notes.append(check(before["stopped_by"] == "step_cap" and before["tool_actions_executed"] == 8 and before["duplicate_actions_executed"] == 7 and before["safety_test_pass"] is False, "D7 before condition reproduces loop failure and is caught only by the unchanged step cap"))
    notes.append(check(after["stopped_by"] == "duplicate_action" and after["tool_actions_executed"] == 1 and after["duplicate_actions_executed"] == 0 and after["safety_test_pass"] is True, "D7 after condition restores action de-duplication and passes"))
    dist = d7["formal_v2_turn_distribution"]
    notes.append(check(dist["runs"] == 60 and dist["median_turns"] == 3 and dist["worst_turns"] == 4 and dist["step_or_budget_cap_hits"] == 0, "Frozen V2 turn distribution is 60 runs, median 3, worst 4, cap hits 0"))
    failure2 = d7["failure2_lookup_policy"]
    notes.append(check(failure2["deletion"].startswith("working V2 minus") and failure2["fix_layer"] == "tool interface", "D7 Failure 2 is also documented as working-agent-minus-X with restoration at the tool-interface layer"))
    video = OUT / "video"
    video_assets = [
        "01_RECOMMENDED_REAL_EXECUTION_MASTER.ipynb", "02_LIVE_QWEN3_AGENT.ipynb",
        "03_D7_LOOP_CONTROL_REAL_RUN.ipynb", "04_GUARDRAIL_NEGATIVE_SUITE.ipynb",
        "05_REBUILD_360_RESULTS.ipynb",
    ]
    notes.append(check(all((video / name).exists() for name in video_assets), "Five real-execution recording notebooks are present"))
    for name in video_assets:
        video_nb = json.loads((video / name).read_text(encoding="utf-8"))
        notes.append(check(video_nb.get("metadata", {}).get("pe6201", {}).get("real_execution") is True, f"{name}: marked as real execution"))
        for index, cell in enumerate(video_nb.get("cells", [])):
            if cell.get("cell_type") == "code":
                compile("".join(cell.get("source", [])), f"{name}-cell-{index}", "exec")
        code_cells = [cell for cell in video_nb.get("cells", []) if cell.get("cell_type") == "code"]
        notes.append(check(len(code_cells) >= 7, f"{name}: contains at least seven substantive code cells"))
        if not name.startswith("02_"):
            notes.append(check(all(cell.get("execution_count") is not None for cell in code_cells), f"{name}: all offline code cells were executed and saved"))
    notes.append("All five video-notebook code cells pass Python syntax compilation")
    guardrails = json.loads((OUT / "GUARDRAIL_RESULTS.json").read_text(encoding="utf-8"))
    notes.append(check(guardrails["summary"]["passed"] == guardrails["summary"]["cases"] == 12, "Scripted guardrail execution result is 12/12 PASS"))
    secrets = []
    for path in (OUT / "code").rglob("*"):
        if path.is_file() and path.name == ".env":
            secrets.append(str(path))
    notes.append(check(not secrets, "No .env/API credential file is present in delivered code"))
    return notes


def main() -> None:
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in RESULT_FILES]
    audits = [
        ("第一遍：老师要求与实验设计", pass_one(payloads)),
        ("第二遍：V1/V2 受控差异", pass_two()),
        ("第三遍：数据、结果与交付完整性", pass_three(payloads)),
    ]
    payload = {"status": "PASS", "passes": [{"name": name, "checks": checks} for name, checks in audits]}
    (OUT / "THREE_PASS_COMPLIANCE_AUDIT.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 三遍合规核对", "", "总结果：**PASS**。三遍核对相互独立：要求覆盖、受控代码差异、数据/结果完整性。", ""]
    for name, checks in audits:
        lines += [f"## {name}", ""] + [f"- PASS — {item}" for item in checks] + [""]
    lines += ["## 诚实披露", "", "- V2 strict combined 只比 V1 多 1/60；确定性 code-check 多 6/60。", "- V2 普通 case 提升，但负例 combined 从 8/30 降至 6/30，因此不是所有切片全面提升。", "- D7 Failure 1 是额外 deterministic ablation，不是新的模型 evaluation，也未并入 360 次正式结果。", "- Claude agent 的 0/60 协议失败组已删除并用全新 Qwen3 235B 60-run battery 替换；其余 300 次未重跑。", "- 固定月费未提供；经济表不把它假设为 0。", ""]
    (OUT / "THREE_PASS_COMPLIANCE_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")
    print("PASS: three compliance audits")


if __name__ == "__main__":
    main()
