"""Fetch public inputs explicitly. Failure never silently generates substitute data."""
import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
here=Path(__file__).resolve().parent
source=here/'overlay/apps/helios-ds-generation/src' if (here/'overlay').exists() else here.parent/'src'
sys.path.insert(0,str(source))
from helios_ds.sector_demo.__main__ import SOURCES
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
for sector,source in SOURCES.items():
    name=sector+('.json' if sector=='pharma' else '.zip')
    req=urllib.request.Request(source['download'],headers={'User-Agent':'Helios-sector-demo/1.0'})
    with urllib.request.urlopen(req,timeout=60) as response: payload=response.read(100_000_001)
    if len(payload)>100_000_000: raise ValueError('Source exceeds 100 MB download bound')
    (args.output/name).write_bytes(payload)
    (args.output/(name+'.provenance.json')).write_text(json.dumps({'source':source,'sha256':hashlib.sha256(payload).hexdigest(),'retrieved_at_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()},indent=2)+'\n')
    print(sector, len(payload),'bytes')
