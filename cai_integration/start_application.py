"""Keep the CAI kernel alive while supervising the isolated application server."""
import os
from pathlib import Path
import sys
import signal
import subprocess


def startup_command(py, root):
    bootstrap = ("import runpy,sys;root=sys.argv.pop(1);sys.path.insert(0,root);"
                 "runpy.run_module('cai_integration.application',run_name='__main__')")
    return [str(py), '-I', '-u', '-c', bootstrap, str(root)]


def supervise(command, *, env, cwd, shutdown_timeout=20):
    # Workbench runs this file inside its monitored Jupyter kernel.
    # Replacing that process breaks the kernel heartbeat and stops the workload.
    child = subprocess.Popen(command, env=env, cwd=cwd, start_new_session=True)
    print(f'Semantic Hub server started as child process {child.pid}; CAI kernel remains active.', flush=True)
    previous = signal.getsignal(signal.SIGTERM)
    def stop(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, stop)
    try:
        status = child.wait()
        if status:
            raise RuntimeError(f'Semantic Hub server exited with status {status}. See the server traceback above.')
    finally:
        try:
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    child.wait(timeout=shutdown_timeout)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    child.wait()
        finally:
            signal.signal(signal.SIGTERM, previous)


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
    supervise(startup_command(py, root), env=env, cwd=root)


if __name__ == '__main__':
    main()
