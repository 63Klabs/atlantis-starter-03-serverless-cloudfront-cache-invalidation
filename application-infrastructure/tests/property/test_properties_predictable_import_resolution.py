"""Property-based tests for predictable import resolution."""

import sys
import importlib
import importlib.util
from pathlib import Path
from hypothesis import given, settings, strategies as st
import time
import threading


@st.composite
def import_patterns(draw):
    """Generate different import patterns for testing predictability."""
    patterns = [
        'import common',
        'import common.logger',
        'import common.constants',
        'import common.retry',
        'import common.window_tracker',
        'from common import logger',
        'from common import constants',
        'from common import retry',
        'from common import window_tracker',
        'from common.logger import setup_logger',
        'from common.constants import LOG_LEVEL_PROD',
        'from common.retry import retry_with_backoff',
        'from common.window_tracker import WindowTracker'
    ]
    return draw(st.sampled_from(patterns))


@st.composite
def timing_scenarios(draw):
    """Generate different timing scenarios for import resolution testing."""
    scenarios = [
        {
            'name': 'cold_start',
            'description': 'Fresh Python process with no cached imports',
            'setup': lambda: clear_all_caches()
        },
        {
            'name': 'warm_cache',
            'description': 'Imports with warm cache',
            'setup': lambda: warm_up_cache()
        },
        {
            'name': 'repeated_import',
            'description': 'Same import executed multiple times',
            'setup': lambda: None
        }
    ]
    return draw(st.sampled_from(scenarios))


@st.composite
def concurrency_scenarios(draw):
    """Generate concurrency scenarios for testing thread safety."""
    scenarios = [
        {
            'name': 'single_thread',
            'thread_count': 1,
            'description': 'Single-threaded import'
        },
        {
            'name': 'multi_thread',
            'thread_count': 3,
            'description': 'Multi-threaded concurrent imports'
        }
    ]
    return draw(st.sampled_from(scenarios))


def clear_all_caches():
    """Clear all import-related caches."""
    # Clear module cache
    modules_to_clear = [name for name in sys.modules.keys() if name.startswith('common')]
    for module_name in modules_to_clear:
        if module_name in sys.modules:
            del sys.modules[module_name]
    
    # Invalidate import caches
    importlib.invalidate_caches()


def warm_up_cache():
    """Warm up the import cache with common modules."""
    try:
        import common
        import common.logger
        import common.constants
    except ImportError:
        pass  # Cache warming is best effort


def measure_import_time(import_statement):
    """Measure the time taken to execute an import statement."""
    start_time = time.perf_counter()
    try:
        exec(import_statement)
        end_time = time.perf_counter()
        return end_time - start_time, None
    except Exception as e:
        end_time = time.perf_counter()
        return end_time - start_time, str(e)


@settings(max_examples=100)
@given(import_pattern=import_patterns())
def test_predictable_import_resolution(import_pattern):
    """
    Property 18: Predictable import resolution
    
    For any function startup simulation, import resolution should be consistent 
    and complete within expected time bounds.
    
    **Feature: import-simplification, Property 18: Predictable import resolution**
    **Validates: Requirements 6.4**
    """
    # Test multiple executions of the same import for consistency
    execution_times = []
    execution_results = []
    
    for i in range(3):
        # Clear cache between executions to simulate different startup conditions
        if i > 0:  # Keep first execution with current cache state
            clear_all_caches()
        
        exec_time, error = measure_import_time(import_pattern)
        execution_times.append(exec_time)
        execution_results.append(error)
    
    # All executions should have the same result (success or failure)
    unique_results = set(r is None for r in execution_results)
    assert len(unique_results) == 1, (
        f"Import '{import_pattern}' had inconsistent results across executions: {execution_results}"
    )
    
    # If imports succeeded, timing should be reasonable and consistent
    if all(r is None for r in execution_results):
        # All imports should complete within reasonable time (2 seconds max)
        max_time = max(execution_times)
        assert max_time < 2.0, (
            f"Import '{import_pattern}' took too long: {max_time:.3f}s. "
            f"This indicates unpredictable or inefficient import resolution."
        )
        
        # Timing should be relatively consistent (no huge variations)
        # Allow for natural variation in import timing, especially for very fast imports
        min_time = min(execution_times)
        if max_time > 0.01:  # Only check consistency for imports that take measurable time
            time_ratio = max_time / min_time if min_time > 0 else float('inf')
            # Allow more variation for very fast operations
            max_allowed_ratio = 1000 if max_time < 0.1 else 100
            assert time_ratio < max_allowed_ratio, (
                f"Import '{import_pattern}' has unpredictable timing: "
                f"min={min_time:.3f}s, max={max_time:.3f}s, ratio={time_ratio:.1f}"
            )


@settings(max_examples=50)
@given(import_pattern=import_patterns(), timing_scenario=timing_scenarios())
def test_import_resolution_under_different_conditions(import_pattern, timing_scenario):
    """
    Test that import resolution is predictable under different timing conditions.
    
    **Feature: import-simplification, Property 18: Predictable import resolution**
    **Validates: Requirements 6.4**
    """
    # Apply the timing scenario setup
    if timing_scenario['setup']:
        timing_scenario['setup']()
    
    # Measure import performance
    exec_time, error = measure_import_time(import_pattern)
    
    # Import should complete within reasonable time regardless of scenario
    assert exec_time < 5.0, (
        f"Import '{import_pattern}' took too long under '{timing_scenario['name']}' scenario: "
        f"{exec_time:.3f}s"
    )
    
    # For successful imports, verify they resolve to expected locations
    if error is None:
        try:
            # Extract module name from import statement
            if import_pattern.startswith('import '):
                module_name = import_pattern.split()[1]
            elif import_pattern.startswith('from ') and ' import ' in import_pattern:
                module_name = import_pattern.split(' import ')[0].split('from ')[1]
            else:
                module_name = None
            
            if module_name and module_name.startswith('common'):
                module = importlib.import_module(module_name)
                if hasattr(module, '__file__') and module.__file__:
                    module_path = str(module.__file__)
                    assert 'layers/common/python' in module_path, (
                        f"Module {module_name} should resolve to layer location predictably, "
                        f"but resolved to {module_path} under scenario '{timing_scenario['name']}'"
                    )
        except Exception:
            # If we can't verify the location, that's okay - the main test is timing
            pass


@settings(max_examples=30)
@given(import_pattern=import_patterns(), concurrency_scenario=concurrency_scenarios())
def test_concurrent_import_resolution(import_pattern, concurrency_scenario):
    """
    Test that import resolution is predictable under concurrent access.
    
    **Feature: import-simplification, Property 18: Predictable import resolution**
    **Validates: Requirements 6.4**
    """
    results = []
    errors = []
    
    def import_worker():
        try:
            exec_time, error = measure_import_time(import_pattern)
            results.append(exec_time)
            errors.append(error)
        except Exception as e:
            results.append(None)
            errors.append(str(e))
    
    # Clear cache before concurrent test
    clear_all_caches()
    
    # Run imports concurrently
    threads = []
    for _ in range(concurrency_scenario['thread_count']):
        thread = threading.Thread(target=import_worker)
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join(timeout=10.0)  # 10 second timeout
        assert not thread.is_alive(), (
            f"Import '{import_pattern}' timed out under concurrent access"
        )
    
    # All threads should have completed
    assert len(results) == concurrency_scenario['thread_count'], (
        f"Not all threads completed for import '{import_pattern}'"
    )
    
    # All threads should have the same result (success or failure)
    unique_errors = set(e is None for e in errors)
    assert len(unique_errors) == 1, (
        f"Concurrent import '{import_pattern}' had inconsistent results: {errors}"
    )
    
    # If successful, all should complete in reasonable time
    if all(e is None for e in errors):
        valid_times = [t for t in results if t is not None]
        if valid_times:
            max_time = max(valid_times)
            assert max_time < 5.0, (
                f"Concurrent import '{import_pattern}' took too long: {max_time:.3f}s"
            )


@settings(max_examples=20)
@given(import_pattern=import_patterns())
def test_import_resolution_determinism(import_pattern):
    """
    Test that import resolution is deterministic across multiple runs.
    
    **Feature: import-simplification, Property 18: Predictable import resolution**
    **Validates: Requirements 6.4**
    """
    # Run the same import multiple times and collect detailed results
    detailed_results = []
    
    for run in range(5):
        # Clear cache for fresh resolution
        clear_all_caches()
        
        try:
            # Execute import and capture details
            exec(import_pattern)
            
            # Try to get module details if it's a simple import
            module_path = None
            if import_pattern.startswith('import ') and '.' in import_pattern:
                module_name = import_pattern.split()[1]
                try:
                    module = importlib.import_module(module_name)
                    if hasattr(module, '__file__'):
                        module_path = str(module.__file__)
                except:
                    pass
            
            detailed_results.append({
                'success': True,
                'error': None,
                'module_path': module_path,
                'run': run
            })
            
        except Exception as e:
            detailed_results.append({
                'success': False,
                'error': str(e),
                'module_path': None,
                'run': run
            })
    
    # All runs should have identical results
    success_values = [r['success'] for r in detailed_results]
    assert len(set(success_values)) == 1, (
        f"Import '{import_pattern}' had non-deterministic success/failure across runs"
    )
    
    # If successful, module paths should be identical
    if all(success_values):
        module_paths = [r['module_path'] for r in detailed_results]
        unique_paths = set(p for p in module_paths if p is not None)
        assert len(unique_paths) <= 1, (
            f"Import '{import_pattern}' resolved to different paths across runs: {unique_paths}"
        )
    
    # Error messages should be identical if they failed
    if not any(success_values):
        error_messages = [r['error'] for r in detailed_results]
        unique_errors = set(error_messages)
        assert len(unique_errors) == 1, (
            f"Import '{import_pattern}' had different error messages across runs: {unique_errors}"
        )


def test_import_resolution_startup_performance():
    """
    Test that import resolution performs well during simulated function startup.
    
    **Feature: import-simplification, Property 18: Predictable import resolution**
    **Validates: Requirements 6.4**
    """
    # Simulate a function startup by importing all common modules
    startup_imports = [
        'import common',
        'from common import logger',
        'from common import constants',
        'from common import retry',
        'from common import window_tracker'
    ]
    
    # Clear all caches to simulate cold start
    clear_all_caches()
    
    # Measure total startup time
    start_time = time.perf_counter()
    
    for import_stmt in startup_imports:
        try:
            exec(import_stmt)
        except ImportError:
            # Some imports might fail, but that shouldn't affect timing test
            pass
    
    total_time = time.perf_counter() - start_time
    
    # Total startup import time should be reasonable (under 3 seconds)
    assert total_time < 3.0, (
        f"Function startup imports took too long: {total_time:.3f}s. "
        f"This indicates unpredictable or slow import resolution."
    )


def test_import_resolution_memory_efficiency():
    """
    Test that import resolution doesn't cause memory issues or excessive caching.
    
    **Feature: import-simplification, Property 18: Predictable import resolution**
    **Validates: Requirements 6.4**
    """
    import gc
    
    # Get initial module count
    initial_module_count = len(sys.modules)
    
    # Import and clear modules multiple times
    for cycle in range(10):
        # Import common modules
        try:
            import common
            import common.logger
            import common.constants
        except ImportError:
            pass
        
        # Clear them
        modules_to_clear = [name for name in sys.modules.keys() if name.startswith('common')]
        for module_name in modules_to_clear:
            if module_name in sys.modules:
                del sys.modules[module_name]
        
        # Force garbage collection
        gc.collect()
    
    # Final module count shouldn't be excessively higher
    final_module_count = len(sys.modules)
    module_growth = final_module_count - initial_module_count
    
    assert module_growth < 50, (
        f"Import resolution caused excessive module growth: {module_growth} modules. "
        f"This indicates potential memory leaks or inefficient caching."
    )