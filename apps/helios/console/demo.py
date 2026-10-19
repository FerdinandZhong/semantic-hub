"""Optional local demo routes hosted by the existing Helios console."""

from __future__ import annotations

import logging
import os
import re
from copy import copy
from typing import Literal
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from helios_core.demo.context import (
    SaveContext,
    ValidateContext,
    ReviewContext,
    ActivateContext,
    BatchReview,
    PublishContext,
    RestoreContext,
    ContextBinding,
    ContextDefinition,
)
from helios_core.demo.proposals import ApplyProposal, GenerateProposal, ProposalWorkspace
from helios_core.demo.builder_artifacts import BuilderArtifacts
from helios_core.llm import llm_from_env
from helios_core.llm.client import LLMError
import httpx
from helios_core.demo.registry import DemoError, PackRegistry
from helios_core.demo.runtime import DemoRuntime, ExampleRequest
from helios_core.retrieval.service import RetrievalError, export_studio_release
from helios_core.demo.connections import ConnectionCreate, ConnectionUpdate, connection_schemas
from .demo_hub import DemoHub
from helios_core.demo.llm_settings import LLMSettings, LLMSettingsSave
from helios_core.demo.playground import Question, RunPlan
from helios_core.demo.materials import (MaterialLibrary, MaterialUpload, MaterialAnalyze,
    MaterialSuggest, MaterialReview, MaterialApply)
from helios_core.demo.query_explanation import ExplainExample, explain_example
from helios_core.demo.document_facts import MaterialVisual, MaterialFacts

LOGGER = logging.getLogger(__name__)
HERE = Path(__file__).parent
ROOT = HERE.parents[2]
demo_router = APIRouter(prefix="/demo", tags=["local-demo"])


def runtime_for(request: Request) -> DemoRuntime:
    runtime = getattr(request.app.state, "demo_runtime", None)
    if runtime is None:
        raise HTTPException(404, "No local demo pack selected")
    hub = getattr(request.app.state, "demo_hub", None)
    if hub is not None:
        try:
            return hub.runtime(request.query_params.get("source") or hub.default_source)
        except DemoError as exc:
            raise HTTPException(409, str(exc)) from None
    return runtime


@demo_router.get("")
def demo_page(request: Request):
    hub_for(request)
    return FileResponse(HERE / "templates" / "demo-hub.html")


@demo_router.get("/query")
def query_page(request: Request):
    runtime_for(request)
    return FileResponse(HERE / "templates" / "demo.html")


def hub_for(request):
    hub = getattr(request.app.state, "demo_hub", None)
    if hub is None:
        raise HTTPException(404, "Semantic workspace is not configured")
    return hub


def settings_for(request):
    hub_for(request)
    return request.app.state.demo_llm_settings


def purpose_llm(request, purpose):
    llm = settings_for(request).client(purpose, llm_from_env)
    if llm is not None and purpose == 'query':
        llm = copy(llm)
        llm.max_tokens = min(getattr(llm, 'max_tokens', 600), 600)
    return llm


@demo_router.get('/llm')
def llm_page(request: Request):
    hub_for(request)
    return FileResponse(HERE / 'templates' / 'demo-llm.html')


@demo_router.get('/api/llm')
def llm_settings_view(request: Request):
    return settings_for(request).view(llm_from_env)


@demo_router.post('/api/llm')
def llm_settings_save(payload: LLMSettingsSave, request: Request):
    try:
        return settings_for(request).save(payload, llm_from_env)
    except DemoError as exc:
        raise HTTPException(409, str(exc)) from None


class TestLLM(BaseModel):
    model_config = ConfigDict(extra='forbid')
    purpose: Literal['draft', 'query', 'embedding']


@demo_router.post('/api/llm/test')
def llm_test(payload: TestLLM, request: Request):
    try:
        llm = purpose_llm(request, payload.purpose)
        if llm is None:
            raise DemoError('This LLM profile is disabled or has no available credential.')
        if payload.purpose == 'embedding':
            vectors = llm.embed(['Semantic Hub connection test'])
            return {'ok': True, 'provider': llm.provider, 'model': llm.model,
                    'dimensions': len(vectors[0]), 'message': f'The saved embedding model returned a {len(vectors[0])}-dimension vector.'}
        llm = copy(llm)
        llm.max_tokens = 32
        response = llm.complete('Reply with OK.', 'Connection test. Reply with OK.')
        if not isinstance(response, str) or not response.strip():
            raise DemoError('The provider returned an empty response.')
        return {'ok': True, 'provider': llm.provider, 'model': llm.model, 'message': 'The saved model responded successfully.'}
    except DemoError as exc:
        raise HTTPException(409, str(exc)) from None
    except LLMError as exc:
        cause=exc.__cause__
        message='The model request failed. Check the saved endpoint, model, and authentication.'
        if isinstance(cause,httpx.HTTPStatusError):
            status=cause.response.status_code
            messages={401:'The model provider rejected the saved API key.',403:'The model provider denied access to this model.',
                      404:'The model or API endpoint was not found.',429:'The model provider reported a rate or quota limit.'}
            message=messages.get(status,f'The model provider rejected the request (HTTP {status}).')
            if status==400:
                try:parameter=cause.response.json().get('error',{}).get('param')
                except (ValueError,AttributeError):parameter=None
                if parameter in ('max_tokens','max_completion_tokens','temperature','model','reasoning_effort'):
                    message+=f' Check compatibility of the {parameter} parameter.'
        raise HTTPException(502,message) from None
    except Exception:
        raise HTTPException(502, 'The LLM request failed. Check the saved endpoint, model, and credential reference.') from None


@demo_router.get('/materials')
def materials_page(request: Request):
    hub_for(request)
    return FileResponse(HERE / 'templates' / 'demo-materials.html')


def materials_for(request):
    hub_for(request)
    return request.app.state.demo_materials


def material_action(request, action):
    try:
        return action(materials_for(request))
    except DemoError as exc:
        raise HTTPException(409, str(exc)) from None
    except Exception:
        # Provider exceptions can contain document text, endpoints, or credentials.
        raise HTTPException(502, 'Supporting material processing failed. Check model configuration and try again.') from None


@demo_router.get('/api/materials')
def materials_catalog(request: Request):
    return materials_for(request).catalog() | {'embedding_ready': bool(purpose_llm(request, 'embedding'))}


@demo_router.post('/api/materials/upload')
def material_upload(payload: MaterialUpload, request: Request):
    item = material_action(request, lambda library: library.upload(payload))
    # ponytail: auto-OCR covers the first 6 image pages (the visual request limit); analyze later pages manually.
    pages = (item.get('visual_source') or {}).get('ocr_pages', [])[:6]
    if not pages:
        return item
    llm = purpose_llm(request, 'draft')
    if llm is None:
        return item | {'ocr_notice': 'Scanned pages need AI transcription. Configure a vision-capable draft model, then analyze pages.'}
    try:
        item = materials_for(request).visual(item['document_id'], MaterialVisual(revision=item['revision'], pages=pages), llm)
    except DemoError as exc:
        return item | {'ocr_notice': f'Automatic transcription did not run: {exc} Analyze pages manually.'}
    except Exception:
        # Provider exceptions can contain document text, endpoints, or credentials. The upload itself is kept.
        return item | {'ocr_notice': 'Automatic transcription failed. Check the draft model configuration, then analyze pages manually.'}
    return item | {'ocr_notice': f"AI transcribed page(s) {', '.join(map(str, pages))}. Verify each transcript against the original page."}


@demo_router.get('/api/materials/{document_id}')
def material_detail(document_id: str, request: Request, revision: int | None = None):
    return material_action(request, lambda library: library.detail(document_id, revision))


@demo_router.post('/api/materials/{document_id}/analyze')
def material_analyze(document_id: str, payload: MaterialAnalyze, request: Request):
    return material_action(request, lambda library: library.analyze(document_id, payload, purpose_llm(request, 'draft')))


@demo_router.get('/api/materials/{document_id}/preview')
def material_preview(document_id: str, request: Request, revision: int, page: int = 1):
    return material_action(request, lambda library: Response(library.preview(document_id, revision, page), media_type='image/png',
                                                           headers={'Cache-Control': 'no-store'}))


@demo_router.post('/api/materials/{document_id}/visual')
def material_visual(document_id: str, payload: MaterialVisual, request: Request):
    return material_action(request, lambda library: library.visual(document_id, payload, purpose_llm(request, 'draft')))


@demo_router.post('/api/materials/{document_id}/facts')
def material_facts(document_id: str, payload: MaterialFacts, request: Request):
    return material_action(request, lambda library: library.facts(document_id, payload))


@demo_router.post('/api/materials/{document_id}/suggest')
def material_suggest(document_id: str, payload: MaterialSuggest, request: Request):
    return material_action(request, lambda library: library.suggest(document_id, payload,
        purpose_llm(request, 'embedding') if payload.use_embeddings else None))


@demo_router.post('/api/materials/{document_id}/review')
def material_review(document_id: str, payload: MaterialReview, request: Request):
    return material_action(request, lambda library: library.review(document_id, payload))


@demo_router.post('/api/materials/{document_id}/apply')
def material_apply(document_id: str, payload: MaterialApply, request: Request):
    return material_action(request, lambda library: library.apply(document_id, payload))


@demo_router.get("/api/hub")
def hub_catalog(request: Request):
    return hub_for(request).catalog()


@demo_router.get("/api/hub/source")
def hub_source(request: Request, source: str):
    try:
        return hub_for(request).source(source)
    except DemoError as exc:
        raise HTTPException(404, str(exc)) from None


@demo_router.get("/api/connections/schema")
def connection_schema(request: Request):
    hub_for(request)
    return connection_schemas()


@demo_router.post("/api/connections")
def create_connection(payload: ConnectionCreate, request: Request):
    try:
        return hub_for(request).connections.create(payload)
    except DemoError as exc:
        raise HTTPException(409, str(exc)) from None
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_input=False, include_context=False, include_url=False)) from None


class UpdateConnection(ConnectionUpdate):
    id: str = Field(min_length=1, max_length=100)
    kind: str


@demo_router.post("/api/connections/update")
def update_connection(payload: UpdateConnection, request: Request):
    try:
        store = hub_for(request).connections
        if store.get(payload.id)['kind'] != payload.kind:
            raise DemoError('Connection type cannot change; configure a new connection')
        return store.update(payload.id, ConnectionUpdate.model_validate(payload.model_dump(exclude={'id', 'kind'})))
    except DemoError as exc:
        raise HTTPException(409, str(exc)) from None
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_input=False, include_context=False, include_url=False)) from None


@demo_router.get("/api/config")
def demo_config(request: Request):
    try:
        runtime = runtime_for(request)
        hub = hub_for(request)
        source = hub.connections.get(request.query_params.get('source') or hub.default_source)
        return runtime.summary() | {'connection_id': source['id'], 'connection_name': source['name']}
    except ValueError:
        raise HTTPException(409, "Invalid sample review receipt") from None


@demo_router.get('/api/playground')
def playground_catalog(request: Request):
    return runtime_for(request).playground.catalog()


@demo_router.post('/api/playground/interpret')
def playground_interpret(payload: Question, request: Request):
    try:
        return runtime_for(request).playground.interpret(payload, purpose_llm(request, 'query') if payload.metric is None else None)
    except (DemoError, RetrievalError) as exc:
        raise HTTPException(409, str(exc)) from None
    except Exception:
        LOGGER.exception('Playground interpretation failed')
        raise HTTPException(502, 'Question interpretation failed. Rephrase or select a saved metric.') from None


@demo_router.post('/api/playground/run')
def playground_run(payload: RunPlan, request: Request):
    try:
        return runtime_for(request).playground.execute(payload, llm_factory=lambda: purpose_llm(request, 'query'))
    except (DemoError, RetrievalError) as exc:
        raise HTTPException(409, str(exc)) from None
    except Exception:
        LOGGER.exception('Playground execution failed')
        raise HTTPException(503, 'The interpreted query could not run. No result is available.') from None


@demo_router.post("/api/example")
def execute_example(payload: ExampleRequest, request: Request):
    runtime = runtime_for(request)
    try:
        return runtime.execute(payload)
    except DemoError as exc:
        raise HTTPException(409, str(exc)) from None
    except Exception:
        LOGGER.exception("Local sample execution failed")
        raise HTTPException(
            503, "Sample execution failed; no result is available"
        ) from None


@demo_router.post('/api/example/explain')
def explain_sample(payload: ExplainExample, request: Request):
    runtime = runtime_for(request)
    try:
        return explain_example(runtime, payload, purpose_llm(request, 'query'))
    except DemoError as exc:
        raise HTTPException(409, str(exc)) from None
    except Exception:
        raise HTTPException(502, 'The query LLM could not explain this result. Check LLM configuration and retry.') from None


@demo_router.get("/context")
def context_page(request: Request):
    hub = hub_for(request)
    try:
        source = hub.connections.get(request.query_params.get('source') or hub.default_source)
    except DemoError as exc:
        raise HTTPException(404, str(exc)) from None
    if source['kind'] != 'local':
        return FileResponse(HERE / 'templates' / 'demo-source-studio.html')
    runtime_for(request)
    return FileResponse(HERE / "templates" / "demo-context.html")


def context_action(request, action, payload=None):
    runtime = runtime_for(request)
    try:
        if payload is not None:
            runtime.check_binding(payload)
        return action(runtime.workspace)
    except DemoError as exc:
        raise HTTPException(409, str(exc)) from None
    except Exception:
        LOGGER.exception("Local context operation failed")
        raise HTTPException(
            503, "Context operation failed. Reload and retry."
        ) from None


@demo_router.get("/api/context")
def context_view(request: Request):
    return context_action(request, lambda w: w.view())


@demo_router.get("/api/context/tables")
def context_tables(request: Request, offset: int = 0, limit: int = 20):
    return context_action(request, lambda w: w.tables(offset, limit))


@demo_router.get("/api/context/table")
def context_table(request: Request, name: str):
    return context_action(request, lambda w: w.table(name))


@demo_router.get("/api/context/version")
def context_version(request: Request, version: str):
    return context_action(request, lambda w: w.release(version))


@demo_router.get("/api/context/proposals")
def context_proposals(request: Request):
    result = context_action(request, lambda w: ProposalWorkspace(w).view())
    llm = purpose_llm(request, 'draft')
    return result | {"llm_available": llm is not None,
                     "llm_provider": llm.provider if llm else None,
                     "llm_model": llm.model if llm else None}


@demo_router.post("/api/context/propose")
def context_propose(payload: GenerateProposal, request: Request):
    return context_action(request, lambda w: ProposalWorkspace(w).generate(
        payload.revision, payload.mode, purpose_llm(request, 'draft') if payload.mode == "llm" else None
    ), payload)


@demo_router.post("/api/context/proposal/apply")
def context_apply_proposal(payload: ApplyProposal, request: Request):
    return context_action(request, lambda w: ProposalWorkspace(w).apply(
        payload.proposal_id, payload.revision
    ), payload)


@demo_router.get("/api/context/artifacts")
def context_artifacts(request: Request, version: str = "draft"):
    def inspect(workspace):
        builder = BuilderArtifacts(workspace)
        if version == "draft":
            return builder.bundle(workspace.view()["draft"]["definition"])
        release = workspace.release(version)
        return release.get("artifacts") or builder.bundle(release["definition"], release["document"], version,
                              release.get("item_review", []))
    return context_action(request, inspect)


@demo_router.get('/api/context/documents')
def context_documents(request: Request):
    def inspect(workspace):
        state = workspace.view()
        documents, warnings = BuilderArtifacts(workspace).document_evidence(state['draft']['definition'])
        reviews = {item['id']: item for item in state['review']['items']}
        for document in documents:
            prefix = 'source-document:' if document['origin'] == 'serving_document' else 'document:'
            decision = reviews.get(prefix + document['id'], {})
            document['review_status'] = decision.get('status', 'pending')
        return {'revision': state['draft']['revision'], 'items': documents, 'warnings': warnings}
    return context_action(request, inspect)


class AttachDocument(ContextBinding):
    revision: int = Field(ge=0)
    filename: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=262144)
    entity_links: list[dict] = Field(default_factory=list, max_length=50)


@demo_router.post("/api/context/document")
def context_document(payload: AttachDocument, request: Request):
    def attach(workspace):
        with workspace.connection() as connection:
            draft = workspace._draft(connection, payload.revision)
        value = draft["definition"]
        references = list(value.get("document_attachments", []))
        if len(references) >= 20:
            raise DemoError("A draft supports at most 20 appended documents")
        reference = BuilderArtifacts(workspace).attach(
            payload.filename, payload.content, payload.entity_links
        )
        if reference not in references:
            references.append(reference)
        value["document_attachments"] = references
        return workspace.save(payload.revision, ContextDefinition.model_validate(value))
    return context_action(request, attach, payload)


@demo_router.get("/api/context/export")
def context_export(request: Request, version: str):
    try:
        return export_studio_release(runtime_for(request).workspace, version)
    except (DemoError, RetrievalError) as exc:
        raise HTTPException(409, str(exc)) from None


@demo_router.post("/api/context/draft")
def context_save(payload: SaveContext, request: Request):
    return context_action(
        request, lambda w: w.save(payload.revision, payload.definition), payload
    )


@demo_router.post("/api/context/validate")
def context_validate(payload: ValidateContext, request: Request):
    return context_action(request, lambda w: w.validate(payload.revision), payload)


@demo_router.post("/api/context/review")
def context_review(payload: ReviewContext, request: Request):
    return context_action(request, lambda w: w.review(payload), payload)


@demo_router.post("/api/context/batch-review")
def context_batch_review(payload: BatchReview, request: Request):
    return context_action(request, lambda w: w.batch_review(payload), payload)


@demo_router.post("/api/context/publish")
def context_publish(payload: PublishContext, request: Request):
    return context_action(request, lambda w: w.publish(payload), payload)


@demo_router.post("/api/context/restore")
def context_restore(payload: RestoreContext, request: Request):
    return context_action(
        request, lambda w: w.restore(payload.revision, payload.version), payload
    )


@demo_router.get("/api/context/compare")
def context_compare(
    request: Request, version: str = "draft", baseline_version: str = "starter"
):
    return context_action(request, lambda w: w.compare(version, baseline_version))


@demo_router.get("/api/context/source-graph")
def context_graph(request: Request, version: str | None = None):
    return context_action(request, lambda w: w.source_graph(version))


@demo_router.post("/api/context/activate")
def context_activate(payload: ActivateContext, request: Request):
    return context_action(
        request, lambda w: w.activate(payload.version, payload.context_sha256), payload
    )


def configure_demo(application) -> None:
    pack_id = os.environ.get("HELIOS_DEMO_DATASET")
    if not pack_id:
        return
    registry = PackRegistry(
        Path(
            os.environ.get("HELIOS_DEMO_REGISTRY", ROOT / "apps/helios/demo-packs.json")
        ),
        Path(
            os.environ.get(
                "HELIOS_DEMO_FIXTURES",
                ROOT / "apps/helios-ds-generation/fixtures/sectors/v1",
            )
        ),
    )
    runtime = DemoRuntime(
        registry.load(pack_id),
        Path(os.environ.get("HELIOS_DEMO_STATE", ROOT / "state/demo")),
    )
    application.state.demo_runtime = runtime
    hub = DemoHub(registry, runtime.state_root, runtime)
    application.state.demo_hub = hub
    application.state.demo_llm_settings = LLMSettings(runtime.state_root)
    @application.exception_handler(RequestValidationError)
    async def redact_model_configuration_errors(request,exc):
        if request.url.path=='/demo/api/llm':
            # Validation errors otherwise echo request values, including a submitted API key.
            return JSONResponse({'detail':[{'loc':error['loc'],'msg':'Invalid model configuration value','type':error['type']}
                                           for error in exc.errors()]},status_code=422)
        return await request_validation_exception_handler(request,exc)
    application.state.demo_materials = MaterialLibrary(hub)
    previous_lifespan = application.router.lifespan_context

    @asynccontextmanager
    async def demo_lifespan(app):
        try:
            async with previous_lifespan(app) as state:
                yield state
        finally:
            hub.close()

    application.router.lifespan_context = demo_lifespan

    @application.middleware("http")
    async def isolate_demo_routes(request, call_next):
        # Until milestone 1B binds conversation tools to pack context, the demo
        # must not expose legacy conversation or live-source routes as a bypass.
        allowed = {
            "/",
            "/demo",
            "/demo/query",
            "/demo/llm",
            "/demo/materials",
            "/demo/api/materials",
            "/demo/api/materials/upload",
            "/static/demo-materials.js",
            "/static/demo-materials.css",
            "/demo/api/llm",
            "/demo/api/llm/test",
            "/demo/api/example/explain",
            "/demo/api/playground",
            "/demo/api/playground/interpret",
            "/demo/api/playground/run",
            "/static/demo-playground.js",
            "/static/demo-playground.css",
            "/static/demo-llm.js",
            "/static/demo-llm.css",
            "/demo/api/hub",
            "/demo/api/hub/source",
            "/demo/api/connections",
            "/demo/api/connections/update",
            "/demo/api/connections/schema",
            "/static/demo-hub.css",
            "/static/demo-hub.js",
            "/static/demo-source-studio.js",
            "/demo/api/config",
            "/demo/api/example",
            "/static/demo.css",
            "/static/demo-shell.css",
            "/static/cloudera-wordmark.png",
            "/static/favicon.svg",
            "/static/favicon-32.png",
            "/static/apple-touch-icon.png",
            "/static/demo.js",
            "/demo/context",
            "/demo/api/context",
            "/demo/api/context/tables",
            "/demo/api/context/table",
            "/demo/api/context/version",
            "/demo/api/context/export",
            "/demo/api/context/proposals",
            "/demo/api/context/propose",
            "/demo/api/context/proposal/apply",
            "/demo/api/context/artifacts",
            "/demo/api/context/documents",
            "/demo/api/context/document",
            "/demo/api/context/draft",
            "/demo/api/context/validate",
            "/demo/api/context/review",
            "/demo/api/context/activate",
            "/static/demo-context.css",
            "/static/demo-context.js",
            "/static/demo-canvas.js",
            "/static/demo-canvas.css",
            "/demo/api/context/batch-review",
            "/demo/api/context/publish",
            "/demo/api/context/restore",
            "/demo/api/context/compare",
            "/demo/api/context/source-graph",
        }
        material_route = re.fullmatch(r'/demo/api/materials/material-[a-f0-9]{32}(?:/(?:analyze|suggest|review|apply|visual|preview|facts))?', request.url.path)
        if request.url.path not in allowed and not material_route:
            return JSONResponse(
                {"detail": "Unavailable in local sample mode"}, status_code=404
            )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response
