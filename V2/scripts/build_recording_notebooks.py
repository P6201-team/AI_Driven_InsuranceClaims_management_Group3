#!/usr/bin/env python3
"""Build five substantial, real-execution notebooks for the PE6201 recording."""
from __future__ import annotations

import contextlib
import io
import json
import os
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "PE6201_A2_Final_Deliverables"
VIDEO = BUNDLE / "video"


def lines(text: str) -> list[str]:
    return [line + "\n" for line in text.strip("\n").splitlines()]


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": lines(text)}


def code(text: str, *, auto: bool = True) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {"pe6201_auto_execute": auto},
        "outputs": [],
        "source": lines(text),
    }


def notebook(title: str, cells: list[dict]) -> dict:
    return {
        "cells": [md(title)] + cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3"},
            "pe6201": {"real_execution": True, "frozen_formal_results_mutated": False},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


SETUP = r'''from pathlib import Path
import csv, json, os, statistics, subprocess, sys, tempfile, textwrap, time

ROOT = next((p for p in [Path.cwd(), Path.cwd().parent, Path('/content/PE6201_A2_Final_Deliverables')]
             if (p/'code'/'V2'/'run_eval.py').exists()), None)
assert ROOT is not None, 'Open the notebook from the final bundle or upload the whole bundle to Colab.'
CODE = ROOT/'code'/'V2'
WORK = Path(tempfile.mkdtemp(prefix='pe6201_recording_'))

def run_cmd(args, cwd=CODE, env=None, check=True):
    merged = dict(os.environ)
    if env: merged.update(env)
    print('$', ' '.join(map(str, args)), flush=True)
    started = time.time()
    p = subprocess.run(args, cwd=cwd, env=merged, text=True, capture_output=True)
    print(p.stdout, end='')
    if p.stderr: print(p.stderr, end='', file=sys.stderr)
    print(f'[exit={p.returncode}; elapsed={time.time()-started:.2f}s]', flush=True)
    if check and p.returncode: raise RuntimeError(f'command failed: {p.returncode}')
    return p

print('Bundle :', ROOT)
print('Runtime:', sys.executable)
print('Workdir:', WORK)
print('Mode   : real program execution; formal result files remain read-only')'''


def master_notebook() -> dict:
    return notebook(
        "# Option 1 — Recommended real-execution master\n\n"
        "This is the safest 5-minute recording route. Every demonstration cell runs the actual evaluator, "
        "agent loop or audit code. Saved outputs are included, and rerunning writes only to a temporary folder.",
        [
            md("## Recording route\n\n1. Audit the 40-case design. 2. Inspect the actual V2 tool contract. "
               "3. Run tests and 12 guardrails. 4. Execute a full negative trajectory. 5. Reproduce D7 before/after. "
               "6. Recompute all 360 quality and cost results from raw runs."),
            code(SETUP),
            md("## 1. Reconstruct the evaluation plan from source fixtures"),
            code(r'''expected = json.loads((CODE/'expected_outcomes_A.json').read_text())
claims = json.loads((CODE/'data_A'/'claims.json').read_text())
negative = [r for r in expected if r['expected_decision'] != 'approve_in_principle']
ordinary = [r for r in expected if r['expected_decision'] == 'approve_in_principle']
families = {}
for row in expected: families[row['family']] = families.get(row['family'], 0) + 1
planned = len(ordinary) + 3*len(negative)
print(f'claims={len(claims)} expected={len(expected)} ordinary={len(ordinary)} negative={len(negative)}')
print(f'formal runs per condition = {len(ordinary)} + 3×{len(negative)} = {planned}')
print('families:')
for name,count in sorted(families.items()): print(f'  {name:<42} {count}')
assert len(claims)==40 and len(ordinary)==30 and len(negative)==10 and planned==60'''),
            md("## 2. Inspect the real V2 `lookup_policy` tool boundary"),
            code(r'''sys.path.insert(0, str(CODE))
import tools
descriptor = tools.DESCRIPTORS['lookup_policy']
print(json.dumps(descriptor, indent=2, ensure_ascii=False))
sample = tools.lookup_policy(member_id='M-6118')
print('\nActual tool observation:')
print(json.dumps(sample, indent=2, ensure_ascii=False))
assert set(sample['member']) == {'member_id','policy_id'}
assert 'policy' in sample and 'remaining' in sample'''),
            md("## 3. Execute the delivered unit tests"),
            code("run_cmd([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])"),
            md("## 4. Execute all 12 scripted guardrail cases"),
            code(r'''guardrail_out = WORK/'guardrail_results.json'
sys.path.insert(0, str(CODE))
from tests.guardrail_runner import run_checklist
guardrail_summary = run_checklist(output_path=str(guardrail_out), verbose=True)
print(json.dumps(guardrail_summary, indent=2))
assert guardrail_summary['passed'] == guardrail_summary['cases'] == 12'''),
            md("## 5. Run a representative negative case through the real agent and tools\n\n"
               "CLM-8888 has mixed claim lines and missing pre-authorisation evidence."),
            code(r'''negative_out = WORK/'negative_case'
p = run_cmd([sys.executable, str(CODE/'run_eval.py'), '--backend','scripted',
             '--prompt-version','v2','--case','CLM-8888','--max-runs','1',
             '--judge','scripted','--verbose','--output-dir',str(negative_out)])
negative_json = json.loads((negative_out/'v2_scripted_raw_results.json').read_text())
negative_run = negative_json['raw_runs'][0]
print('\nGenerated record — not a cached summary:')
print(json.dumps({k:negative_run[k] for k in ['case_id','actual_decision','turns','tokens_in','tokens_out','cost_usd','tools_called','overall_pass']}, indent=2))'''),
            md("## 6. Inspect the newly generated trajectory and evidence"),
            code(r'''record = negative_run['record']
for step in record['trajectory']:
    move = step.get('move') or {}
    print(f"iteration {step['iteration']}: {move.get('thought')}")
    for name,args in move.get('calls') or []: print('   call', name, args)
print('\nfinal decision:', record['decision'])
print('missing evidence:', record.get('missing'))
print('guardrails:', record.get('guardrails_fired'))'''),
            md("## 7. Execute D7 working-agent-minus-X before/after"),
            code(r'''d7_out = WORK/'d7_results'
run_cmd([sys.executable, str(CODE/'scripts'/'run_d7_failure1.py'), '--verbose',
         '--output-dir',str(d7_out),
         '--formal-v2-json',str(ROOT/'results'/'raw_json'/'V2__GPT-4o_mini.json')])
d7 = json.loads((d7_out/'D7_FAILURE1_LOOP_CONTROL.json').read_text())
b,a = d7['before'],d7['after']
print('\nComputed from the new run:')
print('actions',b['tool_actions_executed'],'->',a['tool_actions_executed'])
print('tokens ',b['total_tokens'],'->',a['total_tokens'],f"({b['total_tokens']/a['total_tokens']:.1f}x)")
print('cost   ',b['estimated_cost_usd'],'->',a['estimated_cost_usd'],f"({b['estimated_cost_usd']/a['estimated_cost_usd']:.1f}x)")
print('pass   ',b['safety_test_pass'],'->',a['safety_test_pass'])'''),
            md("## 8. Recompute the 360-run comparison directly from raw trajectories"),
            code(r'''raw_files = sorted((ROOT/'results'/'raw_json').glob('*.json'))
print('raw inputs:', [p.name for p in raw_files])
assert len(raw_files)==6 and not any('Claude' in p.name for p in raw_files)
recomputed=[]
for path in raw_files:
    payload=json.loads(path.read_text()); runs=payload['raw_runs']; cfg=payload['config']
    strict=sum(bool(r['overall_pass']) for r in runs)
    ordinary_runs=[r for r in runs if not r['negative_case']]
    negative_runs=[r for r in runs if r['negative_case']]
    cost=sum(float(r['cost_usd']) for r in runs)/len(runs)
    expected_cost=cost+(1-strict/len(runs))*7.60
    recomputed.append((path.stem,cfg['model'],len(runs),strict,
                       sum(r['overall_pass'] for r in ordinary_runs),
                       sum(r['overall_pass'] for r in negative_runs),cost,expected_cost))
    assert len(runs)==60 and len({r['run_id'] for r in runs})==60
print(f"{'condition':<34} {'strict':>7} {'ordinary':>9} {'negative':>9} {'agent/case':>12} {'expected':>10}")
for name,model,n,s,o,neg,c,e in recomputed:
    print(f'{name:<34} {s:>2}/{n:<2} {o:>2}/30    {neg:>2}/30    ${c:>10.6f} ${e:>9.4f}')
print('total audited runs =',sum(x[2] for x in recomputed))'''),
            md("## 9. Rebuild the economic conclusion"),
            code(r'''best=max(recomputed,key=lambda x:x[3])
cheapest=min(recomputed,key=lambda x:x[7])
print('Highest strict pass:',best[0],f'{best[3]}/60')
print('Lowest expected cost:',cheapest[0],f'${cheapest[7]:.4f}/case ex-fixed')
print('Formula: agent variable cost + (1-P) × US$7.60')
print('Fixed monthly cost: NOT_PROVIDED')
assert 'Qwen3' in best[0] and 'Qwen3' in cheapest[0]'''),
            md("## Closing line\n\nThe recording has just executed the test suite, 12 guardrails, a real multi-tool negative case, "
               "the D7 deletion experiment, a 360-run raw-data audit and the economic calculation. None of these cells merely displays a prepared summary."),
        ],
    )


def live_qwen_notebook() -> dict:
    return notebook(
        "# Option 2 — Live Qwen3 agent and mini-battery\n\n"
        "This version makes real OpenRouter calls. It is the strongest proof that the replacement model itself is running. "
        "The API key is read from the environment and never printed or saved.",
        [
            md("## Safety and cost\n\nRun one case first. The six-run mini-battery is optional. The full 60-run cell is disabled until you deliberately set `RUN_FULL_60 = True`."),
            code(SETUP),
            code(r'''MODEL='qwen/qwen3-235b-a22b-2507'
FAMILY='Qwen3 235B'
print('API key present:', bool(os.getenv('OPENROUTER_API_KEY')))
assert os.getenv('OPENROUTER_API_KEY'), 'Set OPENROUTER_API_KEY before recording.'
print('Evaluated model:',MODEL)
print('Judge model    : anthropic/claude-haiku-4.5 (same grader as the frozen comparison)')''', auto=False),
            md("## 1. Preview the negative case from source data"),
            code(r'''claims={r['claim_id']:r for r in json.loads((CODE/'data_A'/'claims.json').read_text())}
expected={r['case_id']:r for r in json.loads((CODE/'expected_outcomes_A.json').read_text())}
for cid in ['CLM-8888','CLM-8850']:
    print('\n',cid)
    print(json.dumps(claims[cid],indent=2,ensure_ascii=False))
    print('expected:',json.dumps(expected[cid],indent=2,ensure_ascii=False))'''),
            md("## 2. Run CLM-8888 live with verbose turns, tools and judge"),
            code(r'''live_negative=WORK/'live_negative'
run_cmd([sys.executable,str(CODE/'run_eval.py'),'--backend','live','--model',MODEL,
         '--model-family',FAMILY,'--prompt-version','v2','--case','CLM-8888','--max-runs','1',
         '--judge','live','--judge-model','anthropic/claude-haiku-4.5','--verbose',
         '--output-dir',str(live_negative)])''', auto=False),
            md("## 3. Inspect only the result just produced by this notebook"),
            code(r'''payload=json.loads((live_negative/'v2_live_raw_results.json').read_text())
run=payload['raw_runs'][0]
print(json.dumps({k:run[k] for k in ['run_id','case_id','actual_decision','turns','tools_called','tokens_in','tokens_out','cost_usd','code_check_pass','judgement_check_pass','overall_pass']},indent=2))
print('\nFinal record:')
print(json.dumps(run['record'],indent=2,ensure_ascii=False)[:12000])''', auto=False),
            md("## 4. Optional real six-run negative mini-battery\n\nTwo negative cases × three trials. This visibly demonstrates repeated-run stability."),
            code(r'''mini=WORK/'live_mini_battery'
run_cmd([sys.executable,str(CODE/'run_eval.py'),'--backend','live','--model',MODEL,
         '--model-family',FAMILY,'--prompt-version','v2','--case','CLM-8888','--case','CLM-8910',
         '--max-runs','6','--judge','live','--judge-model','anthropic/claude-haiku-4.5',
         '--verbose','--output-dir',str(mini)])''', auto=False),
            code(r'''mini_payload=json.loads((mini/'v2_live_raw_results.json').read_text())
rows=mini_payload['raw_runs']
for r in rows:
    print(r['case_id'],r['trial'],'decision=',r['actual_decision'],'turns=',r['turns'],
          'tools=',len(r['tools_called']),'strict=',r['overall_pass'],'cost=',f"${r['cost_usd']:.6f}")
print('mini strict pass:',sum(r['overall_pass'] for r in rows),'/',len(rows))''', auto=False),
            md("## 5. Optional full 60-run reproduction\n\nThis writes to a fresh temporary directory and never overwrites the submitted formal results."),
            code(r'''RUN_FULL_60=False
if RUN_FULL_60:
    full=WORK/'full_60_reproduction'
    run_cmd([sys.executable,str(CODE/'run_eval.py'),'--backend','live','--model',MODEL,
             '--model-family',FAMILY,'--prompt-version','v2','--judge','live',
             '--judge-model','anthropic/claude-haiku-4.5','--resume','--output-dir',str(full)])
else:
    print('Full 60-run reproduction is intentionally disabled. Set RUN_FULL_60=True to execute it.')''', auto=False),
            md("## Recording note\n\nFor a five-minute video, run sections 1–3. If you want a longer sped-up segment, also run the six-run mini-battery."),
        ],
    )


def d7_notebook() -> dict:
    return notebook(
        "# Option 3 — D7 loop-control failure, code-level deep dive\n\n"
        "This notebook shows the actual guard implementation, runs the deletion experiment, prints both trajectories, and calculates the before/after economics from the newly generated JSON.",
        [
            code(SETUP),
            md("## 1. Show the working guard and loop code"),
            code(r'''import inspect
sys.path.insert(0,str(CODE))
import guardrails, agent
print('Guardrails.check_duplicate source:\n')
print(inspect.getsource(guardrails.Guardrails.check_duplicate))
print('\nAgent loop excerpt:\n')
src=inspect.getsource(agent.run_case)
for i,line in enumerate(src.splitlines(),1):
    if 'check_duplicate' in line or 'MAX_TURNS' in line or 'MAX_TOKENS' in line or 'for ' in line[:12]:
        print(f'{i:03d}: {line}')'''),
            md("## 2. Execute working agent minus action de-duplication, then restore it"),
            code(r'''out=WORK/'d7'
run_cmd([sys.executable,str(CODE/'scripts'/'run_d7_failure1.py'),'--verbose',
         '--output-dir',str(out),'--formal-v2-json',
         str(ROOT/'results'/'raw_json'/'V2__GPT-4o_mini.json')])
result=json.loads((out/'D7_FAILURE1_LOOP_CONTROL.json').read_text())'''),
            md("## 3. Print every attempted turn in the broken condition"),
            code(r'''b=result['before']
for step in b['trajectory']:
    print('iteration',step['iteration'],'usage=',step['usage'])
    print('  thought:',step['move']['thought'])
    print('  calls  :',step['move']['calls'])
print('stop=',b['stopped_by'],'actions=',b['tool_actions_executed'],'duplicates=',b['duplicate_actions_executed'])'''),
            md("## 4. Print the restored condition"),
            code(r'''a=result['after']
for step in a['trajectory']:
    print('iteration',step['iteration'],'usage=',step['usage'])
    print('  thought:',step['move']['thought'])
    print('  calls  :',step['move']['calls'])
print('stop=',a['stopped_by'],'actions=',a['tool_actions_executed'],'duplicates=',a['duplicate_actions_executed'])'''),
            md("## 5. Calculate reductions from the just-generated evidence"),
            code(r'''metrics=['turns_recorded','tool_actions_executed','duplicate_actions_executed','tokens_in','tokens_out','total_tokens','estimated_cost_usd']
print(f"{'metric':<30}{'before':>14}{'after':>14}{'reduction':>14}")
for m in metrics:
    before,after=b[m],a[m]
    reduction=(1-after/before) if before else 0
    print(f'{m:<30}{before:>14.6g}{after:>14.6g}{reduction:>13.1%}')
print('safety:',b['safety_test_pass'],'->',a['safety_test_pass'])'''),
            md("## 6. Recalculate the evidence-based cap from frozen formal trajectories"),
            code(r'''formal=json.loads((ROOT/'results'/'raw_json'/'V2__GPT-4o_mini.json').read_text())['raw_runs']
turns=[r['turns'] for r in formal]
cap_hits=sum((r.get('stopped_by') or '') in {'step_cap','turn_cap','budget_ceiling','token_cap'} for r in formal)
print('runs=',len(turns),'median=',statistics.median(turns),'mean=',statistics.mean(turns),'worst=',max(turns))
print('configured cap=8; headroom=',8-max(turns),'; cap hits=',cap_hits)
assert max(turns)==4 and cap_hits==0'''),
            md("## 7. Explain the fix layer\n\nA prompt reminder cannot guarantee exactly-once execution. The tool name and arguments are valid, so the interface is not at fault. The loop must remember canonical executed actions; therefore the primary fix is code-layer de-duplication, while the unchanged cap remains a late backstop."),
        ],
    )


def guardrail_notebook() -> dict:
    return notebook(
        "# Option 4 — Guardrails and negative-case stress suite\n\n"
        "This notebook executes the 12 D3(b) guardrail tests, then runs four negative cases through the real evaluator for 12 trajectories.",
        [
            code(SETUP),
            md("## 1. Load and inspect the 12 guardrail specifications"),
            code(r'''cases=json.loads((CODE/'tests'/'guardrail_cases.json').read_text())
print('guardrail cases:',len(cases))
for c in cases:
    print(c['case_id'],c['family'],'autonomy=',c['config']['autonomy'],'expected=',c['expected'])'''),
            md("## 2. Execute the guardrail checklist through the actual scaffold"),
            code(r'''sys.path.insert(0,str(CODE))
from tests.guardrail_runner import run_checklist
guard_file=WORK/'guardrails.json'
summary=run_checklist(output_path=str(guard_file),verbose=True)
assert summary['passed']==12 and summary['failed']==0'''),
            md("## 3. Inspect structured logs produced by the checklist"),
            code(r'''guard=json.loads(guard_file.read_text())
for r in guard['results']:
    o=r['observed']
    print(f"{r['case_id']} stop={o['stopped_by']} decision={o['decision']} turns={o['turns']} logs={o['decision_log_records']} pass={r['passed']}")'''),
            md("## 4. Execute four negative claims × three trials using the real agent loop"),
            code(r'''stress=WORK/'negative_stress'
cmd=[sys.executable,str(CODE/'run_eval.py'),'--backend','scripted','--prompt-version','v2',
     '--case','CLM-8888','--case','CLM-8894','--case','CLM-8910','--case','CLM-9053',
     '--max-runs','12','--judge','scripted','--verbose','--output-dir',str(stress)]
run_cmd(cmd)
stress_payload=json.loads((stress/'v2_scripted_raw_results.json').read_text())
rows=stress_payload['raw_runs']
assert len(rows)==12'''),
            md("## 5. Calculate repeat stability and tool coverage from the newly generated runs"),
            code(r'''groups={}
for r in rows: groups.setdefault(r['case_id'],[]).append(r)
for cid,items in groups.items():
    decisions=[r['actual_decision'] for r in items]
    tools=sorted({t for r in items for t in r['tools_called']})
    print('\n',cid,'trials=',len(items),'strict=',sum(r['overall_pass'] for r in items),'/',len(items))
    print(' decisions:',decisions)
    print(' turns    :',[r['turns'] for r in items])
    print(' tools    :',tools)
    print(' tokens   :',sum(r['tokens_in']+r['tokens_out'] for r in items))'''),
            md("## 6. Show one complete newly generated record"),
            code(r'''sample=groups['CLM-8888'][0]
print(json.dumps(sample['record'],indent=2,ensure_ascii=False)[:16000])'''),
            md("## Closing\n\nThis route is fully offline but still exercises the actual loop, registry, tools, guardrails, grader contract and repeated negative-trial plan."),
        ],
    )


def rebuild_notebook() -> dict:
    return notebook(
        "# Option 5 — Rebuild and audit all 360 results from raw runs\n\n"
        "This notebook does not open the prepared summary first. It reads six immutable raw trajectory files, validates all 360 runs, recomputes quality/cost tables, and writes a fresh independent rebuild to a temporary directory.",
        [
            code(SETUP),
            md("## 1. Discover the six raw conditions"),
            code(r'''raw_dir=ROOT/'results'/'raw_json'
files=sorted(raw_dir.glob('*.json'))
print('\n'.join(p.name for p in files))
assert len(files)==6
assert not any('Claude' in p.name for p in files)
assert any('Qwen3' in p.name for p in files)'''),
            md("## 2. Validate run IDs, case/trial coverage and trajectories"),
            code(r'''payloads=[]
for path in files:
    payload=json.loads(path.read_text()); rows=payload['raw_runs']; payloads.append((path,payload))
    assert len(rows)==60
    assert len({r['run_id'] for r in rows})==60
    assert len({r['case_id'] for r in rows})==40
    assert sum(not r['negative_case'] for r in rows)==30
    assert sum(r['negative_case'] for r in rows)==30
    assert all(r.get('record') and 'trajectory' in r['record'] for r in rows)
    assert all(r.get('token_counts_measured') for r in rows)
    print(path.stem,'PASS — 60 runs, 40 cases, 30 ordinary, 30 negative trials, trajectories complete')'''),
            md("## 3. Recompute the model-level quality table"),
            code(r'''summary=[]
for path,payload in payloads:
    rows=payload['raw_runs']; n=len(rows); strict=sum(bool(r['overall_pass']) for r in rows)
    ordinary=[r for r in rows if not r['negative_case']]; negative=[r for r in rows if r['negative_case']]
    agent=sum(float(r['cost_usd']) for r in rows); judge=sum(float(r.get('judgement_cost_usd') or 0) for r in rows)
    summary.append({'label':path.stem,'model':payload['config']['model'],'runs':n,
        'code_pass':sum(bool(r['code_check_pass']) for r in rows),
        'judge_pass':sum(bool(r['judgement_check_pass']) for r in rows),
        'combined_pass':strict,'combined_rate':strict/n,
        'ordinary_pass':sum(bool(r['overall_pass']) for r in ordinary),
        'negative_pass':sum(bool(r['overall_pass']) for r in negative),
        'avg_turns':sum(r['turns'] for r in rows)/n,'tokens_in':sum(r['tokens_in'] for r in rows),
        'tokens_out':sum(r['tokens_out'] for r in rows),'agent_cost_usd':agent,
        'judge_cost_usd':judge,'avg_agent_cost_usd':agent/n})
fields=list(summary[0])
print(' | '.join(fields))
for r in summary: print(' | '.join(str(r[f]) for f in fields))'''),
            md("## 4. Recompute expected economics and ±10 percentage-point sensitivity"),
            code(r'''cost_rows=[]
for r in summary:
    for scenario,p in [('P-10pp',max(0,r['combined_rate']-.1)),('Observed',r['combined_rate']),('P+10pp',min(1,r['combined_rate']+.1))]:
        fallback=(1-p)*7.60; total=r['avg_agent_cost_usd']+fallback
        cost_rows.append({'label':r['label'],'scenario':scenario,'P':p,'agent':r['avg_agent_cost_usd'],
                          'fallback':fallback,'total_per_case':total,'monthly_ex_fixed':total*8000})
for r in cost_rows:
    if r['scenario']=='Observed': print(r)
print('Fixed monthly fee remains NOT_PROVIDED.')'''),
            md("## 5. Write a completely fresh rebuild"),
            code(r'''rebuild=WORK/'independent_rebuild'; rebuild.mkdir()
def write_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
write_csv(rebuild/'model_summary_rebuilt.csv',summary)
write_csv(rebuild/'cost_model_rebuilt.csv',cost_rows)
(rebuild/'audit.json').write_text(json.dumps({'raw_files':[p.name for p,_ in payloads],
    'runs':sum(r['runs'] for r in summary),'summary':summary,'cost':cost_rows},indent=2))
print('fresh files:')
for p in sorted(rebuild.iterdir()): print(' ',p.name,p.stat().st_size,'bytes')'''),
            md("## 6. Independently compare the fresh rebuild with the delivered summary"),
            code(r'''delivered={r['label']:r for r in csv.DictReader((ROOT/'results'/'model_summary.csv').open(encoding='utf-8-sig'))}
name_map={
'V1__GPT-4o_mini':'V1 · GPT-4o mini','V2__GPT-4o_mini':'V2 · GPT-4o mini',
'V2__Gemini_2.5_Flash-Lite':'V2 · Gemini 2.5 Flash-Lite','V2__Mistral_Small_3.2_24B':'V2 · Mistral Small 3.2 24B',
'V2__DeepSeek_V3.1':'V2 · DeepSeek V3.1','V2__Qwen3_235B':'V2 · Qwen3 235B'}
for r in summary:
    label=name_map[r['label']]; d=delivered[label]
    assert int(d['runs'])==r['runs'] and int(d['combined_pass'])==r['combined_pass']
    assert abs(float(d['agent_cost_usd'])-r['agent_cost_usd'])<1e-12
    print('MATCH',label,'strict',r['combined_pass'],'/60','agent cost',f"${r['agent_cost_usd']:.6f}")
print('All 360 rebuilt results match the delivered consolidation.')'''),
            md("## 7. Final result computed by this notebook"),
            code(r'''best=max(summary,key=lambda r:r['combined_pass'])
best_cost=min((r for r in cost_rows if r['scenario']=='Observed'),key=lambda r:r['total_per_case'])
print('Best strict quality:',name_map[best['label']],best['combined_pass'],'/60')
print('Best observed expected cost:',name_map[best_cost['label']],f"${best_cost['total_per_case']:.4f}/case ex-fixed")
print('Qwen replacement is present; Claude agent group is absent.')'''),
        ],
    )


def execute_offline(nb: dict, cwd: Path) -> dict:
    namespace: dict = {}
    count = 0
    old = Path.cwd()
    os.chdir(cwd)
    try:
        for cell in nb["cells"]:
            if cell["cell_type"] != "code" or not cell.get("metadata", {}).get("pe6201_auto_execute", True):
                continue
            count += 1
            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    exec(compile("".join(cell["source"]), f"notebook-cell-{count}", "exec"), namespace)
            except Exception:
                traceback.print_exc(file=output)
                raise
            cell["execution_count"] = count
            text = output.getvalue()
            cell["outputs"] = [{"name": "stdout", "output_type": "stream", "text": lines(text)}] if text else []
    finally:
        os.chdir(old)
    return nb


def main() -> None:
    VIDEO.mkdir(parents=True, exist_ok=True)
    for old in ["01_RECOMMENDED_Offline_Master.ipynb", "02_Live_API_With_Fallback.ipynb",
                "03_D7_Technical_Deep_Dive.ipynb", "04_One_Command_Terminal_Demo.py",
                "05_Offline_Browser_Dashboard.html"]:
        path = VIDEO / old
        if path.exists(): path.unlink()

    notebooks = [
        ("01_RECOMMENDED_REAL_EXECUTION_MASTER.ipynb", master_notebook(), True),
        ("02_LIVE_QWEN3_AGENT.ipynb", live_qwen_notebook(), False),
        ("03_D7_LOOP_CONTROL_REAL_RUN.ipynb", d7_notebook(), True),
        ("04_GUARDRAIL_NEGATIVE_SUITE.ipynb", guardrail_notebook(), True),
        ("05_REBUILD_360_RESULTS.ipynb", rebuild_notebook(), True),
    ]
    for name, nb, run in notebooks:
        if run: nb = execute_offline(nb, BUNDLE)
        (VIDEO/name).write_text(json.dumps(nb,ensure_ascii=False,indent=1),encoding="utf-8")

    master_text=(VIDEO/notebooks[0][0]).read_text(encoding="utf-8")
    (BUNDLE/'PE6201_A2_VIDEO_MASTER.ipynb').write_text(master_text,encoding="utf-8")
    (BUNDLE/'PE6201_A2_Evaluation_Demo.ipynb').write_text(master_text,encoding="utf-8")
    guide='''# 五个真实运行录屏 Notebook

所有版本都是 `.ipynb`。除 live 版本外，已保存实际执行 output；重新运行只写入临时目录，不改正式 360-run 文件。

1. `01_RECOMMENDED_REAL_EXECUTION_MASTER.ipynb`：推荐。依次真实运行 source audit、unit tests、12 guardrails、negative trajectory、D7 和 360-run raw rebuild。
2. `02_LIVE_QWEN3_AGENT.ipynb`：真正调用 Qwen3/OpenRouter。建议录像时只跑单个 CLM-8888；也提供 6-run mini-battery 与手动开启的 60-run reproduction。
3. `03_D7_LOOP_CONTROL_REAL_RUN.ipynb`：展示 guard/loop 源码并执行 working-agent-minus-X before/after。
4. `04_GUARDRAIL_NEGATIVE_SUITE.ipynb`：运行 12 guardrails，再运行四个 negative cases ×3 trials。
5. `05_REBUILD_360_RESULTS.ipynb`：从六份 raw trajectory 重算 360 条质量、成本和敏感性结果，并与交付结果独立核对。

## 最简单的 5 分钟顺序

打开 01：展示 case plan → unit tests/guardrails → CLM-8888 verbose trajectory → D7 before/after → 360-run rebuild → Qwen3 31/60 和成本结论。若一定要证明远端模型实时调用，再切到 02 只跑 CLM-8888。
'''
    (VIDEO/'VIDEO_RECORDING_OPTIONS_CN.md').write_text(guide,encoding="utf-8")
    print('Built and executed five real-run notebooks in',VIDEO)


if __name__ == '__main__':
    main()
