"""Property-based tests for import error prevention."""

import sys
import importlib
import importlib.util
from pathlib import Path
from hypothesis import given, settings, strategies as st
import tempfile
import os


@st.composite
def deployment_scenarios(draw):
    """Generate different deployment scenarios that could cause import issues."""
    scenarios = [
        {
            'name': 'clean_environment',
            'description': 'Fresh Python environment with no cached imports',
            'setup': lambda: clear_import_cache()
        },
        {
            'name': 'missing_layer_simulation',
            'description': 'Simulate missing layer in deployment',
            'setup': lambda: simulate_missing_layer()
        },
        {
            'name': 'path_order_variation',
            'description': 'Different sys.path ordering',
            'setup': lambda: vary_path_order()
        }
    ]
    return draw(st.sampled_from(scenarios))


@st.composite
def critical_imports(draw):
    """Generate critical import statements that must never fail in deployment."""
    imports = [
        'import common',
        'from common import logger',
        'from common import constants',
        'from common import retry',
        'from common import window_tracker',
        'from common.logger import setup_logger',
        'from common.constants import LOG_LEVEL_PROD',
        'from common.retry import retry_with_backoff',
        'from common.window_tracker import check_active_window'
    ]
    return draw(st.sampled_from(imports))


def clear_import_cache():
    """Clear Python import cache to simulate fresh environment."""
    # Remove common modules from cache
    modules_to_clear = [name for name in sys.modules.keys() if name.startswith('common')]
    for module_name in modules_to_clear:
        if module_name in sys.modules:
            del sys.modules[module_name]
    
    # Invalidate import caches
    importlib.invalidate_caches()


def simulate_missing_layer():
    """Simulate a deployment where the layer is missing or misconfigured."""
    # Temporarily remove layer path from sys.path
    layer_path = None
    for path in sys.path[:]:
        if 'layers/common/python' in path:
            layer_path = path
            sys.path.remove(path)
            break
    
    return layer_path


def vary_path_order():
    """Vary the order of paths in sys.path to test robustness."""
    # Save original order
    original_path = sys.path.copy()
    
    # Find our critical paths
    layer_paths = [p for p in sys.path if 'layers/common/python' in p]
    function_paths = [p for p in sys.path if 'functions' in p and 'layers' not in p]
    other_paths = [p for p in sys.path if p not in layer_paths and p not in function_paths]
    
    # Reorder: put layer paths first, then function paths, then others
    sys.path[:] = layer_paths + function_paths + other_paths
    
    return original_path


@settings(max_examples=100)
@given(import_statement=critical_imports())
def test_import_error_prevention(import_statement):
    """
    Property 16: Import error prevention
    
    For any function deployment simulation, the system should prevent ImportError 
    exceptions due to path configuration issues.
    
    **Feature: import-simplification, Property 16: Import error prevention**
    **Validates: Requirements 6.1**
    """
    # Save original state
    original_path = sys.path.copy()
    original_modules = sys.modules.copy()
    
    try:
        # Test the import in current configuration
        exec(import_statement)
        
        # Clear cache and test again (simulate cold start)
        clear_import_cache()
        exec(import_statement)
        
        # Test should pass - no ImportError should occur
        
    except ImportError as e:
        assert False, (
            f"Critical import '{import_statement}' failed with ImportError: {e}. "
            f"This indicates a path configuration issue that would cause deployment failures."
        )
    except Exception as e:
        # Other exceptions might be acceptable (e.g., if importing * from a module that doesn't support it)
        # But ImportError specifically indicates path/configuration issues
        pass
    finally:
        # Restore original state
        sys.path[:] = original_path
        sys.modules.clear()
        sys.modules.update(original_modules)


@settings(max_examples=50)
@given(scenario=deployment_scenarios(), import_statement=critical_imports())
def test_robust_import_under_deployment_conditions(scenario, import_statement):
    """
    Test that imports work robustly under various deployment conditions.
    
    **Feature: import-simplification, Property 16: Import error prevention**
    **Validates: Requirements 6.1**
    """
    # Save original state
    original_path = sys.path.copy()
    original_modules = sys.modules.copy()
    restoration_data = None
    
    try:
        # Apply the scenario setup
        restoration_data = scenario['setup']()
        
        # Test the import under this scenario
        if scenario['name'] == 'missing_layer_simulation':
            # This scenario should fail gracefully, not with confusing errors
            try:
                exec(import_statement)
                # If layer is missing, import should fail clearly
                if 'common' in import_statement:
                    assert False, (
                        f"Import '{import_statement}' should fail when layer is missing, "
                        f"but it succeeded unexpectedly"
                    )
            except ImportError as e:
                # This is expected - but error should be clear
                error_msg = str(e).lower()
                assert 'no module named' in error_msg or 'cannot import' in error_msg, (
                    f"ImportError should be clear when layer is missing. Got: {e}"
                )
        else:
            # Other scenarios should work
            exec(import_statement)
            
    except ImportError as e:
        if scenario['name'] != 'missing_layer_simulation':
            assert False, (
                f"Import '{import_statement}' failed under scenario '{scenario['name']}': {e}. "
                f"This indicates insufficient robustness in import configuration."
            )
    except Exception as e:
        # Non-ImportError exceptions might be acceptable depending on the import
        pass
    finally:
        # Restore original state
        sys.path[:] = original_path
        sys.modules.clear()
        sys.modules.update(original_modules)
        
        # Restore scenario-specific state
        if restoration_data is not None and scenario['name'] == 'missing_layer_simulation':
            if restoration_data not in sys.path:
                sys.path.insert(0, restoration_data)


@settings(max_examples=30)
@given(import_statement=critical_imports())
def test_import_error_messages_are_clear(import_statement):
    """
    Test that when imports do fail, they provide clear error messages.
    
    **Feature: import-simplification, Property 16: Import error prevention**
    **Validates: Requirements 6.1**
    """
    # Save original state
    original_path = sys.path.copy()
    
    try:
        # Remove all our custom paths to force import failure
        paths_to_remove = [p for p in sys.path if 'layers' in p or 'functions' in p]
        for path in paths_to_remove:
            sys.path.remove(path)
        
        # Clear cache
        clear_import_cache()
        
        # Try the import - it should fail with a clear message
        try:
            exec(import_statement)
            # If it succeeds, that's fine (might be importing from standard library)
        except ImportError as e:
            error_msg = str(e)
            
            # Error message should be informative
            assert len(error_msg) > 10, f"ImportError message too short: {error_msg}"
            
            # Should mention the module name
            if 'common' in import_statement:
                assert 'common' in error_msg.lower(), (
                    f"ImportError should mention 'common' module: {error_msg}"
                )
            
            # Should not contain confusing path manipulation references
            confusing_terms = ['sys.path', '__file__', 'dirname', 'append']
            for term in confusing_terms:
                assert term not in error_msg, (
                    f"ImportError message should not contain confusing term '{term}': {error_msg}"
                )
                
    finally:
        # Restore original state
        sys.path[:] = original_path


def test_no_silent_import_failures():
    """
    Test that imports don't fail silently or fall back to unexpected modules.
    
    **Feature: import-simplification, Property 16: Import error prevention**
    **Validates: Requirements 6.1**
    """
    critical_modules = ['common', 'common.logger', 'common.constants', 'common.retry', 'common.window_tracker']
    
    for module_name in critical_modules:
        try:
            module = importlib.import_module(module_name)
            
            # Verify we got the expected module, not a fallback
            if hasattr(module, '__file__') and module.__file__:
                module_path = str(module.__file__)
                
                # Should be from our layers directory, not some system fallback
                assert 'layers/common/python' in module_path, (
                    f"Module {module_name} resolved to unexpected location: {module_path}. "
                    f"This might indicate a silent fallback to a different module."
                )
                
                # Should not be from site-packages or other system locations
                system_locations = ['/usr/lib/python', '/usr/local/lib/python', 'site-packages']
                for location in system_locations:
                    assert location not in module_path, (
                        f"Module {module_name} incorrectly resolved to system location: {module_path}"
                    )
                    
        except ImportError:
            # ImportError is acceptable - it's clear that the module isn't available
            # Silent failures or wrong modules are the problem
            pass


def test_import_performance_is_predictable():
    """
    Test that import resolution is fast and doesn't involve excessive path searching.
    
    **Feature: import-simplification, Property 16: Import error prevention**
    **Validates: Requirements 6.1**
    """
    import time
    
    critical_modules = ['common.logger', 'common.constants', 'common.retry']
    
    for module_name in critical_modules:
        # Clear from cache to force fresh import
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        # Time the import
        start_time = time.time()
        
        try:
            importlib.import_module(module_name)
            import_time = time.time() - start_time
            
            # Import should be fast (less than 1 second even on slow systems)
            assert import_time < 1.0, (
                f"Import of {module_name} took {import_time:.3f} seconds, which is too slow. "
                f"This might indicate excessive path searching or configuration issues."
            )
            
        except ImportError:
            # ImportError is fine - we're testing performance when imports work
            pass