"""Offline fixture acceptance: integrity, leakage boundaries and real compilation."""
import csv
import hashlib
import json
import zipfile
from decimal import Decimal
import pytest
from helios_ds.sector_demo.__main__ import RELATIONSHIPS, read_source, write_pack
from helios_core.ossie.build import validate
from helios_core.ossie.model import SemanticModel
from helios_core.compiler.compiler import Compiler, SemanticRequest

@pytest.mark.parametrize('sector',['finance','manufacturing','pharma','power'])
def test_pack_integrity_and_compiler_reference(tmp_path,sector):
    import duckdb
    write_pack(tmp_path,sector,8100)
    path=tmp_path/sector; first=(path/'manifest.json').read_bytes()
    write_pack(tmp_path,sector,8100)
    assert first==(path/'manifest.json').read_bytes()
    manifest=json.loads(first);assert manifest['state']=='IN_REVIEW'
    assert manifest['external_records_used'] is False
    for rel,digest in manifest['checksums'].items(): assert hashlib.sha256((path/rel).read_bytes()).hexdigest()==digest
    tables={p.stem:list(csv.DictReader(p.open())) for p in (path/'serving').glob('*.csv')}
    for a,b,c,d in RELATIONSHIPS[sector]: assert {r[b] for r in tables[a]} <= {r[d] for r in tables[c]}
    for doc in json.loads((path/'serving/documents.json').read_text()):
        assert (path/'serving'/doc['path']).exists()
        assert any(doc['entity_id'] in r.values() for r in tables[doc['entity_table']])
    assert not any('evaluation' in p.parts for p in (path/'serving').rglob('*'))
    model=json.loads((path/'serving/draft.ossie.json').read_text()); assert not validate(model)
    reference=json.loads((path/'evaluation/reference.json').read_text())
    sql=Compiler(SemanticModel(model)).compile(SemanticRequest.from_dict({'metrics':[reference['metric']]}),dialect='trino').sql
    conn=duckdb.connect()
    try:
        for name in tables:
            conn.execute(f'CREATE TABLE "{name}" AS SELECT * FROM read_csv(?, auto_detect=true)',[str(path/'serving'/(name+'.csv'))])
        compiled=Decimal(str(conn.execute(sql).fetchone()[0])); direct=Decimal(str(conn.execute(reference['reference_sql']).fetchone()[0]))
        assert abs(compiled-Decimal(reference['expected'])) < Decimal('.00000001')
        assert abs(compiled-direct) < Decimal('.00000001')
    finally: conn.close()
    if sector=='power':
        assert len(tables['meter_readings'])==4032
        assert all(r['import_kwh']=='' for r in tables['meter_readings'] if r['quality_status']=='MISSING')
    if sector=='finance':
        ledger={}
        for row in tables['ledger_postings']: ledger[row['transaction_id']]=ledger.get(row['transaction_id'],Decimal(0))+Decimal(row['amount_sgd'])
        assert set(ledger.values())=={Decimal(0)}

def test_source_import_is_explicit_and_bounded(tmp_path):
    with zipfile.ZipFile(tmp_path/'manufacturing.zip','w') as z:
        z.writestr('ai4i2020.csv','Air temperature [K],Process temperature [K],Torque [Nm],Tool wear [min],Rotational speed [rpm],Machine failure\n300,310,40,100,1500,1\n')
    assert len(read_source('manufacturing',tmp_path))==1
    write_pack(tmp_path/'packs','manufacturing',8100,tmp_path)
    manifest=json.loads((tmp_path/'packs/manufacturing/manifest.json').read_text())
    assert manifest['external_records_used'] and manifest['source_records_read']==1
    assert 'Machine failure' not in (tmp_path/'packs/manufacturing/serving/sensor_readings.csv').read_text()
    assert 'Machine failure' in (tmp_path/'packs/manufacturing/evaluation/reference.json').read_text()
    with pytest.raises(FileNotFoundError): read_source('power',tmp_path)

def test_power_source_units_and_mode_separation(tmp_path):
    with zipfile.ZipFile(tmp_path/'power.zip','w') as z:
        z.writestr('household_power_consumption.txt','Date;Time;Global_active_power\n16/12/2006;17:24:00;2.0\n')
    write_pack(tmp_path/'packs','power',8100,tmp_path)
    path=tmp_path/'packs/power'
    readings=list(csv.DictReader((path/'serving/meter_readings.csv').open()))
    assert all(r['import_kwh']=='1.0000' for r in readings if r['quality_status']=='VALID')
    assert all(r['source_sample_date']=='16/12/2006' for r in readings)
    assert Decimal(json.loads((path/'evaluation/reference.json').read_text())['expected'])==Decimal('3960')
    with pytest.raises(ValueError,match='fresh output'): write_pack(tmp_path/'packs','power',8100)

def test_pharma_public_reference_is_separate(tmp_path):
    (tmp_path/'pharma.json').write_text(json.dumps({'results':[{'product_ndc':'TEST-NDC','generic_name':'Test catalog product','dosage_form':'TABLET'}]}))
    write_pack(tmp_path/'packs','pharma',8100,tmp_path)
    path=tmp_path/'packs/pharma/serving'
    assert 'TEST-NDC' in (path/'public_ndc_reference.csv').read_text()
    assert 'TEST-NDC' not in (path/'batches.csv').read_text()
    assert 'Test catalog product' not in (path/'products.csv').read_text()
