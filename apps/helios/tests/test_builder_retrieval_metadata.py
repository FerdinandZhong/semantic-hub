"""Published authoring metadata flows into bounded semantic retrieval."""
import json

import pytest

from apps.helios.tests.test_demo_context import pack
from helios_core.demo.context import ContextDefinition, ContextWorkspace, MetricFilter
from helios_core.compiler import Compiler, SemanticRequest
from helios_core.demo.local import LocalPackEngine
from helios_core.retrieval.index import SemanticIndex
from helios_core.ossie import SemanticModel


@pytest.mark.parametrize("sector", ["finance", "manufacturing", "pharma", "power", "pharma_intelligence"])
def test_reviewed_business_metadata_is_indexed_and_returned_without_reference_sql(tmp_path, sector):
    workspace = ContextWorkspace(pack(sector), tmp_path)
    value = workspace.seed()
    metric = value["metrics"][0]
    metric.update(synonyms=["approved business indicator"],
                  example_questions=["Explain the calibrated baseline"],
                  ontology_concepts=[workspace.pack.tables[0].name],
                  inclusion_rules=["Use the conditions encoded in the approved expression"],
                  owner="test-reviewer", reference_sql="DO_NOT_SERVE_REFERENCE")
    model = workspace.build_model(ContextDefinition.model_validate(value))
    index = SemanticIndex(model)
    assert index.search("calibrated baseline")[0]["name"] == metric["name"]
    bundle = index.bundle("approved business indicator", metric=metric["name"], required_fields=[])["document"]
    assert "DO_NOT_SERVE_REFERENCE" not in json.dumps(bundle)
    extension = json.loads(bundle["metrics"][0]["custom_extensions"][0]["data"])
    assert extension["business_context"]["unit"] == metric["unit"]
    assert extension["business_context"]["owner"] == "test-reviewer"
    assert extension["business_context"]["inclusion_rules"] == metric["inclusion_rules"]


def test_authoring_seed_is_removed_without_dropping_other_extension_rules(tmp_path):
    from helios_core.retrieval.index import Clarification

    workspace = ContextWorkspace(pack("pharma_intelligence"), tmp_path)
    definition = ContextDefinition.model_validate(workspace.seed())
    source_before = json.dumps(workspace._source, sort_keys=True)
    document = workspace.build_model(definition)
    assert "builder_seed" not in json.dumps(document)
    assert json.dumps(workspace._source, sort_keys=True) == source_before
    SemanticIndex(document)

    extension = next(e for e in workspace._source["custom_extensions"] if e["vendor_name"] == "HELIOS")
    metadata = json.loads(extension["data"])
    metadata["mandatory_filter"] = "must not silently discard"
    extension["data"] = json.dumps(metadata)
    document = workspace.build_model(definition)
    assert "mandatory_filter" in json.dumps(document)
    with pytest.raises(Clarification, match="Unsupported mandatory semantic rule"):
        SemanticIndex(document)


def test_fixed_filter_survives_export_and_generic_compilation(tmp_path):
    workspace = ContextWorkspace(pack("power"), tmp_path)
    definition = ContextDefinition.model_validate(workspace.seed())
    metric = definition.metrics[0].model_copy(update={"filters": [MetricFilter(
        field="meter_readings.import_kwh", op=">", value=2.0)]})
    definition = definition.model_copy(update={"metrics": [metric]})
    document = workspace.build_model(definition)
    bundle = SemanticIndex(document).bundle(metric.name, metric=metric.name)["document"]
    generated = Compiler(SemanticModel(bundle)).compile(SemanticRequest(metrics=[metric.name]), "duckdb").sql
    # Independent source expression plus WHERE confirms exported fixed filtering.
    reference = f"SELECT {metric.expression} FROM meter_readings WHERE import_kwh > 2.0"
    engine = LocalPackEngine(workspace.pack)
    try:
        assert engine.query(generated).rows == engine.query(reference).rows
    finally:
        engine.close()
