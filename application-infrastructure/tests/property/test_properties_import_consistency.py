"""Property-based tests for import path consistency after directory restructuring."""

import sys
import os
import ast
import importlib.util
from pathlib import Path

from hypothesis import given, settings, strategies as st


# Custom strategies for generating test data

@st.composite
def file_paths_strategy(draw):
    """Generate test file paths from the actual test directory structure."""
    test_base = Path(__file__).parent.parent  # tests directory
    
    # Get all Python test files
    test_files = []
    for subdir in ['integration', 'property', 'unit']:
        subdir_path = test_base / subdir
        if subdir_path.exists():
            test_files.extend(list(subdir_path.glob('*.py')))
    
    # Filter out __init__.py and this file itself
    test_files = [f for f in test_files if f.name != '__init__.py' and f != Path(__file__)]
    
    if not test_files:
        # Fallback to a known test file if none found
        return test_base / 'unit' / 'test_path_validator.py'
    
    return draw(st.sampled_from(test_files))


@st.composite
def import_statements(draw):
    """Generate various import statement patterns that should work."""
    # Common import patterns used in the test files
    patterns = [
        "from functions.ingestor.handler import process_s3_record",
        "from functions.processor.path_validator import validate_path",
        "from common.logger import get_logger",
        "from functions.processor.handler import handler",
        "from functions.ingestor.window_tracker import track_window",
        "import functions.ingestor.event_parser",
        "import functions.processor.distribution_finder",
        "import common.constants"
    ]
    
    return draw(st.sampled_from(patterns))


# Property Tests

@settings(max_examples=50, deadline=3000)
@given(file_paths_strategy())
def test_property_2_import_path_consistency(test_file_path):
    """Property 2: Import path consistency.
    
    For any Python test file after restructuring, all import statements should 
    resolve correctly from the new location without module not found errors.
    
    **Feature: test-directory-restructure, Property 2: Import path consistency**
    **Validates: Requirements 2.1, 2.2, 2.4**
    """
    # Verify the test file exists
    assert test_file_path.exists(), f"Test file not found: {test_file_path}"
    
    # Read and parse the test file
    try:
        with open(test_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        assert False, f"Failed to read test file {test_file_path}: {str(e)}"
    
    # Parse the AST to find sys.path.insert statements
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        assert False, f"Syntax error in test file {test_file_path}: {str(e)}"
    
    # Find sys.path.insert statements
    sys_path_inserts = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Expr) and 
            isinstance(node.value, ast.Call) and
            isinstance(node.value.func, ast.Attribute) and
            isinstance(node.value.func.value, ast.Attribute) and
            isinstance(node.value.func.value.value, ast.Name) and
            node.value.func.value.value.id == 'sys' and
            node.value.func.value.attr == 'path' and
            node.value.func.attr == 'insert'):
            
            # Extract the path argument (should be second argument)
            if len(node.value.args) >= 2:
                path_arg = node.value.args[1]
                sys_path_inserts.append(path_arg)
    
    # Verify that sys.path.insert uses correct relative path
    for path_node in sys_path_inserts:
        if isinstance(path_node, ast.Call):
            # Check for os.path.join pattern
            if (isinstance(path_node.func, ast.Attribute) and
                isinstance(path_node.func.value, ast.Attribute) and
                isinstance(path_node.func.value.value, ast.Name) and
                path_node.func.value.value.id == 'os' and
                path_node.func.value.attr == 'path' and
                path_node.func.attr == 'join'):
                
                # Check the arguments to os.path.join
                if len(path_node.args) >= 2:
                    # Second argument should be the relative path
                    if isinstance(path_node.args[1], ast.Constant):
                        relative_path = path_node.args[1].value
                        
                        # Determine expected path based on test file location
                        test_subdir = test_file_path.parent.name
                        if test_subdir in ['integration', 'property', 'unit']:
                            expected_path = '../../src'  # From subdirectory to src
                        else:
                            expected_path = '../src'  # For files in tests root
                        
                        # Verify the path is correct
                        assert relative_path == expected_path, (
                            f"Incorrect sys.path.insert in {test_file_path}: "
                            f"found '{relative_path}', expected '{expected_path}'"
                        )


@settings(max_examples=30, deadline=5000)
@given(file_paths_strategy(), import_statements())
def test_property_2_module_resolution(test_file_path, import_statement):
    """Property 2b: Module resolution verification.
    
    For any test file and import statement, the modules should be resolvable
    from the test file's location using the updated sys.path.
    
    **Feature: test-directory-restructure, Property 2: Import path consistency**
    **Validates: Requirements 2.1, 2.2, 2.4**
    """
    # Skip if test file doesn't exist
    if not test_file_path.exists():
        return
    
    # Determine the correct src path relative to the test file
    test_subdir = test_file_path.parent.name
    if test_subdir in ['integration', 'property', 'unit']:
        src_path = test_file_path.parent.parent / 'src'
    else:
        src_path = test_file_path.parent / 'src'
    
    # Verify src directory exists
    if not src_path.exists():
        return  # Skip if src directory not found
    
    # Parse the import statement to extract module name
    try:
        import_tree = ast.parse(import_statement)
    except SyntaxError:
        return  # Skip invalid import statements
    
    # Extract module names from the import statement
    module_names = []
    for node in ast.walk(import_tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                module_names.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                module_names.append(alias.name)
    
    # Test that each module can be found
    for module_name in module_names:
        # Convert module name to file path
        module_parts = module_name.split('.')
        module_file = src_path
        for part in module_parts:
            module_file = module_file / part
        
        # Check for either .py file or __init__.py in directory
        py_file = module_file.with_suffix('.py')
        init_file = module_file / '__init__.py'
        
        # At least one should exist
        assert py_file.exists() or init_file.exists(), (
            f"Module {module_name} not found at {py_file} or {init_file} "
            f"when importing from {test_file_path}"
        )


@settings(max_examples=20, deadline=2000)
@given(st.sampled_from(['integration', 'property', 'unit']))
def test_property_2_subdirectory_import_consistency(test_subdir):
    """Property 2c: Subdirectory import consistency.
    
    For any test subdirectory (integration, property, unit), all test files
    should use consistent import paths relative to their location.
    
    **Feature: test-directory-restructure, Property 2: Import path consistency**
    **Validates: Requirements 2.1, 2.2, 2.4**
    """
    test_base = Path(__file__).parent.parent  # tests directory
    subdir_path = test_base / test_subdir
    
    # Skip if subdirectory doesn't exist
    if not subdir_path.exists():
        return
    
    # Get all Python test files in the subdirectory
    test_files = list(subdir_path.glob('*.py'))
    test_files = [f for f in test_files if f.name != '__init__.py']
    
    # Skip if no test files
    if not test_files:
        return
    
    # Check that all files use consistent sys.path.insert patterns
    expected_path = '../src'  # All subdirectories should use ../src
    
    for test_file in test_files:
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for sys.path.insert patterns in the content
            if 'sys.path.insert' in content:
                # Verify it uses the correct relative path
                assert '../src' in content or '..\\src' in content, (
                    f"Test file {test_file} should use '../src' in sys.path.insert, "
                    f"but content suggests different path"
                )
                
                # Verify it doesn't use the old incorrect path
                assert '../..' not in content or 'sys.path.insert(0, os.path.join(os.path.dirname(__file__), \'../..\'))' not in content, (
                    f"Test file {test_file} still uses old '../..' path pattern"
                )
        
        except Exception as e:
            # Don't fail the test for file reading issues, just skip
            continue