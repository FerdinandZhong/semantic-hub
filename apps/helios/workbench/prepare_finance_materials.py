"""Build synthetic finance supporting materials from serving CSVs only."""
import csv
import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[3]
SERVING = ROOT / 'apps/helios-ds-generation/fixtures/sectors/v1/finance/serving'
OUTPUT = ROOT / 'docs/demo-inputs/finance'


def build(output=OUTPUT):
    output.mkdir(parents=True, exist_ok=True)
    tables = {name:list(csv.DictReader((SERVING/f'{name}.csv').open())) for name in
              ('payments','transactions','accounts','customers','fx_rates','ledger_postings')}
    payments=tables['payments'];transactions={t['transaction_id']:t for t in tables['transactions']}
    assert len(transactions)==len(tables['transactions'])
    settled=[t for t in transactions.values() if t['status']=='SETTLED']
    assert {p['transaction_id'] for p in payments}=={t['transaction_id'] for t in settled}
    total=sum(Decimal(p['amount_sgd']) for p in payments)
    assert total==sum(Decimal(t['amount_sgd']) for t in settled)
    dates=sorted(p['booking_date'] for p in payments)
    assert dates[0]=='2026-09-01' and dates[-1]=='2026-09-30'
    groups=defaultdict(Decimal)
    for p in payments:groups[p['jurisdiction']]+=Decimal(p['amount_sgd'])
    selected=payments[0];tx=transactions[selected['transaction_id']]
    rates={r['currency']:r['sgd_rate'] for r in tables['fx_rates']}
    documents=[('finance-payment-definition.md','Payment definition and reconciliation',[
        'SYNTHETIC DEMO MATERIAL. This document describes the bundled finance fixture. It is not a bank policy or evidence of real customer activity.',
        'Coverage: 1 September 2026 through 30 September 2026. The booking date uses UTC, not Asia/Singapore local time.',
        'The total_amount_sgd metric measures settled sender outflow. Its expression is SUM(payments.amount_sgd). One payments row represents one settled transaction viewed from its sender. payments.customer_id identifies the sender customer; payments.jurisdiction is that customer\'s jurisdiction, not the receiver location.',
        'Only transactions with status SETTLED produce payments rows. REJECTED transactions remain in transactions but do not enter payments or ledger_postings. Exclude rejected transfers from settled sender outflow.',
        'Each settled transaction has a negative debit and an equal positive credit in ledger_postings. Summing signed postings nets to zero. Summing absolute postings counts both sides. Neither is the settled sender outflow metric.',
        'Evidence links explain the meaning of payments, transactions.status, payments.amount_sgd, and total_amount_sgd. They do not change SQL, create a join, or establish financial risk.'
    ]),('finance-fixed-fx-rules.md','Fixed FX and reporting scope',[
        'SYNTHETIC DEMO MATERIAL. Applicable to the September 2026 fixture only. No live market rates or customer exchange rates are represented.',
        'fx_rates.sgd_rate means SGD for one unit of the transaction currency. The fixed fixture rates are: SGD = 1.000000; USD = 1.300000; HKD = 0.170000.',
        'For each transactions row, multiply transactions.amount by the matching fx_rates.sgd_rate. Round the converted amount to two decimal places using ROUND_HALF_UP. Store that value in transactions.amount_sgd. A settled payments.amount_sgd row carries the converted value once.',
        'Convert each transaction before aggregation. Do not sum unlike currencies and then apply one rate. Do not apply an FX rate again to payments.amount_sgd, because that field is already in SGD.',
        'The sender account currency determines transaction currency in this fixture. The fixed FX table has no effective-date column. It cannot answer historical daily rates or real-time exchange-rate questions.',
        'The documents and source rows do not contain fees, account balances, profitability, observed exchange-rate movements, or verified AML findings.'
    ]),('finance-settlement-memo.md','Settlement memo: '+tx['transaction_id'],[
        'SYNTHETIC DEMO MATERIAL. This memo is generated from one existing serving record. It adds no new transfer and makes no claim about a real person.',
        f"Record: transactions.transaction_id = {tx['transaction_id']}. Status: {tx['status']}. Channel: {tx['channel']}. Timestamp: {tx['timestamp']}.",
        f"Sender: accounts.account_id = {tx['sender_account_id']}; customers.customer_id = {selected['customer_id']}. Receiver account: {tx['receiver_account_id']}. Sender jurisdiction: {selected['jurisdiction']}.",
        f"Original amount: {tx['amount']} {tx['currency']}. Fixed rate: {rates[tx['currency']]} SGD per {tx['currency']}. Converted settled amount: {selected['amount_sgd']} SGD. UTC booking date: {selected['booking_date']}.",
        'The payments row and its transactions row refer to the same transfer. A document attachment is supporting evidence, not another fact row to add to the payment total.',
        'The source does not identify a merchant, invoice, transfer purpose, rejection reason, or criminal intent. Do not infer those facts from this memo or the transaction graph.'
    ])]
    pdf=fitz.open()
    blue=(0.19,0.35,0.83);ink=(0.14,0.18,0.26)
    def page(title,number):
        p=pdf.new_page(width=595,height=842)
        p.draw_rect(fitz.Rect(0,0,595,9),color=blue,fill=blue)
        p.insert_text((42,42),'SEMANTIC HUB / SYNTHETIC FINANCE',fontsize=10,color=blue)
        assert p.insert_textbox(fitz.Rect(42,64,553,124),title,fontsize=22,fontname='hebo',color=ink)>=0
        p.insert_text((42,815),f'Synthetic fixture evidence | September 2026 | Page {number}',fontsize=9,color=(.4,.45,.5))
        return p
    def prose_page(doc,number):
        filename,title,paragraphs=doc
        (output/filename).write_text('# '+title+'\n\n'+'\n\n'.join(paragraphs)+'\n')
        p=page(title,number)
        assert p.insert_textbox(fitz.Rect(42,140,553,785),'\n\n'.join(paragraphs),fontsize=11,lineheight=1.5,color=ink)>=0
    prose_page(documents[0],1);prose_page(documents[1],2)
    chart=fitz.open();c=chart.new_page(width=1100,height=760)
    c.insert_text((50,55),'SYNTHETIC / SETTLED SENDER OUTFLOW',fontsize=26,fontname='hebo',color=ink)
    c.insert_text((50,92),'1-30 September 2026 (UTC) | Unit: SGD | Group: sender jurisdiction',fontsize=18,color=ink)
    max_amount=max(groups.values())
    for i,(jurisdiction,amount) in enumerate(sorted(groups.items())):
        y=160+i*130;width=float(amount/max_amount)*640
        c.insert_text((50,y+35),jurisdiction,fontsize=24,fontname='hebo',color=ink)
        c.draw_rect(fitz.Rect(135,y,135+width,y+60),color=blue,fill=blue)
        c.insert_text((150+width,y+38),f'{amount:,.2f}',fontsize=23,color=ink)
    c.insert_text((50,640),'Source: payments.csv; SUM(amount_sgd), grouped by jurisdiction.',fontsize=18,color=ink)
    c.insert_text((50,680),'These are fixture totals, not real bank volumes or market shares.',fontsize=18,color=ink)
    png=c.get_pixmap(matrix=fitz.Matrix(1.5,1.5)).tobytes('png');chart.close()
    (output/'finance-settled-outflow-chart.png').write_bytes(png)
    p=page('Visual review: settled outflow by jurisdiction',3)
    p.insert_textbox(fitz.Rect(42,130,553,190),'SYNTHETIC. Chart values are stored as an image. Analyze page 3 with AI and check each proposed row against the labels.',fontsize=11,lineheight=1.4,color=ink)
    p.insert_image(fitz.Rect(25,210,570,640),stream=png)
    p.insert_textbox(fitz.Rect(42,690,553,775),'Creating a model from this chart creates a separate copy of aggregated fixture facts. Do not append its totals to the original payments or join without a reviewed grain rule.',fontsize=11,lineheight=1.4,color=ink)
    prose_page(documents[2],4)
    pdf.set_metadata({'title':'Synthetic Finance Supporting Evidence','author':'Semantic Hub synthetic fixture generator','subject':'Synthetic evidence; not real banking records'})
    (output/'synthetic-finance-supporting-evidence.pdf').write_bytes(pdf.tobytes(deflate=True,no_new_id=True));pdf.close()
    with (output/'finance-chart-row-guide.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['source_page','metric','sender_jurisdiction','period_start','period_end','value','unit'])
        for j,value in sorted(groups.items()):w.writerow([3,'settled_sender_outflow',j,dates[0],dates[-1],str(value),'SGD'])
    (output/'finance-reference.sql').write_text('-- Paste this statement into total_amount_sgd reference SQL.\n-- Use the independent transaction table to reconcile the payments metric.\nSELECT SUM(amount_sgd) AS total_amount_sgd\nFROM transactions\nWHERE status = \'SETTLED\';\n')
    (output/'finance-chart-reference.sql').write_text('-- Presenter check for page 3. This is not the scalar metric verification query.\nSELECT jurisdiction, SUM(amount_sgd) AS settled_sender_outflow_sgd\nFROM payments\nGROUP BY jurisdiction\nORDER BY jurisdiction;\n')
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    manifest={'synthetic':True,'external_records_used':False,'source':'finance serving CSVs only; evaluation files not used',
        'period_start':dates[0],'period_end':dates[-1],'total_amount_sgd':str(total),'settled_payments':len(payments),
        'chart_rows':{k:str(v) for k,v in sorted(groups.items())},'memo_transaction':tx['transaction_id'],
        'input_sha256':{n+'.csv':sha(SERVING/(n+'.csv')) for n in tables},
        'output_sha256':{p.name:sha(p) for p in sorted(output.iterdir()) if p.suffix in {'.md','.pdf','.png','.csv','.sql'}}}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'output':str(output),'total_amount_sgd':str(total),'chart_rows':manifest['chart_rows']}))
    return manifest

if __name__=='__main__':build()
