"""AMP deployment contracts; no hosted credentials or model calls."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from cai_integration.config import configure_runtime, settings


def test_manifest_has_setup_barrier_and_authenticated_cpu_app():
    spec = yaml.safe_load((ROOT / '.project-metadata.yaml').read_text())
    tasks = spec['tasks']
    assert [t['type'] for t in tasks] == ['create_job', 'run_job', 'start_application']
    assert tasks[1]['wait_for'] is True
    assert tasks[0]['entity_label'] == tasks[1]['entity_label']
    assert tasks[2]['bypass_authentication'] is False and tasks[2]['gpu'] == 0
    for task in tasks:
        if 'script' in task:
            assert (ROOT / task['script']).is_file()
    assert not any('TOKEN' in k or 'KEY' in k for k in spec['environment_variables'])


def test_state_is_persistent_and_key_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv('SEMANTIC_HUB_STATE_DIR', str(tmp_path))
    cfg = configure_runtime()
    key = tmp_path / '.model-secrets/key'
    key.parent.mkdir()
    key.write_bytes(b'preserve-this-key')
    configure_runtime()
    assert key.read_bytes() == b'preserve-this-key'
    assert Path(os.environ['HELIOS_METADATA_DB']).parent == cfg['state']
    assert Path(os.environ['HELIOS_DEMO_STATE']) == cfg['state']


def test_relative_state_is_resolved_from_checkout(monkeypatch):
    monkeypatch.setenv('SEMANTIC_HUB_STATE_DIR', 'state/amp-test')
    assert settings()['state'] == ROOT / 'state/amp-test'


def test_cai_startup_fails_outside_workbench(tmp_path):
    env = dict(os.environ, SEMANTIC_HUB_STATE_DIR=str(tmp_path))
    for key in ('CDSW_APP_PORT', 'CDSW_PROJECT_ID', 'CDSW_DOMAIN'):
        env.pop(key, None)
    proc = subprocess.run([sys.executable, '-c',
        'from cai_integration.application import create_app; create_app()'],
        cwd=ROOT, env=env, capture_output=True, text=True)
    assert proc.returncode != 0
    assert 'authenticated CAI Application' in proc.stderr


@pytest.mark.parametrize('platform', [False, True])
def test_combined_routes_and_shared_runtime(tmp_path, platform):
    # Isolate the console singleton and all import-time environment settings.
    env = dict(os.environ, SEMANTIC_HUB_STATE_DIR=str(tmp_path), HELIOS_DEMO_DATASET='finance')
    if platform:
        env.update(CDSW_APP_PORT='8099', CDSW_PROJECT_ID='offline-test', CDSW_DOMAIN='example.invalid')
    code = '''
from fastapi.testclient import TestClient
from cai_integration.application import create_app
app = create_app(local=LOCAL)
from apps.helios.console.main import app as console
assert app.state.semantic_hub_consumer.hub is console.state.demo_hub
with TestClient(app) as client:
    assert client.get('/healthz').json()['status'] == 'ready'
    home = client.get('/demo')
    assert home.status_code == 200 and 'Semantic Hub' in home.text
    caps = client.get('/api/semantic-hub/v1/capabilities')
    assert caps.status_code == 200
    assert client.get('/api/semantic-hub/v1/models').json()['total'] == 0
    assert client.get('/docs').status_code == 200
    assert client.get('/docs/assets/swagger-ui-bundle.js').status_code == 200
    schema = client.get('/api/semantic-hub/v1/openapi.json').json()
    assert 'ConsumerBearer' not in schema.get('components', {}).get('securitySchemes', {})
    if not LOCAL:
        assert 'CAI Application ingress' in caps.json()['authorization']
        assert 'Workbench session authenticates' in client.get('/docs').text
'''.replace('LOCAL', str(not platform))
    proc = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
