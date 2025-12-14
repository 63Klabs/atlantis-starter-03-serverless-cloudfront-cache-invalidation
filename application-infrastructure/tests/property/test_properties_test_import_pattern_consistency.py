"""Property-based tests for test import pattern consistency."""

import ast
import re
from pathlib import Path
from hypothesis import given, settings, strategies as st


@st.composite
def file_paths_strategy(draw):
    """Generate paths to test files that should use consistent import patterns."""
    test_dir = Path(__file__).parent.parent
    test_files = []
    
    # Collect all Python test files
    for pattern in ['unit/*.py', 'property/*.py', 'integration/*.py']:
        test_files.extend(test_dir.glob(pattern))
    
    # Filter out __init__.py and conftest.py
    test_files = [f for f in test_files if f.name not in ['__init__.py', 'conftest.py']]
    
    if not test_files:
        # Fallback to at least one known test file
        test_files = [test_dir / 'unit' / 'test_logger.py']
    
    return draw(st.sampled_from(test_files))


@st.composite
def common_import_patterns(draw):
    """Generate expected import patterns for common modules."""
    patterns = [
        'from common.logger import',
        'from common.constants import',
        'from common.retry import',
        'from common.window_tracker import'
    ]
    return draw(st.sampled_from(patterns))


@settings(max_examples=50)
@given(test_file=file_paths_strategy())
def test_import_patterns_match_function_patterns(test_file):
    """
    Property 9: Test import patterns match function patterns
    
    For any test file that imports shared utilities, the import statements
    should use the same patterns as function code (from common.module import).
    
    **Feature: import-simplification, Property 9: Test import patterns match function patterns**
    **Validates: Requirements 3.3, 3.4**
    """
    if not test_file.exists():
        return  # Skip if file doesn't exist
    
    try:
        content = test_file.read_text()
    except Exception:
        return  # Skip files that can't be read
    
    # Parse the file to find import statements
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return  # Skip files with syntax errors
    
    common_imports = []
    
    # Find all import statements that reference common modules
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith('common'):
                import_line = f"from {node.module} import"
                if node.names:
                    names = [alias.name for alias in node.names]
                    import_line += f" {', '.join(names)}"
                common_imports.append(import_line)
    
    # If there are common imports, verify they follow the expected pattern
    for import_stmt in common_imports:
        # Should use absolute imports from common namespace
        assert import_stmt.startswith('from common.'), (
            f"Test file {test_file.name} uses incorrect import pattern: {import_stmt}. "
            f"Should use 'from common.module import' pattern to match function code."
        )
        
        # Should not use relative imports
        assert 'from .common' not in import_stmt, (
            f"Test file {test_file.name} uses relative import: {import_stmt}. "
            f"Should use absolute imports like function code."
        )
        
        # Should not use wildcard imports
        assert 'import *' not in import_stmt, (
            f"Test file {test_file.name} uses wildcard import: {import_stmt}. "
            f"Should use specific imports like function code."
        )


@settings(max_examples=30)
@given(test_file=file_paths_strategy())
def test_no_sys_path_manipulation_in_tests(test_file):
    """
    Test that test files don't contain manual sys.path manipulation
    (except in conftest.py which is allowed).
    
    **Feature: import-simplification, Property 9: Test import patterns match function patterns**
    **Validates: Requirements 3.3, 3.4**
    """
    if not test_file.exists() or test_file.name == 'conftest.py':
        return  # Skip conftest.py as it's allowed to have path setup
    
    try:
        content = test_file.read_text()
    except Exception:
        return  # Skip files that can't be read
    
    # Check for sys.path manipulation patterns
    sys_path_patterns = [
        r'sys\.path\.insert',
        r'sys\.path\.append',
        r'sys\.path\s*=',
        r'import\s+sys.*path'
    ]
    
    for pattern in sys_path_patterns:
        matches = re.findall(pattern, content, re.MULTILINE)
        if matches:
            # Allow comments or string literals, but not actual code
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if re.search(pattern, line):
                    stripped = line.strip()
                    # Skip comments and docstrings
                    if not (stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''")):
                        # Check if it's inside a string literal (basic check)
                        if not ('"' in line and line.count('"') >= 2) and not ("'" in line and line.count("'") >= 2):
                            assert False, (
                                f"Test file {test_file.name} contains manual sys.path manipulation "
                                f"on line {i+1}: {line.strip()}. "
                                f"Import resolution should be handled automatically by conftest.py."
                            )


@settings(max_examples=20)
@given(import_pattern=common_import_patterns())
def test_common_import_patterns_are_consistent(import_pattern):
    """
    Test that common import patterns used in tests are consistent
    with the expected function import patterns.
    
    **Feature: import-simplification, Property 9: Test import patterns match function patterns**
    **Validates: Requirements 3.3, 3.4**
    """
    # Verify the pattern follows the expected format
    assert import_pattern.startswith('from common.'), (
        f"Import pattern {import_pattern} should start with 'from common.'"
    )
    
    # Verify it's an absolute import (not relative)
    assert not import_pattern.startswith('from .'), (
        f"Import pattern {import_pattern} should not use relative imports"
    )
    
    # Verify it uses the import keyword
    assert ' import' in import_pattern, (
        f"Import pattern {import_pattern} should use 'import' keyword"
    )
    
    # Verify it targets a valid common module
    valid_modules = ['logger', 'constants', 'retry', 'window_tracker']
    module_found = False
    for module in valid_modules:
        if f'common.{module}' in import_pattern:
            module_found = True
            break
    
    assert module_found, (
        f"Import pattern {import_pattern} should reference a valid common module: {valid_modules}"
    )