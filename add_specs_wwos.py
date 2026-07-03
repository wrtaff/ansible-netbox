import subprocess
import sys

with open('brother_ads2000_cleaned.mw', 'r') as f:
    content = f.read()

# Create a specs string to insert
specs = """== Specifications ==
* '''Model:''' Brother ImageCenter™ ADS-2000
* '''Type:''' High-speed, high-volume desktop document scanner
* '''Speed:''' Up to 24 ppm (Black & White and Color)
* '''Duplex Scanning:''' Two-sided scanning in a single pass
* '''ADF Capacity:''' Up to 50-sheet auto document feed capacity
* '''Resolution:''' Up to 600 x 600 dpi (optical), 1200 x 1200 dpi (interpolated)
* '''Maximum Media Size:''' Widths up to 8.5" and lengths up to 34"
* '''Features:''' Multi-feed detection, background removal, blank page removal, deskew support

"""

# Insert specs right before "== Installation =="
content = content.replace("== Installation ==", specs + "== Installation ==")

# Update the page
cmd = [
    'python3', 'scripts/update_wwos_page.py',
    '--page-name', 'Brother ADS2000 High Speed Document Scanner',
    '--full-content', content,
    '--summary', 'Added technical specifications from brother-usa.com'
]
subprocess.run(cmd, check=True)

# Also update Netbox Device description so we can point to it
import os
import requests
TOKEN = os.environ.get('NETBOX_TOKEN', '')
if not TOKEN:
    with open(os.path.expanduser('~/.bashrc')) as f:
        for line in f:
            if 'NETBOX_TOKEN' in line:
                TOKEN = line.split('=')[1].strip().strip('"').strip("'")
                break
headers = {'Authorization': f'Token {TOKEN}', 'Content-Type': 'application/json'}
requests.patch('http://netbox1.home.arpa/api/dcim/devices/253/', headers=headers, json={
    'comments': '## Wiki\n[Brother ADS2000 High Speed Document Scanner](http://wwos.home.arpa/index.php/Brother_ADS2000_High_Speed_Document_Scanner)\n\n## Tickets\n[trac #3607: Provision Brother ADS-2000 Scanner software on zeus](http://trac.home.arpa/ticket/3607)'
})

print("Success")
