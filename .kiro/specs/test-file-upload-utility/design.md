# Design Document

## Overview

The Test File Upload Utility is a Python script designed to upload test HTML files to S3 buckets with diverse naming patterns and directory structures. This utility supports both local development and CI/CD environments, creating test data that validates CloudFront invalidation consolidation behaviors.

## Architecture

The utility follows a modular architecture with clear separation of concerns:

```
TestFileUploader
├── ArgumentParser - Command line argument handling
├── EnvironmentManager - Environment variable and AWS profile management
├── FileGenerator - Test file content and naming generation
├── PathGenerator - S3 path and directory structure generation
├── S3Uploader - AWS S3 upload operations with retry logic
└── Logger - Structured logging and progress reporting
```

## Components and Interfaces

### ArgumentParser
- **Purpose**: Parse and validate command line arguments
- **Interface**: `parse_args() -> argparse.Namespace`
- **Responsibilities**:
  - Define CLI arguments (--buckets, --environment, --profile, --verbose)
  - Validate argument combinations
  - Provide help documentation

### EnvironmentManager
- **Purpose**: Manage environment configuration and AWS credentials
- **Interface**: 
  - `get_target_buckets(buckets_arg: str) -> List[str]`
  - `setup_aws_session(profile: str) -> boto3.Session`
  - `determine_base_path(environment: str) -> str`
- **Responsibilities**:
  - Resolve bucket list from arguments or environment variables
  - Configure AWS authentication
  - Determine base S3 path based on environment

### FileGenerator
- **Purpose**: Generate test file content and random naming
- **Interface**:
  - `generate_random_filename() -> str`
  - `get_source_content() -> str`
- **Responsibilities**:
  - Read source test.html file
  - Generate 6-character alphanumeric strings for filenames
  - Create test-*.html filename patterns

### PathGenerator
- **Purpose**: Create diverse S3 path structures for testing
- **Interface**: `generate_upload_paths(base_path: str, count: int) -> List[Tuple[str, str]]`
- **Responsibilities**:
  - Generate 12 unique S3 paths per bucket
  - Create directory structures at depths 1-4
  - Mix random filenames with index.html/default.html
  - Ensure patterns that trigger sibling consolidation

### S3Uploader
- **Purpose**: Handle S3 upload operations with error handling
- **Interface**:
  - `upload_file(bucket: str, key: str, content: str) -> bool`
  - `upload_with_retry(bucket: str, key: str, content: str, max_retries: int) -> bool`
- **Responsibilities**:
  - Execute S3 put_object operations
  - Implement exponential backoff retry logic
  - Handle AWS credential and network errors

### Logger
- **Purpose**: Provide structured logging and progress feedback
- **Interface**:
  - `log_upload_success(bucket: str, key: str)`
  - `log_upload_failure(bucket: str, key: str, error: str)`
  - `log_summary(results: Dict[str, int])`
- **Responsibilities**:
  - Log individual upload operations
  - Provide verbose debugging information
  - Generate summary reports

## Data Models

### UploadTask
```python
@dataclass
class UploadTask:
    bucket: str
    key: str
    content: str
    filename: str  # Original filename for logging
```

### UploadResult
```python
@dataclass
class UploadResult:
    bucket: str
    successful_uploads: int
    failed_uploads: int
    upload_paths: List[str]
```

### Configuration
```python
@dataclass
class Configuration:
    buckets: List[str]
    environment: str
    aws_profile: Optional[str]
    verbose: bool
    base_path: str
    source_file_path: str
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Property 1: Bucket list parsing consistency
*For any* comma-delimited bucket string, the utility should upload files to exactly the buckets specified in the list
**Validates: Requirements 1.1**

Property 2: Environment-based configuration
*For any* valid environment parameter, the utility should configure AWS operations and base paths consistently for that environment
**Validates: Requirements 1.2, 3.2**

Property 3: File count consistency
*For any* target bucket, the utility should create exactly 12 test files regardless of bucket name or configuration
**Validates: Requirements 3.1**

Property 4: Filename pattern compliance
*For any* generated filename, it should follow the "test-XXXXXX.html" pattern where XXXXXX is exactly 6 alphanumeric characters
**Validates: Requirements 3.3**

Property 5: Directory depth distribution
*For any* set of 12 generated paths, they should include files at directory depths 1, 2, 3, and 4 levels under the base path
**Validates: Requirements 3.4**

Property 6: Filename variety requirement
*For any* set of 12 generated files, some should be named "index.html" and some should be named "default.html"
**Validates: Requirements 3.5**

Property 7: Retry behavior consistency
*For any* S3 upload failure, the utility should retry up to 3 times with exponential backoff before giving up
**Validates: Requirements 4.1**

Property 8: Bucket error isolation
*For any* list of buckets where some don't exist, the utility should continue processing remaining buckets after logging errors for missing ones
**Validates: Requirements 4.2**

Property 9: Upload logging completeness
*For any* successful file upload, the utility should log the complete S3 path of the uploaded file
**Validates: Requirements 5.1**

Property 10: Summary reporting accuracy
*For any* successful execution, the utility should display a summary showing the count of uploaded files per bucket
**Validates: Requirements 5.2**

## Error Handling

The utility implements comprehensive error handling across multiple failure scenarios:

### AWS Authentication Errors
- Invalid credentials result in clear error messages and non-zero exit codes
- Missing profiles are handled gracefully with fallback to default credentials
- Network connectivity issues provide retry suggestions

### S3 Operation Errors
- Bucket access errors are logged but don't stop processing of other buckets
- Upload failures trigger exponential backoff retry (3 attempts maximum)
- Permission errors provide actionable guidance for resolution

### File System Errors
- Missing source file (test.html) results in immediate exit with error message
- File read errors are handled with specific error reporting

### Configuration Errors
- Missing bucket configuration (no --buckets and no environment variable) provides clear guidance
- Invalid environment parameters result in descriptive error messages

## Testing Strategy

The testing approach combines unit tests for individual components and property-based tests for system-wide behaviors:

### Unit Testing
- Mock AWS S3 operations to test upload logic without actual AWS calls
- Test argument parsing with various input combinations
- Verify path generation algorithms with known inputs
- Test error handling with simulated failure conditions

### Property-Based Testing
- Use Hypothesis library for Python property-based testing
- Generate random bucket lists and verify consistent file upload counts
- Test filename generation across many random seeds
- Verify directory depth distribution across multiple executions
- Test retry behavior with simulated intermittent failures

### Integration Testing
- Test with real S3 buckets in development environment
- Verify end-to-end functionality with various AWS profiles
- Test CI/CD integration with environment variables
- Validate actual file uploads and S3 path structures

The testing framework will use pytest as the primary test runner with Hypothesis for property-based testing, following the existing project testing patterns.
