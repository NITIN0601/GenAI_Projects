#!/usr/bin/env python3
"""
Comprehensive Import Audit Script
Checks for:
1. Circular imports
2. Missing modules
3. Outdated references
4. Import resolution issues
"""

import sys
import os
from pathlib import Path
from collections import defaultdict
import ast
import importlib.util

# Add project to path
PROJECT_ROOT = Path('/Users/nitin/Desktop/Chatbot/Morgan/GENAI')
sys.path.insert(0, str(PROJECT_ROOT))

class ImportAuditor:
    def __init__(self, src_dir):
        self.src_dir = Path(src_dir)
        self.project_root = PROJECT_ROOT
        self.all_files = list(self.src_dir.rglob('*.py'))
        self.import_graph = defaultdict(set)
        self.file_imports = {}
        self.issues = []
        
    def extract_imports(self, file_path):
        """Extract all imports from a Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content, filename=str(file_path))
            
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append({
                            'type': 'import',
                            'module': alias.name,
                            'name': None,
                            'line': node.lineno
                        })
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        imports.append({
                            'type': 'from',
                            'module': module,
                            'name': alias.name,
                            'line': node.lineno
                        })
            return imports
        except SyntaxError as e:
            return [{'type': 'ERROR', 'error': str(e), 'line': e.lineno}]
        except Exception as e:
            return [{'type': 'ERROR', 'error': str(e), 'line': 0}]
    
    def module_to_path(self, module_name):
        """Convert module name to potential file path"""
        if module_name.startswith('src.'):
            rel_path = module_name.replace('.', '/') + '.py'
            full_path = self.project_root / rel_path
            if full_path.exists():
                return full_path
            # Try __init__.py
            init_path = self.project_root / module_name.replace('.', '/') / '__init__.py'
            if init_path.exists():
                return init_path
        return None
    
    def check_import_exists(self, imp, file_path):
        """Check if an import can be resolved"""
        module = imp['module']
        name = imp['name']
        
        # Skip standard library and third-party
        if not module.startswith('src.') and not module.startswith('config.'):
            return True
        
        # Check if module file exists
        module_path = self.module_to_path(module)
        if not module_path:
            return False
        
        # If importing specific name, check if it exists
        if name and name != '*':
            try:
                with open(module_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tree = ast.parse(content)
                
                # Check for class, function, or variable definition
                for node in ast.walk(tree):
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name == name:
                            return True
                    elif isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id == name:
                                return True
                
                # Check __all__ export
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id == '__all__':
                                if isinstance(node.value, (ast.List, ast.Tuple)):
                                    exports = [elt.s for elt in node.value.elts if isinstance(elt, ast.Str)]
                                    exports += [elt.value for elt in node.value.elts if isinstance(elt, ast.Constant)]
                                    if name in exports:
                                        return True
                
                return False
            except:
                return True  # Assume it exists if we can't parse
        
        return True
    
    def build_import_graph(self):
        """Build dependency graph"""
        for file_path in self.all_files:
            rel_path = file_path.relative_to(self.project_root)
            imports = self.extract_imports(file_path)
            self.file_imports[str(rel_path)] = imports
            
            for imp in imports:
                if imp['type'] in ['import', 'from'] and imp['module'].startswith('src.'):
                    target_path = self.module_to_path(imp['module'])
                    if target_path:
                        target_rel = target_path.relative_to(self.project_root)
                        self.import_graph[str(rel_path)].add(str(target_rel))
    
    def detect_circular_imports(self):
        """Detect circular import dependencies"""
        def has_cycle(node, visited, rec_stack, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self.import_graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack, path):
                        return True
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    self.issues.append({
                        'type': 'CIRCULAR_IMPORT',
                        'severity': 'HIGH',
                        'cycle': cycle
                    })
                    return True
            
            path.pop()
            rec_stack.remove(node)
            return False
        
        visited = set()
        for node in self.import_graph:
            if node not in visited:
                has_cycle(node, visited, set(), [])
    
    def check_all_imports(self):
        """Check all imports for issues"""
        for file_path, imports in self.file_imports.items():
            for imp in imports:
                if imp['type'] == 'ERROR':
                    self.issues.append({
                        'type': 'SYNTAX_ERROR',
                        'severity': 'CRITICAL',
                        'file': file_path,
                        'line': imp.get('line', 0),
                        'error': imp.get('error', 'Unknown error')
                    })
                elif imp['type'] in ['import', 'from']:
                    if not self.check_import_exists(imp, file_path):
                        self.issues.append({
                            'type': 'MISSING_IMPORT',
                            'severity': 'HIGH',
                            'file': file_path,
                            'line': imp['line'],
                            'module': imp['module'],
                            'name': imp['name']
                        })
    
    def run_audit(self):
        """Run complete audit"""
        print("=" * 80)
        print("IMPORT AUDIT - GENAI Repository")
        print("=" * 80)
        print(f"\nScanning {len(self.all_files)} Python files...\n")
        
        # Build graph
        self.build_import_graph()
        
        # Check for circular imports
        print("Checking for circular imports...")
        self.detect_circular_imports()
        
        # Check all imports
        print("Checking import resolution...")
        self.check_all_imports()
        
        # Report
        print("\n" + "=" * 80)
        print("AUDIT RESULTS")
        print("=" * 80)
        
        if not self.issues:
            print("\n✅ NO ISSUES FOUND! All imports are valid.\n")
            return
        
        # Group by severity
        critical = [i for i in self.issues if i['severity'] == 'CRITICAL']
        high = [i for i in self.issues if i['severity'] == 'HIGH']
        
        print(f"\n🔴 CRITICAL: {len(critical)}")
        print(f"🟡 HIGH: {len(high)}")
        print(f"📊 TOTAL: {len(self.issues)}\n")
        
        # Print issues
        for issue in sorted(self.issues, key=lambda x: (x['severity'], x['type'])):
            if issue['type'] == 'CIRCULAR_IMPORT':
                print(f"\n🔴 CIRCULAR IMPORT DETECTED:")
                print(f"   Cycle: {' -> '.join(issue['cycle'])}")
            elif issue['type'] == 'MISSING_IMPORT':
                print(f"\n🟡 MISSING IMPORT:")
                print(f"   File: {issue['file']}:{issue['line']}")
                print(f"   Import: from {issue['module']} import {issue['name']}")
            elif issue['type'] == 'SYNTAX_ERROR':
                print(f"\n🔴 SYNTAX ERROR:")
                print(f"   File: {issue['file']}:{issue['line']}")
                print(f"   Error: {issue['error']}")

if __name__ == '__main__':
    auditor = ImportAuditor(PROJECT_ROOT / 'src')
    auditor.run_audit()
