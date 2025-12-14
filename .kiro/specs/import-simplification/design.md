# Import Simplification Design Document

## Overview

This design implements a clean, industry-standard import structure for the Lambda function project that eliminates complex sys.path manipulation and provides consistent import patterns across local development and AWS runtime environments. The solution mirrors Lambda's runtime behavior by organizing shared code in a layer structure that matches AWS's `/opt/python` and `/var/task` paths.

## Architecture

### Current State Analysis

The existing codebase has several import-related issues:
- Manual sys.path manipulation in each function handler
- Inconsistent import patterns with try/catch fallbacks
- Mixed relative and absolute imports
- Complex testing setup requiring manual path configuration
- Shared utilities scattered between functions and common layer

### Target Architecture

```
application-infrastructure/
├── layers/
│   └── common/
│       ├── python/
│       │   └── common/           # Mirrors /opt/python/common in Lambda
│       │       ├── __init__.py
│       │       ├── logger.py     # Multi-function utilities
│       │       ├── constants.py
│       │       ├── retry.py
│       │       └── window_tracker.py
│       └── requirements.txt
│
├── functions/
│   ├── ingestor/
│   │   ├── handler.py            # Clean imports: from common.logger import setup_logger
│   │   ├── event_parser.py       # Function-specific, stays here
│   │   ├── event_filter.py
│   │   ├── queue_client.py
│   │   ├── scheduler_client.py
│   │   └── requirements.txt
│   │
│   └── processor/
│       ├── handler.py            # Clean imports: from common.logger import setup_logger
│       ├── distribution_finder.py # Function-specific, stays here
│       ├── invalidation_client.py
│       ├── path_consolidator.py
│       ├── path_validator.py
│       ├── queue_client.py
│       ├── tag_validator.py
│       └── requirements.txt
│
└── tests/
    ├── conftest.py               # Single path setup for all tests
    ├── unit/
    └── integration/
```

### Import Resolution Strategy

**Lambda Runtime Behavior:**
- `/var/task` (function code) - highest priority
- `/opt/python` (layer code) - second priority
- Standard library - lowest priority

**Local Development Mirroring:**
- `functions/{function_name}/` maps to `/var/task`
- `layers/common/python/` maps to `/opt/python`
- conftest.py adds layer path to sys.path once

## Components and Interfaces

### Layer Structure

**Common Layer (`layers/common/python/common/`)**
- Contains only utilities used by multiple functions
- Provides clean namespace: `from common.module import function`
- Packaged as Lambda layer with `python/common/` structure

**Current Multi-Function Utilities:**
- `logger.py` - Used by both functions
- `constants.py` - Shared constants
- `retry.py` - Retry logic utilities  
- `window_tracker.py` - DynamoDB window management

### Function Structure

**Ingestor Function (`functions/ingestor/`)**
- `handler.py` - Main Lambda handler
- `event_parser.py` - S3 event parsing (ingestor-specific)
- `event_filter.py` - Event filtering logic (ingestor-specific)
- `queue_client.py` - SQS operations (ingestor-specific)
- `scheduler_client.py` - EventBridge scheduler (ingestor-specific)

**Processor Function (`functions/processor/`)**
- `handler.py` - Main Lambda handler
- `distribution_finder.py` - CloudFront discovery (processor-specific)
- `invalidation_client.py` - CloudFront invalidation (processor-specific)
- `path_consolidator.py` - Path consolidation logic (processor-specific)
- `path_validator.py` - Path validation (processor-specific)
- `queue_client.py` - SQS operations (processor-specific)
- `tag_validator.py` - Tag validation (processor-specific)

### Import Patterns

**Standard Pattern for All Functions:**
```python
# Clean imports - no sys.path manipulation
from common.logger import setup_logger
from common.constants import LOG_LEVEL_PROD
from common.retry import retry_with_backoff

# Function-specific imports (relative to function directory)
from event_parser import extract_event_metadata
from queue_client import send_event_to_queue
```

**Test Configuration (`tests/conftest.py`):**
```python
import sys
from pathlib import Path

# Add layer path once for all tests
layer_path = Path(__file__).parent.parent / "layers" / "common" / "python"
sys.path.insert(0, str(layer_path))
```

## Data Models

### Import Resolution Model

```python
# Lambda Runtime Resolution Order
resolution_order = [
    "/var/task",           # Function code (highest priority)
    "/opt/python",         # Layer code
    "/var/runtime",        # Lambda runtime
    # Standard library paths
]

# Local Development Resolution Order  
local_resolution_order = [
    "functions/{function_name}/",     # Function code (highest priority)
    "layers/common/python/",          # Layer code (via conftest.py)
    # Standard library paths
]
```

### Module Classification

```python
# Multi-function utilities (move to common layer)
common_modules = [
    "logger",           # JSON logging with environment detection
    "constants",        # Shared constants and configuration
    "retry",           # Retry logic with exponential backoff
    "window_tracker"   # DynamoDB window management
]

# Function-specific modules (keep with functions)
ingestor_modules = [
    "event_parser",     # S3 event parsing
    "event_filter",     # Event filtering logic
    "queue_client",     # SQS operations for ingestor
    "scheduler_client"  # EventBridge scheduler operations
]

processor_modules = [
    "distribution_finder",  # CloudFront distribution discovery
    "invalidation_client",  # CloudFront invalidation operations
    "path_consolidator",    # Path consolidation logic
    "path_validator",       # CloudFront path validation
    "queue_client",         # SQS operations for processor
    "tag_validator"         # S3 and CloudFront tag validation
]
```

## Data Models

### Package Structure Model

```python
# Layer package structure (matches Lambda expectations)
layer_package = {
    "python/": {
        "common/": {
            "__init__.py": "# Common utilities package",
            "logger.py": "# JSON logging utilities",
            "constants.py": "# Shared constants",
            "retry.py": "# Retry logic",
            "window_tracker.py": "# DynamoDB operations"
        }
    }
}

# Function package structure (minimal, function-specific only)
function_package = {
    "handler.py": "# Main Lambda handler",
    "event_parser.py": "# Function-specific module",
    "queue_client.py": "# Function-specific module",
    # No common utilities (provided by layer)
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Property 1: Import consistency across environments
*For any* shared module import statement, the import should work identically in local development and simulated Lambda environment structures
**Validates: Requirements 1.1**

Property 2: No manual path manipulation in functions
*For any* function code file, the file should contain no sys.path modifications or manual path manipulation
**Validates: Requirements 1.2**

Property 3: Absolute imports from common namespace
*For any* import of shared utilities, the import statement should use absolute imports from the common namespace
**Validates: Requirements 1.3, 1.5**

Property 4: No import fallbacks or path manipulation
*For any* function code, the code should contain no try/except blocks around imports or path manipulation logic
**Validates: Requirements 1.4**

Property 5: Local path resolution matches Lambda structure
*For any* local development setup, the sys.path should mirror Lambda's runtime path structure with layer and function paths
**Validates: Requirements 2.3**

Property 6: Layer packaging structure correctness
*For any* layer package created, the package should contain the python/common/ directory structure expected by Lambda
**Validates: Requirements 2.4**

Property 7: Function packaging excludes common code
*For any* function package created, the package should contain only function-specific code and no common layer modules
**Validates: Requirements 2.5**

Property 8: Test import resolution works automatically
*For any* test execution, common module imports should resolve automatically without additional configuration
**Validates: Requirements 3.1**

Property 9: Test import patterns match function patterns
*For any* test file that imports shared utilities, the import statements should use the same patterns as function code
**Validates: Requirements 3.3, 3.4**

Property 10: New tests require no additional setup
*For any* new test file added, the test should be able to import common modules without additional path configuration
**Validates: Requirements 3.5**

Property 11: Multi-function utilities in common layer
*For any* utility module used by multiple functions, the module should be located in the common layer
**Validates: Requirements 4.1**

Property 12: Single-function utilities stay with functions
*For any* utility module used by only one function, the module should remain in that function's directory
**Validates: Requirements 4.2**

Property 13: Dependency separation
*For any* requirements.txt file, layer dependencies should be separate from function-specific dependencies
**Validates: Requirements 4.3**

Property 14: CloudFormation standard patterns
*For any* CloudFormation template reference to code, the template should use standard CodeUri and LayerVersion patterns
**Validates: Requirements 5.2, 7.3**

Property 15: Deployment artifact structure correctness
*For any* deployment package created, the package structure should match Lambda's runtime expectations
**Validates: Requirements 5.3**

Property 16: Import error prevention
*For any* function deployment simulation, the system should prevent ImportError exceptions due to path configuration issues
**Validates: Requirements 6.1**

Property 17: Shared module accessibility
*For any* shared module update, all functions should be able to import and access the updated module
**Validates: Requirements 6.2**

Property 18: Predictable import resolution
*For any* function startup simulation, import resolution should be consistent and complete within expected time bounds
**Validates: Requirements 6.4**

## Error Handling

### Import Resolution Failures

**Strategy**: Fail fast with clear error messages
- Missing common modules should produce clear "module not found" errors
- Incorrect import patterns should be caught during development/testing
- Path configuration issues should be evident from error messages

**Implementation**:
```python
# Clear error when common module not found
try:
    from common.logger import setup_logger
except ImportError as e:
    raise ImportError(
        f"Cannot import common module: {e}. "
        f"Ensure layer is properly configured and common modules are in layers/common/python/common/"
    )
```

### Function-Specific Module Conflicts

**Strategy**: Prevent naming conflicts between function modules
- Use descriptive module names that indicate function ownership
- Avoid generic names that might conflict across functions
- Document module ownership and purpose clearly

### Testing Import Issues

**Strategy**: Comprehensive import testing in CI/CD
- Test imports in isolated environments
- Verify layer and function packaging separately
- Test import resolution in simulated Lambda environment

## Testing Strategy

### Unit Testing Approach

**Import Resolution Tests**:
- Test that common modules can be imported from functions
- Test that function-specific modules remain accessible
- Test that no sys.path manipulation exists in function code
- Test that import statements follow the required patterns

**Structure Validation Tests**:
- Test directory structure matches specification
- Test that multi-function utilities are in common layer
- Test that single-function utilities stay with functions
- Test packaging creates correct zip structures

**CloudFormation Template Tests**:
- Test that templates use standard CodeUri patterns
- Test that layer references use correct paths
- Test that no hardcoded paths exist in templates

### Property-Based Testing Approach

**Import Pattern Properties**:
- Generate random module names and test import consistency
- Generate random function structures and test import resolution
- Test that import patterns remain consistent across code changes

**Packaging Properties**:
- Generate random file structures and test packaging correctness
- Test that layer packages always contain python/common/ structure
- Test that function packages never contain common layer code

**Path Resolution Properties**:
- Generate random path configurations and test resolution consistency
- Test that local development paths mirror Lambda runtime paths
- Test that import resolution is deterministic and predictable

### Integration Testing

**End-to-End Import Testing**:
- Test complete function deployment with layer
- Test that functions can access all required modules
- Test that import resolution works in actual Lambda environment

**CI/CD Pipeline Testing**:
- Test packaging process creates correct artifacts
- Test that deployment process maintains import compatibility
- Test that layer versioning doesn't break imports

### Testing Framework Selection

**Property-Based Testing Library**: Use `hypothesis` for Python property-based testing
- Minimum 100 iterations per property test
- Generate realistic module names, paths, and structures
- Test import behavior across different configurations

**Unit Testing Framework**: Use `pytest` with the simplified conftest.py setup
- Test individual import behaviors and patterns
- Test structure validation and compliance
- Test error handling and edge cases

## Implementation Notes

### Migration Strategy

1. **Phase 1**: Update conftest.py and test infrastructure
2. **Phase 2**: Clean up common layer and move shared utilities
3. **Phase 3**: Remove sys.path manipulation from function handlers
4. **Phase 4**: Update CloudFormation templates to use standard patterns
5. **Phase 5**: Add comprehensive import testing

### Compatibility Considerations

- No backward compatibility required (complete refactoring approach)
- Focus on core functionality and unit tests first
- Property-based tests can be added after core structure is stable
- Additional utility consolidation can happen after import patterns are fixed

### Performance Considerations

- Import resolution should be fast and predictable
- Layer loading should not significantly impact cold start times
- Common modules should be optimized for quick loading
- Avoid circular imports between common modules