"""Acceptance for local draft, SQL evidence, immutable reviews and query binding."""

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.helios.console.demo import configure_demo, demo_router
from helios_core.demo.context import (
    ContextDefinition,
    ContextWorkspace,
    ReviewContext,
    BatchReview,
    PublishContext,
)
from helios_core.demo.registry import DemoError, PackRegistry
from helios_core.demo.runtime import DemoRuntime, ExampleRequest

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "apps/helios-ds-generation/fixtures/sectors/v1"


def pack(sector="power"):
    return PackRegistry(ROOT / "apps/helios/demo-packs.json", FIXTURES).load(sector)


def binding(runtime):
    return dict(
        pack_id=runtime.pack.entry.id,
        snapshot_sha256=runtime.pack.fingerprint,
        session_id=runtime.session_id,
    )


def definition(workspace):
    value = workspace.seed()
    # Independent evaluation truth is used only by tests, never by the builder.
    ref = json.loads(
        (FIXTURES / workspace.pack.entry.id / "evaluation/reference.json").read_text()
    )
    value["metrics"][0]["reference_sql"] = ref["reference_sql"].replace(
        "AS value", "AS " + value["metrics"][0]["name"]
    )
    return value


def review_request(runtime, version="v1", **changes):
    draft = runtime.workspace.view()["draft"]
    return ReviewContext(
        **(
            binding(runtime)
            | dict(
                revision=draft["revision"],
                version=version,
                validation_sha256=(
                    draft["validation"]["validation_sha256"]
                    if draft["validation"]
                    else "0" * 64
                ),
                reviewer="test reviewer",
                note="Checked independent reference and source key evidence",
                confirmed=True,
            )
            | changes
        )
    )


def approve_items(runtime):
    state = runtime.workspace.view()
    request = BatchReview(
        **binding(runtime),
        revision=state["draft"]["revision"],
        validation_sha256=state["draft"]["validation"]["validation_sha256"],
        item_ids=[i["id"] for i in state["review"]["items"]],
        decision="approve",
        reviewer="test reviewer",
        note="Checked each item and dependency",
        confirmed=True,
    )
    return runtime.workspace.batch_review(request)


def publish(runtime, version="v1"):
    release = runtime.workspace.release(version)
    runtime.workspace.publish(
        PublishContext(
            **binding(runtime),
            version=version,
            context_sha256=release["context_sha256"],
            confirmed=True,
        )
    )


def validated(runtime, value=None):
    w = runtime.workspace
    w.save(
        w.view()["draft"]["revision"],
        ContextDefinition.model_validate(value or definition(w)),
    )
    result = w.validate(w.view()["draft"]["revision"])
    assert result["draft"]["validation"]["passed"], result
    approve_items(runtime)
    return result


@pytest.mark.parametrize("sector", ["finance", "manufacturing", "pharma", "power"])
def test_full_version_lifecycle_persists_and_queries_exact_context(tmp_path, sector):
    runtime = DemoRuntime(pack(sector), tmp_path)
    w = runtime.workspace
    original = runtime.pack.model_bytes
    try:
        assert w.active() is None
        assert w.view()["draft"]["revision"] == 0
        validated(runtime)
        assert runtime.summary()["review_state"] == "IN_REVIEW"
        with pytest.raises(DemoError, match="Confirm"):
            w.review(review_request(runtime, confirmed=False))
        w.review(review_request(runtime))
        assert w.active() is None  # Review and activation are distinct decisions.
        release = w.release("v1")
        publish(runtime)
        w.activate("v1", release["context_sha256"])
        summary = runtime.summary()
        assert summary["context_version"] == "v1"
        request = ExampleRequest(
            **binding(runtime),
            example_id=summary["examples"][0]["id"],
            context_sha256=release["context_sha256"],
        )
        assert (
            runtime.execute(request)["rows"]
            == release["validation"]["metrics"][0]["result"]["rows"]
        )
        assert runtime.execute(request)["context_sha256"] == release["context_sha256"]
        assert ContextWorkspace(runtime.pack, tmp_path).active() == release
        assert runtime.pack.model_bytes == original
        with pytest.raises(DemoError, match="already exists"):
            w.review(review_request(runtime))
        with pytest.raises(DemoError, match="Active context changed"):
            runtime.execute(request.model_copy(update={"context_sha256": ""}))
    finally:
        runtime.close()


def test_draft_revision_conflict_and_edit_invalidate_evidence(tmp_path):
    runtime = DemoRuntime(pack(), tmp_path)
    w = runtime.workspace
    validated(runtime)
    old_review = review_request(runtime)
    value = definition(w)
    value["metrics"][0]["description"] = "Changed business definition"
    w.save(1, ContextDefinition.model_validate(value))
    assert w.view()["draft"]["validation"] is None
    with pytest.raises(DemoError, match="another tab"):
        w.save(1, ContextDefinition.model_validate(value))
    with pytest.raises(DemoError, match="another tab"):
        w.review(old_review)
    with pytest.raises(DemoError, match="Validate this exact"):
        w.review(old_review.model_copy(update={"revision": 2}))
    w.validate(2)
    with pytest.raises(DemoError, match="Validate this exact"):
        w.review(old_review.model_copy(update={"revision": 2}))


@pytest.mark.parametrize(
    "reference",
    [
        "",
        "DELETE FROM meter_readings",
        "SELECT * FROM read_csv('/etc/passwd')",
        "SELECT SUM(import_kwh) AS measured_import_kwh FROM meter_readings",
    ],
)
def test_missing_unsafe_or_wrong_reference_cannot_pass(tmp_path, reference):
    runtime = DemoRuntime(pack(), tmp_path)
    value = definition(runtime.workspace)
    value["metrics"][0]["reference_sql"] = reference
    runtime.workspace.save(0, ContextDefinition.model_validate(value))
    report = runtime.workspace.validate(1)["draft"]["validation"]
    assert not report["passed"]
    assert report["metrics"][0]["error"]
    with pytest.raises(DemoError):
        runtime.workspace.review(review_request(runtime))


def test_grouped_metric_and_multiple_metrics_execute_reviewed_joins(tmp_path):
    runtime = DemoRuntime(pack(), tmp_path)
    value = definition(runtime.workspace)
    value["field_meanings"] = {
        "meters.customer_class": "Customer segment for each meter"
    }
    value["metrics"].append(
        dict(
            name="readings_by_class",
            description="How many readings are in each customer class?",
            unit="readings",
            grain="Customer class",
            time_rule="All available readings",
            expression="COUNT(meter_readings.meter_id)",
            dimensions=["meters.customer_class"],
            reference_sql="SELECT m.customer_class AS customer_class, COUNT(r.meter_id) AS readings_by_class FROM meter_readings r JOIN meters m ON r.meter_id=m.meter_id GROUP BY m.customer_class",
        )
    )
    validated(runtime, value)
    runtime.workspace.review(review_request(runtime))
    release = runtime.workspace.release("v1")
    publish(runtime)
    runtime.workspace.activate("v1", release["context_sha256"])
    try:
        result = runtime.execute(
            ExampleRequest(
                **binding(runtime),
                example_id="readings_by_class",
                context_sha256=release["context_sha256"],
            )
        )
        assert result["columns"] == ["customer_class", "readings_by_class"]
        assert len(result["rows"]) > 1
        assert sum(row[1] for row in result["rows"]) == next(
            t.row_count for t in runtime.pack.tables if t.name == "meter_readings"
        )
        assert "JOIN" in result["sql"]
    finally:
        runtime.close()


@pytest.mark.parametrize("bad_join", ["duplicate", "unmatched", "reverse", "ambiguous"])
def test_join_failures_block_review(tmp_path, bad_join):
    source = pack()
    if bad_join in ["duplicate", "unmatched"]:
        tables = []
        for table in source.tables:
            if table.name == "meters":
                lines = table.csv_bytes.decode().splitlines()
                lines = (
                    lines + [lines[1]]
                    if bad_join == "duplicate"
                    else [lines[0]] + lines[2:]
                )
                table = replace(
                    table,
                    csv_bytes=("\n".join(lines) + "\n").encode(),
                    row_count=len(lines) - 1,
                )
            tables.append(table)
        source = replace(source, tables=tuple(tables))
    runtime = DemoRuntime(source, tmp_path)
    value = definition(runtime.workspace)
    if bad_join == "reverse":
        value["metrics"][0]["expression"] = "COUNT(meters.meter_id)"
        value["metrics"][0]["dimensions"] = ["meter_readings.quality_status"]
    if bad_join == "ambiguous":
        value["metrics"][0]["dimensions"] = ["meters.customer_class"]
        duplicate = copy.deepcopy(value["joins"][-1])
        duplicate["name"] = "alternate_path"
        duplicate["id"] = ""
        value["joins"].append(duplicate)
    runtime.workspace.save(0, ContextDefinition.model_validate(value))
    report = runtime.workspace.validate(1)["draft"]["validation"]
    assert not report["passed"]
    if bad_join in ["reverse", "ambiguous"]:
        assert "unambiguous" in report["errors"][0]
    else:
        assert any(not join["passed"] for join in report["joins"])


def test_released_version_does_not_follow_draft_and_rejects_tampering(tmp_path):
    runtime = DemoRuntime(pack(), tmp_path)
    validated(runtime)
    runtime.workspace.review(review_request(runtime))
    release = runtime.workspace.release("v1")
    publish(runtime)
    runtime.workspace.activate("v1", release["context_sha256"])
    value = definition(runtime.workspace)
    value["metrics"][0]["expression"] = "SUM(meter_readings.import_kwh)"
    runtime.workspace.save(1, ContextDefinition.model_validate(value))
    assert runtime.workspace.active() == release
    assert ContextWorkspace(pack("pharma"), tmp_path).active() is None
    with runtime.workspace.connection(write=True) as connection:
        release["reviewer"] = "edited on disk"
        connection.execute("UPDATE releases SET content=?", (json.dumps(release),))
    with pytest.raises(DemoError, match="checksum"):
        runtime.workspace.active()


def test_demo_routes_bind_all_writes_and_bound_table_access(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIOS_DEMO_DATASET", "power")
    monkeypatch.setenv("HELIOS_DEMO_STATE", str(tmp_path))
    app = FastAPI()
    app.include_router(demo_router)
    configure_demo(app)
    runtime = app.state.demo_runtime
    with TestClient(app) as client:
        assert client.get("/demo/context").status_code == 200
        assert client.get("/demo/api/context/tables?limit=2").json()["total"] == 4
        assert len(client.get("/demo/api/context/tables?limit=2").json()["items"]) == 2
        assert client.get("/demo/api/context/tables?limit=1000").status_code == 409
        table = client.get("/demo/api/context/table?name=meter_readings").json()
        assert len(table["rows"]) == 10
        assert "DECIMAL" in next(
            c["type"] for c in table["columns"] if c["name"] == "import_kwh"
        )
        assert client.get("/demo/api/context/table?name=evaluation").status_code == 409
        payload = binding(runtime) | dict(
            revision=0, definition=definition(runtime.workspace)
        )
        assert (
            client.post(
                "/demo/api/context/draft", json=payload | {"session_id": "old"}
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/demo/api/context/draft", json=payload | {"pack_id": "pharma"}
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/demo/api/context/draft", json=payload | {"extra": True}
            ).status_code
            == 422
        )
        assert client.post("/demo/api/context/draft", json=payload).status_code == 200
        assert client.post(
            "/demo/api/context/validate", json=binding(runtime) | {"revision": 1}
        ).json()["draft"]["validation"]["passed"]
        approve_items(runtime)
        assert (
            client.post(
                "/demo/api/context/review", json=review_request(runtime).model_dump()
            ).status_code
            == 200
        )
        release = client.get("/demo/api/context/version?version=v1").json()
        publish(runtime)
        activation = binding(runtime) | {
            "version": "v1",
            "context_sha256": release["context_sha256"],
        }
        assert (
            client.post(
                "/demo/api/context/activate", json=activation | {"session_id": "old"}
            ).status_code
            == 409
        )
        assert (
            client.post("/demo/api/context/activate", json=activation).json()[
                "active_version"
            ]
            == "v1"
        )
        assert client.get("/api/v1/assistant").status_code == 404


def test_oversized_grouping_cannot_validate_truncated_results(tmp_path):
    runtime = DemoRuntime(pack("finance"), tmp_path)
    value = definition(runtime.workspace)
    value["metrics"][0].update(
        expression="COUNT(transactions.transaction_id)",
        dimensions=["transactions.transaction_id"],
        reference_sql="SELECT 1 FROM transactions",
    )
    runtime.workspace.save(0, ContextDefinition.model_validate(value))
    report = runtime.workspace.validate(1)["draft"]["validation"]
    assert not report["passed"]
    assert "exceeds 200" in report["metrics"][0]["error"]


def test_reconciliation_preserves_nulls_and_numeric_types_when_reordering():
    from decimal import Decimal
    from helios_core.demo.context import equivalent
    from helios_core.engines.base import QueryResult

    left = QueryResult(
        ["group", "value"],
        [(None, Decimal("1.0")), ("", Decimal("2.0")), ("A", Decimal("10.00"))],
    )
    right = QueryResult(["group", "value"], [("A", 10), ("", 2.0), (None, 1)])
    assert equivalent(left, right)
    assert not equivalent(
        left, QueryResult(right.columns, [("A", 10), ("", 2), ("", 1)])
    )
    assert not equivalent(
        QueryResult(["value"], [(float("nan"),)]),
        QueryResult(["value"], [(float("nan"),)]),
    )
    assert equivalent(
        QueryResult(["flag"], [(False,), (True,)]),
        QueryResult(["flag"], [(True,), (False,)]),
    )
    assert not equivalent(
        QueryResult(["flag"], [(True,)]), QueryResult(["flag"], [(1,)])
    )


def test_item_review_mixed_batch_stale_and_publish_gate(tmp_path):
    runtime = DemoRuntime(pack(), tmp_path)
    w = runtime.workspace
    value = definition(w)
    bad = copy.deepcopy(value["metrics"][0])
    bad.update(
        id="metric-bad", name="bad_metric", reference_sql="SELECT 0 AS bad_metric"
    )
    value["metrics"].append(bad)
    w.save(0, ContextDefinition.model_validate(value))
    state = w.validate(1)
    request = BatchReview(
        **binding(runtime),
        revision=1,
        validation_sha256=state["draft"]["validation"]["validation_sha256"],
        item_ids=[i["id"] for i in state["review"]["items"]],
        decision="approve",
        reviewer="reviewer",
        note="Checked validation evidence",
        confirmed=True,
    )
    result = w.batch_review(request)
    assert any(o["accepted"] for o in result["outcomes"])
    assert any(not o["accepted"] for o in result["outcomes"])
    w.save(1, ContextDefinition.model_validate(definition(w)))
    with pytest.raises(DemoError, match="another tab"):
        w.batch_review(request)
    w.validate(2)
    with pytest.raises(DemoError, match="every required"):
        w.review(review_request(runtime))
    approve_items(runtime)
    w.review(review_request(runtime))
    release = w.release("v1")
    with pytest.raises(DemoError, match="Publish"):
        w.activate("v1", release["context_sha256"])
    publish(runtime)
    assert w.view()["versions"][0]["published"]


def test_stable_rename_compare_and_restore(tmp_path):
    runtime = DemoRuntime(pack(), tmp_path)
    w = runtime.workspace
    validated(runtime)
    w.review(review_request(runtime))
    original = w.release("v1")["definition"]
    changed = copy.deepcopy(original)
    changed["metrics"][0]["name"] = "renamed_metric"
    w.save(1, ContextDefinition.model_validate(changed))
    diff = w.compare("draft", "v1")
    item = next(i for i in diff["items"] if i["id"] == original["metrics"][0]["id"])
    assert item["change"] == "modified"
    assert item["before"]["name"] != item["after"]["name"]
    assert w.compare("v1", "v1")["items"]
    restored = w.restore(2, "v1")
    assert restored["draft"]["revision"] == 3
    assert restored["draft"]["definition"] == original
    assert restored["draft"]["validation"] is None
    with pytest.raises(DemoError, match="another tab"):
        w.restore(2, "v1")


def test_structural_metric_failure_preserves_valid_item_eligibility(tmp_path):
    runtime = DemoRuntime(pack(), tmp_path)
    w = runtime.workspace
    value = definition(w)
    invalid = copy.deepcopy(value["metrics"][0])
    invalid.update(
        id="metric-invalid-expression",
        name="invalid_expression",
        expression="SUM(unknown.field)",
    )
    value["metrics"].append(invalid)
    w.save(0, ContextDefinition.model_validate(value))
    state = w.validate(1)
    assert not state["draft"]["validation"]["passed"]
    metrics = [i for i in state["review"]["items"] if i["kind"] == "metric"]
    assert next(i for i in metrics if i["id"] == value["metrics"][0]["id"])["eligible"]
    assert not next(i for i in metrics if i["id"] == "metric-invalid-expression")[
        "eligible"
    ]


def test_baseline_removals_audit_namespace_and_zero_restore(tmp_path):
    runtime = DemoRuntime(pack(), tmp_path)
    w = runtime.workspace
    value = definition(w)
    added = copy.deepcopy(value["metrics"][0])
    added.update(id="metric-extra", name="extra_metric")
    added["reference_sql"] = added["reference_sql"].replace(
        value["metrics"][0]["name"], "extra_metric"
    )
    value["metrics"].append(added)
    validated(runtime, value)
    w.review(review_request(runtime))
    audit = w.release("v1")["item_review"]
    publish(runtime)
    w.activate("v1", w.release("v1")["context_sha256"])
    w.save(1, ContextDefinition.model_validate(definition(w)))
    state = w.validate(2)
    assert state["review"]["baseline_version"] == "v1"
    assert (
        next(i for i in state["review"]["items"] if i["id"] == "metric-extra")["change"]
        == "removed"
    )
    assert w.release("v1")["item_review"] == audit
    invalid = definition(w)
    invalid["metrics"][0]["id"] = "context"
    with pytest.raises(DemoError, match="namespaces"):
        w.save(2, ContextDefinition.model_validate(invalid))
    with w.connection(write=True) as connection:
        connection.execute("DELETE FROM draft")
    assert w.restore(0, "v1")["draft"]["revision"] == 1


@pytest.mark.parametrize(
    "wrong_binding", [{"session_id": "old"}, {"pack_id": "pharma"}]
)
def test_new_write_routes_reject_wrong_binding(tmp_path, monkeypatch, wrong_binding):
    monkeypatch.setenv("HELIOS_DEMO_DATASET", "power")
    monkeypatch.setenv("HELIOS_DEMO_STATE", str(tmp_path))
    app = FastAPI()
    app.include_router(demo_router)
    configure_demo(app)
    runtime = app.state.demo_runtime
    common = binding(runtime) | wrong_binding
    bodies = {
        "batch-review": common
        | dict(
            revision=1,
            validation_sha256="0" * 64,
            item_ids=["context"],
            decision="approve",
            reviewer="reviewer",
            note="Checked evidence",
            confirmed=True,
        ),
        "publish": common | dict(version="v1", context_sha256="0" * 64, confirmed=True),
        "restore": common | dict(version="v1", revision=0),
    }
    with TestClient(app) as client:
        for endpoint, payload in bodies.items():
            assert (
                client.post("/demo/api/context/" + endpoint, json=payload).status_code
                == 409
            )


def test_legacy_release_publication_compatibility_and_reserved_versions(tmp_path):
    from helios_core.demo.registry import canonical, digest

    runtime = DemoRuntime(pack(), tmp_path)
    w = runtime.workspace
    validated(runtime)
    for version in ("starter", "draft"):
        with pytest.raises(DemoError, match="reserved"):
            w.review(review_request(runtime, version=version))
    w.review(review_request(runtime))
    release = w.release("v1")
    request = PublishContext(
        **binding(runtime),
        version="v1",
        context_sha256=release["context_sha256"],
        confirmed=False,
    )
    with pytest.raises(DemoError, match="Confirm"):
        w.publish(request)
    with pytest.raises(DemoError, match="changed"):
        w.publish(
            request.model_copy(update={"confirmed": True, "context_sha256": "0" * 64})
        )
    release.pop("publication_required")
    release.pop("item_review")
    release.pop("context_sha256")
    release["context_sha256"] = digest(canonical(release))
    with w.connection(write=True) as connection:
        connection.execute(
            "UPDATE releases SET content=? WHERE version='v1'", (json.dumps(release),)
        )
    w.activate("v1", release["context_sha256"])
    assert w.view()["versions"][0]["published"]
    result = runtime.execute(
        ExampleRequest(
            **binding(runtime),
            example_id=release["definition"]["metrics"][0]["name"],
            context_sha256=release["context_sha256"],
        )
    )
    assert result["rows"] == release["validation"]["metrics"][0]["result"]["rows"]


def test_saved_metric_lineage_uses_exact_quoted_columns_and_dimensions(tmp_path):
    runtime = DemoRuntime(pack(), tmp_path)
    w = runtime.workspace
    value = definition(w)
    metric = value["metrics"][0]
    metric.update(
        expression='SUM("meter_readings"."import_kwh")',
        dimensions=["meters.customer_class"],
    )
    w.save(0, ContextDefinition.model_validate(value))
    graph = w.source_graph()
    lineage = graph["metric_dependencies"][metric["id"]]
    assert graph["draft_revision"] == 1
    assert lineage["fields"] == ["meter_readings.import_kwh", "meters.customer_class"]
    assert lineage["field_ids"] == [
        "field:meter_readings.import_kwh",
        "field:meters.customer_class",
    ]
    assert lineage["parsed"] and not lineage["warnings"]
    metric["expression"] = "SUM(meter_readings.import_kwh_extra)"
    w.save(1, ContextDefinition.model_validate(value))
    lineage = w.source_graph()["metric_dependencies"][metric["id"]]
    assert lineage["expression_fields"] == []
    assert lineage["unknown_fields"] == ["meter_readings.import_kwh_extra"]
    assert lineage["warnings"]
    metric["expression"] = "SUM("
    w.save(2, ContextDefinition.model_validate(value))
    lineage = w.source_graph()["metric_dependencies"][metric["id"]]
    assert not lineage["parsed"]
    assert lineage["fields"] == ["meters.customer_class"]
    assert lineage["warnings"]
    metric["expression"] = 'SUM("meter_readings.import_kwh)'
    w.save(3, ContextDefinition.model_validate(value))
    assert not w.source_graph()["metric_dependencies"][metric["id"]]["parsed"]


@pytest.mark.parametrize("sector", ["finance", "manufacturing", "pharma", "power"])
def test_version_graph_uses_release_after_draft_changes(tmp_path, sector):
    runtime = DemoRuntime(pack(sector), tmp_path)
    w = runtime.workspace
    try:
        validated(runtime)
        w.review(review_request(runtime))
        publish(runtime)
        release = w.release("v1")
        graph = w.source_graph("v1")
        assert graph["version"] == "v1"
        assert graph["context_sha256"] == release["context_sha256"]
        assert {n["name"] for n in graph["nodes"]} == {
            d["name"] for d in release["document"]["datasets"]
        }
        metric = release["definition"]["metrics"][0]
        assert graph["metric_dependencies"][metric["id"]]["source"] == "reviewed_version"
        assert graph["metric_dependencies"][metric["id"]]["fields"]
        changed = copy.deepcopy(release["definition"])
        changed["metrics"][0]["expression"] = "COUNT(*)"
        changed["joins"] = []
        w.save(release["revision"], ContextDefinition.model_validate(changed))
        before = w.view()
        # Fail if release graph generation attempts to use current source table metadata.
        w.table = lambda *_: pytest.fail("Release graph read current table metadata")
        assert w.source_graph("v1") == graph
        assert w.view() == before
        assert w.release("v1") == release
        with pytest.raises(DemoError):
            w.source_graph("missing-version")
    finally:
        runtime.close()
