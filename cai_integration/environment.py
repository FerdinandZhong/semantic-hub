"""Keep CAI notebook packages outside the application virtual environment."""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys


def isolated_environment(target: Path) -> dict[str, str]:
    env = dict(os.environ)
    for key in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONUSERBASE', 'PIP_TARGET', 'PIP_PREFIX'):
        env.pop(key, None)
    env.update(PYTHONNOUSERSITE='1', PIP_USER='0', PIP_CONFIG_FILE=os.devnull,
               VIRTUAL_ENV=str(target))
    env['PATH'] = str(target / 'bin') + os.pathsep + env.get('PATH', '')
    # Preserve CAI credentials, proxy/CA settings, and explicit package index URLs.
    return env


PROBE = '''
import importlib.metadata as metadata, json, pathlib, site, sys
root = pathlib.Path(sys.prefix).resolve()
dists = list(metadata.distributions())
foreign = sorted({d.metadata.get('Name', 'unknown') for d in dists
                  if not pathlib.Path(d.locate_file('')).resolve().is_relative_to(root)})
vendor = sorted({d.metadata.get('Name', '').lower() for d in dists} &
                {'cml', 'mlflow-skinny', 'mlflow-cml-plugin'})
print(json.dumps({'virtual': sys.prefix != sys.base_prefix,
                  'user_site': site.ENABLE_USER_SITE,
                  'foreign': foreign, 'vendor': vendor}))
'''


def check_isolation(target: Path, env: dict[str, str]) -> bool:
    result = subprocess.run([str(target / 'bin/python'), '-I', '-c', PROBE],
                            env=env, check=True, capture_output=True, text=True)
    report = json.loads(result.stdout)
    return report['virtual'] and not report['user_site'] and not report['foreign'] and not report['vendor']


def prepare_environment(target: Path) -> dict[str, str]:
    env = isolated_environment(target)
    # Rewrite pyvenv.cfg on every setup run to disable system-site-packages.
    # Isolated creation also prevents notebook PYTHONPATH leaking into ensurepip.
    def create():
        subprocess.run([sys.executable, '-I', '-m', 'venv', '--without-pip', str(target)],
                       env=env, check=True)
    create()
    if not check_isolation(target, env):
        backup = target.with_name(target.name + '.before-isolation-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        target.rename(backup)
        print('Preserved contaminated runtime at', backup.name, flush=True)
        create()
    if not check_isolation(target, env):
        raise RuntimeError('Virtual environment isolation failed; application packages were not installed.')
    subprocess.run([str(target / 'bin/python'), '-I', '-m', 'ensurepip', '--upgrade'],
                   env=env, check=True)
    print('Virtual environment isolation passed; CAI runtime packages excluded.', flush=True)
    return env
