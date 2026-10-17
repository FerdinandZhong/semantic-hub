"""AMP job: install an isolated runtime and verify every bundled source."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
import venv


def main():
    root = Path(globals().get('__file__', Path.cwd() / 'cai_integration/setup_environment.py')).resolve().parents[1]
    sys.path.insert(0, str(root))
    from cai_integration.config import configure_runtime
    cfg = configure_runtime()
    if sys.version_info[:2] not in {(3, 11), (3, 12)}:
        raise RuntimeError('Select a Standard Python 3.11 or 3.12 runtime.')
    target = cfg['venv']
    if not (target / 'bin/python').exists():
        venv.EnvBuilder(with_pip=True).create(target)
    py = str(target / 'bin/python')
    env = dict(os.environ, PIP_USER='0', PYTHONNOUSERSITE='1')
    subprocess.run([py, '-m', 'pip', 'install', '-r', str(root / 'cai_integration/requirements.lock')],
                   check=True, cwd=root, env=env)
    subprocess.run([py, '-m', 'pip', 'check'], check=True, cwd=root, env=env)
    subprocess.run([py, str(root / 'cai_integration/verify.py')], check=True, cwd=root, env=env)
    print('Semantic Hub setup complete. No models were reviewed or published automatically.')


if __name__ == '__main__':
    main()
