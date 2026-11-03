"""Optional Helios must never prevent a standalone Hub from starting."""
import json
from unittest.mock import Mock

import pytest

from deployment.cai import connect_external as external
from semantic_hub.providers.registry import Registry

ENV = {"HELIOS_UI_ORIGIN": "https://ui.example", "HELIOS_API_ORIGIN": "https://api.example"}


def healthy(*args):
    return {"reachable": True, "http_status": 200}


@pytest.mark.parametrize("env,reason", [({}, "not_configured"),
    ({"HELIOS_UI_ORIGIN": ENV["HELIOS_UI_ORIGIN"]}, "incomplete_configuration"),
    ({**ENV, "HELIOS_API_ORIGIN": "https://user:secret@api.example"}, "invalid_configuration"),
    ({**ENV, "SEMANTIC_HUB_PROVIDER_MODE": "builtin_only"}, "builtin_only")])
def test_unconfigured_does_not_probe_or_create_state(tmp_path, env, reason):
    check = Mock()
    state = tmp_path / "state"
    assert external.connect(state, environ=env, probe_fn=check)["reason"] == reason
    check.assert_not_called()
    assert not state.exists()


def test_healthy_registers_only_provider_and_is_repeatable(tmp_path):
    for _ in range(2):
        assert external.connect(tmp_path, environ=ENV, probe_fn=healthy)["status"] == "connected"
    registry = Registry(tmp_path)
    assert [p["id"] for p in registry.providers()] == ["builtin", external.PROVIDER_ID]
    assert registry.projects() == []
    provider = registry.provider(external.PROVIDER_ID)
    assert provider["ui_origin"] == ENV["HELIOS_UI_ORIGIN"]
    assert provider["api_origin"] == ENV["HELIOS_API_ORIGIN"]


@pytest.mark.parametrize("result", [{"reachable": False, "http_status": code} for code in (302, 401, 403, 500)] + [{"reachable": False}])
def test_failed_health_leaves_fresh_hub_builtin_only(tmp_path, result):
    report = external.connect(tmp_path, environ=ENV, probe_fn=lambda *a: result)
    assert report["status"] == "unavailable"
    assert [p["id"] for p in Registry(tmp_path).providers()] == ["builtin"]


def test_outage_preserves_manual_projects_and_provider(tmp_path):
    registry = Registry(tmp_path)
    registry.save_provider("manual", "Manual", "https://other-ui.example", "https://other-api.example")
    registry.add_project("Existing", "manual", "org-original", "model-original")
    external.connect(tmp_path, environ=ENV, probe_fn=healthy)
    before = (registry.providers(), registry.projects())
    report = external.connect(tmp_path, environ=ENV, probe_fn=lambda *a: {"reachable": False})
    assert report["status"] == "unavailable"
    assert (registry.providers(), registry.projects()) == before


def test_conflicting_origin_is_not_overwritten(tmp_path):
    registry = Registry(tmp_path)
    registry.save_provider(external.PROVIDER_ID, "External Helios", "https://old-ui.example", "https://old-api.example")
    before = registry.providers()
    assert external.connect(tmp_path, environ=ENV, probe_fn=healthy)["reason"] == "provider_conflict"
    assert registry.providers() == before


def test_only_explicit_health_key_is_used_and_no_secrets_are_serialized(tmp_path):
    calls = []
    def check(value, path, key):
        calls.append((value, path, key))
        return {"reachable": True, "secret": key}
    report = external.connect(tmp_path, environ={**ENV, "CDSW_APIV2_KEY": "owner-secret"}, probe_fn=check)
    assert all(key == "" for _, _, key in calls)
    calls.clear()
    report = external.connect(tmp_path, environ={**ENV, "HELIOS_HEALTH_API_KEY": "health-secret"}, probe_fn=check)
    assert all(key == "health-secret" for _, _, key in calls)
    assert "secret" not in json.dumps(report)
    assert b"health-secret" not in (tmp_path / "providers.sqlite").read_bytes()


def test_probe_exception_is_nonfatal_and_sanitized(tmp_path):
    def fail(*args):
        raise RuntimeError("secret")
    report = external.connect(tmp_path, environ=ENV, probe_fn=fail)
    assert report["reason"] == "health_check_failed"
    assert "secret" not in json.dumps(report)


def test_bounded_opener_uses_no_redirect_and_five_second_timeout(monkeypatch):
    inner = Mock()
    factory = Mock(return_value=inner)
    monkeypatch.setattr(external, "build_opener", factory)
    external.BoundedOpener().open("request", timeout=20)
    factory.assert_called_once_with(external.NoRedirect)
    inner.open.assert_called_once_with("request", timeout=5)


def test_timed_probe_bounds_slow_network(monkeypatch):
    from threading import Event
    release = Event()
    def slow(*args, **kwargs):
        release.wait(2)
        return {"reachable": True}
    monkeypatch.setattr(external, "probe", slow)
    monkeypatch.setattr(external, "PROBE_TIMEOUT", 0.01)
    try:
        assert external.timed_probe("https://api.example", "/healthz")["reason"] == "timeout"
    finally:
        release.set()


@pytest.mark.parametrize("available", [False, True])
def test_cai_bootstrap_checks_optional_provider_before_serving(tmp_path, monkeypatch, available):
    """Exercise the actual isolated child entry point without a CAI server."""
    import runpy
    import sys
    from pathlib import Path
    from unittest.mock import patch

    root = Path(__file__).resolve().parents[2]
    for key in ("HELIOS_DEV", "HELIOS_DEV_USER", "SEMANTIC_HUB_PROVIDER_MODE"):
        monkeypatch.delenv(key, raising=False)
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(external, "timed_probe", lambda *args: {"reachable": available})
    monkeypatch.setattr(sys, "argv", ["bootstrap.py", str(root), "hub", "8123"])
    expected = ["builtin", external.PROVIDER_ID] if available else ["builtin"]

    def serve(*args, **kwargs):
        assert [p["id"] for p in Registry(tmp_path).providers()] == expected
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == 8123

    with patch("cai_integration.application.create_app") as create, patch(
        "cai_integration.config.settings", return_value={"state": tmp_path}
    ), patch("uvicorn.run", side_effect=serve) as server:
        runpy.run_path(str(root / "deployment/launchers/bootstrap.py"), run_name="__main__")
    create.assert_called_once_with(local=False)
    server.assert_called_once()
