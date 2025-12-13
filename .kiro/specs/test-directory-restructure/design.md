# Design Document

## Overview

This design outlines the restructuring of the test directory organization in the application-infrastructure project. The current structure places tests within the src directory (`application-infrastructure/src/tests/`), which mixes test code with application source code. The new structure will move tests to the same level as src (`application-infrastructure/tests/`), creating a cleaner separation and following Python project best practices.

The restructuring involves moving three test subdirectories (integration, property, unit) and updating all import paths to work from the new location. Additionally, a dedicated test virtual environment will be established to isolate test dependencies.

## Architecture

### Current Structure
```
application-infrastructure/
├── src/
│   ├── common/
│   ├── ingestor/
│   ├── processor/
│   └── tests/          # Current location
│       ├── integration/
│       ├── property/
│       └── unit/
├── requirements.txt
└── buildspec.yml
```

### Target Structure
```
application-infrastructure/
├── src/
│   ├── common/
│   ├── ingestor/
│   └── processor/
├── tests/              # New location
│   ├── integration/
│   ├── property/
│   ├── unit/
│   ├── requirements.txt    # Test-specific dependencies
│   └── .venv-test/         # Test virtual environment
├── requirements.txt    # Application dependencies
└── buildspec.yml
```

## Components and Interfaces

### Directory Structure Components

1. **Test Directory Root** (`application-infrastructure/tests/`)
   - Contains all test-related files and subdirectories
   - Houses the test virtual environment
   - Includes test-specific configuration files

2. **Test Subdirectories**
   - `integration/`: Integration tests requiring AWS resources
   - `property/`: Property-based tests using Hypothesis
   - `unit/`: Unit tests for individual components

3. **Test Virtual Environment** (`.venv-test/`)
   - Isolated Python environment for test execution
   - Contains test-specific dependencies
   - Separate from application runtime dependencies

### Import Path Updates

The restructuring requires updating Python import statements in test files:

- **Current imports**: `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))`
- **New imports**: `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))`

### Build System Integration

The build system (CodeBuild via buildspec.yml) needs updates to:
- Install test dependencies in the correct location
- Execute tests from the new directory structure
- Maintain existing test discovery patterns

## Data Models

### File Movement Mapping

```python
# Source to destination mapping
file_moves = {
    'src/tests/integration/': 'tests/integration/',
    'src/tests/property/': 'tests/property/',
    'src/tests/unit/': 'tests/unit/',
}

# Import path transformations
import_updates = {
    "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))": 
    "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))",
    
    "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))":
    "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))"
}
```

### Virtual Environment Configuration

```python
# Test environment setup
test_env_config = {
    'name': '.venv-test',
    'location': 'application-infrastructure/tests/.venv-test',
    'requirements_file': 'application-infrastructure/tests/requirements.txt',
    'python_version': '3.9+',
    'dependencies': [
        'pytest>=8.3.3',
        'pytest-mock>=3.14.0',
        'hypothesis>=6.112.1',
        'moto[all]>=5.0.18',
        'boto3>=1.35.36',
        'botocore>=1.35.36'
    ]
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Based on the prework analysis, I need to perform a property reflection to eliminate redundancy:

**Property Reflection:**
- Properties 2.1, 2.4, and parts of 2.3 all test import resolution - these can be combined into one comprehensive property
- Properties 1.3 and 1.4 both test file preservation - these can be combined 
- Properties 3.1 and 3.2 both test configuration file updates - these can be combined
- Property 3.4 is too general and covered by other specific properties - remove
- Properties 4.2 and 4.4 both test virtual environment setup - these can be combined

**Property 1: Directory structure transformation**
*For any* test directory restructuring operation, all test files should be moved from `src/tests/` to `tests/` while preserving the subdirectory organization (integration, property, unit)
**Validates: Requirements 1.3, 1.4**

**Property 2: Import path consistency**
*For any* Python test file after restructuring, all import statements should resolve correctly from the new location without module not found errors
**Validates: Requirements 2.1, 2.2, 2.4**

**Property 3: Configuration file updates**
*For any* build or CI configuration file, references to test directories should be updated to point to the new `tests/` location
**Validates: Requirements 3.1, 3.2**

**Property 4: Virtual environment dependency completeness**
*For any* test virtual environment setup, all required testing libraries and dependencies should be installed and available for import
**Validates: Requirements 4.2, 4.4**

## Error Handling

### File Operation Errors
- **Missing source files**: Verify all expected test files exist before starting the move operation
- **Permission errors**: Ensure write permissions for creating new directories and moving files
- **Disk space**: Verify sufficient disk space for the restructuring operation

### Import Resolution Errors
- **Broken imports**: Validate that all import statements can be resolved after path updates
- **Circular imports**: Detect and handle any circular import dependencies
- **Missing modules**: Ensure all referenced modules exist in the expected locations

### Virtual Environment Errors
- **Python version compatibility**: Verify Python version meets requirements for test dependencies
- **Package installation failures**: Handle cases where test dependencies cannot be installed
- **Environment activation**: Ensure virtual environment can be properly activated and used

### Build System Integration Errors
- **Configuration parsing**: Handle malformed build configuration files gracefully
- **Path resolution**: Ensure build system can find tests in the new location
- **Test discovery**: Verify test runners can discover all test files

## Testing Strategy

### Dual Testing Approach

This design requires both unit testing and property-based testing approaches:

**Unit Testing:**
- Verify specific directory operations (create, move, delete)
- Test individual import path transformations
- Validate specific configuration file updates
- Test virtual environment creation and activation

**Property-Based Testing:**
- Use **Hypothesis** as the property-based testing library for Python
- Configure each property-based test to run a minimum of **100 iterations**
- Tag each property-based test with comments referencing the design document properties

**Property-Based Test Requirements:**
- Each correctness property must be implemented by a single property-based test
- Tests must be tagged using the format: '**Feature: test-directory-restructure, Property {number}: {property_text}**'
- Property tests verify universal behaviors across all valid inputs
- Unit tests handle specific examples and edge cases

**Test Coverage:**
- File system operations and directory structure validation
- Import statement parsing and path resolution
- Configuration file parsing and updates
- Virtual environment setup and dependency management
- Integration with existing build and CI systems

The testing strategy ensures comprehensive validation of the restructuring process while maintaining the existing test execution capabilities and adding the new virtual environment management features.