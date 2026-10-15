"""Acceptance for typed sample loading, explicit review, and isolated execution."""

import json
import shutil
import subprocess
import sys
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.helios.console.demo import configure_demo, demo_router
from apps.helios.console.demo_hub import DemoHub
from helios_core.demo.local import LocalPackEngine
from helios_core.demo.registry import DemoError, PackRegistry, digest
from helios_core.demo.runtime import DemoRuntime, ExampleRequest, receipt_path, review_pack

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "apps/helios-ds-generation/fixtures/sectors/v1"
REGISTRY = ROOT / "apps/helios/demo-packs.json"


def registry():
    return PackRegistry(REGISTRY, FIXTURES)


def request(runtime, **changes):
    values = dict(
        pack_id=runtime.pack.entry.id,
        snapshot_sha256=runtime.pack.fingerprint,
        session_id=runtime.session_id,
        example_id="aggregate",
    )
    return ExampleRequest(**(values | changes))


@pytest.mark.parametrize("sector", ["finance", "manufacturing", "pharma", "power"])
def test_reviewed_examples_reconcile_to_independent_reference(tmp_path, sector):
    pack = registry().load(sector)
    runtime = DemoRuntime(pack, tmp_path)
    try:
        with pytest.raises(DemoError, match="Review"):
            runtime.execute(request(runtime))
        review_pack(pack, tmp_path, "automated-test-only")
        result = runtime.execute(request(runtime))
        # Only acceptance code opens evaluation truth; runtime never does.
        reference = json.loads((FIXTURES / sector / "evaluation/reference.json").read_text())
        assert abs(Decimal(str(result["rows"][0][0])) - Decimal(reference["expected"])) < Decimal(
            "1e-8"
        )
        direct = runtime._engine.query(reference["reference_sql"], limit=1)
        assert abs(Decimal(str(direct.rows[0][0])) - Decimal(str(result["rows"][0][0]))) < Decimal(
            "1e-8"
        )
        assert result["sql_sha256"] == digest(result["sql"].encode())
        assert runtime.summary()["llm_enabled"] is False
        assert json.loads((FIXTURES / sector / "manifest.json").read_text())["state"] == "IN_REVIEW"
        assert all("evaluation" not in name for name in runtime._engine._tables)
    finally:
        runtime.close()


def test_cross_pack_stale_release_and_old_session_are_rejected(tmp_path):
    pack = registry().load("power")
    runtime = DemoRuntime(pack, tmp_path)
    review_pack(pack, tmp_path, "automated-test-only")
    for changes in [
        {"pack_id": "pharma"},
        {"snapshot_sha256": "0" * 64},
        {"session_id": "previous-process"},
        {"example_id": "freeform"},
    ]:
        with pytest.raises(DemoError):
            runtime.execute(request(runtime, **changes))
    assert runtime._engine is None


def test_review_receipt_cannot_be_reused_for_another_pack(tmp_path):
    power, pharma = registry().load("power"), registry().load("pharma")
    original = review_pack(power, tmp_path, "automated-test-only")
    destination = receipt_path(tmp_path, pharma)
    destination.parent.mkdir(parents=True)
    shutil.copy(original, destination)
    runtime = DemoRuntime(pharma, tmp_path)
    with pytest.raises(DemoError, match="different pack"):
        runtime.execute(request(runtime))


def copied_pack(tmp_path):
    fixtures = tmp_path / "fixtures"
    shutil.copytree(FIXTURES / "power", fixtures / "power")
    reg = tmp_path / "registry.json"
    shutil.copy(REGISTRY, reg)
    return fixtures, reg


def test_evaluation_is_never_read_and_unlisted_files_are_not_discovered(tmp_path):
    fixtures, reg = copied_pack(tmp_path)
    shutil.rmtree(fixtures / "power/evaluation")
    (fixtures / "power/serving/hidden.csv").write_text("secret\nevaluation-answer\n")
    loaded = PackRegistry(reg, fixtures).load("power")
    assert len(loaded.tables) == 4
    assert "evaluation-answer" not in repr(loaded)


@pytest.mark.parametrize("mutation", ["csv", "manifest", "symlink", "model"])
def test_rejects_tampering_and_cross_pack_paths(tmp_path, mutation):
    fixtures, reg = copied_pack(tmp_path)
    power = fixtures / "power"
    if mutation == "csv":
        with (power / "serving/meters.csv").open("a") as output:
            output.write("bad,row\n")
    elif mutation == "manifest":
        (power / "manifest.json").write_text("{}")
    elif mutation == "model":
        (power / "serving/draft.ossie.json").write_text("{}")
    else:
        target = power / "serving/meters.csv"
        target.unlink()
        target.symlink_to(FIXTURES / "power/serving/meters.csv")
    with pytest.raises(DemoError):
        PackRegistry(reg, fixtures).load("power")


def test_declared_schema_mismatch_rejected_even_with_updated_hashes(tmp_path):
    fixtures, reg = copied_pack(tmp_path)
    target = fixtures / "power/serving/meters.csv"
    target.write_text(target.read_text().replace("customer_class", "different_column", 1))
    manifest_path = fixtures / "power/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["checksums"]["serving/meters.csv"] = digest(target.read_bytes())
    manifest_path.write_text(json.dumps(manifest))
    catalog = json.loads(reg.read_text())
    next(e for e in catalog["packs"] if e["id"] == "power")["manifest_sha256"] = digest(
        manifest_path.read_bytes()
    )
    reg.write_text(json.dumps(catalog))
    with pytest.raises(DemoError, match="header"):
        PackRegistry(reg, fixtures).load("power")


def test_local_engine_rejects_writes_external_reads_and_unbounded_queries():
    engine = LocalPackEngine(registry().load("pharma"))
    try:
        for sql in [
            "DELETE FROM batches",
            "SELECT * INTO stolen FROM batches",
            "SELECT * FROM read_csv('/etc/passwd')",
            "SELECT * FROM power.meters",
            "SELECT * FROM batches; SELECT * FROM batches",
            "SELECT * FROM sqlite_master",
            "SELECT * FROM (SELECT * FROM batches)",
            "SELECT random() FROM batches",
        ]:
            with pytest.raises(DemoError):
                engine.query(sql)
        for limit in [None, 0, 1001, True]:
            with pytest.raises(DemoError):
                engine.query("SELECT * FROM batches", limit=limit)
        assert len(engine.query("SELECT * FROM batches", limit=2).rows) == 2
        assert engine.ping()
    finally:
        engine.close()


def test_routes_reject_drafts_and_extra_fields_and_return_real_results(tmp_path):
    runtime = DemoRuntime(registry().load("pharma"), tmp_path)
    app = FastAPI()
    app.state.demo_runtime = runtime
    app.state.demo_hub = DemoHub(registry(), tmp_path, runtime)
    app.include_router(demo_router)
    try:
        with TestClient(app) as client:
            summary = client.get("/demo/api/config").json()
            assert summary["review_state"] == "IN_REVIEW"
            payload = request(runtime).model_dump()
            assert client.post("/demo/api/example", json=payload).status_code == 409
            assert (
                client.post("/demo/api/example", json=payload | {"sql": "SELECT 1"}).status_code
                == 422
            )
            review_pack(runtime.pack, tmp_path, "automated-test-only")
            result = client.post("/demo/api/example", json=payload)
            assert result.status_code == 200
            assert result.json()["rows"]
            assert client.get("/demo").status_code == 200
            assert "<script" in client.get("/demo").text
            assert (
                client.post("/demo/api/example", json=payload | {"pack_id": "power"}).status_code
                == 409
            )
    finally:
        runtime.close()


def test_unselected_console_does_not_expose_demo():
    app = FastAPI()
    app.include_router(demo_router)
    with TestClient(app) as client:
        assert client.get("/demo").status_code == 404
        assert client.get("/demo/api/config").status_code == 404


def test_demo_gate_blocks_legacy_tools_and_disables_response_caching(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIOS_DEMO_DATASET", "power")
    monkeypatch.setenv("HELIOS_DEMO_STATE", str(tmp_path))
    app = FastAPI()
    app.include_router(demo_router)
    configure_demo(app)
    with TestClient(app) as client:
        response = client.get("/demo/api/config")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert client.post("/api/v1/assistant", json={}).status_code == 404
        assert client.get("/docs").status_code == 404


def test_timeout_interrupts_query_and_connection_remains_usable():
    import duckdb

    engine = LocalPackEngine(registry().load("pharma"))
    try:
        sql = (
            "SELECT SUM(a.assay_percent * b.assay_percent * c.assay_percent) "
            "FROM lab_results a CROSS JOIN lab_results b CROSS JOIN lab_results c "
            "CROSS JOIN lab_results d CROSS JOIN lab_results e CROSS JOIN lab_results f"
        )
        with pytest.raises(duckdb.InterruptException):
            engine.query(sql, timeout=0.01)
        assert len(engine.query("SELECT * FROM batches", limit=1).rows) == 1
    finally:
        engine.close()


def test_demo_lifespan_preserves_existing_lifecycle_and_closes_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIOS_DEMO_DATASET", "power")
    monkeypatch.setenv("HELIOS_DEMO_STATE", str(tmp_path))
    events = []

    @asynccontextmanager
    async def existing_lifespan(app):
        events.append("startup")
        yield {"existing_state": True}
        events.append("shutdown")

    app = FastAPI(lifespan=existing_lifespan)
    app.include_router(demo_router)
    configure_demo(app)
    monkeypatch.setattr(app.state.demo_runtime, "close", lambda: events.append("demo_closed"))
    with TestClient(app) as client:
        assert client.get("/demo/api/config").status_code == 200
        assert client.app_state["existing_state"] is True
    assert events == ["startup", "shutdown", "demo_closed"]


def test_launcher_checks_explicit_selection_and_review(tmp_path):
    command = [
        sys.executable,
        str(ROOT / "start_demo.py"),
        "--dataset",
        "pharma",
        "--state-dir",
        str(tmp_path),
    ]
    inspected = subprocess.run(command + ["--inspect"], capture_output=True, text=True, check=True)
    pack = json.loads(inspected.stdout)
    assert pack["pack_id"] == "pharma"
    denied = subprocess.run(command + ["--check"], capture_output=True, text=True)
    assert denied.returncode == 2 and "Review" in denied.stderr
    subprocess.run(
        command
        + ["--review", "--reviewer", "automated-test-only", "--release", pack["snapshot_sha256"]],
        check=True,
        capture_output=True,
    )
    checked = subprocess.run(command + ["--check"], capture_output=True, text=True, check=True)
    assert json.loads(checked.stdout)["pack_id"] == "pharma"
    saved = tmp_path / "settings.json"
    saved.write_text(json.dumps({"pack_id": "power", "snapshot_sha256": pack["snapshot_sha256"]}))
    denied = subprocess.run(
        command + ["--inspect", "--settings", str(saved)], capture_output=True, text=True
    )
    assert denied.returncode == 2 and "Saved settings" in denied.stderr
