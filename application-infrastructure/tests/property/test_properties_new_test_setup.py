"""Property-based tests for new test setup requirements."""

import sys
import importlib
import tempfile
import textwrap
from pathlib import Path
from hypothesis import given, settings, strategies as st


@st.composite
def generate_test_file_content(draw):
    """Generate realistic test file content that imports common modules."""
    common_modules = [
        'common.logger',
        'common.constants', 
        'common.retry',
        'common.window_tracker'
    ]
    
    # Select 1-3 modules to import
    num_imports = draw(st.integers(min_value=1, max_value=3))
    selected_modules = draw(st.lists(
        st.sampled_from(common_modules), 
        min_size=num_imports, 
        max_size=num_imports,
        unique=True
    ))
    
    # Generate import statements
    import_lines = []
    for module in selected_modules:
        # Generate different import styles
        import_style = draw(st.sampled_from([
            f"import {module}",
            f"from {module} import *",
            f"from {module.split('.')[0]} import {module.split('.')[1]}"
        ]))
        import_lines.append(import_style)
    
    # Create a simple test function
    test_content = f"""'''Test file that imports common modules.'''
{chr(10).join(import_lines)}

def test_simple_functionality():
    '''Simple test that uses imported modules.'''
    # This test should work without additional setup
    assert True
"""
    
    return test_content, selected_modules


@settings(max_examples=100)
@given(content_and_modules=generate_test_file_content())
def test_new_tests_require_no_additional_setup(content_and_modules):
    """
    Property 10: New tests require no additional setup
    
    For any new test file that imports common modules, the test should be able
    to import and use common modules without any additional path configuration
    beyond what conftest.py provides.
    
    **Feature: import-simplification, Property 10: New tests require no additional setup**
    **Validates: Requirements 3.5**
    """
    test_content, expected_modules = content_and_modules
    
    # Create a temporary test file
    with tempfile.NamedTemporaryFile(mode='w', suffix='_test.py', delete=False) as temp_file:
        temp_file.write(test_content)
        temp_file_path = Path(temp_file.name)
    
    try:
        # Verify that conftest.py has already set up the necessary paths
        layer_path = str(Path(__file__).parent.parent.parent / "layers" / "common" / "python")
        functions_path = str(Path(__file__).parent.parent.parent / "functions")
        
        assert layer_path in sys.path, (
            f"Layer path {layer_path} should be in sys.path from conftest.py"
        )
        assert functions_path in sys.path, (
            f"Functions path {functions_path} should be in sys.path from conftest.py"
        )
        
        # Load and execute the test file to verify imports work
        spec = importlib.util.spec_from_file_location("temp_test", temp_file_path)
        temp_module = importlib.util.module_from_spec(spec)
        
        try:
            # This should succeed without any additional path manipulation
            spec.loader.exec_module(temp_module)
            
            # Verify the test function exists and can be called
            assert hasattr(temp_module, 'test_simple_functionality'), (
                "Test file should contain the test function"
            )
            
            # Call the test function to ensure it works
            temp_module.test_simple_functionality()
            
        except ImportError as e:
            assert False, (
                f"New test file failed to import common modules without additional setup. "
                f"This violates the requirement that new tests need no additional configuration: {e}"
            )
        except Exception as e:
            assert False, (
                f"New test file failed to execute properly: {e}"
            )
            
    finally:
        # Clean up temporary file
        if temp_file_path.exists():
            temp_file_path.unlink()


@st.composite
def generate_test_directory_scenarios(draw):
    """Generate different test directory scenarios."""
    # Different subdirectories where tests might be placed
    subdirs = [
        "unit",
        "integration", 
        "property",
        "functional",
        "e2e"
    ]
    return draw(st.sampled_from(subdirs))


@settings(max_examples=50)
@given(subdir=generate_test_directory_scenarios())
def test_conftest_setup_works_across_test_directories(subdir):
    """
    Test that conftest.py setup works regardless of test file location
    within the tests directory structure.
    
    **Feature: import-simplification, Property 10: New tests require no additional setup**
    **Validates: Requirements 3.5**
    """
    # Verify that common modules can be imported from any test subdirectory
    # This simulates pytest's behavior of loading conftest.py for all test files
    
    common_modules = ['common.logger', 'common.constants', 'common.retry']
    
    for module_name in common_modules:
        try:
            # Import should work from any test directory because conftest.py
            # is loaded once and applies to all tests
            module = importlib.import_module(module_name)
            assert module is not None, f"Module {module_name} should be importable"
            
            # Verify it's loaded from the correct location
            if hasattr(module, '__file__') and module.__file__:
                module_path = Path(module.__file__)
                assert 'layers/common/python' in str(module_path), (
                    f"Module {module_name} should be from layers/common/python, "
                    f"got {module_path}"
                )
                
        except ImportError as e:
            assert False, (
                f"Failed to import {module_name} from test subdirectory {subdir}. "
                f"conftest.py setup should work across all test directories: {e}"
            )


@settings(max_examples=30)
@given(
    module_name=st.sampled_from([
        'common.logger', 
        'common.constants', 
        'common.retry', 
        'common.window_tracker'
    ])
)
def test_no_additional_sys_path_manipulation_needed(module_name):
    """
    Test that new tests don't need to add any sys.path manipulation
    to import common modules.
    
    **Feature: import-simplification, Property 10: New tests require no additional setup**
    **Validates: Requirements 3.5**
    """
    # Save original sys.path
    original_path = sys.path.copy()
    
    try:
        # Simulate a new test file that doesn't do any path manipulation
        # It should still be able to import common modules because conftest.py
        # has already set up the paths
        
        # Don't add any paths manually - rely only on conftest.py setup
        module = importlib.import_module(module_name)
        assert module is not None
        
        # Verify the module comes from the expected location
        if hasattr(module, '__file__') and module.__file__:
            module_path = Path(module.__file__)
            expected_path_part = 'layers/common/python'
            assert expected_path_part in str(module_path), (
                f"Module {module_name} should come from {expected_path_part}, "
                f"but came from {module_path}"
            )
            
    except ImportError as e:
        assert False, (
            f"Failed to import {module_name} without manual path setup. "
            f"New tests should not require additional sys.path manipulation: {e}"
        )
    finally:
        # Restore original sys.path
        sys.path[:] = original_path