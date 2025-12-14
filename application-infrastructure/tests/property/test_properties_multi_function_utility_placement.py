"""Property-based tests for multi-function utility placement."""

import os
from pathlib import Path
from hypothesis import given, settings, strategies as st


@st.composite
def multi_function_utilities(draw):
    """Generate names of utilities that should be used by multiple functions."""
    utilities = [
        'logger',
        'constants', 
        'retry',
        'window_tracker'
    ]
    return draw(st.sampled_from(utilities))


@st.composite
def function_directories(draw):
    """Generate function directory names."""
    functions = ['ingestor', 'processor']
    return draw(st.sampled_from(functions))


@settings(max_examples=100)
@given(utility_name=multi_function_utilities())
def test_multi_function_utilities_in_common_layer(utility_name):
    """
    Property 11: Multi-function utilities in common layer
    
    For any utility module used by multiple functions, the module should be 
    located in the common layer at layers/common/python/common/{utility_name}.py
    
    **Feature: import-simplification, Property 11: Multi-function utilities in common layer**
    **Validates: Requirements 4.1**
    """
    # Path to the common layer utility
    common_layer_path = Path(__file__).parent.parent.parent / "layers" / "common" / "python" / "common" / f"{utility_name}.py"
    
    # Verify the utility exists in the common layer
    assert common_layer_path.exists(), (
        f"Multi-function utility '{utility_name}' should exist in common layer at {common_layer_path}"
    )
    
    # Verify it's a proper Python file (not empty, has some content)
    assert common_layer_path.stat().st_size > 0, (
        f"Multi-function utility '{utility_name}' in common layer should not be empty"
    )


@settings(max_examples=100)
@given(utility_name=multi_function_utilities(), function_dir=function_directories())
def test_no_duplicate_utilities_in_functions(utility_name, function_dir):
    """
    Test that multi-function utilities are not duplicated in function directories.
    
    **Feature: import-simplification, Property 11: Multi-function utilities in common layer**
    **Validates: Requirements 4.1**
    """
    # Path to potential duplicate in function directory
    function_utility_path = Path(__file__).parent.parent.parent / "functions" / function_dir / f"{utility_name}.py"
    
    # Verify the utility does NOT exist in function directories (no duplicates)
    assert not function_utility_path.exists(), (
        f"Multi-function utility '{utility_name}' should not be duplicated in function directory {function_dir}. "
        f"Found duplicate at {function_utility_path}. It should only exist in the common layer."
    )


@settings(max_examples=50)
@given(utility_name=multi_function_utilities())
def test_common_utilities_importable_from_common_namespace(utility_name):
    """
    Test that multi-function utilities can be imported from the common namespace.
    
    **Feature: import-simplification, Property 11: Multi-function utilities in common layer**
    **Validates: Requirements 4.1**
    """
    try:
        # Should be able to import from common namespace
        import importlib
        module = importlib.import_module(f'common.{utility_name}')
        assert module is not None, f"Module common.{utility_name} imported but is None"
        
        # Verify the module comes from the correct location
        if hasattr(module, '__file__') and module.__file__:
            module_path = Path(module.__file__)
            assert 'layers/common/python/common' in str(module_path), (
                f"Module common.{utility_name} should be loaded from layers/common/python/common, "
                f"but was loaded from {module_path}"
            )
            
    except ImportError as e:
        assert False, (
            f"Failed to import common.{utility_name}. "
            f"Multi-function utility should be importable from common namespace: {e}"
        )