# Requirements Document

## Introduction

This feature fixes a critical bug in the ConsolidationStopLevel functionality where the sibling directory consolidation threshold cannot be overridden by bucket tags. The `consolidate_paths` function is missing the `sibling_threshold` parameter, causing it to always use the hardcoded global constant (10) instead of the bucket-specific configuration value. This prevents proper sibling directory consolidation when custom thresholds are configured via bucket tags.

## Glossary

- **SiblingDirectoryConsolidationThreshold**: The number of sibling directory wildcards that triggers consolidation to their parent directory wildcard
- **Bucket_Tag_Override**: The ability to override default consolidation parameters using bucket-specific tags
- **Consolidate_Paths_Function**: The main entry point function for path consolidation that should accept all configurable threshold parameters
- **Sibling_Threshold_Parameter**: The missing parameter that should allow bucket-specific sibling threshold configuration

## Requirements

### Requirement 1

**User Story:** As a platform administrator, I want the `consolidate_paths` function to accept a `sibling_threshold` parameter, so that bucket-specific sibling directory consolidation thresholds can be properly applied.

#### Acceptance Criteria

1. WHEN the `consolidate_paths` function is called, THE system SHALL accept a `sibling_threshold` parameter
2. WHEN a `sibling_threshold` parameter is provided, THE system SHALL use that value instead of the global constant
3. WHEN no `sibling_threshold` parameter is provided, THE system SHALL fall back to the global constant for backward compatibility
4. WHEN the processor handler calls `consolidate_paths`, THE system SHALL pass the bucket-specific `sibling_directory_threshold` from the configuration
5. WHEN bucket tags configure `SiblingDirectoryConsolidationThreshold=2`, THE system SHALL use that value in the consolidation logic

### Requirement 2

**User Story:** As a platform administrator, I want sibling directory consolidation to work correctly with bucket-specific thresholds, so that paths like `/prod/public/m/*`, `/prod/public/k/*`, `/prod/public/w/*`, `/prod/public/x/*` consolidate to `/prod/public/*` when the configured threshold is exceeded.

#### Acceptance Criteria

1. WHEN bucket tag `SiblingDirectoryConsolidationThreshold=2` is configured and 4 sibling directories exist, THE system SHALL consolidate them since 4 > 2
2. WHEN the sibling threshold is exceeded and ConsolidationStopLevel allows, THE system SHALL consolidate sibling directories to their parent wildcard
3. WHEN the user's specific scenario runs with `SiblingDirectoryConsolidationThreshold=2`, THE system SHALL produce `/prod/public/*` instead of separate directory wildcards
4. WHEN the consolidation logic evaluates sibling directories, THE system SHALL use the bucket-specific threshold value
5. WHEN sibling consolidation occurs, THE system SHALL respect both the threshold and stop level constraints

### Requirement 3

**User Story:** As a system developer, I want the `consolidate_sibling_directories` function to accept a configurable threshold parameter, so that it can use bucket-specific values instead of hardcoded constants.

#### Acceptance Criteria

1. WHEN the `consolidate_sibling_directories` function is called, THE system SHALL accept a `sibling_threshold` parameter
2. WHEN a `sibling_threshold` parameter is provided, THE system SHALL use that value for threshold comparison
3. WHEN no `sibling_threshold` parameter is provided, THE system SHALL use the global constant as default
4. WHEN evaluating sibling consolidation, THE system SHALL compare sibling count against the provided threshold
5. WHEN the threshold logic is updated, THE system SHALL maintain backward compatibility with existing callers

### Requirement 4

**User Story:** As a system developer, I want comprehensive testing to ensure the sibling threshold parameter works correctly across all consolidation scenarios, so that bucket-specific configuration is properly applied.

#### Acceptance Criteria

1. WHEN testing the updated `consolidate_paths` function, THE system SHALL verify that custom sibling thresholds are used correctly
2. WHEN testing sibling directory consolidation, THE system SHALL verify that bucket-specific thresholds override global constants
3. WHEN testing the user's specific scenario, THE system SHALL verify that the expected output `/prod/public/*` is produced
4. WHEN testing backward compatibility, THE system SHALL verify that existing behavior is preserved when no sibling threshold is specified
5. WHEN testing edge cases, THE system SHALL verify that boundary conditions work correctly with custom thresholds