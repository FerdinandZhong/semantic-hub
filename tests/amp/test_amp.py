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
    assert [t['type'] for t in tasks] == [
        'create_job', 'run_job', 'create_job', 'run_job', 'start_application'
    ]
    for create, run in ((tasks[0], tasks[1]), (tasks[2], tasks[3])):
        assert run['wait_for'] is True
        assert create['entity_label'] == run['entity_label']
    assert tasks[0]['script'] == 'deployment/cai/prepare.py'
    assert tasks[2]['script'] == 'deployment/cai/provision.py'
    # Provisioning owns Helios; the AMP manifest owns only Hub.
    assert tasks[4]['bypass_authentication'] is False and tasks[4]['gpu'] == 0
    assert tasks[4]['entity_label'] == 'semantic-hub-app'
    assert tasks[4]['script'] == 'deployment/launchers/hub.py'
    assert spec['environment_variables']['SEMANTIC_HUB_PROVIDER_MODE']['default'] == 'bundled'
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
        shell = client.get('/docs').text
        assert 'Workbench session authenticates' in shell
        assert 'CDSW_APIV2_KEY' in shell and 'persistAuthorization:false' in shell
        assert 'Consumer API token' not in shell and 'access-form' not in shell
        assert schema['components']['securitySchemes']['CAIAPIv2Key']['scheme'] == 'bearer'
        for operations in schema['paths'].values():
            for operation in operations.values():
                assert operation['security'] == [{'CAIAPIv2Key': []}]
'''.replace('LOCAL', str(not platform))
    proc = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr


def test_cai_pythonpath_leak_is_reproduced_and_excluded(tmp_path, monkeypatch):
    from cai_integration.environment import isolated_environment, prepare_environment
    injected = tmp_path / 'cai-site'
    dist = injected / 'mlflow_skinny-2.19.0.dist-info'
    dist.mkdir(parents=True)
    (dist / 'METADATA').write_text('Metadata-Version: 2.1\nName: mlflow-skinny\nVersion: 2.19.0\nRequires-Dist: packaging<0\n')
    monkeypatch.setenv('PYTHONPATH', str(injected))
    monkeypatch.setenv('PIP_TARGET', str(injected))
    monkeypatch.setenv('PIP_PREFIX', str(tmp_path / 'wrong-prefix'))
    monkeypatch.setenv('CDSW_APIV2_KEY', 'keep-runtime-secret')
    monkeypatch.setenv('PIP_INDEX_URL', 'https://packages.example/simple')
    target = tmp_path / 'venv'
    env = prepare_environment(target)
    py = str(target / 'bin/python')
    leaked = subprocess.run([py, '-m', 'pip', 'check'], capture_output=True, text=True)
    assert leaked.returncode != 0 and 'mlflow-skinny' in leaked.stdout
    clean = subprocess.run([py, '-I', '-m', 'pip', 'check'], env=env, capture_output=True, text=True)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert not {'PYTHONPATH', 'PYTHONHOME', 'PIP_TARGET', 'PIP_PREFIX'} & env.keys()
    assert env['CDSW_APIV2_KEY'] == 'keep-runtime-secret'
    assert env['PIP_INDEX_URL'] == 'https://packages.example/simple'


def test_setup_repairs_contaminated_runtime_and_preserves_state(tmp_path):
    from cai_integration.environment import prepare_environment
    target = tmp_path / 'venv'
    prepare_environment(target)
    py = str(target / 'bin/python')
    site = Path(subprocess.check_output([py, '-I', '-c',
        'import sysconfig;print(sysconfig.get_path("purelib"))'], text=True).strip())
    dist = site / 'cml-1.0.0.dist-info'
    dist.mkdir()
    (dist / 'METADATA').write_text('Metadata-Version: 2.1\nName: cml\nVersion: 1.0.0\n')
    state = tmp_path / 'state'
    state.mkdir()
    (state / 'reviewed-model.json').write_text('preserve')
    env = prepare_environment(target)
    assert (state / 'reviewed-model.json').read_text() == 'preserve'
    assert list(tmp_path.glob('venv.before-isolation-*'))
    assert not dist.exists()
    assert subprocess.run([py, '-I', '-m', 'pip', 'check'], env=env).returncode == 0


def test_isolated_bootstrap_consumes_project_argument():
    from cai_integration.start_application import startup_command
    from cai_integration.environment import isolated_environment
    command = startup_command(sys.executable, ROOT) + ['--help']
    result = subprocess.run(command, env=isolated_environment(Path(sys.prefix)),
                            cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert '--local' in result.stdout
    assert 'unrecognized arguments' not in result.stderr


def test_supervisor_preserves_kernel_process_and_reports_server_failure(tmp_path):
    from cai_integration.start_application import supervise
    original_pid = os.getpid()
    supervise([sys.executable, '-c', 'print("child completed")'], env=dict(os.environ), cwd=tmp_path)
    assert os.getpid() == original_pid
    with pytest.raises(RuntimeError, match='exited with status 7'):
        supervise([sys.executable, '-c', 'raise SystemExit(7)'], env=dict(os.environ), cwd=tmp_path)


def test_stopping_kernel_supervisor_terminates_server(tmp_path):
    import signal
    import time
    ready = tmp_path / 'ready'
    stopped = tmp_path / 'stopped'
    child_code = ('import signal,time,pathlib;'
                  f'signal.signal(signal.SIGTERM,lambda *a:(pathlib.Path({str(stopped)!r}).write_text("stopped"),exit(0)));'
                  f'pathlib.Path({str(ready)!r}).write_text("ready");time.sleep(60)')
    supervisor_code = ('from cai_integration.start_application import supervise;import os,sys;'
                       f'supervise([sys.executable,"-c",{child_code!r}],env=dict(os.environ),cwd={str(tmp_path)!r})')
    parent = subprocess.Popen([sys.executable, '-c', supervisor_code], cwd=ROOT)
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            assert parent.poll() is None
            time.sleep(.05)
        assert ready.exists()
        parent.send_signal(signal.SIGTERM)
        parent.wait(timeout=10)
        assert stopped.read_text() == 'stopped'
    finally:
        if parent.poll() is None:
            parent.terminate()
            parent.wait(timeout=10)
