"""Live published-model diagnostics with a specified OpenAI model; no release mutations."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'shared')]
from helios_core.demo.runtime import DemoRuntime
from helios_core.demo.playground import Question,RunPlan
from helios_core.llm.client import LLMClient
from apps.helios.tests.test_pharma_intelligence import registry


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--state-dir',type=Path,required=True)
    parser.add_argument('--token-file',type=Path,required=True)
    parser.add_argument('--model',default='gpt-5.4')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    llm=LLMClient('openai',args.model,args.token_file.expanduser().read_text().strip(),'https://api.openai.com/v1',timeout=60)
    report={'model':args.model,'checked_at':datetime.now(timezone.utc).isoformat(),'connection_reply':llm.complete('Reply with OK.','Connection test.'),'cases':[]}
    runtime=DemoRuntime(registry().load('pharma_intelligence'),args.state_dir)
    try:
        version=runtime.workspace.release('v1.0')
        config=runtime.summary()
        binding={k:config[k] for k in ('pack_id','snapshot_sha256','session_id')}
        cases=[
            ('korea','What is the Korea share of sales for new medicines launched during 2020–2024?','unsupported_scope',['geography'],None),
            ('missing_period','What is the US share of sales for new medicines launched during 1999–2020?','no_data',['period'],None),
            ('usa','What is the US share of sales for new medicines launched during 2020–2024?','ready',[],74.1),
            ('document','What is the North America share of the entire prescription medicine market in 2025?','ready',[],None),
        ]
        for name,text,status,reasons,expected in cases:
            plan=runtime.playground.interpret(Question(**binding,version='v1.0',context_sha256=version['context_sha256'],question=text,mode='auto'),llm)
            item={'id':name,'question':text,'status':plan['status'],'kind':plan.get('kind'),'message':plan.get('message'),
                  'scope_check':plan.get('scope_check'),'agent':plan.get('agent')}
            item['passed']=plan['status']==status
            if reasons:item['passed']&=plan.get('scope_check',{}).get('reason_dimensions',[])==reasons
            if plan['status']=='ready' and expected is not None:
                result=runtime.playground.execute(RunPlan(**binding,plan_id=plan['plan_id']),llm)
                item['rows']=result['rows'];item['passed']&=float(result['rows'][0][0])==expected
            if name=='document':item['passed']&=plan.get('kind')=='document'
            if status!='ready':item['passed']&='plan_id' not in plan
            report['cases'].append(item)
            args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            print(json.dumps({k:item[k] for k in ('id','status','passed','message')}),flush=True)
        report['passed']=sum(c['passed'] for c in report['cases']);report['failed']=len(cases)-report['passed']
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    finally:runtime.close()
    return int(bool(report['failed']))


if __name__=='__main__':raise SystemExit(main())
