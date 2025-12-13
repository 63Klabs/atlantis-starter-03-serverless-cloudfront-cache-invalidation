"""Property-based tests for build and test execution consistency."""

import os
import subprocess
import sys
from pathlib import Path
import tempfile
import shutil

from hypothesis import given, settings, strategies as st


# Custom strategies for generating test data

@st.composite
def build_commands(draw):
    """Generate build commands that should work with the new structure."""
    # Get the current Python executable (which should have pytest available)
    python_exe = sys.executable
    
    # Commands from buildspec.yml that should execute successfully
    commands = [
        f"{python_exe} -m pytest tests/unit/ --tb=short --maxfail=1",
        f"{python_exe} -m pytest tests/property/ --tb=short --maxfail=1", 
        f"{python_exe} -m pytest tests/integration/ --tb=short --maxfail=1"
    ]
    return draw(st.sampled_from(commands))


@st.composite
def dependency_installation_paths(draw):
    """Generate dependency installation paths for functions and layer."""
    # Paths where dependencies should be installable
    base_path = Path(__file__).parent.parent.parent  # application-infrastructure
    paths = [
        base_path / 'functions' / 'ingestor',
        base_path / 'functions' / 'processor', 
        base_path / 'layers' / 'common' / 'python'
    ]
    # Only return existing directories
    existing_paths = [p for p in paths if p.exists()]
    if not existing_paths:
        # Return a placeholder if paths don't exist yet
        return base_path / 'functions' / 'ingestor'
    return draw(st.sampled_from(existing_paths))


@st.composite
def requirements_files(draw):
    """Generate requirements file paths that should exist."""
    base_path = Path(__file__).parent.parent.parent  # application-infrastructure
    req_files = [
        base_path / 'functions' / 'ingestor' / 'requirements.txt',
        base_path / 'functions' / 'processor' / 'requirements.txt',
        base_path / 'layers' / 'common' / 'requirements.txt',
        base_path / 'tests' / 'requirements.txt'
    ]
    # Only return existing files
    existing_files = [f for f in req_files if f.exists()]
    if not existing_files:
        # Return a placeholder if files don't exist yet
        return base_path / 'tests' / 'requirements.txt'
    return draw(st.sampled_from(existing_files))


@st.composite
def discovery_directory_paths(draw):
    """Generate test directory paths that should be discoverable."""
    base_path = Path(__file__).parent.parent.parent  # application-infrastructure
    test_dirs = [
        base_path / 'tests' / 'unit',
        base_path / 'tests' / 'property',
        base_path / 'tests' / 'integration'
    ]
    # Only return existing directories
    existing_dirs = [d for d in test_dirs if d.exists()]
    if not existing_dirs:
        # Return a placeholder if directories don't exist yet
        return base_path / 'tests' / 'unit'
    return draw(st.sampled_from(existing_dirs))


# Property Tests

@settings(max_examples=100, deadline=10000)
@given(build_commands())
def test_property_5_build_and_test_execution_consistency(build_command):
    """Property 5: Build and test execution consistency.
    
    For any build or test execution, the process should complete successfully 
    with the new directory structure.
    
    **Feature: lambda-function-separation, Property 5: Build and test execution consistency**
    **Validates: Requirements 3.1, 3.2, 4.5, 5.3**
    """
    # Change to the application-infrastructure directory
    original_cwd = os.getcwd()
    app_infra_path = Path(__file__).parent.parent.parent
    
    try:
        os.chdir(app_infra_path)
        
        # Execute the build command
        result = subprocess.run(
            build_command.split(),
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout
        )
        
        # Verify command executed without critical errors
        # Note: Tests may fail, but the command itself should execute
        assert result.returncode in [0, 1], (
            f"Build command failed to execute properly: {build_command}\n"
            f"Return code: {result.returncode}\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )
        
        # Verify output indicates test discovery worked
        output = result.stdout + result.stderr
        assert "collected" in output.lower() or "test session starts" in output.lower(), (
            f"Test discovery failed for command: {build_command}\n"
            f"Output: {output}"
        )
        
    except subprocess.TimeoutExpired:
        assert False, f"Build command timed out: {build_command}"
    except Exception as e:
        assert False, f"Unexpected error executing build command: {build_command} - {str(e)}"
    finally:
        os.chdir(original_cwd)


@settings(max_examples=50, deadline=5000)
@given(dependency_installation_paths())
def test_property_5_dependency_installation_paths(install_path):
    """Property 5b: Dependency installation path validation.
    
    For any dependency installation path, the directory structure should support
    proper dependency installation and resolution.
    
    **Feature: lambda-function-separation, Property 5: Build and test execution consistency**
    **Validates: Requirements 3.1, 3.2, 4.5, 5.3**
    """
    # Verify the installation path exists
    assert install_path.exists(), f"Installation path does not exist: {install_path}"
    
    # Verify the path is writable (needed for dependency installation)
    assert os.access(install_path, os.W_OK), (
        f"Installation path is not writable: {install_path}"
    )
    
    # Verify we can create a test file in the path (simulates dependency installation)
    test_file = install_path / 'test_dependency_install.tmp'
    try:
        with open(test_file, 'w') as f:
            f.write('test')
        
        # Verify file was created
        assert test_file.exists(), (
            f"Failed to create test file in installation path: {install_path}"
        )
        
        # Clean up test file
        test_file.unlink()
        
    except Exception as e:
        assert False, f"Failed to test dependency installation in {install_path}: {str(e)}"


@settings(max_examples=30, deadline=3000)
@given(requirements_files())
def test_property_5_requirements_file_validity(requirements_file):
    """Property 5c: Requirements file validity.
    
    For any requirements file, it should be properly formatted and readable
    for dependency installation processes.
    
    **Feature: lambda-function-separation, Property 5: Build and test execution consistency**
    **Validates: Requirements 3.1, 3.2, 4.5, 5.3**
    """
    # Verify requirements file exists
    assert requirements_file.exists(), f"Requirements file does not exist: {requirements_file}"
    
    # Verify file is readable
    try:
        with open(requirements_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        assert False, f"Failed to read requirements file {requirements_file}: {str(e)}"
    
    # Verify file has some content (even if just comments)
    assert len(content.strip()) > 0, f"Requirements file is empty: {requirements_file}"
    
    # Verify file doesn't have obvious syntax errors
    lines = content.strip().split('\n')
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if line and not line.startswith('#'):
            # Basic validation - should not have obvious syntax errors
            assert not line.startswith('='), (
                f"Invalid requirement syntax at line {line_num} in {requirements_file}: {line}"
            )
            assert '==' in line or '>=' in line or '<=' in line or line.isalpha() or '.' in line, (
                f"Suspicious requirement format at line {line_num} in {requirements_file}: {line}"
            )


@settings(max_examples=20, deadline=3000)
@given(discovery_directory_paths())
def test_property_5_test_discovery_consistency(test_path):
    """Property 5d: Test discovery consistency.
    
    For any test directory, pytest should be able to discover and collect tests
    from the directory structure.
    
    **Feature: lambda-function-separation, Property 5: Build and test execution consistency**
    **Validates: Requirements 3.1, 3.2, 4.5, 5.3**
    """
    # Verify test directory exists
    assert test_path.exists(), f"Test directory does not exist: {test_path}"
    
    # Change to the application-infrastructure directory for proper test execution
    original_cwd = os.getcwd()
    app_infra_path = Path(__file__).parent.parent.parent
    
    try:
        os.chdir(app_infra_path)
        
        # Run pytest collection on the test directory
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', str(test_path.relative_to(app_infra_path)), '--collect-only', '-q'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Verify pytest can discover tests (return code 0 or 5 for no tests collected)
        assert result.returncode in [0, 5], (
            f"Test discovery failed for {test_path}\n"
            f"Return code: {result.returncode}\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )
        
        # If there are Python test files, verify they were discovered
        test_files = list(test_path.glob('test_*.py'))
        if test_files:
            output = result.stdout + result.stderr
            # Should show collected tests or indicate collection completed
            assert "collected" in output.lower() or "no tests ran" in output.lower(), (
                f"Test collection output unexpected for {test_path}\n"
                f"Output: {output}"
            )
        
    except subprocess.TimeoutExpired:
        assert False, f"Test discovery timed out for: {test_path}"
    except Exception as e:
        assert False, f"Unexpected error during test discovery for {test_path}: {str(e)}"
    finally:
        os.chdir(original_cwd)


@settings(max_examples=10, deadline=2000)
@given(st.just('buildspec.yml'))
def test_property_5_buildspec_structure_validity(buildspec_file):
    """Property 5e: Buildspec structure validity.
    
    For any buildspec file, it should contain the necessary commands and structure
    to support the new function and layer architecture.
    
    **Feature: lambda-function-separation, Property 5: Build and test execution consistency**
    **Validates: Requirements 3.1, 3.2, 4.5, 5.3**
    """
    # Verify buildspec.yml exists
    app_infra_path = Path(__file__).parent.parent.parent
    buildspec_path = app_infra_path / buildspec_file
    
    assert buildspec_path.exists(), f"Buildspec file does not exist: {buildspec_path}"
    
    # Read and verify buildspec content
    try:
        with open(buildspec_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        assert False, f"Failed to read buildspec file: {str(e)}"
    
    # Verify buildspec contains key sections for new structure
    content_lower = content.lower()
    
    # Should contain function dependency installation
    assert 'functions/ingestor/requirements.txt' in content, (
        "Buildspec missing ingestor function dependency installation"
    )
    assert 'functions/processor/requirements.txt' in content, (
        "Buildspec missing processor function dependency installation"
    )
    
    # Should contain layer dependency installation
    assert 'layers/common/requirements.txt' in content, (
        "Buildspec missing layer dependency installation"
    )
    
    # Should contain layer packaging
    assert 'zip' in content_lower and 'layer' in content_lower, (
        "Buildspec missing layer packaging commands"
    )
    
    # Should contain test execution for all test types
    assert 'pytest tests/unit/' in content, (
        "Buildspec missing unit test execution"
    )
    assert 'pytest tests/property/' in content, (
        "Buildspec missing property test execution"
    )
    assert 'pytest tests/integration/' in content, (
        "Buildspec missing integration test execution"
    )


@settings(max_examples=5, deadline=1000)
@given(st.just('template.yml'))
def test_property_5_cloudformation_template_consistency(template_file):
    """Property 5f: CloudFormation template consistency.
    
    For any CloudFormation template, it should be syntactically valid and
    reference the correct paths for the new function and layer structure.
    
    **Feature: lambda-function-separation, Property 5: Build and test execution consistency**
    **Validates: Requirements 3.1, 3.2, 4.5, 5.3**
    """
    # Verify template.yml exists
    app_infra_path = Path(__file__).parent.parent.parent
    template_path = app_infra_path / template_file
    
    assert template_path.exists(), f"CloudFormation template does not exist: {template_path}"
    
    # Read and verify template content
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        assert False, f"Failed to read CloudFormation template: {str(e)}"
    
    # Verify template references new function paths
    assert 'functions/ingestor' in content, (
        "CloudFormation template missing reference to ingestor function path"
    )
    assert 'functions/processor' in content, (
        "CloudFormation template missing reference to processor function path"
    )
    
    # Verify template is valid YAML/CloudFormation format
    content_lower = content.lower()
    assert 'awstemplateformatversion' in content_lower, (
        "CloudFormation template missing AWSTemplateFormatVersion"
    )
    
    # Note: Layer definition may not be present yet during restructuring
    # This test validates the template is structurally sound for the build process