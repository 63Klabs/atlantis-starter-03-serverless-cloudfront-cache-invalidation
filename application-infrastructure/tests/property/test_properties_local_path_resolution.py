"""Property-based tests for local path resolution matching Lambda structure."""

import sys
import importlib
from pathlib import Path
from hypothesis import given, settings, strategies as st


@st.composite
def lambda_path_structures(draw):
    """Generate Lambda runtime path structures for testing."""
    structures = [
        {
            'name': 'layer_first',
            'description': 'Layer path before function path (Lambda default)',
            'paths': ['/opt/python', '/var/task']
        },
        {
            'name': 'function_first', 
            'description': 'Function path before layer path',
            'paths': ['/var/task', '/opt/python']
        }
    ]
    return draw(st.sampled_from(structures))


@st.composite
def common_modules(draw):
    """Generate common module names for path resolution testing."""
    modules = [
        'common',
        'common.logger',
        'common.constants',
        'common.retry', 
        'common.window_tracker'
    ]
    return draw(st.sampled_from(modules))


def get_local_equivalent_paths():
    """Get the local paths that should mirror Lambda structure."""
    base_path = Path(__file__).parent.parent.parent
    
    return {
        '/var/task': str(base_path / 'functions'),  # Function code location
        '/opt/python': str(base_path / 'layers' / 'common' / 'python')  # Layer location
    }


@settings(max_examples=100)
@given(module_name=common_modules())
def test_local_path_resolution_matches_lambda_structure(module_name):
    """
    Property 5: Local path resolution matches Lambda structure
    
    For any local development setup, the sys.path should mirror Lambda's runtime 
    path structure with layer and function paths.
    
    **Feature: import-simplification, Property 5: Local path resolution matches Lambda structure**
    **Validates: Requirements 2.3**
    """
    local_paths = get_local_equivalent_paths()
    
    # Verify that local sys.path contains Lambda-equivalent paths
    lambda_layer_equivalent = local_paths['/opt/python']
    lambda_function_equivalent = local_paths['/var/task']
    
    assert lambda_layer_equivalent in sys.path, (
        f"Local sys.path should contain Lambda layer equivalent: {lambda_layer_equivalent}"
    )
    
    assert lambda_function_equivalent in sys.path, (
        f"Local sys.path should contain Lambda function equivalent: {lambda_function_equivalent}"
    )
    
    # Test that module resolution works with this structure
    try:
        module = importlib.import_module(module_name)
        
        if hasattr(module, '__file__') and module.__file__:
            module_path = str(module.__file__)
            
            # Module should be resolved from the layer path (for common modules)
            # Allow for both real layer path and simulated environments
            is_from_real_layer = lambda_layer_equivalent in module_path
            is_from_simulation = '/opt/python' in module_path and '/tmp/' in module_path
            
            assert is_from_real_layer or is_from_simulation, (
                f"Common module {module_name} should resolve from layer path {lambda_layer_equivalent} "
                f"or simulation environment, but resolved from {module_path}"
            )
            
    except ImportError as e:
        assert False, f"Module {module_name} should be resolvable with Lambda-like path structure: {e}"


@settings(max_examples=50)
@given(path_structure=lambda_path_structures())
def test_path_order_matches_lambda_priority(path_structure):
    """
    Test that local path ordering matches Lambda's resolution priority.
    
    **Feature: import-simplification, Property 5: Local path resolution matches Lambda structure**
    **Validates: Requirements 2.3**
    """
    local_paths = get_local_equivalent_paths()
    
    # Map Lambda paths to local equivalents
    local_equivalent_paths = []
    for lambda_path in path_structure['paths']:
        if lambda_path in local_paths:
            local_equivalent_paths.append(local_paths[lambda_path])
    
    # Find positions in sys.path
    path_positions = {}
    for local_path in local_equivalent_paths:
        try:
            path_positions[local_path] = sys.path.index(local_path)
        except ValueError:
            assert False, f"Required path {local_path} not found in sys.path"
    
    # For Lambda's default behavior (/var/task before /opt/python)
    # Local equivalent should be functions before layers/common/python
    function_path = local_paths['/var/task']
    layer_path = local_paths['/opt/python']
    
    if function_path in path_positions and layer_path in path_positions:
        # Function path should come before layer path (higher priority)
        assert path_positions[function_path] < path_positions[layer_path], (
            f"Function path {function_path} should have higher priority than layer path {layer_path}. "
            f"Current positions: function={path_positions[function_path]}, layer={path_positions[layer_path]}"
        )


@settings(max_examples=30)
@given(module_name=common_modules())
def test_resolution_deterministic_across_restarts(module_name):
    """
    Test that path resolution is deterministic and consistent across test runs.
    
    **Feature: import-simplification, Property 5: Local path resolution matches Lambda structure**
    **Validates: Requirements 2.3**
    """
    # Clear module from cache to force fresh resolution
    if module_name in sys.modules:
        del sys.modules[module_name]
    
    # Import module multiple times and verify consistent resolution
    module_paths = []
    
    for _ in range(3):
        try:
            # Clear from cache
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            # Import fresh
            module = importlib.import_module(module_name)
            
            if hasattr(module, '__file__') and module.__file__:
                module_paths.append(str(module.__file__))
            else:
                module_paths.append(None)
                
        except ImportError as e:
            assert False, f"Module {module_name} should be consistently importable: {e}"
    
    # All paths should be identical (deterministic resolution)
    assert len(set(module_paths)) == 1, (
        f"Module {module_name} resolved to different paths across imports: {module_paths}"
    )
    
    # Path should be from the expected location (layer)
    if module_paths[0] is not None:
        local_paths = get_local_equivalent_paths()
        layer_path = local_paths['/opt/python']
        
        assert layer_path in module_paths[0], (
            f"Module {module_name} should consistently resolve from layer path {layer_path}, "
            f"but resolved from {module_paths[0]}"
        )


def test_no_duplicate_paths_in_resolution():
    """
    Test that sys.path doesn't contain duplicate entries that could cause confusion.
    
    **Feature: import-simplification, Property 5: Local path resolution matches Lambda structure**
    **Validates: Requirements 2.3**
    """
    local_paths = get_local_equivalent_paths()
    
    # Check for duplicates of our critical paths
    for lambda_path, local_path in local_paths.items():
        occurrences = sys.path.count(local_path)
        assert occurrences <= 1, (
            f"Path {local_path} (Lambda equivalent of {lambda_path}) appears {occurrences} times in sys.path. "
            f"This could cause unpredictable import resolution."
        )


def test_path_structure_mirrors_lambda_exactly():
    """
    Test that the overall path structure mirrors Lambda's structure.
    
    **Feature: import-simplification, Property 5: Local path resolution matches Lambda structure**
    **Validates: Requirements 2.3**
    """
    local_paths = get_local_equivalent_paths()
    
    # Verify all required Lambda-equivalent paths exist and are accessible
    for lambda_path, local_path in local_paths.items():
        path_obj = Path(local_path)
        
        assert path_obj.exists(), (
            f"Local path {local_path} (Lambda equivalent of {lambda_path}) does not exist"
        )
        
        assert path_obj.is_dir(), (
            f"Local path {local_path} (Lambda equivalent of {lambda_path}) is not a directory"
        )
        
        # For layer path, verify it contains the common module structure
        if lambda_path == '/opt/python':
            common_path = path_obj / 'common'
            assert common_path.exists(), (
                f"Layer path {local_path} should contain 'common' directory"
            )
            
            init_file = common_path / '__init__.py'
            assert init_file.exists(), (
                f"Common module directory should contain __init__.py: {init_file}"
            )