# Design Document

## Overview

This design addresses the update of the upload-test-files.py script from using an `--environments` parameter to a `--stages` parameter. The change aligns the script's terminology with the deployment workflow while maintaining all existing functionality. The design includes fixing implementation bugs, updating all tests, and ensuring CI/CD pipeline compatibility.

## Architecture

The upload utility maintains its existing modular architecture with the following components:
- **ArgumentParser**: Handles command-line argument parsing and validation
- **EnvironmentManager**: Manages AWS credentials and configuration (renamed methods for stage handling)
- **FileGenerator**: Generates test file content and random naming
- **PathGenerator**: Creates diverse S3 path structures for testing
- **S3Uploader**: Handles S3 upload operations with retry logic
- **Logger**: Provides structured logging and progress feedback

The key architectural change is that stage processing replaces environment processing throughout the system.

## Components and Interfaces

### ArgumentParser Updates
- Replace `--environment` parameter with `--stages` parameter
- Default value changes from 'prod' to 'prod' (maintains same default)
- Accept comma-delimited list of stage names
- Update help text to reflect stage terminology

### EnvironmentManager Updates
- Add `get_target_stages()` method to parse comma-delimited stage list
- Update `determine_base_path()` method to handle stage-to-path mapping
- Maintain existing AWS session management functionality
- Remove environment-specific terminology from method names and documentation

### Configuration Object Updates
- Replace `environment` field with `stages` field
- Update all references throughout the codebase
- Maintain backward compatibility in terms of functionality

### PathGenerator Updates
- Update to work with multiple stages per execution
- Generate paths for each stage's base path
- Maintain existing path diversity and structure requirements

## Data Models

### Configuration Class
```python
@dataclass
class Configuration:
    buckets: List[str]
    stages: List[str]  # Changed from environment: str
    aws_profile: Optional[str]
    verbose: bool
    base_path: str  # Removed - calculated per stage
    source_file_path: str
```

### Stage Processing Flow
```
Input: --stages "stage,prod"
↓
Parse: ["stage", "prod"]
↓
For each stage:
  - Determine base path (/stage/public/ or /prod/public/)
  - Generate 12 upload paths
  - Create upload tasks
↓
Execute all upload tasks
↓
Report results by bucket
```

## Error Handling

### Stage Processing Errors
- Invalid stage names are processed using standard stage-to-path logic
- Empty stage lists default to ["prod"]
- Malformed stage strings are parsed with error recovery

### Backward Compatibility
- No breaking changes to core functionality
- All existing error handling patterns maintained
- CI/CD pipeline compatibility preserved

## Testing Strategy

### Unit Tests Updates
- Update all Configuration object instantiations to use `stages` instead of `environment`
- Update method name references (e.g., `determine_base_path` calls)
- Test stage list parsing and validation
- Test multiple stage processing

### Integration Tests Updates  
- Update CI/CD pipeline tests to use `--stages` parameter
- Test buildspec execution with new parameter
- Verify environment variable compatibility

### Property-Based Tests Updates
- Update all property tests to use stages configuration
- Test stage-based path generation properties
- Verify stage list processing properties
- Maintain existing property validation logic

## Implementation Fixes Required

### Bug Fixes in upload-test-files.py
1. **Line 298**: `stages` parameter not properly handled in Configuration creation
2. **Line 315**: `base_path` variable undefined - should be calculated per stage
3. **Line 325**: `generate_base_path()` method doesn't exist - should be `determine_base_path()`
4. **Line 326**: Loop structure needs to handle multiple stages correctly

### Method Updates Required
1. Update `EnvironmentManager.determine_base_path()` to handle stage parameter
2. Add `EnvironmentManager.get_target_stages()` method
3. Update main() function to handle multiple stages correctly
4. Fix Configuration object creation with proper stage handling

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Stage list parsing consistency
*For any* comma-delimited stage string, the parsed stage list should contain exactly the stage names specified in the input string
**Validates: Requirements 1.1**

### Property 2: Multi-stage upload completeness  
*For any* list of stages and buckets, the system should upload exactly 12 files per bucket per stage
**Validates: Requirements 1.2, 2.1**

### Property 3: Stage-based path generation
*For any* stage name, the generated base path should follow the stage-to-path mapping rules consistently
**Validates: Requirements 1.5, 2.2**

### Property 4: Invalid stage name handling
*For any* stage name input (valid or invalid), the system should process it using consistent stage-based path logic without errors
**Validates: Requirements 1.4**

### Property 5: Error isolation across stages
*For any* execution where some stages encounter errors, the system should continue processing remaining stages successfully
**Validates: Requirements 2.3**

### Property 6: Summary reporting accuracy
*For any* completed execution, the summary report should accurately reflect the actual upload results for all stages and buckets
**Validates: Requirements 2.4**

### Property 7: Verbose logging completeness
*For any* execution in verbose mode, the logs should contain detailed information about each stage being processed
**Validates: Requirements 2.5**

### Property 8: CI/CD multi-stage processing
*For any* CI/CD execution with multiple stages, the system should process all stages correctly and upload files to appropriate paths
**Validates: Requirements 4.3, 4.4**

### Property 9: Stage list handling robustness
*For any* stage list input (including edge cases like empty strings, whitespace, trailing commas), the system should handle it gracefully
**Validates: Requirements 5.3**