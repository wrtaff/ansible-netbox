import subprocess
import os

os.chdir('/home/will/ansible-netbox/scripts')

pb_content = """'''[[Playbooks/install_czkawka.yml|install_czkawka.yml]]''' is an [[Ansible playbook]] that installs the [[Czkawka]] duplicate file finder (CLI and GUI).

== See also ==
* '''[[Czkawka]]''' — the parent application.

{{bop}}
[[Category: Ansible_playbooks]]
"""

with open("/tmp/pb_content.txt", "w") as f:
    f.write(pb_content)

subprocess.run(["python3", "create_wwos_page.py", "Playbooks/install_czkawka.yml", "Ansible_playbooks"], check=False)
subprocess.run(["python3", "update_wwos_page.py", "--page-name", "Playbooks/install_czkawka.yml", "--full-content", pb_content], check=True)

res = subprocess.run(["python3", "get_wwos_page.py", "Czkawka"], capture_output=True, text=True, check=True)
cz_content = res.stdout

if "== Ansible playbook ==" not in cz_content:
    if "{{bop}}" in cz_content:
        new_cz = cz_content.replace("{{bop}}", "== Ansible playbook ==\\n* '''[[Playbooks/install_czkawka.yml]]'''\\n\\n{{bop}}")
    elif "[[Category:" in cz_content:
        new_cz = cz_content.replace("[[Category:", "== Ansible playbook ==\\n* '''[[Playbooks/install_czkawka.yml]]'''\\n\\n{{bop}}\\n[[Category:")
    else:
        new_cz = cz_content + "\\n\\n== Ansible playbook ==\\n* '''[[Playbooks/install_czkawka.yml]]'''\\n\\n{{bop}}\\n[[Category: Data deduplication]]"

    with open("/tmp/cz_content.txt", "w") as f:
        f.write(new_cz)

    subprocess.run(["python3", "update_wwos_page.py", "--page-name", "Czkawka", "--full-content", new_cz], check=True)
    print("Updated Czkawka page.")
else:
    print("Czkawka already has Ansible playbook section.")
