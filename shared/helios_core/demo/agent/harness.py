"""Official DeepSeek Harness SDK adapter. No substitute loop or silent fallback."""
from __future__ import annotations
import json
import secrets
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import yaml
from helios_core.demo.registry import DemoError
from .memory import Memory
from .tools import SemanticTools, TOOL_SCHEMAS

HERE = Path(__file__).resolve().parent
# The bundled runtime materializes its plugin profile during startup.
START_LOCK = threading.Lock()


def profile(llm):
    endpoint = llm.base_url or 'https://api.openai.com/v1'
    if llm.provider not in ('openai', 'mistral'):
        raise DemoError('The Playground Harness currently requires an OpenAI-compatible query model configuration.')
    provider = 'helios-query'
    adapter = {'apiKeyEnv':'HELIOS_HARNESS_MODEL_KEY', 'baseURL':endpoint,
               'api':'openai-completions', 'models':[{'id':llm.model, 'contextWindow':128000, 'maxTokens':2000}],
               'retryPolicy':{'mode':'normal','maxRetries':1}}
    return provider, adapter


def interpret(playground, payload, llm):
    try:
        from deepseek_harness import DeepSeekHarness
    except ImportError:
        raise DemoError('Install the pinned DeepSeek Harness SDK from demo-requirements.txt to use AI questions.') from None
    tools = SemanticTools(playground,payload,llm)
    provider, adapter = profile(llm)
    turn = 'turn-' + secrets.token_hex(12)
    root = playground.runtime.state_root / 'playground-agent' / playground.runtime.pack.entry.id / payload.context_sha256
    root.mkdir(parents=True, exist_ok=True)
    memory = Memory(root)
    token = secrets.token_urlsafe(32)

    class Bridge(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            if self.headers.get('Authorization') != 'Bearer '+token or self.path != '/tools':
                self.send_error(403); return
            try:
                size = int(self.headers.get('Content-Length','0'))
                if not 0 < size <= 20000: raise ValueError('Invalid body')
                body = json.loads(self.rfile.read(size))
                value = tools.call(body['tool'],body['args'])
            except Exception as exc:
                # Tool rejection is recoverable within the remaining turn budget.
                value = {'status':'tool_rejected','message':str(exc)[:1000] if isinstance(exc,DemoError) else 'Invalid tool arguments, scope, or budget. Inspect the model and preserve the original question.'}
            raw = json.dumps(value, ensure_ascii=False, default=str).encode()
            self.send_response(200); self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

    server = HTTPServer(('127.0.0.1',0),Bridge)
    server.timeout = 1
    worker = threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    response = None
    failure = None
    try:
        with tempfile.TemporaryDirectory(prefix='config-',dir=root) as temp:
            patch = Path(temp)/'cordis.patch.yml'
            config = [{'id':name,'disabled':True} for name in ('persistent-bash','persistent-pwsh','llm-deepseek')]
            config += [{'id':'system-prompt','config':{'includeHarnessIdentity':False,'includeRuntimeContext':False,
                        'personaPrefix':(HERE/'skills/query.md').read_text()}},
                       {'insert':[{'id':'semantic-model-adapter','name':'@deepseek-ai/dsh-llm-pi-ai',
                                   'config':{'providers':{provider:adapter}}},
                                  {'id':'semantic-tools','name':str(HERE/'plugin.mjs'),
                                   'config':{'tools':tools.schemas}}]}]
            patch.write_text(yaml.safe_dump(config,sort_keys=False))
            harness = DeepSeekHarness(dsh_home=str(root/'runtime'),cwd=str(root),profile='sdk-minimal',
                patches=(str(patch),),provider=provider,model=llm.model,max_tokens=2000,
                request_timeout_seconds=120,initialize_timeout_seconds=30,
                env={'HELIOS_HARNESS_MODEL_KEY':llm.api_key or '',
                     'HELIOS_HARNESS_BRIDGE':f'http://127.0.0.1:{server.server_port}/tools',
                     'HELIOS_HARNESS_BRIDGE_TOKEN':token})
            try:
                with START_LOCK:
                    harness.start()
                result = harness.run(json.dumps({'original_question':payload.question,
                    'version':payload.version,'answer_mode':payload.mode,
                    'memory_policy':'This is an independent turn. Prior answers are not evidence. Use only this release and fresh tools.'},ensure_ascii=False),session_id=turn)
                final = result.final_response.strip()
                if final.startswith('```'):
                    final = final.split('\n',1)[1].rsplit('```',1)[0]
                try:
                    receipt = json.loads(final).get('receipt_id')
                except (ValueError, AttributeError):
                    receipt = None
                response = tools.receipts.get(receipt)
                # A single tool receipt is authoritative even if the model adds prose.
                # Multiple receipts need an explicit choice; never guess between plans.
                if response is None and len(tools.receipts)==1:
                    response = next(iter(tools.receipts.values()))
                if response is None:
                    raise ValueError('No checked receipt')
            finally:
                harness.close()
    except Exception as exc:
        failure = type(exc).__name__
        # Never surface SDK errors containing provider headers or a prompt transcript.
        response = {'status':'unavailable', 'choices':[],
                    'message':'The agent could not produce a checked answer plan within its budget. No query answer was issued. Try a narrower question or a saved metric.'}
    finally:
        server.shutdown();server.server_close();worker.join(timeout=2)
    response['agent'] = {'framework':'DeepSeek Harness','sdk_version':'0.1.5rc1', 'provider':llm.provider,
        'model':llm.model,'turn_id':turn,'tool_budget':12,'trace':tools.trace,'failure_type':failure,
        'memory_scope':'Selected published context and source snapshot; previous answers are not reused as facts.'}
    memory.record(turn,payload.context_sha256,playground.runtime.pack.fingerprint,payload.question,response,tools.trace)
    if response.get('plan_id'):
        with playground.lock:
            playground.plans[response['plan_id']]['response']['agent'] = response['agent']
    return response
