"""Property-based tests for Lambda function deployment isolation."""

import os
import sys
from pathlib import Path
from typing import Set, List

from hypothesis import given, settings, strategies as st


# Custom strategies for generating test data

@st.composite
def function_names(draw):
    """Generate Lambda function names that should be isolated."""
    functions = ['ingestor', 'processor']
    return draw(st.sampled_from(functions))


@st.composite
def function_directories(draw):
    """Generate function directory paths."""
    base_path = Path(__file__).parent.parent.parent  # application-infrastructure
    function_name = draw(function_names())
    return base_path / 'functions' / function_name


@st.composite
def function_file_pairs(draw):
    """Generate pairs of function names for cross-contamination testing."""
    functions = ['ingestor', 'processor']
    func1 = draw(st.sampled_from(functions))
    func2 = draw(st.sampled_from([f for f in functions if f != func1]))
    return (func1, func2)


def get_python_files_in_directory(directory: Path) -> Set[str]:
    """Get all Python files in a directory recursively.
    
    Args:
        directory: Directory to scan
        
    Returns:
        Set of relative file paths (without .py extension)
    """
    if not directory.exists():
        return set()
    
    python_files = set()
    for py_file in directory.rglob('*.py'):
        if py_file.name != '__init__.py':  # Exclude __init__.py files
            # Get relative path from directory and remove .py extension
            rel_path = py_file.relative_to(directory)
            module_path = str(rel_path.with_suffix(''))
            python_files.add(module_path)
    
    return python_files


def get_function_specific_modules(function_name: str) -> Set[str]:
    """Get modules that should be specific to a function.
    
    Args:
        function_name: Name of the function (ingestor or processor)
        
    Returns:
        Set of module names that should only exist in this function
    """
    if function_name == 'ingestor':
        return {
            'handler',
            'event_parser', 
            'event_filter',
            'queue_client',
            'scheduler_client',
            'window_tracker'
        }
    elif function_name == 'processor':
        return {
            'handler',
            'distribution_finder',
            'invalidation_client', 
            'path_consolidator',
            'path_validator',
            'queue_client',
            'tag_validator'
        }
    else:
        return set()


def get_common_modules() -> Set[str]:
    """Get modules that should be in the common layer, not in functions.
    
    Returns:
        Set of module names that should only exist in the layer
    """
    return {
        'constants',
        'logger',
        'retry'
    }


# Property Tests

@settings(max_examples=100, deadline=3000)
@given(function_names())
def test_property_1_function_deployment_isolation(function_name):
    """Property 1: Function deployment isolation.
    
    For any Lambda function deployment package, the package should contain only 
    code specific to that function and not include code from other functions.
    
    **Feature: lambda-function-separation, Property 1: Function deployment isolation**
    **Validates: Requirements 1.2, 4.1**
    """
    base_path = Path(__file__).parent.parent.parent  # application-infrastructure
    function_dir = base_path / 'functions' / function_name
    
    # Skip test if function directory doesn't exist yet
    if not function_dir.exists():
        return
    
    # Get all Python modules in this function directory
    function_modules = get_python_files_in_directory(function_dir)
    
    # Get modules that should be specific to this function
    expected_modules = get_function_specific_modules(function_name)
    
    # Get modules that should NOT be in any function (common modules)
    common_modules = get_common_modules()
    
    # Verify function contains its expected modules
    for expected_module in expected_modules:
        assert expected_module in function_modules, (
            f"Function {function_name} missing expected module: {expected_module}"
        )
    
    # Verify function does NOT contain common modules (they should be in layer)
    for common_module in common_modules:
        assert common_module not in function_modules, (
            f"Function {function_name} contains common module {common_module} "
            f"that should be in the layer, not the function directory"
        )
    
    # Verify function does NOT contain modules from other functions
    other_functions = ['ingestor', 'processor']
    other_functions.remove(function_name)
    
    for other_function in other_functions:
        other_function_modules = get_function_specific_modules(other_function)
        for other_module in other_function_modules:
            # Skip modules that might legitimately exist in multiple functions
            # (like 'handler' or 'queue_client' which can have different implementations)
            if other_module in expected_modules:
                continue
                
            assert other_module not in function_modules, (
                f"Function {function_name} contains module {other_module} "
                f"that should only exist in function {other_function}"
            )


@settings(max_examples=50, deadline=2000)
@given(function_file_pairs())
def test_property_1_cross_function_isolation(function_pair):
    """Property 1b: Cross-function isolation validation.
    
    For any pair of Lambda functions, neither should contain modules that
    belong specifically to the other function.
    
    **Feature: lambda-function-separation, Property 1: Function deployment isolation**
    **Validates: Requirements 1.2, 4.1**
    """
    func1_name, func2_name = function_pair
    base_path = Path(__file__).parent.parent.parent  # application-infrastructure
    
    func1_dir = base_path / 'functions' / func1_name
    func2_dir = base_path / 'functions' / func2_name
    
    # Skip test if either function directory doesn't exist yet
    if not func1_dir.exists() or not func2_dir.exists():
        return
    
    # Get modules in each function
    func1_modules = get_python_files_in_directory(func1_dir)
    func2_modules = get_python_files_in_directory(func2_dir)
    
    # Get function-specific modules for each
    func1_specific = get_function_specific_modules(func1_name)
    func2_specific = get_function_specific_modules(func2_name)
    
    # Find modules that should be unique to each function
    func1_unique = func1_specific - func2_specific
    func2_unique = func2_specific - func1_specific
    
    # Verify func1 doesn't contain func2's unique modules
    for func2_unique_module in func2_unique:
        assert func2_unique_module not in func1_modules, (
            f"Function {func1_name} contains module {func2_unique_module} "
            f"that should only exist in function {func2_name}"
        )
    
    # Verify func2 doesn't contain func1's unique modules  
    for func1_unique_module in func1_unique:
        assert func1_unique_module not in func2_modules, (
            f"Function {func2_name} contains module {func1_unique_module} "
            f"that should only exist in function {func1_name}"
        )


@settings(max_examples=30, deadline=2000)
@given(function_names())
def test_property_1_function_requirements_isolation(function_name):
    """Property 1c: Function requirements file isolation.
    
    For any Lambda function, it should have its own requirements.txt file
    for function-specific dependencies, separate from other functions and the layer.
    
    **Feature: lambda-function-separation, Property 1: Function deployment isolation**
    **Validates: Requirements 1.2, 4.1**
    """
    base_path = Path(__file__).parent.parent.parent  # application-infrastructure
    function_dir = base_path / 'functions' / function_name
    
    # Skip test if function directory doesn't exist yet
    if not function_dir.exists():
        return
    
    # Verify function has its own requirements.txt
    requirements_file = function_dir / 'requirements.txt'
    assert requirements_file.exists(), (
        f"Function {function_name} missing requirements.txt file"
    )
    
    # Verify requirements file is readable
    try:
        with open(requirements_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        assert False, f"Failed to read requirements file for {function_name}: {str(e)}"
    
    # Verify file has some content (even if just comments)
    assert len(content.strip()) > 0, (
        f"Requirements file is empty for function {function_name}"
    )
    
    # Verify requirements file is function-specific (contains function name or relevant dependencies)
    content_lower = content.lower()
    assert function_name in content_lower or 'boto3' in content_lower or 'function' in content_lower, (
        f"Requirements file for {function_name} should contain function-specific content"
    )


@settings(max_examples=20, deadline=1500)
@given(function_names())
def test_property_1_function_directory_structure(function_name):
    """Property 1d: Function directory structure validation.
    
    For any Lambda function, its directory should contain only the files
    necessary for that specific function's operation.
    
    **Feature: lambda-function-separation, Property 1: Function deployment isolation**
    **Validates: Requirements 1.2, 4.1**
    """
    base_path = Path(__file__).parent.parent.parent  # application-infrastructure
    function_dir = base_path / 'functions' / function_name
    
    # Skip test if function directory doesn't exist yet
    if not function_dir.exists():
        return
    
    # Get all files in the function directory
    all_files = list(function_dir.rglob('*'))
    python_files = [f for f in all_files if f.suffix == '.py']
    other_files = [f for f in all_files if f.is_file() and f.suffix != '.py']
    
    # Verify function has Python files
    assert len(python_files) > 0, (
        f"Function {function_name} directory contains no Python files"
    )
    
    # Verify function has handler.py (required for Lambda functions)
    handler_file = function_dir / 'handler.py'
    assert handler_file.exists(), (
        f"Function {function_name} missing required handler.py file"
    )
    
    # Verify non-Python files are appropriate for a function directory
    allowed_extensions = {'.txt', '.md', '.json', '.yml', '.yaml', '.pyc'}
    for other_file in other_files:
        if other_file.name.startswith('.'):
            continue  # Skip hidden files
        # Skip files in __pycache__ directories
        if '__pycache__' in str(other_file):
            continue
        assert other_file.suffix in allowed_extensions, (
            f"Function {function_name} contains unexpected file: {other_file.name}"
        )
    
    # Verify no subdirectories (functions should be flat)
    subdirs = [f for f in all_files if f.is_dir()]
    # Allow __pycache__ directories
    non_cache_subdirs = [d for d in subdirs if not d.name.startswith('__pycache__')]
    assert len(non_cache_subdirs) == 0, (
        f"Function {function_name} should not contain subdirectories, found: "
        f"{[d.name for d in non_cache_subdirs]}"
    )


@settings(max_examples=10, deadline=1000)
@given(st.just('functions'))
def test_property_1_functions_directory_isolation(functions_dir_name):
    """Property 1e: Functions directory isolation validation.
    
    For any functions directory, it should only contain individual function
    directories and no shared code or common modules.
    
    **Feature: lambda-function-separation, Property 1: Function deployment isolation**
    **Validates: Requirements 1.2, 4.1**
    """
    base_path = Path(__file__).parent.parent.parent  # application-infrastructure
    functions_dir = base_path / functions_dir_name
    
    # Skip test if functions directory doesn't exist yet
    if not functions_dir.exists():
        return
    
    # Get all items in functions directory
    items = list(functions_dir.iterdir())
    
    # Verify all items are directories (no loose files)
    for item in items:
        if item.name.startswith('.'):
            continue  # Skip hidden files/directories
        assert item.is_dir(), (
            f"Functions directory contains non-directory item: {item.name}"
        )
    
    # Verify directory names match expected function names
    expected_functions = {'ingestor', 'processor'}
    actual_functions = {item.name for item in items if item.is_dir() and not item.name.startswith('.')}
    
    # Allow subset (functions may not all be moved yet)
    unexpected_functions = actual_functions - expected_functions
    assert len(unexpected_functions) == 0, (
        f"Functions directory contains unexpected function directories: {unexpected_functions}"
    )
    
    # Verify no common modules exist directly in functions directory
    common_modules = get_common_modules()
    for item in items:
        if item.is_file() and item.suffix == '.py':
            module_name = item.stem
            assert module_name not in common_modules, (
                f"Functions directory contains common module {module_name} "
                f"that should be in the layer"
            )