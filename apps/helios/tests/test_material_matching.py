"""Match business evidence without allowing generic provenance fields to dominate."""
import base64
from pathlib import Path

import pytest

from apps.helios.console.demo_hub import DemoHub
from helios_core.demo.materials import MaterialLibrary, MaterialSuggest, MaterialUpload
from helios_core.demo.registry import PackRegistry
from helios_core.demo.runtime import DemoRuntime

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def library(tmp_path):
    registry = PackRegistry(ROOT / 'apps/helios/demo-packs.json',
                            ROOT / 'apps/helios-ds-generation/fixtures/sectors/v1')
    hub = DemoHub(registry, tmp_path, DemoRuntime(registry.load('power'), tmp_path))
    yield MaterialLibrary(hub)
    hub.close()


def match(library, text):
    item = library.upload(MaterialUpload(filename='evidence.md',
        content_base64=base64.b64encode(text.encode()).decode()))
    return library.suggest(item['document_id'], MaterialSuggest(revision=item['revision']))


def test_trial_brief_matches_population_meaning_instead_of_source_keys(library):
    text = (ROOT / 'apps/helios-ds-generation/fixtures/sectors/v1/pharma_intelligence'
            '/serving/documents/trial_denominators.md').read_text()
    item = match(library, text)
    links = [link for link in item['links'] if link['source'] == 'pharma_intelligence']
    assert links
    assert any(link['target'] == 'field:trial_results.denominator_count' for link in links)
    assert all(not link['target'].endswith('.source_id') for link in links)
    assert all(link['quote'] in next(c['text'] for c in item['chunks'] if c['id'] == link['chunk_id'])
               for link in links)


def test_endpoint_evidence_matches_business_metric_or_concept(library):
    item = match(library,
        'Published objective response rate without prior HER2 ADC: 75% in the 71-person cohort, '
        '95% confidence interval 63-83. Do not pool endpoint percentages across cohorts.')
    links = [link for link in item['links'] if link['source'] == 'pharma_intelligence']
    assert any(link['target'] in ('metric:no_prior_adc_orr_percent', 'concept:ObjectiveResponseRate')
               for link in links)
    assert all(not link['target'].endswith('.source_id') for link in links)


def test_explicit_provenance_reference_remains_matchable(library):
    item = match(library,
        'trial_cohorts.source_id records the source for the cohort denominator. '
        'This source reference identifies the source document used for the cohort.')
    assert any(link['source'] == 'pharma_intelligence'
               and link['target'] == 'field:trial_cohorts.source_id' for link in item['links'])
