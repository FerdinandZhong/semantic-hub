import json
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from semantic_hub.api import install
from semantic_hub.providers.discovery import Discovery


@pytest.fixture
def setup(tmp_path, monkeypatch):
    class Hub:
        def catalog(self):
            return {"sources": []}

    monkeypatch.setenv("SEMANTIC_HUB_API_TOKEN", "hub-token")
    app = FastAPI()
    app.state.local_no_auth = True
    app.state.platform_auth = False
    install(app, Hub(), tmp_path, local=True)
    app.state.provider_registry.save_provider(
        "team", "Team", "https://ui.test", "https://api.test"
    )
    calls = []
    state = {"status": 200, "wrong_org": False}

    def handler(request):
        calls.append(request)
        key = request.headers.get("authorization")
        if state["status"] != 200:
            return httpx.Response(
                state["status"],
                text="secret upstream details",
                headers={"Location": "https://evil.test"},
            )
        if request.url.path.endswith("/organizations"):
            return httpx.Response(
                200, json={"organizations": [{"id": "org", "name": "Organization"}]}
            )
        model = {
            "id": "a" if key == "Bearer alice" else "b",
            "name": "Model",
            "organization_id": "other" if state["wrong_org"] else "org",
        }
        if request.url.path.endswith("/models"):
            assert request.url.params["organization_id"] == "org"
            return httpx.Response(
                200, json={"models": [model] if key != "Bearer empty" else []}
            )
        return httpx.Response(200, json=model)

    original = httpx.Client
    monkeypatch.setattr(
        "semantic_hub.providers.discovery.httpx.Client",
        lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    )
    return TestClient(app), calls, state, app


BASE = "/api/semantic-hub/v2"


def test_private_ca_bundle_is_loaded_without_proxy_inheritance(setup, monkeypatch):
    client, _, _, _ = setup
    import ssl

    context = ssl.create_default_context()
    calls = []
    monkeypatch.setenv("SSL_CERT_FILE", "/operator/ca.pem")

    def load_context(*, cafile):
        calls.append(cafile)
        return context

    monkeypatch.setattr(
        "semantic_hub.providers.discovery.ssl.create_default_context", load_context
    )
    response = client.post(
        BASE + "/providers/team/discover",
        json={},
        headers={"X-Helios-API-Key": "alice"},
    )
    assert response.status_code == 200
    assert calls == ["/operator/ca.pem"]


def test_invalid_ca_configuration_returns_safe_error(setup, monkeypatch):
    client, _, _, _ = setup
    monkeypatch.setenv("SSL_CERT_FILE", "/missing/private-ca.pem")
    response = client.post(
        BASE + "/providers/team/discover",
        json={},
        headers={"X-Helios-API-Key": "alice"},
    )
    assert response.status_code == 502
    assert "private-ca" not in response.text


def test_link_reuses_legacy_reference_after_permission_check(setup):
    client, calls, _, app = setup
    legacy = dict(
        id="external-old-random",
        name="Original name",
        provider_id="team",
        organization_id="org",
        model_id="a",
    )
    with app.state.provider_registry.connect() as db:
        db.execute(
            "INSERT INTO projects VALUES (?, ?)", (legacy["id"], json.dumps(legacy))
        )
    response = client.post(
        BASE + "/projects",
        json={
            "name": "New name",
            "provider_id": "team",
            "organization_id": "org",
            "model_id": "a",
        },
        headers={"X-Helios-API-Key": "alice"},
    )
    assert response.status_code == 201
    assert response.json() == legacy
    assert len(app.state.provider_registry.projects()) == 1
    assert calls[-1].url.path.endswith("/models/a")


def test_discovery_is_permission_filtered_and_credentials_are_isolated(setup):
    client, calls, _, _ = setup
    for key, ident in [("alice", "a"), ("bob", "b")]:
        response = client.post(
            BASE + "/providers/team/discover",
            json={"organization_id": "org"},
            headers={
                "X-Helios-API-Key": key,
                "Authorization": "Bearer hub",
                "Cookie": "session=secret",
                "X-User": "admin",
            },
        )
        assert response.status_code == 200
        assert response.json()["models"][0]["id"] == ident
        assert response.headers["cache-control"] == "no-store"
    for request in calls:
        assert not any(
            h in request.headers for h in ["cookie", "x-user", "x-helios-api-key"]
        )
        assert request.headers["authorization"] in {"Bearer alice", "Bearer bob"}
        assert "/organizations/org/models" not in request.url.path
    assert client.post(BASE + "/providers/team/discover", json={}).status_code == 401
    assert (
        client.post(
            BASE + "/providers/team/discover",
            json={},
            headers={"X-Helios-API-Key": "alice"},
        ).json()["models"]
        == []
    )
    assert (
        client.post(
            BASE + "/providers/team/discover",
            json={"organization_id": "org"},
            headers={"X-Helios-API-Key": "empty"},
        ).json()["models"]
        == []
    )


@pytest.mark.parametrize("status", [302, 401, 403, 404, 500])
def test_safe_errors_and_no_redirects(setup, status):
    client, calls, state, _ = setup
    state["status"] = status
    response = client.post(
        BASE + "/providers/team/discover",
        json={},
        headers={"X-Helios-API-Key": "alice"},
    )
    assert response.status_code == (status if status in (401, 403, 404) else 502)
    assert "secret" not in response.text
    assert len(calls) == 1


def test_save_rechecks_permission_org_and_is_idempotent(setup):
    client, calls, state, _ = setup
    body = dict(name="Saved", provider_id="team", organization_id="org", model_id="a")
    headers = {"X-Helios-API-Key": "alice"}
    first = client.post(BASE + "/projects", json=body, headers=headers)
    assert first.status_code == 201
    assert (
        client.post(BASE + "/projects", json=body, headers=headers).json()
        == first.json()
    )
    assert len(client.get(BASE + "/workspaces").json()["items"]) == 1
    state["wrong_org"] = True
    assert (
        client.post(BASE + "/projects", json=body, headers=headers).status_code == 403
    )
    state["status"] = 403
    assert (
        client.post(BASE + "/projects", json=body, headers=headers).status_code == 403
    )
    assert all(r.url.path == "/api/v1/models/a" for r in calls)


def test_mutation_guards_apply_before_upstream(setup):
    client, calls, _, app = setup
    headers = {"X-Helios-API-Key": "alice", "Origin": "https://evil.test"}
    assert (
        client.post(
            BASE + "/providers/team/discover", json={}, headers=headers
        ).status_code
        == 403
    )
    app.state.local_no_auth = False
    app.state.platform_auth = False
    assert (
        client.post(
            BASE + "/providers/team/discover",
            json={},
            headers={"X-Helios-API-Key": "alice", "Authorization": "Bearer hub-token"},
        ).status_code
        == 403
    )
    assert not calls


def test_malformed_and_oversized_payloads(monkeypatch):
    from semantic_hub.providers import discovery

    original = httpx.Client
    for payload in [
        b"no json",
        b"[]",
        b'{"organizations": [null]}',
        b"x" * (discovery.MAX_BYTES + 1),
    ]:
        monkeypatch.setattr(
            discovery.httpx,
            "Client",
            lambda **kw: original(
                transport=httpx.MockTransport(
                    lambda req: httpx.Response(200, content=payload)
                ),
                **kw,
            ),
        )
        with pytest.raises(Exception) as exc:
            Discovery(
                {"kind": "helios", "api_origin": "https://api.test"}, "alice"
            ).discover()
        assert exc.value.status_code == 502


def test_loopback_only_allows_keyless_local_mode():
    provider = {"kind": "helios", "api_origin": "http://127.0.0.1:8201"}
    assert "Authorization" not in Discovery(provider, None, local=True).headers
    with pytest.raises(Exception) as exc:
        Discovery(provider, None, local=False)
    assert exc.value.status_code == 401
    provider["api_origin"] = "https://remote.test"
    with pytest.raises(Exception) as exc:
        Discovery(provider, None, local=True)
    assert exc.value.status_code == 401


def test_discovery_rejects_unknown_org_and_inconsistent_models(setup):
    client, calls, state, _ = setup
    headers = {"X-Helios-API-Key": "alice"}
    assert (
        client.post(
            BASE + "/providers/team/discover",
            json={"organization_id": "unknown"},
            headers=headers,
        ).status_code
        == 403
    )
    assert len(calls) == 1
    state["wrong_org"] = True
    assert (
        client.post(
            BASE + "/providers/team/discover",
            json={"organization_id": "org"},
            headers=headers,
        ).status_code
        == 502
    )
