"""Bounded live model checks against a temporary pharmaceutical semantic release."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'shared')]
from helios_core.llm import LLMClient
from helios_core.llm.openai_compat import openai_compatibility
from helios_core.demo.runtime import DemoRuntime
from apps.helios.tests.test_pharma_intelligence import registry, FIXTURES
from apps.helios.tests.test_demo_context import validated, review_request, publish
from apps.helios.tests.test_demo_playground import question, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', nargs='+', default=['gpt-4o', 'gpt-5.4', 'gpt-6.1-sol'])
    parser.add_argument('--token-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    key = args.token_file.expanduser().read_text().strip()
    if not key:
        parser.error('The model credential file is empty.')
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'scope': 'Temporary published fixture; no deployed model settings or user releases changed.', 'models': []}
    cases = [
        ('supported_cohort', 'What is the US share of sales for new medicines launched during 2020–2024?', 'ready', 74.1),
        ('missing_period', 'What is the US share of sales for new medicines launched during 1999–2020?', 'no_data', None),
        ('unsupported_geography', 'What is the Korea share of sales for new medicines launched during 2020–2024?', 'unsupported_scope', None),
    ]
    with tempfile.TemporaryDirectory(prefix='semantic-hub-model-compat-') as temp:
        runtime = DemoRuntime(registry().load('pharma_intelligence'), Path(temp))
        try:
            definition = runtime.workspace.seed()
            refs = {x['metric']: x['reference_sql'] for x in json.loads(
                (FIXTURES / 'pharma_intelligence/evaluation/references.json').read_text())}
            for metric in definition['metrics']:
                metric['reference_sql'] = refs[metric['name']]
            validated(runtime, definition)
            runtime.workspace.review(review_request(runtime))
            publish(runtime)
            for model in args.models:
                client = LLMClient('openai', model, key, 'https://api.openai.com/v1', max_tokens=32, timeout=90)
                item = {'model': model, 'api': openai_compatibility(model).api, 'cases': []}
                try:
                    item['connection_ok'] = client.complete('Reply with OK.', 'Connection test. Reply with OK.').strip() == 'OK'
                except Exception as exc:
                    item['connection_ok'], item['connection_error'] = False, type(exc).__name__
                print(model, 'connection', item['connection_ok'], flush=True)
                if not item['connection_ok']:
                    report['models'].append(item)
                    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
                    continue
                client.max_tokens = 600
                for name, text, expected, number in cases:
                    plan = runtime.playground.interpret(question(runtime, metric=None, mode='auto', question=text), client)
                    entry = {'case': name, 'expected': expected, 'status': plan['status'], 'message': plan.get('message'),
                             'agent': plan.get('agent'), 'scope_check': plan.get('scope_check')}
                    entry['passed'] = plan['status'] == expected and bool(plan.get('agent', {}).get('trace'))
                    if plan['status'] == 'ready':
                        result = run(runtime, plan)
                        entry['sql'], entry['rows'] = result['sql'], result['rows']
                        entry['passed'] &= number is not None and float(result['rows'][0][0]) == number
                    else:
                        entry['passed'] &= 'plan_id' not in plan
                    item['cases'].append(entry)
                    print(model, name, entry['status'], entry['passed'], flush=True)
                report['models'].append(item)
                args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        finally:
            runtime.close()
    report['passed'] = all(x['connection_ok'] and all(y['passed'] for y in x['cases']) for x in report['models'])
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
