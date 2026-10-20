"""Published Semantic Hub contracts for remote agents; no drafting or implicit LLM calls."""
from __future__ import annotations
import json
import math
import threading
from collections import OrderedDict
import sqlglot
from sqlglot import exp
from helios_core.compiler import Compiler, SemanticRequest
from helios_core.retrieval.service import RetrievalService, Scope, export_studio_release
from helios_core.retrieval.index import SemanticIndex
from .registry import DemoError, canonical, digest
from .document_answers import passages
from .context import result_payload
from .agent.scope import check_scope, check_query_scope
from .lance_vectors import LanceVectorStore


class ConsumerService:
    def __init__(self, hub, settings):
        self.hub, self.settings = hub, settings
        self.retrieval = RetrievalService()
        self.indexes = OrderedDict()
        self.lock = threading.RLock()
        self.vectors = LanceVectorStore(hub.state_root / 'consumer-search.lance')

    def versions(self, model_id):
        runtime = self.hub.runtime(model_id)
        return {'model_id':model_id, **runtime.playground.catalog()}

    def models(self, query='', limit=20, offset=0):
        items=[]
        for source in self.hub.connections.list()['items']:
            if source['kind'] != 'local': continue
            versions=self.versions(source['id'])['versions']
            if not versions: continue
            if query and query.casefold() not in (source['id']+' '+source['name']+' '+versions[0]['title']).casefold(): continue
            items.append({'model_id':source['id'],'title':versions[0]['title'],
                          'source_kind':source['kind'],'published_versions':len(versions),
                          'latest_published':versions[0], 'status':'published'})
        items.sort(key=lambda v:v['model_id'])
        return {'items':items[offset:offset+limit], 'total':len(items),'offset':offset,'limit':limit,
                'scope':'Published semantic models only; drafts are excluded.'}

    def package(self, model_id, version, context_sha256=None):
        runtime=self.hub.runtime(model_id)
        package=export_studio_release(runtime.workspace,version)
        release=package['context']
        if context_sha256 and release['context_sha256'] != context_sha256:
            raise DemoError('Version context mismatch. Retrieve the selected published version again.')
        if release['snapshot_sha256'] != runtime.pack.fingerprint:
            raise DemoError('Published version does not match the available source snapshot.')
        return runtime,package

    def details(self, model_id,version,context_sha256=None):
        _,package=self.package(model_id,version,context_sha256)
        release=package['context'];artifacts=package['artifacts']
        return {'model_id':model_id,'version':version,'context_sha256':release['context_sha256'],
                'snapshot_sha256':release['snapshot_sha256'],'manifest':package['manifest'],
                'definition':release['definition'],'semantic_model':package['document'],
                'metadata':artifacts.get('metadata',{}),'ontology':artifacts.get('ontology',{}),
                'document_count':len(passages(release)), 'immutable':True}

    def adopt(self, model_id,version,context_sha256,principal):
        runtime,package=self.package(model_id,version,context_sha256)
        manifest=self.retrieval.register(model_id,version,package['document'],
            publication=package['manifest']['publication'],context_sha256=context_sha256)
        scope=Scope(principal,'consumer-published-v1',{model_id:manifest['release_id']},{model_id:None},
                    context=runtime.session_id)
        return runtime,package,scope

    def resolve(self, payload,principal):
        runtime,package,scope=self.adopt(payload.model_id,payload.version,payload.context_sha256,principal)
        required=list(payload.required_fields)
        metric=next((m for m in package['context']['definition']['metrics'] if m['name']==payload.metric),None)
        if metric:
            checked=check_scope(runtime,metric,payload.query,[])
            required=list(dict.fromkeys(required+[f['field'] for f in checked['filters']]))
        # An explicitly selected metric uses only its dependencies and requested fields.
        # Preserve []: converting it to None enables unrelated lexical field expansion.
        result=self.retrieval.resolve_context(payload.query,scope,model=payload.model_id,
            metric=payload.metric,required_fields=required if metric else required or None)
        if not metric and result['status']=='ready':
            chosen=result['bundle'].get('metrics',[])
            metric=next((m for m in package['context']['definition']['metrics'] if chosen and m['name']==chosen[0]['name']),None)
            if metric:
                checked=check_scope(runtime,metric,payload.query,[])
                required=list(dict.fromkeys(required+[f['field'] for f in checked['filters']]))
                result=self.retrieval.resolve_context(payload.query,scope,model=payload.model_id,
                    metric=metric['name'],required_fields=required)
        return result | {'model_id':payload.model_id,'version':payload.version,
                         'context_sha256':payload.context_sha256,
                         'snapshot_sha256':package['context']['snapshot_sha256'],
                         'notice':'Definitions and candidate evidence are not query results. Preserve all requested scope constraints.'}

    def coverage(self,payload):
        runtime,package=self.package(payload.model_id,payload.version,payload.context_sha256)
        metric=next((m for m in package['context']['definition']['metrics'] if m['name']==payload.metric),None)
        if not metric: raise DemoError('Unknown published metric.')
        return check_scope(runtime,metric,payload.question,[]) | {'model_id':payload.model_id,
            'version':payload.version,'context_sha256':payload.context_sha256,
            'metric':metric,'notice':'Temporal coverage only. The calling agent must also check population, geography, units, and aggregation.'}

    @staticmethod
    def fixed_scope_conflict(metric,filters):
        # Do not reinterpret a conditional metric as a different population.
        tree=sqlglot.parse_one(metric['expression'],read='duckdb')
        choices={}
        for case in tree.find_all(exp.Case):
            for branch in case.args.get('ifs',[]):
                condition=branch.this
                if list(condition.find_all(exp.Or)): continue
                for eq in condition.find_all(exp.EQ):
                    if isinstance(eq.this,exp.Column) and isinstance(eq.expression,exp.Literal):
                        choices.setdefault(eq.this.sql(),set()).add(str(eq.expression.this))
        for f in filters:
            known=choices.get(f['field'],set())
            if len(known)==1 and f['op']=='=' and str(f['value']) not in known:
                return f"The metric fixes {f['field']} to {next(iter(known))}. The requested filter cannot replace that definition."
        return None

    def query(self,payload,principal,execute=False):
        runtime,package,scope=self.adopt(payload.model_id,payload.version,payload.context_sha256,principal)
        request=payload.model_dump(include={'metrics','dimensions','filters','limit'})
        # Validate the supplied bundle before deriving or executing anything.
        self.retrieval.validate_request(payload.bundle_id,scope,request,model=payload.model_id)
        metric=next(m for m in package['context']['definition']['metrics'] if m['name']==payload.metrics[0])
        base={'model_id':payload.model_id,'version':payload.version,'context_sha256':payload.context_sha256,
              'snapshot_sha256':runtime.pack.fingerprint,'question':payload.question,'metric':metric}
        coverage=check_query_scope(runtime,metric,payload.question,request['filters'])
        if coverage['status']!='supported':
            return base | {'status':coverage['status'],'message':coverage['message'],'scope_check':coverage,'rows':[]}
        request['filters']=coverage['filters']
        bounded=self.retrieval.validate_request(payload.bundle_id,scope,request,model=payload.model_id)
        compiled=Compiler(bounded).compile(SemanticRequest.from_dict(request),dialect='duckdb')
        response=base | {'status':'ready','request':request,'sql':compiled.sql,'sql_sha256':digest(compiled.sql.encode()),
            'scope_check':coverage,'engine':'local_duckdb','bundle_id':payload.bundle_id,
            'notice':'The calling agent owns natural-language interpretation. This service validates a typed request against published definitions.'}
        if not execute:return response
        # Extra row reports truncation, never silently broadens the requested result limit.
        execution=Compiler(bounded).compile(SemanticRequest.from_dict(request|{'limit':payload.limit+1}),dialect='duckdb')
        data=result_payload(runtime.query_local(execution.sql,limit=payload.limit+1))
        truncated=len(data['rows'])>payload.limit;data['rows']=data['rows'][:payload.limit]
        self.package(payload.model_id,payload.version,payload.context_sha256)
        empty=not data['rows'] or all(all(v is None for v in row[len(payload.dimensions):]) for row in data['rows'])
        return response | data | {'status':'no_data' if empty else 'answered', 'truncated':truncated,
            'result_sha256':digest(canonical(data)), 'unit':metric['unit'],
            'message':'No matching value was returned. Missing data is not zero.' if empty else 'Result from the selected local source snapshot.'}

    def search(self,payload):
        if (payload.version or payload.context_sha256) and not payload.model_id:
            raise DemoError('A version or context hash requires model_id.')
        if payload.context_sha256 and not payload.version:
            raise DemoError('A context hash requires an explicit version.')
        if payload.model_id:
            versions=self.versions(payload.model_id)['versions']
            if not versions:raise DemoError('This model has no published version.')
            choices=[{'model_id':payload.model_id,'latest_published':versions[0]}] if not payload.version else [{'model_id':payload.model_id,'latest_published':{'version':payload.version}}]
        else:choices=self.models(limit=100)['items']
        records=[];lexical=[]
        for choice in choices:
            model_id=choice['model_id'];version=payload.version or choice['latest_published']['version']
            _,package=self.package(model_id,version,payload.context_sha256)
            sha=package['context']['context_sha256'];cache_key=(model_id,version,sha)
            with self.lock:
                if cache_key not in self.indexes:
                    self.indexes[cache_key]=SemanticIndex(package['document'])
                    while len(self.indexes)>128:self.indexes.popitem(last=False)
                index=self.indexes[cache_key]
                matches=index.search(payload.query,limit=payload.limit)
            binding={'model_id':model_id,'version':version,'context_sha256':sha}
            lexical.extend([binding|m for m in matches])
            if payload.mode=='embedding':
                definition=package['context']['definition']
                for m in definition['metrics']:
                    text=json.dumps({k:v for k,v in m.items() if k not in ('reference_sql','id')},ensure_ascii=False)
                    records.append(binding|{'kind':'metric','name':m['name'],'text':text})
                for d in package['document']['datasets']:
                    records.append(binding|{'kind':'dataset','name':d['name'],'text':d['name']+' '+d.get('description','')})
                    for f in d['fields']:
                        records.append(binding|{'kind':'field','name':d['name']+'.'+f['name'],
                            'text':d['name']+'.'+f['name']+' '+json.dumps(f,ensure_ascii=False)})
        if payload.mode=='keyword':
            return {'method':'keyword','items':sorted(lexical,key=lambda v:-v['score'])[:payload.limit],
                    'scope':'Selected published versions','notice':'Search relevance does not establish factual support.'}
        client=self.settings.client('embedding')
        if client is None:raise DemoError('Embedding search is unavailable. Configure an embedding model in Model configuration.')
        if len(records)>1000:raise DemoError('Embedding search exceeds the corpus budget. Select a specific model.')
        texts=[payload.query]+[r['text'] for r in records]
        if any(len(t)>16000 for t in texts):raise DemoError('A semantic record exceeds the embedding input budget.')
        vectors=self.vectors.vectors(client,texts)
        q=vectors[0]
        def cosine(v):
            den=math.sqrt(sum(x*x for x in q)*sum(x*x for x in v))
            return sum(a*b for a,b in zip(q,v))/den if den else 0.0
        found=[{k:v for k,v in r.items() if k!='text'}|{'score':cosine(v)} for r,v in zip(records,vectors[1:])]
        return {'method':'embedding','embedding_model':client.model,'storage':'Lance',
                'items':sorted(found,key=lambda v:-v['score'])[:payload.limit],
                'scope':'Selected published versions','notice':'Similarity ranks candidates. It does not prove facts or authorize a query.'}
