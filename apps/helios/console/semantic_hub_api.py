"""Dedicated read-only published-model API for MCP and external agent consumers."""
from __future__ import annotations
import hashlib
import os
import secrets
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from helios_core.demo.registry import Contract, DemoError, PackRegistry
from helios_core.demo.playground import QueryShape
from helios_core.demo.consumer import ConsumerService
from helios_core.demo.runtime import DemoRuntime
from helios_core.demo.llm_settings import LLMSettings
from helios_core.demo.document_answers import passages
from helios_core.retrieval.service import RetrievalError
from helios_core.llm import LLMError
from .demo_hub import DemoHub

ROOT=Path(__file__).resolve().parents[3]
PREFIX='/api/semantic-hub/v1'


bearer=HTTPBearer(auto_error=False,scheme_name='ConsumerBearer')


def authorize(request:Request,credentials:HTTPAuthorizationCredentials|None=Depends(bearer)):
    # AMP traffic has already passed the authenticated CAI Application ingress.
    # Do not compare a caller's CAI key with the launching job's injected key.
    if getattr(request.app.state,'platform_auth',False):return 'cai-ingress'
    if request.app.state.local_no_auth:return 'local-demo'
    expected=os.environ.get('SEMANTIC_HUB_API_TOKEN','')
    if not expected:raise HTTPException(503,{'code':'api_not_configured','message':'Configure a consumer API token.'})
    supplied=request.headers.get('Authorization','')
    if not secrets.compare_digest(supplied,'Bearer '+expected):
        raise HTTPException(401,{'code':'unauthorized','message':'A valid consumer bearer token is required.'},headers={'WWW-Authenticate':'Bearer'})
    return 'consumer:'+hashlib.sha256(expected.encode()).hexdigest()


router=APIRouter(prefix=PREFIX,tags=['semantic-hub-consumer'],dependencies=[Depends(authorize)])


def service(request):return request.app.state.semantic_hub_consumer


class Pin(Contract):
    model_id:str=Field(min_length=1,max_length=100)
    version:str=Field(min_length=1,max_length=40)
    context_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')


class Search(Contract):
    query:str=Field(min_length=1,max_length=4000)
    model_id:str|None=Field(default=None,max_length=100)
    version:str|None=Field(default=None,max_length=40)
    context_sha256:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')
    mode:Literal['keyword','embedding']='keyword'
    limit:int=Field(default=10,ge=1,le=20)


class Resolve(Pin):
    query:str=Field(min_length=1,max_length=4000)
    metric:str|None=Field(default=None,max_length=128)
    required_fields:list[str]=Field(default_factory=list,max_length=100)


class Coverage(Pin):
    metric:str=Field(min_length=1,max_length=128)
    question:str=Field(min_length=1,max_length=2000)


class TypedQuery(Pin,QueryShape):
    bundle_id:str=Field(min_length=1,max_length=128)
    question:str=Field(min_length=1,max_length=2000)
    limit:int=Field(default=100,ge=1,le=100)


@router.get('/capabilities')
def capabilities(request:Request):
    s=service(request)
    return {'service':'Semantic Hub','api_version':'v1','role':'Published semantic context for external agents',
        'search':{'keyword':True,'embedding':s.settings.client('embedding') is not None,'embedding_storage':'Lance'},
        'version_pinning':True,'bundle_ttl_seconds':300,'execution':{'engine':'local_duckdb','max_rows':100,'arbitrary_sql':False},
        'authorization':('CAI Application ingress; project access, all published models; no per-model grants.' if getattr(request.app.state,'platform_auth',False) else 'Local demo without authentication; all published models.' if request.app.state.local_no_auth else 'Shared read-only demo token; all published models in this workspace. No per-user grants.'),
        'capabilities':['inventory','versions','definitions','metadata','ontology','lineage','published_documents','search','resolve','coverage','compile','sample_query'],
        'limitations':['No model editing or publication','No live enterprise query engine','Calling agent owns natural-language interpretation']}


@router.get('/models')
def models(request:Request,q:str=Query(default='',max_length=4000),limit:int=Query(default=20,ge=1,le=100),offset:int=Query(default=0,ge=0)):
    return service(request).models(q,limit,offset)


@router.get('/models/{model_id}')
def model(request:Request,model_id:str):
    s=service(request);versions=s.versions(model_id)
    if not versions['versions']:raise HTTPException(404,{'code':'not_published','message':'No published model is available.'})
    runtime=s.hub.runtime(model_id)
    return {'model_id':model_id,'title':versions['versions'][0]['title'],'versions':versions['versions'],
            'active_version':versions['active_version'], 'source':{'kind':'local','origin':runtime.pack.entry.data_origin,
            'snapshot_sha256':runtime.pack.fingerprint,'timezone':runtime.pack.entry.timezone,'adapter':'local_duckdb'},
            'notice':'Connection credentials and unpublished drafts are excluded.'}


@router.get('/models/{model_id}/versions')
def versions(request:Request,model_id:str):return service(request).versions(model_id)


@router.get('/models/{model_id}/versions/{version}')
def version_detail(request:Request,model_id:str,version:str,context_sha256:str|None=None):
    return service(request).details(model_id,version,context_sha256)


@router.get('/models/{model_id}/versions/{version}/graph')
def graph(request:Request,model_id:str,version:str,context_sha256:str|None=None):
    runtime,package=service(request).package(model_id,version,context_sha256)
    return {'model_id':model_id,'version':version,'context_sha256':package['context']['context_sha256'],
            'graph':runtime.workspace.source_graph(version),'notice':'Declared and SQL-derived lineage, not observed engine execution.'}


@router.get('/models/{model_id}/versions/{version}/documents')
def documents(request:Request,model_id:str,version:str,context_sha256:str|None=None):
    _,package=service(request).package(model_id,version,context_sha256)
    items=passages(package['context'])
    if len(str(items))>100000:raise HTTPException(413,{'code':'evidence_budget','message':'Published evidence exceeds this consumer response budget.'})
    return {'model_id':model_id,'version':version,'context_sha256':package['context']['context_sha256'],
            'items':items,'total':len(items),'artifact_sha256':package['artifacts']['artifact_sha256'],
            'notice':'Only linked passages frozen in this publication. Original preview links refer to the local Studio and may be unavailable remotely.'}


@router.post('/search')
def search(payload:Search,request:Request):return service(request).search(payload)


@router.post('/resolve')
def resolve(payload:Resolve,request:Request,principal=Depends(authorize)):
    return service(request).resolve(payload,principal)


@router.post('/coverage')
def coverage(payload:Coverage,request:Request):return service(request).coverage(payload)


@router.post('/compile')
def compile_query(payload:TypedQuery,request:Request,principal=Depends(authorize)):
    return service(request).query(payload,principal)


@router.post('/query')
def query(payload:TypedQuery,request:Request,principal=Depends(authorize)):
    return service(request).query(payload,principal,execute=True)


def create_application(hub=None,settings=None,*,local_no_auth=False,platform_auth=False):
    if platform_auth and (local_no_auth or not all(os.environ.get(k) for k in ('CDSW_APP_PORT','CDSW_PROJECT_ID','CDSW_DOMAIN'))):
        raise ValueError('Platform authentication requires an authenticated CAI Application environment.')
    owns_hub=hub is None
    if owns_hub:
        state=Path(os.environ.get('HELIOS_DEMO_STATE',ROOT/'state/demo'))
        registry=PackRegistry(Path(os.environ.get('HELIOS_DEMO_REGISTRY',ROOT/'apps/helios/demo-packs.json')),
            Path(os.environ.get('HELIOS_DEMO_FIXTURES',ROOT/'apps/helios-ds-generation/fixtures/sectors/v1')))
        runtime=DemoRuntime(registry.load(os.environ.get('HELIOS_DEMO_DATASET','power')),state)
        hub=DemoHub(registry,state,runtime)
    settings=settings or LLMSettings(hub.state_root)
    @asynccontextmanager
    async def lifespan(app):
        yield
        if owns_hub:hub.close()
    app=FastAPI(title='Semantic Hub consumer API',version='1.0',docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
    app.state.local_no_auth=local_no_auth
    app.state.platform_auth=platform_auth
    app.state.semantic_hub_consumer=ConsumerService(hub,settings)
    app.include_router(router)
    app.mount('/docs/assets',StaticFiles(directory=Path(__file__).parent/'static/swagger'),name='swagger-assets')
    @app.get('/docs',include_in_schema=False,response_class=HTMLResponse)
    def docs():
        content=(Path(__file__).parent/'templates/semantic-hub-api-docs.html').read_text().replace('__LOCAL_NO_AUTH__','true' if local_no_auth or platform_auth else 'false')
        if platform_auth:
            content=content.replace('Local demo access. No consumer token is required.','CAI Application access. Your Workbench session authenticates this page.')
        return content
    @app.get(PREFIX+'/docs',include_in_schema=False)
    def docs_alias():return RedirectResponse('/docs')
    @app.get(PREFIX+'/openapi.json',dependencies=[Depends(authorize)],include_in_schema=False)
    def schema():
        spec=app.openapi()
        if local_no_auth or platform_auth:
            import copy
            spec=copy.deepcopy(spec)
            spec.get('components',{}).pop('securitySchemes',None)
            for operations in spec['paths'].values():
                for operation in operations.values():
                    if isinstance(operation,dict):operation.pop('security',None)
        return spec
    async def domain_error(request,exc):
        return JSONResponse({'error':{'code':'semantic_contract_rejected','message':str(exc),'retryable':False}},status_code=409)
    app.add_exception_handler(DemoError,domain_error)
    app.add_exception_handler(RetrievalError,domain_error)
    @app.exception_handler(LLMError)
    async def provider_error(request,exc):
        return JSONResponse({'error':{'code':'embedding_unavailable','message':'The configured embedding provider is unavailable.','retryable':True}},status_code=503)
    @app.middleware('http')
    async def no_store(request,call_next):
        response=await call_next(request);response.headers['Cache-Control']='no-store';return response
    return app
