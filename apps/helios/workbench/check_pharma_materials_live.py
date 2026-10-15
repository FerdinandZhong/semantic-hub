"""Opt-in live document analysis and semantic proposal check in isolated state."""
import argparse
import base64
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'shared')]

from apps.helios.console.demo_hub import DemoHub
from helios_core.demo.builder_artifacts import BuilderArtifacts
from helios_core.demo.materials import MaterialLibrary, MaterialUpload, MaterialAnalyze, MaterialSuggest, MaterialReview, MaterialApply
from helios_core.demo.proposals import ProposalWorkspace
from helios_core.demo.registry import PackRegistry
from helios_core.demo.runtime import DemoRuntime
from helios_core.llm import LLMClient


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--token-file',type=Path,required=True)
    parser.add_argument('--document',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--proposal',action='store_true')
    parser.add_argument('--capture-public-evidence',action='store_true',
                        help='Save model requests and responses for public-document diagnostics.')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    llm=LLMClient('openai','gpt-4o',args.token_file.expanduser().read_text().strip(),
                  'https://api.openai.com/v1',max_tokens=8000,timeout=90)
    if args.capture_public_evidence:
        complete = llm.complete
        calls = []
        def captured_complete(system, user):
            answer = complete(system, user)
            calls.append({'system': system, 'request': json.loads(user), 'response': answer})
            (args.output/'model-calls.json').write_text(json.dumps(calls, indent=2))
            return answer
        llm.complete = captured_complete
    registry=PackRegistry(ROOT/'apps/helios/demo-packs.json',ROOT/'apps/helios-ds-generation/fixtures/sectors/v1')
    with tempfile.TemporaryDirectory(prefix='pharma-materials-') as temp:
        state=Path(temp)
        hub=DemoHub(registry,state,DemoRuntime(registry.load('pharma_intelligence'),state))
        try:
            library=MaterialLibrary(hub)
            item=library.upload(MaterialUpload(filename=args.document.name,content_base64=base64.b64encode(args.document.read_bytes()).decode()))
            print('Uploaded',item['chunk_count'],'chunks',flush=True)
            item=library.analyze(item['document_id'],MaterialAnalyze(revision=1),llm)
            claims=item['analysis']['claims']
            assert claims
            for claim in claims:
                assert claim['quote'] in next(c['text'] for c in item['chunks'] if c['id']==claim['chunk_id'])
            print('Verified',len(claims),'exact-quote claims',flush=True)
            item=library.suggest(item['document_id'],MaterialSuggest(revision=1))
            links=[link for link in item['links'] if link['source']=='pharma_intelligence']
            assert links,'No matching pharma intelligence targets'
            # This automated decision is isolated test evidence, never a user's approval.
            selected=links[:4]
            ids=[link['id'] for link in selected]
            library.review(item['document_id'],MaterialReview(revision=1,link_ids=ids,decision='approved',reviewer='Isolated automated test',note='Test-only attribution; no user model approval.'))
            library.apply(item['document_id'],MaterialApply(revision=1,link_ids=ids,source='pharma_intelligence',expected_revision=0))
            workspace=hub.runtime('pharma_intelligence').workspace
            draft=workspace.view()['draft']
            attachment=draft['definition']['document_attachments'][0]
            resolved=BuilderArtifacts(workspace).resolve([attachment])[0]
            assert len(resolved['semantic_links'])==len(selected)
            report={'status':'passed','model':'gpt-4o','input':str(args.document),'document_sha256':item['sha256'],
                    'chunks':item['chunk_count'],'claims':len(claims),'pharma_candidate_links':len(links),
                    'applied_test_targets':[link['target'] for link in selected],
                    'lineage_links':len(resolved['semantic_links']), 'user_state_modified':False}
            if args.proposal:
                print('Generating semantic definitions from structured schema and attached document evidence',flush=True)
                proposal=ProposalWorkspace(workspace).generate(draft['revision'],mode='llm',llm=llm)
                coverage=proposal['evidence']['document_coverage']
                assert 'attachment:'+attachment['id'] in coverage['selected_citations']
                assert workspace.view()['draft']['revision']==draft['revision']
                report['proposal']={'metrics':len(proposal['definition']['metrics']),
                                    'document_coverage':coverage,'warnings':proposal['warnings'],
                                    'applied':False,'metric_origins':proposal['metric_origins']}
                (args.output/'proposal.json').write_text(json.dumps(proposal,indent=2))
            assert workspace.view()['versions']==[]
            (args.output/'analysis.json').write_text(json.dumps(item['analysis'],indent=2))
            (args.output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report,indent=2),flush=True)
        finally:
            hub.close()


if __name__=='__main__':
    main()
