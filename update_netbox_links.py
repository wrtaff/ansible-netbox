import subprocess

with open('brother_ads2000_cleaned.mw', 'r') as f:
    content = f.read()

new_netbox = """== NetBox ==
* Scanner Device: [http://netbox1.home.arpa/dcim/devices/253/ brother-ads-2000]
* Host Device (Logically attached): [http://netbox1.home.arpa/dcim/devices/7/ zeus]
* Host Interface (Physically attached): [http://netbox1.home.arpa/dcim/interfaces/449/ usb-6 on Anker Hub]"""

content = content.replace("== NetBox ==\n* Device (Logically attached): [http://netbox1.home.arpa/dcim/devices/7/ zeus]\n* Interface (Physically attached): [http://netbox1.home.arpa/dcim/interfaces/449/ usb-6 on Anker Hub]", new_netbox)

cmd = [
    'python3', 'scripts/update_wwos_page.py',
    '--page-name', 'Brother ADS2000 High Speed Document Scanner',
    '--full-content', content,
    '--summary', 'Added link to dedicated NetBox device'
]
subprocess.run(cmd, check=True)
