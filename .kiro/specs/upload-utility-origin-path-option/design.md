# Design Document: Upload Utility Origin Path Option

## Overview

This design adds a new `--origin_path` command-line option to the upload-test-files.py utility, allowing users to specify custom origin path patterns for testing CloudFront distributions with non-standard origin paths. The enhancement modifies the `determine_base_path()` function to accept and process the origin path pattern, replacing the hard-coded `/{stage}/public/` pattern with a configurable value.

## Architecture

### Current Flow

```
1. Parse command-line arguments (--buckets, --stages, --profile, --verbose)
2. Create Configuration with hard-coded base_path=""
3. For each bucket and stage:
   a. Call determine_base_path(stage) → returns "/{stage}/public/"
   b. Generate upload paths using base_path
   c. Upload files to S3
```

### Enhanced Flow

```
1. Parse command-line arguments (--buckets, --stages, --profile, --verbose, --origin_path)
2. Validate origin_path pattern (must start with '/')
3. Create Configuration with origin_path_pattern
4. For each bucket and stage:
   a. Call determine_base_path(stage, origin_path_pattern)
   b. Replace {stageId} with actual stage value
   c. Ensure path starts and ends with '/'
   d. Generate upload paths using base_path
   e. Upload files to S3
```

## Components and Interfaces

### Modified Component: ArgumentParser

#### Method: `_create_parser()`

**Changes Required**:
- Add new `--origin_path` argument with appropriate help text

**New Code**:
```python
parser.add_argument(
    '--origin_path',
    type=str,
    default='/{stageId}/public',
    help=(
        'Origin path pattern for S3 uploads (default: /{stageId}/public). '
        'Must start with "/". Can include {stageId} placeholder for dynamic substitution. '
        'Examples: /app/{stageId}, /static, /{stageId}/public'
    )
)
```

#### Method: `_validate_args()`

**Changes Required**:
- Add validation for `--origin_path` format

**New Code**:
```python
def _validate_args(self, args: argparse.Namespace) -> None:
    """Validate argument combinations and requirements"""
    # Validate origin_path format
    if not args.origin_path.startswith('/'):
        raise ValueError(
            "Origin path must start with '/'. "
            f"Invalid value: '{args.origin_path}'. "
            "Examples: /app/{{stageId}}, /static, /{{stageId}}/public"
        )
```

### Modified Component: Configuration

#### Dataclass: `Configuration`

**Changes Required**:
- Add new field `origin_path_pattern: str`

**New Code**:
```python
@dataclass
class Configuration:
    """Configuration data for the upload utility"""
    buckets: List[str]
    stages: List[str]
    aws_profile: Optional[str]
    verbose: bool
    base_path: str
    source_file_path: str
    origin_path_pattern: str = '/{stageId}/public'  # New field with default
```

### Modified Component: EnvironmentManager

#### Method: `determine_base_path()`

**Current Signature**:
```python
def determine_base_path(self, stage: str) -> str:
    """
    Determine S3 base path based on stage
    
    Args:
        stage: Target stage name
        
    Returns:
        Base S3 path for uploads
    """
    return f'/{stage}/public/'
```

**New Signature**:
```python
def determine_base_path(self, stage: str, origin_path_pattern: str = '/{stageId}/public') -> str:
    """
    Determine S3 base path based on stage and origin path pattern
    
    Args:
        stage: Target stage name
        origin_path_pattern: Origin path pattern with optional {stageId} placeholder
        
    Returns:
        Base S3 path for uploads (always starts and ends with '/')
        
    Examples:
        >>> determine_base_path('prod', '/{stageId}/public')
        '/prod/public/'
        
        >>> determine_base_path('prod', '/app/{stageId}')
        '/app/prod/'
        
        >>> determine_base_path('prod', '/static')
        '/static/'
        
        >>> determine_base_path('prod', '/{stageId}')
        '/prod/'
    """
    # Replace {stageId} placeholder with actual stage value
    base_path = origin_path_pattern.replace('{stageId}', stage)
    
    # Ensure path starts with '/'
    if not base_path.startswith('/'):
        base_path = '/' + base_path
    
    # Ensure path ends with '/'
    if not base_path.endswith('/'):
        base_path = base_path + '/'
    
    return base_path
```

### Modified Component: main()

**Changes Required**:
- Pass `origin_path_pattern` from args to Configuration
- Pass `origin_path_pattern` to `determine_base_path()` calls

**Modified Code**:
```python
def main():
    """Main script execution"""
    # Parse arguments
    arg_parser = ArgumentParser()
    args = arg_parser.parse_args()
    
    # Setup logging
    logger = setup_console_logging(args.verbose)
    
    try:
        # Setup environment manager
        env_manager = EnvironmentManager()
        
        # Get target buckets
        buckets = env_manager.get_target_buckets(args.buckets)
        
        # Setup AWS session
        session = env_manager.setup_aws_session(args.profile)
                
        # Get target stages
        stages = env_manager.get_target_stages(args.stages)
        
        # Create configuration
        source_file_path = Path(__file__).parent.parent.parent / "test.html"
        config = Configuration(
            buckets=buckets,
            stages=stages,
            aws_profile=args.profile,
            verbose=args.verbose,
            base_path="",  # Will be calculated per stage
            source_file_path=str(source_file_path),
            origin_path_pattern=args.origin_path  # NEW: Pass origin_path from args
        )
        
        # ... rest of initialization ...
        
        # Generate upload tasks with enhanced tracking
        upload_tasks = []
        source_content = file_generator.get_source_content()
        structure_info = None
        
        for bucket in buckets:
            for stage in stages:
                # MODIFIED: Pass origin_path_pattern to determine_base_path
                base_path = env_manager.determine_base_path(stage, config.origin_path_pattern)
                upload_paths, nested_info = path_generator.generate_all_upload_paths_with_info(base_path)
                
                # ... rest of upload task generation ...
```

## Data Models

### Command-Line Arguments

**New Argument**:
```python
{
    'origin_path': str,  # Default: '/{stageId}/public'
    # Examples:
    # - '/{stageId}/public' (default)
    # - '/app/{stageId}'
    # - '/static'
    # - '/{stageId}'
}
```

### Configuration

**Updated Configuration**:
```python
@dataclass
class Configuration:
    buckets: List[str]
    stages: List[str]
    aws_profile: Optional[str]
    verbose: bool
    base_path: str
    source_file_path: str
    origin_path_pattern: str = '/{stageId}/public'  # NEW FIELD
```

## Correctness Properties

### Property 1: Default Behavior Preservation

*For any* invocation without the `--origin_path` option, the base path should be `/{stage}/public/` (current behavior).

**Validates: Requirements 6.1, 6.3**

### Property 2: Stage Placeholder Replacement

*For any* origin path pattern containing `{stageId}` and a given stage value, the base path should have the placeholder replaced with the actual stage.

**Validates: Requirements 1.6, 2.2**

### Property 3: Leading Slash Enforcement

*For any* base path returned by `determine_base_path()`, the path should start with `/`.

**Validates: Requirements 2.3**

### Property 4: Trailing Slash Enforcement

*For any* base path returned by `determine_base_path()`, the path should end with `/`.

**Validates: Requirements 2.4**

### Property 5: Pattern Validation

*For any* `--origin_path` value that does not start with `/`, the utility should display an error and exit before processing any buckets.

**Validates: Requirements 3.1, 3.2, 3.3**

## Error Handling

### Error Scenarios

1. **Invalid Origin Path (Missing Leading Slash)**
   - **Detection**: Check `args.origin_path.startswith('/')`
   - **Action**: Raise `ValueError` with clear message
   - **Message**: "Origin path must start with '/'. Invalid value: '{value}'. Examples: /app/{stageId}, /static, /{stageId}/public"
   - **Exit Code**: 1

2. **Empty Origin Path**
   - **Detection**: Check `args.origin_path` is not empty
   - **Action**: Use default value `/{stageId}/public`
   - **Note**: argparse default handles this case

### Logging Requirements

- Log the origin path pattern being used at startup
- Log the resolved base path for each bucket/stage combination
- Include origin path pattern in verbose logging output

Example log structure:
```python
logger.info(f"Origin path pattern: {config.origin_path_pattern}")
logger.info(f"Resolved base path for {bucket}/{stage}: {base_path}")
```

## Testing Strategy

### Unit Tests

1. **Test: Default origin path pattern**
   - Args: No `--origin_path` provided
   - Expected: `determine_base_path('prod')` returns `/prod/public/`
   - **Validates: Property 1**

2. **Test: Custom origin path with stage placeholder**
   - Args: `--origin_path /app/{stageId}`
   - Expected: `determine_base_path('prod', '/app/{stageId}')` returns `/app/prod/`
   - **Validates: Property 2**

3. **Test: Custom origin path without stage placeholder**
   - Args: `--origin_path /static`
   - Expected: `determine_base_path('prod', '/static')` returns `/static/`
   - **Validates: Property 2**

4. **Test: Origin path with only stage placeholder**
   - Args: `--origin_path /{stageId}`
   - Expected: `determine_base_path('prod', '/{stageId}')` returns `/prod/`
   - **Validates: Property 2**

5. **Test: Leading slash enforcement**
   - Input: Pattern without leading slash
   - Expected: `determine_base_path()` adds leading slash
   - **Validates: Property 3**

6. **Test: Trailing slash enforcement**
   - Input: Pattern without trailing slash
   - Expected: `determine_base_path()` adds trailing slash
   - **Validates: Property 4**

7. **Test: Invalid origin path (missing leading slash)**
   - Args: `--origin_path app/{stageId}`
   - Expected: `ValueError` raised with clear message
   - **Validates: Property 5**

8. **Test: Multiple stages with custom pattern**
   - Args: `--origin_path /app/{stageId}`, stages `prod,staging`
   - Expected: 
     - `determine_base_path('prod', '/app/{stageId}')` returns `/app/prod/`
     - `determine_base_path('staging', '/app/{stageId}')` returns `/app/staging/`
   - **Validates: Property 2**

### Integration Tests

1. **Test: End-to-end with custom origin path**
   - Setup: Mock S3 bucket
   - Args: `--buckets test-bucket --stages prod --origin_path /app/{stageId}`
   - Execute: Run upload utility
   - Verify: Files uploaded to `/app/prod/` prefix

2. **Test: Backward compatibility**
   - Setup: Mock S3 bucket
   - Args: `--buckets test-bucket --stages prod` (no --origin_path)
   - Execute: Run upload utility
   - Verify: Files uploaded to `/prod/public/` prefix (current behavior)

### Documentation Updates

Files to update:
1. **DEPLOYMENT_GUIDE.md** - Add examples with `--origin_path` option
2. **application-infrastructure/build-scripts/post-deploy.sh** - Add comment about optional `--origin_path`
3. **Test files** - Update any tests that import or call the upload utility
4. **Spec documents** - Update references to the upload utility

### Test Configuration

- **Framework**: pytest (Kiro's preferred framework)
- **Mocking**: Use `unittest.mock` for AWS service calls
- **Coverage**: Aim for 100% coverage of modified code paths
- **Fast execution**: All unit tests should complete in < 2 seconds total

## Implementation Notes

### Minimal Changes

The implementation follows these principles:
1. Add new argument with sensible default
2. Update Configuration dataclass with new field
3. Modify `determine_base_path()` to accept and process pattern
4. Update main() to pass pattern through the call chain
5. Add validation in ArgumentParser

### Backward Compatibility

- Default value matches current hard-coded behavior
- No changes required to existing scripts or CI/CD pipelines
- All existing tests continue to pass without modification

### Code Quality

- Follow existing code style and patterns
- Add comprehensive docstrings with examples
- Include type hints for all new/modified functions
- Maintain existing error handling patterns
