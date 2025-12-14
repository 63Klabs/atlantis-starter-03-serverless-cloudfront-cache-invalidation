"""
Property-based tests for layer packaging structure correctness.

**Feature: import-simplification, Property 6: Layer packaging structure correctness**
**Validates: Requirements 2.4**
"""

import os
import tempfile
import zipfile
from pathlib import Path
from hypothesis import given, settings, strategies as st
import shutil
import subprocess


@st.composite
def layer_directories(draw):
    """Generate layer directory paths that should exist."""
    return draw(st.sampled_from(['layers/common']))


@settings(max_examples=10, deadline=5000)
@given(layer_path=layer_directories())
def test_property_6_layer_packaging_structure_correctness(layer_path):
    """
    Property 6: Layer packaging structure correctness
    
    For any layer package created, the package should contain the python/common/ 
    directory structure expected by Lambda runtime.
    
    **Feature: import-simplification, Property 6: Layer packaging structure correctness**
    **Validates: Requirements 2.4**
    """
    # Get the layer source directory
    app_infra_path = Path(__file__).parent.parent.parent
    layer_source_path = app_infra_path / layer_path
    
    # Verify source layer directory exists
    assert layer_source_path.exists(), f"Layer source directory does not exist: {layer_source_path}"
    
    # Create a temporary directory for packaging simulation
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        package_path = temp_path / "layer_package.zip"
        
        # Simulate layer packaging by creating a zip file
        # This mirrors what AWS SAM/CloudFormation does
        try:
            with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add all files from the layer source, maintaining structure
                python_source = layer_source_path / 'python'
                if python_source.exists():
                    for root, dirs, files in os.walk(python_source):
                        for file in files:
                            file_path = Path(root) / file
                            # Calculate relative path from layer source
                            relative_path = file_path.relative_to(layer_source_path)
                            zipf.write(file_path, str(relative_path))
        except Exception as e:
            assert False, f"Failed to create layer package: {e}"
        
        # Verify the package was created
        assert package_path.exists(), f"Layer package was not created: {package_path}"
        assert package_path.stat().st_size > 0, "Layer package is empty"
        
        # Extract and verify package structure
        extract_path = temp_path / "extracted"
        extract_path.mkdir()
        
        try:
            with zipfile.ZipFile(package_path, 'r') as zipf:
                zipf.extractall(extract_path)
        except Exception as e:
            assert False, f"Failed to extract layer package: {e}"
        
        # Verify Lambda-expected structure: python/common/
        python_dir = extract_path / 'python'
        assert python_dir.exists(), (
            f"Layer package missing 'python/' directory. "
            f"Lambda expects layers to have python/ at the root. "
            f"Found: {list(extract_path.iterdir())}"
        )
        
        common_dir = python_dir / 'common'
        assert common_dir.exists(), (
            f"Layer package missing 'python/common/' directory. "
            f"Common modules should be in python/common/. "
            f"Found in python/: {list(python_dir.iterdir())}"
        )
        
        # Verify __init__.py exists in common module
        init_file = common_dir / '__init__.py'
        assert init_file.exists(), (
            f"Layer package missing '__init__.py' in python/common/. "
            f"Python modules need __init__.py to be importable. "
            f"Found in python/common/: {list(common_dir.iterdir())}"
        )
        
        # Verify common modules are present
        expected_modules = ['logger.py', 'constants.py', 'retry.py', 'window_tracker.py']
        for module in expected_modules:
            module_file = common_dir / module
            assert module_file.exists(), (
                f"Layer package missing expected common module: {module}. "
                f"Found modules: {[f.name for f in common_dir.iterdir() if f.suffix == '.py']}"
            )
        
        # Verify no files are directly in python/ (should be in python/common/)
        python_files = [f for f in python_dir.iterdir() if f.is_file() and f.suffix == '.py']
        assert len(python_files) == 0, (
            f"Layer package should not have Python files directly in python/. "
            f"All modules should be in python/common/. "
            f"Found files in python/: {[f.name for f in python_files]}"
        )
        
        # Verify no common modules are in the root of the package
        root_python_files = [f for f in extract_path.iterdir() if f.is_file() and f.suffix == '.py']
        common_modules_in_root = [f for f in root_python_files if f.stem in [m.replace('.py', '') for m in expected_modules]]
        assert len(common_modules_in_root) == 0, (
            f"Layer package should not have common modules in root. "
            f"They should be in python/common/. "
            f"Found common modules in root: {[f.name for f in common_modules_in_root]}"
        )


@settings(max_examples=5, deadline=3000)
@given(st.just('layers/common'))
def test_property_6_layer_source_structure_correctness(layer_path):
    """
    Property 6b: Layer source structure correctness
    
    For any layer source directory, it should be organized to produce correct
    packaging structure when processed by build tools.
    
    **Feature: import-simplification, Property 6: Layer packaging structure correctness**
    **Validates: Requirements 2.4**
    """
    # Get the layer source directory
    app_infra_path = Path(__file__).parent.parent.parent
    layer_source_path = app_infra_path / layer_path
    
    assert layer_source_path.exists(), f"Layer source directory does not exist: {layer_source_path}"
    
    # Verify source has correct structure for packaging
    python_dir = layer_source_path / 'python'
    assert python_dir.exists(), (
        f"Layer source missing 'python/' subdirectory. "
        f"This is required for Lambda layer packaging. "
        f"Found: {list(layer_source_path.iterdir())}"
    )
    
    common_dir = python_dir / 'common'
    assert common_dir.exists(), (
        f"Layer source missing 'python/common/' subdirectory. "
        f"Common modules should be organized in python/common/. "
        f"Found in python/: {list(python_dir.iterdir())}"
    )
    
    # Verify requirements.txt is at layer root (not in python/)
    requirements_file = layer_source_path / 'requirements.txt'
    assert requirements_file.exists(), (
        f"Layer source missing 'requirements.txt' at layer root. "
        f"Build tools expect requirements.txt at {layer_source_path}/requirements.txt"
    )
    
    # Verify requirements.txt is NOT in python/ directory
    python_requirements = python_dir / 'requirements.txt'
    assert not python_requirements.exists(), (
        f"Layer source should not have requirements.txt in python/ directory. "
        f"It should be at the layer root for build tools to find it."
    )
    
    # Verify common modules exist and are not empty
    expected_modules = ['logger.py', 'constants.py', 'retry.py', 'window_tracker.py']
    for module in expected_modules:
        module_file = common_dir / module
        assert module_file.exists(), (
            f"Layer source missing expected common module: {module}. "
            f"Found modules: {[f.name for f in common_dir.iterdir() if f.suffix == '.py']}"
        )
        
        assert module_file.stat().st_size > 0, (
            f"Common module {module} is empty. "
            f"Modules should contain actual implementation."
        )


@settings(max_examples=5, deadline=2000)
@given(st.just('buildspec.yml'))
def test_property_6_build_process_layer_packaging(buildspec_file):
    """
    Property 6c: Build process creates correct layer packages
    
    For any build configuration, the layer packaging commands should create
    packages with the correct structure for Lambda deployment.
    
    **Feature: import-simplification, Property 6: Layer packaging structure correctness**
    **Validates: Requirements 2.4**
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
    
    # Verify layer packaging commands are present
    assert 'zip -r' in buildspec_content and 'common-layer.zip' in buildspec_content, (
        "Buildspec should contain layer packaging commands that create common-layer.zip"
    )
    
    # Verify layer packaging uses correct source directory
    assert 'layers/common' in buildspec_content, (
        "Buildspec should package from layers/common directory"
    )
    
    # Verify layer packaging includes python/ directory
    assert 'python/' in buildspec_content, (
        "Buildspec should package the python/ directory for Lambda layer structure"
    )
    
    # Verify layer dependencies are installed to correct location
    layer_install_pattern = 'pip install -r application-infrastructure/layers/common/requirements.txt -t application-infrastructure/layers/common/python/'
    assert layer_install_pattern in buildspec_content, (
        f"Buildspec should install layer dependencies to layers/common/python/. "
        f"Expected pattern: {layer_install_pattern}"
    )
    
    # Verify no function dependencies are mixed with layer packaging
    function_patterns = [
        'functions/ingestor/requirements.txt -t application-infrastructure/layers',
        'functions/processor/requirements.txt -t application-infrastructure/layers'
    ]
    
    for pattern in function_patterns:
        assert pattern not in buildspec_content, (
            f"Buildspec should not install function dependencies to layer directory. "
            f"Found problematic pattern: {pattern}"
        )