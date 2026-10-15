"""Materialize explicitly reviewed visual observations as immutable local sources."""
from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Literal

from pydantic import Field, field_validator

from .context import ContextDefinition, now
from .registry import Contract, DemoError, PackRegistry, canonical, digest


class MaterialVisual(Contract):
    revision: int = Field(ge=1)
    pages: list[int] = Field(min_length=1, max_length=6)


class FactRow(Contract):
    id: str = Field(pattern=r'^observation_[0-9]+$')
    page: int = Field(ge=1, le=32)
    entity: str = Field(max_length=500)
    metric: str = Field(min_length=1, max_length=500)
    value: float | None = Field(allow_inf_nan=False)
    unit: str = Field(max_length=500)
    period: str = Field(max_length=500)
    population: str = Field(max_length=500)
    denominator: float | None = Field(ge=0, allow_inf_nan=False)
    source_quote: str = Field(min_length=1, max_length=2000)
    extraction_kind: Literal['text', 'table', 'chart']
    uncertainty: str = Field(max_length=500)

    @field_validator('metric', 'source_quote')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('A metric and source quotation are required')
        return value.strip()


class MaterialFacts(Contract):
    revision: int = Field(ge=1)
    extraction_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    title: str = Field(min_length=3, max_length=100)
    rows: list[FactRow] = Field(min_length=1, max_length=128)
    reviewer: str = Field(min_length=1, max_length=120)
    note: str = Field(min_length=3, max_length=2000)
    acknowledged: bool


class DocumentModelRegistry:
    """Overlay locally reviewed source packs without editing the fixture registry."""
    def __init__(self, base, state_root):
        self.base = base
        self.root = Path(state_root) / 'document-models'
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.refresh()

    def refresh(self):
        self.entries = dict(self.base.entries)
        self.local = {}
        for index in sorted(self.root.glob('*/registry.json')):
            registry = PackRegistry(index, index.parent)
            for key in registry.entries:
                if key in self.entries:
                    raise DemoError('A document model conflicts with a registered source')
                self.entries[key] = registry.entries[key]
                self.local[key] = registry

    def load(self, key):
        return self.local[key].load(key) if key in self.local else self.base.load(key)

    def create(self, item, payload):
        pack_id = 'doc_' + digest(canonical({'document': item['sha256'], 'id': item['document_id'],
                        'review': payload.model_dump(mode='json')}))[:32]
        with self.lock:
            target = self.root / pack_id
            if not target.exists():
                with tempfile.TemporaryDirectory(prefix='.building-', dir=self.root) as temporary:
                    stage = Path(temporary) / 'ready'
                    stage.mkdir()
                    entry = write_fact_pack(stage, pack_id, item, payload)
                    write_json(stage / 'registry.json', {'schema': 'helios.demo-registry.v1', 'packs': [entry]})
                    pack = PackRegistry(stage/'registry.json', stage).load(pack_id)
                    # Validate real typed loading before the source becomes visible.
                    from .local import LocalPackEngine
                    adapter = LocalPackEngine(pack)
                    adapter.close()
                    os.replace(stage, target)
            self.refresh()
        return pack_id


def write_json(path, content):
    path.write_bytes(json.dumps(content, indent=2, ensure_ascii=False).encode() + b'\n')


OBSERVATION_SCHEMA = {
    'observation_id': ('String', 'Stable ID of the reviewed extracted observation.'),
    'document_id': ('String', 'Uploaded document identity; links to document_sources.'),
    'entity': ('String', 'Entity label as reviewed; not an automatically resolved enterprise entity key.'),
    'metric': ('String', 'Reported indicator or endpoint; keep distinct endpoints separate.'),
    'value': ('Float', 'Reviewed numeric value; null means unknown, not zero. Do not aggregate unlike indicators.'),
    'unit': ('String', 'Reviewed source unit; percentages retain their source scale.'),
    'period': ('String', 'Observation period as reported; may differ from publication date.'),
    'population': ('String', 'Population or market scope to which this observation applies.'),
    'denominator': ('Float', 'Reported denominator; null when unavailable. Do not infer it from another endpoint.'),
    'source_page': ('Integer', 'Physical page number in the original uploaded file, starting at one.'),
    'source_quote': ('String', 'Reviewer-checked source wording or chart labels; not machine-verified text extraction.'),
    'extraction_kind': ('String', 'Text, table, or chart visual extraction route.'),
    'uncertainty': ('String', 'Retained extraction uncertainty or reviewer caveat.'),
    'reviewer': ('String', 'Local reviewer attribution, not authenticated enterprise identity.'),
    'review_note': ('String', 'Reviewer decision note for the selected observation batch.'),
}
SOURCE_SCHEMA = {
    'document_id': ('String', 'Unique uploaded document identifier.'),
    'revision': ('Integer', 'Exact uploaded document revision.'),
    'filename': ('String', 'Original filename.'),
    'sha256': ('String', 'SHA256 of original uploaded bytes.'),
    'extraction_id': ('String', 'Hash binding the model response to source bytes and selected pages.'),
    'extraction_model': ('String', 'Vision model that proposed the observations.'),
    'reviewed_at': ('String', 'Local timestamp of explicit extraction review.'),
}


def write_fact_pack(output, pack_id, item, payload):
    """Generate deterministic schemas and safe per-observation metrics, never LLM SQL."""
    root = output / pack_id
    serving = root / 'serving'
    (serving / 'documents').mkdir(parents=True)
    extracted = item['visual_extraction']
    reviewed_at = now()
    rows = []
    for proposed in payload.rows:
        value = proposed.model_dump()
        rows.append({'observation_id': value.pop('id'), 'document_id': item['document_id'],
                     'source_page': value.pop('page'), **value, 'reviewer': payload.reviewer.strip(), 'review_note': payload.note.strip()})
    sources = [{'document_id': item['document_id'], 'revision': item['revision'], 'filename': item['filename'],
                'sha256': item['sha256'], 'extraction_id': payload.extraction_id, 'extraction_model': extracted['model'], 'reviewed_at': reviewed_at}]
    schemas = {'document_observations': OBSERVATION_SCHEMA, 'document_sources': SOURCE_SCHEMA}
    for table, data in [('document_observations', rows), ('document_sources', sources)]:
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=list(schemas[table]))
        writer.writeheader()
        writer.writerows(data)
        (serving / (table + '.csv')).write_text(stream.getvalue())
    description = 'Reviewed document-derived observations. Values retain source pages, units, scope, and extraction uncertainty. Semantic validation and publication remain pending.'
    meanings = {'document_observations': 'One reviewed document assertion per row; distinct populations, periods, and units must not be pooled.',
                'document_sources': 'Original upload and extraction provenance for the reviewed observations.'}
    common = dict(grain='One reviewed document observation', time_rule='Use the reported period; do not infer missing dates.',
                  owner=payload.reviewer.strip(), reference_sql='', ontology_concepts=['DocumentObservation'],
                  evidence_refs=['document:reviewed_visual_evidence'], assumptions=['Reviewed visual extraction; unknown values remain null.'])
    metrics = [dict(name='reviewed_observation_count', expression='COUNT(document_observations.observation_id)',
                    description='Count of explicitly reviewed observations in this document-derived source.', unit='observations',
                    example_questions=['How many reviewed observations are available?'], **common)]
    for row in rows:
        if row['value'] is None or len(metrics) == 20:
            continue
        # This exact-row metric cannot pool different units, populations or dates.
        name = row['observation_id'] + '_value'
        metrics.append(dict(name=name,
             expression=f"MAX(CASE WHEN document_observations.observation_id = '{row['observation_id']}' THEN document_observations.value END)",
             description=f"{row['metric']} for {row['entity']}. Population: {row['population']}. Period: {row['period']}."[:1000],
             unit=(row['unit'] or 'unspecified')[:64], example_questions=[f"What is {row['metric'][:250]} for {row['entity'][:250]} ({row['observation_id']})?"], **common))
    seed = ContextDefinition.model_validate(dict(title=payload.title, description=description, metrics=metrics,
              joins=[dict(name='observation_document', from_field='document_observations.document_id',
                          to_field='document_sources.document_id', meaning='Every reviewed observation refers to its original uploaded document revision.')],
              dataset_meanings=meanings,
              field_meanings={f'{t}.{f}': desc for t, fields in schemas.items() for f, (_, desc) in fields.items()},
              field_roles={f'{t}.{f}': 'identifier' if f == next(iter(fields)) else 'foreign_key' if f == 'document_id'
                           else 'measure' if f in ('value', 'denominator') else 'attribute' for t, fields in schemas.items() for f in fields},
              glossary_terms=[{'term': 'DocumentObservation', 'definition': 'A source assertion explicitly checked by a local reviewer; not independent truth certification.'},
                              {'term': 'EvidenceLineage', 'definition': 'Trace from a reviewed row to its uploaded source revision and physical page.'}])).model_dump()
    expression = lambda sql: {'dialects': [{'dialect': 'ANSI_SQL', 'expression': sql}]}
    model = {'version': '0.2.0.dev0', 'name': pack_id, 'description': description,
             'datasets': [dict(name=t, source=t, description=meanings[t], fields=[dict(name=f, datatype=kind, description=desc,
                          expression=expression(f), dimension={'is_time': False}) for f,(kind,desc) in fields.items()]) for t,fields in schemas.items()],
             'relationships': [{'name': 'observation_document', 'from': 'document_observations', 'to': 'document_sources',
                                'from_columns': ['document_id'], 'to_columns': ['document_id']}],
             'metrics': [dict(name=m['name'], description=m['description'], expression=expression(m['expression'])) for m in metrics],
             'custom_extensions': [{'vendor_name': 'HELIOS', 'data': json.dumps({'builder_seed': seed})}]}
    write_json(serving/'draft.ossie.json', model)
    write_json(serving/'metadata.json', {'synthetic': False, 'data_origin': 'document_evidence', 'timezone': 'UTC', 'dataset_meanings': meanings})
    evidence = {'document_id': item['document_id'], 'revision': item['revision'], 'sha256': item['sha256'],
                'extraction': extracted, 'review': payload.model_dump(mode='json'), 'reviewed_at': reviewed_at,
                'reviewed_model_links': [link for link in item['links'] if link['status'] == 'approved']}
    # Archive original proposals and reviewer corrections together in the model's serving evidence.
    text = '# Reviewed visual document evidence\n\n' + json.dumps(evidence, indent=2, ensure_ascii=False)
    (serving/'documents/reviewed_visual_evidence.md').write_text(text)
    write_json(serving/'documents.json', [{'document_id': 'reviewed_visual_evidence', 'path': 'documents/reviewed_visual_evidence.md',
               'entity_table': 'document_sources', 'entity_id': item['document_id'], 'source_sha256': item['sha256'],
               'material_kind': 'reviewed_visual_extraction', 'review_status': 'IN_REVIEW'}])
    manifest = {'sector': pack_id, 'synthetic': False, 'state': 'IN_REVIEW', 'serving_root': 'serving',
                'source': {'name': item['filename']}, 'source_inputs': sources, 'reviewed_extraction': payload.extraction_id,
                'generation_mode': 'document-derived; visually extracted and explicitly reviewed observations',
                'row_counts': {'document_observations': len(rows), 'document_sources': 1},
                'checksums': {str(p.relative_to(root)): digest(p.read_bytes()) for p in serving.rglob('*') if p.is_file()}}
    write_json(root/'manifest.json', manifest)
    return {'id': pack_id, 'title': payload.title, 'timezone': 'UTC', 'data_origin': 'document_evidence',
            'manifest_sha256': digest((root/'manifest.json').read_bytes()), 'model_sha256': digest((serving/'draft.ossie.json').read_bytes()),
            'examples': [{'id': 'aggregate' if i == 0 else m['name'], 'question': m['example_questions'][0], 'metric': m['name'], 'unit': m['unit']}
                         for i,m in enumerate(metrics)]}
