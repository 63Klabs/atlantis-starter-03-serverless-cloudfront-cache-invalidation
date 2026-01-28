# Implementation Plan: Upload Utility Origin Path Option

## Overview

This plan adds a new `--origin_path` command-line option to the upload-test-files.py utility, allowing users to specify custom origin path patterns for testing CloudFront distributions with non-standard origin paths. The implementation modifies the ArgumentParser, Configuration, EnvironmentManager, and main() function to support the new option while maintaining full backward compatibility.

## Tasks

- [x] 1. Update ArgumentParser class
  - [x] 1.1 Add --origin_path argument to _create_parser()
    - Add argument with default value `/{stageId}/public`
    - Include comprehensive help text with examples
    - Set type to `str`
    - _Requirements: 1.1, 1.3, 5.6_
  
  - [x] 1.2 Add validation to _validate_args()
    - Check that origin_path starts with `/`
    - Raise ValueError with clear message if validation fails
    - Include examples in error message
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 2. Update Configuration dataclass
  - Add new field `origin_path_pattern: str` with default value `/{stageId}/public`
  - Ensure field is properly typed
  - _Requirements: 4.1, 4.2_

- [x] 3. Update EnvironmentManager.determine_base_path()
  - [x] 3.1 Update function signature
    - Add parameter `origin_path_pattern: str = '/{stageId}/public'`
    - Update docstring with examples
    - _Requirements: 2.1, 4.3, 4.4_
  
  - [x] 3.2 Implement pattern processing logic
    - Replace `{stageId}` placeholder with actual stage value
    - Ensure returned path starts with `/`
    - Ensure returned path ends with `/`
    - Remove hard-coded `f'/{stage}/public/'` return statement
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

- [x] 4. Update main() function
  - [x] 4.1 Pass origin_path to Configuration
    - Update Configuration instantiation to include `origin_path_pattern=args.origin_path`
    - _Requirements: 4.1_
  
  - [x] 4.2 Pass origin_path_pattern to determine_base_path()
    - Update call from `determine_base_path(stage)` to `determine_base_path(stage, config.origin_path_pattern)`
    - _Requirements: 4.3, 4.4_
  
  - [x] 4.3 Add logging for origin path pattern
    - Log the origin path pattern at startup
    - Log resolved base path for each bucket/stage in verbose mode
    - _Requirements: Logging requirements from design_

- [x] 5. Write unit tests for determine_base_path()
  - [x] 5.1 Test default origin path pattern
    - Call `determine_base_path('prod')` with default pattern
    - Verify returns `/prod/public/`
    - _Requirements: 6.1, 6.3_
  
  - [x] 5.2 Test custom origin path with stage placeholder
    - Call `determine_base_path('prod', '/app/{stageId}')`
    - Verify returns `/app/prod/`
    - _Requirements: 1.6, 2.2_
  
  - [x] 5.3 Test custom origin path without stage placeholder
    - Call `determine_base_path('prod', '/static')`
    - Verify returns `/static/`
    - _Requirements: 2.2_
  
  - [x] 5.4 Test origin path with only stage placeholder
    - Call `determine_base_path('prod', '/{stageId}')`
    - Verify returns `/prod/`
    - _Requirements: 2.2_
  
  - [x] 5.5 Test leading slash enforcement
    - Call `determine_base_path('prod', 'app/{stageId}')`
    - Verify returns `/app/prod/` (leading slash added)
    - _Requirements: 2.3_
  
  - [x] 5.6 Test trailing slash enforcement
    - Call `determine_base_path('prod', '/app/{stageId}')`
    - Verify returns `/app/prod/` (trailing slash added)
    - _Requirements: 2.4_
  
  - [x] 5.7 Test multiple stages with custom pattern
    - Call `determine_base_path('prod', '/app/{stageId}')` → `/app/prod/`
    - Call `determine_base_path('staging', '/app/{stageId}')` → `/app/staging/`
    - Verify both return correct paths
    - _Requirements: 2.2_

- [x] 6. Write unit tests for ArgumentParser validation
  - [x] 6.1 Test valid origin path patterns
    - Test `/{stageId}/public` (default)
    - Test `/app/{stageId}`
    - Test `/static`
    - Verify no errors raised
    - _Requirements: 3.4_
  
  - [x] 6.2 Test invalid origin path (missing leading slash)
    - Test `app/{stageId}`
    - Verify ValueError raised with clear message
    - Verify error message includes examples
    - _Requirements: 3.1, 3.2_

- [x] 7. Write integration test for end-to-end flow
  - [x] 7.1 Test with custom origin path
    - Mock S3 bucket and client
    - Run utility with `--origin_path /app/{stageId} --stages prod`
    - Verify files uploaded to `/app/prod/` prefix
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4_
  
  - [x] 7.2 Test backward compatibility
    - Mock S3 bucket and client
    - Run utility without `--origin_path` option
    - Verify files uploaded to `/prod/public/` prefix (current behavior)
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 8. Update documentation
  - [x] 8.1 Update DEPLOYMENT_GUIDE.md
    - Add examples using `--origin_path` option
    - Show different pattern formats
    - _Requirements: 5.1_
  
  - [x] 8.2 Update post-deploy.sh comments
    - Add comment explaining optional `--origin_path` parameter
    - _Requirements: 5.1_
  
  - [x] 8.3 Review and update integration tests
    - Check test_origin_path_resolution.py
    - Check test_enhanced_upload_utility_e2e.py
    - Check test_backward_compatibility_enhanced.py
    - Update if they reference the upload utility
    - _Requirements: 5.2_

- [x] 9. Run all tests and verify
  - Run all unit tests for upload utility
  - Run all integration tests
  - Verify no regressions in existing functionality
  - Verify all new tests pass
  - _Requirements: 6.2_

## Notes

- The default value `/{stageId}/public` maintains current behavior
- The implementation ensures minimal code changes
- All existing scripts and CI/CD pipelines continue to work without modification
- Tests use pytest framework per repository standards
- Unit tests should complete in < 2 seconds
- Integration tests should complete in < 10 seconds
