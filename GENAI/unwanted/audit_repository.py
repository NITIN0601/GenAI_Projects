#!/usr/bin/env python3
"""
Repository audit script - analyzes all files and categorizes them.
"""

import os
from pathlib import Path
from collections import defaultdict
import json

def audit_repository(base_path):
    """Audit the repository and categorize files."""
    
    categories = {
        'core_modules': [],
        'test_scripts': [],
        'extraction_scripts': [],
        'duplicate_scripts': [],
        'output_files': [],
        'config_files': [],
        'documentation': []
    }
    
    # Walk through directory
    for root, dirs, files in os.walk(base_path):
        # Skip unwanted directory
        if 'unwanted' in root or '__pycache__' in root or '.git' in root:
            continue
        
        for file in files:
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, base_path)
            
            # Categorize
            if file.endswith('.py'):
                if 'test' in file.lower():
                    categories['test_scripts'].append(rel_path)
                elif 'extract' in file.lower() or 'debug' in file.lower() or 'search' in file.lower():
                    categories['extraction_scripts'].append(rel_path)
                elif any(x in rel_path for x in ['models/', 'embeddings/', 'scrapers/', 'rag/', 'cache/', 'config/', 'utils/']):
                    categories['core_modules'].append(rel_path)
                else:
                    categories['extraction_scripts'].append(rel_path)
            
            elif file.endswith(('.json', '.csv', '.log')):
                categories['output_files'].append(rel_path)
            
            elif file.endswith(('.md', '.txt', '.sh')):
                categories['documentation'].append(rel_path)
    
    return categories

if __name__ == "__main__":
    base_path = "/Users/nitin/Desktop/Chatbot/Morgan/GENAI"
    categories = audit_repository(base_path)
    
    print("\n=== REPOSITORY AUDIT ===\n")
    
    for category, files in categories.items():
        print(f"\n{category.upper().replace('_', ' ')} ({len(files)}):")
        for f in sorted(files):
            print(f"  - {f}")
    
    # Save to JSON
    with open('repository_audit.json', 'w') as f:
        json.dump(categories, f, indent=2)
    
    print(f"\n\nAudit saved to repository_audit.json")
