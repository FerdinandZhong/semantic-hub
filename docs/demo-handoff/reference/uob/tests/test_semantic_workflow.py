"""Regression checks for source scope, draft gates, and semantic publication."""
import json
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
from app.connectors import ConnectionFailure
from app.source_workflow import SourceRequest, discover, SAMPLE_COLUMNS
from app.semantics import digest, load_model

HEAD={'Authorization':'Bearer operator'}
def settings():return Settings(api_token='operator',llm_url='',llm_model='',alloydb_dsn='',semantic_file='',trino_host='trino.fixture',trino_user='reader',helios_path=os.getenv('TEST_HELIOS_PATH',''))
def payload(mode='sample'):
    return {'mode':mode,'catalog':'iceberg','schema':'demo','table':'payments','name':'reviewed_payments',
            'context':{'grain':'One row per payment','units':'SGD','time_rule':'Booking date','inclusion':'All source view rows','exclusion':'No additional exclusions'},
            'meanings':{'customer_id':'Customer identifier','amount_sgd':'Payment amount in SGD','jurisdiction':'Booking jurisdiction','booking_date':'Payment booking date'},
            'metric':{'name':'total_outward_payments','column':'amount_sgd','aggregate':'sum','description':'Total payment amount'}}
REFERENCE='SELECT SUM(amount_sgd) AS total_outward_payments FROM iceberg.demo.payments'

def client(tmp_path):return TestClient(create_app(settings(),tmp_path/'settings.json'))

def create(c,mode='sample'):
    r=c.post('/api/semantic-workspace/drafts',json=payload(mode),headers=HEAD)
    assert r.status_code==200,r.text
    return r.json()

def validate(c,d,reference=REFERENCE):
    return c.post('/api/semantic-workspace/drafts/'+d['id']+'/validate',json={'revision':d['revision'],'reference_sql':reference},headers=HEAD)

def publish(c,d,confirmed=True):
    return c.post('/api/semantic-workspace/drafts/'+d['id']+'/publish',json={'revision':d['revision'],'release':'r1','reviewer':'Data owner','confirmed':confirmed},headers=HEAD)

def test_sample_onboarding_stays_offline(tmp_path,monkeypatch):
    def forbidden(*args):raise AssertionError('Sample made a live call')
    monkeypatch.setattr('app.source_workflow.execute_trino',forbidden)
    monkeypatch.setattr('app.semantic_workflow.execute_trino',forbidden)
    with client(tmp_path) as c:
        for action in ['columns','preview','profile']:
            r=c.post('/api/sources/discover',json={'mode':'sample','action':action,'catalog':'iceberg','schema':'demo','table':'payments'},headers=HEAD)
            assert r.status_code==200 and r.json()['synthetic']
        d=create(c);r=validate(c,d)
        assert r.status_code==200 and r.json()['passed'],r.text
        release=publish(c,d)
        assert release.status_code==200
        assert c.post('/api/semantic-workspace/releases/'+release.json()['id']+'/activate',json={},headers=HEAD).status_code==409
    with client(tmp_path) as c:assert len(c.get('/api/semantic-workspace',headers=HEAD).json()['releases'])==1


def test_source_queries_reject_injection_and_bound_reads(monkeypatch):
    queries=[]
    def fake(s,sql):
        queries.append(sql)
        if 'information_schema.columns' in sql:return [{'column_name':'amount_sgd','data_type':'decimal(18,2)'}]
        return [{'amount_sgd':2}]
    monkeypatch.setattr('app.source_workflow.execute_trino',fake)
    request=SourceRequest(mode='live',action='preview',catalog='iceberg',schema='demo',table='payments')
    assert discover(settings(),request)['rows']==[{'amount_sgd':2}]
    assert queries[-1].endswith('LIMIT 50')
    with pytest.raises(ConnectionFailure):discover(settings(),request.model_copy(update={'schema_name':"demo' OR 1=1 --"}))


def test_auth_origin_and_sample_errors(tmp_path):
    with client(tmp_path) as c:
        assert c.get('/api/semantic-workspace').status_code==401
        assert c.post('/api/semantic-workspace/drafts',json=payload()).status_code==401
        assert c.post('/api/semantic-workspace/drafts',json=payload(),headers={**HEAD,'Origin':'https://other.example'}).status_code==403
        r=c.post('/api/sources/discover',json={'mode':'sample','action':'preview','catalog':'private','schema':'demo','table':'payments'},headers=HEAD)
        assert r.status_code==503 and r.json()['sample_fallback'] is False


def test_review_and_validation_gates(tmp_path):
    with client(tmp_path) as c:
        d=create(c)
        assert publish(c,d).status_code==409
        r=validate(c,d,'SELECT COUNT(amount_sgd) AS total_outward_payments FROM iceberg.demo.payments')
        assert r.status_code==200 and not r.json()['passed']
        assert publish(c,d).status_code==409
        assert validate(c,d).json()['passed']
        assert publish(c,d,False).status_code==422
        assert publish(c,d).status_code==200
        assert publish(c,d).status_code==409
        values={k:d['definition'][k] for k in ['context','meanings','metric']}
        updated=c.post('/api/semantic-workspace/drafts/'+d['id'],json={'revision':1,**values},headers=HEAD).json()
        assert updated['revision']==2 and updated['validation'] is None
        assert publish(c,d).status_code==409
        assert publish(c,updated).status_code==409


def test_reference_sql_restrictions(tmp_path):
    with client(tmp_path) as c:
        d=create(c)
        for sql in ['DELETE FROM iceberg.demo.payments','SELECT * FROM other.private.payments', 'SELECT * FROM iceberg.demo.payments; DROP TABLE iceberg.demo.payments', 'SELECT ( FROM iceberg.demo.payments']:
            assert validate(c,d,sql).status_code==503
        assert publish(c,d).status_code==409


def test_incomplete_model_returns_controlled_error(tmp_path):
    path=tmp_path/'model.json';doc={'name':'bad','datasets':[{}]};path.write_text(json.dumps(doc))
    s=settings();s.semantic_file=str(path);s.semantic_sha=digest(doc);s.semantic_version='r1'
    with TestClient(create_app(s,tmp_path/'settings.json')) as c:
        r=c.get('/api/semantics',headers=HEAD)
        assert r.status_code==503 and 'Invalid Ossie' in r.json()['error']


def test_live_release_uses_real_compiler_and_preserves_old_active_context(tmp_path,monkeypatch):
    if not os.getenv('TEST_HELIOS_PATH'):pytest.skip('Reviewed Helios checkout required')
    def metadata(s,r):return {'columns':SAMPLE_COLUMNS}
    queries=[]
    def execute(s,sql):queries.append(sql);return [{'total_outward_payments':4900}]
    monkeypatch.setattr('app.semantic_workflow.discover',metadata)
    monkeypatch.setattr('app.semantic_workflow.execute_trino',execute)
    with client(tmp_path) as c:
        registry=c.app.state.registry
        registry.connections('data',{'semantic_file':'/previous/model.json','semantic_sha':'old','semantic_version':'old'})
        d=create(c,'live')
        assert registry.settings().semantic_version=='old'
        r=validate(c,d)
        assert r.status_code==200 and r.json()['passed'],r.text
        assert r.json()['compiler']=='Helios / Trino' and 'SUM(' in queries[0]
        release=publish(c,d);assert release.status_code==200,release.text
        assert registry.settings().semantic_version=='old'
        activate=c.post('/api/semantic-workspace/releases/'+release.json()['id']+'/activate',json={},headers=HEAD)
        assert activate.status_code==200,activate.text
        assert load_model(registry.settings())['name']=='reviewed_payments'
        registry.connections('data',{'trino_host':'changed.fixture'})
        assert c.post('/api/semantic-workspace/releases/'+release.json()['id']+'/activate',json={},headers=HEAD).status_code==409
        assert publish(c,d).status_code==409


def test_live_schema_change_blocks_validation(tmp_path,monkeypatch):
    monkeypatch.setattr('app.semantic_workflow.discover',lambda s,r:{'columns':SAMPLE_COLUMNS})
    with client(tmp_path) as c:
        d=create(c,'live')
        monkeypatch.setattr('app.semantic_workflow.discover',lambda s,r:{'columns':SAMPLE_COLUMNS[:-1]})
        assert 'schema changed' in validate(c,d).json()['error']
        assert publish(c,d).status_code==409


def test_schema_change_blocks_publication_after_passing_validation(tmp_path,monkeypatch):
    if not os.getenv('TEST_HELIOS_PATH'):pytest.skip('Reviewed Helios checkout required')
    monkeypatch.setattr('app.semantic_workflow.discover',lambda s,r:{'columns':SAMPLE_COLUMNS})
    monkeypatch.setattr('app.semantic_workflow.execute_trino',lambda s,sql:[{'total_outward_payments':4900}])
    with client(tmp_path) as c:
        d=create(c,'live');assert validate(c,d).json()['passed']
        monkeypatch.setattr('app.semantic_workflow.discover',lambda s,r:{'columns':SAMPLE_COLUMNS[:-1]})
        assert publish(c,d).status_code==503
        assert not c.app.state.semantic_workspace.view()['releases']


def test_unreviewed_columns_block_publication(tmp_path):
    with client(tmp_path) as c:
        values=payload();values['meanings']={}
        d=c.post('/api/semantic-workspace/drafts',json=values,headers=HEAD).json()
        assert validate(c,d).json()['passed']
        assert publish(c,d).status_code==422
