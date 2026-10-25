from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from semantic_hub.api import install
from semantic_hub.providers.registry import Registry, origin


@pytest.mark.parametrize(
    "url",
    [
        "http://remote.test",
        "https://user:secret@host.test",
        "https://host.test/path",
        "https://host.test?q=1",
        "javascript:alert(1)",
        "https://host.test:wrong",
    ],
)
def test_origin_rejects_unsafe_or_non_origin_values(url):
    with pytest.raises(ValueError):
        origin(url, local=True)


def test_loopback_requires_local_mode():
    assert origin("http://127.0.0.1:8100/", local=True) == "http://127.0.0.1:8100"
    with pytest.raises(ValueError):
        origin("http://127.0.0.1:8100")


def test_registration_is_idempotent_and_does_not_retarget_projects(tmp_path):
    registry = Registry(tmp_path)
    args = ("helios-team", "Team", "https://ui.test", "https://api.test")
    registry.save_provider(*args)
    registry.save_provider(*args)
    project = registry.add_project(
        "Finance", "helios-team", "org & admin=1", "model/name"
    )
    assert len(registry.providers()) == 2
    assert parse_qs(urlsplit(registry.links(project)["studio"]).query) == {
        "organization": ["org & admin=1"],
        "model": ["model/name"],
    }
    with pytest.raises(ValueError):
        registry.save_provider(
            "helios-team", "Team", "https://other.test", "https://api.test"
        )
    with pytest.raises(ValueError):
        registry.add_project("Finance", "builtin", "org", "model")
    assert Registry(tmp_path).projects() == [project]


def test_api_auth_registration_and_workspace_identity(tmp_path, monkeypatch):
    class Hub:
        def catalog(self):
            return {
                "sources": [
                    dict(
                        id="finance",
                        name="Finance",
                        kind="local",
                        description="Sample",
                        model={"status": "published"},
                        studio_url="/demo/context?source=finance",
                    )
                ]
            }

    app = FastAPI()
    app.state.local_no_auth = False
    app.state.platform_auth = False
    install(app, Hub(), tmp_path)
    monkeypatch.setenv("SEMANTIC_HUB_API_TOKEN", "test-secret")
    client = TestClient(app)
    prefix = "/api/semantic-hub/v2"
    assert client.get(prefix + "/providers").status_code == 401
    client.headers["Authorization"] = "Bearer test-secret"
    body = dict(
        id="helios-team",
        name="Team",
        ui_origin="https://ui.test",
        api_origin="https://api.test",
    )
    assert client.post(prefix + "/providers", json=body).status_code == 403
    app.state.local_no_auth = True
    assert (
        client.post(
            prefix + "/providers", json=body, headers={"Origin": "https://evil.test"}
        ).status_code
        == 403
    )
    assert client.post(prefix + "/providers", json=body).status_code == 201
    response = client.post(
        prefix + "/projects",
        json=dict(
            name="External finance",
            provider_id="helios-team",
            organization_id="org",
            model_id="native",
        ),
    )
    assert response.status_code == 201, response.text
    items = client.get(prefix + "/workspaces").json()["items"]
    assert items[0]["id"] == "finance" and items[0]["provider_id"] == "builtin"
    assert items[1]["native"] is False and items[1]["model"] is None
    assert (
        items[1]["links"]["chat"]
        == "https://ui.test/talk?organization=org&model=native"
    )
