# Requirements Document

## Introduction

This feature enhances the existing Multi-Bucket CloudFront Invalidation Service by adding dynamic, per-bucket configuration capabilities for path consolidation behavior. Currently, the system uses global constants for directory consolidation thresholds and operates with fixed consolidation rules. This enhancement allows each S3 bucket to override these settings through bucket tags and introduces a new consolidation stop level mechanism to provide fine-grained control over consolidation behavior.

## Glossary

- **Bucket_Tag**: AWS S3 bucket tag used to configure invalidation behavior
- **Directory_Consolidation_Threshold**: Number of files in a directory that triggers consolidation to directory wildcard
- **Consolidation_Stop_Level**: Directory depth from root where consolidation is prevented
- **Processor_Function**: Lambda function that processes invalidation events and applies consolidation
- **CloudFormation_Parameter**: Template parameter that sets default configuration values
- **Root_Directory**: The base directory path (e.g., `/prod/public`) from which depth is measured

## Requirements

### Requirement 1

**User Story:** As a platform administrator, I want to configure directory consolidation thresholds per S3 bucket, so that different applications can have customized invalidation behavior based on their specific needs.

#### Acceptance Criteria

1. WHEN the Processor_Function reads bucket tags, THE system SHALL check for the `invalidator:DirectoryConsolidationThreshold` tag
2. WHEN the `invalidator:DirectoryConsolidationThreshold` tag exists with a value between 1 and 1000, THE system SHALL use that value instead of the global DIRECTORY_CONSOLIDATION_THRESHOLD
3. WHEN the `invalidator:DirectoryConsolidationThreshold` tag does not exist, THE system SHALL use the default DIRECTORY_CONSOLIDATION_THRESHOLD from common.constants
4. WHEN the `invalidator:DirectoryConsolidationThreshold` tag has an invalid value, THE system SHALL log a warning and use the default DIRECTORY_CONSOLIDATION_THRESHOLD
5. WHEN consolidation logic executes, THE system SHALL apply the bucket-specific threshold for that bucket's paths

### Requirement 2

**User Story:** As a platform administrator, I want to control where directory consolidation stops relative to the root directory, so that I can prevent over-consolidation that might invalidate too much content.

#### Acceptance Criteria

1. WHEN the Processor_Function reads bucket tags, THE system SHALL check for the `invalidator:ConsolidationStopLevel` tag
2. WHEN the `invalidator:ConsolidationStopLevel` tag exists with a value between 0 and 1000, THE system SHALL use that value as the consolidation stop level
3. WHEN the `invalidator:ConsolidationStopLevel` tag does not exist, THE system SHALL use the default CONSOLIDATION_STOP_LEVEL constant set to 1
4. WHEN the consolidation stop level is 0, THE system SHALL automatically consolidate all paths to the root wildcard `/*`
5. WHEN the consolidation stop level is greater than 1, THE system SHALL prevent any consolidation (file and sibling) from occurring at that depth or shallower from the root

### Requirement 3

**User Story:** As a platform administrator, I want to set system-wide default values for consolidation parameters through CloudFormation, so that I can manage configuration centrally while allowing per-bucket overrides.

#### Acceptance Criteria

1. WHEN the CloudFormation template is deployed, THE system SHALL accept a DirectoryConsolidationThreshold parameter that sets the DIRECTORY_CONSOLIDATION_THRESHOLD constant
2. WHEN the CloudFormation template is deployed, THE system SHALL accept a ConsolidationStopLevel parameter that sets the CONSOLIDATION_STOP_LEVEL constant
3. WHEN the CloudFormation template is deployed, THE system SHALL accept an AggregationWindowSeconds parameter that sets the AGGREGATION_WINDOW_SECONDS constant
4. WHEN these parameters are not provided, THE system SHALL use the existing default values
5. WHEN the Lambda functions start, THE system SHALL read these values from environment variables set by the CloudFormation parameters

### Requirement 4

**User Story:** As a developer, I want the consolidation logic to respect the consolidation stop level, so that consolidation behavior is predictable and controllable at different directory depths.

#### Acceptance Criteria

1. WHEN the consolidation stop level is 1 (default), THE system SHALL continue consolidation as it currently does
2. WHEN the consolidation stop level is 2, THE system SHALL prevent consolidation of paths like `/dir1/a/*`, `/dir1/b/*`, `/dir1/test.html` to `/dir1/*`
3. WHEN the consolidation stop level is 3, THE system SHALL prevent consolidation of paths like `/dir1/a/z/*`, `/dir1/a/y/*`, `/dir1/a/z/index.html` to `/dir1/a/*`
4. WHEN a file would normally be shortened due to index.* or default.* rules, THE system SHALL not shorten it if the result would violate the consolidation stop level
5. WHEN sibling directory consolidation would occur at or above the stop level, THE system SHALL prevent that consolidation

### Requirement 5

**User Story:** As a system operator, I want comprehensive logging of consolidation configuration decisions, so that I can troubleshoot and audit consolidation behavior.

#### Acceptance Criteria

1. WHEN bucket tags are read for consolidation configuration, THE system SHALL log the discovered tag values in JSON format
2. WHEN default values are used due to missing tags, THE system SHALL log which defaults are being applied
3. WHEN invalid tag values are encountered, THE system SHALL log warnings with the invalid values and fallback behavior
4. WHEN consolidation stop level prevents consolidation, THE system SHALL log the prevention decision with the affected paths
5. WHEN bucket-specific thresholds are applied, THE system SHALL log the threshold value being used for each bucket