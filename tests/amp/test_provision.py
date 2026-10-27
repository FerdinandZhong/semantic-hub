import json
from copy import deepcopy
import pytest
from deployment.cai.provision import provision, ProvisionError, CAIClient


class FakeClient:
    def __init__(self):
        self.apps = {}
        self.creates = 0
        self.lose_response = False

    def list(self, project):
        return list(self.apps.values())

    def get(self, project, ident):
        return deepcopy(self.apps[ident])

    def restart(self, project, ident):
        pass

    def create(self, project, payload):
        self.creates += 1
        ident = str(self.creates)
        app = dict(
            payload,
            id=ident,
            url=f"https://app-{ident}.example.test",
            status="APPLICATION_RUNNING",
        )
        self.apps[ident] = app
        if self.lose_response:
            self.lose_response = False
            raise ProvisionError("Response lost")
        return deepcopy(app)


def run(tmp_path, client, **kwargs):
    return provision(
        mode="bundled",
        state_path=tmp_path / "provision.json",
        project_id="project",
        runtime_identifier="runtime",
        revision="revision",
        client=client,
        **kwargs,
    )


def test_create_and_reuse(tmp_path):
    client = FakeClient()
    state = run(tmp_path, client)
    assert state["stage"] == "applications_running"
    assert run(tmp_path, client) == state
    assert client.creates == 2
    assert all(a["bypass_authentication"] is False for a in client.apps.values())
    assert all("CDSW_APIV2_KEY" not in a["environment"] for a in client.apps.values())


def test_lost_response_reconciles_ownership(tmp_path):
    client = FakeClient()
    client.lose_response = True
    with pytest.raises(ProvisionError):
        run(tmp_path, client)
    state = run(tmp_path, client)
    assert client.creates == 2
    assert state["applications"]["helios_api"]["id"] == "1"


def test_partial_failure_preserves_ids(tmp_path):
    client = FakeClient()
    run(tmp_path, client)
    client.apps["2"]["status"] = "APPLICATION_FAILED"
    with pytest.raises(ProvisionError, match="timed out"):
        run(tmp_path, client, timeout=0)
    assert (
        json.loads((tmp_path / "provision.json").read_text())["applications"][
            "helios_api"
        ]["id"]
        == "1"
    )
    client.apps["2"]["status"] = "APPLICATION_RUNNING"
    run(tmp_path, client)
    assert client.creates == 2


@pytest.mark.parametrize("mode", ["external", "builtin_only"])
def test_skipped_modes_require_no_client_or_state(tmp_path, mode):
    assert provision(mode=mode, state_path=tmp_path / "state")["stage"] == "skipped"
    assert not (tmp_path / "state").exists()


def test_reject_foreign_name(tmp_path):
    client = FakeClient()
    client.apps["foreign"] = dict(id="foreign", name="Semantic Hub helios api")
    with pytest.raises(ProvisionError, match="conflicts"):
        run(tmp_path, client)
    assert client.creates == 0


def test_reject_changed_revision(tmp_path):
    client = FakeClient()
    run(tmp_path, client)
    path = tmp_path / "provision.json"
    state = json.loads(path.read_text())
    state["revision"] = "different"
    path.write_text(json.dumps(state))
    with pytest.raises(ProvisionError, match="revision"):
        run(tmp_path, client)


def test_reject_disabled_ingress(tmp_path):
    client = FakeClient()
    run(tmp_path, client)
    client.apps["1"]["bypass_authentication"] = True
    with pytest.raises(ProvisionError, match="authentication"):
        run(tmp_path, client)


def test_timeout_bounded(tmp_path):
    client = FakeClient()
    run(tmp_path, client)
    client.apps["1"]["status"] = "APPLICATION_STARTING"
    with pytest.raises(ProvisionError, match="timed out"):
        run(tmp_path, client, timeout=0)


def test_missing_url_keeps_id_for_retry(tmp_path):
    client = FakeClient()
    original = client.create

    def create(project, payload):
        app = original(project, payload)
        client.apps[app["id"]].pop("url")
        app.pop("url")
        return app

    client.create = create
    with pytest.raises(ProvisionError, match="HELIOS_API_ORIGIN"):
        run(tmp_path, client)
    assert client.creates == 2
    state = run(
        tmp_path,
        client,
        origins={
            "helios_api": "https://api.example.test",
            "helios_ui": "https://ui.example.test",
        },
    )
    assert client.creates == 2
    assert state["applications"]["helios_api"]["origin_source"] == "configured"


def test_http_errors_do_not_expose_response_secrets():
    class Session:
        headers = {}

        def request(self, *args, **kwargs):
            return type("Response", (), {"status_code": 403, "text": "super-secret"})()

    client = CAIClient("https://workbench.example.test", "key", session=Session())
    with pytest.raises(ProvisionError) as err:
        client.list("project")
    assert "super-secret" not in str(err.value)


def test_owned_stopped_application_restarts_on_retry(tmp_path):
    client = FakeClient()
    run(tmp_path, client)
    client.apps["1"]["status"] = "APPLICATION_STOPPED"
    restarted = []

    def restart(project, ident):
        restarted.append(ident)
        client.apps[ident]["status"] = "APPLICATION_RUNNING"

    client.restart = restart
    run(tmp_path, client)
    assert restarted == ["1"]
    assert client.creates == 2


def test_reuse_rejects_changed_launcher(tmp_path):
    client = FakeClient()
    run(tmp_path, client)
    client.apps["1"]["script"] = "foreign.py"
    with pytest.raises(ProvisionError, match="configuration"):
        run(tmp_path, client)


def test_management_redirect_is_rejected():
    class Session:
        def request(self, *args, **kwargs):
            assert kwargs["allow_redirects"] is False
            return type("Response", (), {"status_code": 302})()

    client = CAIClient("https://workbench.example.test", "key", session=Session())
    with pytest.raises(ProvisionError, match="302"):
        client.list("project")


def test_restart_tolerates_stale_stopped_status(tmp_path):
    client = FakeClient()
    run(tmp_path, client)
    client.apps["1"]["status"] = "APPLICATION_STOPPED"
    counts = []

    def restart(project, ident):
        counts.append(ident)

    def sleep(seconds):
        client.apps["1"]["status"] = "APPLICATION_RUNNING"

    client.restart = restart
    run(tmp_path, client, sleep=sleep)
    assert counts == ["1"]
