"""Generated artifacts preserve serving evidence and explicit attachment bindings."""
from pathlib import Path

import pytest

from helios_core.demo.builder_artifacts import BuilderArtifacts
from helios_core.demo.context import ContextWorkspace
from helios_core.demo.registry import DemoError, PackRegistry, digest

ROOT = Path(__file__).resolve().parents[3]


def artifacts(tmp_path, sector='manufacturing'):
    pack = PackRegistry(ROOT / 'apps/helios/demo-packs.json', ROOT / 'apps/helios-ds-generation/fixtures/sectors/v1').load(sector)
    workspace = ContextWorkspace(pack, tmp_path)
    return BuilderArtifacts(workspace)


def test_serving_document_bytes_and_proposed_mapping_are_exported(tmp_path):
    builder = artifacts(tmp_path)
    bundle = builder.bundle(builder.workspace.seed())
    assert bundle['documents']
    source = builder.pack.documents[0]
    document = bundle['documents'][0]
    assert document['content'].encode() == source.content_bytes
    assert document['sha256'] == digest(source.content_bytes)
    assert document['entity_links'][0]['value'] == 'SYN-WO000'
    assert document['link_status'] == 'proposed'
    assert bundle['ontology']['mapping_status'] == 'proposed'
    assert bundle['quality']['document_assertions_are_authoritative'] is False
    assert all('evaluation' not in doc['citation'] for doc in bundle['documents'])


def test_attachment_is_bound_to_content_entity_and_snapshot(tmp_path):
    builder = artifacts(tmp_path)
    reference = builder.attach('inspection.md', 'Operator reported tool wear.', [{'table': 'work_orders', 'column': 'work_order_id', 'value': 'SYN-WO000'}])
    assert builder.resolve([reference])[0]['content'] == 'Operator reported tool wear.'
    assert builder.resolve([reference])[0]['assertion_status'] == 'document_assertion'
    with pytest.raises(DemoError, match='immutable'):
        builder.resolve([reference | {'sha256': '0' * 64}])
    with pytest.raises(DemoError, match='does not exist'):
        builder.attach('other.txt', 'Unknown entity', [{'table': 'work_orders', 'column': 'work_order_id', 'value': 'missing'}])
    with pytest.raises(DemoError, match='unique'):
        builder.attach('other.txt', 'Not a key', [{'table': 'work_orders', 'column': 'status', 'value': 'completed'}])


def test_attachments_are_immutable_and_size_bounded(tmp_path):
    builder = artifacts(tmp_path)
    first = builder.attach('memo.txt', 'First assertion')
    second = builder.attach('memo.txt', 'Second assertion')
    assert first['id'] != second['id']
    assert builder.resolve([first])[0]['content'] == 'First assertion'
    with pytest.raises(DemoError):
        builder.attach('../memo.txt', 'escaped')
    with pytest.raises(DemoError):
        builder.attach('memo.md', 'x' * 262145)
    with pytest.raises(DemoError):
        builder.attach('memo.json', '{}')


def test_empty_source_document_pack_does_not_invent_documents(tmp_path):
    builder = artifacts(tmp_path, 'finance')
    bundle = builder.bundle(builder.workspace.seed())
    assert bundle['documents'] == []
    assert bundle['document_manifest'] == []


def test_version_artifacts_bind_attachment_bytes_and_definition(tmp_path):
    builder = artifacts(tmp_path)
    reference = builder.attach('claim.md', 'Document assertion', [{'table': 'work_orders', 'column': 'work_order_id', 'value': 'SYN-WO000'}])
    definition = builder.workspace.seed() | {'document_attachments': [reference]}
    bundle = builder.bundle(definition, version='v1')
    assert bundle['version'] == 'v1'
    assert bundle['documents'][-1]['sha256'] == reference['sha256']
    assert bundle['definition_sha256'] != builder.bundle(builder.workspace.seed())['definition_sha256']
    with builder.workspace.connection(write=True) as connection:
        connection.execute('UPDATE builder_documents SET content=? WHERE id=?', (b'tampered', reference['id']))
    with pytest.raises(DemoError, match='checksum'):
        builder.bundle(definition, version='v1')


@pytest.mark.parametrize('sector', ['finance', 'manufacturing', 'pharma', 'power'])
def test_graph_edges_and_mapping_refer_to_existing_nodes(tmp_path, sector):
    builder = artifacts(tmp_path, sector)
    definition = builder.workspace.seed()
    definition['metrics'][0]['ontology_concepts'] = ['Operator business concept']
    definition['field_roles'] = {next(iter(builder.workspace._fields)): 'attribute'}
    bundle = builder.bundle(definition)
    graph = bundle['ontology']['graph']
    nodes = {(node['label'], node['key']) for node in graph['nodes']}
    for edge in graph['edges']:
        assert (edge['from_label'], edge['from_key']) in nodes
        assert (edge['to_label'], edge['to_key']) in nodes
    assert ('Class', 'concept:Operator business concept') in nodes
    assert bundle['ontology']['source_mapping']['concepts']
    assert any(field['role_provenance'] == 'operator_authored' for field in bundle['metadata']['fields'])
    for mapping in bundle['ontology']['source_mapping']['relationships']:
        assert mapping['edge'] == 'RANGE'
        assert any(edge['properties'].get('join') == mapping['ossie_relationship'] for edge in graph['edges'])


@pytest.mark.parametrize('sector', ['finance', 'manufacturing', 'pharma', 'power'])
def test_llm_draft_provenance_citations_and_glossary_links(tmp_path, sector):
    builder = artifacts(tmp_path, sector)
    definition = builder.workspace.seed()
    field = next(iter(builder.workspace._fields))
    definition['proposal_provenance'] = {'mode': 'llm', 'provider': 'openai', 'model': 'gpt-4o', 'generated_at': '2026-10-12T00:00:00Z', 'snapshot_sha256': builder.pack.fingerprint}
    definition['field_roles'] = {field: 'attribute'}
    definition['field_meanings'] = {field: 'Proposed field meaning'}
    definition['glossary_terms'] = [{'term': 'Example concept', 'columns': ['source.' + field]}]
    definition['metrics'][0]['ontology_concepts'] = ['Example concept']
    definition['metrics'][0]['evidence_refs'] = ['document:' + document.document_id for document in builder.pack.documents]
    bundle = builder.bundle(definition)
    metadata_field = next(item for item in bundle['metadata']['fields'] if item['field'] == field)
    assert metadata_field['role_provenance'] == 'draft_with_llm_provenance'
    assert metadata_field['meaning_status'] == 'draft_with_llm_provenance'
    assert bundle['metadata']['proposal_provenance']['model'] == 'gpt-4o'
    citations = {document['citation'] for document in bundle['documents']}
    for metric in bundle['metadata']['metrics']:
        for reference in metric.get('evidence_refs', []):
            if reference.startswith('document:'):
                assert reference in citations
    graph = bundle['ontology']['graph']
    assert any(edge['from_key'] == 'glossary:0' and edge['to_key'] == field and edge['type'] == 'MAPS_TO' for edge in graph['edges'])
    for node in graph['nodes']:
        if node['key'] in {'glossary:0', 'concept:Example concept'}:
            assert node['properties']['provenance'] == 'draft_with_llm_provenance'


def test_legacy_reference_serializer_preserves_exact_hash_and_resolution(tmp_path):
    from helios_core.demo.context import DocumentAttachment
    builder = artifacts(tmp_path)
    reference = builder.attach('legacy.md', 'Legacy document')
    assert 'supporting_material' not in reference
    assert DocumentAttachment.model_validate(reference).model_dump() == reference
    assert builder.resolve([DocumentAttachment.model_validate(reference).model_dump()])[0]['content'] == 'Legacy document'


def test_supporting_material_provenance_is_immutable_and_versioned(tmp_path):
    from helios_core.demo.context import DocumentAttachment
    builder = artifacts(tmp_path)
    content = 'Operator asserted tool wear.'
    target = 'metric:' + builder.workspace.seed()['metrics'][0]['name']
    provenance = {'document_id': 'shared-memo', 'revision': 1, 'sha256': digest(content.encode()),
        'source_id': builder.pack.entry.id, 'links': [{'chunk_id': 'chunk-1', 'location': 'Paragraph 1',
        'quote': 'tool wear', 'target': target, 'reviewer': 'Operator', 'note': 'Definition context'}]}
    reference = builder.attach('memo.md', content, [], supporting_material=provenance)
    assert DocumentAttachment.model_validate(reference).model_dump() == reference
    document = builder.resolve([reference])[0]
    assert document['semantic_links'][0]['target'] == target
    assert document['assertion_status'] == 'document_assertion'
    definition = builder.workspace.seed() | {'document_attachments': [reference]}
    bundle = builder.bundle(definition, version='v1')
    assert bundle['documents'][-1]['supporting_material'] == provenance
    assert bundle['document_manifest'][-1]['semantic_links'][0]['target'] == target
    modified = reference | {'supporting_material': provenance | {'revision': 2}}
    with pytest.raises(DemoError, match='immutable'):
        builder.resolve([modified])
    # Resolving a saved reference does not depend on targets in the latest draft.
    builder.workspace.view = lambda: (_ for _ in ()).throw(AssertionError('Unexpected draft lookup'))
    assert builder.resolve([reference])[0]['content'] == content


@pytest.mark.parametrize('change', [
    {'sha256': 'invalid'}, {'source_id': 'invalid/source'},
    {'links': [{'chunk_id': 'chunk-1', 'location': 'Paragraph 1', 'quote': 'tool wear',
        'target': 'metric:missing', 'reviewer': 'Operator', 'note': ''}]},
    {'links': [{'chunk_id': 'chunk-1', 'location': 'Paragraph 1', 'quote': 'invented quote',
        'target': 'table:work_orders', 'reviewer': 'Operator', 'note': ''}]},
])
def test_supporting_material_rejects_wrong_content_source_target_or_quote(tmp_path, change):
    builder = artifacts(tmp_path)
    content = 'Operator asserted tool wear.'
    provenance = {'document_id': 'memo', 'revision': 1, 'sha256': digest(content.encode()),
        'source_id': builder.pack.entry.id, 'links': []} | change
    with pytest.raises(DemoError):
        builder.attach('memo.md', content, [], supporting_material=provenance)


def test_added_connection_identity_and_original_upload_digest_are_preserved(tmp_path):
    builder = artifacts(tmp_path)
    excerpt = 'Exported supporting excerpt with reviewed claim.'
    original_digest = digest(b'Original uploaded PDF bytes')
    metadata = {'document_id': 'shared-doc', 'revision': 1, 'sha256': original_digest,
        'source_id': 'connection-added-123', 'links': [{'chunk_id': 'chunk-1', 'location': 'Page 1',
        'quote': 'reviewed claim', 'target': 'model:connection-added-123', 'reviewer': 'Operator', 'note': ''}]}
    reference = builder.attach('excerpt.md', excerpt, [], supporting_material=metadata)
    assert reference['sha256'] == digest(excerpt.encode())
    assert reference['supporting_material']['sha256'] == original_digest
    assert reference['supporting_material']['source_id'] != builder.pack.entry.id
    assert builder.resolve([reference])[0]['semantic_links'][0]['target'] == 'model:connection-added-123'
    wrong_target = metadata | {'links': [metadata['links'][0] | {'target': 'model:another-connection'}]}
    with pytest.raises(DemoError, match='unknown semantic target'):
        builder.attach('excerpt.md', excerpt, [], supporting_material=wrong_target)
