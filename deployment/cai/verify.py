"""Check application endpoints without claiming full CAI acceptance."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from deployment.cai.provision import checked_origin, save
from deployment.launchers.common import configuration


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe(origin, path, key="", *, opener=None):
    url = checked_origin(origin) + path
    headers = {"Authorization": "Bearer " + key} if key else {}
    try:
        with (opener or build_opener(NoRedirect)).open(
            Request(url, headers=headers), timeout=20
        ) as response:
            body = response.read(65536)
            if path == "/healthz" and body.strip() == b"ok":
                valid = True
            else:
                try:
                    value = json.loads(body)
                    valid = isinstance(value, dict) and "status" in value
                except (ValueError, UnicodeDecodeError):
                    valid = False
            return {
                "reachable": response.status == 200 and valid,
                "http_status": response.status,
                "reason": "health_response" if valid else "unexpected_response",
            }
    except HTTPError as error:
        return {
            "reachable": False,
            "http_status": error.code,
            "reason": "authentication_or_http_error",
        }
    except (URLError, TimeoutError, OSError):
        return {"reachable": False, "reason": "connection_failed"}


def verify(mode, hub_origin, provider_origins=None, *, key="", probe_fn=probe):
    if mode not in {"bundled", "external", "builtin_only"}:
        raise ValueError("Unknown provider mode")
    targets = {"hub": (hub_origin, "/healthz")}
    if mode != "builtin_only":
        origins = provider_origins or {}
        targets.update(
            helios_api=(origins["helios_api"], "/api/v1/healthz"),
            helios_ui=(origins["helios_ui"], "/healthz"),
        )
    checks = {
        role: probe_fn(origin, path, key) for role, (origin, path) in targets.items()
    }
    return {
        "mode": mode,
        "endpoints_reachable": all(c["reachable"] for c in checks.values()),
        "checks": checks,
        "cai_acceptance": "pending",
        "browser_identity_verified": False,
        "native_query_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hub-origin", required=True)
    args = parser.parse_args()
    cfg = configuration()
    origins = {}
    if cfg["mode"] == "bundled":
        state = json.loads((cfg["deployment"] / "provision.json").read_text())
        origins = {
            role: state["applications"][role]["origin"]
            for role in ("helios_api", "helios_ui")
        }
    elif cfg["mode"] == "external":
        origins = {
            "helios_api": os.environ.get("HELIOS_API_ORIGIN", ""),
            "helios_ui": os.environ.get("HELIOS_UI_ORIGIN", ""),
        }
    # Use a caller-supplied key; never serialize it or forward it through redirects.
    report = verify(
        cfg["mode"], args.hub_origin, origins, key=os.environ.get("CDSW_APIV2_KEY", "")
    )
    save(cfg["deployment"] / "verification.json", report)
    print(json.dumps(report, indent=2))
    return 0 if report["endpoints_reachable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
