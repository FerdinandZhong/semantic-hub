"""Explicit local review and deterministic examples; generic LLM planning stays disabled."""

from __future__ import annotations

import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field

from helios_core.compiler import Compiler, SemanticRequest
from helios_core.ossie.model import SemanticModel
from .context import ContextWorkspace, ContextBinding, MetricDefinition, result_payload
from .local import LocalPackEngine
from .registry import Contract, DemoError, PackSnapshot, canonical, confined, digest


class ReviewReceipt(Contract):
    schema_version: Literal["helios.demo-review.v1"] = "helios.demo-review.v1"
    scope: Literal["local_sample_examples"] = "local_sample_examples"
    pack_id: str
    snapshot_sha256: str
    model_sha256: str
    reviewer: str = Field(min_length=1, max_length=200)
    reviewed_at: str


def receipt_path(state_root: Path, pack: PackSnapshot) -> Path:
    return confined(state_root.resolve(), f"{pack.entry.id}/{pack.fingerprint}/review.json")


def review_pack(pack: PackSnapshot, state_root: Path, reviewer: str) -> Path:
    if not reviewer.strip():
        raise DemoError("An explicit local reviewer is required")
    receipt = ReviewReceipt(
        pack_id=pack.entry.id,
        snapshot_sha256=pack.fingerprint,
        model_sha256=pack.entry.model_sha256,
        reviewer=reviewer.strip(),
        reviewed_at=datetime.now(timezone.utc).isoformat(),
    )
    path = receipt_path(state_root, pack)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Immutable review receipts: an existing decision is never replaced implicitly.
    if path.exists():
        read_review(pack, state_root)
    else:
        with path.open("x") as output:
            output.write(receipt.model_dump_json(indent=2) + "\n")
    return path


def read_review(pack: PackSnapshot, state_root: Path) -> ReviewReceipt:
    path = receipt_path(state_root, pack)
    if not path.is_file():
        raise DemoError("Review this sample snapshot explicitly before execution")
    receipt = ReviewReceipt.model_validate_json(path.read_bytes())
    if (
        receipt.pack_id != pack.entry.id
        or receipt.snapshot_sha256 != pack.fingerprint
        or receipt.model_sha256 != pack.entry.model_sha256
    ):
        raise DemoError("Review receipt belongs to a different pack or release")
    return receipt


class ExampleRequest(Contract):
    pack_id: str = Field(max_length=64)
    snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    session_id: str = Field(max_length=128)
    example_id: str = Field(max_length=64)
    context_sha256: str = Field(default="", max_length=64)


class DemoRuntime:
    def __init__(self, pack: PackSnapshot, state_root: Path):
        self.pack = pack
        self.state_root = state_root
        self.workspace = ContextWorkspace(pack, state_root)
        self.session_id = secrets.token_urlsafe(24)
        self._engine: LocalPackEngine | None = None
        self._lock = threading.Lock()
        from .playground import Playground
        self.playground = Playground(self)

    def summary(self) -> dict:
        try:
            review = read_review(self.pack, self.state_root)
        except FileNotFoundError:
            review = None
        except DemoError:
            review = None
        active = self.workspace.active()
        return {
            "context_version": active["version"] if active else None,
            "context_sha256": active["context_sha256"] if active else "",
            "pack_id": self.pack.entry.id,
            "title": self.pack.entry.title,
            "snapshot_sha256": self.pack.fingerprint,
            "model_sha256": active["validation"]["model_sha256"]
            if active
            else self.pack.entry.model_sha256,
            "session_id": self.session_id,
            "mode": "synthetic_sample" if self.pack.synthetic else self.pack.entry.data_origin + "_derived",
            "data_origin": self.pack.entry.data_origin,
            "planner": "reviewed_context" if active else "predefined_examples",
            "llm_enabled": False,
            "timezone": self.pack.entry.timezone,
            "source": self.pack.source_name,
            "generation_mode": self.pack.generation_mode,
            "synthetic": self.pack.synthetic,
            "review_state": "LOCAL_SAMPLE_REVIEWED" if review or active else "IN_REVIEW",
            "reviewer": active["reviewer"] if active else (review.reviewer if review else None),
            "examples": [
                {
                    "id": m["name"],
                    "metric": m["name"],
                    "question": m["description"],
                    "unit": m["unit"],
                }
                for m in active["definition"]["metrics"]
            ]
            if active
            else [e.model_dump() for e in self.pack.entry.examples],
        }

    def check_binding(self, request: ContextBinding | ExampleRequest) -> None:
        if (
            request.pack_id != self.pack.entry.id
            or request.snapshot_sha256 != self.pack.fingerprint
            or request.session_id != self.session_id
        ):
            raise DemoError("Stale or cross-pack execution binding; reload the selected demo")

    def execute(self, request: ExampleRequest) -> dict:
        self.check_binding(request)
        active = self.workspace.active()
        expected_hash = active["context_sha256"] if active else ""
        if request.context_sha256 != expected_hash:
            raise DemoError("Active context changed. Reload the query page before execution.")
        if active:
            metric = next(
                (m for m in active["definition"]["metrics"] if m["name"] == request.example_id),
                None,
            )
            if metric is None:
                raise DemoError("Unknown metric in the reviewed context")
            compiled = self.workspace.compile_metric(
                SemanticModel(active["document"]), MetricDefinition.model_validate(metric)
            )
            example_id, question, unit = metric["name"], metric["description"], metric["unit"]
            limit = 200
        else:
            read_review(self.pack, self.state_root)
            compiled, example_id, question, unit = self._baseline(request.example_id)
            limit = 1
        result = self.query_local(compiled.sql, limit=limit)
        data = result_payload(result)
        return {
            "pack_id": self.pack.entry.id,
            "snapshot_sha256": self.pack.fingerprint,
            "model_sha256": active["validation"]["model_sha256"]
            if active
            else self.pack.entry.model_sha256,
            "context_version": active["version"] if active else None,
            "context_sha256": expected_hash,
            "example_id": example_id,
            "question": question,
            "unit": unit,
            "planner": "reviewed_context" if active else "predefined_examples",
            "mode": "synthetic_sample" if self.pack.synthetic else self.pack.entry.data_origin + "_derived",
            **data,
            "sql": compiled.sql,
            "sql_sha256": digest(compiled.sql.encode()),
            "result_sha256": digest(canonical(data)),
            "source_manifest_sha256": self.pack.entry.manifest_sha256,
        }

    def query_local(self, sql, limit=200):
        with self._lock:
            if self._engine is None:
                self._engine = LocalPackEngine(self.pack)
            return self._engine.query(sql, limit=limit)

    def _baseline(self, example_id):
        example = next((e for e in self.pack.entry.examples if e.id == example_id), None)
        if example is None:
            raise DemoError("Unknown predefined example")
        compiled = Compiler(SemanticModel(self.pack.model_document())).compile(
            SemanticRequest(metrics=[example.metric], limit=1), dialect="duckdb"
        )
        return compiled, example.id, example.question, example.unit

    def close(self) -> None:
        with self._lock:
            if self._engine:
                self._engine.close()
                self._engine = None
