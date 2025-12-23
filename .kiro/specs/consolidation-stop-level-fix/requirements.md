# Requirements Document

## Introduction

This feature fixes the ConsolidationStopLevel functionality in the Multi-Bucket CloudFront Invalidation Service. The current implementation has the depth comparison logic backwards - it prevents consolidation at deep depths when it should prevent consolidation at shallow depths (closer to root). The fix ensures that the stop level correctly corresponds to directory depth levels, where ConsolidationStopLevel=1 prevents consolidation shallower than level 1, ConsolidationStopLevel=2 prevents consolidation shallower than level 2, and so on. The current logic `depth >= stop_level` should be maintained, but the depth calculation needs to be corrected to use the first 'public' directory as the reference point.

## Glossary

- **ConsolidationStopLevel**: Directory depth level where consolidation is prevented for shallower depths
- **Directory_Depth**: The number of directory levels from the first 'public' directory found in the path
- **Path_Consolidation**: The process of replacing multiple individual paths with directory wildcards
- **Root_Path**: The first 'public' directory found in the path, which serves as level 1
- **Processor_Function**: Lambda function that processes invalidation events and applies consolidation

## Requirements

### Requirement 1

**User Story:** As a platform administrator, I want ConsolidationStopLevel=0 to continue working as it currently does, so that existing behavior is preserved for immediate root consolidation.

#### Acceptance Criteria

1. WHEN ConsolidationStopLevel is set to 0, THE system SHALL consolidate all paths to the root wildcard `/*`
2. WHEN ConsolidationStopLevel is 0, THE system SHALL ignore all other consolidation rules and immediately return `/*`
3. WHEN ConsolidationStopLevel is 0, THE system SHALL log that root consolidation is being applied
4. WHEN ConsolidationStopLevel is 0, THE system SHALL maintain backward compatibility with existing deployments

### Requirement 2

**User Story:** As a platform administrator, I want ConsolidationStopLevel=1 to prevent consolidation shallower than level 1, so that consolidation only occurs at level 1 and deeper.

#### Acceptance Criteria

1. WHEN ConsolidationStopLevel is set to 1, THE system SHALL allow consolidation to occur at depth 1 and deeper (e.g., `/prod/public/*`, `/prod/public/m/*`)
2. WHEN ConsolidationStopLevel is 1 and threshold is met, THE system SHALL prevent consolidation at depth 0 (root level shallower than public)
3. WHEN ConsolidationStopLevel is 1 and threshold is met, THE system SHALL consolidate paths like `/prod/public/file1.html`, `/prod/public/file2.html` to `/prod/public/*`
4. WHEN ConsolidationStopLevel is 1 and threshold is met, THE system SHALL consolidate paths like `/prod/public/m/file1.html`, `/prod/public/m/file2.html` to `/prod/public/m/*`
5. WHEN ConsolidationStopLevel is 1, THE system SHALL maintain the current default behavior for backward compatibility

### Requirement 3

**User Story:** As a platform administrator, I want ConsolidationStopLevel values greater than 1 to prevent consolidation shallower than the corresponding directory depth level, so that I can control exactly where consolidation stops.

#### Acceptance Criteria

1. WHEN ConsolidationStopLevel is set to N (where N > 1), THE system SHALL allow consolidation to occur at depth N and deeper
2. WHEN ConsolidationStopLevel is 2, THE system SHALL allow consolidation like `/prod/public/m/file1.html`, `/prod/public/m/file2.html` to `/prod/public/m/*`
3. WHEN ConsolidationStopLevel is 2, THE system SHALL prevent consolidation like `/prod/public/*` (depth 1 < stop level 2)
4. WHEN ConsolidationStopLevel is 3, THE system SHALL allow consolidation like `/prod/public/m/n/file1.html` to `/prod/public/m/n/*`
5. WHEN ConsolidationStopLevel is N, THE system SHALL prevent consolidation at depths less than N

### Requirement 4

**User Story:** As a platform administrator, I want the depth calculation to be consistent and predictable based on the first 'public' directory, so that ConsolidationStopLevel values correspond to actual directory structure levels.

#### Acceptance Criteria

1. WHEN calculating path depth, THE system SHALL count directory levels from the first 'public' directory found in the path
2. WHEN a path is `/prod/public/m/file.html`, THE system SHALL calculate its parent directory `/prod/public/m` as depth 2
3. WHEN a path is `/prod/public/m/n/file.html`, THE system SHALL calculate its parent directory `/prod/public/m/n` as depth 3
4. WHEN a path is `/site1/prod/public/scripts/file.html`, THE system SHALL calculate its parent directory `/site1/prod/public/scripts` as depth 2
5. WHEN the first 'public' directory is found, THE system SHALL treat it as level 1 for depth calculations

### Requirement 5

**User Story:** As a system operator, I want comprehensive logging of ConsolidationStopLevel decisions, so that I can understand and troubleshoot consolidation behavior.

#### Acceptance Criteria

1. WHEN ConsolidationStopLevel prevents consolidation, THE system SHALL log the stop level value and the blocked depth
2. WHEN ConsolidationStopLevel allows consolidation, THE system SHALL log the consolidation decision with depth information
3. WHEN depth calculations are performed, THE system SHALL include depth values in debug logs
4. WHEN ConsolidationStopLevel=0 triggers root consolidation, THE system SHALL log this special case behavior
5. WHEN invalid ConsolidationStopLevel values are encountered, THE system SHALL log warnings and fallback behavior

### Requirement 6

**User Story:** As a developer, I want the ConsolidationStopLevel logic to work correctly with both index file consolidation and directory threshold consolidation, so that all consolidation types respect the stop level.

#### Acceptance Criteria

1. WHEN ConsolidationStopLevel prevents consolidation, THE system SHALL apply the restriction to index/default file consolidation
2. WHEN ConsolidationStopLevel prevents consolidation, THE system SHALL apply the restriction to directory threshold consolidation
3. WHEN ConsolidationStopLevel prevents consolidation, THE system SHALL apply the restriction to sibling directory consolidation
4. WHEN ConsolidationStopLevel allows consolidation at a depth, THE system SHALL permit all consolidation types at that depth
5. WHEN multiple consolidation rules apply, THE system SHALL ensure ConsolidationStopLevel takes precedence over other rules