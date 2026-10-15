"""Source-bound builder artifacts and immutable local document attachments."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from helios_core.ontology.graph import GraphEdge, GraphNode, OntologyGraph
from helios_core.ontology.mapping import ConceptMapping, EntityMapping, Identifiers, RelationshipMapping, SourceMapping
from .registry import DemoError, canonical, digest

MAX_DOCUMENT_BYTES = 262144


def _ext(field):
    result = {}
    for extension in field.get('custom_extensions', []):
        if extension.get('vendor_name') == 'HELIOS':
            try:
                value = json.loads(extension.get('data', '{}'))
            except (ValueError, TypeError):
                continue
            if isinstance(value, dict):
                result.update(value)
    return result


class BuilderArtifacts:
    def __init__(self, workspace):
        self.workspace = workspace
        self.pack = workspace.pack
        self.rows = {
            table.name: list(csv.DictReader(io.StringIO(table.csv_bytes.decode('utf-8'))))
            for table in self.pack.tables
        }

    def validate_links(self, links: list[dict]) -> list[dict]:
        if len(links) > 50:
            raise DemoError('A document supports at most 50 entity links')
        normalized = []
        for link in links:
            if set(link) != {'table', 'column', 'value'}:
                raise DemoError('Entity links require table, column, and value')
            table, column, value = link['table'], link['column'], link['value']
            if not all(isinstance(v, str) and v for v in (table, column, value)):
                raise DemoError('Entity link values must be nonempty strings')
            rows = self.rows.get(table)
            if not rows or column not in rows[0]:
                raise DemoError('Entity link references an unknown table or column')
            values = [row[column] for row in rows]
            if any(not item for item in values) or len(set(values)) != len(values):
                raise DemoError('Entity links require a unique nonempty source key')
            if value not in values:
                raise DemoError('Entity link value does not exist in the serving snapshot')
            if link not in normalized:
                normalized.append(dict(link))
        return normalized

    def validate_supporting_material(self, metadata: dict, data: bytes) -> dict:
        from .context import SupportingMaterialReference
        from pydantic import ValidationError
        try:
            provenance = SupportingMaterialReference.model_validate(metadata).model_dump()
        except ValidationError:
            raise DemoError('Supporting material provenance is invalid') from None
        # The library binds the original upload checksum and connection identity.
        # The attachment checksum separately binds this exported excerpt.
        definition = self.workspace.view()['draft']['definition']
        targets = {'model:' + provenance['source_id']}
        for dataset in self.pack.model_document()['datasets']:
            targets.add('table:' + dataset['name'])
            targets.update('field:' + dataset['name'] + '.' + field['name'] for field in dataset['fields'])
        targets.update('metric:' + metric['name'] for metric in definition['metrics'])
        targets.update('concept:' + concept for metric in definition['metrics'] for concept in metric.get('ontology_concepts', []))
        targets.update('concept:' + term['term'] for term in definition.get('glossary_terms', []) if isinstance(term.get('term'), str))
        for link in provenance['links']:
            if link['target'] not in targets:
                raise DemoError('Supporting material link references an unknown semantic target')
            if link['quote'] not in data.decode('utf-8'):
                raise DemoError('Supporting material quote does not occur in attachment content')
        return provenance

    @staticmethod
    def _table(connection):
        connection.execute('CREATE TABLE IF NOT EXISTS builder_documents (id TEXT PRIMARY KEY, reference TEXT NOT NULL, content BLOB NOT NULL)')

    def attach(self, filename: str, content: str, entity_links: list[dict] | None = None, supporting_material: dict | None = None) -> dict:
        if not isinstance(filename, str) or Path(filename).name != filename or len(filename) > 160 or Path(filename).suffix.lower() not in {'.txt', '.md'}:
            raise DemoError('Attachments require a local .txt or .md filename')
        if not isinstance(content, str):
            raise DemoError('Document content must be UTF-8 text')
        data = content.encode('utf-8')
        if not data or len(data) > MAX_DOCUMENT_BYTES or '\x00' in content:
            raise DemoError('Document content must be nonempty text below 256 KiB')
        reference = {'filename': filename, 'sha256': digest(data), 'snapshot_sha256': self.pack.fingerprint, 'entity_links': self.validate_links(entity_links or [])}
        if supporting_material is not None:
            reference['supporting_material'] = self.validate_supporting_material(supporting_material, data)
        reference['id'] = 'document-' + digest(canonical(reference))[:32]
        with self.workspace.connection(write=True) as connection:
            self._table(connection)
            connection.execute('INSERT OR IGNORE INTO builder_documents VALUES (?, ?, ?)', (reference['id'], json.dumps(reference), data))
        return reference

    def resolve(self, references: list[dict]) -> list[dict]:
        documents = []
        if not references:
            return documents
        with self.workspace.connection() as connection:
            if connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='builder_documents'").fetchone() is None:
                raise DemoError('Document attachment is not present in this workspace')
            for reference in references:
                row = connection.execute('SELECT reference, content FROM builder_documents WHERE id=?', (reference.get('id'),)).fetchone()
                if row is None or json.loads(row['reference']) != reference:
                    raise DemoError('Document reference does not match its immutable attachment')
                data = bytes(row['content'])
                if reference['snapshot_sha256'] != self.pack.fingerprint or digest(data) != reference['sha256']:
                    raise DemoError('Document attachment snapshot or checksum mismatch')
                self.validate_links(reference['entity_links'])
                semantic_links = [dict(link) | {'status': 'reviewer_linked', 'assertion_status': 'document_assertion'} for link in reference.get('supporting_material', {}).get('links', [])]
                documents.append(reference | {'semantic_links': semantic_links, 'content': data.decode('utf-8'), 'citation': 'attachment:' + reference['id'], 'origin': 'operator_attachment', 'assertion_status': 'document_assertion'})
        return documents

    def document_evidence(self, definition: dict):
        """Read document evidence independently of draft SQL validity."""
        warnings = []
        documents = []
        if not self.pack.documents:
            warnings.append('Serving snapshot contains no source documents')
        for document in self.pack.documents:
            metadata = json.loads(document.metadata_bytes)
            links = []
            table, value = metadata.get('entity_table'), metadata.get('entity_id')
            if table in self.rows and value:
                matches = []
                for column in self.rows[table][0] if self.rows[table] else []:
                    try:
                        matches.extend(self.validate_links([{'table': table, 'column': column, 'value': str(value)}]))
                    except DemoError:
                        continue
                if len(matches) == 1:
                    links = matches
                elif matches:
                    warnings.append(f'{document.document_id}: source entity key is ambiguous')
            if not links:
                warnings.append(f'{document.document_id}: source document has no verified entity link')
            documents.append({'id': document.document_id, 'filename': document.path, 'sha256': document.sha256, 'snapshot_sha256': self.pack.fingerprint, 'entity_links': links, 'link_status': 'proposed' if links else 'unmapped', 'content': document.content_bytes.decode('utf-8'), 'citation': 'document:' + document.document_id, 'origin': 'serving_document', 'assertion_status': 'document_assertion', 'source_metadata': metadata})
        documents.extend(self.resolve(definition.get('document_attachments', [])))
        for document in documents:
            if not document['entity_links']:
                warnings.append(f"{document['id']}: document has no entity links")
        return documents, sorted(set(warnings))

    def bundle(self, definition: dict, semantic_model: dict | None = None, version: str | None = None, reviews=None) -> dict:
        from .context import ContextDefinition
        if hasattr(definition, 'model_dump'):
            definition = definition.model_dump()
        semantic_model = semantic_model or self.workspace.build_model(ContextDefinition.model_validate(definition))
        warnings, fields, nodes, edges, entities, concepts = [], [], [], [], [], []
        proposal_provenance = definition.get('proposal_provenance')
        authored_provenance = ('draft_with_llm_provenance' if proposal_provenance and proposal_provenance.get('mode') == 'llm' else 'operator_authored')
        source_fields = {d['name'] + '.' + f['name']: f for d in self.pack.model_document()['datasets'] for f in d['fields']}
        foreign_fields = {j['from_field'] for j in definition.get('joins', [])}
        mapping_version = version or 'draft'
        for dataset in semantic_model['datasets']:
            table = dataset['name']
            rows = self.rows[table]
            candidates = [f['name'] for f in dataset['fields'] if rows and all(r[f['name']] for r in rows) and len({r[f['name']] for r in rows}) == len(rows)]
            key_candidates = [name for name in candidates if name == 'id' or name.endswith('_id')]
            nodes.append(GraphNode('Class', table, {'status': 'proposed', 'evidence': 'declared_serving_schema'}))
            nodes.append(GraphNode('OssieElement', 'dataset:' + table, {'kind': 'dataset', 'source_sha256': self.pack.fingerprint}))
            edges.append(GraphEdge('MAPS_TO', 'OssieElement', 'dataset:' + table, 'Class', table, {'status': 'proposed'}))
            if len(key_candidates) == 1:
                entities.append(EntityMapping(ossie_element=table, **{'class': table}, identifiers=Identifiers(primary=key_candidates)))
            else:
                warnings.append(f'{table}: no inferred identifier; explicit entity links remain available for verified unique keys')
            for field in dataset['fields']:
                name = table + '.' + field['name']
                meaning = definition.get('field_meanings', {}).get(name, '')
                source_field = source_fields[name]
                role = definition.get('field_roles', {}).get(name)
                role_source = authored_provenance
                if not role:
                    role = _ext(source_field).get('role')
                    role_source = 'declared_source_extension'
                if not role:
                    dimension = source_field.get('dimension')
                    role = ('foreign_key' if name in foreign_fields else 'identifier' if len(key_candidates) == 1 and field['name'] in key_candidates else 'time' if dimension and dimension.get('is_time') else 'dimension' if dimension else 'unknown')
                    role_source = 'structural_proposal'
                fields.append({'field': name, 'datatype': field['datatype'], 'role': role, 'role_provenance': role_source, 'meaning': meaning, 'meaning_status': authored_provenance if meaning else 'unknown', 'source': 'serving_schema'})
                if role == 'unknown':
                    warnings.append(f'{name}: field role is unknown')
                nodes.append(GraphNode('Attribute', name, {'datatype': field['datatype'], 'meaning': meaning, 'status': 'proposed'}))
                edges.append(GraphEdge('HAS_ATTRIBUTE', 'Class', table, 'Attribute', name))
        for metric in definition['metrics']:
            key = 'metric:' + metric['name']
            nodes.append(GraphNode('GlossaryTerm', key, {'description': metric['description'], 'expression': metric['expression'], 'status': 'proposed', 'concepts': metric.get('ontology_concepts', [])}))
            nodes.append(GraphNode('OssieElement', key, {'kind': 'metric', 'source_sha256': self.pack.fingerprint}))
            edges.append(GraphEdge('MAPS_TO', 'OssieElement', key, 'GlossaryTerm', key, {'status': 'proposed'}))
            for concept in metric.get('ontology_concepts', []):
                concept_key = 'concept:' + concept
                if not any(n.label == 'Class' and n.key == concept_key for n in nodes):
                    nodes.append(GraphNode('Class', concept_key, {'status': 'proposed', 'provenance': authored_provenance}))
                edges.append(GraphEdge('MAPS_TO', 'GlossaryTerm', key, 'Class', concept_key, {'status': 'proposed'}))
                concepts.append(ConceptMapping(glossary_term=key, **{'class': concept_key}, ossie_element=metric['name']))
        for join in definition.get('joins', []):
            # RANGE represents the declared attribute-to-class source relation.
            # It does not claim an inferred domain predicate or class hierarchy.
            edges.append(GraphEdge('RANGE', 'Attribute', join['from_field'], 'Class', join['to_field'].split('.')[0], {'join': join['name'], 'target_field': join['to_field'], 'cardinality': join.get('cardinality'), 'meaning': join['meaning'], 'status': 'proposed', 'provenance': authored_provenance}))
        for index, term in enumerate(definition.get('glossary_terms', [])):
            glossary_key = 'glossary:' + str(index)
            nodes.append(GraphNode('GlossaryTerm', glossary_key, {'term': term, 'status': 'proposed', 'provenance': authored_provenance}))
            for column in term.get('columns', []):
                column = column.removeprefix('source.')
                if column in source_fields:
                    edges.append(GraphEdge('MAPS_TO', 'GlossaryTerm', glossary_key, 'Attribute', column, {'status': 'proposed', 'provenance': authored_provenance}))
                else:
                    warnings.append(f'{glossary_key}: unknown glossary column {column}')
        graph = OntologyGraph(mapping_version, tuple(nodes), tuple(edges))
        mapping = SourceMapping(model=self.pack.entry.id, ontology_version=mapping_version, entities=entities, concepts=concepts, relationships=[RelationshipMapping(ossie_relationship=join['name'], edge='RANGE') for join in definition.get('joins', [])])
        documents, document_warnings = self.document_evidence(definition)
        warnings.extend(document_warnings)
        bundle = {'schema': 'helios.builder-artifacts.v1', 'version': mapping_version, 'snapshot_sha256': self.pack.fingerprint, 'definition_sha256': digest(canonical(definition)), 'semantic_layer': semantic_model, 'metadata': {'title': definition['title'], 'business_context': definition['description'], 'fields': fields, 'metrics': definition['metrics'], 'joins': definition.get('joins', []), 'tables': [{'name': t.name, 'row_count': t.row_count, 'sha256': digest(t.csv_bytes), 'authority': 'serving_source_fact'} for t in self.pack.tables]}, 'ontology': {'graph': json.loads(graph.canonical_json()), 'graph_sha256': graph.content_hash, 'source_mapping': mapping.model_dump(by_alias=True), 'mapping_status': 'proposed', 'entity_resolution': 'explicit_verified_keys_only'}, 'documents': documents, 'document_manifest': [{k: v for k, v in doc.items() if k != 'content'} for doc in documents], 'quality': {'warnings': sorted(set(warnings)), 'document_assertions_are_authoritative': False, 'review_status': 'requires_explicit_review'}, 'reviews': reviews or []}
        bundle['document_source_manifest_sha256'] = digest(self.pack.document_manifest_bytes)
        bundle['metadata']['proposal_provenance'] = proposal_provenance
        bundle['metadata']['authored_provenance'] = authored_provenance
        bundle['metadata']['dataset_meanings'] = definition.get('dataset_meanings', {})
        bundle['metadata']['glossary_terms'] = definition.get('glossary_terms', [])
        bundle['ontology']['scope'] = 'source_structure_proposal'
        bundle['artifact_sha256'] = digest(canonical(bundle))
        return bundle
