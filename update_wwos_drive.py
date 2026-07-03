import subprocess
import sys

with open('brother_ads2000_cleaned.mw', 'r') as f:
    content = f.read()

# Replace old wget instructions with the new GDrive links
old_text = """Download Brother's brscan4 `.deb` file from [http://welcome.solutions.brother.com/bsc/public_s/id/linux/en/download_scn.html here].

<pre>
wget http://www.brother.com/pub/bsc/linux/dlf/brscan4-0.4.2-1.i386.deb
sudo dpkg -i brscan4-0.4.2-1.i386.deb
</pre>

Install the `brother-udev-rule` package (not architecture specific):
<pre>
wget http://www.brother.com/pub/bsc/linux/dlf/brother-udev-rule-type1-1.0.0-1.all.deb
sudo dpkg -i brother-udev-rule-type1-1.0.0-1.all.deb 
</pre>"""

new_text = """The required driver files have been archived to Google Drive:
* '''brscan4''' (32-bit): brscan4-0.4.2-1.i386.deb<ref>Google Drive: [https://drive.google.com/file/d/1vPmyhwkcHwBiRg4QKdBYJjsOJaMHlorx/view?usp=drivesdk brscan4-0.4.2-1.i386.deb] retrieved 2026-06-15</ref>
* '''brscan4''' (64-bit): brscan4-0.4.11-1.amd64.deb<ref>Google Drive: [https://drive.google.com/file/d/1v2hybPBbz1QTR68HQ3hEpfrO-ewWNvG_/view?usp=drivesdk brscan4-0.4.11-1.amd64.deb] retrieved 2026-06-15</ref>
* '''brother-udev-rule''': brother-udev-rule-type1-1.0.0-1.all.deb<ref>Google Drive: [https://drive.google.com/file/d/1f1HU-alOOYMbAI4fpRSMxaDHepVfAlsq/view?usp=drivesdk brother-udev-rule-type1-1.0.0-1.all.deb] retrieved 2026-06-15</ref>"""

content = content.replace(old_text, new_text)

with open('brother_ads2000_cleaned.mw', 'w') as f:
    f.write(content)

cmd = [
    'python3', 'scripts/update_wwos_page.py',
    '--page-name', 'Brother ADS2000 High Speed Document Scanner',
    '--full-content', content,
    '--summary', 'Updated driver download links to Google Drive archive'
]
subprocess.run(cmd, check=True)

print("Updated WWOS successfully.")
