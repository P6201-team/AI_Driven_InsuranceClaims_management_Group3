#!/usr/bin/env python3
"""Build the PE6201 A2 handoff from frozen raw evaluation JSON files.

This script intentionally uses only the Python standard library so that the
notebook/report bundle can be rebuilt on Colab or a clean laptop.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "evaluation_package"
OUT = ROOT / "PE6201_A2_Final_Deliverables"
DATA_OUT = OUT / "results"

INPUTS = [
    ("V1 · GPT-4o mini", "v1", ROOT / "a2_evaluation_outputs/final_v1_gpt4o_mini/v1_raw_results.json"),
    ("V2 · GPT-4o mini", "v2", ROOT / "a2_evaluation_outputs/final_v2_gpt4o_mini_record_complete/v2_live_raw_results.json"),
    ("V2 · Gemini 2.5 Flash-Lite", "v2", ROOT / "a2_evaluation_outputs/battery_v2_gemini_2_5_flash_lite/v2_live_raw_results.json"),
    ("V2 · Mistral Small 3.2 24B", "v2", ROOT / "a2_evaluation_outputs/battery_v2_mistral_small_3_2_24b/v2_live_raw_results.json"),
    ("V2 · DeepSeek V3.1", "v2", ROOT / "a2_evaluation_outputs/battery_v2_deepseek_chat_v3_1/v2_live_raw_results.json"),
    ("V2 · Qwen3 235B", "v2", ROOT / "a2_evaluation_outputs/battery_v2_qwen3_235b_a22b_2507/v2_live_raw_results.json"),
]

FAILURE_COST = 7.60
MONTHLY_VOLUME = 8000


def pct(n: float, d: float) -> float:
    return n / d if d else 0.0


def lookup_policy_tokens(run: dict) -> int:
    total = 0
    for item in (run.get("record") or {}).get("tool_observations", []):
        if item.get("tool") == "lookup_policy":
            total += int(item.get("observation_tokens_estimated") or 0)
    return total


def failure_category(run: dict) -> str:
    if run.get("overall_pass"):
        return "pass"
    tools = run.get("tools_called") or []
    stopped = run.get("stopped_by") or ""
    failures = " | ".join(run.get("code_check_failures") or [])
    judge_reason = (run.get("judgement") or {}).get("reason", "")
    text = (failures + " " + judge_reason).lower()
    if not tools:
        return "no_tool_call / protocol_compatibility"
    if stopped in {"turn_cap", "token_cap"}:
        return stopped
    if run.get("actual_decision") != run.get("expected_decision"):
        return "wrong_decision"
    if "duplicate" in text:
        return "duplicate_evidence_missing_or_wrong"
    if "approved_total" in text or "refused_total" in text or "line-level" in text or "disposition" in text:
        return "final_record_incomplete"
    if not run.get("code_check_pass") and run.get("judgement_check_pass"):
        return "code_only_failure"
    if run.get("code_check_pass") and not run.get("judgement_check_pass"):
        return "judge_only_failure"
    return "multiple_or_other"


def model_summary(label: str, version: str, payload: dict) -> dict:
    runs = payload["raw_runs"]
    n = len(runs)
    ordinary = [r for r in runs if not r.get("negative_case")]
    negative = [r for r in runs if r.get("negative_case")]
    agent_cost = sum(float(r.get("cost_usd") or 0) for r in runs)
    judge_cost = sum(float(r.get("judgement_cost_usd") or 0) for r in runs)
    combined = sum(bool(r.get("overall_pass")) for r in runs)
    c = agent_cost / n if n else 0
    p = combined / n if n else 0
    expected = c + (1 - p) * FAILURE_COST
    return {
        "label": label,
        "version": version,
        "model": payload["config"].get("model"),
        "model_family": payload["config"].get("model_family"),
        "judge_model": payload["config"].get("judge_model"),
        "runs": n,
        "code_pass": sum(bool(r.get("code_check_pass")) for r in runs),
        "code_rate": pct(sum(bool(r.get("code_check_pass")) for r in runs), n),
        "judge_pass": sum(bool(r.get("judgement_check_pass")) for r in runs),
        "judge_rate": pct(sum(bool(r.get("judgement_check_pass")) for r in runs), n),
        "combined_pass": combined,
        "combined_rate": p,
        "ordinary_pass": sum(bool(r.get("overall_pass")) for r in ordinary),
        "ordinary_runs": len(ordinary),
        "ordinary_rate": pct(sum(bool(r.get("overall_pass")) for r in ordinary), len(ordinary)),
        "negative_pass": sum(bool(r.get("overall_pass")) for r in negative),
        "negative_runs": len(negative),
        "negative_rate": pct(sum(bool(r.get("overall_pass")) for r in negative), len(negative)),
        "avg_turns": sum(float(r.get("turns") or 0) for r in runs) / n,
        "tokens_in": sum(int(r.get("tokens_in") or 0) for r in runs),
        "tokens_out": sum(int(r.get("tokens_out") or 0) for r in runs),
        "cached_tokens": sum(int(r.get("cached_tokens") or 0) for r in runs),
        "agent_cost_usd": agent_cost,
        "judge_cost_usd": judge_cost,
        "avg_agent_cost_usd": c,
        "expected_fallback_cost_per_case_usd": (1 - p) * FAILURE_COST,
        "expected_total_cost_per_case_ex_fixed_usd": expected,
        "monthly_cost_ex_fixed_usd": expected * MONTHLY_VOLUME,
        "fixed_monthly_usd": "NOT_PROVIDED",
        "input_price_per_million": payload["config"].get("input_price_per_million"),
        "output_price_per_million": payload["config"].get("output_price_per_million"),
        "price_as_of": payload["config"].get("price_as_of"),
        "price_source": payload["config"].get("price_source"),
        "avg_lookup_policy_observation_tokens": sum(lookup_policy_tokens(r) for r in runs) / n,
        "failure_categories": dict(Counter(failure_category(r) for r in runs if not r.get("overall_pass"))),
    }


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fields = fields or list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def make_notebook(summary_rows: list[dict], v1v2_rows: list[dict]) -> dict:
    def md(text: str) -> dict:
        return {"cell_type": "markdown", "metadata": {}, "source": [line + "\n" for line in text.splitlines()]}

    def code(text: str) -> dict:
        return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [line + "\n" for line in text.splitlines()]}

    return {
        "cells": [
            md("# PE6201 A2 Problem A — Evaluation Demo\n\n录屏建议：按顺序运行每个 cell。Notebook 只读取已经冻结的结果，不会发起 API 请求或产生费用。"),
            md("## 1. 评估设计\n\n- 40 个 cases：30 个普通 case ×1，10 个负例 ×3，因此每个模型 60 次。\n- V1 与 V2 均用 `openai/gpt-4o-mini` 做受控比较。\n- V2 只改变 `lookup_policy` 的返回精简和 descriptor。\n- `overall_pass = code_check_pass AND judgement_check_pass`。"),
            code("from pathlib import Path\nimport pandas as pd\nimport matplotlib.pyplot as plt\nROOT = Path.cwd()\nif not (ROOT / 'results').exists():\n    ROOT = Path('/content/PE6201_A2_Final_Deliverables')\nsummary = pd.read_csv(ROOT / 'results' / 'model_summary.csv')\nruns = pd.read_csv(ROOT / 'results' / 'all_runs_detailed.csv')\ndelta = pd.read_csv(ROOT / 'results' / 'v1_v2_case_delta.csv')\nsummary[['label','combined_pass','runs','code_pass','judge_pass','ordinary_pass','negative_pass','avg_agent_cost_usd']]"),
            md("## 2. V1 → V2 结果\n\n讲解重点：V2 的 deterministic code-check 有明显提高；combined 总分小幅提高；但负例稳定性下降，必须如实呈现。"),
            code("summary[summary['label'].isin(['V1 · GPT-4o mini','V2 · GPT-4o mini'])].set_index('label')[['code_rate','judge_rate','combined_rate','ordinary_rate','negative_rate']].T.plot(kind='bar', figsize=(10,5)); plt.ylim(0,1); plt.ylabel('Pass rate'); plt.tight_layout()"),
            code("delta[delta['outcome_change'] != 'unchanged'][['case_id','trial','v1_overall','v2_overall','outcome_change','v1_reason','v2_reason']]"),
            md("## 3. 五模型 V2 横向比较\n\n原 Claude agent 组因统一协议下 0/60、没有形成有效工具链而被替换。Qwen3 235B replacement battery 为全新 60 次 live runs；其他模型保持冻结。"),
            code("summary.sort_values('combined_rate', ascending=False)[['label','combined_rate','code_rate','judge_rate','avg_turns','avg_agent_cost_usd','expected_total_cost_per_case_ex_fixed_usd']]"),
            code("summary.sort_values('combined_rate').plot.barh(x='label', y='combined_rate', legend=False, figsize=(9,5)); plt.xlim(0,1); plt.xlabel('Strict combined pass rate'); plt.tight_layout()"),
            md("## 4. 经济计算\n\n每 case 期望成本（不含固定月费）=`agent variable cost + (1-P) × 7.60`。月量为 8,000；固定月费未提供，所以不会擅自填 0。"),
            code("cost = pd.read_csv(ROOT / 'results' / 'cost_model.csv')\ncost[['label','pass_rate_scenario','agent_variable_cost_per_case_usd','fallback_cost_per_case_usd','total_cost_per_case_ex_fixed_usd','monthly_cost_ex_fixed_usd']]"),
            md("## 5. 单次 trace 展示\n\n下面可换 `case_id` 和模型，展示 turns、tools、tokens、cost 和失败原因。"),
            code("case_id = 'CLM-8842'\nmodel_label = 'V2 · GPT-4o mini'\nruns[(runs.case_id == case_id) & (runs.label == model_label)].T"),
            md("## 6. 录屏结论建议（中文）\n\n1. V1 经过共享模型代码修正后，不再出现负例 0/30。\n2. V2 只改 `lookup_policy` 接口：member 去噪、日期边界 inclusive、使用 remaining、并明确通过后仍要做 downstream checks 与记录证据。\n3. V2 的 strict combined 比 V1 多通过 1 次，code-check 多通过 6 次；普通 case 更好，但负例仍不够稳定。\n4. 经济结果必须和质量一起看：便宜模型若导致更多 fallback，可能总成本反而更高。\n5. 固定月费缺失，因此当前月成本只报告 ex-fixed，不能称 all-in。"),
        ],
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python", "version": "3"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    missing = [str(p) for _, _, p in INPUTS if not p.exists()]
    if missing:
        raise SystemExit("Missing completed result files:\n" + "\n".join(missing))
    OUT.mkdir(parents=True, exist_ok=True)
    DATA_OUT.mkdir(parents=True, exist_ok=True)

    payloads = {}
    summary_rows = []
    detailed_rows = []
    for label, version, path in INPUTS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payloads[label] = payload
        summary_rows.append(model_summary(label, version, payload))
        for run in payload["raw_runs"]:
            judgement = run.get("judgement") or {}
            detailed_rows.append({
                "label": label, "version": version, "model": run.get("model"), "model_family": run.get("model_family"),
                "judge_model": judgement.get("judge_model"), "run_id": run.get("run_id"), "case_id": run.get("case_id"),
                "family": run.get("family"), "trial": run.get("trial"), "negative_case": run.get("negative_case"),
                "expected_decision": run.get("expected_decision"), "actual_decision": run.get("actual_decision"),
                "code_check_pass": run.get("code_check_pass"), "judgement_check_pass": run.get("judgement_check_pass"),
                "overall_pass": run.get("overall_pass"), "failure_category": failure_category(run),
                "code_check_failures": " | ".join(run.get("code_check_failures") or []),
                "judge_reason": judgement.get("reason"), "agent_reason": (run.get("record") or {}).get("reason"),
                "turns": run.get("turns"), "tokens_in": run.get("tokens_in"), "tokens_out": run.get("tokens_out"),
                "cached_tokens": run.get("cached_tokens"), "agent_cost_usd": run.get("cost_usd"),
                "judge_cost_usd": run.get("judgement_cost_usd"), "seconds": run.get("seconds"),
                "stopped_by": run.get("stopped_by"), "tools_called": json.dumps(run.get("tools_called") or [], ensure_ascii=False),
                "guardrails_fired": json.dumps(run.get("guardrails_fired") or [], ensure_ascii=False),
                "lookup_policy_observation_tokens_estimated": lookup_policy_tokens(run),
                "run_timestamp": run.get("run_timestamp"), "source_json": str(path),
            })

    v1 = payloads["V1 · GPT-4o mini"]["raw_runs"]
    v2 = payloads["V2 · GPT-4o mini"]["raw_runs"]
    v1_map = {(r["case_id"], r["trial"]): r for r in v1}
    v2_map = {(r["case_id"], r["trial"]): r for r in v2}
    delta_rows = []
    for key in sorted(v1_map):
        a, b = v1_map[key], v2_map[key]
        outcome_change = "unchanged"
        if not a["overall_pass"] and b["overall_pass"]:
            outcome_change = "improved"
        elif a["overall_pass"] and not b["overall_pass"]:
            outcome_change = "regressed"
        delta_rows.append({
            "case_id": key[0], "trial": key[1], "negative_case": a["negative_case"],
            "v1_code": a["code_check_pass"], "v2_code": b["code_check_pass"],
            "v1_judge": a["judgement_check_pass"], "v2_judge": b["judgement_check_pass"],
            "v1_overall": a["overall_pass"], "v2_overall": b["overall_pass"], "outcome_change": outcome_change,
            "v1_decision": a["actual_decision"], "v2_decision": b["actual_decision"],
            "v1_turns": a["turns"], "v2_turns": b["turns"],
            "v1_cost_usd": a["cost_usd"], "v2_cost_usd": b["cost_usd"],
            "v1_lookup_policy_tokens": lookup_policy_tokens(a), "v2_lookup_policy_tokens": lookup_policy_tokens(b),
            "v1_reason": (a.get("record") or {}).get("reason"), "v2_reason": (b.get("record") or {}).get("reason"),
        })

    cost_rows = []
    base_expected = summary_rows[0]["expected_total_cost_per_case_ex_fixed_usd"]
    for row in summary_rows:
        for name, p in [("P-10pp", max(0, row["combined_rate"] - .10)), ("Observed P", row["combined_rate"]), ("P+10pp", min(1, row["combined_rate"] + .10))]:
            c = row["avg_agent_cost_usd"]
            fallback = (1 - p) * FAILURE_COST
            cost_rows.append({
                "label": row["label"], "scenario": name, "pass_rate_scenario": p,
                "agent_variable_cost_per_case_usd": c, "fallback_cost_per_case_usd": fallback,
                "total_cost_per_case_ex_fixed_usd": c + fallback,
                "monthly_volume": MONTHLY_VOLUME, "monthly_cost_ex_fixed_usd": (c + fallback) * MONTHLY_VOLUME,
                "fixed_monthly_usd": "NOT_PROVIDED", "all_in_monthly_cost_usd": "NOT_CALCULABLE",
                "failure_cost_usd": FAILURE_COST,
                "break_even_pass_rate_to_match_v1": 1 - ((base_expected - c) / FAILURE_COST),
                "formula": "C + (1-P)*7.60; monthly ex-fixed = per-case*8000",
            })

    case_groups = defaultdict(list)
    for r in detailed_rows:
        case_groups[(r["label"], r["case_id"], r["family"], r["negative_case"])].append(r)
    case_rows = []
    for (label, case_id, family, negative), rows in sorted(case_groups.items()):
        case_rows.append({
            "label": label, "case_id": case_id, "family": family, "negative_case": negative, "runs": len(rows),
            "code_passes": sum(bool(r["code_check_pass"]) for r in rows),
            "judge_passes": sum(bool(r["judgement_check_pass"]) for r in rows),
            "combined_passes": sum(bool(r["overall_pass"]) for r in rows),
            "combined_rate": pct(sum(bool(r["overall_pass"]) for r in rows), len(rows)),
            "avg_turns": sum(float(r["turns"] or 0) for r in rows) / len(rows),
            "avg_agent_cost_usd": sum(float(r["agent_cost_usd"] or 0) for r in rows) / len(rows),
            "failure_categories": json.dumps(dict(Counter(r["failure_category"] for r in rows)), ensure_ascii=False),
        })

    write_csv(DATA_OUT / "model_summary.csv", [{**r, "failure_categories": json.dumps(r["failure_categories"], ensure_ascii=False)} for r in summary_rows])
    write_csv(DATA_OUT / "all_runs_detailed.csv", detailed_rows)
    write_csv(DATA_OUT / "v1_v2_case_delta.csv", delta_rows)
    write_csv(DATA_OUT / "cost_model.csv", cost_rows)
    write_csv(DATA_OUT / "case_summary.csv", case_rows)
    (DATA_OUT / "all_results.json").write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "summaries": summary_rows, "runs": detailed_rows, "v1_v2_delta": delta_rows, "cost_model": cost_rows, "case_summary": case_rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    # Copy immutable raw evidence into the final bundle.
    raw_dir = DATA_OUT / "raw_json"
    raw_dir.mkdir(exist_ok=True)
    for label, _, path in INPUTS:
        shutil.copy2(path, raw_dir / (label.replace(" · ", "__").replace(" ", "_").replace("/", "-") + ".json"))

    v1s, v2s = summary_rows[0], summary_rows[1]
    improved = [r for r in delta_rows if r["outcome_change"] == "improved"]
    regressed = [r for r in delta_rows if r["outcome_change"] == "regressed"]
    report = f"""# PE6201 A2 Problem A — 最终评估报告

生成时间：{datetime.now(timezone.utc).isoformat()}  
严格口径：`overall_pass = code_check_pass AND judgement_check_pass`

## 执行摘要

- V1（GPT-4o mini）：combined {v1s['combined_pass']}/{v1s['runs']}，code {v1s['code_pass']}/{v1s['runs']}，judge {v1s['judge_pass']}/{v1s['runs']}。
- V2（GPT-4o mini）：combined {v2s['combined_pass']}/{v2s['runs']}，code {v2s['code_pass']}/{v2s['runs']}，judge {v2s['judge_pass']}/{v2s['runs']}。
- V2 的 combined 比 V1 多 {v2s['combined_pass']-v1s['combined_pass']} 次，code-check 多 {v2s['code_pass']-v1s['code_pass']} 次；普通 case 多 {v2s['ordinary_pass']-v1s['ordinary_pass']} 次。
- 风险：V2 负例 combined 为 {v2s['negative_pass']}/{v2s['negative_runs']}，V1 为 {v1s['negative_pass']}/{v1s['negative_runs']}，下降 {v1s['negative_pass']-v2s['negative_pass']} 次。结论是“总体小幅提升、确定性规则提升明显，但负例稳定性未全面提升”。

## Claude agent 组替换

- 原 Claude Haiku 4.5 被评估 agent 组在统一 JSON/tool protocol 下为 0/60，因此从最终横向比较中删除。
- 只新增并运行 Qwen3 235B 的 60-run replacement battery；其余五个 condition 共 300 次完全不重跑，正式总数仍为 360。
- Qwen3 235B：code **49/60**、judge **32/60**、strict combined **31/60**；ordinary **20/30**、negative **11/30**，59/60 runs 产生真实 tool calls。
- Qwen3 的 agent cost 为 US$0.055454/60 runs，平均约 US$0.000924/case；按相同 fallback 公式，observed expected cost 为约 US$3.6743/case（不含固定月费）。
- 为保持评分口径可比，replacement battery 继续使用与其他横向模型相同的 Claude Haiku judge；被删除的是 Claude 作为被评估 agent 的组，不是统一 judge protocol。

## V2 相对 V1 只改了什么

1. `lookup_policy` 的 `member` 返回从完整 member row 精简为 `member_id`、`policy_id`；`policy` 与 `remaining` 结构保持不变。
2. 同一 tool descriptor 明确：使用 `policy.start_date/end_date`；起止日均包含；额度判断使用 `remaining` 而非 `annual_limit`。
3. descriptor 明确三个 exact triggers：`policy_lapsed`、`outside_policy_dates`、`annual_limit_exceeded`；通过 policy 检查后仍要做 hospital、exact duplicate、逐行 coverage、必要时 pre-authorisation，并把结果带入最终 record。
4. V1 与 V2 的其他工具、registry、loop、guardrails、模型设置和共享 prompt 相同。

为什么会提升：接口去噪减少了 member name/join date 对模型的干扰；日期和剩余额度边界从隐含信息变成可执行规则；dependency/evidence 提示减少了“保单有效就提前结束”和“做了检查但没写入最终记录”。本次结果中共有 {len(improved)} 个 run 从 fail→pass，{len(regressed)} 个 run 从 pass→fail，完整清单见 `results/v1_v2_case_delta.csv`。由于 LLM 仍有非确定行为，不能把每个差异都归因于 descriptor；最可靠的信号是 code-check 从 {v1s['code_pass']} 提升至 {v2s['code_pass']}。

## D7 两个可复现 failure

- Failure 1（loop control）使用“working agent minus action de-duplication”的 deterministic ablation，不调用模型、不重跑 360 次正式 evaluation。修复前由 step cap 才停止：执行 8 个 tool actions，其中 7 个重复，65,880 tokens，估算 US$0.010368，safety test fail；恢复 `Guardrails.check_duplicate` 后，第 2 次相同动作即停止：仅执行 1 个 action、0 个重复，6,240 tokens，估算 US$0.001044，safety test pass。
- 正式 V2 冻结结果的 turn distribution 为 median 3、worst 4、cap 8、cap hits 0/60；因此 cap=8 留有 4 turns headroom，没有证据显示 cap 降低正式 pass rate。
- Failure 2（tool interface）同样按 deletion 表述：working V2 minus `lookup_policy` interface refinement，即恢复 V1 的这一项 contract；恢复 compact member return 和 precise descriptor 后得到 V2。详情、trajectory 与 before/after 均见 `D7_TWO_REPRODUCED_FAILURES.md`。
- D7 实验是额外的 targeted evidence，不并入也不替换 360 次正式结果。

## 经济计算

- 变量模型成本 C 使用 provider 实测或按当前价格重算的 agent cost；judge cost 单列，不计入生产 serving cost。
- 失败 fallback：`(1-P) × US$7.60`。
- 每 case：`C + (1-P) × 7.60`。
- 月量：8,000；月成本（不含固定费）=`每 case × 8,000`。
- 固定月费没有提供，因此报告为 `NOT_PROVIDED`，绝不按 0 假设。
- 敏感性：每个模型均计算 `P-10pp / observed P / P+10pp`。
- break-even：`P_be = 1 - (E-C)/7.60`；本表用 V1 observed expected cost 作为 E，同时保留公式供替换。

## 文件导览

- `results/all_runs_detailed.csv`：每次运行的 case、decision、两个 grader、turns、tokens、cost、失败分类。
- `results/case_summary.csv`：case 级汇总。
- `results/model_summary.csv`：模型级质量与成本。
- `results/cost_model.csv`：三层经济计算与 ±10pp sensitivity。
- `results/raw_json/`：完整原始 record、trajectory、tool observations 和 response metadata。
- `results/D7_FAILURE1_LOOP_CONTROL.json/.csv`：D7 Failure 1 的机器可读 before/after 证据。
- `D7_TWO_REPRODUCED_FAILURES.md`：两个 failure 的完整复现、修复层级和解释。
- `PE6201_A2_VIDEO_MASTER.ipynb`：推荐的 5 分钟录屏入口，真实运行 tests、guardrails、negative case、D7 和 360-run rebuild。
- `video/`：五个长流程、真实运行的 `.ipynb` 版本和中文录屏顺序。
- `PE6201_A2_Evaluation_Demo.ipynb`：与推荐 real-execution master 同步。
"""
    (OUT / "FINAL_REPORT_CN.md").write_text(report, encoding="utf-8")
    (OUT / "PE6201_A2_Evaluation_Demo.ipynb").write_text(json.dumps(make_notebook(summary_rows, delta_rows), ensure_ascii=False, indent=1), encoding="utf-8")

    # Machine-readable integrity manifest.
    manifest = {}
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name != "MANIFEST_SHA256.json":
            manifest[str(path.relative_to(OUT))] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
    (OUT / "MANIFEST_SHA256.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Built {OUT}")


if __name__ == "__main__":
    main()
