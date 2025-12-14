"""Property-based tests for shared module accessibility."""

import sys
import importlib
import importlib.util
from pathlib import Path
from hypothesis import given, settings, strategies as st
import tempfile
import os


@st.composite
def shared_modules(draw):
    """Generate shared module names that should be accessible to all functions."""
    modules = [
        'common.logger',
        'common.constants',
        'common.retry',
        'common.window_tracker'
    ]
    return draw(st.sampled_from(modules))


@st.composite
def function_contexts(draw):
    """Generate different function execution contexts."""
    contexts = [
        {
            'name': 'ingestor',
            'path': 'functions/ingestor',
            'description': 'Ingestor function context'
        },
        {
            'name': 'processor', 
            'path': 'functions/processor',
            'description': 'Processor function context'
        },
        {
            'name': 'test_environment',
            'path': 'tests',
            'description': 'Test execution context'
        }
    ]
    return draw(st.sampled_from(contexts))


@st.composite
def module_update_scenarios(draw):
    """Generate scenarios for testing module updates."""
    scenarios = [
        {
            'name': 'function_addition',
            'description': 'New function added to module',
            'change_type': 'addition'
        },
        {
            'name': 'function_modification',
            'description': 'Existing function modified',
            'change_type': 'modification'
        },
        {
            'name': 'constant_update',
            'description': 'Constants updated',
            'change_type': 'constant'
        }
    ]
    return draw(st.sampled_from(scenarios))


def simulate_function_context(context):
    """Simulate running in a specific function context."""
    base_path = Path(__file__).parent.parent.parent
    context_path = base_path / context['path']
    
    # Add context path to sys.path if not already there
    context_path_str = str(context_path)
    if context_path_str not in sys.path:
        sys.path.insert(0, context_path_str)
        return context_path_str
    return None


@settings(max_examples=100)
@given(module_name=shared_modules(), context=function_contexts())
def test_shared_module_accessibility(module_name, context):
    """
    Property 17: Shared module accessibility
    
    For any shared module update, all functions should be able to import 
    and access the updated module.
    
    **Feature: import-simplification, Property 17: Shared module accessibility**
    **Validates: Requirements 6.2**
    """
    # Save original state
    original_path = sys.path.copy()
    added_path = None
    
    try:
        # Simulate the function context
        added_path = simulate_function_context(context)
        
        # Clear module cache to ensure fresh import
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        # Test that the module is accessible from this context
        module = importlib.import_module(module_name)
        assert module is not None, f"Module {module_name} should be accessible from {context['name']} context"
        
        # Verify the module is loaded from the shared location (layer)
        if hasattr(module, '__file__') and module.__file__:
            module_path = str(module.__file__)
            assert 'layers/common/python' in module_path, (
                f"Module {module_name} should be loaded from shared layer location, "
                f"but was loaded from {module_path} in context {context['name']}"
            )
        
        # Test that we can access common attributes/functions
        if module_name == 'common.logger':
            # Should have logging functions
            assert hasattr(module, 'setup_logger') or hasattr(module, 'get_logger'), (
                f"Logger module should have logging functions accessible from {context['name']}"
            )
        elif module_name == 'common.constants':
            # Should have constants
            module_dict = dir(module)
            constants = [attr for attr in module_dict if attr.isupper()]
            assert len(constants) > 0, (
                f"Constants module should have constants accessible from {context['name']}"
            )
        elif module_name == 'common.retry':
            # Should have retry functionality
            assert hasattr(module, 'retry_with_backoff') or 'retry' in str(module.__dict__), (
                f"Retry module should have retry functions accessible from {context['name']}"
            )
        elif module_name == 'common.window_tracker':
            # Should have window tracking functionality
            assert hasattr(module, 'WindowTracker') or 'track' in str(module.__dict__), (
                f"Window tracker module should have tracking functions accessible from {context['name']}"
            )
            
    except ImportError as e:
        assert False, (
            f"Shared module {module_name} should be accessible from {context['name']} context, "
            f"but import failed: {e}"
        )
    finally:
        # Restore original state
        sys.path[:] = original_path


@settings(max_examples=50)
@given(module_name=shared_modules())
def test_module_updates_propagate_to_all_functions(module_name):
    """
    Test that when a shared module is updated, all functions see the changes.
    
    **Feature: import-simplification, Property 17: Shared module accessibility**
    **Validates: Requirements 6.2**
    """
    contexts = [
        {'name': 'ingestor', 'path': 'functions/ingestor'},
        {'name': 'processor', 'path': 'functions/processor'},
        {'name': 'test', 'path': 'tests'}
    ]
    
    # Save original state
    original_path = sys.path.copy()
    
    try:
        module_paths = []
        
        # Test that all contexts import the same module instance
        for context in contexts:
            # Clear cache
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            # Simulate context
            added_path = simulate_function_context(context)
            
            # Import module
            module = importlib.import_module(module_name)
            
            if hasattr(module, '__file__') and module.__file__:
                module_paths.append(str(module.__file__))
            else:
                module_paths.append(None)
        
        # All contexts should import from the same location (shared layer)
        unique_paths = set(p for p in module_paths if p is not None)
        assert len(unique_paths) <= 1, (
            f"Module {module_name} resolved to different paths from different contexts: {module_paths}. "
            f"This means updates won't propagate consistently."
        )
        
        # The shared location should be the layer
        if len(unique_paths) == 1:
            shared_path = list(unique_paths)[0]
            assert 'layers/common/python' in shared_path, (
                f"Shared module {module_name} should be in layer location, "
                f"but all contexts resolved to {shared_path}"
            )
            
    finally:
        # Restore original state
        sys.path[:] = original_path


@settings(max_examples=30)
@given(module_name=shared_modules(), context=function_contexts())
def test_no_module_shadowing(module_name, context):
    """
    Test that function-specific modules don't shadow shared modules.
    
    **Feature: import-simplification, Property 17: Shared module accessibility**
    **Validates: Requirements 6.2**
    """
    # Save original state
    original_path = sys.path.copy()
    
    try:
        # Simulate function context
        added_path = simulate_function_context(context)
        
        # Import the shared module
        module = importlib.import_module(module_name)
        
        if hasattr(module, '__file__') and module.__file__:
            module_path = str(module.__file__)
            
            # Should not be shadowed by function-specific modules
            function_specific_paths = ['functions/ingestor', 'functions/processor']
            for func_path in function_specific_paths:
                if func_path in module_path and 'layers' not in module_path:
                    assert False, (
                        f"Shared module {module_name} is being shadowed by function-specific module "
                        f"at {module_path} in context {context['name']}"
                    )
            
            # Should come from the shared layer
            assert 'layers/common/python' in module_path, (
                f"Shared module {module_name} should come from layer, "
                f"but came from {module_path} in context {context['name']}"
            )
            
    except ImportError as e:
        assert False, f"Shared module {module_name} should be accessible: {e}"
    finally:
        # Restore original state
        sys.path[:] = original_path


@settings(max_examples=20)
@given(module_name=shared_modules())
def test_module_accessibility_after_cache_clear(module_name):
    """
    Test that shared modules remain accessible after import cache is cleared.
    
    **Feature: import-simplification, Property 17: Shared module accessibility**
    **Validates: Requirements 6.2**
    """
    # First import
    try:
        module1 = importlib.import_module(module_name)
        path1 = str(module1.__file__) if hasattr(module1, '__file__') else None
    except ImportError as e:
        assert False, f"Initial import of {module_name} failed: {e}"
    
    # Clear cache
    if module_name in sys.modules:
        del sys.modules[module_name]
    importlib.invalidate_caches()
    
    # Second import after cache clear
    try:
        module2 = importlib.import_module(module_name)
        path2 = str(module2.__file__) if hasattr(module2, '__file__') else None
    except ImportError as e:
        assert False, f"Import of {module_name} failed after cache clear: {e}"
    
    # Should resolve to the same location
    assert path1 == path2, (
        f"Module {module_name} resolved to different paths before and after cache clear: "
        f"{path1} vs {path2}"
    )
    
    # Should still be from the layer
    if path2:
        assert 'layers/common/python' in path2, (
            f"Module {module_name} should still resolve from layer after cache clear, "
            f"but resolved from {path2}"
        )


def test_all_shared_modules_accessible_together():
    """
    Test that all shared modules can be imported together without conflicts.
    
    **Feature: import-simplification, Property 17: Shared module accessibility**
    **Validates: Requirements 6.2**
    """
    shared_modules_list = ['common.logger', 'common.constants', 'common.retry', 'common.window_tracker']
    
    # Clear all from cache
    for module_name in shared_modules_list:
        if module_name in sys.modules:
            del sys.modules[module_name]
    
    imported_modules = {}
    
    # Import all shared modules
    for module_name in shared_modules_list:
        try:
            module = importlib.import_module(module_name)
            imported_modules[module_name] = module
        except ImportError as e:
            assert False, f"Failed to import shared module {module_name}: {e}"
    
    # Verify all were imported successfully
    assert len(imported_modules) == len(shared_modules_list), (
        f"Not all shared modules were imported. Expected {len(shared_modules_list)}, "
        f"got {len(imported_modules)}"
    )
    
    # Verify they're all from the layer
    for module_name, module in imported_modules.items():
        if hasattr(module, '__file__') and module.__file__:
            module_path = str(module.__file__)
            assert 'layers/common/python' in module_path, (
                f"Module {module_name} should be from layer, but is from {module_path}"
            )


@settings(max_examples=20)
@given(context=function_contexts())
def test_shared_module_namespace_consistency(context):
    """
    Test that the 'common' namespace is consistent across all contexts.
    
    **Feature: import-simplification, Property 17: Shared module accessibility**
    **Validates: Requirements 6.2**
    """
    # Save original state
    original_path = sys.path.copy()
    
    try:
        # Simulate function context
        added_path = simulate_function_context(context)
        
        # Clear cache
        modules_to_clear = [name for name in sys.modules.keys() if name.startswith('common')]
        for module_name in modules_to_clear:
            if module_name in sys.modules:
                del sys.modules[module_name]
        
        # Import the common package
        common_module = importlib.import_module('common')
        
        # Verify it has the expected submodules available
        expected_submodules = ['logger', 'constants', 'retry', 'window_tracker']
        
        for submodule in expected_submodules:
            try:
                full_name = f'common.{submodule}'
                submod = importlib.import_module(full_name)
                assert submod is not None, f"Submodule {full_name} should be accessible"
            except ImportError as e:
                assert False, (
                    f"Submodule common.{submodule} should be accessible from {context['name']} context: {e}"
                )
        
        # Verify common module is from the layer
        if hasattr(common_module, '__file__') and common_module.__file__:
            common_path = str(common_module.__file__)
            assert 'layers/common/python' in common_path, (
                f"Common module should be from layer in {context['name']} context, "
                f"but is from {common_path}"
            )
            
    finally:
        # Restore original state
        sys.path[:] = original_path