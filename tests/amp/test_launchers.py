"""CAI launch specifications do not install packages or provision resources."""

import json
from unittest.mock import patch
import pytest
from deployment.launchers import common
from deployment.cai import prepare


def fixture_root(tmp_path):
    (tmp_path / ".venv-semantic-hub/bin").mkdir(parents=True)
    (tmp_path / ".venv-semantic-hub/bin/python").touch()
    (tmp_path / ".venv-helios/bin").mkdir(parents=True)
    (tmp_path / ".venv-helios/bin/python").touch()
    return tmp_path


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for key in list(common.os.environ):
        if key.startswith(("HELIOS_", "SEMANTIC_HUB_")):
            monkeypatch.delenv(key)
    monkeypatch.setenv("CDSW_APP_PORT", "8123")


@pytest.mark.parametrize("mode", ["external", "builtin_only"])
def test_hub_does_not_require_checkout(tmp_path, monkeypatch, mode):
    root = fixture_root(tmp_path)
    monkeypatch.setenv("SEMANTIC_HUB_PROVIDER_MODE", mode)
    with patch(
        "deployment.local.run.validate_lock",
        side_effect=AssertionError("must not inspect native checkout"),
    ):
        command, env, cwd = common.specification("hub", root)
    assert command[1:3] == ["-I", "-u"]
    assert command[-1] == "8123"
    assert env["SEMANTIC_HUB_STATE_DIR"] == str(root / "state/semantic-hub")
    assert cwd == root


def test_native_uses_discovered_origins_and_separate_state(tmp_path, monkeypatch):
    root = fixture_root(tmp_path)
    deployment = root / "state/deployment"
    deployment.mkdir(parents=True)
    (deployment / "provision.json").write_text(
        json.dumps(
            {
                "applications": {
                    "helios_ui": {"origin": "https://ui.example"},
                    "helios_api": {"origin": "https://api.example"},
                }
            }
        )
    )
    monkeypatch.setenv("HELIOS_CAI_PROXY_AUTH_CONFIRMED", "1")
    monkeypatch.setenv("HELIOS_METADATA_DB", "/wrong/hub.db")
    with patch(
        "deployment.local.run.validate_lock", return_value=root / "external/helios"
    ):
        command, env, cwd = common.specification("helios-api", root)
        _, ui, _ = common.specification("helios-ui", root)
    assert cwd == root / "external/helios"
    assert command[-2:] == ["helios-api", "8123"]
    assert env["HELIOS_UI_ORIGINS"] == "https://ui.example"
    assert env["HELIOS_METADATA_DB"] == str(root / "state/helios/helios.db")
    assert ui["HELIOS_API_URL"] == "https://api.example"
    assert ui["HELIOS_ROOT"] == str(deployment / "helios-ui")


@pytest.mark.parametrize("key", ["HELIOS_DEV", "HELIOS_DEV_USER"])
def test_rejects_development_identity(tmp_path, monkeypatch, key):
    monkeypatch.setenv(key, "1")
    with pytest.raises(RuntimeError, match="Development identity"):
        common.specification("hub", fixture_root(tmp_path))


def test_native_requires_explicit_proxy_attestation(tmp_path):
    with patch("deployment.local.run.validate_lock", return_value=tmp_path):
        with pytest.raises(RuntimeError, match="strips client identity"):
            common.specification("helios-api", fixture_root(tmp_path))


@pytest.mark.parametrize(
    "value",
    [
        "https://user:secret@example",
        "https://example/path",
        "http://example",
        "https://example?secret=1",
        "https://example#fragment",
    ],
)
def test_origin_rejects_unsafe_configuration(value):
    with pytest.raises(RuntimeError):
        common.origin(value)


def test_missing_discovery_has_bounded_failure(tmp_path):
    with pytest.raises(RuntimeError, match="Timed out"):
        common.discovered_origin(common.configuration(tmp_path), "helios_ui", timeout=0)


def test_state_overlap_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "HELIOS_STATE_DIR", str(tmp_path / "state/semantic-hub/provider")
    )
    with pytest.raises(RuntimeError, match="separate"):
        common.configuration(tmp_path)


@pytest.mark.parametrize("mode", ["external", "builtin_only"])
def test_prepare_skips_native_code_and_install(tmp_path, monkeypatch, mode):
    monkeypatch.setenv("SEMANTIC_HUB_PROVIDER_MODE", mode)
    monkeypatch.setenv("HELIOS_UI_ORIGIN", "https://ui.example")
    monkeypatch.setenv("HELIOS_API_ORIGIN", "https://api.example")
    with patch("deployment.cai.prepare.subprocess.run") as run, patch(
        "deployment.local.run.validate_lock",
        side_effect=AssertionError("native checkout not needed"),
    ):
        result = prepare.prepare(tmp_path)
    assert result == {"mode": mode, "native_prepared": False}
    assert run.call_count == 1
    assert run.call_args.args[0][-1].endswith("cai_integration/setup_environment.py")


def test_launcher_uses_existing_kernel_supervisor(monkeypatch):
    with patch.object(
        common, "specification", return_value=(["python", "-I"], {"A": "B"}, "/root")
    ), patch("cai_integration.start_application.supervise") as supervise:
        common.launch("hub")
    supervise.assert_called_once_with(["python", "-I"], env={"A": "B"}, cwd="/root")


def test_fresh_import_initializes_only_locked_gitlink(tmp_path):
    (tmp_path / "deployment").mkdir()
    (tmp_path / "deployment/provider-lock.json").write_text(
        json.dumps({"helios": {"path": "external/helios", "commit": "abc123"}})
    )
    with patch.object(
        prepare.subprocess,
        "check_output",
        return_value="160000 commit abc123\texternal/helios",
    ), patch.object(prepare.subprocess, "run") as run, patch(
        "deployment.local.run.validate_lock", return_value=tmp_path / "external/helios"
    ):
        prepare.initialize_checkout(tmp_path)
    run.assert_called_once_with(
        ["git", "submodule", "update", "--init", "--", "external/helios"],
        cwd=tmp_path,
        check=True,
    )


def test_gitlink_mismatch_never_fetches(tmp_path):
    (tmp_path / "deployment").mkdir()
    (tmp_path / "deployment/provider-lock.json").write_text(
        json.dumps({"helios": {"path": "external/helios", "commit": "abc123"}})
    )
    with patch.object(
        prepare.subprocess,
        "check_output",
        return_value="160000 commit wrong\texternal/helios",
    ), patch.object(prepare.subprocess, "run") as run:
        with pytest.raises(RuntimeError, match="does not match"):
            prepare.initialize_checkout(tmp_path)
    run.assert_not_called()


def test_bundled_preflight_fails_before_install(tmp_path, monkeypatch):
    monkeypatch.setenv("SEMANTIC_HUB_PROVIDER_MODE", "bundled")
    with patch.object(prepare.subprocess, "run") as run:
        with pytest.raises(RuntimeError, match="verified ingress"):
            prepare.prepare(tmp_path)
    run.assert_not_called()
