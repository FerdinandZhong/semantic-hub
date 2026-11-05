"""Glossary term authoring: save-time validation and review integration."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.helios.console.demo import configure_demo, demo_router
from apps.helios.tests.test_demo_context import approve_items, binding, definition, pack, review_request
from helios_core.demo.context import ContextDefinition
from helios_core.demo.registry import DemoError
from helios_core.demo.runtime import DemoRuntime


def client_for(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIOS_DEMO_DATASET", "power")
    monkeypatch.setenv("HELIOS_DEMO_STATE", str(tmp_path))
    app = FastAPI()
    app.include_router(demo_router)
    configure_demo(app)
    return app.state.demo_runtime, TestClient(app)


def field(runtime):
    return "source." + next(iter(runtime.workspace._fields))


def post(client, runtime, revision, value):
    return client.post("/demo/api/context/draft", json=binding(runtime) | dict(revision=revision, definition=value))


def test_save_rejects_bad_terms_with_clear_messages(tmp_path, monkeypatch):
    runtime, client = client_for(tmp_path, monkeypatch)
    value, good = definition(runtime.workspace), {"name": "Peak", "definition": "Highest load", "columns": [field(runtime)]}
    cases = [
        ({"name": " ", "definition": "x"}, "needs a name"),
        ({"name": "A", "definition": ""}, "needs a definition"),
        ({"name": "A", "definition": "x", "columns": ["source.nope.nope"]}, "unknown source fields"),
        ({"name": "A", "definition": "x" * 1001}, "too long"),
        ({"name": "peak", "definition": "dup"}, "unique"),
    ]
    with client:
        for bad, message in cases:
            r = post(client, runtime, 0, value | {"glossary_terms": [good, bad]})
            assert r.status_code == 409 and message in r.json()["detail"], (bad, r.text)
        assert post(client, runtime, 0, value | {"glossary_terms": [good]}).status_code == 200
        assert post(client, runtime, 0, value | {"glossary_terms": [good] * 101}).status_code == 422


def test_legacy_proposal_shaped_terms_still_save_unchanged(tmp_path):
    runtime = DemoRuntime(pack(), tmp_path)
    w = runtime.workspace
    legacy = [{"term": "Old", "definition": "", "confidence": 0.7}, {"name": "Prop", "columns": [], "confidence": 0.9}]
    # Legacy terms are accepted when they equal what is already stored.
    w.check_glossary(legacy, stored=legacy)
    with pytest.raises(DemoError, match="needs a definition"):
        w.check_glossary(legacy, stored=[])


def test_term_edit_is_a_per_term_review_item_and_invalidates_validation(tmp_path):
    runtime = DemoRuntime(pack(), tmp_path)
    w = runtime.workspace
    value = definition(w)
    w.save(0, ContextDefinition.model_validate(value))
    w.validate(1)
    term = {"name": "Peak load", "definition": "Highest demand", "columns": [field(runtime)]}
    state = w.save(1, ContextDefinition.model_validate(value | {"glossary_terms": [term]}))
    assert state["draft"]["validation"] is None
    items = {i["id"]: i for i in state["review"]["items"]}
    assert items["term:Peak load"]["kind"] == "glossary" and items["term:Peak load"]["change"] == "added"
    assert "glossary_terms" not in (items["context"]["after"] or {})
    state = w.validate(2)
    approve_items(runtime)
    w.review(review_request(runtime))  # approved term items publish cleanly
    # Editing the term marks only that item modified and clears validation again.
    term2 = term | {"definition": "Highest hourly demand"}
    state = w.save(2, ContextDefinition.model_validate(value | {"glossary_terms": [term2]}), baseline_version="v1")
    assert state["draft"]["validation"] is None
    assert {i["id"]: i["change"] for i in state["review"]["items"]}["term:Peak load"] == "modified"
