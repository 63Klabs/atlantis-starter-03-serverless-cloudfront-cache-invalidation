# Implementation Plan

- [x] 1. Update test infrastructure for simplified imports
  - Update conftest.py to add layer path once for all tests
  - Remove manual path manipulation from existing test files
  - Verify that tests can import common modules automatically
  - _Requirements: 3.1, 3.2, 3.5_

- [x] 1.1 Write property test for test import resolution
  - **Property 8: Test import resolution works automatically**
  - **Validates: Requirements 3.1**

- [x] 1.2 Write property test for test import pattern consistency
  - **Property 9: Test import patterns match function patterns**
  - **Validates: Requirements 3.3, 3.4**

- [x] 2. Clean up and organize common layer modules
  - Ensure logger.py, constants.py, retry.py, window_tracker.py are in layers/common/python/common/
  - Remove any duplicate utilities from function directories
  - Update __init__.py to properly expose common modules
  - _Requirements: 4.1, 4.4_

- [x] 2.1 Write property test for multi-function utility placement
  - **Property 11: Multi-function utilities in common layer**
  - **Validates: Requirements 4.1**

- [x] 2.2 Write unit tests for common layer structure
  - Test that required common modules exist in correct locations
  - Test that common modules can be imported properly
  - _Requirements: 4.1, 4.4_

- [x] 3. Remove sys.path manipulation from ingestor function
  - Remove setup_imports() function and manual path handling from handler.py
  - Update all imports to use clean absolute imports: `from common.logger import setup_logger`
  - Keep function-specific modules (event_parser, event_filter, queue_client, scheduler_client) in ingestor directory
  - _Requirements: 1.2, 1.3, 1.4, 1.5, 4.2, 4.5_

- [x] 3.1 Write property test for no path manipulation
  - **Property 2: No manual path manipulation in functions**
  - **Validates: Requirements 1.2**

- [x] 3.2 Write property test for absolute imports
  - **Property 3: Absolute imports from common namespace**
  - **Validates: Requirements 1.3, 1.5**

- [x] 3.3 Write property test for no import fallbacks
  - **Property 4: No import fallbacks or path manipulation**
  - **Validates: Requirements 1.4**

- [x] 4. Remove sys.path manipulation from processor function
  - Remove manual path handling from handler.py
  - Update all imports to use clean absolute imports: `from common.logger import setup_logger`
  - Keep function-specific modules (distribution_finder, invalidation_client, path_consolidator, path_validator, queue_client, tag_validator) in processor directory
  - _Requirements: 1.2, 1.3, 1.4, 1.5, 4.2, 4.5_

- [x] 4.1 Write property test for single-function utilities placement
  - **Property 12: Single-function utilities stay with functions**
  - **Validates: Requirements 4.2**

- [x] 5. Update CloudFormation templates for standard patterns
  - Ensure template.yml uses standard CodeUri and LayerVersion patterns
  - Remove any hardcoded paths or non-standard references
  - Follow SAM/CloudFormation best practices for layer and function references
  - _Requirements: 5.2, 7.3_

- [x] 5.1 Write property test for CloudFormation standard patterns
  - **Property 14: CloudFormation standard patterns**
  - **Validates: Requirements 5.2, 7.3**

- [x] 6. Implement packaging validation
  - Create scripts or tests to validate layer packaging creates python/common/ structure
  - Create scripts or tests to validate function packaging excludes common layer code
  - Ensure deployment artifacts match Lambda expectations
  - _Requirements: 2.4, 2.5, 5.3_

- [x] 6.1 Write property test for layer packaging structure
  - **Property 6: Layer packaging structure correctness**
  - **Validates: Requirements 2.4**

- [x] 6.2 Write property test for function packaging separation
  - **Property 7: Function packaging excludes common code**
  - **Validates: Requirements 2.5**

- [x] 6.3 Write property test for deployment artifact structure
  - **Property 15: Deployment artifact structure correctness**
  - **Validates: Requirements 5.3**

- [x] 7. Add comprehensive import testing
  - Create tests to verify import consistency across environments
  - Create tests to verify local path resolution matches Lambda structure
  - Create tests to prevent import errors and ensure shared module accessibility
  - _Requirements: 1.1, 2.3, 6.1, 6.2, 6.4_

- [x] 7.1 Write property test for import consistency
  - **Property 1: Import consistency across environments**
  - **Validates: Requirements 1.1**

- [x] 7.2 Write property test for local path resolution
  - **Property 5: Local path resolution matches Lambda structure**
  - **Validates: Requirements 2.3**

- [x] 7.3 Write property test for import error prevention
  - **Property 16: Import error prevention**
  - **Validates: Requirements 6.1**

- [x] 7.4 Write property test for shared module accessibility
  - **Property 17: Shared module accessibility**
  - **Validates: Requirements 6.2**

- [x] 7.5 Write property test for predictable import resolution
  - **Property 18: Predictable import resolution**
  - **Validates: Requirements 6.4**

- [x] 8. Validate dependency separation
  - Ensure requirements.txt files are properly separated between layer and functions
  - Verify layer dependencies are in layers/common/requirements.txt
  - Verify function-specific dependencies are in functions/{name}/requirements.txt
  - _Requirements: 4.3_

- [x] 8.1 Write property test for dependency separation
  - **Property 13: Dependency separation**
  - **Validates: Requirements 4.3**

- [x] 9. Final integration testing and validation
  - Run all existing unit tests to ensure they pass with new import structure
  - Verify that functions can be packaged and deployed successfully
  - Test that import resolution works end-to-end
  - _Requirements: 3.1, 5.1, 6.1, 6.4_

- [x] 9.1 Write property test for new test setup requirements
  - **Property 10: New tests require no additional setup**
  - **Validates: Requirements 3.5**

- [x] 10. Checkpoint - Ensure all tests pass and imports work correctly
  - Ensure all tests pass, ask the user if questions arise.