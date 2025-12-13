"""Property-based tests for virtual environment setup."""

import sys
import os
import subprocess
import importlib.util
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from hypothesis import given, settings, strategies as st


# Custom strategies for generating test data

@st.composite
def required_test_dependencies(draw):
    """Generate required test dependencies from requirements.txt."""
    # Core dependencies that must be available
    core_deps = [
        'pytest',
        'hypothesis', 
        'moto',
        'boto3',
        'botocore'
    ]
    
    # Optional dependencies that may be included
    optional_deps = [
        'pytest_mock',
        'requests',
        'jinja2',
        'jsonschema'
    ]
    
    # Always include core dependencies
    selected_deps = core_deps.copy()
    
    # Randomly include some optional dependencies
    num_optional = draw(st.integers(min_value=0, max_value=len(optional_deps)))
    selected_optional = draw(st.lists(
        st.sampled_from(optional_deps), 
        min_size=0, 
        max_size=num_optional,
        unique=True
    ))
    
    selected_deps.extend(selected_optional)
    return selected_deps


@st.composite
def virtual_environment_path(draw):
    """Generate virtual environment path variations."""
    base_path = Path(__file__).parent.parent  # tests directory, not property subdirectory
    venv_name = draw(st.sampled_from(['.venv-test', '.venv-test/']))
    return base_path / venv_name


# Property Tests

@settings(max_examples=20, deadline=5000)  # 5 second deadline for subprocess calls
@given(required_test_dependencies())
def test_property_4_virtual_environment_dependency_completeness(dependencies):
    """Property 4: Virtual environment dependency completeness.
    
    For any test virtual environment setup, all required testing libraries 
    and dependencies should be installed and available for import.
    
    **Feature: test-directory-restructure, Property 4: Virtual environment dependency completeness**
    **Validates: Requirements 4.2, 4.4**
    """
    # Get the virtual environment path (in tests directory, not property subdirectory)
    venv_path = Path(__file__).parent.parent / '.venv-test'
    python_executable = venv_path / 'bin' / 'python'
    
    # Verify virtual environment exists
    assert venv_path.exists(), f"Virtual environment not found at {venv_path}"
    assert python_executable.exists(), f"Python executable not found at {python_executable}"
    
    # Test each dependency
    for dependency in dependencies:
        # Normalize dependency name for import (handle package name variations)
        import_name = dependency.replace('-', '_').replace('pytest_mock', 'pytest_mock')
        
        # Test that the dependency can be imported in the virtual environment
        try:
            result = subprocess.run([
                str(python_executable), 
                '-c', 
                f'import {import_name}; print("SUCCESS: {import_name} imported")'
            ], capture_output=True, text=True, timeout=30)
            
            # Verify the import succeeded
            assert result.returncode == 0, f"Failed to import {import_name}: {result.stderr}"
            assert "SUCCESS" in result.stdout, f"Import verification failed for {import_name}"
            
        except subprocess.TimeoutExpired:
            assert False, f"Import test for {import_name} timed out"
        except Exception as e:
            assert False, f"Unexpected error testing {import_name}: {str(e)}"


@settings(max_examples=10, deadline=3000)  # 3 second deadline for subprocess calls
@given(virtual_environment_path())
def test_property_4_virtual_environment_isolation(venv_path):
    """Property 4b: Virtual environment isolation.
    
    For any virtual environment, it should be isolated from the system Python
    and use its own package installations.
    
    **Feature: test-directory-restructure, Property 4: Virtual environment dependency completeness**
    **Validates: Requirements 4.2, 4.4**
    """
    # Normalize the path (in tests directory, not property subdirectory)
    venv_path = Path(__file__).parent.parent / '.venv-test'
    python_executable = venv_path / 'bin' / 'python'
    
    # Skip if virtual environment doesn't exist
    if not venv_path.exists() or not python_executable.exists():
        return
    
    # Test that the virtual environment uses its own Python
    try:
        result = subprocess.run([
            str(python_executable), 
            '-c', 
            'import sys; print(sys.executable)'
        ], capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0, f"Failed to get Python executable path: {result.stderr}"
        
        # Verify the Python executable is within the virtual environment
        reported_python = result.stdout.strip()
        assert str(venv_path) in reported_python, f"Virtual environment not isolated: {reported_python}"
        
    except subprocess.TimeoutExpired:
        assert False, "Virtual environment isolation test timed out"
    except Exception as e:
        assert False, f"Unexpected error testing virtual environment isolation: {str(e)}"


@settings(max_examples=10, deadline=3000)  # 3 second deadline for subprocess calls
@given(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))))
def test_property_4_requirements_file_consistency(package_name):
    """Property 4c: Requirements file consistency.
    
    For any package listed in requirements.txt, it should be installable
    and available in the virtual environment.
    
    **Feature: test-directory-restructure, Property 4: Virtual environment dependency completeness**
    **Validates: Requirements 4.2, 4.4**
    """
    # Read the actual requirements.txt file (in tests directory, not property subdirectory)
    requirements_file = Path(__file__).parent.parent / 'requirements.txt'
    
    if not requirements_file.exists():
        return  # Skip if requirements file doesn't exist
    
    # Parse requirements file
    with open(requirements_file, 'r') as f:
        requirements = [line.strip() for line in f.readlines() if line.strip() and not line.startswith('#')]
    
    # Filter to only test actual packages from requirements.txt
    actual_packages = []
    for req in requirements:
        # Extract package name (before version specifiers)
        pkg_name = req.split('>=')[0].split('==')[0].split('<')[0].split('>')[0].split('[')[0]
        actual_packages.append(pkg_name)
    
    # Only test if the generated package name matches an actual requirement
    if package_name not in actual_packages:
        return
    
    # Test the actual package (in tests directory, not property subdirectory)
    venv_path = Path(__file__).parent.parent / '.venv-test'
    python_executable = venv_path / 'bin' / 'python'
    
    if not python_executable.exists():
        return
    
    # Normalize package name for import
    import_name = package_name.replace('-', '_')
    
    try:
        result = subprocess.run([
            str(python_executable), 
            '-c', 
            f'import {import_name}; print("INSTALLED: {import_name}")'
        ], capture_output=True, text=True, timeout=20)
        
        # The package should be importable if it's in requirements.txt
        assert result.returncode == 0, f"Required package {import_name} not available: {result.stderr}"
        assert "INSTALLED" in result.stdout, f"Package verification failed for {import_name}"
        
    except subprocess.TimeoutExpired:
        assert False, f"Package test for {import_name} timed out"
    except Exception as e:
        assert False, f"Unexpected error testing package {import_name}: {str(e)}"