"""Build additive, offline sector fixtures. No publication or live service access."""
import argparse
import csv
import hashlib
import io
from itertools import islice
import json
import random
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from .finance import generate as finance

SOURCES = {
 'manufacturing': {'name':'UCI AI4I 2020 Predictive Maintenance', 'url':'https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset', 'download':'https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip', 'license':'CC BY 4.0', 'doi':'10.24432/C5HS5C'},
 'pharma': {'name':'openFDA National Drug Code directory', 'url':'https://open.fda.gov/apis/drug/ndc/', 'download':'https://api.fda.gov/drug/ndc.json?limit=100', 'license':'CC0, subject to openFDA exceptions', 'license_url':'https://open.fda.gov/license/'},
 'power': {'name':'UCI Individual Household Electric Power Consumption', 'url':'https://archive.ics.uci.edu/dataset/235/individual+household+electric+power+consumption', 'download':'https://archive.ics.uci.edu/static/public/235/individual+household+electric+power+consumption.zip', 'license':'CC BY 4.0', 'doi':'10.24432/C58K54'}
}

RELATIONSHIPS = {
 'finance': [('accounts','customer_id','customers','customer_id'),('transactions','sender_account_id','accounts','account_id'),('transactions','receiver_account_id','accounts','account_id'),('ledger_postings','transaction_id','transactions','transaction_id'),('payments','customer_id','customers','customer_id')],
 'manufacturing': [('sensor_readings','asset_id','assets','asset_id'),('work_orders','asset_id','assets','asset_id')],
 'pharma': [('batches','product_id','products','product_id'),('lab_results','batch_id','batches','batch_id'),('deviations','batch_id','batches','batch_id')],
 'power': [('feeders','substation_id','substations','substation_id'),('meters','feeder_id','feeders','feeder_id'),('meter_readings','meter_id','meters','meter_id')]
}

def read_source(sector, cache):
    if not cache: return []
    path=Path(cache)/({'manufacturing':'manufacturing.zip','pharma':'pharma.json','power':'power.zip'}[sector])
    if not path.exists(): raise FileNotFoundError(path)
    if sector=='pharma': return json.loads(path.read_text())['results']
    with zipfile.ZipFile(path) as archive:
        suffix='.csv' if sector=='manufacturing' else '.txt'
        names=[n for n in archive.namelist() if n.endswith(suffix)]
        if len(names)!=1: raise ValueError('Expected one source data file')
        with archive.open(names[0]) as raw:
            return list(islice(csv.DictReader(io.TextIOWrapper(raw,encoding='utf-8-sig'),delimiter=',' if sector=='manufacturing' else ';'),10000))

def build(sector, seed, raw):
    rng=random.Random(seed); docs=[]; truth={}; tables={}
    if sector=='manufacturing':
        tables={'assets':[], 'sensor_readings':[], 'work_orders':[]}
        for i in range(12): tables['assets'].append({'asset_id':f'SYN-M{i:03}', 'site':'Synthetic plant A', 'line':f'Line {i%3+1}'})
        for i in range(240):
            source=raw[i%len(raw)] if raw else {}
            row={'reading_id':f'SYN-R{i:04}', 'asset_id':f'SYN-M{i%12:03}', 'observed_at_utc':(datetime(2026,9,24,tzinfo=timezone.utc)+timedelta(minutes=30*i)).isoformat(),
                 'air_temperature_k':source.get('Air temperature [K]',round(rng.gauss(300,2),2)), 'process_temperature_k':source.get('Process temperature [K]',round(rng.gauss(310,1),2)),
                 'rotational_speed_rpm':source.get('Rotational speed [rpm]',round(rng.uniform(1200,1800))), 'torque_nm':source.get('Torque [Nm]',round(max(0,rng.gauss(40,10)),2)), 'tool_wear_min':source.get('Tool wear [min]',rng.randrange(250))}
            tables['sensor_readings'].append(row)
            if source: truth[row['reading_id']]={k:source[k] for k in ['Machine failure','TWF','HDF','PWF','OSF','RNF'] if k in source}
        for i in range(12):
            key=f'SYN-WO{i:03}'; asset=f'SYN-M{i:03}'
            tables['work_orders'].append({'work_order_id':key,'asset_id':asset,'status':'PLANNED','downtime_minutes':15+i*2})
            docs.append((key, f'# Synthetic maintenance note {key}\n\nAsset: {asset}. Inspect tool wear and torque readings. This is an authored training scenario. No real failure is asserted.\n', 'work_orders',key))
        metric=('work_orders','downtime_minutes','planned_downtime_minutes','Total planned maintenance minutes; not observed downtime.')
    elif sector=='pharma':
        tables={'products':[], 'batches':[], 'lab_results':[], 'deviations':[]}
        for i in range(8): tables['products'].append({'product_id':f'SYN-P{i:03}', 'product_name':f'Synthetic formulation {i+1}', 'dosage_form':['TABLET','CAPSULE','PATCH'][i%3]})
        for i in range(24):
            batch=f'SYN-B{i:03}'; tables['batches'].append({'batch_id':batch,'product_id':f'SYN-P{i%8:03}','manufactured_date':f'2026-09-{i+1:02}','review_status':'IN_REVIEW'})
            docs.append((batch, f'# Synthetic batch review {batch}\n\nProduct: SYN-P{i%8:03}. Review the linked draft laboratory result SYN-L{i:03} and any open deviation. All identifiers and manufacturing activities are fictional. Human review is required; this report does not authorize release.\n', 'batches', batch))
            tables['lab_results'].append({'result_id':f'SYN-L{i:03}','batch_id':batch,'test_name':'ASSAY','assay_percent':str(Decimal('98.00')+Decimal(i%7)/10),'unit':'percent','result_status':'DRAFT'})
            if i%4==0:
                deviation=f'SYN-D{i:03}'; tables['deviations'].append({'deviation_id':deviation,'batch_id':batch,'category':'DOCUMENTATION','status':'OPEN'})
                docs.append((deviation,f'# Synthetic deviation {deviation}\n\nBatch: {batch}. A fictional review found an incomplete equipment log. Investigate the documentation and request reviewer approval. This is not a medical recommendation or release decision.\n','deviations',deviation))
        # Public catalog records remain separate from fictional quality and batch records.
        if raw:
            tables['public_ndc_reference']=[{'product_ndc':r.get('product_ndc',''),'generic_name':r.get('generic_name',''),'dosage_form':r.get('dosage_form','')} for r in raw]
        metric=('lab_results','assay_percent','average_assay_percent','Mean draft assay percentage. No product-release or clinical decision is implied.')
    else:
        tables={'substations':[], 'feeders':[], 'meters':[], 'meter_readings':[]}
        for i in range(3):
            tables['substations'].append({'substation_id':f'SYN-SS{i}','region':['North','Central','East'][i]})
            tables['feeders'].append({'feeder_id':f'SYN-F{i}','substation_id':f'SYN-SS{i}','voltage_kv':'22'})
        for i in range(12): tables['meters'].append({'meter_id':f'SYN-M{i:03}','feeder_id':f'SYN-F{i%3}','customer_class':['Residential','Commercial','Industrial'][i%3]})
        usable=[r for r in raw if r.get('Global_active_power') not in ('?', '',None)]
        if raw and not usable: raise ValueError('Source has no usable active power samples')
        for day in range(7):
            for meter in range(12):
                for halfhour in range(48):
                    i=len(tables['meter_readings']); source=usable[i%len(usable)] if usable else None
                    # An imported one-minute sample shapes a fictional half-hour profile.
                    # This is not a measured half-hour aggregate of the source household.
                    kw=Decimal(source['Global_active_power']) if source else Decimal(str(round(1.5+meter*.35+day*.13+rng.random(),3)))
                    start=datetime(2026,9,23,16,tzinfo=timezone.utc)+timedelta(days=day,minutes=30*halfhour)
                    tables['meter_readings'].append({'reading_id':f'SYN-E{i:05}','meter_id':f'SYN-M{meter:03}','interval_start_utc':start.isoformat(),'reading_date':f'2026-09-{24+day:02}', 'region':['North','Central','East'][meter%3], 'import_kwh':str((kw/2).quantize(Decimal('.0001'))),'quality_status':'MISSING' if i%131==0 else 'VALID','is_estimated':'true' if i%97==0 else 'false','source_sample_date':source['Date'] if source else ''})
                    if tables['meter_readings'][-1]['quality_status']=='MISSING': tables['meter_readings'][-1]['import_kwh']=''
        metric=('meter_readings','import_kwh','measured_import_kwh','Measured imported energy, kWh. Only VALID, non-estimated readings; dates use Asia/Singapore.')
    return tables, docs, truth, metric

def model(sector,tables,metric):
    datasets=[]
    for name,rows in tables.items():
        fields=[]
        for field,value in rows[0].items():
            numeric=field in {'torque_nm','air_temperature_k','process_temperature_k','tool_wear_min','rotational_speed_rpm','downtime_minutes','assay_percent','import_kwh','voltage_kv','amount','amount_sgd','sgd_rate'}
            fields.append({'name':field,'datatype':'Decimal' if numeric else ('DateTimeTz' if field in {'observed_at_utc','interval_start_utc','timestamp'} else 'Date' if field.endswith('_date') else 'String'),'expression':{'dialects':[{'dialect':'ANSI_SQL','expression':field}]},'dimension':{'is_time':field.endswith('_date')}})
        datasets.append({'name':name,'source':name,'fields':fields})
    table,column,name,description=metric
    operation='AVG' if sector=='pharma' else 'SUM'
    expr=f'{operation}({table}.{column})'
    if sector=='power': expr="SUM(CASE WHEN meter_readings.quality_status = 'VALID' AND meter_readings.is_estimated = 'false' THEN meter_readings.import_kwh ELSE 0 END)"
    return {'version':'0.2.0.dev0','name':f'synthetic_{sector}','datasets':datasets,'relationships':[{'name':a+'_'+b+'_'+c,'from':a,'to':c,'from_columns':[b],'to_columns':[d]} for a,b,c,d in RELATIONSHIPS[sector]],'metrics':[{'name':name,'description':description,'expression':{'dialects':[{'dialect':'ANSI_SQL','expression':expr}]}}]}

def write_pack(output,sector,seed,cache=None):
    path=output/sector
    if (path/'manifest.json').exists():
        previous=json.loads((path/'manifest.json').read_text())
        if sector!='finance' and previous.get('external_records_used') != bool(cache):
            raise ValueError('Use a fresh output directory when changing source mode')
    path.mkdir(parents=True,exist_ok=True)
    if sector=='finance':
        pack=finance(seed); tables=pack['tables']; docs=[]; truth=pack['evaluation']; metric=('payments','amount_sgd','total_amount_sgd','Settled sender outflow, SGD; fixed synthetic FX.')
        manifest=pack['manifest']; metadata=pack['metadata']
    else:
        raw=read_source(sector,cache)
        required={'manufacturing':{'Air temperature [K]','Process temperature [K]','Torque [Nm]','Tool wear [min]','Rotational speed [rpm]'},'pharma':{'product_ndc'},'power':{'Date','Time','Global_active_power'}}[sector]
        if cache and (not raw or any(not required <= r.keys() for r in raw)):
            raise ValueError('Requested source is empty or has an unsupported schema')
        tables,docs,truth,metric=build(sector,seed,raw)
        manifest={'synthetic':True,'seed':seed,'source':SOURCES[sector],'external_records_used':bool(raw),'source_records_read':len(raw),'generation_mode':'source-derived fictional extension' if raw else 'source-informed synthetic; no source records downloaded','limitations':['Fictional demo data; not SP Group, a real plant, or a real manufacturer.','No production prediction, regulatory approval, or calibration is established.']}
        if cache:
            source_path=Path(cache)/({'manufacturing':'manufacturing.zip','pharma':'pharma.json','power':'power.zip'}[sector]);manifest['source_sha256']=hashlib.sha256(source_path.read_bytes()).hexdigest()
        metadata={'datasets':[{'name':name,'fields':list(rows[0])} for name,rows in tables.items()], 'timezone':'Asia/Singapore' if sector=='power' else 'UTC'}
    serving=path/'serving'; serving.mkdir(exist_ok=True)
    for name,rows in tables.items():
        with (serving/(name+'.csv')).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader();writer.writerows(rows)
    documents=[]
    for key,text,table,entity in docs:
        target=serving/'documents'/(key+'.md'); target.parent.mkdir(exist_ok=True);target.write_text(text)
        documents.append({'document_id':key,'path':'documents/'+target.name,'entity_table':table,'entity_id':entity,'synthetic':True,'review_status':'IN_REVIEW'})
    (serving/'documents.json').write_text(json.dumps(documents,indent=2)+'\n')
    metadata['relationships']=[{'from':a+'.'+b,'to':c+'.'+d} for a,b,c,d in RELATIONSHIPS[sector]]
    (serving/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (serving/'draft.ossie.json').write_text(json.dumps(model(sector,tables,metric),indent=2)+'\n')
    evaluation=path/'evaluation';evaluation.mkdir(exist_ok=True)
    table,column,name,_=metric
    selected=tables[table]
    where=" WHERE quality_status = 'VALID' AND is_estimated = 'false'" if sector=='power' else ''
    if sector=='power': selected=[r for r in selected if r['quality_status']=='VALID' and r['is_estimated']=='false']
    value=sum((Decimal(str(r[column])) for r in selected),Decimal(0))
    if sector=='pharma': value/=len(selected)
    expected=str(value)
    operation='AVG' if sector=='pharma' else 'SUM'
    (evaluation/'reference.json').write_text(json.dumps({'metric':name,'question':f'What is {name.replace("_"," ")}?','reference_sql':f'SELECT {operation}({column}) AS value FROM {table}'+where,'expected':expected,'truth':truth},indent=2)+'\n')
    manifest.update({'sector':sector,'state':'IN_REVIEW','generator_version':1,'row_counts':{n:len(r) for n,r in tables.items()},'documents':len(docs),'serving_root':'serving','evaluation_root':'evaluation','evaluation_policy':'Never crawl evaluation or include it in query prompts.'})
    manifest['checksums']={str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(path.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    (path/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,required=True);p.add_argument('--seed',type=int,default=8100);p.add_argument('--sector',choices=['finance','manufacturing','pharma','power','all'],default='all');p.add_argument('--source-cache',type=Path)
    args=p.parse_args()
    for sector in ['finance','manufacturing','pharma','power'] if args.sector=='all' else [args.sector]: write_pack(args.output,sector,args.seed,args.source_cache if sector!='finance' else None)
    (args.output/'catalog.json').write_text(json.dumps({'schema':'helios.sector-fixtures.v1','packs':[s for s in ['finance','manufacturing','pharma','power','pharma_intelligence'] if (args.output/s/'manifest.json').exists()],'state':'IN_REVIEW'},indent=2)+'\n')
if __name__=='__main__': main()
