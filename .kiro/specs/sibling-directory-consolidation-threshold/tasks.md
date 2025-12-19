# Implementation Plan

- [x] 1. Update CloudFormation template with new parameter and environment variable
  - Add SiblingDirectoryConsolidationThreshold parameter with default value of 10 and range 1-1000
  - Update ConsolidationStopLevel parameter MaxValue from 1000 to 20
  - Add SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD environment variable to Processor Lambda
  - Add parameter to Application Parameters group in metadata
  - _Requirements: 1.1, 1.2, 1.3, 4.1_

- [x] 1.1 Write unit test for CloudFormation parameter validation
  - Test SiblingDirectoryConsolidationThreshold parameter accepts values 1-1000
  - Test ConsolidationStopLevel parameter accepts values 0-20
  - Test parameter defaults are correct
  - _Requirements: 1.1, 1.2, 4.1_

- [x] 2. Update constants module to read SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD environment variable
  - Change SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD from hardcoded value to use _get_validated_int_env
  - Update CONSOLIDATION_STOP_LEVEL validation range from (0, 1000) to (0, 20)
  - Ensure default value of 10 for sibling threshold
  - Ensure validation range of 1-1000 for sibling threshold
  - _Requirements: 1.4, 4.1, 5.1, 5.2, 5.3, 5.4_

- [x] 2.1 Write property test for environment variable reading
  - **Property 3: Environment variable reading**
  - **Validates: Requirements 1.4, 5.2**
  - _Requirements: 1.4, 5.2_

- [x] 2.2 Write property test for environment variable validation
  - **Property 15: Environment variable validation**
  - **Validates: Requirements 5.4**
  - _Requirements: 5.4_

- [x] 2.3 Write property test for environment variable fallback
  - **Property 16: Environment variable fallback**
  - **Validates: Requirements 5.3**
  - _Requirements: 5.3_

- [x] 2.4 Write property test for ConsolidationStopLevel range validation
  - **Property 11: ConsolidationStopLevel parameter validation**
  - **Property 13: ConsolidationStopLevel upper bound validation**
  - **Property 14: ConsolidationStopLevel lower bound validation**
  - **Validates: Requirements 4.1, 4.3, 4.4**
  - _Requirements: 4.1, 4.3, 4.4_

- [x] 3. Update tag_validator.py to support sibling directory threshold tag
  - Add reading of invalidator:SiblingDirectoryConsolidationThreshold tag in get_bucket_consolidation_config
  - Add validation of sibling threshold tag value (1-1000 range)
  - Add sibling_directory_threshold to returned config dictionary
  - Add sibling_directory_threshold_source to returned config dictionary
  - Update ConsolidationStopLevel tag validation range from (0, 1000) to (0, 20)
  - Add logging for sibling threshold configuration resolution
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.4, 4.2_

- [x] 3.1 Write property test for bucket tag reading
  - **Property 4: Bucket tag reading**
  - **Validates: Requirements 2.1**
  - _Requirements: 2.1_

- [x] 3.2 Write property test for valid tag value usage
  - **Property 5: Valid tag value usage**
  - **Validates: Requirements 2.2**
  - _Requirements: 2.2_

- [x] 3.3 Write property test for invalid tag value handling
  - **Property 6: Invalid tag value handling**
  - **Validates: Requirements 2.3**
  - _Requirements: 2.3_

- [x] 3.4 Write property test for missing tag fallback
  - **Property 7: Missing tag fallback**
  - **Validates: Requirements 2.4**
  - _Requirements: 2.4_

- [x] 3.5 Write property test for configuration priority resolution
  - **Property 8: Configuration priority resolution**
  - **Validates: Requirements 3.1**
  - _Requirements: 3.1_

- [x] 3.6 Write property test for parameter fallback behavior
  - **Property 9: Parameter fallback behavior**
  - **Validates: Requirements 3.2**
  - _Requirements: 3.2_

- [x] 3.7 Write property test for configuration source logging
  - **Property 10: Configuration source logging**
  - **Validates: Requirements 3.4**
  - _Requirements: 3.4_

- [x] 3.8 Write property test for ConsolidationStopLevel tag validation
  - **Property 12: ConsolidationStopLevel tag validation**
  - **Validates: Requirements 4.2**
  - _Requirements: 4.2_

- [x] 4. Update documentation files
  - Update README.md with new SiblingDirectoryConsolidationThreshold parameter and tag
  - Update CONFIGURATION_TROUBLESHOOTING.md with new configuration option
  - Update DEPLOYMENT_GUIDE.md with examples using the new tag
  - Update ConsolidationStopLevel range documentation from 0-1000 to 0-20
  - _Requirements: 1.1, 2.1, 4.1_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.