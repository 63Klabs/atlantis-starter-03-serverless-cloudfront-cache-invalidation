# Requirements Document

## Introduction

This feature fixes the ConsolidationStopLevel functionality in the Multi-Bucket CloudFront Invalidation Service. The current implementation has incorrect behavior for ConsolidationStopLevel values greater than 0. The fix ensures that the stop level correctly corresponds to directory depth levels, where level 1 allows consolidation at `/level1/*`, level 2 allows consolidation at `/level1/level2/*`, and so on.

## Glossary

- **ConsolidationStopLevel**: Directory depth level where consolidation is allowed to occur
- **Directory_Depth**: The number of directory levels from the root path
- **Path_Consolidation**: The process of replacing multiple individual paths with directory wildcards
- **Root_Path**: The base directory path from which depth is measured (typically `/`)
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

**User Story:** As a platform administrator, I want ConsolidationStopLevel=1 to allow consolidation at the first directory level, so that paths like `/test.html`, `/test2.html`, `/level1/*` can be consolidated appropriately.

#### Acceptance Criteria

1. WHEN ConsolidationStopLevel is set to 1, THE system SHALL allow consolidation to occur at depth 1 (e.g., `/level1/*`)
2. WHEN ConsolidationStopLevel is 1 and threshold is met, THE system SHALL consolidate paths like `/test.html`, `/test2.html`, `/other.html` to `/*`
3. WHEN ConsolidationStopLevel is 1 and threshold is met, THE system SHALL consolidate paths like `/level1/file1.html`, `/level1/file2.html` to `/level1/*`
4. WHEN ConsolidationStopLevel is 1, THE system SHALL prevent consolidation at depth 0 (root level) only when it would bypass normal threshold logic
5. WHEN ConsolidationStopLevel is 1, THE system SHALL maintain the current default behavior for backward compatibility

### Requirement 3

**User Story:** As a platform administrator, I want ConsolidationStopLevel values greater than 1 to allow consolidation at the corresponding directory depth level, so that I can control exactly where consolidation occurs.

#### Acceptance Criteria

1. WHEN ConsolidationStopLevel is set to N (where N > 1), THE system SHALL allow consolidation to occur at depth N and deeper
2. WHEN ConsolidationStopLevel is 2, THE system SHALL allow consolidation like `/level1/level2/file1.html`, `/level1/level2/file2.html` to `/level1/level2/*`
3. WHEN ConsolidationStopLevel is 2, THE system SHALL allow consolidation like `/level1/level2/*`, `/level1/level3/*` to `/level1/*`
4. WHEN ConsolidationStopLevel is 3, THE system SHALL allow consolidation like `/level1/level2/level3/file1.html` to `/level1/level2/level3/*`
5. WHEN ConsolidationStopLevel is N, THE system SHALL prevent consolidation at depths less than N

### Requirement 4

**User Story:** As a platform administrator, I want the depth calculation to be consistent and predictable, so that ConsolidationStopLevel values correspond to actual directory structure levels.

#### Acceptance Criteria

1. WHEN calculating path depth, THE system SHALL count directory levels from the root path
2. WHEN a path is `/level1/file.html`, THE system SHALL calculate its parent directory `/level1` as depth 1
3. WHEN a path is `/level1/level2/file.html`, THE system SHALL calculate its parent directory `/level1/level2` as depth 2
4. WHEN a path is `/level1/level2/level3/file.html`, THE system SHALL calculate its parent directory `/level1/level2/level3` as depth 3
5. WHEN the root path is `/`, THE system SHALL use absolute depth counting from the filesystem root

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