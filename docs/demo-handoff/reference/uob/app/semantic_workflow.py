"""Persistent drafts and immutable local releases; live validation uses Trino and Helios."""
import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import uuid
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from fastapi import HTTPException
from .connectors import ConnectionFailure, redact
from .source_workflow import SourceRequest, discover, identifier, SAMPLE_ROWS
from .semantics import compile_query, digest, execute_trino, validate_sql


def now():return datetime.now(timezone.utc).isoformat()
class Strict(BaseModel):model_config=ConfigDict(extra='forbid')
class BusinessContext(Strict):
    grain: str = Field(min_length=3,max_length=1000)
    units: str = Field(min_length=2,max_length=1000)
    time_rule: str = Field(min_length=3,max_length=1000)
    inclusion: str = Field(min_length=3,max_length=1000)
    exclusion: str = Field(min_length=3,max_length=1000)
class Metric(Strict):
    name: str = Field(pattern=r'^[a-z][a-z0-9_]{1,63}$')
    column: str = Field(max_length=128)
    aggregate: Literal['sum','avg','count','min','max']
    description: str = Field(min_length=3,max_length=1000)
class DraftCreate(Strict):
    mode: Literal['sample','live']
    catalog: str
    schema_name: str = Field(alias='schema')
    table: str
    name: str = Field(pattern=r'^[a-z][a-z0-9_]{1,63}$')
    context: BusinessContext
    meanings: dict[str,str] = Field(default_factory=dict)
    metric: Metric
class DraftUpdate(Strict):
    revision: int = Field(ge=1)
    context: BusinessContext
    meanings: dict[str,str]
    metric: Metric
class ValidateRequest(Strict):
    revision: int = Field(ge=1)
    reference_sql: str = Field(min_length=3,max_length=8000)
class PublishRequest(Strict):
    revision: int = Field(ge=1)
    release: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')
    reviewer: str = Field(min_length=3,max_length=200)
    confirmed: bool


def connection_signature(settings):
    fields=['trino_host','trino_port','trino_scheme','trino_user','trino_catalog','trino_schema','helios_path','trino_password','ca_bundle']
    return hashlib.sha256(json.dumps({k:getattr(settings,k) for k in fields},sort_keys=True).encode()).hexdigest()


def model_document(draft):
    spec=draft['definition'];metric=spec['metric'];columns=draft['columns']
    field_names={c['name'] for c in columns}
    if set(spec['meanings'])-field_names:raise ConnectionFailure('Column meanings must refer to discovered columns.')
    if metric['column'] not in field_names:raise ConnectionFailure('Select a discovered metric column.')
    column=next(c for c in columns if c['name']==metric['column'])
    if metric['aggregate'] in {'sum','avg'} and not re.match(r'(decimal|numeric|int|bigint|smallint|tinyint|double|real|float)',column['type'],re.I):
        raise ConnectionFailure('Sum and average require a numeric source column.')
    table=spec['table']
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}',table):raise ConnectionFailure('Choose a view with a simple table name for this first semantic workflow.')
    context='; '.join(k.replace('_',' ')+': '+v for k,v in spec['context'].items())
    fields=[]
    for col in columns:
        identifier(col['name'])
        typ=col['type'].lower()
        dtype=next((v for starts,v in [('decimal','Decimal'),('numeric','Decimal'),('bigint','Integer'),('int','Integer'),('smallint','Integer'),('double','Float'),('real','Float'),('boolean','Boolean'),('timestamp','DateTime'),('date','Date')] if typ.startswith(starts)),'String')
        fields.append({'name':col['name'],'datatype':dtype,'description':spec['meanings'].get(col['name'],'Needs business review.'),'expression':{'dialects':[{'dialect':'ANSI_SQL','expression':identifier(col['name'])}]},'dimension':{'is_time':dtype in {'Date','DateTime'}}})
    return {'version':'0.2.0.dev0','name':spec['name'],'description':context,'datasets':[{'name':table,'source':'.'.join([spec['catalog'],spec['schema'],table]),'description':context,'fields':fields}],
            'metrics':[{'name':metric['name'],'description':metric['description']+'; '+context,'expression':{'dialects':[{'dialect':'ANSI_SQL','expression':metric['aggregate'].upper()+'('+table+'.'+identifier(metric['column'])+')'}]}}],'relationships':[]}


def canonical_rows(rows):
    def value(v):
        if isinstance(v,(int,float,Decimal)) and not isinstance(v,bool):
            number=Decimal(str(v))
            if not number.is_finite():raise ConnectionFailure('Non-finite numeric results cannot be reconciled.')
            return str(number.normalize())
        return str(v) if v is not None else None
    return sorted(json.dumps({k:value(v) for k,v in row.items()},sort_keys=True) for row in rows)


def sample_execute(sql,doc):
    import sqlglot
    try:ast=sqlglot.parse_one(validate_sql(sql,doc),read='trino')
    except ConnectionFailure:raise
    except Exception:raise ConnectionFailure('Reference SQL is invalid or outside the allowed query scope.') from None
    for table in ast.find_all(sqlglot.exp.Table):table.set('catalog',None);table.set('db',None)
    with sqlite3.connect(':memory:') as conn:
        conn.row_factory=sqlite3.Row
        conn.execute('CREATE TABLE payments (customer_id TEXT, amount_sgd NUMERIC, jurisdiction TEXT, booking_date TEXT)')
        conn.executemany('INSERT INTO payments VALUES (:customer_id,:amount_sgd,:jurisdiction,:booking_date)',SAMPLE_ROWS)
        try:return [dict(r) for r in conn.execute(ast.sql(dialect='sqlite')).fetchmany(100)]
        except sqlite3.Error:raise ConnectionFailure('Sample reference SQL cannot run against the sample payment table.') from None


class SemanticWorkspace:
    def __init__(self,path):
        self.path=Path(path)
        self.lock=threading.RLock()
        self.data=json.loads(self.path.read_text()) if self.path.exists() else {'drafts':{},'releases':{}}

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix('.tmp')
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as handle:json.dump(self.data,handle)
        os.chmod(tmp,0o600);os.replace(tmp,self.path)

    def view(self):
        with self.lock:return copy.deepcopy(self.data)

    def draft(self,key,revision=None):
        with self.lock:
            if key not in self.data['drafts']:raise HTTPException(404,'Draft not found.')
            draft=copy.deepcopy(self.data['drafts'][key])
        if revision is not None and draft['revision']!=revision:raise HTTPException(409,'Draft changed. Reload it before continuing.')
        return draft

    def create(self,settings,request):
        spec=request.model_dump(by_alias=True)
        columns=discover(settings,SourceRequest(mode=request.mode,action='columns',catalog=request.catalog,schema=request.schema_name,table=request.table))['columns']
        draft={'id':str(uuid.uuid4()),'mode':request.mode,'revision':1,'definition':spec,'columns':columns,'validation':None,'created_at':now()}
        draft['document']=model_document(draft)
        with self.lock:self.data['drafts'][draft['id']]=draft;self.save()
        return copy.deepcopy(draft)

    def update(self,key,request):
        with self.lock:
            draft=self.draft(key,request.revision)
            draft['definition'].update(request.model_dump(exclude={'revision'}))
            draft['document']=model_document(draft)
            draft['revision']+=1;draft['validation']=None
            self.data['drafts'][key]=draft;self.save()
            return copy.deepcopy(draft)

    def validate(self,settings,key,request):
        draft=self.draft(key,request.revision);doc=draft['document'];spec=draft['definition']
        current=discover(settings,SourceRequest(mode=draft['mode'],action='columns',catalog=spec['catalog'],schema=spec['schema'],table=spec['table']))['columns']
        if current!=draft['columns']:raise ConnectionFailure('Source schema changed. Create a new draft from current source metadata.')
        metric=spec['metric']
        fixture_sha=None
        if draft['mode']=='sample' and settings.sample_finance_dir:
            from .sample_finance import Finance
            finance=Finance(settings)
            sql=compile_query(settings,doc,{'metrics':[metric['name']],'limit':100})
            compiled=finance.execute(sql,doc);reference=finance.execute(request.reference_sql,doc)
            compiler='Helios / offline synthetic DuckDB'
            fixture_sha=finance.manifest['database_sha256']
        elif draft['mode']=='sample':
            sql=validate_sql(f'SELECT {metric["aggregate"].upper()}({identifier(metric["column"])}) AS {identifier(metric["name"])} FROM iceberg.demo.payments',doc)
            compiled=sample_execute(sql,doc);reference=sample_execute(request.reference_sql,doc)
            compiler='Offline sample preview; no Helios or live source validation'
        else:
            sql=compile_query(settings,doc,{'metrics':[metric['name']],'limit':100})
            try:reference_sql=validate_sql(request.reference_sql,doc)
            except ConnectionFailure:raise
            except Exception:raise ConnectionFailure('Reference SQL is invalid or outside the allowed query scope.') from None
            compiled=execute_trino(settings,sql);reference=execute_trino(settings,reference_sql)
            compiler='Helios / Trino'
        if not compiled or not reference or len(compiled)>=100 or len(reference)>=100:
            raise ConnectionFailure('Validation requires non-empty results below the row limit.')
        matched=canonical_rows(compiled)==canonical_rows(reference)
        evidence={'passed':matched,'revision':draft['revision'],'document_sha256':digest(doc),'source_signature':connection_signature(settings),
                  'fixture_sha256':fixture_sha,
                  'checked_at':now(),'sql':sql,'reference_sql':request.reference_sql,'compiled_rows':len(compiled),'reference_rows':len(reference),'compiler':compiler,
                  'detail':'Results match the reference SQL.' if matched else 'Results differ from the reference SQL. Review the metric and business rules.'}
        with self.lock:
            self.draft(key,request.revision)
            self.data['drafts'][key]['validation']=evidence;self.save()
        return {**evidence,"compiled_result":redact(compiled),"reference_result":redact(reference)}

    def check_source(self,settings,definition,mode,columns):
        current=discover(settings,SourceRequest(mode=mode,action='columns',catalog=definition['catalog'],schema=definition['schema'],table=definition['table']))['columns']
        if current!=columns:raise ConnectionFailure('Source schema changed. Create and validate a new draft.')

    def publish(self,settings,key,request):
        snapshot=self.draft(key,request.revision)
        if not request.confirmed:raise HTTPException(422,'Confirm the business definitions and validation evidence before publishing.')
        if not snapshot['validation'] or not snapshot['validation']['passed']:
            raise HTTPException(409,'Validate the current draft successfully before publishing.')
        meanings=snapshot['definition']['meanings']
        if any(not meanings.get(c['name'],'').strip() or meanings.get(c['name'])=='Needs business review.' for c in snapshot['columns']):
            raise HTTPException(422,'Review the business meaning of every source column before publishing.')
        self.check_source(settings,snapshot['definition'],snapshot['mode'],snapshot['columns'])
        if snapshot['mode']=='sample' and settings.sample_finance_dir:
            from .sample_finance import Finance
            if snapshot['validation'].get('fixture_sha256')!=Finance(settings).manifest['database_sha256']:
                raise HTTPException(409,'Synthetic data changed. Validate the draft again before publication.')
        with self.lock:
            draft=self.draft(key,request.revision);validation=draft['validation']
            if not request.confirmed:raise HTTPException(422,'Confirm the business definitions and validation evidence before publishing.')
            if not validation or not validation['passed'] or validation['document_sha256']!=digest(draft['document']):
                raise HTTPException(409,'Validate the current draft successfully before publishing.')
            if draft['mode']=='live' and validation['source_signature']!=connection_signature(settings):
                raise HTTPException(409,'Source or compiler settings changed. Validate the draft again.')
            release_key=draft['definition']['name']+':'+request.release
            if release_key in self.data['releases']:raise HTTPException(409,'Release already exists. Use a new version.')
            release={'id':release_key,'model_id':draft['definition']['name'],'release':request.release,'mode':draft['mode'],
                     'document':copy.deepcopy(draft['document']),'sha256':digest(draft['document']),'reviewer':request.reviewer,
                     'published_at':now(),'validation':copy.deepcopy(validation),'definition':copy.deepcopy(draft['definition']), 'columns':copy.deepcopy(draft['columns'])}
            self.data['releases'][release_key]=release;self.save()
            return copy.deepcopy(release)

    def selected_sample(self,settings):
        from .sample_finance import Finance
        finance=Finance(settings)
        with self.lock:release=copy.deepcopy(self.data['releases'].get(self.data.get('sample_active')))
        if not release:raise ConnectionFailure('Publish and select a reviewed sample release in Build semantic context before querying financial data.')
        if release['mode']!='sample' or digest(release['document'])!=release['sha256']:
            raise ConnectionFailure('The selected sample release is invalid or its checksum changed.')
        if release['validation'].get('fixture_sha256')!=finance.manifest['database_sha256']:
            raise ConnectionFailure('The synthetic data changed. Validate, publish and select a new sample release.')
        return release

    def select_sample(self,settings,key):
        if not settings.sample_finance_dir:raise HTTPException(409,'Configure a synthetic financial artifact before selecting its sample release.')
        with self.lock:
            release=self.data['releases'].get(key)
            if not release:raise HTTPException(404,'Sample release not found.')
            if release['mode']!='sample':raise HTTPException(409,'Only sample releases can be selected for sample queries.')
            # Verify without changing the pointer on failure.
            from .sample_finance import Finance
            finance=Finance(settings)
            if digest(release['document'])!=release['sha256'] or release['validation'].get('fixture_sha256')!=finance.manifest['database_sha256']:
                raise HTTPException(409,'The sample release or its fixture binding changed. Publish a validated sample release.')
            self.data['sample_active']=key;self.save()
            return {'sample_active':key,'live_settings_changed':False}

    def activate(self,settings,registry,key):
        with self.lock:
            release=copy.deepcopy(self.data['releases'].get(key))
            if not release:raise HTTPException(404,'Release not found.')
            if release['mode']!='live':raise HTTPException(409,'Sample releases cannot be activated for live queries.')
            if release['validation']['source_signature']!=connection_signature(settings):raise HTTPException(409,'Connection settings changed. Validate and publish a new release before activation.')
            self.check_source(settings,release['definition'],release['mode'],release['columns'])
            directory=self.path.parent/'semantic-releases';directory.mkdir(parents=True,exist_ok=True)
            path=directory/(hashlib.sha256(key.encode()).hexdigest()+'.json')
            payload=json.dumps(release['document'],sort_keys=True)
            if path.exists() and digest(json.loads(path.read_text()))!=release['sha256']:raise HTTPException(409,'Published release file changed. Restore it before activation.')
            if not path.exists():
                fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,'w') as handle:handle.write(payload)
            registry.connections('data',{'semantic_file':str(path),'semantic_sha':release['sha256'],'semantic_version':release['release'],'semantic_id':release['model_id'],'alloydb_dsn':''})
            return {'active_release':key,'storage':'Local approved file','alloydb_override_cleared':True}
