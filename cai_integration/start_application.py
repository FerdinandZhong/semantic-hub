"""CAI Application entry point; switch to the shared project virtual environment."""
import os
from pathlib import Path
import sys


def main():
    root = Path(globals().get('__file__', Path.cwd() / 'cai_integration/start_application.py')).resolve().parents[1]
    sys.path.insert(0, str(root))
    from cai_integration.config import settings
    from cai_integration.environment import isolated_environment, check_isolation
    py = settings()['venv'] / 'bin/python'
    if not py.is_file():
        raise RuntimeError('Run the semantic-hub-setup AMP job before starting this Application.')
    env = isolated_environment(py.parent.parent)
    if not check_isolation(py.parent.parent, env):
        raise RuntimeError('Runtime isolation failed. Rerun the updated AMP setup job.')
    os.chdir(root)
    bootstrap = ("import runpy,sys;sys.path.insert(0,sys.argv[1]);"
                 "runpy.run_module('cai_integration.application',run_name='__main__')")
    os.execve(str(py), [str(py), '-I', '-c', bootstrap, str(root)], env)


if __name__ == '__main__':
    main()
