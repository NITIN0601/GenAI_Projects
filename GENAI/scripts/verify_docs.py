#!/usr/bin/env python3
"""
Verify markdown documentation structure and links.
"""
import re
from pathlib import Path
from typing import List, Tuple

def check_markdown_links(md_file: Path) -> List[Tuple[str, str]]:
    """Check for broken links in a markdown file."""
    content = md_file.read_text()
    # Find all markdown links [text](path)
    links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
    
    broken = []
    for text, link in links:
        # Skip external links and anchors
        if link.startswith(('http://', 'https://', '#', 'file://')):
            continue
        
        # Resolve relative path
        link_path = (md_file.parent / link).resolve()
        if not link_path.exists():
            broken.append((text, link))
    
    return broken

def main():
    """Main verification function."""
    base_path = Path('/Users/nitin/Desktop/Chatbot/Morgan/GENAI')
    
    print("=" * 70)
    print("📋 DOCUMENTATION VERIFICATION REPORT")
    print("=" * 70)
    
    # Count markdown files
    active_md = list(base_path.glob('*.md'))
    docs_md = list((base_path / 'docs').glob('*.md'))
    scripts_md = list((base_path / 'scripts').glob('*.md'))
    tests_md = list((base_path / 'tests').glob('*.md'))
    archive_md = list((base_path / 'archive').rglob('*.md'))
    
    print(f"\n📊 File Count:")
    print(f"  Root directory:     {len(active_md)} files")
    print(f"  docs/ directory:    {len(docs_md)} files")
    print(f"  scripts/ directory: {len(scripts_md)} files")
    print(f"  tests/ directory:   {len(tests_md)} files")
    print(f"  archive/ directory: {len(archive_md)} files")
    print(f"  TOTAL:              {len(active_md) + len(docs_md) + len(scripts_md) + len(tests_md) + len(archive_md)} files")
    
    print(f"\n📁 Root Directory Files:")
    for md_file in sorted(active_md):
        print(f"  [OK] {md_file.name}")
    
    # Check for broken links in active docs
    print(f"\n🔗 Link Verification:")
    all_broken = {}
    
    for md_file in active_md + docs_md + scripts_md + tests_md:
        broken = check_markdown_links(md_file)
        if broken:
            all_broken[str(md_file.relative_to(base_path))] = broken
    
    if all_broken:
        print("  ❌ Broken links found:")
        for file, links in all_broken.items():
            print(f"\n  {file}:")
            for text, link in links:
                print(f"    - [{text}]({link})")
    else:
        print("  ✅ No broken links found in active documentation!")
    
    # Verify key files exist
    print(f"\n📄 Key Files Check:")
    key_files = [
        'README.md',
        'DOCUMENTATION.md',
        'GETTING_STARTED.md',
        'USAGE_GUIDE.md',
        'SYSTEM_OVERVIEW.md',
        'MIGRATION_GUIDE.md',
        'ENTERPRISE_FEATURES.md',
        'docs/README.md',
        'docs/UNIFIED_EXTRACTION.md',
        'scripts/README.md',
        'tests/README.md',
    ]
    
    for key_file in key_files:
        file_path = base_path / key_file
        if file_path.exists():
            print(f"  [OK] {key_file}")
        else:
            print(f"  ❌ MISSING: {key_file}")
    
    # Verify archive structure
    print(f"\n📦 Archive Structure:")
    consolidation_dir = base_path / 'archive' / 'consolidation'
    old_docs_dir = base_path / 'archive' / 'old_docs'
    
    if consolidation_dir.exists():
        consolidation_files = list(consolidation_dir.glob('*.md'))
        print(f"  [OK] archive/consolidation/ - {len(consolidation_files)} files")
    else:
        print(f"  ❌ archive/consolidation/ - NOT FOUND")
    
    if old_docs_dir.exists():
        old_docs_files = list(old_docs_dir.glob('*.md'))
        print(f"  [OK] archive/old_docs/ - {len(old_docs_files)} files")
    else:
        print(f"  ❌ archive/old_docs/ - NOT FOUND")
    
    print("\n" + "=" * 70)
    print("✅ VERIFICATION COMPLETE")
    print("=" * 70)

if __name__ == '__main__':
    main()
