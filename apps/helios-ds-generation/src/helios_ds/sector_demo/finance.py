"""Independent deterministic finance fixtures; not calibrated banking or AML data."""
import csv
import hashlib
import json
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .finance_metadata import inventory

SCHEMA = {
    'customers': [('customer_id','varchar'),('display_name','varchar'),('jurisdiction','varchar')],
    'accounts': [('account_id','varchar'),('customer_id','varchar'),('currency','varchar')],
    'fx_rates': [('currency','varchar'),('sgd_rate','decimal(12,6)')],
    'transactions': [('transaction_id','varchar'),('sender_account_id','varchar'),('receiver_account_id','varchar'),
                     ('timestamp','timestamp with time zone'),('currency','varchar'),('amount','decimal(18,2)'),
                     ('amount_sgd','decimal(18,2)'),('status','varchar'),('channel','varchar')],
    'ledger_postings': [('posting_id','varchar'),('transaction_id','varchar'),('account_id','varchar'),('amount_sgd','decimal(18,2)')],
    'payments': [('transaction_id','varchar'),('customer_id','varchar'),('amount_sgd','decimal(18,2)'),
                 ('jurisdiction','varchar'),('booking_date','date')],
}


def money(value):
    return str(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def generate(seed=8100, customers=200, transactions=5000):
    if not 12 <= customers <= 10000 or not 1 <= transactions <= 100000:
        raise ValueError('Use 12–10000 customers and 1–100000 background transactions')
    rng=random.Random(seed)
    base=datetime(2026,9,1,tzinfo=timezone.utc)
    rates={'SGD':Decimal('1.000000'),'USD':Decimal('1.300000'),'HKD':Decimal('0.170000')}
    tables={name:[] for name in SCHEMA}
    for i in range(customers):
        tables['customers'].append({'customer_id':f'SYN-C{i:05d}','display_name':f'Synthetic party {i:05d}',
                                    'jurisdiction':['SG','HK','GB'][i%3]})
        tables['accounts'].append({'account_id':f'SYN-A{i:05d}','customer_id':f'SYN-C{i:05d}',
                                   'currency':list(rates)[i%3]})
    tables['fx_rates']=[{'currency':currency,'sgd_rate':str(rate)} for currency,rate in rates.items()]
    labels=[]

    def add(sender, receiver, cents, instant, status='SETTLED', scenario=None):
        account=tables['accounts'][sender]
        amount=Decimal(cents)/100
        amount_sgd=money(amount*rates[account['currency']])
        transaction_id=f'SYN-T{len(tables["transactions"]):08d}'
        row={'transaction_id':transaction_id,'sender_account_id':account['account_id'],
             'receiver_account_id':tables['accounts'][receiver]['account_id'],'timestamp':instant.isoformat(),
             'currency':account['currency'],'amount':money(amount),'amount_sgd':amount_sgd,
             'status':status,'channel':rng.choice(['WIRE','APP','BATCH'])}
        tables['transactions'].append(row)
        if status=='SETTLED':
            for suffix,owner,value in [('D',sender,-Decimal(amount_sgd)),('C',receiver,Decimal(amount_sgd))]:
                tables['ledger_postings'].append({'posting_id':transaction_id+'-'+suffix,'transaction_id':transaction_id,
                                                  'account_id':tables['accounts'][owner]['account_id'],'amount_sgd':money(value)})
            tables['payments'].append({'transaction_id':transaction_id,'customer_id':account['customer_id'],
                                       'amount_sgd':amount_sgd,'jurisdiction':tables['customers'][sender]['jurisdiction'],
                                       'booking_date':instant.date().isoformat()})
        if scenario:labels.append({'transaction_id':transaction_id,'scenario':scenario})

    for _ in range(transactions):
        sender=rng.randrange(customers)
        receiver=rng.randrange(customers-1)
        if receiver>=sender:receiver+=1
        add(sender,receiver,max(100,int(rng.lognormvariate(9,1.2))),
            base+timedelta(seconds=rng.randrange(30*86400)),
            'REJECTED' if rng.random()<0.03 else 'SETTLED')
    # Injected graph motifs are evaluation scenarios, not proof of criminal conduct.
    for i in range(3):add(i,(i+1)%3,100000,base+timedelta(days=10,minutes=i),scenario='cycle')
    for i in range(4,8):add(3,i,250000,base+timedelta(days=12,minutes=i),scenario='fan_out')
    for i in range(8,12):add(i,3,175000,base+timedelta(days=14,minutes=i),scenario='fan_in')
    metadata={'schema':'uob.metadata.inventory.v1','mode':'sample','datasets':[]}
    for table,fields in SCHEMA.items():
        dataset=inventory('iceberg','synthetic_finance',table,
                          [{'name':n,'type':t} for n,t in fields],mode='sample')['datasets'][0]
        dataset['description']='Independent synthetic fixture: '+table.replace('_',' ')
        metadata['datasets'].append(dataset)
    metadata['relationships']=[{'from':'accounts.customer_id','to':'customers.customer_id'},
                               {'from':'transactions.sender_account_id','to':'accounts.account_id'},
                               {'from':'transactions.receiver_account_id','to':'accounts.account_id'},
                               {'from':'ledger_postings.transaction_id','to':'transactions.transaction_id'}]
    metadata['lineage']=[{'inputs':['transactions','accounts','customers'],'output':'payments',
                          'origin':'synthetic transformation contract',
                          'rule':'Settled sender outflow; convert to SGD before aggregation; UTC booking date.'}]
    metadata['glossary']=[{'term':'outward payment','meaning':'One settled transfer viewed from its sender; counted once.'},
                           {'term':'amount_sgd','meaning':'Transfer amount converted with fixed illustrative fixture FX rates.'}]
    metadata['limitations']=['All data and lineage are synthetic; Atlas has not been contacted.',
                             'Relationships and glossary are authored fixture contracts, not inferred source facts.',
                             'No permissions are enforced by metadata labels.']
    # Keep corruption and evaluation truth outside operational tables and semantic context.
    corrupt=[dict(tables['transactions'][0]) for _ in range(3)]
    corrupt[2].update(transaction_id='SYN-BAD-ORPHAN',sender_account_id='SYN-MISSING',amount='-1.00',currency='')
    return {'tables':tables,'metadata':metadata,'evaluation':{'scenario_labels':labels,'invalid_transactions':corrupt},
            'manifest':{'schema':'uob.synthetic.finance.v1','generator_version':1,'seed':seed,'synthetic':True,
                        'background_transactions':transactions,'injected_transactions':len(labels),
                        'external_records_used':False,'fx_rates':'Fixed illustrative values; not market rates',
                        'limitations':['Not calibrated to UOB or a real banking population.',
                                       'Scenario labels are not validated AML predictions.']}}
