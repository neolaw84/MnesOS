#!/usr/bin/env python3
"""
Synchronizes the contents of the root `docs/` directory into the `references/`
subdirectory of each agent skill under `.agents/skills/` to enable standalone
agent skill bundles distributed outside the repository.
"""

import os
import sys
import shutil

def sync_references():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    docs_dir = os.path.join(root_dir, 'docs')
    skills_base = os.path.join(root_dir, '.agents', 'skills')

    if not os.path.exists(docs_dir):
        print(f"Error: Source docs directory not found at {docs_dir}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(skills_base):
        print(f"Error: Skills base directory not found at {skills_base}", file=sys.stderr)
        sys.exit(1)

    print("Synchronizing docs/ to skill references/ directories...")
    
    for skill_name in os.listdir(skills_base):
        skill_dir = os.path.join(skills_base, skill_name)
        if not os.path.isdir(skill_dir):
            continue
            
        ref_dir = os.path.join(skill_dir, 'references')
        
        # Ensure clean target directory
        if os.path.exists(ref_dir):
            print(f" -> Cleaning existing references in {skill_name}...")
            shutil.rmtree(ref_dir)
            
        print(f" -> Copying docs tree to {skill_name}/references...")
        shutil.copytree(docs_dir, ref_dir)
        
    print("Successfully synchronized all skill references!")

if __name__ == "__main__":
    sync_references()
