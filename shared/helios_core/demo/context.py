"""Versioned local context authoring over an immutable local source snapshot.

Operator metadata stays in a pack-scoped SQLite workspace. Validation executes
only bounded SELECTs against serving bytes; it never reads evaluation answers.
"""

from __future__ import annotations

import copy
import csv
import io
import itertools
import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

import sqlglot
from pydantic import Field, field_validator, model_serializer
from sqlglot import exp

from helios_core.compiler import Compiler, SemanticRequest, Filter
from helios_core.engines.base import QueryResult
from helios_core.ossie.build import validate as validate_ossie
from helios_core.ossie.model import SemanticModel
from .local import LocalPackEngine
from .registry import Contract, DemoError, PackSnapshot, canonical, confined, digest


class MetricFilter(Contract):
    field: str = Field(max_length=260)
    op: Literal["=", "!=", "<>", ">", ">=", "<", "<=", "in", "not in", "between", "like", "is null", "is not null"]
    value: str | int | float | bool | list[str | int | float | bool] | None = None


class SupportingMaterialLink(Contract):
    chunk_id: str = Field(min_length=1, max_length=160)
    location: str = Field(min_length=1, max_length=500)
    quote: str = Field(min_length=1, max_length=16000)
    target: str = Field(min_length=1, max_length=500)
    reviewer: str = Field(min_length=1, max_length=160)
    note: str = Field(default="", max_length=2000)


class SupportingMaterialReference(Contract):
    document_id: str = Field(min_length=1, max_length=160)
    revision: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    links: list[SupportingMaterialLink] = Field(default_factory=list, max_length=128)


class DocumentAttachment(Contract):
    id: str
    filename: str
    sha256: str
    snapshot_sha256: str
    entity_links: list[dict] = Field(default_factory=list)
    supporting_material: SupportingMaterialReference | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_reference(self, handler):
        result = handler(self)
        if self.supporting_material is None:
            result.pop("supporting_material", None)
        return result


class MetricDefinition(Contract):
    id: str = Field(default="", max_length=160)
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    description: str = Field(min_length=3, max_length=1000)
    expression: str = Field(min_length=3, max_length=4000)
    unit: str = Field(min_length=1, max_length=64)
    grain: str = Field(min_length=3, max_length=500)
    time_rule: str = Field(min_length=3, max_length=500)
    dimensions: list[str] = Field(default_factory=list, max_length=3)
    reference_sql: str = Field(default="", max_length=8000)
    synonyms: list[str] = Field(default_factory=list, max_length=30)
    example_questions: list[str] = Field(default_factory=list, max_length=20)
    owner: str = Field(default="", max_length=120)
    inclusion_rules: list[str] = Field(default_factory=list, max_length=30)
    exclusion_rules: list[str] = Field(default_factory=list, max_length=30)
    ontology_concepts: list[str] = Field(default_factory=list, max_length=30)
    evidence_refs: list[str] = Field(default_factory=list, max_length=50)
    assumptions: list[str] = Field(default_factory=list, max_length=30)
    confidence: float | None = Field(default=None, ge=0, le=1)
    rationale: str = Field(default="", max_length=2000)
    filters: list[MetricFilter] = Field(default_factory=list, max_length=20)

    @field_validator("synonyms", "example_questions", "inclusion_rules", "exclusion_rules", "ontology_concepts", "evidence_refs", "assumptions")
    @classmethod
    def bounded_descriptions(cls, values):
        if any(len(value) > 1000 for value in values):
            raise ValueError("Metric metadata entries must stay below 1,000 characters")
        return values


class ProposalProvenance(Contract):
    mode: Literal["evidence", "llm"]
    provider: str = Field(default="", max_length=120)
    model: str = Field(default="", max_length=160)
    generated_at: str
    snapshot_sha256: str
    source: str = "source_schema_and_profile"


class JoinDefinition(Contract):
    id: str = Field(default="", max_length=160)
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,127}$")
    from_field: str = Field(max_length=260)
    to_field: str = Field(max_length=260)
    cardinality: Literal["many_to_one"] = "many_to_one"
    meaning: str = Field(min_length=3, max_length=500)


class ContextDefinition(Contract):
    title: str = Field(min_length=3, max_length=100)
    description: str = Field(min_length=3, max_length=1500)
    metrics: list[MetricDefinition] = Field(min_length=1, max_length=20)
    joins: list[JoinDefinition] = Field(default_factory=list, max_length=20)
    field_meanings: dict[str, str] = Field(default_factory=dict, max_length=100)
    proposal_provenance: ProposalProvenance | None = None
    document_attachments: list[DocumentAttachment] = Field(default_factory=list, max_length=20)
    dataset_meanings: dict[str, str] = Field(default_factory=dict, max_length=50)
    field_roles: dict[str, Literal["identifier", "foreign_key", "time", "measure", "dimension", "attribute"]] = Field(default_factory=dict, max_length=100)
    glossary_terms: list[dict] = Field(default_factory=list, max_length=100)


class ContextBinding(Contract):
    pack_id: str = Field(max_length=64)
    snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    session_id: str = Field(max_length=128)


class SaveContext(ContextBinding):
    revision: int = Field(ge=0)
    definition: ContextDefinition


class ValidateContext(ContextBinding):
    revision: int = Field(ge=1)


class ReviewContext(ValidateContext):
    version: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,39}$")
    validation_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewer: str = Field(min_length=1, max_length=120)
    note: str = Field(min_length=3, max_length=1000)
    confirmed: bool


class BatchReview(ValidateContext):
    validation_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    item_ids: list[str] = Field(min_length=1, max_length=150)
    decision: Literal["approve", "request_changes"]
    reviewer: str = Field(min_length=1, max_length=120)
    note: str = Field(min_length=3, max_length=1000)
    confirmed: bool


class RestoreContext(ContextBinding):
    revision: int = Field(ge=0)
    version: str = Field(max_length=40)


class ActivateContext(ContextBinding):
    version: str = Field(max_length=40)
    context_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class PublishContext(ActivateContext):
    confirmed: bool


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def result_payload(result: QueryResult) -> dict:
    def value(item):
        if isinstance(item, Decimal):
            return str(item)
        if isinstance(item, (date, datetime)):
            return item.isoformat()
        return item

    return {
        "columns": result.columns,
        "rows": [[value(v) for v in row] for row in result.rows],
    }


def equivalent(left: QueryResult, right: QueryResult) -> bool:
    if (
        left.columns != right.columns
        or len(left.rows) != len(right.rows)
        or not left.rows
    ):
        return False

    def sort_value(value):
        if value is None:
            return (0, "")
        if isinstance(value, bool):
            return (4, int(value))
        if isinstance(value, (Decimal, float, int)):
            number = Decimal(str(value))
            return (1, number) if number.is_finite() else (2, str(value))
        return (3, str(value))

    def normalized(rows):
        return sorted(rows, key=lambda row: tuple(sort_value(value) for value in row))

    for a, b in zip(normalized(left.rows), normalized(right.rows)):
        for x, y in zip(a, b):
            if isinstance(x, bool) or isinstance(y, bool):
                if type(x) is not type(y) or x != y:
                    return False
            elif isinstance(x, (Decimal, float, int)) and isinstance(
                y, (Decimal, float, int)
            ):
                dx, dy = Decimal(str(x)), Decimal(str(y))
                if (
                    not dx.is_finite()
                    or not dy.is_finite()
                    or abs(dx - dy) > Decimal("1e-8")
                ):
                    return False
            elif x != y:
                return False
    return True


class ContextWorkspace:
    def __init__(self, pack: PackSnapshot, state_root: Path):
        self.pack = pack
        self.path = confined(
            state_root.resolve(), f"{pack.entry.id}/{pack.fingerprint}/context.sqlite"
        )
        self._source = pack.model_document()
        self._fields = {
            f"{d['name']}.{f['name']}": f
            for d in self._source["datasets"]
            for f in d["fields"]
        }

    @contextmanager
    def connection(self, *, write=False):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute(
                "CREATE TABLE IF NOT EXISTS draft (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, definition TEXT NOT NULL, validation TEXT)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS releases (version TEXT PRIMARY KEY, content TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS decisions (revision INTEGER, item_id TEXT, content TEXT, PRIMARY KEY(revision,item_id))"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS publications (version TEXT PRIMARY KEY, context_sha256 TEXT NOT NULL, published_at TEXT NOT NULL)"
            )
            if write:
                connection.execute("BEGIN IMMEDIATE")
            with connection:
                yield connection
        finally:
            connection.close()

    def seed(self) -> dict:
        # A checksummed source pack can ship reviewed-in-code business definitions.
        # They remain an unapproved draft and never contain evaluation answers.
        for extension in self._source.get("custom_extensions", []):
            if extension.get("vendor_name") == "HELIOS":
                candidate = json.loads(extension.get("data", "{}" )).get("builder_seed")
                if candidate is not None:
                    return self.identify(ContextDefinition.model_validate(candidate).model_dump())
        examples = {e.metric: e for e in self.pack.entry.examples}
        metrics = []
        for metric in self._source["metrics"]:
            example = examples.get(metric["name"])
            metrics.append(
                {
                    "name": metric["name"],
                    "description": metric.get("description") or metric["name"],
                    "expression": metric["expression"]["dialects"][0]["expression"],
                    "unit": example.unit if example else "count",
                    "grain": "One aggregate over the selected source records",
                    "time_rule": f"Reporting timezone: {self.pack.entry.timezone}; no date filter",
                    "dimensions": [],
                    "reference_sql": "",
                }
            )
        joins = [
            {
                "name": j["name"],
                "from_field": j["from"] + "." + j["from_columns"][0],
                "to_field": j["to"] + "." + j["to_columns"][0],
                "cardinality": "many_to_one",
                "meaning": f"Link {j['from']} to {j['to']} by its declared key",
            }
            for j in self._source.get("relationships", [])
        ]
        return self.identify(
            {
                "title": self.pack.entry.title + " context",
                "description": ("Business definitions for the selected synthetic dataset. Review before use."
                                if self.pack.synthetic else
                                "Business definitions for curated public source facts. Review source provenance before use."),
                "metrics": metrics,
                "joins": joins,
                "field_meanings": {},
            }
        )

    @staticmethod
    def identify(definition):
        value = copy.deepcopy(definition)
        for kind in ("metrics", "joins"):
            for item in value[kind]:
                if not item.get("id"):
                    item["id"] = kind[:-1] + "-" + digest(item["name"].encode())[:20]
        return value

    def _draft(self, connection, revision=None) -> dict:
        row = connection.execute("SELECT * FROM draft WHERE id=1").fetchone()
        draft = (
            {
                "revision": row["revision"],
                "definition": json.loads(row["definition"]),
                "validation": (
                    json.loads(row["validation"]) if row["validation"] else None
                ),
            }
            if row
            else {"revision": 0, "definition": self.seed(), "validation": None}
        )
        draft["definition"] = self.identify(draft["definition"])
        baseline = connection.execute(
            "SELECT value FROM settings WHERE key='draft_baseline'"
        ).fetchone()
        draft["baseline_version"] = baseline[0] if baseline else "starter"
        if revision is not None and draft["revision"] != revision:
            raise DemoError("Draft changed in another tab. Reload before continuing.")
        return draft

    def view(self) -> dict:
        with self.connection() as connection:
            draft = self._draft(connection)
            releases = [
                json.loads(r["content"])
                for r in connection.execute(
                    "SELECT content FROM releases ORDER BY rowid DESC LIMIT 100"
                )
            ]
            active = connection.execute(
                "SELECT value FROM settings WHERE key='active'"
            ).fetchone()
        return {
            "review": self.review_items(draft),
            "draft": draft,
            "versions": [
                {
                    k: r[k]
                    for k in (
                        "version",
                        "context_sha256",
                        "reviewer",
                        "reviewed_at",
                        "revision",
                        "note",
                    )
                }
                | {"published": self.is_published(r)}
                for r in releases
            ],
            "active_version": active["value"] if active else None,
            "pack_id": self.pack.entry.id,
            "snapshot_sha256": self.pack.fingerprint,
        }

    def tables(self, offset=0, limit=20) -> dict:
        if not 0 <= offset <= 10000 or not 1 <= limit <= 50:
            raise DemoError("Invalid table page")
        return {
            "total": len(self.pack.tables),
            "items": [
                {
                    "name": t.name,
                    "row_count": t.row_count,
                    "field_count": len(t.columns),
                }
                for t in self.pack.tables[offset : offset + limit]
            ],
        }

    def table(self, name: str) -> dict:
        table = next((t for t in self.pack.tables if t.name == name), None)
        if table is None:
            raise DemoError("Table does not belong to the selected pack")
        reader = csv.DictReader(io.StringIO(table.csv_bytes.decode()))
        rows = [
            {k: v[:500] if v else None for k, v in row.items()}
            for row in itertools.islice(reader, 10)
        ]
        return {
            "name": name,
            "row_count": table.row_count,
            "preview_limit": 10,
            "columns": [
                {
                    "id": f"field:{name}.{n}",
                    "name": n,
                    "type": t,
                    "qualified": f"{name}.{n}",
                }
                for n, t in table.columns
            ],
            "rows": rows,
        }

    def save(
        self, revision: int, definition: ContextDefinition, baseline_version=None
    ) -> dict:
        for name, meaning in definition.field_meanings.items():
            if (
                name not in self._fields
                or not isinstance(meaning, str)
                or len(meaning) > 1000
            ):
                raise DemoError(
                    "Column meaning must reference a declared field and stay below 1,000 characters"
                )
        value = self.identify(definition.model_dump())
        ids = [i["id"] for kind in ("metrics", "joins") for i in value[kind]]
        if any(
            not item["id"].startswith(kind[:-1] + "-")
            for kind in ("metrics", "joins")
            for item in value[kind]
        ):
            raise DemoError("Object IDs must use metric- or join- namespaces")
        if len(ids) != len(set(ids)):
            raise DemoError("Object IDs must be unique")
        with self.connection(write=True) as connection:
            self._draft(connection, revision)
            if baseline_version is None:
                active = connection.execute(
                    "SELECT value FROM settings WHERE key='active'"
                ).fetchone()
                prior = connection.execute(
                    "SELECT value FROM settings WHERE key='draft_baseline'"
                ).fetchone()
                baseline_version = (
                    active[0] if active else prior[0] if prior else "starter"
                )
            if baseline_version != "starter":
                self._release(connection, baseline_version)
            connection.execute(
                "INSERT OR REPLACE INTO settings VALUES ('draft_baseline', ?)",
                (baseline_version,),
            )
            connection.execute(
                "INSERT INTO draft VALUES (1, ?, ?, NULL) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision, definition=excluded.definition, validation=NULL",
                (revision + 1, json.dumps(value)),
            )
        return self.view()

    def build_model(self, definition: ContextDefinition) -> dict:
        if any(k not in self._fields for k in definition.field_roles):
            raise DemoError("Field roles must reference declared source fields")
        if any(k not in {d['name'] for d in self._source['datasets']} for k in definition.dataset_meanings):
            raise DemoError("Dataset meanings must reference declared source tables")
        if definition.document_attachments:
            from .builder_artifacts import BuilderArtifacts
            BuilderArtifacts(self).resolve(
                [a.model_dump() for a in definition.document_attachments]
            )
        names = [m.name for m in definition.metrics]
        if len(names) != len(set(names)):
            raise DemoError("Metric names must be unique")
        join_names = [j.name for j in definition.joins]
        if len(join_names) != len(set(join_names)):
            raise DemoError("Relationship names must be unique")
        document = copy.deepcopy(self._source)
        document.update(
            name=definition.title,
            description=definition.description,
            metrics=[],
            relationships=[],
        )
        # The seed initializes the editor; current reviewed definitions below
        # supply serving semantics. Do not export stale authoring rules twice.
        extensions = []
        for extension in document.get("custom_extensions", []):
            if extension.get("vendor_name") == "HELIOS":
                metadata = json.loads(extension.get("data", "{}"))
                if isinstance(metadata, dict) and "builder_seed" in metadata:
                    metadata.pop("builder_seed")
                    if not metadata:
                        continue
                    extension = {**extension, "data": json.dumps(metadata)}
            extensions.append(extension)
        if "custom_extensions" in document:
            document["custom_extensions"] = extensions
        for dataset in document["datasets"]:
            dataset["description"] = definition.dataset_meanings.get(dataset["name"], dataset.get("description", ""))
            for field in dataset["fields"]:
                field["description"] = definition.field_meanings.get(
                    f"{dataset['name']}.{field['name']}", field.get("description", "")
                )
                role = definition.field_roles.get(f"{dataset['name']}.{field['name']}")
                if role:
                    extensions = field.setdefault("custom_extensions", [])
                    extension = next((item for item in extensions if item["vendor_name"] == "HELIOS"), None)
                    if extension is None:
                        extensions.append({"vendor_name": "HELIOS", "data": json.dumps({"role": role})})
                    else:
                        metadata = json.loads(extension["data"])
                        metadata["role"] = role
                        extension["data"] = json.dumps(metadata)
        for join in definition.joins:
            if join.from_field not in self._fields or join.to_field not in self._fields:
                raise DemoError("Relationship keys must belong to the selected pack")
            source, source_key = join.from_field.split(".")
            target, target_key = join.to_field.split(".")
            if (
                source == target
                or self._fields[join.from_field]["datatype"]
                != self._fields[join.to_field]["datatype"]
            ):
                raise DemoError(
                    "Relationships need different tables and matching key types"
                )
            document["relationships"].append(
                {
                    "name": join.name,
                    "from": source,
                    "to": target,
                    "from_columns": [source_key],
                    "to_columns": [target_key],
                }
            )
        for metric in definition.metrics:
            expressions = sqlglot.parse(metric.expression)
            if len(expressions) != 1 or not isinstance(
                expressions[0], (exp.Sum, exp.Avg, exp.Count, exp.Min, exp.Max)
            ):
                raise DemoError(
                    "Use one SUM, AVG, COUNT(column), MIN or MAX expression per metric"
                )
            tree = expressions[0]
            columns = list(tree.find_all(exp.Column))
            if not columns or any(
                c.db or c.catalog or f"{c.table}.{c.name}" not in self._fields
                for c in columns
            ):
                raise DemoError(
                    "Metric columns must use declared table.column identifiers"
                )
            if len({c.table for c in columns}) != 1:
                raise DemoError("A metric expression must use one fact table")
            if metric.filters:
                from helios_core.compiler.compiler import _condition
                source_model = SemanticModel(document)
                fact = columns[0].table
                predicates = []
                for predicate in metric.filters:
                    if predicate.field not in self._fields or predicate.field.split(".")[0] != fact:
                        raise DemoError("Fixed metric filters must reference fields in the metric table")
                    field = source_model.field(predicate.field)
                    predicates.append(_condition(
                        exp.column(field.name, table=fact),
                        Filter(**predicate.model_dump()), field,
                    ))
                tree.set("this", exp.Case(ifs=[exp.If(
                    this=exp.and_(*predicates), true=tree.this.copy()
                )]))
            allowed = {
                "SUM",
                "AVG",
                "COUNT",
                "MIN",
                "MAX",
                "CASE",
                "IF",
                "COALESCE",
                "AND",
                "OR",
            }
            if any(
                isinstance(n, (exp.Query, exp.Table, exp.Window))
                or (isinstance(n, exp.Func) and n.sql_name() not in allowed)
                for n in tree.walk()
            ):
                raise DemoError("Metric expression contains unsupported SQL")
            if len(list(tree.find_all(exp.AggFunc))) != 1:
                raise DemoError("Nested aggregates are unsupported")
            if any(d not in self._fields for d in metric.dimensions):
                raise DemoError("Grouping fields must belong to the selected pack")
            outputs = [d.split(".")[1] for d in metric.dimensions] + [metric.name]
            if len(outputs) != len(set(outputs)):
                raise DemoError("Grouping and metric output names must be unique")
            document["metrics"].append(
                {
                    "name": metric.name,
                    "description": metric.description,
                    "ai_context": {"synonyms": metric.synonyms},
                    "custom_extensions": [{"vendor_name": "HELIOS", "data": json.dumps({
                        "business_context": metric.model_dump(include={
                            "unit", "grain", "time_rule", "owner", "synonyms", "example_questions",
                            "inclusion_rules", "exclusion_rules", "ontology_concepts", "evidence_refs",
                            "assumptions", "rationale",
                        })
                    }, sort_keys=True)}],
                    "expression": {
                        "dialects": [{"dialect": "ANSI_SQL", "expression": tree.sql()}]
                    },
                }
            )
        if validate_ossie(document):
            raise DemoError("The generated semantic model failed Ossie validation")
        model = SemanticModel(document)
        for metric in definition.metrics:
            self.compile_metric(model, metric)
        return document

    @staticmethod
    def compile_metric(model: SemanticModel, metric: MetricDefinition):
        fact = model.metric(metric.name).dataset

        # Require a unique directed many-to-one route for every grouping table.
        def paths(current, target, seen):
            if current == target:
                return 1
            return min(
                2,
                sum(
                    paths(r.to_dataset, target, seen | {r.to_dataset})
                    for r in model.relationships.values()
                    if r.from_dataset == current and r.to_dataset not in seen
                ),
            )

        for dimension in metric.dimensions + [f.field for f in metric.filters]:
            if paths(fact, dimension.split(".")[0], {fact}) != 1:
                raise DemoError(
                    "Grouping requires one unambiguous many-to-one path from the metric table"
                )
        compiled = Compiler(model).compile(
            SemanticRequest(
                metrics=[metric.name], dimensions=metric.dimensions,
                limit=201
            ),
            dialect="duckdb",
        )
        visited = {fact}
        for name in compiled.joins:
            relationship = model.relationships[name]
            if (
                relationship.from_dataset not in visited
                or relationship.to_dataset in visited
            ):
                raise DemoError(
                    "Compiler selected a join that can multiply the metric's source rows"
                )
            visited.add(relationship.to_dataset)
        return compiled

    def validate(self, revision: int) -> dict:
        with self.connection() as connection:
            draft = self._draft(connection, revision)
        definition = ContextDefinition.model_validate(draft["definition"])
        report = {
            "revision": revision,
            "definition_sha256": digest(canonical(draft["definition"])),
            "snapshot_sha256": self.pack.fingerprint,
            "checked_at": now(),
            "passed": False,
            "metrics": [],
            "joins": [],
            "errors": [],
        }
        engine = None
        try:
            invalid_metrics = {}
            try:
                document = self.build_model(definition)
            except DemoError as exc:
                report["errors"].append(str(exc))
                document = None
                for metric in definition.metrics:
                    try:
                        candidate_document = self.build_model(
                            definition.model_copy(update={"metrics": [metric]})
                        )
                        if document is None:
                            document = candidate_document
                    except DemoError as item_error:
                        invalid_metrics[metric.name] = str(item_error)
                if document is None:
                    raise DemoError("No metric has a valid semantic definition")
            engine = LocalPackEngine(self.pack)
            for join in definition.joins:
                source, source_key = join.from_field.split(".")
                target, target_key = join.to_field.split(".")
                total, nonnull, distinct = engine.query(
                    f'SELECT COUNT(*), COUNT("{target_key}"), COUNT(DISTINCT "{target_key}") FROM "{target}"',
                    limit=1,
                ).rows[0]
                unmatched = engine.query(
                    f'SELECT COUNT(*) FROM "{source}" AS s LEFT JOIN "{target}" AS t ON s."{source_key}" = t."{target_key}" WHERE t."{target_key}" IS NULL',
                    limit=1,
                ).rows[0][0]
                passed = total == nonnull == distinct and unmatched == 0
                report["joins"].append(
                    {
                        "name": join.name,
                        "passed": passed,
                        "target_rows": total,
                        "duplicate_keys": nonnull - distinct,
                        "null_target_keys": total - nonnull,
                        "unmatched_source_rows": unmatched,
                    }
                )
            for metric in definition.metrics:
                item = {"name": metric.name, "passed": False}
                try:
                    if metric.name in invalid_metrics:
                        raise DemoError(invalid_metrics[metric.name])
                    metric_document = self.build_model(
                        definition.model_copy(update={"metrics": [metric]})
                    )
                    compiled = self.compile_metric(
                        SemanticModel(metric_document), metric
                    )
                    candidate = engine.query(compiled.sql, limit=201)
                    item.update(sql=compiled.sql, result=result_payload(candidate))
                    if len(candidate.rows) >= 201:
                        raise DemoError(
                            "Validation exceeds 200 rows; narrow the grouping"
                        )
                    if not metric.reference_sql.strip():
                        raise DemoError(
                            "Supply reviewer-authored reference SQL to reconcile this metric"
                        )
                    reference = engine.query(metric.reference_sql, limit=201)
                    if len(reference.rows) >= 201:
                        raise DemoError("Reference result exceeds 200 rows")
                    item.update(
                        reference_result=result_payload(reference),
                        reference_sql=metric.reference_sql,
                        passed=equivalent(candidate, reference),
                    )
                    if not item["passed"]:
                        item["error"] = (
                            "Compiled and reference results differ. Check columns, filters, grain and units."
                        )
                except DemoError as exc:
                    item["error"] = str(exc)
                except Exception:
                    item["error"] = (
                        "SQL could not execute within the local source scope and query budget. Check its fields and types."
                    )
                report["metrics"].append(item)
            report["passed"] = (
                not report["errors"]
                and all(j["passed"] for j in report["joins"])
                and all(m["passed"] for m in report["metrics"])
            )
            report["model_sha256"] = digest(canonical(document))
        except DemoError as exc:
            report["errors"].append(str(exc))
        except Exception:
            report["errors"].append(
                "Validation could not complete. Check SQL syntax, field types and source scope."
            )
        finally:
            if engine:
                engine.close()
        report["validation_sha256"] = digest(canonical(report))
        with self.connection(write=True) as connection:
            self._draft(connection, revision)
            connection.execute(
                "UPDATE draft SET validation=? WHERE id=1", (json.dumps(report),)
            )
        return self.view()

    def review(self, request: ReviewContext) -> dict:
        if request.version in {"starter", "draft"}:
            raise DemoError("Version names starter and draft are reserved")
        if (
            not request.confirmed
            or not request.reviewer.strip()
            or not request.note.strip()
        ):
            raise DemoError(
                "Confirm the definitions and evidence, with a reviewer and review note"
            )
        with self.connection(write=True) as connection:
            draft = self._draft(connection, request.revision)
            validation = draft["validation"]
            if (
                not validation
                or not validation["passed"]
                or validation["validation_sha256"] != request.validation_sha256
                or validation["definition_sha256"]
                != digest(canonical(draft["definition"]))
            ):
                raise DemoError(
                    "Validate this exact draft successfully before reviewing a version"
                )
            if any(
                i["status"] != "approved"
                for i in self.review_items(draft, connection)["items"]
            ):
                raise DemoError(
                    "Approve every required item before final version review"
                )
            definition = ContextDefinition.model_validate(draft["definition"])
            document = self.build_model(definition)
            release = {
                "version": request.version,
                "revision": request.revision,
                "pack_id": self.pack.entry.id,
                "snapshot_sha256": self.pack.fingerprint,
                "scope": "local_sample_context",
                "publication_required": True,
                "item_review": self.review_items(draft, connection),
                "definition": draft["definition"],
                "document": document,
                "validation": validation,
                "reviewer": request.reviewer.strip(),
                "note": request.note.strip(),
                "reviewed_at": now(),
            }
            from .builder_artifacts import BuilderArtifacts
            release["artifacts"] = BuilderArtifacts(self).bundle(
                release["definition"], document, request.version, release["item_review"]
            )
            release["context_sha256"] = digest(canonical(release))
            try:
                connection.execute(
                    "INSERT INTO releases VALUES (?, ?)",
                    (request.version, json.dumps(release)),
                )
            except sqlite3.IntegrityError:
                raise DemoError(
                    "That version already exists. Choose a new immutable version name."
                ) from None
        return self.view()

    def _release(self, connection, version) -> dict:
        row = connection.execute(
            "SELECT content FROM releases WHERE version=?", (version,)
        ).fetchone()
        if row is None:
            raise DemoError("Reviewed context version not found for this pack")
        release = json.loads(row["content"])
        content = {k: v for k, v in release.items() if k != "context_sha256"}
        if (
            digest(canonical(content)) != release["context_sha256"]
            or release["pack_id"] != self.pack.entry.id
            or release["snapshot_sha256"] != self.pack.fingerprint
        ):
            raise DemoError("Reviewed context checksum or source binding is invalid")
        return release

    def release(self, version: str) -> dict:
        with self.connection() as connection:
            return self._release(connection, version)

    def activate(self, version: str, expected_hash: str) -> dict:
        with self.connection(write=True) as connection:
            release = self._release(connection, version)
            if release["context_sha256"] != expected_hash:
                raise DemoError("Context version changed. Reload before activation.")
            if not self.is_published(release, connection):
                raise DemoError("Publish this reviewed version before activation")
            connection.execute(
                "INSERT INTO settings VALUES ('active', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (version,),
            )
        return self.view()

    def is_published(self, release, connection=None):
        if not release.get("publication_required"):
            return True
        if connection is None:
            with self.connection() as conn:
                return self.is_published(release, conn)
        row = connection.execute(
            "SELECT context_sha256 FROM publications WHERE version=?",
            (release["version"],),
        ).fetchone()
        return bool(row and row[0] == release["context_sha256"])

    def publish(self, request):
        if not request.confirmed:
            raise DemoError("Confirm publication of this reviewed version")
        with self.connection(write=True) as connection:
            release = self._release(connection, request.version)
            if release["context_sha256"] != request.context_sha256:
                raise DemoError("Context version changed. Reload before publication")
            connection.execute(
                "INSERT OR IGNORE INTO publications VALUES (?, ?, ?)",
                (request.version, request.context_sha256, now()),
            )
        return self.view()

    def compare(
        self,
        version="draft",
        baseline_version="starter",
        definition=None,
        connection=None,
    ):
        if connection is None:
            with self.connection() as conn:
                return self.compare(version, baseline_version, definition, conn)
        if connection is not None:
            before = (
                self.seed()
                if baseline_version == "starter"
                else self.identify(
                    self._release(connection, baseline_version)["definition"]
                )
            )
            after = (
                definition
                if definition is not None
                else (
                    self._draft(connection)["definition"]
                    if version == "draft"
                    else self.identify(self._release(connection, version)["definition"])
                )
            )

        def objects(value):
            result = {
                "context": (
                    "context",
                    value["title"],
                    {k: value.get(k) for k in ("title", "description", "dataset_meanings", "field_roles", "glossary_terms", "proposal_provenance")},
                )
            }
            for attachment in value.get("document_attachments", []):
                result["document:" + attachment["id"]] = (
                    "document", attachment["filename"], attachment
                )
            for document in self.pack.documents:
                result["source-document:" + document.document_id] = (
                    "document", document.document_id,
                    {"origin": "serving_document", "citation": document.path,
                     "sha256": document.sha256,
                     "source_metadata": json.loads(document.metadata_bytes),
                     "content": document.content_bytes.decode("utf-8")},
                )
            result["ontology:source-mapping"] = (
                "ontology", "Source ontology mapping",
                {"scope": "source_structure_proposal",
                 "entities": [table.name for table in self.pack.tables],
                 "relationships": value.get("joins", []),
                 "metric_concepts": {metric["name"]: metric.get("ontology_concepts", [])
                                     for metric in value.get("metrics", [])},
                 "glossary_terms": value.get("glossary_terms", [])},
            )
            for kind in ("metrics", "joins"):
                result.update(
                    {
                        item["id"]: (kind[:-1], item["name"], item)
                        for item in value[kind]
                    }
                )
            result.update(
                {
                    "field:"
                    + name: (
                        "field",
                        name,
                        {
                            "meaning": value["field_meanings"].get(
                                name, field.get("description", "")
                            ),
                            "type": field["datatype"],
                        },
                    )
                    for name, field in self._fields.items()
                }
            )
            return result

        old, new = objects(before), objects(after)
        dependency_changed = (
            before["joins"] != after["joins"]
            or before["field_meanings"] != after["field_meanings"]
        )
        items = []
        for identifier in sorted(old.keys() | new.keys()):
            a, b = old.get(identifier), new.get(identifier)
            kind, name, _ = b or a
            change = (
                "added"
                if not a
                else (
                    "removed"
                    if not b
                    else (
                        "modified"
                        if a[2] != b[2]
                        else (
                            "affected"
                            if kind == "metric" and dependency_changed
                            else "unchanged"
                        )
                    )
                )
            )
            items.append(
                dict(
                    id=identifier,
                    kind=kind,
                    name=name,
                    change=change,
                    before=a[2] if a else None,
                    after=b[2] if b else None,
                )
            )
        return dict(items=items, baseline_version=baseline_version, version=version)

    def review_items(self, draft, connection=None):
        if connection is None:
            with self.connection() as conn:
                return self.review_items(draft, conn)
        baseline_version = draft.get("baseline_version", "starter")
        items = self.compare(
            baseline_version=baseline_version,
            definition=draft["definition"],
            connection=connection,
        )["items"]
        validation = draft["validation"] or {}
        if connection is not None:
            decisions = {
                row["item_id"]: json.loads(row["content"])
                for row in connection.execute(
                    "SELECT * FROM decisions WHERE revision=?", (draft["revision"],)
                )
            }
        for item in items:
            reasons = (
                list(validation.get("errors", []))
                if item["kind"] in ("context", "field", "document", "ontology")
                else []
            )
            if not validation:
                reasons.append("Validate the saved revision first")
            if item["kind"] in ("metric", "join") and item["after"]:
                evidence = next(
                    (
                        v
                        for v in validation.get(item["kind"] + "s", [])
                        if v["name"] == item["name"]
                    ),
                    None,
                )
                if not evidence or not evidence["passed"]:
                    reasons.append(
                        (evidence or {}).get("error", "Item validation failed")
                    )
            if item["kind"] == "metric" and any(
                not j["passed"] for j in validation.get("joins", [])
            ):
                reasons.append("A relationship dependency failed validation")
            item.update(eligible=not reasons, reasons=reasons, status="pending")
            decision = decisions.get(item["id"])
            if decision and decision["validation_sha256"] == validation.get(
                "validation_sha256"
            ):
                item["status"] = (
                    "approved"
                    if decision["decision"] == "approve"
                    else "changes_requested"
                )
                item["decision"] = decision
        return {
            "items": items,
            "baseline_version": baseline_version,
            "counts": {
                status: sum(i["status"] == status for i in items)
                for status in ("pending", "approved", "changes_requested")
            },
        }

    def batch_review(self, request):
        if (
            not request.confirmed
            or not request.reviewer.strip()
            or not request.note.strip()
        ):
            raise DemoError("Confirm the item decision with reviewer and note")
        with self.connection(write=True) as connection:
            draft = self._draft(connection, request.revision)
            validation = draft["validation"]
            if (
                not validation
                or validation["validation_sha256"] != request.validation_sha256
                or validation["definition_sha256"]
                != digest(canonical(draft["definition"]))
            ):
                raise DemoError("Validate this exact saved revision before item review")
            items = {i["id"]: i for i in self.review_items(draft, connection)["items"]}
            outcomes = []
            for identifier in dict.fromkeys(request.item_ids):
                item = items.get(identifier)
                if not item or (request.decision == "approve" and not item["eligible"]):
                    outcomes.append(
                        dict(
                            id=identifier,
                            accepted=False,
                            reasons=(
                                item["reasons"] if item else ["Unknown review item"]
                            ),
                        )
                    )
                    continue
                decision = request.model_dump(exclude={"item_ids", "session_id"}) | {
                    "decided_at": now()
                }
                connection.execute(
                    "INSERT OR REPLACE INTO decisions VALUES (?, ?, ?)",
                    (request.revision, identifier, json.dumps(decision)),
                )
                outcomes.append(
                    dict(
                        id=identifier,
                        accepted=True,
                        status=(
                            "approved"
                            if request.decision == "approve"
                            else "changes_requested"
                        ),
                    )
                )
        return self.view() | {"outcomes": outcomes}

    def restore(self, revision, version):
        with self.connection() as connection:
            self._draft(connection, revision)
            definition = self._release(connection, version)["definition"]
        return self.save(
            revision,
            ContextDefinition.model_validate(definition),
            baseline_version=version,
        )

    def source_graph(self, version=None):
        with self.connection() as connection:
            draft = self._release(connection, version) if version else self._draft(connection)
        # A release graph must never borrow its schema or definitions from the current draft.
        document = draft["document"] if version else self.pack.model_document()
        source_fields = {
            f"{dataset['name']}.{field['name']}"
            for dataset in document["datasets"] for field in dataset["fields"]
        }
        dependencies = {}
        for metric in draft["definition"]["metrics"]:
            expression_fields = set()
            unknown_fields = set()
            warnings = []
            parsed = True
            try:
                trees = sqlglot.parse(metric["expression"])
                if len(trees) != 1 or trees[0] is None:
                    warnings.append("Expression must contain one SQL expression")
                    parsed = False
                for tree in trees:
                    if tree is None:
                        continue
                    for column in tree.find_all(exp.Column):
                        qualified = column.sql()
                        if not column.db and not column.catalog and column.table:
                            qualified = f"{column.table}.{column.name}"
                            if qualified in source_fields:
                                expression_fields.add(qualified)
                                continue
                        unknown_fields.add(qualified)
            except sqlglot.errors.SqlglotError:
                parsed = False
                warnings.append(
                    "SQL dependency parsing failed; expression dependencies are unavailable"
                )
            dimension_fields = set()
            for qualified in metric["dimensions"]:
                if qualified in source_fields:
                    dimension_fields.add(qualified)
                else:
                    unknown_fields.add(qualified)
            if unknown_fields:
                warnings.append(
                    "Some referenced fields do not match declared source fields"
                )
            fields = sorted(expression_fields | dimension_fields)
            dependencies[metric["id"]] = {
                "source": "reviewed_version" if version else "saved_draft",
                "parsed": parsed,
                "fields": fields,
                "field_ids": ["field:" + field for field in fields],
                "expression_fields": sorted(expression_fields),
                "dimension_fields": sorted(dimension_fields),
                "unknown_fields": sorted(unknown_fields),
                "warnings": warnings,
            }
        return {
            "draft_revision": draft["revision"],
            "version": version,
            "context_sha256": draft.get("context_sha256"),
            "definition_sha256": digest(canonical(draft["definition"])),
            "metric_dependencies": dependencies,
            "nodes": [
                {
                    "id": dataset["name"], "name": dataset["name"],
                    "type": "dataset", "label": dataset["name"],
                    "description": dataset.get("description", ""),
                    "columns": [
                        {"id": f"field:{dataset['name']}.{field['name']}",
                         "name": field["name"], "qualified": f"{dataset['name']}.{field['name']}",
                         "type": field["datatype"], "description": field.get("description", "")}
                        for field in dataset["fields"]
                    ],
                }
                for dataset in document["datasets"]
            ] if version else [
                self.table(t.name) | {"id": t.name, "type": "dataset", "label": t.name}
                for t in self.pack.tables
            ],
            "edges": [
                j
                | {
                    "source": j["from_field"].split(".")[0],
                    "target": j["to_field"].split(".")[0],
                    "label": j["name"],
                    "kind": "join",
                }
                for j in draft["definition"]["joins"]
            ],
        }

    def active(self) -> dict | None:
        # Preserve read-only startup when no context workspace has been created.
        if not self.path.exists():
            return None
        with self.connection() as connection:
            row = connection.execute(
                "SELECT value FROM settings WHERE key='active'"
            ).fetchone()
            return self._release(connection, row["value"]) if row else None
