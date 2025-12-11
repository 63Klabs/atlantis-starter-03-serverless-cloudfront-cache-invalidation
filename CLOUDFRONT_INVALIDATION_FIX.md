# CloudFront Invalidation Path Validation Fix

## Problem

The CloudFront invalidation service was failing with the error:
```
InvalidArgument - Your request contains one or more invalid invalidation paths
```

This error occurs when the paths sent to CloudFront's `CreateInvalidation` API don't meet AWS's path validation requirements.

## Root Cause Analysis

CloudFront has strict requirements for invalidation paths:

1. **Must start with `/`** - All paths must begin with a forward slash
2. **No double slashes** - Paths cannot contain `//` (except after protocol)
3. **Limited character set** - Only alphanumeric, hyphens, underscores, dots, slashes, and asterisks are allowed
4. **No spaces or special characters** - Characters like `@`, `#`, `%`, spaces, etc. are not allowed
5. **Cannot be empty** - Empty strings are not valid paths
6. **Length limits** - Paths have a maximum length (around 8000 characters)

The original code had multiple sources of invalid paths:

### 1. Path Construction Issues
- Paths with double slashes from improper concatenation
- Paths containing spaces or special characters from S3 object names
- Empty paths from edge cases in path processing
- Paths not starting with `/` from fallback logic

### 2. Path Consolidator Issues
The path consolidator was creating invalid paths in several scenarios:

- **Double slashes in wildcards**: When `get_parent_directory()` returned `/dir/` and constructed `f"{parent}/*"`, it created `/dir//*`
- **Unvalidated input processing**: The consolidator processed invalid input paths without cleaning them first
- **Edge cases in parent directory calculation**: Paths with double slashes weren't properly normalized

**Example problematic consolidation:**
```
Input: ["/path//with//double", "/dir/index.html"]
Output: ["/path//with//double", "/dir//*"]  # Both invalid!
```

## Solution

### 1. Created Path Validation Module

Added `application-infrastructure/src/processor/path_validator.py` with:

- **`validate_cloudfront_path()`** - Validates paths against CloudFront requirements
- **`sanitize_path()`** - Attempts to fix common path issues automatically
- **`validate_and_sanitize_paths()`** - Batch processing with deduplication

### 2. Fixed Path Consolidator

Updated `application-infrastructure/src/processor/path_consolidator.py` to:

- **Clean input paths** before processing (remove double slashes, ensure leading slash)
- **Fix `get_parent_directory()`** to handle double slashes and trailing slashes properly
- **Validate input paths** and skip invalid ones with proper logging
- **Prevent double slash creation** in wildcard path construction

### 3. Updated Invalidation Client

Modified `application-infrastructure/src/processor/invalidation_client.py` to:

- Validate and sanitize all paths before sending to CloudFront
- Log validation issues for debugging
- Reject invalidation requests with no valid paths
- Provide detailed error information

### 3. Enhanced Debugging

Added comprehensive logging to:

- Track path construction in the processor handler
- Log paths before and after consolidation
- Show validation results and sanitization actions
- Provide detailed CloudFront API request/response information

## Key Features

### Path Sanitization

The sanitizer automatically fixes common issues:

```python
# Examples of automatic fixes:
"no-leading-slash.html" → "/no-leading-slash.html"
"/path//double//slash" → "/path/double/slash"  
"/path with spaces" → "/pathwithspaces"
"/path/with@symbols" → "/path/withsymbols"
```

### Validation Rules

```python
# Valid paths:
"/", "/*", "/file.html", "/dir/*", "/path/file.css"

# Invalid paths (rejected):
"", "no-slash", "//double", "/path with space", "/path@symbol"
```

### Batch Processing

- Processes multiple paths efficiently
- Removes duplicates automatically
- Provides detailed error reporting
- Maintains path order where possible

## Testing

Created comprehensive unit tests in `application-infrastructure/src/tests/unit/test_path_validator.py`:

- 19 test cases covering all validation scenarios
- Edge case handling (empty paths, very long paths, etc.)
- Integration tests with common S3 patterns
- Wildcard path validation

All existing tests continue to pass, ensuring no regression.

## Deployment

The fix is backward compatible and requires no configuration changes:

1. **Automatic activation** - Path validation runs automatically on all invalidation requests
2. **Graceful degradation** - Invalid paths are logged but don't crash the system
3. **Enhanced logging** - Better visibility into path processing for debugging

## Monitoring

After deployment, monitor for:

1. **Reduced InvalidArgument errors** - Should see fewer CloudFront API failures
2. **Path validation warnings** - Check logs for paths that needed sanitization
3. **Successful invalidations** - Verify invalidation requests are completing successfully

## Example Log Output

```json
{
  "timestamp": "2025-12-11T23:07:16.783511Z",
  "level": "INFO", 
  "message": "Successfully created invalidation 12345 for distribution E27WAZX7393SM0",
  "distribution_id": "E27WAZX7393SM0",
  "path_count": 2,
  "paths": ["/valid/path1.html", "/valid/path2.css"]
}
```

## Files Modified

1. **New files:**
   - `application-infrastructure/src/processor/path_validator.py`
   - `application-infrastructure/src/tests/unit/test_path_validator.py`

2. **Modified files:**
   - `application-infrastructure/src/processor/path_consolidator.py`
   - `application-infrastructure/src/processor/invalidation_client.py`
   - `application-infrastructure/src/processor/handler.py`

## Benefits

- **Eliminates InvalidArgument errors** from malformed paths
- **Automatic path correction** for common issues
- **Better debugging** with detailed logging
- **Robust error handling** prevents system crashes
- **Comprehensive testing** ensures reliability
- **Zero configuration** required for deployment