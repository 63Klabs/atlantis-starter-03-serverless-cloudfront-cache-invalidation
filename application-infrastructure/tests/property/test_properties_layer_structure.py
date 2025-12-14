"""Property-based tests for Lambda layer structure and dependency resolution."""

import sys
import os
import ast
import importlib.util
from pathlib import Path

# Layer path is now configured in conftest.py - no manual setup needed

from hypothesis import given, settings, strategies as st


# Custom strategies for generating test data

@st.composite
def layer_module_names(draw):
    """Generate module names that should be available in the common layer."""
    # These are the modules that were moved to the layer
    modules = [
        'common',
        'common.constants',
        'common.logger', 
        'common.retry'
    ]
    return draw(st.sampled_from(modules))


@st.composite
def layer_import_statements(draw):
    """Generate import statements that should work with the layer structure."""
    # Import patterns that functions should use to access layer code
    patterns = [
        "import common",
        "import common.constants",
        "import common.logger",
        "import common.retry",
        "from common import constants",
        "from common import logger",
        "from common import retry",
        "from common.constants import MAX_RETRY_ATTEMPTS_SQS",
        "from common.logger import setup_logger",
        "from common.retry import retry_with_backoff"
    ]
    return draw(st.sampled_from(patterns))


@st.composite
def function_directories(draw):
    """Generate function directory paths that should use the layer."""
    # These are the function directories that will use the layer
    base_path = Path(__file__).parent.parent.parent  # application-infrastructure
    function_dirs = [
        base_path / 'functions' / 'ingestor',
        base_path / 'functions' / 'processor'
    ]
    # Only return existing directories
    existing_dirs = [d for d in function_dirs if d.exists()]
    if not existing_dirs:
        # Return a placeholder if directories don't exist yet
        return base_path / 'functions' / 'ingestor'
    return draw(st.sampled_from(existing_dirs))


# Property Tests

@settings(max_examples=100, deadline=5000)
@given(layer_module_names())
def test_property_2_layer_dependency_resolution(module_name):
    """Property 2: Layer dependency resolution.
    
    For any function that uses common code, all imports from the common layer 
    should resolve correctly at runtime.
    
    **Feature: lambda-function-separation, Property 2: Layer dependency resolution**
    **Validates: Requirements 2.3, 3.3, 3.4**
    """
    # Verify the layer directory structure exists
    layer_base = Path(__file__).parent.parent.parent / 'layers' / 'common'
    assert layer_base.exists(), f"Layer base directory not found: {layer_base}"
    
    layer_python_path = layer_base / 'python'
    assert layer_python_path.exists(), f"Layer python directory not found: {layer_python_path}"
    
    # Verify the module can be imported from the layer structure
    try:
        # Try to import the module using importlib
        spec = importlib.util.find_spec(module_name)
        assert spec is not None, f"Module {module_name} not found in layer structure"
        
        # Verify the module file exists in the expected layer location
        if spec.origin:
            module_path = Path(spec.origin).resolve()
            layer_python_path_resolved = layer_python_path.resolve()
            # Should be within the layer python directory
            assert layer_python_path_resolved in module_path.parents, (
                f"Module {module_name} found at {module_path}, "
                f"but should be within layer path {layer_python_path_resolved}"
            )
        
        # Try to actually import the module
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Verify module loaded successfully
        assert module is not None, f"Failed to load module {module_name}"
        
    except ImportError as e:
        assert False, f"Failed to import {module_name} from layer: {str(e)}"
    except Exception as e:
        assert False, f"Unexpected error importing {module_name}: {str(e)}"


@settings(max_examples=50, deadline=3000)
@given(layer_import_statements())
def test_property_2_layer_import_syntax(import_statement):
    """Property 2b: Layer import syntax validation.
    
    For any valid import statement targeting layer modules, the import should
    execute successfully without syntax or resolution errors.
    
    **Feature: lambda-function-separation, Property 2: Layer dependency resolution**
    **Validates: Requirements 2.3, 3.3, 3.4**
    """
    # Verify the import statement is syntactically valid
    try:
        ast.parse(import_statement)
    except SyntaxError as e:
        assert False, f"Invalid import syntax: {import_statement} - {str(e)}"
    
    # Try to execute the import statement
    try:
        # Create a temporary namespace for the import
        temp_namespace = {}
        exec(import_statement, temp_namespace)
        
        # Verify something was imported (namespace should have new entries)
        # Filter out built-ins that are always present
        imported_items = {k: v for k, v in temp_namespace.items() 
                         if not k.startswith('__')}
        assert len(imported_items) > 0, (
            f"Import statement '{import_statement}' did not import anything"
        )
        
    except ImportError as e:
        assert False, f"Import failed: {import_statement} - {str(e)}"
    except Exception as e:
        assert False, f"Unexpected error executing import: {import_statement} - {str(e)}"


@settings(max_examples=30, deadline=2000)
@given(st.sampled_from(['constants', 'logger', 'retry']))
def test_property_2_layer_module_structure(module_name):
    """Property 2c: Layer module structure validation.
    
    For any common module in the layer, it should maintain the same structure
    and functionality as the original module.
    
    **Feature: lambda-function-separation, Property 2: Layer dependency resolution**
    **Validates: Requirements 2.3, 3.3, 3.4**
    """
    # Import the module from the layer
    full_module_name = f'common.{module_name}'
    
    try:
        module = __import__(full_module_name, fromlist=[module_name])
    except ImportError as e:
        assert False, f"Failed to import {full_module_name}: {str(e)}"
    
    # Verify module has expected attributes based on module type
    if module_name == 'constants':
        # Constants module should have key configuration constants
        expected_attrs = [
            'AGGREGATION_WINDOW_SECONDS',
            'MAX_RETRY_ATTEMPTS_SQS',
            'RETRY_INITIAL_DELAY_MS',
            'MAX_PATHS_PER_INVALIDATION'
        ]
        for attr in expected_attrs:
            assert hasattr(module, attr), (
                f"Constants module missing expected attribute: {attr}"
            )
    
    elif module_name == 'logger':
        # Logger module should have key functions and classes
        expected_attrs = [
            'JSONFormatter',
            'get_log_level',
            'setup_logger',
            'log_with_context'
        ]
        for attr in expected_attrs:
            assert hasattr(module, attr), (
                f"Logger module missing expected attribute: {attr}"
            )
    
    elif module_name == 'retry':
        # Retry module should have retry functions
        expected_attrs = [
            'calculate_delay_with_jitter',
            'retry_with_backoff'
        ]
        for attr in expected_attrs:
            assert hasattr(module, attr), (
                f"Retry module missing expected attribute: {attr}"
            )


@settings(max_examples=20, deadline=2000)
@given(st.just('common'))
def test_property_2_layer_package_structure(package_name):
    """Property 2d: Layer package structure validation.
    
    For any package in the layer, it should be properly structured as a Python
    package with correct __init__.py and module organization.
    
    **Feature: lambda-function-separation, Property 2: Layer dependency resolution**
    **Validates: Requirements 2.3, 3.3, 3.4**
    """
    # Verify the package can be imported
    try:
        package = __import__(package_name)
    except ImportError as e:
        assert False, f"Failed to import package {package_name}: {str(e)}"
    
    # Verify package has __file__ attribute (indicates proper package structure)
    assert hasattr(package, '__file__'), (
        f"Package {package_name} missing __file__ attribute"
    )
    
    # Verify package file is in the expected layer location
    if package.__file__:
        package_path = Path(package.__file__).resolve()
        layer_python_path = Path(__file__).parent.parent.parent / 'layers' / 'common' / 'python'
        layer_python_path_resolved = layer_python_path.resolve()
        
        assert layer_python_path_resolved in package_path.parents, (
            f"Package {package_name} found at {package_path}, "
            f"but should be within layer path {layer_python_path_resolved}"
        )
    
    # Verify package directory contains expected modules
    package_dir = Path(package.__file__).parent
    expected_modules = ['constants.py', 'logger.py', 'retry.py', '__init__.py']
    
    for module_file in expected_modules:
        module_path = package_dir / module_file
        assert module_path.exists(), (
            f"Package {package_name} missing expected module: {module_file}"
        )


@settings(max_examples=10, deadline=1000)
@given(st.just('requirements.txt'))
def test_property_2_layer_requirements_file(requirements_file):
    """Property 2e: Layer requirements file validation.
    
    For any layer, it should have a properly structured requirements.txt file
    for dependency management.
    
    **Feature: lambda-function-separation, Property 2: Layer dependency resolution**
    **Validates: Requirements 2.3, 3.3, 3.4**
    """
    # Verify requirements.txt exists in layer directory
    layer_base = Path(__file__).parent.parent.parent / 'layers' / 'common'
    requirements_path = layer_base / requirements_file
    
    assert requirements_path.exists(), (
        f"Layer requirements file not found: {requirements_path}"
    )
    
    # Verify file is readable
    try:
        with open(requirements_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        assert False, f"Failed to read requirements file: {str(e)}"
    
    # Verify file has some content (even if just comments)
    assert len(content.strip()) > 0, (
        f"Requirements file is empty: {requirements_path}"
    )
    
    # For this layer, verify it documents that no external dependencies are needed
    # (since common modules only use standard library)
    content_lower = content.lower()
    assert 'standard library' in content_lower or 'no external' in content_lower, (
        f"Requirements file should document that only standard library is used"
    )