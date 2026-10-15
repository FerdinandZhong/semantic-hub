"""Build a bounded public-fact pack from a checked, offline curation snapshot.

This generator does not download sources, infer trial outcomes, or create patients.
Run with --facts and --output; it writes only the pharma_intelligence subdirectory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

PACK_ID = 'pharma_intelligence'
TITLE = 'Pharmaceutical Industry Intelligence & New Drug Analysis'

# name: (datatype, meaning). Explicit schemas avoid CSV type inference.
SCHEMAS = {
    'source_documents': {
        'source_id': ('String', 'Stable source reference identifier; not a model review decision.'),
        'title': ('String', 'Publisher document title.'),
        'publisher': ('String', 'Organisation publishing the evidence.'),
        'publication_period': ('String', 'Report edition or original approval scope; distinct from observation period.'),
        'source_url': ('String', 'Original public source URL.'),
        'sha256': ('String', 'SHA256 of the exact downloaded source bytes.'),
        'retrieved_date': ('Date', 'Date of source capture, not the date of the reported event.'),
    },
    'drugs': {
        'drug_id': ('String', 'Local stable identifier derived from the FDA trade name.'),
        'brand_name': ('String', 'FDA-listed drug trade name; combination products remain one listed drug.'),
        'active_ingredient': ('String', 'Active ingredient text as published; combinations are not split into approval events.'),
        'source_id': ('String', 'Source for the product fact.'),
    },
    'approval_events': {
        'approval_id': ('String', 'One row in the FDA CDER 2025 novel-drug list.'),
        'drug_id': ('String', 'Drug covered by this original approval event.'),
        'approval_date': ('Date', 'Original FDA approval date in the selected 2025 list.'),
        'regulator': ('String', 'Regulator and centre; these records cover FDA CDER only.'),
        'jurisdiction': ('String', 'Approval jurisdiction; not a worldwide approval claim.'),
        'approved_use': ('String', 'Published use at original approval; not a current prescribing recommendation.'),
        'source_id': ('String', 'Source for this approval event.'),
        'source_locator': ('String', 'Source table and row locator.'),
        'source_quality_note': ('String', 'Unresolved publisher text issue; an empty value is not independent clinical verification.'),
    },
    'trials': {
        'trial_id': ('String', 'Public trial registry identifier.'),
        'drug_id': ('String', 'Drug evaluated in the selected approval evidence.'),
        'trial_name': ('String', 'Trial name in the FDA snapshot.'),
        'sponsor': ('String', 'Company identified in the FDA snapshot.'),
        'design': ('String', 'Detailed source design; see source_quality_note for conflicting summary text.'),
        'population_description': ('String', 'Bounded original-approval efficacy population, not all trial enrollment.'),
        'evidence_patients': ('Integer', '105 patients in this FDA efficacy evidence subset, not patient-level records.'),
        'source_id': ('String', 'Source for the trial evidence.'),
        'source_locator': ('String', 'Source section used for curation.'),
        'source_quality_note': ('String', 'Unresolved design wording or scope issue requiring source review.'),
    },
    'trial_cohorts': {
        'cohort_id': ('String', 'Stable key for one disjoint prior-treatment cohort.'),
        'trial_id': ('String', 'Trial containing this approval evidence cohort.'),
        'prior_her2_adc': ('String', 'Yes or No for prior HER2-targeted antibody-drug conjugate treatment.'),
        'patient_count': ('Integer', 'Cohort denominator for ORR; not the responder denominator used for DOR.'),
        'source_id': ('String', 'Source for the cohort denominator.'),
        'source_locator': ('String', 'Table header establishing the denominator.'),
    },
    'trial_results': {
        'result_id': ('String', 'One trial cohort and endpoint result.'),
        'cohort_id': ('String', 'Cohort to which the endpoint applies.'),
        'endpoint': ('String', 'ORR or DOR_GE_6_MONTHS; these endpoints have different denominators.'),
        'value': ('Decimal', 'Published percentage; never sum or take an unweighted average across endpoints or cohorts.'),
        'unit': ('String', 'Percent, represented on a 0 to 100 scale.'),
        'denominator_count': ('Integer', 'ORR uses all cohort patients; DOR uses responders (53 or 15).'),
        'ci_lower': ('Decimal', 'Published lower 95% confidence bound for ORR; null when not reported.'),
        'ci_upper': ('Decimal', 'Published upper 95% confidence bound for ORR; null when not reported.'),
        'source_id': ('String', 'Source for the reported endpoint value.'),
        'source_locator': ('String', 'Table and footnote establishing endpoint scope.'),
    },
    'trial_demographics': {
        'demographic_id': ('String', 'One demographic dimension and subgroup in the overall efficacy population.'),
        'trial_id': ('String', 'Trial whose overall efficacy population is described.'),
        'dimension': ('String', 'Sex, Race, Ethnicity, or Age; each dimension describes the same 105 people.'),
        'subgroup': ('String', 'Source subgroup label, including Missing where reported.'),
        'patient_count': ('Integer', 'Subgroup count; do not sum across demographic dimensions.'),
        'reported_percent': ('Decimal', 'Source rounded percentage; retained without recalculation.'),
        'denominator_count': ('Integer', 'Overall efficacy population denominator of 105.'),
        'source_id': ('String', 'Source for the demographic fact.'),
        'source_locator': ('String', 'Source table establishing the subgroup counts.'),
        'source_quality_note': ('String', 'Source table versus figure discrepancy retained for review.'),
    },
    'industry_observations': {
        'observation_id': ('String', 'One indicator, geography, and observation period.'),
        'indicator': ('String', 'new_medicine_sales_share, not total pharmaceutical market share.'),
        'geography': ('String', 'Source chart region; Europe Top 5 is France, Germany, Italy, Spain, and the UK.'),
        'period_start': ('Integer', 'First year of the chart observation period, not report publication year.'),
        'period_end': ('Integer', 'Last year of the chart observation period.'),
        'value': ('Decimal', 'Chart share on a 0 to 100 percent scale; only comparable within the same scope and period.'),
        'unit': ('String', 'Percent of the chart-defined sales distribution.'),
        'market_scope': ('String', 'New-medicine launch cohort scope; not the overall drug market.'),
        'source_id': ('String', 'EFPIA report containing the chart; underlying chart attribution is IQVIA MIDAS.'),
        'source_locator': ('String', 'Original PDF page and chart locator.'),
        'source_quality_note': ('String', 'Source indicator and period scope; nearby market-growth figures describe a different indicator.'),
    },
}
MEANINGS = {
    'source_documents': 'Public evidence provenance, including original URLs, checksums, and capture dates.',
    'drugs': '46 distinct products in FDA CDER novel drug approvals for calendar year 2025.',
    'approval_events': '46 original US FDA CDER approval events; not all FDA actions or global approvals.',
    'trials': 'One published original-approval trial evidence subset, not a complete trial registry.',
    'trial_cohorts': 'Two disjoint prior-treatment cohorts in the selected 105-person efficacy population.',
    'trial_results': 'Four published endpoint percentages, with explicit cohort and endpoint denominators.',
    'trial_demographics': 'Eleven aggregate demographic categories across four overlapping dimensions; no individual patient records.',
    'industry_observations': 'Five regional chart shares for sales of new medicines launched during 2020-2024.',
}
RELATIONSHIPS = [
    ('approval_events', 'drug_id', 'drugs', 'drug_id'),
    ('trials', 'drug_id', 'drugs', 'drug_id'),
    ('trial_cohorts', 'trial_id', 'trials', 'trial_id'),
    ('trial_results', 'cohort_id', 'trial_cohorts', 'cohort_id'),
    ('trial_demographics', 'trial_id', 'trials', 'trial_id'),
] + [(table, 'source_id', 'source_documents', 'source_id') for table in SCHEMAS if table != 'source_documents']


def metric(name, expression, description, unit, grain, time_rule, concept, question, sql, expected, evidence):
    return dict(name=name, expression=expression, description=description, unit=unit, grain=grain,
                time_rule=time_rule, ontology_concepts=[concept], example_questions=[question],
                synonyms=[], owner='Local semantic reviewer', dimensions=[], reference_sql='',
                inclusion_rules=[grain], exclusion_rules=['Do not extend beyond the stated source population, period, or jurisdiction.'],
                evidence_refs=[evidence], assumptions=['Curated source facts; semantic approval is pending.']), dict(
                    metric=name, reference_sql=sql, expected=str(expected))


def metrics():
    definitions = [
        metric('novel_approval_count', 'COUNT(approval_events.approval_id)',
               'Number of FDA CDER novel-drug original approvals in the captured 2025 list. Count events once.',
               'approvals', 'One original FDA CDER approval event', 'Approval dates within calendar year 2025',
               'RegulatoryApproval', 'How many novel drugs did FDA CDER approve in 2025?',
               'SELECT COUNT(*) AS novel_approval_count FROM approval_events', 46, 'document:approval_scope'),
        metric('evidence_patient_count', 'SUM(trial_cohorts.patient_count)',
               'Patients across the two disjoint Beamion LUNG-1 original-approval cohorts. Excludes other trial populations.',
               'patients', 'Two disjoint efficacy cohorts: 71 without prior HER2 ADC and 34 with prior HER2 ADC',
               'Original approval evidence snapshot, 2025-08-08; not current enrollment', 'TrialPopulation',
               'How many patients are in the original HERNEXEOS approval efficacy population?',
               'SELECT SUM(patient_count) AS evidence_patient_count FROM trial_cohorts', 105, 'document:trial_denominators'),
        metric('no_prior_adc_orr_percent', "MAX(CASE WHEN trial_results.result_id = 'beamion_no_prior_adc_orr' THEN trial_results.value END)",
               'Published objective response rate for the 71-person cohort without prior HER2 ADC; 95% CI 63-83.',
               '%', 'One ORR result for the no-prior-ADC cohort; do not pool endpoint percentages',
               'Original approval evidence snapshot, 2025-08-08', 'ObjectiveResponseRate',
               'What was the response rate without previous HER2-targeted ADC?',
               "SELECT value AS no_prior_adc_orr_percent FROM trial_results WHERE result_id = 'beamion_no_prior_adc_orr'", 75, 'document:trial_denominators'),
        metric('prior_adc_orr_percent', "MAX(CASE WHEN trial_results.result_id = 'beamion_prior_adc_orr' THEN trial_results.value END)",
               'Published objective response rate for the 34-person prior-HER2-ADC cohort; 95% CI 29-61.',
               '%', 'One ORR result for the prior-ADC cohort', 'Original approval evidence snapshot, 2025-08-08',
               'ObjectiveResponseRate', 'What was the response rate with previous HER2-targeted ADC?',
               "SELECT value AS prior_adc_orr_percent FROM trial_results WHERE result_id = 'beamion_prior_adc_orr'", 44, 'document:trial_denominators'),
        metric('no_prior_adc_durable_response_percent', "MAX(CASE WHEN trial_results.result_id = 'beamion_no_prior_adc_dor_ge_6_months' THEN trial_results.value END)",
               'Published percentage of 53 responders with observed response duration at least six months; denominator is not 71 or 105.',
               '%', 'One observed DOR result among 53 responders in the no-prior-ADC cohort',
               'Original approval evidence snapshot, 2025-08-08', 'DurationOfResponse',
               'What share of responders without prior HER2 ADC had a response lasting at least six months?',
               "SELECT value AS no_prior_adc_durable_response_percent FROM trial_results WHERE result_id = 'beamion_no_prior_adc_dor_ge_6_months'", 58, 'document:trial_denominators'),
        metric('us_new_medicine_sales_share_percent', "MAX(CASE WHEN industry_observations.geography = 'USA' THEN industry_observations.value END)",
               'USA share in the EFPIA page 4 chart for sales of new medicines launched during 2020-2024. Latest sales are in 2025 at ex-factory prices. Not total market share.',
               '%', 'One USA chart observation for new-medicine sales, using the chart period',
               'Medicine launch period 2020-2024; latest sales in 2025; report edition 2026', 'NewMedicineSalesShare',
               'What USA share does the 2020-2024 new-medicine sales chart report?',
               "SELECT value AS us_new_medicine_sales_share_percent FROM industry_observations WHERE geography = 'USA'", '74.1', 'document:industry_chart_scope'),
    ]
    return [d for d, _ in definitions], [r for _, r in definitions]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_pack(output: Path, facts_path: Path):
    facts = json.loads(facts_path.read_text())
    if facts.get('schema') != 'helios.pharma-intelligence-facts.v1' or facts.get('synthetic') is not False:
        raise ValueError('Expected the explicit public-fact curation schema')
    tables = facts['tables']
    if set(tables) != set(SCHEMAS):
        raise ValueError('Unexpected curated table set')
    for table, rows in tables.items():
        if not rows or any(set(row) != set(SCHEMAS[table]) for row in rows):
            raise ValueError('Curated rows differ from the explicit schema: ' + table)
        key = next(iter(SCHEMAS[table]))
        if len({row[key] for row in rows}) != len(rows):
            raise ValueError('Duplicate primary key: ' + table)
    for a, b, c, d in RELATIONSHIPS:
        if not {r[b] for r in tables[a]} <= {r[d] for r in tables[c]}:
            raise ValueError('Unresolved source relationship: ' + a + '.' + b)
    root = output / PACK_ID
    serving = root / 'serving'
    (serving / 'documents').mkdir(parents=True, exist_ok=True)
    (root / 'evaluation').mkdir(exist_ok=True)
    for table, rows in tables.items():
        with (serving / (table + '.csv')).open('w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=list(SCHEMAS[table]))
            writer.writeheader()
            writer.writerows(rows)
    definitions, references = metrics()
    joins = [dict(name=f'{a}_{b}_{c}', from_field=a+'.'+b, to_field=c+'.'+d,
                  cardinality='many_to_one', meaning=f'Each {a} row references one {c} row by {b}.')
             for a, b, c, d in RELATIONSHIPS]
    glossary = [
        {'term': 'RegulatoryApproval', 'definition': 'An original FDA CDER approval event in the bounded 2025 list; not an NDC listing.'},
        {'term': 'TrialPopulation', 'definition': 'The 105-person original-approval efficacy subset, not every participant in the trial.'},
        {'term': 'ObjectiveResponseRate', 'definition': 'Published response percentage in one cohort; denominator is 71 or 34 patients.'},
        {'term': 'DurationOfResponse', 'definition': 'Observed response duration among responders; denominators are 53 and 15.'},
        {'term': 'NewMedicineSalesShare', 'definition': 'Regional share for the chart-defined 2020-2024 launch cohort, not total drug-market share.'},
    ]
    seed = dict(title=TITLE, description='Curated public facts from FDA CDER 2025 approvals, HERNEXEOS original-approval evidence, and an EFPIA 2026 industry chart. Source caveats remain visible; no patient records or pipeline forecasts are invented.',
                metrics=definitions, joins=joins, glossary_terms=glossary, dataset_meanings=MEANINGS,
                field_meanings={t+'.'+f: description for t, fields in SCHEMAS.items() for f, (_, description) in fields.items()},
                field_roles={t+'.'+f: ('identifier' if f == next(iter(fields)) else 'foreign_key' if f.endswith('_id') else 'time' if datatype == 'Date' or f in ('period_start', 'period_end') else 'measure' if datatype in ('Integer', 'Decimal') else 'attribute')
                             for t, fields in SCHEMAS.items() for f, (datatype, _) in fields.items()})
    expr = lambda sql: {'dialects': [{'dialect': 'ANSI_SQL', 'expression': sql}]}
    model = dict(version='0.2.0.dev0', name=PACK_ID, description=seed['description'],
                 datasets=[dict(name=t, source=t, description=MEANINGS[t], fields=[
                     dict(name=f, datatype=dt, description=desc, expression=expr(f), dimension={'is_time': dt == 'Date'})
                     for f, (dt, desc) in fields.items()]) for t, fields in SCHEMAS.items()],
                 relationships=[{'name': f'{a}_{b}_{c}', 'from': a, 'to': c, 'from_columns': [b], 'to_columns': [d]} for a, b, c, d in RELATIONSHIPS],
                 metrics=[dict(name=m['name'], description=m['description'], expression=expr(m['expression']),
                               custom_extensions=[{'vendor_name': 'HELIOS', 'data': json.dumps({'business_context': {k: v for k, v in m.items() if k not in ('expression', 'reference_sql')}}, sort_keys=True)}]) for m in definitions],
                 custom_extensions=[{'vendor_name': 'HELIOS', 'data': json.dumps({'builder_seed': seed}, sort_keys=True)}])
    write_json(serving/'draft.ossie.json', model)
    write_json(serving/'metadata.json', {'synthetic': False, 'timezone': 'UTC', 'dataset_meanings': MEANINGS, 'glossary_terms': glossary, 'curation_method': facts['curation_method']})
    briefs = [
        ('approval_scope', 'FDA_APPROVALS_2025', 'FDA approval scope',
         'The selected list covers 46 original FDA CDER novel-drug approvals in 2025. It does not cover all approval actions, all FDA centres, later indication expansions, or other jurisdictions. Count each listed product once, including combination products. The source text for Nereus appears truncated. Exdensur contains an apparent inserted word. The CSV preserves these issues with review notes.'),
        ('trial_denominators', 'FDA_HERNEXEOS_SNAPSHOT', 'Trial endpoint and population definitions',
         'The original HERNEXEOS efficacy evidence covers 105 people in two cohorts. The cohort without previous HER2 ADC contains 71 patients; the prior-ADC cohort contains 34. ORR is reported as 75% and 44%, respectively. DOR of at least six months is reported as 58% among 53 responders and 27% among 15 responders. DOR uses responders as its denominator. Do not use all 105 patients as the denominator or average the two percentages. These are reported cohort results, not comparative efficacy estimates. The detailed design says single-arm while summary text mentions randomization; this source inconsistency remains for review.'),
        ('demographic_scope', 'FDA_HERNEXEOS_FIGURE_1', 'Demographic chart and table scope',
         'Figure 1 represents the same 105-person efficacy population as FDA Table 1. The sex counts are 72 female and 33 male. Each demographic dimension describes the same people. Summing sex, race, ethnicity, and age counts would count people four times. The missing-ethnicity percentage differs between Table 1 and Figure 4 text. The curated table retains Table 1 with an explicit discrepancy note.'),
        ('industry_chart_scope', 'EFPIA_FIGURES_2026', 'Industry chart period and market definition',
         'The selected geographical chart on PDF page 4 describes sales of new medicines launched during 2020-2024. USA is 74.1%; Europe Top 5 is 15.6%; Japan is 3.6%; Pharmerging is 2.9%; the rest of the world is 3.8%. Europe Top 5 comprises France, Germany, Italy, Spain, and the United Kingdom. These values are not total pharmaceutical market shares. The report edition is 2026. Both this chart and the related new-medicine-sales prose use 2020-2024. Nearby market-growth prose uses 2020-2025 for a different indicator; do not combine those figures. The original chart attributes its underlying data to IQVIA MIDAS.'),
    ]
    documents = []
    for id, source_id, title, body in briefs:
        source = next(s for s in tables['source_documents'] if s['source_id'] == source_id)
        text = f'# {title}\n\n{body}\n\nSource: {source["source_url"]}\nSource SHA256: {source["sha256"]}\nRetrieved: {source["retrieved_date"]}\n\nCurated evidence brief; not a verbatim publisher document or an automated visual extraction. Semantic review is pending.\n'
        path = 'documents/'+id+'.md'
        (serving/path).write_text(text)
        documents.append(dict(document_id=id, path=path, entity_table='source_documents', entity_id=source_id,
                              source_url=source['source_url'], source_sha256=source['sha256'], synthetic=False,
                              review_status='IN_REVIEW', material_kind='curated_source_brief'))
    write_json(serving/'documents.json', documents)
    write_json(root/'evaluation/reference.json', references[0])
    write_json(root/'evaluation/references.json', references)
    manifest = dict(sector=PACK_ID, synthetic=False, state='IN_REVIEW', generator_version=1,
                    source={'name': 'FDA CDER and EFPIA curated public evidence', 'url': tables['source_documents'][0]['source_url']},
                    source_inputs=tables['source_documents'], external_records_used=True,
                    source_records_read=sum(len(rows) for rows in tables.values()),
                    generation_mode='public-source-derived; curated published facts',
                    curation_snapshot_sha256=digest(facts_path.read_bytes()),
                    limitations=['Bounded reference dataset, not a complete pharmaceutical pipeline database.',
                                 'Original approval evidence is historical; current indications can differ.',
                                 'Source inconsistencies are retained; semantic review remains pending.',
                                 'Original PDF and image bytes remain in the source cache; serving documents are curated evidence briefs.'],
                    row_counts={t:len(rows) for t, rows in tables.items()}, documents=len(documents),
                    serving_root='serving', evaluation_root='evaluation',
                    evaluation_policy='Never crawl evaluation or include it in query prompts.')
    manifest['checksums'] = {str(p.relative_to(root)): digest(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'manifest.json'}
    write_json(root/'manifest.json', manifest)
    return dict(id=PACK_ID, title=TITLE, timezone='UTC', adapter='local_duckdb', retrieval='disabled', data_origin='public_source',
                manifest_sha256=digest((root/'manifest.json').read_bytes()), model_sha256=digest((serving/'draft.ossie.json').read_bytes()),
                examples=[dict(id='aggregate' if i == 0 else m['name'], question=m['example_questions'][0], metric=m['name'], unit=m['unit']) for i,m in enumerate(definitions)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--facts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(write_pack(args.output, args.facts), indent=2))


if __name__ == '__main__':
    main()
