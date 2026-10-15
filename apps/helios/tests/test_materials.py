"""Supporting material revisions require evidence, review, and current model bindings."""
import base64
import copy
import json
from pathlib import Path

import pytest

from apps.helios.console.demo_hub import DemoHub
from helios_core.demo.builder_artifacts import BuilderArtifacts
from helios_core.demo.context import ContextDefinition
from helios_core.demo.materials import (
    MaterialLibrary, MaterialUpload, MaterialAnalyze, MaterialSuggest, MaterialReview, MaterialApply,
)
from helios_core.demo.registry import DemoError, PackRegistry
from helios_core.demo.runtime import DemoRuntime

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def library(tmp_path):
    registry = PackRegistry(ROOT / 'apps/helios/demo-packs.json', ROOT / 'apps/helios-ds-generation/fixtures/sectors/v1')
    hub = DemoHub(registry, tmp_path, DemoRuntime(registry.load('power'), tmp_path))
    result = MaterialLibrary(hub)
    yield result
    hub.close()


def upload(library, text='Total planned maintenance minutes; not observed downtime.', document_id=None):
    return library.upload(MaterialUpload(filename='policy.md', content_base64=base64.b64encode(text.encode()).decode(), document_id=document_id))


def suggestions(library, item, **kwargs):
    return library.suggest(item['document_id'], MaterialSuggest(revision=item['revision'], **kwargs))


def source_link(item, source='manufacturing'):
    return next(link for link in item['links'] if link['source'] == source)


def approve(library, item, link):
    return library.review(item['document_id'], MaterialReview(revision=item['revision'], link_ids=[link['id']], decision='approved', reviewer='Test reviewer', note='Confirmed document scope and model meaning.'))


def application(item, link, revision=0, source=None):
    return MaterialApply(revision=item['revision'], link_ids=[link['id']], source=source or link['source'], expected_revision=revision)


class EvidenceModel:
    provider = 'test-only'
    model = 'exact-quotes'

    def __init__(self, hallucinate=False):
        self.calls = []
        self.hallucinate = hallucinate

    def complete(self, system, user):
        payload = json.loads(user)
        self.calls.append(payload)
        return json.dumps({'summary': 'Source evidence.', 'claims': [
            {'chunk_id': c['id'], 'quote': 'invented claim without evidence' if self.hallucinate else c['text'][:40],
             'statement': 'The source states its policy.', 'kind': 'rule'} for c in payload['chunks']]})


def test_revisions_keep_historical_content_and_reject_duplicates(library):
    first = upload(library)
    historical = copy.deepcopy(library.detail(first['document_id'], 1))
    with pytest.raises(DemoError, match='already the latest'):
        upload(library, document_id=first['document_id'])
    second = upload(library, 'Changed maintenance policy.', first['document_id'])
    assert second['revision'] == 2
    old = library.detail(first['document_id'], 1)
    assert old['sha256'] == historical['sha256']
    assert old['chunks'] == historical['chunks']
    assert old['analysis'] is None and old['links'] == []
    assert old['latest_revision'] == 2
    assert library.catalog()['items'][0]['revision'] == 2
    with pytest.raises(DemoError, match='newer document revision'):
        suggestions(library, first)
    with pytest.raises(DemoError, match='does not exist'):
        upload(library, document_id='missing')


def test_analysis_covers_all_batches_and_rejects_hallucinated_quotes_atomically(library):
    item = upload(library, ('Policy requires planned maintenance. ' * 500))
    assert item['chunk_count'] > 6
    model = EvidenceModel()
    analyzed = library.analyze(item['document_id'], MaterialAnalyze(revision=1), model)
    assert analyzed['analysis']['covered_chunks'] == item['chunk_count']
    assert len(model.calls) > 1
    expected = {c['id'] for c in item['chunks']}
    assert {c['chunk_id'] for c in analyzed['analysis']['claims']} == expected
    assert {c['id'] for call in model.calls for c in call['chunks']} == expected
    with pytest.raises(DemoError, match='unsupported citation'):
        library.analyze(item['document_id'], MaterialAnalyze(revision=1), EvidenceModel(True))
    assert library.detail(item['document_id'])['analysis'] == analyzed['analysis']
    with pytest.raises(DemoError, match='Configure'):
        library.analyze(item['document_id'], MaterialAnalyze(revision=1), None)


@pytest.mark.parametrize('source,text', [
    ('manufacturing', 'Total planned maintenance minutes; not observed downtime.'),
    ('finance', 'Settled sender outflow SGD fixed synthetic FX total amount.'),
])
def test_keyword_matches_have_exact_chunk_citations(library, source, text):
    item = suggestions(library, upload(library, text))
    link = source_link(item, source)
    chunk = next(c for c in item['chunks'] if c['id'] == link['chunk_id'])
    assert link['quote'] in chunk['text']
    assert link['location'] == chunk['location']
    assert link['status'] == 'suggested'
    assert item['matching']['method'] == 'keyword'


def test_apply_requires_review_and_draft_compare_and_swap(library):
    item = suggestions(library, upload(library))
    link = source_link(item)
    with pytest.raises(DemoError, match='approved links'):
        library.apply(item['document_id'], application(item, link))
    reviewed = approve(library, item, link)
    with pytest.raises(DemoError, match='draft changed'):
        library.apply(item['document_id'], application(item, link, revision=12))
    applied = library.apply(item['document_id'], application(item, link))
    workspace = library.hub.runtime('manufacturing').workspace
    draft = workspace.view()['draft']
    assert draft['revision'] == 1
    reference = draft['definition']['document_attachments'][0]
    assert reference['supporting_material']['document_id'] == item['document_id']
    assert reference['supporting_material']['revision'] == 1
    assert applied['usage'][0]['draft_revision'] == 1
    resolved = BuilderArtifacts(workspace).resolve([reference])[0]
    assert item['chunks'][0]['text'] in resolved['content']
    # The material review freezes its evidence, while model approval remains separate.
    assert workspace.view()['versions'] == []
    with pytest.raises(DemoError, match='frozen'):
        library.analyze(item['document_id'], MaterialAnalyze(revision=1), EvidenceModel())
    with pytest.raises(DemoError, match='recorded decision'):
        library.review(item['document_id'], MaterialReview(revision=1, link_ids=[link['id']], decision='rejected', reviewer='Other reviewer', note='Changed decision'))
    rematched = suggestions(library, reviewed)
    assert next(l for l in rematched['links'] if l['id'] == link['id'])['status'] == 'approved'


def test_stale_target_blocks_review_and_apply(library):
    item = suggestions(library, upload(library))
    link = source_link(item)
    approve(library, item, link)
    workspace = library.hub.runtime('manufacturing').workspace
    definition = copy.deepcopy(workspace.view()['draft']['definition'])
    definition['description'] += ' Changed scope.'
    workspace.save(0, ContextDefinition.model_validate(definition))
    assert next(l for l in library.detail(item['document_id'])['links'] if l['id'] == link['id'])['stale']
    with pytest.raises(DemoError, match='target model changed'):
        approve(library, item, link)
    with pytest.raises(DemoError, match='target model changed'):
        library.apply(item['document_id'], application(item, link, revision=1))


def test_unknown_selection_and_cross_source_apply_are_rejected(library):
    item = suggestions(library, upload(library))
    link = source_link(item)
    with pytest.raises(DemoError, match='unknown link'):
        library.review(item['document_id'], MaterialReview(revision=1, link_ids=[link['id'], 'missing'], decision='approved', reviewer='Test', note='Checked'))
    assert source_link(library.detail(item['document_id']))['status'] == 'suggested'
    approve(library, item, link)
    with pytest.raises(DemoError, match='one target model'):
        library.apply(item['document_id'], application(item, link, source='finance'))
    assert library.hub.runtime('finance').workspace.view()['draft']['revision'] == 0


class Vectors:
    model = 'test-vector-v1'

    def __init__(self, fingerprint='test-v1'):
        self.fingerprint = fingerprint
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return [[1.0, 1.0 + (len(text) % 17) / 17.0, 0.5] for text in texts]


def test_embeddings_cache_by_content_and_provider_fingerprint(library):
    item = upload(library)
    payload = MaterialSuggest(revision=1, use_embeddings=True)
    vectors = Vectors()
    first = library.suggest(item['document_id'], payload, vectors)
    assert first['matching']['method'] == 'keyword+embedding'
    assert vectors.calls
    count = len(vectors.calls)
    repeated = library.suggest(item['document_id'], payload, vectors)
    assert len(vectors.calls) == count
    assert [l['id'] for l in repeated['links']] == [l['id'] for l in first['links']]
    changed = Vectors('test-v2')
    rebuilt = library.suggest(item['document_id'], payload, changed)
    assert changed.calls and rebuilt['matching']['fingerprint'] == 'test-v2'
    with pytest.raises(DemoError, match='configure an embedding'):
        library.suggest(item['document_id'], payload)


def test_added_local_connection_can_receive_reviewed_shared_evidence(library):
    connection = library.hub.connections.create({'name': 'Another manufacturing plant', 'kind': 'local', 'config': {'pack_id': 'manufacturing'}})
    # Model titles make this connection a distinct lexical target.
    workspace = library.hub.runtime(connection['id']).workspace
    definition = copy.deepcopy(workspace.view()['draft']['definition'])
    definition['title'] = 'Dedicated plant maintenance'
    workspace.save(0, ContextDefinition.model_validate(definition))
    item = suggestions(library, upload(library, 'Dedicated plant maintenance planned minutes downtime.'))
    link = source_link(item, connection['id'])
    approve(library, item, link)
    library.apply(item['document_id'], application(item, link, revision=1))
    attachment = workspace.view()['draft']['definition']['document_attachments'][0]
    assert attachment['supporting_material']['source_id'] == connection['id']
    assert library.hub.runtime('manufacturing').workspace.view()['draft']['revision'] == 0


def test_new_document_revision_preserves_published_supporting_artifact(library):
    from apps.helios.tests.test_demo_context import definition, validated, review_request, publish
    item = suggestions(library, upload(library))
    link = source_link(item)
    approve(library, item, link)
    library.apply(item['document_id'], application(item, link))
    runtime = library.hub.runtime('manufacturing')
    attachments = copy.deepcopy(runtime.workspace.view()['draft']['definition']['document_attachments'])
    value = definition(runtime.workspace) | {'document_attachments': attachments}
    validated(runtime, value)
    runtime.workspace.review(review_request(runtime))
    publish(runtime)
    release = copy.deepcopy(runtime.workspace.release('v1'))
    document = next(d for d in release['artifacts']['documents'] if d.get('supporting_material'))
    assert document['supporting_material']['revision'] == 1
    revised = upload(library, 'Maintenance policy changed in revision two.', item['document_id'])
    assert revised['revision'] == 2
    assert runtime.workspace.release('v1') == release
    assert BuilderArtifacts(runtime.workspace).resolve(attachments)[0]['content'] == document['content']
    old = library.detail(item['document_id'], 1)
    assert source_link(old)['status'] == 'approved'
    assert old['usage'][0]['revision'] == 1
    with pytest.raises(DemoError, match='newer document revision'):
        library.apply(item['document_id'], application(item, link, revision=runtime.workspace.view()['draft']['revision']))


def test_one_section_can_suggest_multiple_models_without_one_model_dominating(library):
    item = suggestions(library, upload(library,
        'The planned_downtime_minutes metric sums work_orders.downtime_minutes. '
        'Planned maintenance time is not observed downtime. '
        'Finance settled sender outflow SGD uses settled transaction amounts and fixed synthetic FX rates.'))
    assert len(item['chunks']) == 1
    assert {'manufacturing', 'finance'} <= {l['source'] for l in item['links']}
    for source in {l['source'] for l in item['links']}:
        assert sum(l['source'] == source for l in item['links']) <= 2


def test_exclusion_claims_retain_exact_source_and_invalid_kinds_fail(library):
    class Model(EvidenceModel):
        kind = 'exclusion'
        def complete(self, system, user):
            response = json.loads(super().complete(system, user))
            response['claims'][0]['kind'] = self.kind
            return json.dumps(response)
    item = upload(library)
    model = Model()
    result = library.analyze(item['document_id'], MaterialAnalyze(revision=1), model)
    assert result['analysis']['claims'][0]['kind'] == 'exclusion'
    model.kind = 'executed_fact'
    with pytest.raises(DemoError, match='invalid evidence'):
        library.analyze(item['document_id'], MaterialAnalyze(revision=1), model)
    assert library.detail(item['document_id'])['analysis'] == result['analysis']


def test_embedding_dimension_change_clears_namespace_for_retry(library):
    class ChangingEmbedder:
        fingerprint = 'dimension-test'
        model = 'test-embedding'
        width = 2
        def embed(self, texts):
            return [[1.0] * self.width for _ in texts]
    client = ChangingEmbedder()
    library._vectors(client, ['first'])
    client.width = 3
    with pytest.raises(DemoError, match='dimensions changed'):
        library._vectors(client, ['first', 'second'])
    assert library._vectors(client, ['first', 'second']) == [[1.0]*3, [1.0]*3]
