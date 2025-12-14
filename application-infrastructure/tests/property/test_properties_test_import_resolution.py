"""Property-based tests for test import resolution."""

import sys
import importlib
import importlib.util
from pathlib import Path
from hypothesis import given, settings, strategies as st


@st.composite
def common_module_names(draw):
    """Generate names of modules that should be available in the common layer."""
    modules = [
        'common',
        'common.logger',
        'common.constants', 
        'common.retry',
        'common.window_tracker'
    ]
    return draw(st.sampled_from(modules))


@settings(max_examples=100)
@given(module_name=common_module_names())
def test_import_resolution_works_automatically(module_name):
    """
    Property 8: Test import resolution works automatically
    
    For any common module, the module should be importable automatically
    without additional configuration when conftest.py is loaded.
    
    **Feature: import-simplification, Property 8: Test import resolution works automatically**
    **Validates: Requirements 3.1**
    """
    # Verify that the module can be imported without any manual path setup
    try:
        # This should work because conftest.py has already set up the path
        module = importlib.import_module(module_name)
        assert module is not None, f"Module {module_name} imported but is None"
        
        # Verify the module has the expected location (from layer)
        if hasattr(module, '__file__') and module.__file__:
            module_path = Path(module.__file__)
            # Should be from the layers/common/python directory
            assert 'layers/common/python' in str(module_path), (
                f"Module {module_name} should be loaded from layers/common/python, "
                f"but was loaded from {module_path}"
            )
            
    except ImportError as e:
        assert False, (
            f"Failed to import {module_name} automatically. "
            f"This indicates test import resolution is not working properly: {e}"
        )


@settings(max_examples=50)
@given(module_name=common_module_names())
def test_no_manual_path_setup_required(module_name):
    """
    Test that common modules can be imported without any manual sys.path manipulation
    in the test file itself.
    
    **Feature: import-simplification, Property 8: Test import resolution works automatically**
    **Validates: Requirements 3.1**
    """
    # Save current sys.path
    original_path = sys.path.copy()
    
    try:
        # Remove any manual additions (simulate a fresh test file)
        # Keep only the paths that conftest.py should have added
        layer_path = str(Path(__file__).parent.parent.parent / "layers" / "common" / "python")
        functions_path = str(Path(__file__).parent.parent.parent / "functions")
        
        # Verify these paths are in sys.path (added by conftest.py)
        assert layer_path in sys.path, f"Layer path {layer_path} should be in sys.path from conftest.py"
        assert functions_path in sys.path, f"Functions path {functions_path} should be in sys.path from conftest.py"
        
        # Import should still work without any additional setup
        module = importlib.import_module(module_name)
        assert module is not None
        
    finally:
        # Restore original sys.path
        sys.path[:] = original_path