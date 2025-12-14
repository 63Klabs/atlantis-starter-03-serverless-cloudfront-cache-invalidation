"""Property-based tests for single-function utilities placement.

**Feature: import-simplification, Property 12: Single-function utilities stay with functions**
**Validates: Requirements 4.2**
"""

import os
from pathlib import Path
from hypothesis import given, strategies as st
import pytest


def get_function_specific_modules():
    """Get modules that should be specific to individual functions."""
    # Based on the design document, these modules are function-specific
    ingestor_specific = [
        'event_parser.py',
        'event_filter.py', 
        'queue_client.py',
        'scheduler_client.py'
    ]
    
    processor_specific = [
        'distribution_finder.py',
        'invalidation_client.py',
        'path_consolidator.py',
        'path_validator.py',
        'queue_client.py',
        'tag_validator.py'
    ]
    
    return {
        'ingestor': ingestor_specific,
        'processor': processor_specific
    }


def get_functions_dir():
    """Get the functions directory path."""
    return Path(__file__).parent.parent.parent / "functions"


def test_single_function_utilities_stay_with_functions():
    """
    **Feature: import-simplification, Property 12: Single-function utilities stay with functions**
    **Validates: Requirements 4.2**
    
    Property: For any utility module used by only one function, the module should 
    remain in that function's directory.
    """
    functions_dir = get_functions_dir()
    
    if not functions_dir.exists():
        pytest.skip("Functions directory not found")
    
    function_specific_modules = get_function_specific_modules()
    
    for function_name, expected_modules in function_specific_modules.items():
        function_dir = functions_dir / function_name
        
        if not function_dir.exists():
            continue
            
        for module_name in expected_modules:
            module_path = function_dir / module_name
            
            # Check that the module exists in the function directory
            assert module_path.exists(), (
                f"Function-specific module {module_name} should exist in "
                f"{function_name} directory at {module_path}"
            )
            
            # Check that it's not in the common layer
            common_layer_path = (
                functions_dir.parent / "layers" / "common" / "python" / "common" / module_name
            )
            assert not common_layer_path.exists(), (
                f"Single-function module {module_name} should not be in common layer. "
                f"Found at {common_layer_path}"
            )


def test_no_duplicate_modules_across_functions():
    """
    **Feature: import-simplification, Property 12: Single-function utilities stay with functions**
    **Validates: Requirements 4.2**
    
    Property: Function-specific modules should not be duplicated across functions
    (except for modules with the same name but different purposes like queue_client).
    """
    functions_dir = get_functions_dir()
    
    if not functions_dir.exists():
        pytest.skip("Functions directory not found")
    
    # Collect all Python modules from all function directories
    function_modules = {}
    
    for function_dir in functions_dir.iterdir():
        if function_dir.is_dir() and not function_dir.name.startswith('.'):
            modules = []
            for py_file in function_dir.glob("*.py"):
                if py_file.name != "__init__.py" and py_file.name != "handler.py":
                    modules.append(py_file.name)
            function_modules[function_dir.name] = modules
    
    # Check for unexpected duplicates (queue_client is expected to be duplicated)
    all_modules = []
    for function_name, modules in function_modules.items():
        for module in modules:
            all_modules.append((function_name, module))
    
    # Group by module name
    module_locations = {}
    for function_name, module in all_modules:
        if module not in module_locations:
            module_locations[module] = []
        module_locations[module].append(function_name)
    
    # Check for unexpected duplicates
    for module_name, locations in module_locations.items():
        if len(locations) > 1:
            # queue_client is expected to be in both functions with different implementations
            if module_name == "queue_client.py":
                continue
            
            # Other modules should not be duplicated
            assert False, (
                f"Module {module_name} found in multiple functions: {locations}. "
                f"Single-function utilities should stay with their specific function."
            )


@given(st.text(min_size=1, max_size=50))
def test_module_placement_property(module_name):
    """
    **Feature: import-simplification, Property 12: Single-function utilities stay with functions**
    **Validates: Requirements 4.2**
    
    Property-based test: For any module name, if it exists in a function directory,
    it should be function-specific and not in the common layer (unless it's a known shared module).
    """
    # Skip invalid module names
    if not module_name.isidentifier() or module_name.startswith('_'):
        return
    
    functions_dir = get_functions_dir()
    if not functions_dir.exists():
        return
    
    # Known shared modules that should be in common layer
    shared_modules = {'logger.py', 'constants.py', 'retry.py', 'window_tracker.py'}
    
    module_filename = f"{module_name}.py"
    
    # Check if module exists in any function directory
    found_in_functions = []
    for function_dir in functions_dir.iterdir():
        if function_dir.is_dir():
            module_path = function_dir / module_filename
            if module_path.exists():
                found_in_functions.append(function_dir.name)
    
    # If found in function directories
    if found_in_functions:
        # Should not be a shared module in common layer (unless it's a known shared module)
        if module_filename not in shared_modules:
            common_layer_path = (
                functions_dir.parent / "layers" / "common" / "python" / "common" / module_filename
            )
            
            # If it exists in common layer, it should be a shared module
            if common_layer_path.exists():
                assert module_filename in shared_modules, (
                    f"Module {module_filename} found in both function directories {found_in_functions} "
                    f"and common layer. Single-function utilities should stay with functions."
                )