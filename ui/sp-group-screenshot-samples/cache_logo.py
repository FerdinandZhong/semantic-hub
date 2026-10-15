"""Embed the published SP Group logo for offline screenshot pages."""
import base64
from pathlib import Path
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parent
URL='https://isomer-user-content.by.gov.sg/302/316d5d40-0b43-4a81-ab58-c4edd8b076f2/sp_group.png'
asset=ROOT/'assets/sp-group.png'
if asset.exists():image=asset.read_bytes()
else:
    with urlopen(Request(URL,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as response:image=response.read(5_000_001)
if not image.startswith(b'\x89PNG\r\n\x1a\n') or len(image)>5_000_000:raise ValueError('Expected the published PNG logo, smaller than 5 MB.')
asset.parent.mkdir(exist_ok=True);asset.write_bytes(image)
uri='data:image/png;base64,'+base64.b64encode(image).decode('ascii')
for page in ROOT.glob('*.html'):
    source=page.read_text()
    source=source.replace('src="'+URL+'"','src="'+uri+'"')
    page.write_text(source)
print('Published logo embedded in all five pages. They can now open fully offline.')
