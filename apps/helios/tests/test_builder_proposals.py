"""Proposal generation stages source-grounded candidates without changing drafts."""
import pytest
from apps.helios.tests.test_demo_context import pack
from helios_core.demo.context import ContextDefinition, ContextWorkspace
from helios_core.demo.proposals import ProposalWorkspace
from helios_core.demo.registry import DemoError


def test_evidence_stages_and_apply_checks_revision(tmp_path):
    ws = ContextWorkspace(pack(), tmp_path)
    proposals = ProposalWorkspace(ws)
    before = ws.view()['draft']
    candidate = proposals.generate(0)
    assert candidate['mode'] == 'evidence'
    assert candidate['label'] == 'Deterministic source evidence draft'
    assert ws.view()['draft'] == before
    assert candidate['definition']['metrics'][0]['reference_sql'] == ''
    assert proposals.apply(candidate['proposal_id'], 0)['draft']['revision'] == 1
    with pytest.raises(DemoError):
        proposals.apply(candidate['proposal_id'], 0)


class FakeLLM:
    provider = 'fake'
    model = 'test'
    calls = 0
    def complete_json(self, system, user):
        import json
        self.calls += 1
        data = json.loads(user.split('\n\nReturn')[0])
        if 'fact_tables' in data:
            fact = data['fact_tables'][0]
            col = fact['measures'][0]['column']
            return {'metrics': [{'name': 'Proposed total', 'description': 'Source measure total',
                'dataset': fact['table'], 'expression': f'SUM({col})', 'confidence': .8}]}
        return {'name': 'Source table', 'kind': 'fact', 'description': 'Source table',
            'fields': [{'column': c['column'], 'role': 'measure' if c['type'].lower().startswith(('decimal', 'double', 'float', 'int', 'bigint')) else 'dimension',
                'description': 'Source field meaning', 'confidence': .8} for c in data['columns']]}


def test_llm_runs_proposer_and_clears_reference_sql(tmp_path):
    ws = ContextWorkspace(pack(), tmp_path)
    llm = FakeLLM()
    candidate = ProposalWorkspace(ws).generate(0, 'llm', llm)
    assert llm.calls > 1
    assert ws.view()['draft']['revision'] == 0
    metric = next(m for m in candidate['definition']['metrics'] if m['name'] == 'proposed_total')
    assert metric['reference_sql'] == ''
    assert metric['confidence'] == .8
    ws.build_model(ContextDefinition.model_validate(candidate['definition']))


def test_filters_compile_and_metadata_exports(tmp_path):
    ws = ContextWorkspace(pack(), tmp_path)
    definition = ContextDefinition.model_validate(ws.seed())
    metric = definition.metrics[0]
    import sqlglot
    from sqlglot import exp
    column = next(sqlglot.parse_one(metric.expression).find_all(exp.Column))
    filters = [__import__('helios_core.demo.context', fromlist=['MetricFilter']).MetricFilter(field=f'{column.table}.{column.name}', op='>', value=0)]
    metric = metric.model_copy(update={'filters': filters, 'synonyms': ['example synonym'], 'reference_sql': 'SECRET_REFERENCE'})
    definition = definition.model_copy(update={'metrics': [metric]})
    document = ws.build_model(definition)
    from helios_core.ossie.model import SemanticModel
    assert 'CASE' in ws.compile_metric(SemanticModel(document), metric).sql.upper()
    assert 'SECRET_REFERENCE' not in str(document)
    assert document['metrics'][0]['ai_context']['synonyms'] == ['example synonym']


@pytest.mark.parametrize('sector', ['power', 'finance', 'manufacturing', 'pharma'])
def test_pipeline_across_sectors(tmp_path, sector):
    ws = ContextWorkspace(pack(sector), tmp_path)
    candidate = ProposalWorkspace(ws).generate(0, 'llm', FakeLLM())
    assert candidate['proposer_output']['datasets']
    assert candidate['proposer_output']['relationships']
    assert candidate['definition']['field_roles']
    assert candidate['definition']['dataset_meanings']
    assert ws.view()['draft']['revision'] == 0


class HostileLLM(FakeLLM):
    def __init__(self, invented_evidence=False):
        self.invented_evidence = invented_evidence
    def complete_json(self, system, user):
        result = super().complete_json(system, user)
        if 'metrics' in result:
            metric = result['metrics'][0]
            metric.update(reference_sql='SELECT evaluation_answer', filters=[{'field': 'invented.key', 'op': '=', 'value': 1}],
                synonyms=['Source synonym'], inclusion_rules=['Include approved source events'],
                assumptions=['Reporting period unknown'], owner='', rationale='Source column measure',
                evidence_refs=['invented:evidence'] if self.invented_evidence else [], ontology_concepts=[])
        return result


def test_untrusted_reference_and_filters_never_execute(tmp_path):
    ws = ContextWorkspace(pack(), tmp_path)
    proposal = ProposalWorkspace(ws).generate(0, 'llm', HostileLLM())
    metric = next(m for m in proposal['definition']['metrics'] if m['name'] == 'proposed_total')
    assert metric['reference_sql'] == ''
    assert metric['filters'] == []
    assert metric['inclusion_rules'] == ['Include approved source events']
    assert metric['synonyms'] == ['Source synonym']


def test_invented_evidence_preserves_draft(tmp_path):
    ws = ContextWorkspace(pack(), tmp_path)
    before = ws.view()['draft']
    with pytest.raises(DemoError, match='evidence'):
        ProposalWorkspace(ws).generate(0, 'llm', HostileLLM(True))
    assert ws.view()['draft'] == before


class QualifiedLLM(FakeLLM):
    def __init__(self, database='source'):
        self.database = database
    def complete_json(self, system, user):
        result = super().complete_json(system, user)
        if 'metrics' in result:
            metric = result['metrics'][0]
            import sqlglot
            from sqlglot import exp
            column = next(sqlglot.parse_one(metric['expression']).find_all(exp.Column))
            table = metric['dataset'].removeprefix('source.')
            metric['expression'] = f'SUM({self.database}.{table}.{column.name})'
        return result


def test_bound_source_qualification_normalizes_and_unknown_database_rejects(tmp_path):
    ws = ContextWorkspace(pack(), tmp_path)
    proposal = ProposalWorkspace(ws).generate(0, 'llm', QualifiedLLM())
    assert 'source.' not in proposal['definition']['metrics'][0]['expression']
    with pytest.raises(DemoError, match='dataset'):
        ProposalWorkspace(ws).generate(0, 'llm', QualifiedLLM('foreign'))
    assert ws.view()['draft']['revision'] == 0


class NoFactsLLM(FakeLLM):
    def complete_json(self, system, user):
        result = super().complete_json(system, user)
        if 'kind' in result:
            result['kind'] = 'dimension'
            for field in result['fields']:
                field['role'] = 'attribute'
        return result


def test_pharma_declared_metric_table_is_permitted_despite_role_uncertainty(tmp_path):
    ws = ContextWorkspace(pack('pharma'), tmp_path)
    proposal = ProposalWorkspace(ws).generate(0, 'llm', NoFactsLLM())
    assert proposal['proposer_output']['metrics']
    assert all(ds['kind'] == 'dimension' for ds in proposal['proposer_output']['datasets'])
    source = ws.seed()['metrics'][0]
    retained = next(m for m in proposal['definition']['metrics'] if m['name'] == source['name'])
    assert retained['expression'] == source['expression']
    assert retained['confidence'] is None
    assert 'Declared source candidate' in retained['rationale']
    assert any('not reproduced exactly' in warning for warning in proposal['warnings'])


class StringMetadataLLM(HostileLLM):
    def complete_json(self, system, user):
        result = super().complete_json(system, user)
        if 'metrics' in result:
            result['metrics'][0].update(assumptions='Reporting period needs review.',
                synonyms='Source total', inclusion_rules='Source records only')
        return result


def test_string_metadata_normalizes_without_character_expansion(tmp_path):
    ws = ContextWorkspace(pack(), tmp_path)
    proposal = ProposalWorkspace(ws).generate(0, 'llm', StringMetadataLLM())
    metric = next(m for m in proposal['definition']['metrics'] if m['name'] == 'proposed_total')
    assert metric['assumptions'][0] == 'Reporting period needs review.'
    assert len(metric['assumptions']) == 2
    assert metric['synonyms'] == ['Source total']
    assert metric['inclusion_rules'] == ['Source records only']
    assert any('normalized assumptions string' in warning for warning in proposal['warnings'])


def test_manufacturing_attached_document_reaches_bounded_proposer_prompt(tmp_path):
    import json
    from helios_core.demo.builder_artifacts import BuilderArtifacts
    ws = ContextWorkspace(pack('manufacturing'), tmp_path)
    reference = BuilderArtifacts(ws).attach('operator-rule.md', 'UNIQUE_ATTACHMENT_RULE: use source facts only.')
    definition = ws.seed()
    definition['document_attachments'] = [reference]
    ws.save(0, ContextDefinition.model_validate(definition))

    class RecordingLLM(FakeLLM):
        prompts = []
        def complete_json(self, system, user):
            self.prompts.append((system, user))
            return super().complete_json(system, user)

    llm = RecordingLLM()
    proposal = ProposalWorkspace(ws).generate(1, 'llm', llm)
    table_prompts = [(system, json.loads(user.split('\n\nReturn')[0]))
                     for system, user in llm.prompts if 'row_count' in user]
    assert table_prompts
    for system, payload in table_prompts:
        assert 'untrusted evidence' in system
        assert any('UNIQUE_ATTACHMENT_RULE' in doc['text'] for doc in payload['source_documents'])
        assert len(payload['source_documents']) <= 5
        assert all(len(doc['text']) <= 1500 for doc in payload['source_documents'])
    coverage = proposal['evidence']['document_coverage']
    assert 'attachment:' + reference['id'] in coverage['selected_citations']
    assert coverage['total_count'] == len(ws.pack.documents) + 1
    assert any('Document evidence covers' in warning for warning in proposal['warnings'])


def test_exact_formula_preserves_declared_business_qualifier_and_identity(tmp_path):
    ws = ContextWorkspace(pack('manufacturing'), tmp_path)
    source = ws.seed()['metrics'][0]

    class ExactFormulaLLM(FakeLLM):
        def complete_json(self, system, user):
            result = super().complete_json(system, user)
            if 'metrics' in result:
                import sqlglot
                from sqlglot import exp
                dataset = next(sqlglot.parse_one(source['expression']).find_all(exp.Column)).table
                result['metrics'] = [{'name': 'Generic total downtime', 'description': 'All downtime events',
                    'dataset': 'source.' + dataset, 'expression': source['expression'], 'confidence': .9,
                    'synonyms': ['Downtime total']}]
            return result

    proposal = ProposalWorkspace(ws).generate(0, 'llm', ExactFormulaLLM())
    metric = next(m for m in proposal['definition']['metrics'] if m['name'] == source['name'])
    assert metric['description'] == source['description']
    assert metric['id'] == source['id']
    assert metric['unit'] == source['unit']
    assert metric['synonyms'] == ['Downtime total']
    assert proposal['proposer_output']['metrics'][0]['description'] == 'All downtime events'
    assert any('preserved declared name and business description' in warning for warning in proposal['warnings'])
