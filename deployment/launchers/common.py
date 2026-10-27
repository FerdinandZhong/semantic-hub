"""Isolated CAI process specifications; no provisioning occurs during startup."""

from __future__ import annotations
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

MODES = {"bundled", "external", "builtin_only"}


def configuration(root=None):
    root = Path(
        root
        or os.environ.get("CDSW_PROJECT_DIR")
        or Path(__file__).resolve().parents[2]
    ).resolve()
    mode = os.environ.get("SEMANTIC_HUB_PROVIDER_MODE", "bundled")
    if mode not in MODES:
        raise RuntimeError("Invalid SEMANTIC_HUB_PROVIDER_MODE")

    def path(key, default):
        value = Path(os.environ.get(key) or default).expanduser()
        return (value if value.is_absolute() else root / value).resolve()

    hub = path("SEMANTIC_HUB_STATE_DIR", root / "state/semantic-hub")
    deployment = path("SEMANTIC_HUB_DEPLOYMENT_STATE_DIR", hub.parent / "deployment")
    provider = path("HELIOS_STATE_DIR", hub.parent / "helios")
    artifacts = path("HELIOS_ARTIFACT_DIR", deployment / "helios-ui")
    if hub == provider or hub in provider.parents or provider in hub.parents:
        raise RuntimeError("Hub and Helios state directories must be separate")
    return dict(
        root=root,
        mode=mode,
        hub=hub,
        provider=provider,
        deployment=deployment,
        artifacts=artifacts,
    )


def origin(value):
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("CAI origins must be exact HTTPS origins")
    return value


def discovered_origin(cfg, service, *, timeout=300):
    key = "HELIOS_API_URL" if service == "helios_api" else "HELIOS_UI_ORIGINS"
    alternative = "HELIOS_API_ORIGIN" if service == "helios_api" else "HELIOS_UI_ORIGIN"
    if os.environ.get(alternative):
        return origin(os.environ[alternative].rstrip("/"))
    if os.environ.get(key):
        return origin(os.environ[key].rstrip("/"))
    deadline = time.monotonic() + timeout
    while True:
        try:
            data = json.loads((cfg["deployment"] / "provision.json").read_text())
            value = data.get("applications", {}).get(service, {}).get("origin")
            if value:
                return origin(value.rstrip("/"))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Timed out waiting for assigned {service} origin")
        time.sleep(1)


def specification(service, root=None):
    from cai_integration.environment import isolated_environment
    from deployment.local.run import validate_lock

    cfg = configuration(root)
    root = cfg["root"]
    if any(os.environ.get(key) for key in ("HELIOS_DEV", "HELIOS_DEV_USER")):
        raise RuntimeError("Development identity is forbidden in CAI launchers")
    port = int(os.environ.get("CDSW_APP_PORT", "0"))
    if not 1 <= port <= 65535:
        raise RuntimeError("CAI must inject a valid CDSW_APP_PORT")
    native = service != "hub"
    checkout = root
    if native:
        if cfg["mode"] != "bundled":
            raise RuntimeError("Native launchers require bundled mode")
        checkout = validate_lock(root)
        # This operator attestation is not a substitute for live spoofing tests.
        if os.environ.get("HELIOS_CAI_PROXY_AUTH_CONFIRMED") != "1":
            raise RuntimeError(
                "Confirm authenticated ingress strips client identity headers: HELIOS_CAI_PROXY_AUTH_CONFIRMED=1"
            )
    venv = root / (".venv-helios" if native else ".venv-semantic-hub")
    python = venv / "bin/python"
    if not python.is_file():
        raise RuntimeError("Run deployment/cai/prepare.py before starting applications")
    env = isolated_environment(venv)
    for key in list(env):
        if key in {
            "HELIOS_ROOT",
            "HELIOS_METADATA_DB",
            "HELIOS_RUNS_DIR",
            "HELIOS_EVIDENCE_INDEX",
            "HELIOS_DEMO_STATE",
            "HELIOS_API_URL",
            "HELIOS_UI_ORIGINS",
        }:
            env.pop(key)
    env.update(
        SEMANTIC_HUB_STATE_DIR=str(cfg["hub"]),
        CDSW_PROJECT_DIR=str(root),
        CDSW_APP_PORT=str(port),
    )
    if native:
        state = cfg["provider"]
        state.mkdir(parents=True, exist_ok=True)
        env.update(
            HELIOS_ROOT=str(state),
            HELIOS_METADATA_DB=str(state / "helios.db"),
            HELIOS_RUNS_DIR=str(state / "runs"),
            HELIOS_EVIDENCE_INDEX=str(state / "evidence.lance"),
            PYSTOW_HOME=str(state / "pystow"),
        )
        if service == "helios-api":
            env["HELIOS_UI_ORIGINS"] = discovered_origin(cfg, "helios_ui")
        else:
            env.update(
                HELIOS_ROOT=str(cfg["artifacts"]),
                HELIOS_API_URL=discovered_origin(cfg, "helios_api"),
            )
    return (
        [
            str(python),
            "-I",
            "-u",
            str(root / "deployment/launchers/bootstrap.py"),
            str(checkout),
            service,
            str(port),
        ],
        env,
        checkout,
    )


def launch(service):
    from cai_integration.start_application import supervise

    command, env, cwd = specification(service)
    supervise(command, env=env, cwd=cwd)
