"""PDF layout whitespace can be recovered without accepting altered evidence."""
import base64
import json
from pathlib import Path

import pytest

from apps.helios.console.demo_hub import DemoHub
from helios_core.demo.materials import MaterialLibrary, MaterialUpload, MaterialAnalyze, grounded_quote
from helios_core.demo.registry import PackRegistry, DemoError
from helios_core.demo.runtime import DemoRuntime

ROOT=Path(__file__).resolve().parents[3]


def test_whitespace_recovery_keeps_exact_source_span():
    text='Share of new\nmedicines: 74.1% in 2020-2024.'
    assert grounded_quote('new medicines: 74.1%',text)=='new\nmedicines: 74.1%'
    assert grounded_quote('new medicines: 75.1%',text) is None
    assert grounded_quote('total market share: 74.1%',text) is None
    assert grounded_quote('2024-2020',text) is None
    assert grounded_quote('brain drain’.', 'brain drain’ .') == 'brain drain’ .'
    assert grounded_quote('105 patients', '10 5 patients') is None
    assert grounded_quote('10 5 patients', '105 patients') is None
    assert grounded_quote('jobs indirectly.', 'jobs indirectly — both upstream and downstream.') is None


@pytest.mark.parametrize('repair',[True,False])
@pytest.mark.parametrize('failure',['citation','schema'])
def test_repair_is_bounded_and_unsupported_claims_do_not_persist(tmp_path,repair,failure):
    registry=PackRegistry(ROOT/'apps/helios/demo-packs.json',ROOT/'apps/helios-ds-generation/fixtures/sectors/v1')
    hub=DemoHub(registry,tmp_path,DemoRuntime(registry.load('pharma_intelligence'),tmp_path))
    class Model:
        provider='test'
        model='test'
        calls=0
        def complete(self,system,user):
            self.calls+=1
            data=json.loads(user)
            chunk=data['chunks'][0]
            if self.calls==2:
                assert data['citation_errors' if failure=='citation' else 'validation_errors']
            valid = repair and self.calls==2
            return json.dumps({'summary':'Evidence','claims':[{'chunk_id':chunk['id'],
                    'quote':chunk['text'] if valid or failure=='schema' else 'Invented denominator of 999 patients.',
                    'statement':'Trial population scope.','kind':'source' if failure=='schema' and not valid else 'definition'}]})
    try:
        lib=MaterialLibrary(hub)
        item=lib.upload(MaterialUpload(filename='evidence.txt',content_base64=base64.b64encode(b'The original efficacy population contains 105 patients.').decode()))
        model=Model()
        if repair:
            result=lib.analyze(item['document_id'],MaterialAnalyze(revision=1),model)
            assert result['analysis']['claims'][0]['quote']==item['chunks'][0]['text']
        else:
            with pytest.raises(DemoError,match='unsupported citation' if failure=='citation' else 'invalid evidence'):
                lib.analyze(item['document_id'],MaterialAnalyze(revision=1),model)
            assert lib.detail(item['document_id'])['analysis'] is None
        assert model.calls==2
    finally:
        hub.close()
