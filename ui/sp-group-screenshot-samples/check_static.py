"""Offline content checks. Browser layout acceptance remains a separate check."""
import csv
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
root=Path(__file__).resolve().parent
pack=root.parents[1]/'apps/helios-ds-generation/fixtures/sectors/v1/power'
fixture=json.loads((root/'sample-data.json').read_text())['power']
rows=list(csv.DictReader((pack/'serving/meter_readings.csv').open()))
valid=[r for r in rows if r['quality_status']=='VALID' and r['is_estimated']=='false']
assert sum(Decimal(r['import_kwh']) for r in valid)==sum(Decimal(v) for v in fixture['import_kwh'])
assert len(valid)==sum(fixture['valid_readings'])
assert fixture['fixture_sha256']==hashlib.sha256((pack/'manifest.json').read_bytes()).hexdigest()
models=json.loads((root/'context-models.json').read_text())['models']
context=(root/'context.html').read_text()
embedded=json.loads(re.search(r'const models=(.*?);\nfunction escapeText',context,re.S)[1])
assert embedded==models
for model in models: assert len(model['definitions'])==model['count']
for name in ['index','context','nifi','observability','data']:
    text=(root/(name+'.html')).read_text()
    assert not re.search(r'banking|payment|SGD|currency|jurisdiction|reversal',text,re.I),name
    assert 'SP Group' in text and 'sp-group-logo' in text
    for href in re.findall(r'href="([^"]+)"',text):
        if href.endswith('.html'): assert (root/href).is_file(),href
    for tag in ['div','section','aside','main']:
        assert len(re.findall('<'+tag+r'\b',text))==text.count('</'+tag+'>'),(name,tag)
data=(root/'data.html').read_text()
assert '8,547.28 kWh' in data and '3,960' in data
assert "quality_status = 'VALID' AND is_estimated = 'false'" in data
assert 'fictional' in data.lower()
print('PASS: five power pages, linked navigation, embedded models, balanced containers and fixture-derived energy totals.')
