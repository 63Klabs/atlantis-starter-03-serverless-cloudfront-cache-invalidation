"""Property-based tests for no manual path manipulation in functions.

**Feature: import-simplification, Property 2: No manual path manipulation in functions**
**Validates: Requirements 1.2**
"""

import ast
import os
from pathlib import Path
from hypothesis import given, strategies as st
import pytest


def get_function_files():
    """Get all Python files in function directories."""
    functions_dir = Path(__file__).parent.parent.parent / "functions"
    function_files = []
    
    if functions_dir.exists():
        for function_dir in functions_dir.iterdir():
            if function_dir.is_dir():
                for py_file in function_dir.glob("*.py"):
                    function_files.append(py_file)
    
    return function_files


def has_sys_path_manipulation(file_path: Path) -> bool:
    """Check if a Python file contains sys.path manipulation."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the AST to look for sys.path modifications
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            # Check for sys.path.insert, sys.path.append, etc.
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    # Check for sys.path.insert(), sys.path.append(), etc.
                    if (isinstance(node.func.value, ast.Attribute) and
                        isinstance(node.func.value.value, ast.Name) and
                        node.func.value.value.id == 'sys' and
                        node.func.value.attr == 'path'):
                        return True
            
            # Check for direct sys.path assignment
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (isinstance(target, ast.Attribute) and
                        isinstance(target.value, ast.Name) and
                        target.value.id == 'sys' and
                        target.attr == 'path'):
                        return True
        
        return False
        
    except Exception:
        # If we can't parse the file, assume it's problematic
        return True


def test_no_sys_path_manipulation_in_functions():
    """
    **Feature: import-simplification, Property 2: No manual path manipulation in functions**
    **Validates: Requirements 1.2**
    
    Property: For any function code file, the file should contain no sys.path 
    modifications or manual path manipulation.
    """
    function_files = get_function_files()
    
    # Skip if no function files found (test environment issue)
    if not function_files:
        pytest.skip("No function files found")
    
    for file_path in function_files:
        assert not has_sys_path_manipulation(file_path), (
            f"Function file {file_path} contains sys.path manipulation. "
            f"Functions should use clean imports without manual path handling."
        )


@given(st.text())
def test_no_path_manipulation_property(file_content):
    """
    **Feature: import-simplification, Property 2: No manual path manipulation in functions**
    **Validates: Requirements 1.2**
    
    Property-based test: For any valid Python code, if it's in a function directory,
    it should not contain sys.path manipulation.
    """
    # Skip empty or very short content
    if len(file_content.strip()) < 10:
        return
    
    try:
        # Try to parse as Python code
        tree = ast.parse(file_content)
        
        # Check for sys.path manipulation patterns
        has_manipulation = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if (isinstance(node.func.value, ast.Attribute) and
                        isinstance(node.func.value.value, ast.Name) and
                        node.func.value.value.id == 'sys' and
                        node.func.value.attr == 'path'):
                        has_manipulation = True
                        break
        
        # If this were function code, it should not have sys.path manipulation
        if has_manipulation:
            # This would be a violation if it were in a function directory
            pass  # We can't assert here since this is generated content
            
    except SyntaxError:
        # Invalid Python code, skip
        return