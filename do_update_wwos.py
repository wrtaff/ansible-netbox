import subprocess
import sys

# 1. Update the Scanner Page
with open('brother_ads2000_cleaned.mw', 'r') as f:
    content = f.read()

cmd = [
    'python3', 'scripts/update_wwos_page.py',
    '--page-name', 'Brother ADS2000 High Speed Document Scanner',
    '--full-content', content,
    '--summary', 'Added links to Trac #3607, NetBox, and Playbook'
]
subprocess.run(cmd, check=True)

# 2. Create the Playbook Page
playbook_content = """'''[[Playbooks/brother_scanner]]''' deploys the driver and automation for the Brother ADS-2000 Document Scanner.

== See also ==
* '''[[Brother ADS2000 High Speed Document Scanner]]''' — Device details and manual configuration notes.

== Trac ==
'''[http://trac.home.arpa/ticket/3607 trac #3607 "Provision Brother ADS-2000 Scanner software on zeus"]'''

{{bop}}
[[Category:Playbooks]]
"""

with open('playbook_temp.mw', 'w') as f:
    f.write(playbook_content)

cmd_create = [
    'python3', 'scripts/create_wwos_page.py',
    'Playbooks/brother_scanner',
    'playbook_temp.mw',
    '--categories', 'Playbooks'
]
subprocess.run(cmd_create, check=True)

cmd_update = [
    'python3', 'scripts/update_wwos_page.py',
    '--page-name', 'Playbooks/brother_scanner',
    '--full-content', playbook_content,
    '--summary', 'Initial creation'
]
subprocess.run(cmd_update, check=True)

print("Done updating and creating pages.")
