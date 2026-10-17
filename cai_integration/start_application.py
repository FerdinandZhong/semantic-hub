"""CAI Application entry point; switch to the shared project virtual environment."""
import os
from pathlib import Path
import sys


def main():
    root = Path(globals().get('__file__', Path.cwd() / 'cai_integration/start_application.py')).resolve().parents[1]
    sys.path.insert(0, str(root))
    from cai_integration.config import settings
    py = settings()['venv'] / 'bin/python'
    if not py.is_file():
        raise RuntimeError('Run the semantic-hub-setup AMP job before starting this Application.')
    env = dict(os.environ, PYTHONNOUSERSITE='1')
    # Console scripts and the agent runtime must resolve in the same environment.
    env['PATH'] = str(py.parent) + os.pathsep + env.get('PATH', '')
    os.chdir(root)
    os.execve(str(py), [str(py), '-m', 'cai_integration.application'], env)


if __name__ == '__main__':
    main()
