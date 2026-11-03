"""Connect an explicitly configured, running external Helios without provisioning it."""
from __future__ import annotations

import argparse
import json
import os
from queue import Empty, Queue
from threading import Thread
from pathlib import Path
import sys
from urllib.request import build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from deployment.cai.verify import NoRedirect, probe
from semantic_hub.providers.registry import Registry, origin

PROVIDER_ID = "helios-external"
PROBE_TIMEOUT = 5


class BoundedOpener:
    """Keep the shared strict health check within a short socket timeout."""

    def __init__(self):
        self.opener = build_opener(NoRedirect)

    def open(self, request, timeout=None):
        return self.opener.open(request, timeout=PROBE_TIMEOUT)


def timed_probe(value, path, key=""):
    # Socket timeouts alone do not bound slow streaming responses or DNS lookup.
    results = Queue(maxsize=1)

    def run():
        try:
            results.put(probe(value, path, key, opener=BoundedOpener()))
        except Exception:
            results.put({"reachable": False})

    Thread(target=run, daemon=True).start()
    try:
        return results.get(timeout=PROBE_TIMEOUT)
    except Empty:
        return {"reachable": False, "reason": "timeout"}


def connect(state_dir, *, environ=None, probe_fn=None):
    """Return a nonfatal, credential-free report; preserve all existing records."""
    env = os.environ if environ is None else environ
    report = {"status": "skipped", "reason": "not_configured", "provider_id": PROVIDER_ID}
    if env.get("SEMANTIC_HUB_PROVIDER_MODE", "auto") == "builtin_only":
        return dict(report, reason="builtin_only")
    ui, api = (env.get(name, "").strip() for name in ("HELIOS_UI_ORIGIN", "HELIOS_API_ORIGIN"))
    if not ui and not api:
        return report
    if not ui or not api:
        return dict(report, status="unavailable", reason="incomplete_configuration")
    try:
        ui, api = origin(ui), origin(api)
    except (ValueError, TypeError):
        return dict(report, status="unavailable", reason="invalid_configuration")
    check = probe_fn or timed_probe
    checks = {}
    for role, value, path in (("ui", ui, "/healthz"), ("api", api, "/api/v1/healthz")):
        try:
            result = check(value, path, env.get("HELIOS_HEALTH_API_KEY", ""))
            # Do not serialize arbitrary upstream responses, exceptions, or credentials.
            checks[role] = {"reachable": result.get("reachable") is True}
        except Exception:
            checks[role] = {"reachable": False}
    report["checks"] = checks
    if not all(item["reachable"] for item in checks.values()):
        return dict(report, status="unavailable", reason="health_check_failed")
    try:
        registry = Registry(Path(state_dir))
        registry.save_provider(PROVIDER_ID, "External Helios", ui, api)
    except ValueError:
        return dict(report, status="unavailable", reason="provider_conflict")
    except Exception:
        return dict(report, status="unavailable", reason="registry_unavailable")
    return dict(report, status="connected", reason="healthy")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retry", action="store_true", help="Repeat the bounded connection check now")
    parser.parse_args(argv)
    from cai_integration.config import settings
    print(json.dumps(connect(settings()["state"]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
