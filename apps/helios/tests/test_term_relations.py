"""Typed glossary term relations live in the definition only."""
import json

import pytest
from fastapi.testclient import TestClient

from apps.helios.console.demo_hub import DemoHub
from apps.helios.console.semantic_hub_api import PREFIX, create_application
from apps.helios.tests.test_demo_context import approve_items, binding, definition, pack, publish, review_request, validated
from apps.helios.tests.test_glossary_authoring import client_for, post
from apps.helios.tests.test_pharma_intelligence import FIXTURES, registry
from helios_core.demo.builder_artifacts import BuilderArtifacts
from helios_core.demo.context import BatchReview, ContextDefinition
from helios_core.demo.registry import DemoError, canonical, digest
from helios_core.demo.runtime import DemoRuntime

TERMS = [{"name": n, "definition": "d"} for n in ("Alpha", "Beta", "Gamma")]


def rel(a, r, b, **extra):
    return {"from": a, "relation": r, "to": b} | extra


def test_absent_relations_leave_hashes_unchanged(tmp_path):
    # Hashes captured at the commit before term_relations existed (manufacturing seed).
    w = DemoRuntime(pack("manufacturing"), tmp_path).workspace
    dumped = ContextDefinition.model_validate(w.seed()).model_dump()
    assert "term_relations" not in dumped
    assert digest(canonical(dumped)) == "a600c9fc6f3edf2977e144ab153345267e2630f829ed79e8c4d96bac0ecb56ad"
    builder = BuilderArtifacts(w)
    assert builder.bundle(dumped)["artifact_sha256"] == "40707d3ef71a90cc385cad511376368404ed5004f269338707cc21e4919b9dcd"
    assert digest(canonical(w.compare(definition=dumped)["items"])) == "bc8c7e0bc85cac795e5dea8f1d7a8c54b02c6535bbbed0f805d3cf8370b90f85"
    with_terms = dict(dumped, glossary_terms=[{"name": "T", "definition": "d", "columns": []}])
    assert builder.bundle(with_terms)["artifact_sha256"] == "8c43ba00a541ab23f88b35eeb8a045c046680eebc346f0a5357db5009f411b17"


@pytest.mark.parametrize("relations,message", [
    ([rel("Alpha", "broader", "Nope")], "not in this draft"),
    ([rel("Alpha", "likes", "Beta")], "unknown type"),
    ([rel("Alpha", "related", "alpha")], "itself"),
    ([rel("Alpha", "related", "Beta"), rel("alpha", "related", "BETA")], "twice"),
    ([rel("Alpha", "broader", "Beta"), rel("Beta", "broader", "Gamma"), rel("Alpha", "narrower", "Gamma")], "cycle"),
    ([rel("Alpha", "broader", "Beta"), rel("Alpha", "narrower", "Beta")], "cycle"),
])
def test_save_rejects_bad_relations(tmp_path, monkeypatch, relations, message):
    runtime, client = client_for(tmp_path, monkeypatch)
    value = definition(runtime.workspace) | {"glossary_terms": TERMS}
    with client:
        r = post(client, runtime, 0, value | {"term_relations": relations})
        assert r.status_code == 409 and message in r.json()["detail"], r.text


def test_deleting_or_renaming_a_referenced_term_names_the_relation(tmp_path, monkeypatch):
    runtime, client = client_for(tmp_path, monkeypatch)
    value = definition(runtime.workspace) | {"glossary_terms": TERMS, "term_relations": [rel("Alpha", "related", "Beta", note="x")]}
    with client:
        assert post(client, runtime, 0, value).status_code == 200
        r = post(client, runtime, 1, value | {"glossary_terms": TERMS[:1] + TERMS[2:]})
        assert r.status_code == 409 and "Alpha related Beta" in r.json()["detail"] and "remove the relation" in r.json()["detail"]
        renamed = [TERMS[0], {"name": "Beta2", "definition": "d"}]
        assert post(client, runtime, 1, value | {"glossary_terms": renamed}).status_code == 409
        # Removing the relation first allows the deletion.
        assert post(client, runtime, 1, value | {"glossary_terms": TERMS[:1], "term_relations": []}).status_code == 200


def test_relation_is_its_own_review_item_and_needs_approval(tmp_path):
    runtime = DemoRuntime(pack(), tmp_path)
    w = runtime.workspace
    value = definition(w) | {"glossary_terms": TERMS}
    w.save(0, ContextDefinition.model_validate(value))
    w.validate(1)
    approve_items(runtime)
    assert not [i for i in w.view()["review"]["items"] if i["kind"] == "term_relation"]
    state = w.save(1, ContextDefinition.model_validate(value | {"term_relations": [rel("Alpha", "part_of", "Beta")]}), baseline_version=None)
    assert state["draft"]["validation"] is None
    items = {i["id"]: i for i in state["review"]["items"]}
    item = items["relation:Alpha|part_of|Beta"]
    assert item["kind"] == "term_relation" and item["change"] == "added" and item["status"] == "pending"
    assert "term_relations" not in (items["context"]["after"] or {})
    w.validate(2)
    assert {i["id"]: i["status"] for i in w.view()["review"]["items"]}["relation:Alpha|part_of|Beta"] == "pending"


def test_relation_review_ids_do_not_collide_for_term_name_delimiters(tmp_path):
    runtime = DemoRuntime(pack(), tmp_path)
    try:
        w = runtime.workspace
        terms = [{"name": name, "definition": "d"} for name in
                 ("Alpha", "Alpha|related", "Beta", "related|Beta", "Alpha%7Crelated")]
        relations = [rel("Alpha|related", "related", "Beta"),
                     rel("Alpha", "related", "related|Beta"),
                     rel("Alpha%7Crelated", "related", "Beta")]
        w.check_relations(relations, terms)
        state = w.save(0, ContextDefinition.model_validate(
            definition(w) | {"glossary_terms": terms, "term_relations": relations}))
        items = [item for item in state["review"]["items"] if item["kind"] == "term_relation"]
        assert len(items) == len(relations)
        assert len({item["id"] for item in items}) == len(relations)
        assert {json.dumps(item["after"], sort_keys=True) for item in items} == {
            json.dumps(relation, sort_keys=True) for relation in relations}
        state = w.validate(1)
        unapproved = items[0]["id"]
        w.batch_review(BatchReview(
            **binding(runtime), revision=1,
            validation_sha256=state["draft"]["validation"]["validation_sha256"],
            item_ids=[item["id"] for item in state["review"]["items"] if item["id"] != unapproved],
            decision="approve", reviewer="test reviewer", note="Approve all except one relation", confirmed=True))
        with pytest.raises(DemoError, match="Approve every required item"):
            w.review(review_request(runtime))
        approve_items(runtime)
        w.review(review_request(runtime))
    finally:
        runtime.close()


@pytest.fixture(scope="module")
def published(tmp_path_factory):
    root = tmp_path_factory.mktemp("relations-api")
    reg = registry()
    runtime = DemoRuntime(reg.load("pharma_intelligence"), root)
    hub = DemoHub(reg, root, runtime)
    value = runtime.workspace.seed()
    refs = {i["metric"]: i["reference_sql"] for i in json.loads((FIXTURES / "pharma_intelligence/evaluation/references.json").read_text())}
    for metric in value["metrics"]:
        metric["reference_sql"] = refs[metric["name"]]
    value |= {"glossary_terms": TERMS, "term_relations": [rel("Alpha", "narrower", "Beta")]}
    validated(runtime, value)
    runtime.workspace.review(review_request(runtime))
    publish(runtime)
    yield hub, runtime, value
    hub.close()


def test_consumer_sees_relations_only_in_definition(published, monkeypatch):
    hub, runtime, value = published
    monkeypatch.setenv("SEMANTIC_HUB_API_TOKEN", "t")
    with TestClient(create_application(hub, type("S", (), {"client": lambda self, role: None})()), headers={"Authorization": "Bearer t"}) as client:
        details = client.get(PREFIX + "/models/pharma_intelligence/versions/v1").json()
    assert details["definition"]["term_relations"] == [rel("Alpha", "narrower", "Beta")]
    plain = {k: v for k, v in value.items() if k != "term_relations"}
    bundle = BuilderArtifacts(runtime.workspace).bundle(ContextDefinition.model_validate(plain).model_dump(), version="v1")
    assert details["ontology"]["graph"] == bundle["ontology"]["graph"]
    assert details["ontology"]["graph_sha256"] == bundle["ontology"]["graph_sha256"]
