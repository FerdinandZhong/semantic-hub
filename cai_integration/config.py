"""Paths and process settings shared by AMP setup and startup."""
from __future__ import annotations
import os
from pathlib import Path


def project_root() -> Path:
    # Workbench may execute a script as notebook cells without __file__.
    roots = [Path(os.environ.get('CDSW_PROJECT_DIR') or Path.cwd()),
             Path(__file__).resolve().parents[1]]
    for root in roots:
        if (root / 'start_demo.py').is_file() and (root / '.project-metadata.yaml').is_file():
            return root.resolve()
    raise RuntimeError('Run AMP setup from the Semantic Hub project checkout.')


def settings() -> dict:
    root = project_root()
    state = Path(os.environ.get('SEMANTIC_HUB_STATE_DIR') or root / 'state/semantic-hub').expanduser()
    if not state.is_absolute():
        state = root / state
    return {'root': root, 'state': state.resolve(),
            'venv': root / '.venv-semantic-hub',
            'dataset': os.environ.get('HELIOS_DEMO_DATASET') or 'finance'}


def configure_runtime() -> dict:
    cfg = settings()
    state = cfg['state']
    state.mkdir(parents=True, exist_ok=True)
    # A durable key resides beneath state/.model-secrets; never regenerate it on launch.
    os.environ.update(HELIOS_DEMO_STATE=str(state), HELIOS_DEMO_DATASET=cfg['dataset'],
                      HELIOS_METADATA_DB=str(state / 'console.db'), PYSTOW_HOME=str(state / 'pystow'))
    os.environ.setdefault('LLM_PROVIDER', 'openai')
    os.environ.setdefault('INFERENCE_BASE_URL', 'https://api.openai.com/v1')
    os.environ.setdefault('INFERENCE_MODEL', 'gpt-4o')
    return cfg
