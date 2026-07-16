#!/usr/bin/env python3
"""
Syncs Pops single-file markdown skills into the directory-based format required by Antigravity.
Creates proxy directories in ~/.gemini/antigravity-cli/skills/ with a SKILL.md symlink.
"""
import os, glob

def main():
    src_dirs = ['/home/will/pops/skills/domain', '/home/will/pops/skills/core']
    dest_dir = os.path.expanduser('~/.gemini/antigravity-cli/skills')
    os.makedirs(dest_dir, exist_ok=True)

    print(f"Syncing Pops skills to Antigravity format in {dest_dir}...")
    count = 0
    for src_dir in src_dirs:
        for filepath in glob.glob(os.path.join(src_dir, '*.md')):
            filename = os.path.basename(filepath)
            skill_name = filename[:-3]
            if skill_name.lower() == 'readme': continue
            
            proxy_folder = os.path.join(dest_dir, skill_name)
            os.makedirs(proxy_folder, exist_ok=True)
            
            dest_file = os.path.join(proxy_folder, 'SKILL.md')
            if os.path.exists(dest_file):
                os.remove(dest_file)
            os.symlink(filepath, dest_file)
            count += 1
            
    print(f"Successfully linked {count} skills. You can now use @skillname in Antigravity.")

if __name__ == '__main__':
    main()
