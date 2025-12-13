# Design Document

## Overview

This design outlines the restructuring of the AWS Lambda application architecture to separate individual Lambda functions into their own directories and extract common Python code into a Lambda layer. The current structure places all function code in a shared `src/` directory, which results in deployment packages containing unnecessary code and makes it difficult to manage function-specific dependencies.

The new architecture will create dedicated directories for each Lambda function (`ingestor` and `processor`) and move shared functionality to a Lambda layer. This enables more efficient deployments where each function is packaged only with the code it needs, while shared functionality is provided through a reusable Lambda layer.

## Architecture

### Current Structure
```
application-infrastructure/
├── src/
│   ├── common/              # Shared utilities (will become layer)
│   │   ├── constants.py
│   │   ├── logger.py
│   │   └── retry.py
│   ├── ingestor/            # Ingestor function code
│   │   ├── handler.py
│   │   ├── event_parser.py
│   │   ├── event_filter.py
│   │   ├── queue_client.py
│   │   ├── scheduler_client.py
│   │   └── window_tracker.py
│   └── processor/           # Processor function code
│       ├── handler.py
│       ├── distribution_finder.py
│       ├── invalidation_client.py
│       ├── path_consolidator.py
│       ├── path_validator.py
│       ├── queue_client.py
│       └── tag_validator.py
├── tests/
├── template.yml
└── buildspec.yml
```

### Target Structure
```
application-infrastructure/
├── functions/
│   ├── ingestor/            # Ingestor function directory
│   │   ├── handler.py
│   │   ├── event_parser.py
│   │   ├── event_filter.py
│   │   ├── queue_client.py
│   │   ├── scheduler_client.py
│   │   ├── window_tracker.py
│   │   └── requirements.txt # Function-specific dependencies
│   └── processor/           # Processor function directory
│       ├── handler.py
│       ├── distribution_finder.py
│       ├── invalidation_client.py
│       ├── path_consolidator.py
│       ├── path_validator.py
│       ├── queue_client.py
│       ├── tag_validator.py
│       └── requirements.txt # Function-specific dependencies
├── layers/
│   └── common/              # Lambda layer for shared code
│       ├── python/
│       │   └── common/      # Layer Python path structure
│       │       ├── constants.py
│       │       ├── logger.py
│       │       └── retry.py
│       └── requirements.txt # Layer dependencies
├── tests/                   # Updated test structure
├── template.yml             # Updated with layer resources
└── buildspec.yml           # Updated build process
```

## Components and Interfaces

### Lambda Function Directories

1. **Ingestor Function** (`functions/ingestor/`)
   - Contains all ingestor-specific code and logic
   - Includes handler and supporting modules
   - Has its own requirements.txt for function-specific dependencies
   - Imports common functionality from the Lambda layer

2. **Processor Function** (`functions/processor/`)
   - Contains all processor-specific code and logic
   - Includes handler and supporting modules
   - Has its own requirements.txt for function-specific dependencies
   - Imports common functionality from the Lambda layer

### Lambda Layer Structure

3. **Common Layer** (`layers/common/`)
   - Contains shared utilities and constants
   - Follows Lambda layer Python path structure (`python/common/`)
   - Has its own requirements.txt for shared dependencies
   - Provides common functionality to both functions

### Build System Integration

4. **CloudFormation Template Updates**
   - Defines Lambda layer resource
   - Associates layer with both Lambda functions
   - Updates CodeUri paths for functions
   - Maintains existing IAM permissions and configurations

5. **Build Process Updates**
   - Packages each function directory separately
   - Creates layer ZIP with proper Python path structure
   - Handles dependency installation for functions and layer
   - Maintains test execution capabilities

## Data Models

### Directory Structure Mapping

```python
# Source to destination mapping for restructuring
restructure_mapping = {
    # Function code moves
    'src/ingestor/': 'functions/ingestor/',
    'src/processor/': 'functions/processor/',
    
    # Common code moves to layer
    'src/common/': 'layers/common/python/common/',
    
    # Test updates (import path changes)
    'tests/': 'tests/',  # Location stays same, imports change
}

# Import path transformations
import_updates = {
    # Function imports from layer
    'from common.': 'from common.',  # Layer provides common at root
    'sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))': '',  # Remove local path manipulation
    
    # Test imports to new function locations
    'from ingestor.': 'from functions.ingestor.',
    'from processor.': 'from functions.processor.',
}
```

### Lambda Layer Configuration

```python
# Layer structure for AWS Lambda
layer_config = {
    'name': 'CommonLayer',
    'path': 'layers/common/',
    'python_path': 'python/',  # Required by Lambda layer convention
    'common_modules': [
        'common/constants.py',
        'common/logger.py', 
        'common/retry.py'
    ],
    'requirements_file': 'layers/common/requirements.txt'
}
```

### CloudFormation Resource Updates

```yaml
# New resources to add to template.yml
Resources:
  CommonLayer:
    Type: AWS::Lambda::LayerVersion
    Properties:
      LayerName: !Sub '${Prefix}-${ProjectId}-${StageId}-CommonLayer'
      Content:
        S3Bucket: !Ref S3ArtifactsBucket
        S3Key: !Sub '${S3KeyPrefix}layers/common.zip'
      CompatibleRuntimes:
        - python3.14
      Description: "Common utilities and constants for Lambda functions"

  # Updated function resources
  IngestorFunction:
    Properties:
      CodeUri: functions/ingestor/  # Updated path
      Layers:
        - !Ref CommonLayer  # Add layer reference
      
  ProcessorFunction:
    Properties:
      CodeUri: functions/processor/  # Updated path
      Layers:
        - !Ref CommonLayer  # Add layer reference
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

**Property Reflection:**
After reviewing the prework analysis, I identified several redundant properties:
- Properties 1.2 and 4.1 both test deployment package contents - combined into Property 1
- Properties 2.4 and 4.3 both test CloudFormation layer associations - combined into Property 2  
- Properties 3.3 and 3.4 both test import resolution - combined into Property 3
- Properties 1.1, 1.5, 2.1, 4.4, 5.1, 5.2 are all structural checks - combined into Property 4
- Properties 3.1, 3.2, 4.5 are all about execution success - combined into Property 5

**Property 1: Function deployment isolation**
*For any* Lambda function deployment package, the package should contain only code specific to that function and not include code from other functions
**Validates: Requirements 1.2, 4.1**

**Property 2: Layer dependency resolution**
*For any* function that uses common code, all imports from the common layer should resolve correctly at runtime
**Validates: Requirements 2.3, 3.3, 3.4**

**Property 3: Functional behavior preservation**
*For any* Lambda function, the behavior and logic should remain identical before and after the restructuring
**Validates: Requirements 1.3, 3.5**

**Property 4: Architectural boundary enforcement**
*For any* function directory, it should not contain imports or dependencies from other function directories (only layer imports allowed)
**Validates: Requirements 1.4**

**Property 5: Build and test execution consistency**
*For any* build or test execution, the process should complete successfully with the new directory structure
**Validates: Requirements 3.1, 3.2, 4.5, 5.3**

## Error Handling

### File Operation Errors
- **Missing source files**: Verify all expected function and common files exist before restructuring
- **Permission errors**: Ensure write permissions for creating new directories and moving files
- **Path conflicts**: Handle cases where target directories already exist

### Import Resolution Errors
- **Broken imports**: Validate that all import statements resolve correctly after restructuring
- **Layer import failures**: Ensure layer imports work in both local development and deployed environments
- **Circular dependencies**: Detect and prevent circular imports between functions and layer

### Build System Errors
- **Package creation failures**: Handle errors during function and layer ZIP creation
- **Dependency installation errors**: Manage cases where dependencies cannot be installed
- **CloudFormation template validation**: Ensure template changes are syntactically correct

### Test Integration Errors
- **Test discovery failures**: Ensure test runners can find all tests after restructuring
- **Import path resolution in tests**: Handle test imports that reference moved code
- **CI/CD pipeline failures**: Validate that buildspec changes work in the CI/CD environment

## Testing Strategy

### Dual Testing Approach

This design requires both unit testing and property-based testing approaches:

**Unit Testing:**
- Verify specific directory operations and file moves
- Test individual import path transformations
- Validate CloudFormation template syntax and structure
- Test specific build script operations

**Property-Based Testing:**
- Use **Hypothesis** as the property-based testing library for Python
- Configure each property-based test to run a minimum of **100 iterations**
- Tag each property-based test with comments referencing the design document properties

**Property-Based Test Requirements:**
- Each correctness property must be implemented by a single property-based test
- Tests must be tagged using the format: '**Feature: lambda-function-separation, Property {number}: {property_text}**'
- Property tests verify universal behaviors across all valid inputs
- Unit tests handle specific examples and edge cases

**Test Coverage:**
- Directory structure validation and file organization
- Import statement resolution and path correctness
- CloudFormation template resource definitions
- Build process execution and package creation
- Layer structure and Python path compliance
- Dependency management and installation
- CI/CD integration and test execution

The testing strategy ensures comprehensive validation of the restructuring process while maintaining all existing functionality and adding the new Lambda layer architecture benefits.