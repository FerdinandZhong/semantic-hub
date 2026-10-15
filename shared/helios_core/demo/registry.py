"""Validate declared demo packs and snapshot serving bytes without reading evaluation data."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from helios_core.ossie.build import validate


class DemoError(ValueError):
    """A pack, review, or execution binding is invalid."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Example(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    question: str = Field(min_length=1, max_length=500)
    metric: str = Field(min_length=1, max_length=128)
    unit: str = Field(max_length=32)


class PackEntry(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    title: str = Field(min_length=1, max_length=100)
    timezone: str
    adapter: Literal["local_duckdb"] = "local_duckdb"
    retrieval: Literal["disabled"] = "disabled"
    data_origin: Literal["synthetic", "public_source", "document_evidence"] = "synthetic"
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    model_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    examples: tuple[Example, ...]


SQL_TYPES = {
    "String": "VARCHAR",
    "Decimal": "DECIMAL(28,8)",
    "Integer": "BIGINT",
    "Float": "DOUBLE",
    "Boolean": "BOOLEAN",
    "Date": "DATE",
    "DateTime": "TIMESTAMP",
    "DateTimeTz": "TIMESTAMPTZ",
}


def identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", value):
        raise DemoError("Unsupported local SQL identifier")
    return value


def confined(root: Path, relative: str) -> Path:
    """Reject aliases as well as escapes, including cross-pack symlinks."""
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or any(p in {"..", "."} for p in rel.parts):
        raise DemoError("Invalid pack path")
    path = root / rel
    if path.resolve() != path.absolute() or not path.resolve().is_relative_to(root.resolve()):
        raise DemoError("Pack paths cannot escape or use symlinks")
    return path


@dataclass(frozen=True)
class TableSnapshot:
    name: str
    columns: tuple[tuple[str, str], ...]
    csv_bytes: bytes
    row_count: int


@dataclass(frozen=True)
class DocumentSnapshot:
    document_id: str
    path: str
    content_bytes: bytes
    sha256: str
    metadata_bytes: bytes = b"{}"


@dataclass(frozen=True)
class PackSnapshot:
    entry: PackEntry
    fingerprint: str
    model_bytes: bytes
    tables: tuple[TableSnapshot, ...]
    generation_mode: str
    source_name: str
    document_count: int
    documents: tuple[DocumentSnapshot, ...] = ()
    document_manifest_bytes: bytes = b"[]"
    synthetic: bool = True

    def model_document(self) -> dict:
        return json.loads(self.model_bytes)


class PackRegistry:
    def __init__(self, registry_path: Path, fixtures_root: Path):
        self.fixtures_root = fixtures_root.resolve()
        raw = json.loads(registry_path.read_text())
        if set(raw) != {"schema", "packs"} or raw["schema"] != "helios.demo-registry.v1":
            raise DemoError("Unsupported runtime registry")
        entries = [PackEntry.model_validate_json(json.dumps(e)) for e in raw["packs"]]
        self.entries = {e.id: e for e in entries}
        if not entries or len(entries) != len(self.entries):
            raise DemoError("Duplicate or empty pack registry")

    def load(self, pack_id: str) -> PackSnapshot:
        if pack_id not in self.entries:
            raise DemoError("Unknown dataset pack")
        entry = self.entries[pack_id]
        ZoneInfo(entry.timezone)
        pack = confined(self.fixtures_root, pack_id)
        manifest_bytes = confined(pack, "manifest.json").read_bytes()
        if digest(manifest_bytes) != entry.manifest_sha256:
            raise DemoError("Source manifest checksum mismatch")
        manifest = json.loads(manifest_bytes)
        if (
            manifest.get("sector") != pack_id
            or manifest.get("synthetic") is not (entry.data_origin == "synthetic")
            or manifest.get("state") != "IN_REVIEW"
            or manifest.get("serving_root") != "serving"
        ):
            raise DemoError("Expected an IN_REVIEW pack with matching declared data origin")
        if entry.data_origin == "public_source" and (
            manifest.get("external_records_used") is not True
            or not manifest.get("source", {}).get("url")
            or not manifest.get("source_inputs")
        ):
            raise DemoError("Public-source packs require source provenance")
        if entry.data_origin == "document_evidence" and (
            not manifest.get("source_inputs") or not manifest.get("reviewed_extraction")
        ):
            raise DemoError("Document-derived packs require reviewed extraction provenance")
        serving = confined(pack, "serving")
        contents: dict[str, bytes] = {}
        # Evaluation checksum entries are deliberately never opened or indexed.
        for relative, expected in manifest["checksums"].items():
            if not relative.startswith("serving/"):
                continue
            local = relative.removeprefix("serving/")
            source = confined(serving, local)
            if source.stat().st_size > 10_000_000:
                raise DemoError("Serving asset exceeds the local demo size limit")
            data = source.read_bytes()
            if digest(data) != expected:
                raise DemoError("Serving asset checksum mismatch")
            contents[local] = data
        if sum(map(len, contents.values())) > 50_000_000:
            raise DemoError("Pack exceeds the local demo size limit")
        model_bytes = contents.get("draft.ossie.json", b"")
        if digest(model_bytes) != entry.model_sha256:
            raise DemoError("Semantic model checksum mismatch")
        model = json.loads(model_bytes)
        if validate(model):
            raise DemoError("Invalid Ossie model")
        tables = []
        for ds in model["datasets"]:
            name = identifier(ds["name"])
            if ds["source"] != name:
                raise DemoError("Local model sources must match declared table names")
            columns = []
            for field in ds["fields"]:
                field_name = identifier(field["name"])
                if field["datatype"] not in SQL_TYPES:
                    raise DemoError("Unsupported declared column type")
                columns.append((field_name, SQL_TYPES[field["datatype"]]))
            if len({c[0] for c in columns}) != len(columns):
                raise DemoError("Duplicate column name")
            data = contents.get(name + ".csv")
            if data is None:
                raise DemoError("Missing declared serving table")
            reader = csv.reader(io.StringIO(data.decode("utf-8")))
            if next(reader, None) != [c[0] for c in columns]:
                raise DemoError("CSV header differs from declared schema")
            count = 0
            for row in reader:
                if len(row) != len(columns):
                    raise DemoError("CSV row differs from declared schema")
                count += 1
            if count != manifest["row_counts"].get(name):
                raise DemoError("Serving row count mismatch")
            tables.append(TableSnapshot(name, tuple(columns), data, count))
        if len({t.name for t in tables}) != len(tables):
            raise DemoError("Duplicate table name")
        if {p for p in contents if p.endswith(".csv")} != {t.name + ".csv" for t in tables}:
            raise DemoError("Serving tables must have explicit model schemas")
        metrics = {m["name"] for m in model["metrics"]}
        if (
            not entry.examples
            or len({e.id for e in entry.examples}) != len(entry.examples)
            or any(e.metric not in metrics for e in entry.examples)
        ):
            raise DemoError("Examples must reference declared metrics")
        documents = json.loads(contents["documents.json"])
        snapshots = []
        for doc in documents:
            rel = doc["path"]
            if not rel.startswith("documents/") or rel not in contents:
                raise DemoError("Document is outside the declared document root")
            confined(serving, rel)
            snapshots.append(DocumentSnapshot(doc["document_id"], rel, contents[rel], digest(contents[rel]), canonical(doc)))
        if len({d.document_id for d in snapshots}) != len(snapshots):
            raise DemoError("Duplicate document identifier")
        fingerprint = digest(
            canonical(
                    {"contract": "helios.demo-snapshot.v1", "entry": entry.model_dump(
                        mode="json", exclude={"data_origin"} if entry.data_origin == "synthetic" else set()
                    )}
            )
        )
        source = manifest.get("source", {})
        return PackSnapshot(
            entry,
            fingerprint,
            model_bytes,
            tuple(tables),
            manifest.get("generation_mode", "independently synthetic"),
            source.get("name", "Independent synthetic finance"),
            len(documents),
            tuple(snapshots),
            contents["documents.json"],
            manifest["synthetic"],
        )
