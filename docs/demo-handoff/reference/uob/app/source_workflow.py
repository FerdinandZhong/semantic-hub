"""Read-only table discovery with bounded samples and sample-only profiling."""
from collections import Counter
from typing import Literal
import re
from pydantic import BaseModel, ConfigDict, Field
from .connectors import ConnectionFailure, redact
from .semantics import execute_trino
from .metadata_inventory import inventory

SAMPLE_COLUMNS = [
    {'name':'customer_id','type':'varchar'}, {'name':'amount_sgd','type':'decimal(18,2)'},
    {'name':'jurisdiction','type':'varchar'}, {'name':'booking_date','type':'date'},
]
SAMPLE_ROWS = [
    {'customer_id':'C001','amount_sgd':1200,'jurisdiction':'SG','booking_date':'2026-09-01'},
    {'customer_id':'C001','amount_sgd':2400,'jurisdiction':'SG','booking_date':'2026-09-02'},
    {'customer_id':'C002','amount_sgd':500,'jurisdiction':'HK','booking_date':'2026-09-01'},
    {'customer_id':'C003','amount_sgd':800,'jurisdiction':'SG','booking_date':'2026-09-03'},
]
class SourceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['sample','live']
    action: Literal['catalogs','schemas','tables','columns','preview','profile']
    catalog: str = Field(default='',max_length=128)
    schema_name: str = Field(default='',max_length=128,alias='schema')
    table: str = Field(default='',max_length=128)


def identifier(value):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$-]{0,127}', value):
        raise ConnectionFailure('Select a supported catalog, schema and table name from source discovery.')
    return '"'+value+'"'


def source_path(request):
    return '.'.join(identifier(x) for x in [request.catalog,request.schema_name,request.table])


def discover(settings, request):
    action=request.action
    if request.mode=='sample' and settings.sample_finance_dir:
        from .sample_finance import Finance
        return Finance(settings).discover(request)
    if request.mode=='sample':
        if action=='catalogs':return {'mode':'sample','items':['iceberg'],'synthetic':True}
        if request.catalog!='iceberg':raise ConnectionFailure('Unknown sample catalog.')
        if action=='schemas':return {'mode':'sample','items':['demo'],'synthetic':True}
        if request.schema_name!='demo':raise ConnectionFailure('Unknown sample schema.')
        if action=='tables':return {'mode':'sample','items':['payments'],'synthetic':True}
        if request.table!='payments':raise ConnectionFailure('Unknown sample table.')
        columns=SAMPLE_COLUMNS
        rows=SAMPLE_ROWS
    else:
        if action=='catalogs':
            rows=execute_trino(settings,'SHOW CATALOGS')
            return {'mode':'live','items':[next(iter(r.values())) for r in rows],'bounded':True}
        catalog=identifier(request.catalog)
        if action=='schemas':
            rows=execute_trino(settings,f'SHOW SCHEMAS FROM {catalog}')
            return {'mode':'live','items':[next(iter(r.values())) for r in rows],'bounded':True}
        schema=identifier(request.schema_name)
        if action=='tables':
            rows=execute_trino(settings,f'SHOW TABLES FROM {catalog}.{schema}')
            return {'mode':'live','items':[next(iter(r.values())) for r in rows],'bounded':True}
        table=identifier(request.table)
        rows=execute_trino(settings,f'SELECT column_name, data_type FROM {catalog}.information_schema.columns WHERE table_schema = \'{request.schema_name}\' AND table_name = \'{request.table}\' ORDER BY ordinal_position LIMIT 100')
        if not rows or len(rows)>=100:raise ConnectionFailure('Table is unavailable or has too many columns for this demo. Choose a smaller approved view.')
        columns=[{'name':r['column_name'],'type':r['data_type']} for r in rows]
        # Fail closed on unsupported names before building expressions from metadata.
        for column in columns:identifier(column['name'])
        if action!='columns':rows=execute_trino(settings,f'SELECT * FROM {catalog}.{schema}.{table} LIMIT 50')
    result={'mode':request.mode,'synthetic':request.mode=='sample','source':'.'.join([request.catalog,request.schema_name,request.table]),'columns':columns}
    result['metadata']=inventory(request.catalog,request.schema_name,request.table,columns,mode=request.mode)
    if action=='preview':result.update(rows=redact(rows[:50]),limit=50)
    if action=='profile':
        result.update(sample_size=len(rows),scope='At most 50 returned rows; sample statistics do not establish whole-table quality or key uniqueness.',columns=[{
            **column,'nulls':sum(r.get(column['name']) is None for r in rows),
            'distinct_in_sample':len(Counter(str(r.get(column['name'])) for r in rows if r.get(column['name']) is not None)),
        } for column in columns])
    return result
