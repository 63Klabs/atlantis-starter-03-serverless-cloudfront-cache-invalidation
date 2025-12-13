"""Property-based tests for architectural boundary enforcement."""

import ast
import os
import sys
from pathlib import Path
from typing import Set, List, Dict, Tuple

from hypothesis import given, settings, strategies as st


# Custom strategies for generating test data

@st.composite
def function_names(draw):
    """Generate Lambda function names that should be isolated."""
    functions = ['ingestor', 'processor']
    return draw(st.sampled_from(functions))


@st.composite
def function_directories(draw):
    """Generate function directory paths."""
    base_path = Path(__file__).parent.parent.parent  # application-infrastructure
    function_name = draw(function_names())
    return base_path / 'functions' / function_name


@st.composite
def python_files_in_function(draw):
    """Generate Python files within function directories."""
    function_dir = draw(function_directories())
    
    if not function_dir.exists():
        return None
    
    python_files = list(function_dir.rglob('*.py'))
    if not python_files:
        return None
    
    return draw(st.sampled_from(python_files))


def get_python_files_in_directory(directory: Path) -> List[Path]:
    """Get all Python files in a directory recursively.
    
    Args:
        directory: Directory to scan
        
    Returns:
        List of Python file paths
    """
    if not directory.exists():
        return []
    
    python_files = []
    for py_file in directory.rglob('*.py'):
        if py_file.name != '__init__.py':  # Exclude __init__.py files
            python_files.append(py_file)
    
    return python_files


def extract_imports_from_file(file_path: Path) -> Set[str]:
    """Extract import statements from a Python file.
    
    Args:
        file_path: Path to Python file
        
    Returns:
        Set of import module names
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        imports = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
        
        return imports
    except Exception:
        # If we can't parse the file, return empty set
        return set()


def get_cross_function_imports(function_name: str, imports: Set[str]) -> Set[str]:
    """Get imports that violate architectural boundaries.
    
    Args:
        function_name: Name of the function being analyzed
        imports: Set of import module names from the function
        
    Returns:
        Set of imports that violate architectural boundaries
    """
    other_functions = ['ingestor', 'processor']
    if function_name in other_functions:
        other_functions.remove(function_name)
    
    violations = set()
    for import_name in imports:
        for other_function in other_functions:
            if import_name.startswith(f'{other_function}.'):
                violations.add(import_name)
    
    return violations


def get_allowed_imports() -> Set[str]:
    """Get imports that are allowed for all functions.
    
    Returns:
        Set of allowed import prefixes
    """
    return {
        'common.',  # Lambda layer imports
        'boto3',    # AWS SDK
        'botocore', # AWS SDK core
        'json',     # Standard library
        'os',       # Standard library
        'sys',      # Standard library
        'typing',   # Standard library
        'datetime', # Standard library
        'time',     # Standard library
        'uuid',     # Standard library
        'logging',  # Standard library
        'pathlib',  # Standard library
        'urllib',   # Standard library
        're',       # Standard library
        'base64',   # Standard library
        'hashlib',  # Standard library
        'collections', # Standard library
        'itertools',   # Standard library
        'functools',   # Standard library
    }


def is_allowed_import(import_name: str, function_name: str) -> bool:
    """Check if an import is allowed for a function.
    
    Args:
        import_name: Name of the import
        function_name: Name of the function
        
    Returns:
        True if import is allowed, False otherwise
    """
    allowed_imports = get_allowed_imports()
    
    # Allow imports from the same function
    if import_name.startswith(f'{function_name}.'):
        return True
    
    # Allow standard library and common layer imports
    for allowed_prefix in allowed_imports:
        if import_name.startswith(allowed_prefix):
            return True
    
    # Allow exact matches for standard library modules
    standard_modules = {
        'json', 'os', 'sys', 'typing', 'datetime', 'time', 'uuid',
        'logging', 'pathlib', 'urllib', 're', 'base64', 'hashlib',
        'collections', 'itertools', 'functools', 'ast', 'inspect'
    }
    if import_name in standard_modules:
        return True
    
    return False


# Property Tests

@settings(max_examples=100, deadline=5000)
@given(function_names())
def test_property_4_architectural_boundary_enforcement(function_name):
    """Property 4: Architectural boundary enforcement.
    
    For any function directory, it should not contain imports or dependencies 
    from other function directories (only layer imports allowed).
    
    **Feature: lambda-function-separation, Property 4: Architectural boundary enforcement**
    **Validates: Requirements 1.4**
    """
    base_path = Path(__file__).parent.parent.parent  # application-infrastructure
    function_dir = base_path / 'functions' / function_name
    
    # Skip test if function directory doesn't exist yet
    if not function_dir.exists():
        return
    
    # Get all Python files in this function directory
    python_files = get_python_files_in_directory(function_dir)
    
    # Skip if no Python files
    if not python_files:
        return
    
    # Check each Python file for architectural boundary violations
    violations = []
    
    for py_file in python_files:
        # Extract imports from the file
        imports = extract_imports_from_file(py_file)
        
        # Check for cross-function imports (architectural violations)
        cross_function_imports = get_cross_function_imports(function_name, imports)
        
        if cross_function_imports:
            violations.append({
                'file': str(py_file.relative_to(base_path)),
                'violations': list(cross_function_imports)
            })
    
    # Assert no architectural boundary violations
    assert len(violations) == 0, (
        f"Function {function_name} contains architectural boundary violations:\n" +
        "\n".join([
            f"  File: {v['file']}\n    Violations: {', '.join(v['violations'])}"
            for v in violations
        ]) +
        f"\n\nFunctions should only import from:\n"
        f"  - Their own modules ({function_name}.*)\n"
        f"  - The common layer (common.*)\n"
        f"  - Standard library modules\n"
        f"  - AWS SDK modules (boto3, botocore)\n"
        f"\nThey should NOT import from other function directories."
    )


@settings(max_examples=50, deadline=3000)
@given(python_files_in_function())
def test_property_4_individual_file_boundary_enforcement(py_file):
    """Property 4b: Individual file boundary enforcement.
    
    For any Python file in a function directory, it should not import
    modules from other function directories.
    
    **Feature: lambda-function-separation, Property 4: Architectural boundary enforcement**
    **Validates: Requirements 1.4**
    """
    if py_file is None:
        return
    
    base_path = Path(__file__).parent.parent.parent  # application-infrastructure
    
    # Determine which function this file belongs to
    try:
        relative_path = py_file.relative_to(base_path)
        path_parts = relative_path.parts
        
        if len(path_parts) < 3 or path_parts[0] != 'functions':
            return  # Not in functions directory
        
        function_name = path_parts[1]
        if function_name not in ['ingestor', 'processor']:
            return  # Unknown function
        
    except ValueError:
        return  # File not in base path
    
    # Extract imports from the file
    imports = extract_imports_from_file(py_file)
    
    # Check each import for architectural violations
    violations = []
    for import_name in imports:
        if not is_allowed_import(import_name, function_name):
            # Check if it's a cross-function import
            other_functions = ['ingestor', 'processor']
            if function_name in other_functions:
                other_functions.remove(function_name)
            
            for other_function in other_functions:
                if import_name.startswith(f'{other_function}.'):
                    violations.append(import_name)
    
    # Assert no violations
    assert len(violations) == 0, (
        f"File {py_file.relative_to(base_path)} in function {function_name} "
        f"contains architectural boundary violations: {', '.join(violations)}\n"
        f"Functions should not import from other function directories."
    )


@settings(max_examples=30, deadline=2000)
@given(function_names())
def test_property_4_layer_import_compliance(function_name):
    """Property 4c: Layer import compliance.
    
    For any function, all imports from the common layer should use
    the correct 'common.' prefix, not relative paths.
    
    **Feature: lambda-function-separation, Property 4: Architectural boundary enforcement**
    **Validates: Requirements 1.4**
    """
    base_path = Path(__file__).parent.parent.parent  # application-infrastructure
    function_dir = base_path / 'functions' / function_name
    
    # Skip test if function directory doesn't exist yet
    if not function_dir.exists():
        return
    
    # Get all Python files in this function directory
    python_files = get_python_files_in_directory(function_dir)
    
    # Skip if no Python files
    if not python_files:
        return
    
    # Check each Python file for proper layer imports
    violations = []
    
    for py_file in python_files:
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for problematic import patterns
            lines = content.split('\n')
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # Check for relative imports to common modules
                if ('from ..common' in line or 
                    'import ..common' in line or
                    'sys.path.insert' in line):
                    violations.append({
                        'file': str(py_file.relative_to(base_path)),
                        'line': line_num,
                        'content': line
                    })
        
        except Exception:
            # Skip files we can't read
            continue
    
    # Assert no violations
    assert len(violations) == 0, (
        f"Function {function_name} contains improper layer import patterns:\n" +
        "\n".join([
            f"  File: {v['file']}:{v['line']}\n    Content: {v['content']}"
            for v in violations
        ]) +
        f"\n\nFunctions should import from the layer using 'from common.' syntax, "
        f"not relative imports or sys.path manipulation."
    )


@settings(max_examples=20, deadline=1500)
@given(function_names())
def test_property_4_function_isolation_completeness(function_name):
    """Property 4d: Function isolation completeness.
    
    For any function, it should be completely self-contained except for
    allowed dependencies (layer, standard library, AWS SDK).
    
    **Feature: lambda-function-separation, Property 4: Architectural boundary enforcement**
    **Validates: Requirements 1.4**
    """
    base_path = Path(__file__).parent.parent.parent  # application-infrastructure
    function_dir = base_path / 'functions' / function_name
    
    # Skip test if function directory doesn't exist yet
    if not function_dir.exists():
        return
    
    # Get all Python files in this function directory
    python_files = get_python_files_in_directory(function_dir)
    
    # Skip if no Python files
    if not python_files:
        return
    
    # Collect all imports across all files in the function
    all_imports = set()
    for py_file in python_files:
        imports = extract_imports_from_file(py_file)
        all_imports.update(imports)
    
    # Categorize imports
    allowed_imports = set()
    disallowed_imports = set()
    
    for import_name in all_imports:
        if is_allowed_import(import_name, function_name):
            allowed_imports.add(import_name)
        else:
            disallowed_imports.add(import_name)
    
    # Assert function is properly isolated
    assert len(disallowed_imports) == 0, (
        f"Function {function_name} has disallowed imports that break isolation: "
        f"{', '.join(sorted(disallowed_imports))}\n"
        f"Allowed import categories:\n"
        f"  - Same function modules ({function_name}.*)\n"
        f"  - Common layer (common.*)\n"
        f"  - Standard library modules\n"
        f"  - AWS SDK (boto3, botocore)\n"
        f"\nActual allowed imports found: {', '.join(sorted(allowed_imports))}"
    )


@settings(max_examples=10, deadline=1000)
@given(st.just('functions'))
def test_property_4_functions_directory_boundary_enforcement(functions_dir_name):
    """Property 4e: Functions directory boundary enforcement.
    
    For any functions directory, each function subdirectory should be
    completely isolated from other function subdirectories.
    
    **Feature: lambda-function-separation, Property 4: Architectural boundary enforcement**
    **Validates: Requirements 1.4**
    """
    base_path = Path(__file__).parent.parent.parent  # application-infrastructure
    functions_dir = base_path / functions_dir_name
    
    # Skip test if functions directory doesn't exist yet
    if not functions_dir.exists():
        return
    
    # Get all function directories
    function_dirs = [d for d in functions_dir.iterdir() 
                    if d.is_dir() and not d.name.startswith('.')]
    
    if len(function_dirs) < 2:
        return  # Need at least 2 functions to test isolation
    
    # Check isolation between each pair of functions
    violations = []
    
    for i, func_dir_1 in enumerate(function_dirs):
        for func_dir_2 in function_dirs[i+1:]:
            func_name_1 = func_dir_1.name
            func_name_2 = func_dir_2.name
            
            # Get Python files from both functions
            files_1 = get_python_files_in_directory(func_dir_1)
            files_2 = get_python_files_in_directory(func_dir_2)
            
            # Check if function 1 imports from function 2
            for py_file in files_1:
                imports = extract_imports_from_file(py_file)
                cross_imports = [imp for imp in imports if imp.startswith(f'{func_name_2}.')]
                if cross_imports:
                    violations.append({
                        'from_function': func_name_1,
                        'to_function': func_name_2,
                        'file': str(py_file.relative_to(base_path)),
                        'imports': cross_imports
                    })
            
            # Check if function 2 imports from function 1
            for py_file in files_2:
                imports = extract_imports_from_file(py_file)
                cross_imports = [imp for imp in imports if imp.startswith(f'{func_name_1}.')]
                if cross_imports:
                    violations.append({
                        'from_function': func_name_2,
                        'to_function': func_name_1,
                        'file': str(py_file.relative_to(base_path)),
                        'imports': cross_imports
                    })
    
    # Assert no cross-function dependencies
    assert len(violations) == 0, (
        f"Found architectural boundary violations between functions:\n" +
        "\n".join([
            f"  {v['from_function']} -> {v['to_function']}\n"
            f"    File: {v['file']}\n"
            f"    Imports: {', '.join(v['imports'])}"
            for v in violations
        ]) +
        f"\n\nFunctions should be completely isolated from each other."
    )