"""Opt-in real vision/embedding check; all review and model creation use isolated state."""
import argparse
import base64
import copy
import io
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'shared')]

from apps.helios.console.demo_hub import DemoHub
from helios_core.demo.materials import MaterialLibrary, MaterialUpload, MaterialSuggest
from helios_core.demo.document_facts import MaterialVisual, MaterialFacts, FactRow
from helios_core.demo.registry import PackRegistry
from helios_core.demo.runtime import DemoRuntime
from helios_core.demo.context import ContextDefinition
from helios_core.demo.embeddings import EmbeddingClient
from helios_core.llm import LLMClient
from helios_core.demo import visual_documents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--token-file', type=Path, required=True)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scanned-only', action='store_true', help='Exercise an image-only PDF derived from the public FDA chart')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    validate = visual_documents._validate
    candidate_count = 0
    def capture_candidate(candidate, pages):
        nonlocal candidate_count
        candidate_count += 1
        path = args.output / f'public-extraction-candidate-{candidate_count}.json'
        try:
            result = validate(candidate, pages)
        except ValueError as exc:
            path.write_text(json.dumps({'candidate': candidate, 'validation_error': str(exc)}, indent=2))
            print('Extraction schema error:', str(exc), flush=True)
            raise
        path.write_text(json.dumps({'candidate': candidate, 'validation_error': None}, indent=2))
        return result
    visual_documents._validate = capture_candidate
    state = args.output/'isolated-state'
    registry = PackRegistry(ROOT/'apps/helios/demo-packs.json', ROOT/'apps/helios-ds-generation/fixtures/sectors/v1')
    hub = DemoHub(registry, state, DemoRuntime(registry.load('pharma_intelligence'), state))
    llm = LLMClient('openai', 'gpt-4o', args.token_file.read_text().strip(), 'https://api.openai.com/v1', max_tokens=8000, timeout=90)
    embedder = EmbeddingClient('text-embedding-3-small', llm.api_key, llm.base_url, timeout=90)
    calls = []
    embed = embedder.embed
    def record_embed(texts):
        calls.append(len(texts))
        return embed(texts)
    embedder.embed = record_embed
    library = MaterialLibrary(hub)
    results = []
    try:
        inputs = [('fda-hernexeos-trial-demographics-sex.png', [1]), ('efpia-industry-figures-2026.pdf', [4])]
        source_root = args.sources
        if args.scanned_only:
            from PIL import Image
            source_root = args.output
            filename = 'fda-hernexeos-scanned-chart.pdf'
            preview = visual_documents.render_visual_page(inputs[0][0], (args.sources/inputs[0][0]).read_bytes(), 1)
            with Image.open(io.BytesIO(preview)) as chart:
                chart.save(source_root/filename, format='PDF')
            inputs = [(filename, [1])]
        for filename, pages in inputs:
            print('Extracting', filename, 'pages', pages, flush=True)
            item = library.upload(MaterialUpload(filename=filename, content_base64=base64.b64encode((source_root/filename).read_bytes()).decode()))
            if args.scanned_only:
                assert not item['chunks'] and item['status']=='visual_pending'
            item = library.visual(item['document_id'], MaterialVisual(revision=1, pages=pages), llm)
            extraction = item['visual_extraction']
            (args.output/(Path(filename).stem+'-extraction.json')).write_text(json.dumps(extraction, indent=2))
            assert extraction['observations'], 'Expected chart observations'
            if filename.startswith('fda-'):
                values = {row['value'] for row in extraction['observations']}
                assert {72, 33, 31, 69}.issubset(values), values
                assert all(row['denominator'] is None for row in extraction['observations'])
                for label, value in [('male',33), ('female',72), ('male',31), ('female',69)]:
                    assert any(row['value']==value and re.search(r'\b'+label+r'\b',
                        row['entity']+' '+row['metric'], re.I) for row in extraction['observations']), (label,value)
            else:
                for label, value in [('us',74.1), ('europe',15.6), ('japan',3.6), ('pharmerging',2.9), ('rest',3.8)]:
                    assert any(row['value']==value and label in row['entity'].lower()
                               and row['extraction_kind']=='chart' for row in extraction['observations']), (label, extraction['observations'])
            print('Extracted', len(extraction['observations']), 'observations', flush=True)
            # Cache verification uses exactly this real extracted evidence.
            sample = [c['text'] for c in item['chunks'] if c.get('extraction_method')=='vision']
            vectors = library._vectors(embedder, sample)
            before = len(calls)
            assert vectors == library._vectors(embedder, sample)
            assert len(calls) == before
            # Retain at most 19 numeric rows so all generated metric references can be checked.
            selected = [row for row in extraction['observations'] if row['value'] is not None][:19]
            rows = [{k: row[k] for k in FactRow.model_fields} for row in selected]
            for row in rows:
                if not row['unit'].strip():
                    row['unit']='unspecified'
            created = library.facts(item['document_id'], MaterialFacts(revision=1, extraction_id=extraction['extraction_id'],
                title='Isolated test: ' + Path(filename).stem[:75], rows=rows, reviewer='Automated isolated acceptance',
                note='Test-only review to verify data flow; not a user approval or scientific validation.', acknowledged=True))
            runtime = hub.runtime(created['source'])
            definition = copy.deepcopy(runtime.workspace.view()['draft']['definition'])
            for metric in definition['metrics']:
                if metric['name']=='reviewed_observation_count':
                    metric['reference_sql']='SELECT COUNT(*) AS reviewed_observation_count FROM document_observations'
                else:
                    identity=metric['name'].removesuffix('_value')
                    metric['reference_sql']=f"SELECT value AS {metric['name']} FROM document_observations WHERE observation_id = '{identity}'"
            runtime.workspace.save(0, ContextDefinition.model_validate(definition))
            validation=runtime.workspace.validate(1)['draft']['validation']
            assert validation['passed'], validation
            assert runtime.workspace.view()['versions']==[]
            results.append({'input':filename,'pages':pages,'document_sha256':item['sha256'],
                            'observations':len(extraction['observations']),'created_source':created['source'],
                            'reviewed_test_rows':len(rows),'validated_metrics':len(definition['metrics']),
                            'embedding_dimensions':len(vectors[0]), 'repeat_embedding_calls':0,'status':'passed'})
        report={'model':'gpt-4o','embedding_model':'text-embedding-3-small','vector_storage':'Lance',
                'user_state_modified':False,'semantic_versions_published':0,'results':results}
        (args.output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)
    finally:
        hub.close()


if __name__=='__main__':
    main()
