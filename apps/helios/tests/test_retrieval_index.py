import copy

import pytest

from helios_core.retrieval.index import Clarification, SemanticIndex


def document():
    return {"name": "test", "datasets": [{"name": "sales", "source": "db.sales", "primary_key": ["id"], "fields": [
        {"name": "id", "expression": {"dialects": [{"expression": "id"}]}},
        {"name": "amount", "ai_context": {"synonyms": ["turnover"]}, "expression": {"dialects": [{"expression": "amount"}]}},
        {"name": "double", "expression": {"dialects": [{"expression": "amount * 2"}]}}
    ]}], "metrics": [{"name": "revenue", "expression": {"dialects": [{"expression": "SUM(sales.double)"}]}}]}


def test_permissions_filter_dependencies_before_limit():
    index = SemanticIndex(document())
    assert index.search("turnover", frozenset({"sales.amount"})) == []
    assert index.search("turnover", frozenset({"sales.amount", "sales.id"}))[0]["name"] == "sales.amount"
    assert index.search("revenue", frozenset({"sales.double", "sales.id"})) == []


def test_bundle_keeps_transitive_dependencies_and_executable_attributes():
    original = document()
    original["metrics"][0]["custom_extensions"] = [{"vendor_name": "HELIOS", "data": '{"dataset":"sales"}'}]
    index = SemanticIndex(original)
    result = index.bundle("revenue")
    assert {f["name"] for f in result["document"]["datasets"][0]["fields"]} == {"id", "amount", "double"}
    assert result["document"]["metrics"] == original["metrics"]
    assert result["evidence"]["token_count_method"] == "conservative UTF-8 byte upper bound"


def test_document_is_an_immutable_snapshot():
    original = document()
    index = SemanticIndex(original)
    digest = index.document_sha256
    original["datasets"][0]["fields"].clear()
    retrieved = index.document
    retrieved["datasets"].clear()
    assert index.document_sha256 == digest
    assert index.search("turnover")


def test_budgets_fail_without_truncating_closure():
    index = SemanticIndex(document())
    with pytest.raises(Clarification, match="budget"):
        index.bundle("revenue", max_fields=2)
    with pytest.raises(Clarification, match="budget"):
        index.bundle("revenue", max_tokens=1)
    result = index.bundle("revenue", token_counter=lambda text: 7, max_tokens=7)
    assert result["evidence"]["context_tokens"] == 7


def test_ambiguous_dependency_rejected_at_build():
    doc = document()
    second = copy.deepcopy(doc["datasets"][0])
    second.update(name="other", source="db.other")
    doc["datasets"].append(second)
    doc["metrics"][0]["expression"]["dialects"][0]["expression"] = "SUM(amount)"
    with pytest.raises(Clarification, match="ambiguous"):
        SemanticIndex(doc)


def test_unknown_mandatory_rule_fails_closed():
    doc = document()
    doc["datasets"][0]["custom_extensions"] = [{"vendor_name": "HELIOS", "data": '{"mandatory_filter":"amount > 0"}'}]
    with pytest.raises(Clarification, match="mandatory"):
        SemanticIndex(doc)


def test_metric_anchor_ignores_disconnected_description_distractors():
    doc = document()
    doc["datasets"].append({"name": "customers", "source": "db.customers", "primary_key": ["id"], "fields": [{"name": "id"}, {"name": "region", "dimension": {}}]})
    doc["relationships"] = [{"name": "customer_join", "from": "sales", "to": "customers", "from_columns": ["id"], "to_columns": ["id"]}]
    for n in range(30):
        doc["datasets"].append({"name": f"archive{n}", "source": f"db.archive{n}", "fields": [{"name": "region", "description": "historical revenue region"}]})
    result = SemanticIndex(doc).bundle("revenue by region")
    assert {d["name"] for d in result["document"]["datasets"]} == {"sales", "customers"}
    assert result["document"]["relationships"][0]["name"] == "customer_join"
    assert "region" in {f["name"] for d in result["document"]["datasets"] for f in d["fields"]}


def test_join_keys_cannot_be_silently_omitted():
    doc = document()
    doc["datasets"].append({"name": "customers", "source": "db.customers", "fields": [{"name": "id"}, {"name": "region"}]})
    doc["relationships"] = [{"name": "customer_join", "from": "sales", "to": "customers", "from_columns": ["id"], "to_columns": ["id"]}]
    allowed = frozenset({"sales.id", "sales.amount", "sales.double", "customers.region"})
    with pytest.raises(Clarification, match="join path"):
        SemanticIndex(doc).bundle("revenue by region", allowed)


def test_diamond_join_paths_require_clarification():
    doc = document()
    for name in ["left", "right", "customers"]:
        doc["datasets"].append({"name": name, "source": f"db.{name}", "fields": [{"name": "id"}, {"name": "region"}]})
    doc["relationships"] = [{"name": f"{a}_{b}", "from": a, "to": b, "from_columns": ["id"], "to_columns": ["id"]} for a, b in [("sales", "left"), ("sales", "right"), ("left", "customers"), ("right", "customers")]]
    with pytest.raises(Clarification, match="join paths"):
        SemanticIndex(doc).bundle("revenue by region")


def test_computed_field_cycle_is_rejected():
    doc = document()
    doc["datasets"][0]["fields"][1]["expression"]["dialects"][0]["expression"] = "double / 2"
    with pytest.raises(Clarification, match="cycle"):
        SemanticIndex(doc)


def test_opaque_annotations_cannot_leak_forbidden_catalog_metadata():
    import json
    doc = document()
    secret = "forbidden_payroll_tax_identifier"
    payload = json.dumps({"full_catalog": {"fields": [{"name": secret}]}})
    doc["custom_extensions"] = [{"vendor_name": "HELIOS", "data": payload}]
    doc["catalog_annotation"] = {"field_name": secret}
    doc["datasets"][0]["custom_extensions"] = [{"vendor_name": "OTHER", "data": payload}]
    doc["datasets"][0]["fields"][1]["ai_context"]["catalog"] = {"name": secret}
    doc["datasets"][0]["fields"][1]["expression"]["catalog"] = {"name": secret}
    doc["metrics"][0]["custom_extensions"] = [{"vendor_name": "HELIOS", "data": json.dumps({"dataset": "sales", "catalog": {"name": secret}})}]
    allowed = frozenset({"sales.id", "sales.amount", "sales.double"})
    result = SemanticIndex(doc).bundle("revenue", allowed)
    assert secret not in json.dumps(result)
    assert json.loads(result["document"]["metrics"][0]["custom_extensions"][0]["data"]) == {"dataset": "sales"}


@pytest.mark.parametrize("value", [0, -1, True, "100", None])
def test_invalid_context_limits_require_clarification(value):
    with pytest.raises(Clarification, match="positive integers"):
        SemanticIndex(document()).bundle("revenue", max_tokens=value)


def test_unknown_executable_extension_fails_closed():
    doc = document()
    doc["custom_extensions"] = [{"vendor_name": "OTHER", "data": '{"runtime":{"filters":["amount > 0"]}}'}]
    with pytest.raises(Clarification, match="mandatory"):
        SemanticIndex(doc)
