"""Source-derived pharma scope, typed SQL, provenance, and document lineage."""
import base64
import copy
import csv
import io
import json
from decimal import Decimal
from pathlib import Path

import pytest

from apps.helios.console.demo_hub import DemoHub
from helios_core.compiler import Compiler, SemanticRequest
from helios_core.demo.builder_artifacts import BuilderArtifacts
from helios_core.demo.context import ContextDefinition, ContextWorkspace
from helios_core.demo.local import LocalPackEngine
from helios_core.demo.materials import MaterialLibrary, MaterialUpload, MaterialSuggest, MaterialReview, MaterialApply
from helios_core.demo.registry import PackRegistry, DemoError, canonical, digest
from helios_core.demo.runtime import DemoRuntime
from helios_core.ossie.model import SemanticModel

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / 'apps/helios-ds-generation/fixtures/sectors/v1'
REGISTRY = ROOT / 'apps/helios/demo-packs.json'


def registry():
    return PackRegistry(REGISTRY, FIXTURES)


def rows(pack):
    return {t.name:list(csv.DictReader(io.StringIO(t.csv_bytes.decode()))) for t in pack.tables}


def test_existing_pack_fingerprints_are_unchanged():
    entries = json.loads(REGISTRY.read_text())['packs']
    for entry in entries:
        if entry['id'] == 'pharma_intelligence':
            continue
        expected = digest(canonical({'contract':'helios.demo-snapshot.v1', 'entry':entry}))
        assert registry().load(entry['id']).fingerprint == expected


def test_curated_scope_denominators_and_source_boundaries():
    pack = registry().load('pharma_intelligence')
    data = rows(pack)
    assert not pack.synthetic
    assert len(data['drugs']) == len(data['approval_events']) == 46
    assert {r['approval_date'][:4] for r in data['approval_events']} == {'2025'}
    assert sum(int(r['patient_count']) for r in data['trial_cohorts']) == 105
    for dimension in {r['dimension'] for r in data['trial_demographics']}:
        assert sum(int(r['patient_count']) for r in data['trial_demographics'] if r['dimension']==dimension) == 105
    denominators = {r['result_id']:int(r['denominator_count']) for r in data['trial_results']}
    assert denominators == {'beamion_no_prior_adc_orr':71, 'beamion_no_prior_adc_dor_ge_6_months':53,
                            'beamion_prior_adc_orr':34, 'beamion_prior_adc_dor_ge_6_months':15}
    assert sum(Decimal(r['value']) for r in data['industry_observations']) == 100
    assert {r['geography']: Decimal(r['value']) for r in data['industry_observations']} == {
        'USA': Decimal('74.1'), 'Europe (Top 5)': Decimal('15.6'), 'Japan': Decimal('3.6'),
        'Pharmerging': Decimal('2.9'), 'Rest of the World': Decimal('3.8'),
    }
    assert all('2021-2025' not in r['source_quality_note'] for r in data['industry_observations'])
    assert {(r['period_start'],r['period_end']) for r in data['industry_observations']} == {('2020','2024')}
    assert any(r['source_quality_note'] for r in data['trials'])
    assert all('Press Release' not in r['approved_use'] for r in data['approval_events'])
    assert all(d['sha256'] and d['source_url'].startswith('https://') for d in data['source_documents'])
    assert not set(data) & {'batches','lab_results','patients'}
    assert registry().load('pharma').synthetic


def test_all_metrics_compile_reconcile_and_validate(tmp_path):
    pack = registry().load('pharma_intelligence')
    workspace = ContextWorkspace(pack,tmp_path)
    definition = workspace.seed()
    references = json.loads((FIXTURES/'pharma_intelligence/evaluation/references.json').read_text())
    by_name = {r['metric']:r for r in references}
    model = SemanticModel(workspace.build_model(ContextDefinition.model_validate(definition)))
    engine = LocalPackEngine(pack)
    try:
        for metric in definition['metrics']:
            reference = by_name[metric['name']]
            sql = Compiler(model).compile(SemanticRequest.from_dict({'metrics':[metric['name']]}),dialect='trino').sql
            result = engine.query(sql).rows[0][0]
            assert Decimal(str(result)) == Decimal(reference['expected'])
            assert Decimal(str(engine.query(reference['reference_sql']).rows[0][0])) == Decimal(str(result))
            metric['reference_sql'] = reference['reference_sql']
        assert definition['field_roles']['industry_observations.period_start'] == 'time'
        assert definition['glossary_terms']
        assert all(m['evidence_refs'] for m in definition['metrics'])
        workspace.save(0,ContextDefinition.model_validate(definition))
        validation = workspace.validate(1)['draft']['validation']
        assert validation['passed'], validation
        assert workspace.view()['versions'] == []
    finally:
        engine.close()


def test_document_matching_and_apply_keeps_sql_and_review_separate(tmp_path):
    reg=registry()
    hub=DemoHub(reg,tmp_path,DemoRuntime(reg.load('pharma_intelligence'),tmp_path))
    try:
        library=MaterialLibrary(hub)
        source=FIXTURES/'pharma_intelligence/serving/documents/trial_denominators.md'
        item=library.upload(MaterialUpload(filename=source.name,content_base64=base64.b64encode(source.read_bytes()).decode()))
        item=library.suggest(item['document_id'],MaterialSuggest(revision=1))
        links=[l for l in item['links'] if l['source']=='pharma_intelligence']
        assert links
        payload=MaterialApply(revision=1,link_ids=[links[0]['id']],source='pharma_intelligence',expected_revision=0)
        with pytest.raises(DemoError,match='approved links'):
            library.apply(item['document_id'],payload)
        workspace=hub.runtime('pharma_intelligence').workspace
        before=copy.deepcopy(workspace.seed()['metrics'])
        library.review(item['document_id'],MaterialReview(revision=1,link_ids=[links[0]['id']],decision='approved',reviewer='Test only',note='Verified source scope and denominator.'))
        library.apply(item['document_id'],payload)
        draft=workspace.view()['draft']['definition']
        assert draft['metrics']==before
        attachment=draft['document_attachments'][0]
        resolved=BuilderArtifacts(workspace).resolve([attachment])[0]
        assert resolved['semantic_links'][0]['target']==links[0]['target']
        assert resolved['semantic_links'][0]['quote'] in resolved['content']
        assert workspace.view()['versions']==[]
        # Source briefs are evidence, not independent patient observations.
        assert '53 responders' in resolved['content']
    finally:
        hub.close()


def test_pack_generation_is_deterministic_and_foreign_keys_fail_closed(tmp_path):
    from helios_ds.sector_demo.pharma_intelligence import write_pack
    facts=ROOT/'apps/helios-ds-generation/fixtures/source_facts/pharma_intelligence.json'
    first=write_pack(tmp_path,facts)
    assert first==write_pack(tmp_path,facts)
    assert first==next(e for e in json.loads(REGISTRY.read_text())['packs'] if e['id']=='pharma_intelligence')
    bad=json.loads(facts.read_text())
    bad['tables']['trial_results'][0]['cohort_id']='invented_cohort'
    bad_path=tmp_path/'bad.json';bad_path.write_text(json.dumps(bad))
    with pytest.raises(ValueError,match='Unresolved source relationship'):
        write_pack(tmp_path/'bad-pack',bad_path)


def test_public_source_provenance_cannot_be_missing(tmp_path):
    import shutil
    fixtures=tmp_path/'fixtures'
    shutil.copytree(FIXTURES/'pharma_intelligence',fixtures/'pharma_intelligence')
    path=fixtures/'pharma_intelligence/manifest.json'
    manifest=json.loads(path.read_text());manifest['source_inputs']=[]
    path.write_text(json.dumps(manifest))
    entry=next(e for e in json.loads(REGISTRY.read_text())['packs'] if e['id']=='pharma_intelligence')
    entry['manifest_sha256']=digest(path.read_bytes())
    regpath=tmp_path/'registry.json';regpath.write_text(json.dumps({'schema':'helios.demo-registry.v1','packs':[entry]}))
    with pytest.raises(DemoError,match='source provenance'):
        PackRegistry(regpath,fixtures).load('pharma_intelligence')
