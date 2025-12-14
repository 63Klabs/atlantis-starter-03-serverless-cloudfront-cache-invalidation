"""
Property-based tests for function packaging separation.

**Feature: import-simplification, Property 7: Function packaging excludes common code**
**Validates: Requirements 2.5**
"""

import os
import tempfile
import zipfile
from pathlib import Path
from hypothesis import given, settings, strategies as st


@st.composite
def function_directories(draw):
    """Generate function directory names that should exist."""
    return draw(st.sampled_from(['functions/ingestor', 'functions/processor']))


@settings(max_examples=10, deadline=5000)
@given(function_path=function_directories())
def test_property_7_function_packaging_excludes_common_code(function_path):
    """
    Property 7: Function packaging excludes common code
    
    For any function package created, the package should contain only 
    function-specific code and no common layer modules.
    
    **Feature: import-simplification, Property 7: Function packaging excludes common code**
    **Validates: Requirements 2.5**
    """
    # Get the function source directory
    app_infra_path = Path(__file__).parent.parent.parent
    function_source_path = app_infra_path / function_path
    
    # Verify source function directory exists
    assert function_source_path.exists(), f"Function source directory does not exist: {function_source_path}"
    
    # Create a temporary directory for packaging simulation
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        package_path = temp_path / "function_package.zip"
        
        # Simulate function packaging by creating a zip file
        # This mirrors what AWS SAM/CloudFormation does
        try:
            with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add all files from the function source
                for root, dirs, files in os.walk(function_source_path):
                    for file in files:
                        file_path = Path(root) / file
                        # Calculate relative path from function source
                        relative_path = file_path.relative_to(function_source_path)
                        zipf.write(file_path, str(relative_path))
        except Exception as e:
            assert False, f"Failed to create function package: {e}"
        
        # Verify the package was created
        assert package_path.exists(), f"Function package was not created: {package_path}"
        assert package_path.stat().st_size > 0, "Function package is empty"
        
        # Extract and verify package structure
        extract_path = temp_path / "extracted"
        extract_path.mkdir()
        
        try:
            with zipfile.ZipFile(package_path, 'r') as zipf:
                zipf.extractall(extract_path)
        except Exception as e:
            assert False, f"Failed to extract function package: {e}"
        
        # Verify handler.py exists (required for Lambda functions)
        handler_file = extract_path / 'handler.py'
        assert handler_file.exists(), (
            f"Function package missing 'handler.py'. "
            f"Lambda functions require a handler module. "
            f"Found files: {[f.name for f in extract_path.iterdir() if f.is_file()]}"
        )
        
        # Verify common layer modules are NOT included in function package
        common_modules = ['logger.py', 'constants.py', 'retry.py', 'window_tracker.py']
        
        for module in common_modules:
            module_file = extract_path / module
            assert not module_file.exists(), (
                f"Function package should NOT contain common module '{module}'. "
                f"Common modules should be provided by the layer, not bundled with functions. "
                f"Found in package: {[f.name for f in extract_path.iterdir() if f.suffix == '.py']}"
            )
        
        # Verify no 'common' directory exists in function package
        common_dir = extract_path / 'common'
        assert not common_dir.exists(), (
            f"Function package should NOT contain 'common' directory. "
            f"Common modules are provided by the layer. "
            f"Found directories: {[d.name for d in extract_path.iterdir() if d.is_dir()]}"
        )
        
        # Verify no 'python' directory exists in function package (that's for layers)
        python_dir = extract_path / 'python'
        assert not python_dir.exists(), (
            f"Function package should NOT contain 'python' directory. "
            f"The python/ structure is for layers, not functions. "
            f"Found directories: {[d.name for d in extract_path.iterdir() if d.is_dir()]}"
        )
        
        # Verify function-specific modules are present
        function_name = function_path.split('/')[-1]  # Extract 'ingestor' or 'processor'
        
        if function_name == 'ingestor':
            expected_modules = ['event_parser.py', 'event_filter.py', 'queue_client.py', 'scheduler_client.py']
        elif function_name == 'processor':
            expected_modules = ['distribution_finder.py', 'invalidation_client.py', 'path_consolidator.py', 
                              'path_validator.py', 'queue_client.py', 'tag_validator.py']
        else:
            expected_modules = []
        
        for module in expected_modules:
            module_file = extract_path / module
            assert module_file.exists(), (
                f"Function package missing expected function-specific module: {module}. "
                f"Found modules: {[f.name for f in extract_path.iterdir() if f.suffix == '.py']}"
            )
        
        # Verify requirements.txt exists (functions should have their own dependencies)
        requirements_file = extract_path / 'requirements.txt'
        assert requirements_file.exists(), (
            f"Function package missing 'requirements.txt'. "
            f"Functions should specify their own dependencies. "
            f"Found files: {[f.name for f in extract_path.iterdir() if f.is_file()]}"
        )


@settings(max_examples=10, deadline=3000)
@given(function_path=function_directories())
def test_property_7_function_source_excludes_common_modules(function_path):
    """
    Property 7b: Function source directories exclude common modules
    
    For any function source directory, it should not contain common layer modules
    that should be provided by the layer.
    
    **Feature: import-simplification, Property 7: Function packaging excludes common code**
    **Validates: Requirements 2.5**
    """
    # Get the function source directory
    app_infra_path = Path(__file__).parent.parent.parent
    function_source_path = app_infra_path / function_path
    
    assert function_source_path.exists(), f"Function source directory does not exist: {function_source_path}"
    
    # Verify common modules are NOT in function source
    common_modules = ['logger.py', 'constants.py', 'retry.py', 'window_tracker.py']
    
    for module in common_modules:
        module_file = function_source_path / module
        assert not module_file.exists(), (
            f"Function source should NOT contain common module '{module}'. "
            f"Common modules should only exist in layers/common/python/common/. "
            f"Found in {function_path}: {[f.name for f in function_source_path.iterdir() if f.suffix == '.py']}"
        )
    
    # Verify no 'common' subdirectory in function source
    common_dir = function_source_path / 'common'
    assert not common_dir.exists(), (
        f"Function source should NOT contain 'common' subdirectory. "
        f"Common modules are provided by the layer. "
        f"Found directories in {function_path}: {[d.name for d in function_source_path.iterdir() if d.is_dir()]}"
    )
    
    # Verify function has its own requirements.txt (not relying on layer requirements)
    requirements_file = function_source_path / 'requirements.txt'
    assert requirements_file.exists(), (
        f"Function source missing 'requirements.txt'. "
        f"Functions should manage their own dependencies separately from the layer."
    )


@settings(max_examples=5, deadline=2000)
@given(st.just('buildspec.yml'))
def test_property_7_build_process_function_separation(buildspec_file):
    """
    Property 7c: Build process maintains function packaging separation
    
    For any build configuration, function packaging should not include
    common layer code and should install dependencies separately.
    
    **Feature: import-simplification, Property 7: Function packaging excludes common code**
    **Validates: Requirements 2.5**
    """
    # Get the buildspec file
    app_infra_path = Path(__file__).parent.parent.parent
    buildspec_path = app_infra_path / buildspec_file
    
    assert buildspec_path.exists(), f"Build specification file does not exist: {buildspec_path}"
    
    # Read buildspec content
    try:
        with open(buildspec_path, 'r', encoding='utf-8') as f:
            buildspec_content = f.read()
    except Exception as e:
        assert False, f"Failed to read buildspec file: {e}"
    
    # Verify function dependencies are installed to function directories (not layer)
    ingestor_install_pattern = 'pip install -r application-infrastructure/functions/ingestor/requirements.txt -t application-infrastructure/functions/ingestor/'
    processor_install_pattern = 'pip install -r application-infrastructure/functions/processor/requirements.txt -t application-infrastructure/functions/processor/'
    
    assert ingestor_install_pattern in buildspec_content, (
        f"Buildspec should install ingestor dependencies to function directory. "
        f"Expected pattern: {ingestor_install_pattern}"
    )
    
    assert processor_install_pattern in buildspec_content, (
        f"Buildspec should install processor dependencies to function directory. "
        f"Expected pattern: {processor_install_pattern}"
    )
    
    # Verify layer dependencies are NOT installed to function directories
    layer_to_function_patterns = [
        'layers/common/requirements.txt -t application-infrastructure/functions/ingestor/',
        'layers/common/requirements.txt -t application-infrastructure/functions/processor/'
    ]
    
    for pattern in layer_to_function_patterns:
        assert pattern not in buildspec_content, (
            f"Buildspec should NOT install layer dependencies to function directories. "
            f"Found problematic pattern: {pattern}"
        )
    
    # Verify function dependencies are NOT installed to layer directory
    function_to_layer_patterns = [
        'functions/ingestor/requirements.txt -t application-infrastructure/layers/common/',
        'functions/processor/requirements.txt -t application-infrastructure/layers/common/'
    ]
    
    for pattern in function_to_layer_patterns:
        assert pattern not in buildspec_content, (
            f"Buildspec should NOT install function dependencies to layer directory. "
            f"Found problematic pattern: {pattern}"
        )
    
    # Verify separate packaging for layer and functions
    assert 'common-layer.zip' in buildspec_content, (
        "Buildspec should create separate layer package (common-layer.zip)"
    )
    
    # Verify layer packaging doesn't include function code
    layer_packaging_section = buildspec_content[buildspec_content.find('common-layer.zip'):buildspec_content.find('common-layer.zip') + 200]
    
    function_patterns_in_layer = ['functions/ingestor', 'functions/processor']
    for pattern in function_patterns_in_layer:
        assert pattern not in layer_packaging_section, (
            f"Layer packaging should not include function directories. "
            f"Found function pattern in layer packaging: {pattern}"
        )


@settings(max_examples=5, deadline=2000)
@given(function_path=function_directories())
def test_property_7_function_imports_use_layer_modules(function_path):
    """
    Property 7d: Function code imports common modules from layer namespace
    
    For any function that uses common utilities, it should import them from
    the common namespace rather than having local copies.
    
    **Feature: import-simplification, Property 7: Function packaging excludes common code**
    **Validates: Requirements 2.5**
    """
    # Get the function source directory
    app_infra_path = Path(__file__).parent.parent.parent
    function_source_path = app_infra_path / function_path
    
    assert function_source_path.exists(), f"Function source directory does not exist: {function_source_path}"
    
    # Check handler.py for proper imports
    handler_file = function_source_path / 'handler.py'
    assert handler_file.exists(), f"Function missing handler.py: {handler_file}"
    
    try:
        with open(handler_file, 'r', encoding='utf-8') as f:
            handler_content = f.read()
    except Exception as e:
        assert False, f"Failed to read handler.py: {e}"
    
    # Verify imports use common namespace (not local modules)
    common_modules = ['logger', 'constants', 'retry', 'window_tracker']
    
    for module in common_modules:
        # Check if module is imported
        if f'import {module}' in handler_content or f'from {module}' in handler_content:
            # If imported, should use common namespace
            correct_import_patterns = [
                f'from common.{module} import',
                f'import common.{module}',
                f'from common import {module}'
            ]
            
            has_correct_import = any(pattern in handler_content for pattern in correct_import_patterns)
            
            # Check for incorrect local imports
            incorrect_import_patterns = [
                f'from .{module} import',
                f'from {module} import',
                f'import {module}'
            ]
            
            has_incorrect_import = any(pattern in handler_content for pattern in incorrect_import_patterns)
            
            if has_incorrect_import and not has_correct_import:
                assert False, (
                    f"Function {function_path} imports {module} incorrectly. "
                    f"Should use 'from common.{module} import ...' instead of local import. "
                    f"This ensures the module comes from the layer, not a local copy."
                )