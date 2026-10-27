"""Bounded, non-destructive CAI API v2 provider provisioning.

Schema: https://docs.cloudera.com/machine-learning/1.5.5/rest-api-reference/index.html
Create starts applications immediately. Older schemas expose only subdomain,
not URL; they require operator-confirmed origins instead of DNS inference.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
import time
import uuid
import fcntl
from functools import wraps
from urllib.parse import quote
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode


class ProvisionError(RuntimeError):
    pass


class CAIClient:
    def __init__(self, host, api_key, *, session=None):
        host = host.rstrip("/")
        for suffix in ("/api/v1", "/api/v2"):
            if host.endswith(suffix):
                host = host[: -len(suffix)]
        try:
            checked_origin(host)
        except ValueError:
            raise ProvisionError("Management host must be an HTTPS origin.") from None
        if not api_key:
            raise ProvisionError(
                "HTTPS management host and management API key are required."
            )
        self.base = host + "/api/v2"
        self.session = session
        self.headers = {
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        }

    def request(self, method, path, **kwargs):
        # Never include response bodies, request environments, or keys in errors.
        try:
            if self.session is not None:
                r = self.session.request(
                    method,
                    self.base + path,
                    timeout=30,
                    headers=self.headers,
                    allow_redirects=False,
                    **kwargs,
                )
                if r.status_code >= 300:
                    raise ProvisionError(
                        f"CAI management request failed (HTTP {r.status_code})."
                    )
                return r.json()
            url = self.base + path
            if kwargs.get("params"):
                url += "?" + urlencode(kwargs["params"])
            data = json.dumps(kwargs["json"]).encode() if "json" in kwargs else None

            class NoRedirect(HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None

            with build_opener(NoRedirect).open(
                Request(url, data=data, headers=self.headers, method=method), timeout=30
            ) as response:
                return json.load(response)
        except HTTPError as error:
            raise ProvisionError(
                f"CAI management request failed (HTTP {error.code})."
            ) from None
        except (URLError, TimeoutError, OSError):
            raise ProvisionError(
                "CAI management request failed; retry setup to reconcile resources."
            ) from None

    def path(self, project, ident=None):
        base = "/projects/" + quote(project, safe="") + "/applications"
        return base if ident is None else base + "/" + quote(ident, safe="")

    def list(self, project):
        result, token, seen = [], "", set()
        while True:
            page = self.request("GET", self.path(project), params={"page_token": token})
            result.extend(page.get("applications", []))
            token = page.get("next_page_token", "")
            if not token:
                return result
            if token in seen:
                raise ProvisionError("CAI returned a repeated page token.")
            seen.add(token)

    def get(self, project, ident):
        return self.request("GET", self.path(project, ident))

    def restart(self, project, ident):
        return self.request("POST", self.path(project, ident) + ":restart", json={})

    def create(self, project, payload):
        # POST is deliberately never retried: the response can be lost after creation.
        return self.request("POST", self.path(project), json=payload)


def state_directory():
    from deployment.launchers.common import configuration

    return configuration()["deployment"]


def serialized(function):
    @wraps(function)
    def wrapped(**kwargs):
        if kwargs.get("mode") != "bundled":
            return function(**kwargs)
        path = Path(kwargs["state_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return function(**kwargs)

    return wrapped


def save(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def checked_origin(value):
    from semantic_hub.providers.registry import origin

    return origin(value, local=False)


@serialized
def provision(
    *,
    mode,
    state_path,
    project_id="",
    runtime_identifier="",
    revision="",
    client=None,
    environment=None,
    origins=None,
    timeout=600,
    sleep=time.sleep,
    clock=time.monotonic,
):
    if mode not in {"bundled", "external", "builtin_only"}:
        raise ProvisionError("Unknown provider mode.")
    if mode != "bundled":
        return {"mode": mode, "stage": "skipped", "applications": {}}
    if not project_id or not runtime_identifier or not revision or client is None:
        raise ProvisionError(
            "Bundled provisioning requires project, runtime, revision, and management client."
        )
    path = Path(state_path)
    state = (
        json.loads(path.read_text())
        if path.exists()
        else {
            "deployment_id": uuid.uuid4().hex,
            "project_id": project_id,
            "mode": mode,
            "revision": revision,
            "runtime_identifier": runtime_identifier,
            "applications": {},
        }
    )
    for key, value in [
        ("project_id", project_id),
        ("mode", mode),
        ("revision", revision),
        ("runtime_identifier", runtime_identifier),
    ]:
        if state.get(key) != value:
            raise ProvisionError(
                f"Deployment {key} conflicts with the saved checkpoint."
            )
    save(path, state)
    origins = origins or {}
    for role in ("helios_api", "helios_ui"):
        marker = f'semantic-hub:{state["deployment_id"]}:{role}:{revision}'
        name = "Semantic Hub " + role.replace("_", " ")
        record = state["applications"].setdefault(role, {})
        if record.get("id"):
            app = client.get(project_id, record["id"])
        else:
            apps = client.list(project_id)
            owned = [a for a in apps if a.get("description") == marker]
            if len(owned) > 1:
                raise ProvisionError(
                    "Multiple applications claim this deployment role."
                )
            if owned:
                app = client.get(project_id, owned[0]["id"])
            else:
                if any(a.get("name") == name for a in apps):
                    raise ProvisionError(
                        "Application name conflicts with another deployment."
                    )
                payload = dict(
                    name=name,
                    description=marker,
                    script=f"deployment/launchers/{role}.py",
                    subdomain=f'sh-{state["deployment_id"][:12]}-{role.replace("helios_", "")}',
                    cpu=2,
                    memory=8,
                    runtime_identifier=runtime_identifier,
                    bypass_authentication=False,
                    environment=environment or {},
                )
                state["stage"] = "creating_" + role
                save(path, state)
                app = client.create(project_id, payload)
        if (
            app.get("description") != marker
            or app.get("bypass_authentication") is not False
        ):
            raise ProvisionError(
                "Application ownership or ingress authentication could not be verified."
            )
        if not app.get("id"):
            raise ProvisionError("CAI omitted the application identifier.")
        record["id"] = app["id"]
        save(path, state)
        for key, expected in [
            ("script", f"deployment/launchers/{role}.py"),
            ("runtime_identifier", runtime_identifier),
        ]:
            if app.get(key) != expected:
                raise ProvisionError(
                    "Application launch configuration conflicts with this deployment."
                )
        actual_environment = app.get("environment", {})
        if isinstance(actual_environment, str):
            actual_environment = json.loads(actual_environment)
        if any(actual_environment.get(k) != v for k, v in (environment or {}).items()):
            raise ProvisionError(
                "Application environment conflicts with this deployment."
            )
        value = app.get("url") or origins.get(role)
        if value:
            record.update(
                origin=checked_origin(value),
                origin_source="platform" if app.get("url") else "configured",
            )
            save(path, state)
    if any(not r.get("origin") for r in state["applications"].values()):
        raise ProvisionError(
            "CAI did not return application URLs. Supply verified HELIOS_API_ORIGIN and HELIOS_UI_ORIGIN and retry."
        )
    for role, record in state["applications"].items():
        deadline = clock() + timeout
        app = client.get(project_id, record["id"])
        restarting = str(app.get("status", "")).lower().removeprefix(
            "application_"
        ) in {"failed", "stopped"}
        if restarting:
            client.restart(project_id, record["id"])
        while True:
            app = client.get(project_id, record["id"])
            status = str(app.get("status", "")).lower().removeprefix("application_")
            record["status"] = status
            save(path, state)
            if status == "running":
                break
            if status == "starting":
                restarting = False
            if status in {"failed", "stopped", "stopping"} and not restarting:
                raise ProvisionError(
                    "Provider application is not running; inspect CAI and retry setup after recovery."
                )
            if clock() >= deadline:
                raise ProvisionError("Provider application readiness timed out.")
            sleep(5)
    state["stage"] = "applications_running"
    save(path, state)
    return state


def main():
    mode = os.environ.get("SEMANTIC_HUB_PROVIDER_MODE", "bundled")
    if mode != "bundled":
        provision(mode=mode, state_path=state_directory() / "provision.json")
        from deployment.cai.configure_providers import configure

        configure(mode)
        return
    from deployment.launchers.common import configuration

    cfg = configuration()
    lock = json.loads((cfg["root"] / "deployment/provider-lock.json").read_text())
    state = provision(
        mode=mode,
        state_path=state_directory() / "provision.json",
        project_id=os.environ.get("CDSW_PROJECT_ID")
        or os.environ.get("CML_PROJECT_ID", ""),
        runtime_identifier=os.environ.get("SEMANTIC_HUB_RUNTIME_IDENTIFIER", ""),
        revision=lock["helios"]["commit"],
        client=CAIClient(
            os.environ.get("CDSW_API_URL", ""), os.environ.get("CDSW_APIV2_KEY", "")
        ),
        environment={
            "SEMANTIC_HUB_PROVIDER_MODE": mode,
            **{
                k: v
                for k, v in os.environ.items()
                if k
                in {
                    "SEMANTIC_HUB_STATE_DIR",
                    "SEMANTIC_HUB_DEPLOYMENT_STATE_DIR",
                    "HELIOS_STATE_DIR",
                    "HELIOS_ARTIFACT_DIR",
                    "HELIOS_CAI_PROXY_AUTH_CONFIRMED",
                }
            },
        },
        origins={
            role: os.environ.get(key)
            for role, key in [
                ("helios_api", "HELIOS_API_ORIGIN"),
                ("helios_ui", "HELIOS_UI_ORIGIN"),
            ]
        },
    )
    from deployment.cai.configure_providers import configure

    configure(mode, state=state)
    state["stage"] = "provider_registered"
    save(state_directory() / "provision.json", state)


if __name__ == "__main__":
    import sys

    sys.path.insert(
        0, str(Path(os.environ.get("CDSW_PROJECT_DIR") or Path.cwd()).resolve())
    )
    main()
