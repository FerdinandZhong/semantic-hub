"""Customer query acceptance against isolated published fixtures; optional live GPT-4o."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'shared')]
from apps.helios.tests.test_demo_playground import released, question
from helios_core.demo.playground import RunPlan
from apps.helios.tests.test_demo_context import binding
from helios_core.demo.context import result_payload
from helios_core.llm.client import LLMClient


def normalized(rows):
    def cell(v):
        if v is None:return None
        try:return str(Decimal(str(v)).normalize())
        except InvalidOperation:return str(v)
    return sorted([tuple(cell(v) for v in row) for row in rows], key=str)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--live-ai',action='store_true')
    parser.add_argument('--token-file',type=Path,default=Path.home()/'tokens/openai')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/customer-query-verification.json')
    parser.add_argument('--case',action='append',dest='case_ids')
    args=parser.parse_args()
    cases=json.loads((ROOT/'docs/customer-demo-queries.json').read_text())['cases']
    if args.case_ids:cases=[c for c in cases if c['id'] in args.case_ids]
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'live_ai':args.live_ai,'model':'gpt-4o' if args.live_ai else None,'scope':'Isolated temporary state. No user drafts, approvals or releases modified.','cases':[]}
    token=args.token_file.read_text().strip() if args.live_ai else None
    with tempfile.TemporaryDirectory(prefix='helios-customer-queries-') as temp:
        def sector_run(sector):
            r=released(Path(temp)/sector,sector);results=[]
            llm=LLMClient('openai','gpt-4o',token,'https://api.openai.com/v1',timeout=60) if args.live_ai else None
            try:
                for case in [c for c in cases if c['sector']==sector]:
                    item={'id':case['id'],'question':case['question'],'expected':case['expected']}
                    if case['reference_sql']:
                        reference=result_payload(r.query_local(case['reference_sql']))
                        item['expected_result']=reference
                    if llm:
                        try:
                            plan=r.playground.interpret(question(r,metric=None,mode='auto',question=case['question']),llm)
                            item['agent']=plan.get('agent');item['status']=plan['status'];item['message']=plan.get('message',plan.get('interpretation'))
                            if plan['status']=='ready':
                                item['request']=plan.get('request');item['sql']=plan.get('sql')
                                result=r.playground.execute(RunPlan(**binding(r),plan_id=plan['plan_id']),llm)
                                item['result']=result
                                item['passed']=bool(case['reference_sql']) and normalized(result.get('rows',[]))==normalized(reference['rows']) and result.get('columns')==reference['columns']
                            else:item['passed']=case['expected']=='needs_clarification' and plan['status'] in ('needs_clarification','no_data') and not plan.get('plan_id')
                        except Exception as exc:
                            item.update(status='error',error=str(exc),passed=False)
                    else:item.update(status='reference_verified' if case['reference_sql'] else 'not_run',passed=None)
                    results.append(item)
                    print(case['id'],item['status'],item['passed'],flush=True)
            finally:r.close()
            return results
        with ThreadPoolExecutor(max_workers=2) as pool:
            for result in pool.map(sector_run,['finance','power']):report['cases'].extend(result)
    report['passed']=sum(c['passed'] is True for c in report['cases'])
    report['failed']=sum(c['passed'] is False for c in report['cases'])
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['live_ai','passed','failed']}))
    return int(report['failed']>0)
if __name__=='__main__':raise SystemExit(main())
