#!/usr/bin/env python3
"""
Auto-fix test files to include authentication headers.
"""
import re
from pathlib import Path
import sys

def fix_test_file(filepath):
    """Add auth_headers to client requests in test file."""
    print(f"Processing: {filepath}")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    original = content
    modified = content
    
    # Fix 1: Add mock_auth_service to client fixtures that don't have it
    # Look for @pytest.fixture\ndef client(...): pattern
    def add_mock_auth_to_fixture(match):
        fixture_def = match.group(0)
        params = match.group(1)
        # Only add if not already present
        if 'mock_auth_service' not in params:
            if params.strip():
                new_params = params + ', mock_auth_service'
            else:
                new_params = 'mock_auth_service'
            return fixture_def.replace(f'def client({params}):', f'def client({new_params}):')
        return fixture_def
    
    # Find client fixtures and add mock_auth_service parameter
    modified = re.sub(
        r'@pytest\.fixture\s+def client\(([^)]*)\):',
        add_mock_auth_to_fixture,
        modified
    )
    
    # Fix 2: Add auth_headers to test method signatures if calling authenticated endpoints
    # Pattern: def test_xyz(self, client, ...) where there's a client.get/post/etc call
    def add_auth_headers_param(match):
        method_sig = match.group(0)
        if 'auth_headers' in method_sig:
            return method_sig  # Already has it
        # Insert auth_headers before the closing )
        return method_sig.replace('):', ', auth_headers):')
    
    # Add auth_headers parameter to test methods that use client requests
    # This is a bit broad but safer than missing some
    modified = re.sub(
        r'def (test_\w+)\(self,\s*client[^)]*\):',
        add_auth_headers_param,
        modified
    )
    
    # Fix 3: Add headers=auth_headers to client requests
    # Pattern variations to handle:
    # - client.get("/path")
    # - client.post("/path", json={...})
    # - client.post("/path", data={...})
    # - client.post("/path", files={...})
    
    # Handle simple case: client.METHOD("/path")
    modified = re.sub(
        r'client\.(get|post|put|delete|patch)\((["\'][^"\']+["\'])\)(?!\s*,\s*headers)',
        r'client.\1(\2, headers=auth_headers)',
        modified
    )
    
    # Handle with json: client.METHOD("/path", json=...)
    # Only add headers if not already present
    modified = re.sub(
        r'client\.(get|post|put|delete|patch)\((["\'][^"\']+["\']),\s*json=(?![^)]*headers=)',
        r'client.\1(\2, headers=auth_headers, json=',
        modified
    )
    
    # Handle with data: client.METHOD("/path", data=...)
    modified = re.sub(
        r'client\.(get|post|put|delete|patch)\((["\'][^"\']+["\']),\s*data=(?![^)]*headers=)',
        r'client.\1(\2, headers=auth_headers, data=',
        modified
    )
    
    # Handle with files: client.METHOD("/path", files=...)
    modified = re.sub(
        r'client\.(post)\((["\'][^"\']+["\']),\s*files=(?![^)]*headers=)',
        r'client.\1(\2, headers=auth_headers, files=',
        modified
    )
    
    # Handle with params: client.METHOD("/path", params=...)
    modified = re.sub(
        r'client\.(get|post|put|delete|patch)\((["\'][^"\']+["\']),\s*params=(?![^)]*headers=)',
        r'client.\1(\2, headers=auth_headers, params=',
        modified
    )
    
    # Fix 4: Don't add headers to health endpoints (they should be unauthenticated)
    # Remove headers from /api/health, /api/readiness, /
    for health_path in ['/api/health', '/api/readiness', '/']:
        modified = re.sub(
            rf'client\.(get|post)\(["\']({re.escape(health_path)})["\'],\s*headers=auth_headers,?\s*',
            r'client.\1("\2", ',
            modified
        )
        modified = re.sub(
            rf'client\.(get|post)\(["\']({re.escape(health_path)})["\'],\s*headers=auth_headers\)',
            r'client.\1("\2")',
            modified
        )
    
    # Write back if modified
    if modified != original:
        with open(filepath, 'w') as f:
            f.write(modified)
        print(f"  ✅ Fixed: {filepath}")
        return True
    else:
        print(f"  ⏭️  Skipped (no changes needed): {filepath}")
        return False

def main():
    # Find all test files
    test_dir = Path("backend/tests")
    if not test_dir.exists():
        print(f"Error: {test_dir} not found!")
        sys.exit(1)
    
    fixed_count = 0
    skipped_count = 0
    
    for test_file in sorted(test_dir.rglob("test_*.py")):
        # Skip conftest.py
        if 'conftest' in str(test_file):
            continue
        
        if fix_test_file(test_file):
            fixed_count += 1
        else:
            skipped_count += 1
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Fixed: {fixed_count} files")
    print(f"  Skipped: {skipped_count} files")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()

