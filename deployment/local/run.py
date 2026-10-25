#!/usr/bin/env python3
"""Local v2 process launcher. Run prepare once, then start/check/stop."""

from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = Path(__file__).with_name("bootstrap.py")


def read_json(path):
    return json.loads(path.read_text()) if path.exists() else {}


def validate_lock(root=ROOT):
    lock = read_json(root / "deployment/provider-lock.json")["helios"]
    checkout = root / lock["path"]
    if not (checkout / ".git").exists():
        raise RuntimeError(
            "Helios checkout missing. Initialize the pinned submodule first; no fallback was started."
        )
    top = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "--show-toplevel"], text=True
    ).strip()
    if Path(top).resolve() != checkout.resolve():
        raise RuntimeError("Helios checkout missing its own Git worktree.")
    dirty = subprocess.check_output(
        ["git", "-C", str(checkout), "status", "--porcelain", "--untracked-files=no"],
        text=True,
    ).strip()
    if dirty:
        raise RuntimeError(
            "Helios checkout has tracked changes. Restore the pinned checkout before starting."
        )
    actual = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != lock["commit"]:
        raise RuntimeError(
            f"Helios lock mismatch: expected {lock['commit']}, found {actual}. No fallback was started."
        )
    return checkout


def command_identity(pid):
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart=", "-o", "command="],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def owned(record):
    return (
        bool(record.get("identity"))
        and command_identity(record["pid"]) == record["identity"]
    )


def require_free(port):
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(
                f"Port {port} is occupied. The launcher will not stop or adopt its process."
            ) from exc


def healthy(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def isolated_env(state):
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("HELIOS_", "SEMANTIC_HUB_", "CDSW_"))
        and k not in {"PYTHONPATH", "PYTHONHOME"}
    }
    env.update(PYSTOW_HOME=str(state / "pystow"))
    return env


def plan(args):
    hub_state = args.state / "hub"
    hub_env = isolated_env(hub_state)
    hub_env.update(SEMANTIC_HUB_STATE_DIR=str(hub_state), CDSW_PROJECT_DIR=str(ROOT))
    specs = [
        (
            "hub",
            ROOT,
            ROOT / ".venv-semantic-hub/bin/python",
            args.hub_port,
            hub_env,
            f"http://127.0.0.1:{args.hub_port}/healthz",
        )
    ]
    if args.mode == "bundled":
        checkout = validate_lock()
        state = args.state / "helios"
        env = isolated_env(state)
        env.update(
            HELIOS_ROOT=str(state),
            HELIOS_METADATA_DB=str(state / "helios.db"),
            HELIOS_RUNS_DIR=str(state / "runs"),
            HELIOS_EVIDENCE_INDEX=str(state / "evidence.lance"),
            HELIOS_DEV="1",
            HELIOS_DEV_USER="local-reviewer",
            HELIOS_UI_ORIGINS=f"http://127.0.0.1:{args.helios_ui_port}",
        )
        specs.append(
            (
                "helios-api",
                checkout,
                ROOT / ".venv-helios/bin/python",
                args.helios_api_port,
                env,
                f"http://127.0.0.1:{args.helios_api_port}/api/v1/healthz",
            )
        )
        env = isolated_env(state)
        env.update(
            HELIOS_ROOT=str(args.state / "native-ui"),
            HELIOS_API_URL=f"http://127.0.0.1:{args.helios_api_port}",
            CDSW_APP_PORT=str(args.helios_ui_port),
        )
        specs.append(
            (
                "helios-ui",
                checkout,
                ROOT / ".venv-helios/bin/python",
                args.helios_ui_port,
                env,
                f"http://127.0.0.1:{args.helios_ui_port}/healthz",
            )
        )
    if len({s[3] for s in specs}) != len(specs):
        raise RuntimeError("Each service requires a different port.")
    return specs


def register(args):
    if args.mode == "builtin_only":
        return
    sys.path.insert(0, str(ROOT))
    from semantic_hub.providers.registry import Registry

    ui = (
        args.helios_ui_origin
        if args.mode == "external"
        else f"http://127.0.0.1:{args.helios_ui_port}"
    )
    api = (
        args.helios_api_origin
        if args.mode == "external"
        else f"http://127.0.0.1:{args.helios_api_port}"
    )
    if not ui or not api:
        raise RuntimeError(
            "External mode requires --helios-ui-origin and --helios-api-origin. No bundled fallback is allowed."
        )
    Registry(args.state / "hub", local=True).save_provider(
        "helios-local", "Local Helios", ui, api
    )


def stop_records(data):
    for record in reversed(data.get("processes", [])):
        if owned(record):
            os.kill(record["pid"], signal.SIGTERM)
    deadline = time.monotonic() + 8
    while (
        any(owned(r) for r in data.get("processes", [])) and time.monotonic() < deadline
    ):
        time.sleep(0.1)
    for record in data.get("processes", []):
        if owned(record):
            os.kill(record["pid"], signal.SIGKILL)


def prepare(args):
    if not (ROOT / ".venv-semantic-hub/bin/python").exists():
        raise RuntimeError(
            "Hub environment missing. Run the existing Hub setup first: .venv-semantic-hub/bin/python is required."
        )
    if args.mode != "bundled":
        return
    checkout = validate_lock()
    python = ROOT / ".venv-helios/bin/python"
    if not python.exists():
        subprocess.run(
            [sys.executable, "-m", "venv", str(python.parents[1])], check=True
        )
    requirements = [
        line
        for line in (checkout / "apps/helios/console/requirements.txt")
        .read_text()
        .splitlines()
        if line.strip()
        and not line.startswith("#")
        and not line.startswith(("lancedb", "sentence-transformers"))
    ]
    # Console requirements omit LinkML; its runtime requires newer jsonschema.
    requirements = [
        line for line in requirements if not line.startswith("jsonschema==")
    ]
    requirements += ["linkml-runtime==1.12.1", "jsonschema==4.26.0"]
    target = args.state / "provider-runtime-requirements.txt"
    target.write_text("\n".join(requirements) + "\n")
    subprocess.run([str(python), "-m", "pip", "install", "-r", str(target)], check=True)
    ui = checkout / "apps/helios/ui"
    subprocess.run(["npm", "ci"], cwd=ui, check=True)
    subprocess.run(
        [
            "npm",
            "run",
            "build",
            "--",
            "--outDir",
            str(args.state / "native-ui/apps/helios/ui/dist"),
        ],
        cwd=ui,
        check=True,
    )
    print(
        "Prepared. Embeddings/vector evidence search omitted; live backends require their own configuration."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "start", "check", "stop"])
    parser.add_argument(
        "--mode", choices=["bundled", "external", "builtin_only"], default="bundled"
    )
    parser.add_argument("--state", type=Path, default=ROOT / "state/local-v2")
    parser.add_argument("--hub-port", type=int, default=8099)
    parser.add_argument("--helios-api-port", type=int, default=8101)
    parser.add_argument("--helios-ui-port", type=int, default=8100)
    parser.add_argument("--helios-ui-origin")
    parser.add_argument("--helios-api-origin")
    args = parser.parse_args()
    args.state = args.state.expanduser().resolve()
    args.state.mkdir(parents=True, exist_ok=True)
    manifest = args.state / "processes.json"
    with (args.state / "launcher.lock").open("a") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        data = read_json(manifest)
        if args.action == "prepare":
            prepare(args)
        elif args.action == "stop":
            stop_records(data)
            manifest.write_text(json.dumps(dict(data, processes=[]), indent=2))
            print("Stopped launcher-owned processes. Persistent state retained.")
        elif args.action == "check":
            ok = bool(data.get("processes"))
            for record in data.get("processes", []):
                ready = owned(record) and healthy(record["health_url"])
                ok &= ready
                print(
                    f"{record['name']}: {'ready' if ready else 'unavailable'} ({record['health_url']})"
                )
            print(f"Hub v2: {data.get('hub_url', 'not started')}")
            if data.get("mode") == "external":
                for name, url in data["external"].items():
                    ready = healthy(
                        url + ("/api/v1/healthz" if name == "api" else "/healthz")
                    )
                    print(
                        f"External Helios {name}: {'reachable' if ready else 'unavailable'} ({url})"
                    )
                    ok &= ready
            return 0 if ok else 1
        else:
            if any(owned(r) for r in data.get("processes", [])):
                raise RuntimeError(
                    "This state already has running owned processes. Use check or stop first."
                )
            specs = plan(args)
            for name, _, python, port, _, _ in specs:
                if not python.exists():
                    raise RuntimeError(
                        f"{name} environment missing: {python}. Run prepare first; no fallback was started."
                    )
                require_free(port)
            register(args)
            data = dict(
                mode=args.mode,
                hub_url=f"http://127.0.0.1:{args.hub_port}/v2",
                processes=[],
                external=dict(ui=args.helios_ui_origin, api=args.helios_api_origin),
            )
            try:
                for name, root, python, port, env, url in specs:
                    (args.state / ("hub" if name == "hub" else "helios")).mkdir(
                        exist_ok=True
                    )
                    with (args.state / f"{name}.log").open("ab") as log:
                        child = subprocess.Popen(
                            [
                                str(python),
                                "-I",
                                str(BOOTSTRAP),
                                str(root),
                                name,
                                str(port),
                            ],
                            cwd=root,
                            env=env,
                            stdout=log,
                            stderr=log,
                            start_new_session=True,
                        )
                    record = dict(
                        name=name,
                        pid=child.pid,
                        identity=command_identity(child.pid),
                        health_url=url,
                    )
                    data["processes"].append(record)
                    manifest.write_text(json.dumps(data, indent=2))
                    deadline = time.monotonic() + 45
                    while (
                        child.poll() is None
                        and not healthy(url)
                        and time.monotonic() < deadline
                    ):
                        time.sleep(0.2)
                    if child.poll() is not None or not healthy(url):
                        raise RuntimeError(
                            f'{name} failed readiness. See {args.state / (name + ".log")}. No fallback was started.'
                        )
            except BaseException:
                stop_records(data)
                raise
            print(f"Hub v2: {data['hub_url']}")
            print(f"Mode: {args.mode}; processes and logs: {args.state}")
            if args.mode == "bundled":
                print(
                    f"Helios UI: http://127.0.0.1:{args.helios_ui_port}; API: http://127.0.0.1:{args.helios_api_port}"
                )
                print(
                    "Metadata readiness passed. Live backends need configuration; embeddings/vector evidence search are omitted."
                )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, subprocess.CalledProcessError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
