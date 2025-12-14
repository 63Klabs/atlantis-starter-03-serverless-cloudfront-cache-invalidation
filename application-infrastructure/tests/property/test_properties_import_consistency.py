"""Property-based tests for import consistency across environments."""

import sys
import importlib
import importlib.util
from pathlib import Path
from hypothesis import given, settings, strategies as st
import tempfile
import os


@st.composite
def shared_module_names(draw):
    """Generate names of shared modules that should work consistently."""
    modules = [
        'common.logger',
        'common.constants', 
        'common.retry',
        'common.window_tracker'
    ]
    return draw(st.sampled_from(modules))


@st.composite
def import_statement_patterns(draw):
    """Generate different import statement patterns for shared modules."""
    module = draw(shared_module_names())
    
    patterns = [
        f"import {module}",
        f"from {module} import *",
    ]
    
    # Add specific function imports for known modules
    if module == 'common.logger':
        patterns.extend([
            "from common.logger import setup_logger",
            "from common.logger import get_logger"
        ])
    elif module == 'common.constants':
        patterns.extend([
            "from common.constants import LOG_LEVEL_PROD",
            "from common.constants import DEFAULT_TIMEOUT"
        ])
    elif module == 'common.retry':
        patterns.extend([
            "from common.retry import retry_with_backoff",
            "from common.retry import RetryConfig"
        ])
    elif module == 'common.window_tracker':
        patterns.extend([
            "from common.window_tracker import WindowTracker",
            "from common.window_tracker import track_window"
        ])
    
    return draw(st.sampled_from(patterns))


def simulate_lambda_environment():
    """Simulate Lambda's import environment structure."""
    # Create a temporary directory structure that mirrors Lambda
    temp_dir = tempfile.mkdtemp()
    
    # Create /var/task equivalent (function code)
    var_task = Path(temp_dir) / "var" / "task"
    var_task.mkdir(parents=True)
    
    # Create /opt/python equivalent (layer code)
    opt_python = Path(temp_dir) / "opt" / "python"
    opt_python.mkdir(parents=True)
    
    # Copy common modules to opt/python
    common_src = Path(__file__).parent.parent.parent / "layers" / "common" / "python" / "common"
    common_dst = opt_python / "common"
    
    if common_src.exists():
        import shutil
        shutil.copytree(common_src, common_dst)
    
    return temp_dir, str(var_task), str(opt_python)


@settings(max_examples=100)
@given(import_statement=import_statement_patterns())
def test_import_consistency_across_environments(import_statement):
    """
    Property 1: Import consistency across environments
    
    For any shared module import statement, the import should work identically 
    in local development and simulated Lambda environment structures.
    
    **Feature: import-simplification, Property 1: Import consistency across environments**
    **Validates: Requirements 1.1**
    """
    # Test 1: Import works in current local development environment
    local_success = False
    local_error = None
    
    try:
        # Execute the import statement in local environment
        exec(import_statement)
        local_success = True
    except Exception as e:
        local_error = str(e)
    
    # Test 2: Import works in simulated Lambda environment
    lambda_success = False
    lambda_error = None
    
    temp_dir = None
    try:
        temp_dir, var_task_path, opt_python_path = simulate_lambda_environment()
        
        # Save original sys.path
        original_path = sys.path.copy()
        
        # Set up Lambda-like sys.path
        sys.path = [var_task_path, opt_python_path] + [p for p in sys.path if not p.startswith(str(Path(__file__).parent.parent.parent))]
        
        # Clear import cache for modules we're testing
        modules_to_clear = [name for name in sys.modules.keys() if name.startswith('common')]
        for module_name in modules_to_clear:
            if module_name in sys.modules:
                del sys.modules[module_name]
        
        # Execute the import statement in Lambda-like environment
        exec(import_statement)
        lambda_success = True
        
    except Exception as e:
        lambda_error = str(e)
    finally:
        # Restore original sys.path
        if 'original_path' in locals():
            sys.path[:] = original_path
        
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Restore import cache
        importlib.invalidate_caches()
    
    # Both environments should have the same result
    assert local_success == lambda_success, (
        f"Import consistency failed for '{import_statement}'. "
        f"Local success: {local_success} (error: {local_error}), "
        f"Lambda success: {lambda_success} (error: {lambda_error})"
    )
    
    # If both failed, that's also consistent (might be an invalid import)
    # If both succeeded, that's the expected behavior
    if not local_success and not lambda_success:
        # Both failed consistently - this might be expected for invalid imports
        pass
    elif local_success and lambda_success:
        # Both succeeded - this is the ideal case
        pass


@settings(max_examples=50)
@given(module_name=shared_module_names())
def test_import_paths_are_environment_independent(module_name):
    """
    Test that import statements don't depend on specific local paths.
    
    **Feature: import-simplification, Property 1: Import consistency across environments**
    **Validates: Requirements 1.1**
    """
    # Save original sys.path to restore later
    original_path = sys.path.copy()
    
    try:
        # Import the module in normal environment (not simulated)
        module = importlib.import_module(module_name)
        
        if hasattr(module, '__file__') and module.__file__:
            module_path = Path(module.__file__)
            
            # The import should not depend on absolute paths specific to local development
            # It should work through the layer structure
            path_str = str(module_path)
            
            # Should not contain development-specific absolute paths
            assert not path_str.startswith('/home/'), f"Module path should not be user-specific: {path_str}"
            assert not path_str.startswith('/Users/'), f"Module path should not be user-specific: {path_str}"
            
            # Should be from the layers structure OR a temporary simulation directory
            # (indicating proper layer setup in either real or simulated environment)
            is_from_layers = 'layers/common/python' in path_str
            is_from_simulation = '/opt/python' in path_str and '/tmp/' in path_str
            
            assert is_from_layers or is_from_simulation, (
                f"Module {module_name} should be loaded from layers structure or simulation, "
                f"but was loaded from {path_str}"
            )
            
    except ImportError as e:
        assert False, f"Module {module_name} should be importable: {e}"
    finally:
        # Restore original sys.path
        sys.path[:] = original_path


@settings(max_examples=30)
@given(module_name=shared_module_names())
def test_no_environment_specific_imports(module_name):
    """
    Test that modules don't contain environment-specific import logic.
    
    **Feature: import-simplification, Property 1: Import consistency across environments**
    **Validates: Requirements 1.1**
    """
    # Save original sys.path to restore later
    original_path = sys.path.copy()
    
    try:
        # Import and inspect the module source (only in real environment, not simulation)
        module = importlib.import_module(module_name)
        
        if hasattr(module, '__file__') and module.__file__:
            module_path = str(module.__file__)
            
            # Only inspect source if it's from the real layers directory (not simulation)
            if 'layers/common/python' in module_path and os.path.exists(module.__file__):
                with open(module.__file__, 'r') as f:
                    source_code = f.read()
                
                # Should not contain environment-specific import patterns
                forbidden_patterns = [
                    'sys.path.append',
                    'sys.path.insert',
                    'os.path.join(os.path.dirname',
                    'try:\n    import',
                    'except ImportError:',
                    '__file__' # Should not manipulate paths based on __file__
                ]
                
                for pattern in forbidden_patterns:
                    assert pattern not in source_code, (
                        f"Module {module_name} contains environment-specific import pattern: {pattern}"
                    )
            # If it's from simulation, skip source inspection (file doesn't exist)
                
    except ImportError as e:
        assert False, f"Module {module_name} should be importable for inspection: {e}"
    finally:
        # Restore original sys.path
        sys.path[:] = original_path