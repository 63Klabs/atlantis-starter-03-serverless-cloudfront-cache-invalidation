"""
Property-based tests for deployment artifact structure correctness.

**Feature: import-simplification, Property 15: Deployment artifact structure correctness**
**Validates: Requirements 5.3**
"""

import os
import tempfile
import zipfile
import yaml
from pathlib import Path
from hypothesis import given, settings, strategies as st
import re


@st.composite
def deployment_artifacts(draw):
    """Generate deployment artifact types that should be created."""
    return draw(st.sampled_from(['layer', 'function']))


@settings(max_examples=5, deadline=3000)
@given(st.just('template.yml'))
def test_property_15_cloudformation_template_artifact_references(template_file):
    """
    Property 15: Deployment artifact structure correctness
    
    For any CloudFormation template, it should reference deployment artifacts
    with the correct structure expected by Lambda runtime.
    
    **Feature: import-simplification, Property 15: Deployment artifact structure correctness**
    **Validates: Requirements 5.3**
    """
    # Get the template path
    app_infra_path = Path(__file__).parent.parent.parent
    template_path = app_infra_path / template_file
    
    assert template_path.exists(), f"CloudFormation template does not exist: {template_path}"
    
    # Read template content
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
    except Exception as e:
        assert False, f"Failed to read CloudFormation template: {e}"
    
    # Verify template references correct artifact structure
    
    # Check CodeUri patterns for functions
    code_uri_matches = re.findall(r'CodeUri:\s*([^\s\n]+)', template_content)
    assert len(code_uri_matches) > 0, "Template should have CodeUri references for Lambda functions"
    
    for code_uri in code_uri_matches:
        # Should reference functions directory with correct structure
        assert code_uri.startswith('functions/'), (
            f"CodeUri should reference functions/ directory. Got: {code_uri}"
        )
        
        # Should reference specific function subdirectories
        valid_functions = ['functions/ingestor/', 'functions/processor/']
        assert any(code_uri.startswith(func) for func in valid_functions), (
            f"CodeUri should reference valid function directory. "
            f"Expected one of {valid_functions}, got: {code_uri}"
        )
    
    # Check ContentUri patterns for layers
    content_uri_matches = re.findall(r'ContentUri:\s*([^\s\n]+)', template_content)
    
    for content_uri in content_uri_matches:
        # Should reference layers directory with correct structure
        assert content_uri.startswith('layers/'), (
            f"ContentUri should reference layers/ directory. Got: {content_uri}"
        )
        
        # Should reference common layer specifically
        assert content_uri.startswith('layers/common'), (
            f"ContentUri should reference layers/common/ directory. Got: {content_uri}"
        )
    
    # Verify layer references use proper CloudFormation patterns
    layer_ref_pattern = r'Layers:\s*\n\s*-\s*!Ref\s+(\w+)'
    layer_refs = re.findall(layer_ref_pattern, template_content)
    
    assert len(layer_refs) > 0, (
        "Template should have layer references using !Ref pattern"
    )
    
    # Verify layer resources are defined
    for layer_ref in layer_refs:
        layer_definition_pattern = f'{layer_ref}:\\s*\\n\\s*Type:\\s*AWS::Serverless::LayerVersion'
        assert re.search(layer_definition_pattern, template_content), (
            f"Layer {layer_ref} should be defined as AWS::Serverless::LayerVersion"
        )


@settings(max_examples=5, deadline=2000)
@given(st.just('buildspec.yml'))
def test_property_15_build_artifacts_match_lambda_expectations(buildspec_file):
    """
    Property 15b: Build artifacts match Lambda deployment expectations
    
    For any build process, the created artifacts should match the structure
    and format expected by AWS Lambda deployment.
    
    **Feature: import-simplification, Property 15: Deployment artifact structure correctness**
    **Validates: Requirements 5.3**
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
    
    # Verify layer packaging creates Lambda-compatible structure
    assert 'zip -r' in buildspec_content and 'common-layer.zip' in buildspec_content, (
        "Build should create layer zip file for Lambda deployment"
    )
    
    # Verify layer packaging includes python/ directory (Lambda requirement)
    layer_zip_context = buildspec_content[buildspec_content.find('common-layer.zip') - 100:buildspec_content.find('common-layer.zip') + 100]
    assert 'python/' in layer_zip_context, (
        "Layer packaging should include python/ directory as required by Lambda"
    )
    
    # Verify dependencies are installed to correct locations for Lambda
    layer_deps_pattern = 'pip install -r application-infrastructure/layers/common/requirements.txt -t application-infrastructure/layers/common/python/'
    assert layer_deps_pattern in buildspec_content, (
        f"Layer dependencies should be installed to python/ directory. Expected: {layer_deps_pattern}"
    )
    
    # Verify function dependencies are installed to function root (Lambda expectation)
    function_deps_patterns = [
        'pip install -r application-infrastructure/functions/ingestor/requirements.txt -t application-infrastructure/functions/ingestor/',
        'pip install -r application-infrastructure/functions/processor/requirements.txt -t application-infrastructure/functions/processor/'
    ]
    
    for pattern in function_deps_patterns:
        assert pattern in buildspec_content, (
            f"Function dependencies should be installed to function root for Lambda. Expected: {pattern}"
        )
    
    # Verify CloudFormation packaging is included
    assert 'aws cloudformation package' in buildspec_content, (
        "Build should include CloudFormation packaging for deployment"
    )
    
    # Verify S3 bucket is used for artifact storage
    assert '--s3-bucket' in buildspec_content, (
        "CloudFormation packaging should use S3 bucket for artifact storage"
    )


@settings(max_examples=3, deadline=4000)
@given(st.just('layers/common'))
def test_property_15_layer_artifact_lambda_compatibility(layer_path):
    """
    Property 15c: Layer artifacts are Lambda runtime compatible
    
    For any layer artifact structure, it should be compatible with
    Lambda's runtime import resolution and path expectations.
    
    **Feature: import-simplification, Property 15: Deployment artifact structure correctness**
    **Validates: Requirements 5.3**
    """
    # Get the layer source directory
    app_infra_path = Path(__file__).parent.parent.parent
    layer_source_path = app_infra_path / layer_path
    
    assert layer_source_path.exists(), f"Layer source directory does not exist: {layer_source_path}"
    
    # Simulate Lambda runtime structure validation
    python_dir = layer_source_path / 'python'
    assert python_dir.exists(), (
        f"Layer missing python/ directory. Lambda expects layers to have python/ at root."
    )
    
    common_dir = python_dir / 'common'
    assert common_dir.exists(), (
        f"Layer missing python/common/ directory. Common modules should be in python/common/ for Lambda import resolution."
    )
    
    # Verify Lambda-compatible module structure
    init_file = common_dir / '__init__.py'
    assert init_file.exists(), (
        f"Layer missing __init__.py in python/common/. Lambda requires __init__.py for module imports."
    )
    
    # Verify common modules are present and Lambda-importable
    expected_modules = ['logger.py', 'constants.py', 'retry.py', 'window_tracker.py']
    for module in expected_modules:
        module_file = common_dir / module
        assert module_file.exists(), (
            f"Layer missing expected module {module} in python/common/. "
            f"Lambda functions expect these modules to be available for import."
        )
        
        # Verify module is not empty (Lambda would fail to import empty modules)
        assert module_file.stat().st_size > 0, (
            f"Module {module} is empty. Lambda requires modules to have actual content."
        )
    
    # Verify no conflicting files in python/ root (Lambda import resolution)
    python_files = [f for f in python_dir.iterdir() if f.is_file() and f.suffix == '.py']
    assert len(python_files) == 0, (
        f"Layer should not have Python files directly in python/ directory. "
        f"Lambda import resolution expects modules in subdirectories. "
        f"Found: {[f.name for f in python_files]}"
    )
    
    # Verify no problematic system files that could interfere with Lambda
    # Note: __pycache__ is acceptable as it gets cleaned during packaging
    problematic_files = ['.DS_Store', 'Thumbs.db']
    problematic_dirs = ['.git']
    
    for root, dirs, files in os.walk(python_dir):
        for file in files:
            assert file not in problematic_files, (
                f"Layer contains problematic system file {file} that could interfere with Lambda deployment"
            )
        for dir_name in dirs:
            assert dir_name not in problematic_dirs, (
                f"Layer contains problematic system directory {dir_name} that could interfere with Lambda deployment"
            )


@settings(max_examples=3, deadline=3000)
@given(function_path=st.sampled_from(['functions/ingestor', 'functions/processor']))
def test_property_15_function_artifact_lambda_compatibility(function_path):
    """
    Property 15d: Function artifacts are Lambda runtime compatible
    
    For any function artifact structure, it should be compatible with
    Lambda's runtime execution and import expectations.
    
    **Feature: import-simplification, Property 15: Deployment artifact structure correctness**
    **Validates: Requirements 5.3**
    """
    # Get the function source directory
    app_infra_path = Path(__file__).parent.parent.parent
    function_source_path = app_infra_path / function_path
    
    assert function_source_path.exists(), f"Function source directory does not exist: {function_source_path}"
    
    # Verify Lambda handler requirements
    handler_file = function_source_path / 'handler.py'
    assert handler_file.exists(), (
        f"Function missing handler.py. Lambda requires a handler module for execution."
    )
    
    # Verify handler has Lambda-compatible structure
    try:
        with open(handler_file, 'r', encoding='utf-8') as f:
            handler_content = f.read()
    except Exception as e:
        assert False, f"Failed to read handler.py: {e}"
    
    # Verify handler has a handler function (Lambda requirement)
    # Lambda can use any function name as long as it's specified in the template
    handler_function_patterns = ['def lambda_handler(', 'def handler(']
    has_handler_function = any(pattern in handler_content for pattern in handler_function_patterns)
    assert has_handler_function, (
        f"Handler missing handler function. Lambda requires an entry point function. "
        f"Expected one of: {handler_function_patterns}"
    )
    
    # Verify function uses correct import patterns for Lambda
    # Should import from common namespace (provided by layer)
    common_import_patterns = [
        'from common.',
        'import common.'
    ]
    
    has_common_imports = any(pattern in handler_content for pattern in common_import_patterns)
    
    # Check for problematic local imports of common modules
    common_modules = ['logger', 'constants', 'retry', 'window_tracker']
    problematic_imports = []
    
    for module in common_modules:
        if f'from {module} import' in handler_content or f'import {module}' in handler_content:
            # Check if it's not using common namespace
            if f'from common.{module}' not in handler_content and f'import common.{module}' not in handler_content:
                problematic_imports.append(module)
    
    if problematic_imports:
        assert False, (
            f"Function has problematic imports: {problematic_imports}. "
            f"Should import from common namespace (e.g., 'from common.logger import') "
            f"to use layer-provided modules in Lambda runtime."
        )
    
    # Verify function requirements.txt exists (Lambda deployment requirement)
    requirements_file = function_source_path / 'requirements.txt'
    assert requirements_file.exists(), (
        f"Function missing requirements.txt. Lambda deployment requires dependency specification."
    )
    
    # Verify no common layer modules are duplicated in function
    common_modules_files = ['logger.py', 'constants.py', 'retry.py', 'window_tracker.py']
    for module_file in common_modules_files:
        module_path = function_source_path / module_file
        assert not module_path.exists(), (
            f"Function contains common module {module_file}. "
            f"This would conflict with layer-provided modules in Lambda runtime."
        )
    
    # Verify no layer-like structure in function
    python_dir = function_source_path / 'python'
    assert not python_dir.exists(), (
        f"Function should not contain python/ directory. "
        f"This structure is for layers, not functions in Lambda."
    )
    
    common_dir = function_source_path / 'common'
    assert not common_dir.exists(), (
        f"Function should not contain common/ directory. "
        f"Common modules are provided by the layer in Lambda runtime."
    )