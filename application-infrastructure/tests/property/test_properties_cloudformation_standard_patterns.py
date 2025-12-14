"""
Property-based tests for CloudFormation standard patterns.

**Feature: import-simplification, Property 14: CloudFormation standard patterns**
**Validates: Requirements 5.2, 7.3**
"""

import yaml
from pathlib import Path
from hypothesis import given, strategies as st, settings
import re


@settings(max_examples=10, deadline=2000)
@given(st.just('template.yml'))
def test_property_14_cloudformation_standard_patterns(template_file):
    """Property 14: CloudFormation standard patterns.
    
    For any CloudFormation template reference to code, the template should use 
    standard CodeUri and LayerVersion patterns.
    
    **Validates: Requirements 5.2, 7.3**
    """
    # Get the template path
    app_infra_path = Path(__file__).parent.parent.parent
    template_path = app_infra_path / template_file
    
    assert template_path.exists(), f"CloudFormation template does not exist: {template_path}"
    
    # Read template content
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        assert False, f"Failed to read CloudFormation template: {str(e)}"
    
    # Validate basic CloudFormation structure without full YAML parsing
    # (CloudFormation templates use intrinsic functions that complicate YAML parsing)
    
    # Check for basic CloudFormation structure
    assert 'AWSTemplateFormatVersion' in content, "Missing AWSTemplateFormatVersion"
    assert 'Transform' in content and 'AWS::Serverless' in content, "Missing SAM Transform"
    assert 'Resources:' in content, "Missing Resources section"
    
    # For detailed validation, we'll check the content as text
    content_lower = content.lower()
    
    # Find and verify CodeUri patterns using text search
    code_uri_matches = re.findall(r'CodeUri:\s*([^\s\n]+)', content)
    assert len(code_uri_matches) > 0, "No CodeUri found in template"
    
    for code_uri in code_uri_matches:
        # Should use functions/{function_name}/ pattern
        assert code_uri.startswith('functions/'), (
            f"CodeUri should start with 'functions/', got: {code_uri}"
        )
        
        # Should not contain hardcoded paths or absolute paths
        assert not code_uri.startswith('/'), (
            f"CodeUri should not be absolute path, got: {code_uri}"
        )
        
        # Should not contain '..' or other path manipulation
        assert '..' not in code_uri, (
            f"CodeUri should not contain path traversal, got: {code_uri}"
        )
    
    # Find and verify ContentUri patterns using text search
    content_uri_matches = re.findall(r'ContentUri:\s*([^\s\n]+)', content)
    
    for content_uri in content_uri_matches:
        # Should use layers/{layer_name}/ pattern
        assert content_uri.startswith('layers/'), (
            f"ContentUri should start with 'layers/', got: {content_uri}"
        )
        
        # Should not contain hardcoded paths or absolute paths
        assert not content_uri.startswith('/'), (
            f"ContentUri should not be absolute path, got: {content_uri}"
        )
        
        # Should not contain '..' or other path manipulation
        assert '..' not in content_uri, (
            f"ContentUri should not contain path traversal, got: {content_uri}"
        )
    
    # Verify layer references use standard !Ref pattern
    layer_ref_matches = re.findall(r'Layers:\s*\n\s*-\s*([^\s\n]+)', content)
    
    for layer_ref in layer_ref_matches:
        # Layer references should use !Ref, not hardcoded ARNs
        assert not layer_ref.startswith('arn:aws:lambda:'), (
            f"Layer reference should use !Ref, not hardcoded ARN: {layer_ref}"
        )
        
        # Should use !Ref pattern
        assert layer_ref.startswith('!Ref'), (
            f"Layer reference should use !Ref pattern, got: {layer_ref}"
        )
    
    # Verify no hardcoded paths in template content
    hardcoded_patterns = [
        r'/opt/python',  # Lambda runtime paths
        r'/var/task',    # Lambda runtime paths
        r'C:\\',         # Windows paths
        r'/home/',       # Unix home paths
        r'/tmp/',        # Temporary paths (except legitimate Lambda temp usage)
    ]
    
    for pattern in hardcoded_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        # Allow /tmp/ in comments or legitimate Lambda usage
        if pattern == r'/tmp/' and matches:
            # Check if it's in comments or legitimate usage
            for match in matches:
                line_with_match = [line for line in content.split('\n') if pattern in line][0]
                if not (line_with_match.strip().startswith('#') or 'AWS::Lambda' in line_with_match):
                    assert False, f"Found hardcoded path pattern {pattern} in non-comment context"
        elif matches and pattern != r'/tmp/':
            assert False, f"Found hardcoded path pattern {pattern} in template"
    
    # Verify AWS::Serverless::Function and AWS::Serverless::LayerVersion are used
    assert 'AWS::Serverless::Function' in content, "Template should use AWS::Serverless::Function"
    assert 'AWS::Serverless::LayerVersion' in content, "Template should use AWS::Serverless::LayerVersion"


@settings(max_examples=5, deadline=1000)
@given(st.just('layers/common/'))
def test_property_14_layer_structure_standards(layer_path):
    """Property 14b: Layer structure follows Lambda standards.
    
    For any layer directory, it should follow the python/{module}/ structure
    expected by Lambda runtime.
    
    **Validates: Requirements 5.2**
    """
    # Get the layer path
    app_infra_path = Path(__file__).parent.parent.parent
    full_layer_path = app_infra_path / layer_path
    
    assert full_layer_path.exists(), f"Layer directory does not exist: {full_layer_path}"
    
    # Verify python subdirectory exists
    python_path = full_layer_path / 'python'
    assert python_path.exists(), f"Layer missing python/ subdirectory: {python_path}"
    
    # Verify common module directory exists
    common_path = python_path / 'common'
    assert common_path.exists(), f"Layer missing python/common/ subdirectory: {common_path}"
    
    # Verify __init__.py exists in common module
    init_file = common_path / '__init__.py'
    assert init_file.exists(), f"Layer missing __init__.py in common module: {init_file}"
    
    # Verify no files are directly in python/ (should be in python/common/)
    python_files = [f for f in python_path.iterdir() if f.is_file() and f.suffix == '.py']
    assert len(python_files) == 0, (
        f"Python files should be in python/common/, not directly in python/: {python_files}"
    )


@settings(max_examples=5, deadline=1000)
@given(st.sampled_from(['functions/ingestor/', 'functions/processor/']))
def test_property_14_function_structure_standards(function_path):
    """Property 14c: Function structure follows Lambda standards.
    
    For any function directory, it should contain handler.py and follow
    standard Lambda function organization.
    
    **Validates: Requirements 5.2**
    """
    # Get the function path
    app_infra_path = Path(__file__).parent.parent.parent
    full_function_path = app_infra_path / function_path
    
    assert full_function_path.exists(), f"Function directory does not exist: {full_function_path}"
    
    # Verify handler.py exists
    handler_file = full_function_path / 'handler.py'
    assert handler_file.exists(), f"Function missing handler.py: {handler_file}"
    
    # Verify requirements.txt exists
    requirements_file = full_function_path / 'requirements.txt'
    assert requirements_file.exists(), f"Function missing requirements.txt: {requirements_file}"
    
    # Verify no common layer modules are duplicated in function directory
    common_modules = ['logger.py', 'constants.py', 'retry.py', 'window_tracker.py']
    
    for module in common_modules:
        module_file = full_function_path / module
        assert not module_file.exists(), (
            f"Function should not contain common module {module}, "
            f"it should be in the layer: {module_file}"
        )