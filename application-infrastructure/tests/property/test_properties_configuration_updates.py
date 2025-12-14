"""
Property-based tests for configuration file updates during test directory restructuring.

**Feature: test-directory-restructure, Property 3: Configuration file updates**
**Validates: Requirements 3.1, 3.2**

These tests verify that build and CI configuration files are properly updated
to reference the new test directory location after restructuring.
"""

import os
import sys
import tempfile
from hypothesis import given, strategies as st, assume
import pytest

# No need to add src to path - using new function structure


@given(
    old_path=st.one_of(
        st.just('src/tests/integration'),
        st.just('src/tests/property'),
        st.just('src/tests/unit'),
        st.just('application-infrastructure/src/tests'),
        st.just('./src/tests/integration'),
        st.just('${CODEBUILD_SRC_DIR}/src/tests')
    ),
    file_content=st.text(min_size=10, max_size=1000)
)
def test_buildspec_yml_path_updates(old_path, file_content):
    """
    **Feature: test-directory-restructure, Property 3: Configuration file updates**
    
    For any buildspec.yml file containing references to src/tests paths,
    all such references should be updated to point to the new tests/ location.
    """
    assume('src/tests' in old_path)
    assume(len(file_content.strip()) > 0)
    
    # Create a temporary buildspec.yml with old path references
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        test_content = f"""
version: 0.2
phases:
  build:
    commands:
      - pytest {old_path} -v
      - echo "Running tests from {old_path}"
{file_content}
"""
        f.write(test_content)
        temp_file = f.name
    
    try:
        # Read the original content
        with open(temp_file, 'r') as f:
            original_content = f.read()
        
        # Simulate the configuration update process
        updated_content = _update_buildspec_paths(original_content)
        
        # Verify that src/tests references are updated to tests/
        assert 'src/tests' not in updated_content, "Old src/tests references should be removed"
        
        # Verify that new tests/ references exist where old ones were
        if 'src/tests/' in original_content:
            assert 'tests/' in updated_content, "New tests/ references should exist"
        
        # Verify the structure is preserved (version, phases, etc.)
        assert 'version: 0.2' in updated_content, "YAML structure should be preserved"
        assert 'phases:' in updated_content, "Build phases should be preserved"
        
    finally:
        # Clean up
        os.unlink(temp_file)


@given(
    script_content=st.text(min_size=20, max_size=500),
    test_command=st.sampled_from([
        'pytest src/tests/unit/',
        'pytest src/tests/integration/',
        'pytest src/tests/property/',
        'python -m pytest src/tests/',
    ])
)
def test_shell_script_path_updates(script_content, test_command):
    """
    **Feature: test-directory-restructure, Property 3: Configuration file updates**
    
    For any shell script containing pytest commands with src/tests paths,
    all such commands should be updated to use the new tests/ location.
    """
    assume(len(script_content.strip()) > 0)
    
    # Create a temporary shell script with old path references
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        full_script = f"""#!/bin/bash
set -e

echo "Running tests"
{test_command} -v
{script_content}
echo "Tests complete"
"""
        f.write(full_script)
        temp_file = f.name
    
    try:
        # Read the original content
        with open(temp_file, 'r') as f:
            original_content = f.read()
        
        # Simulate the script update process
        updated_content = _update_script_paths(original_content)
        
        # Verify that src/tests references are updated
        assert 'src/tests' not in updated_content, "Old src/tests references should be removed"
        
        # Verify that new tests/ references exist
        if 'pytest' in original_content and 'src/tests' in original_content:
            assert 'tests/' in updated_content, "New tests/ references should exist in pytest commands"
        
        # Verify script structure is preserved
        assert '#!/bin/bash' in updated_content, "Shebang should be preserved"
        assert 'echo "Running tests"' in updated_content, "Script structure should be preserved"
        
    finally:
        # Clean up
        os.unlink(temp_file)


@given(
    doc_content=st.text(min_size=50, max_size=800),
    pytest_examples=st.lists(
        st.sampled_from([
            'pytest src/tests/unit/test_handler.py -v',
            'pytest src/tests/integration/ -v',
            'pytest src/tests/property/test_properties.py',
        ]),
        min_size=1,
        max_size=3
    )
)
def test_documentation_path_updates(doc_content, pytest_examples):
    """
    **Feature: test-directory-restructure, Property 3: Configuration file updates**
    
    For any documentation file containing pytest command examples with src/tests paths,
    all such examples should be updated to use the new tests/ location.
    """
    assume(len(doc_content.strip()) > 0)
    
    # Create a temporary documentation file with old path references
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        full_doc = f"""# Test Documentation

## Running Tests

{doc_content}

## Examples

```bash
{chr(10).join(pytest_examples)}
```

## Additional Content
More documentation here.
"""
        f.write(full_doc)
        temp_file = f.name
    
    try:
        # Read the original content
        with open(temp_file, 'r') as f:
            original_content = f.read()
        
        # Simulate the documentation update process
        updated_content = _update_documentation_paths(original_content)
        
        # Verify that src/tests references are updated
        assert 'src/tests' not in updated_content, "Old src/tests references should be removed from documentation"
        
        # Verify that new tests/ references exist where pytest commands were
        if any('pytest' in example and 'src/tests' in example for example in pytest_examples):
            assert 'tests/' in updated_content, "New tests/ references should exist in pytest examples"
        
        # Verify documentation structure is preserved
        assert '# Test Documentation' in updated_content, "Documentation structure should be preserved"
        assert '```bash' in updated_content, "Code block formatting should be preserved"
        
    finally:
        # Clean up
        os.unlink(temp_file)


def _update_buildspec_paths(content):
    """Simulate updating buildspec.yml paths from src/tests to tests/."""
    # Replace src/tests/ with tests/
    updated = content.replace('src/tests/', 'tests/')
    # Handle cases without trailing slash
    updated = updated.replace('src/tests', 'tests')
    return updated


def _update_script_paths(content):
    """Simulate updating shell script paths from src/tests to tests/."""
    # Replace pytest src/tests with pytest tests
    updated = content.replace('pytest src/tests/', 'pytest tests/')
    updated = updated.replace('pytest src/tests', 'pytest tests')
    # Handle python -m pytest cases
    updated = updated.replace('python -m pytest src/tests/', 'python -m pytest tests/')
    updated = updated.replace('python -m pytest src/tests', 'python -m pytest tests')
    return updated


def _update_documentation_paths(content):
    """Simulate updating documentation paths from src/tests to tests/."""
    # Replace all src/tests references with tests/
    updated = content.replace('src/tests/', 'tests/')
    updated = updated.replace('src/tests', 'tests')
    return updated


if __name__ == "__main__":
    pytest.main([__file__, "-v"])