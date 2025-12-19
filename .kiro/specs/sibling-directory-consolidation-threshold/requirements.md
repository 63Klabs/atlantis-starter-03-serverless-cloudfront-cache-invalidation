# Requirements Document

## Introduction

This feature adds support for configuring the sibling directory consolidation threshold through CloudFormation parameters and per-bucket S3 tags, following the same pattern as the existing DirectoryConsolidationThreshold feature. The sibling directory consolidation threshold controls when multiple sibling directories should be consolidated into a parent directory wildcard pattern during CloudFront invalidation path optimization.

## Glossary

- **Sibling Directory Consolidation Threshold**: The number of sibling directories that triggers consolidation to their parent directory wildcard (e.g., `/dir1/*`, `/dir2/*`, `/dir3/*` becomes `/*/`)
- **CloudFormation Parameter**: A template parameter that allows configuration at stack deployment time
- **S3 Bucket Tag**: A key-value pair attached to an S3 bucket for per-bucket configuration overrides
- **Path Consolidation**: The process of optimizing CloudFront invalidation paths by replacing multiple specific paths with wildcard patterns
- **Environment Variable**: A runtime configuration value passed to Lambda functions from CloudFormation parameters

## Requirements

### Requirement 1

**User Story:** As a DevOps engineer, I want to configure the sibling directory consolidation threshold at the CloudFormation stack level, so that I can set appropriate defaults for all buckets in my deployment.

#### Acceptance Criteria

1. WHEN deploying the CloudFormation stack THEN the system SHALL accept a SiblingDirectoryConsolidationThreshold parameter with a default value of 10
2. WHEN the SiblingDirectoryConsolidationThreshold parameter is provided THEN the system SHALL validate it is between 1 and 1000 inclusive
3. WHEN the SiblingDirectoryConsolidationThreshold parameter is set THEN the system SHALL pass it to the Processor Lambda as the SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD environment variable
4. WHEN the Processor Lambda starts THEN the system SHALL read the SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD environment variable and use it as the default threshold

### Requirement 2

**User Story:** As a bucket owner, I want to override the sibling directory consolidation threshold for my specific bucket using S3 tags, so that I can optimize invalidation behavior based on my bucket's content structure.

#### Acceptance Criteria

1. WHEN a bucket has the invalidator:SiblingDirectoryConsolidationThreshold tag THEN the system SHALL read and validate the tag value
2. WHEN the invalidator:SiblingDirectoryConsolidationThreshold tag contains a valid integer between 1 and 1000 THEN the system SHALL use that value instead of the default threshold
3. WHEN the invalidator:SiblingDirectoryConsolidationThreshold tag contains an invalid value THEN the system SHALL log a warning and use the default threshold
4. WHEN a bucket lacks the invalidator:SiblingDirectoryConsolidationThreshold tag THEN the system SHALL use the default threshold from the environment variable

### Requirement 3

**User Story:** As a system administrator, I want the sibling directory consolidation threshold to follow the same configuration priority as other consolidation settings, so that the system behavior is consistent and predictable.

#### Acceptance Criteria

1. WHEN resolving the sibling directory consolidation threshold THEN the system SHALL use bucket tags as the highest priority
2. WHEN bucket tags are not available or invalid THEN the system SHALL use the CloudFormation parameter value as the fallback
3. WHEN both bucket tags and CloudFormation parameters are unavailable THEN the system SHALL use the hardcoded default of 10
4. WHEN logging configuration resolution THEN the system SHALL indicate the source of each configuration value (tag, parameter, or default)

### Requirement 4

**User Story:** As a DevOps engineer, I want to increase the maximum range for ConsolidationStopLevel to 0-20, so that I can prevent consolidation at deeper directory levels when needed.

#### Acceptance Criteria

1. WHEN validating the ConsolidationStopLevel parameter THEN the system SHALL accept values from 0 to 20 inclusive
2. WHEN validating the invalidator:ConsolidationStopLevel tag THEN the system SHALL accept values from 0 to 20 inclusive
3. WHEN a ConsolidationStopLevel value exceeds 20 THEN the system SHALL reject it and use the default value
4. WHEN a ConsolidationStopLevel value is below 0 THEN the system SHALL reject it and use the default value

### Requirement 5

**User Story:** As a developer, I want the sibling directory consolidation threshold to be configurable through environment variables in the constants module, so that it follows the same pattern as other thresholds and can be easily tested.

#### Acceptance Criteria

1. WHEN the constants module loads THEN the system SHALL read the SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD environment variable
2. WHEN the SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD environment variable is valid THEN the system SHALL use that value
3. WHEN the SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD environment variable is invalid or missing THEN the system SHALL use the hardcoded default of 10
4. WHEN validating the environment variable THEN the system SHALL ensure it is between 1 and 1000 inclusive