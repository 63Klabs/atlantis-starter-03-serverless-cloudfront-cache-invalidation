# Requirements Document

## Introduction

The origin-path-pattern feature extends the CloudFront cache invalidation system to support configurable S3 bucket path structures beyond the hardcoded `/{stageId}/public` pattern. This advanced feature enables the invalidator application to work with S3 buckets that use different directory structures while maintaining backward compatibility with existing deployments.

An **Origin Path** is a specific subfolder or directory within an S3 bucket that CloudFront uses as the content source. An **Origin Path Pattern** is a literal string (no wildcards) that may contain a `{stageId}` placeholder to represent the path structure in S3.

## Glossary

- **Invalidator_Application**: The CloudFormation stack containing Lambda functions that process S3 events and trigger CloudFront cache invalidations
- **Ingestor_Function**: Lambda function triggered by S3 events that performs initial filtering and queues events for processing
- **Processor_Function**: Lambda function that reads bucket tags, performs advanced filtering, consolidates paths, and triggers CloudFront invalidations
- **Origin_Path**: A specific subfolder or directory within an S3 bucket that CloudFront uses as the content source (e.g., `/prod/public`)
- **Origin_Path_Pattern**: A literal string representing the path structure in S3, optionally containing `{stageId}` placeholder (e.g., `/{stageId}/public`)
- **Event_Object_Path**: The S3 object key received in Lambda event notifications
- **Bucket_Origin_Path_Pattern**: The resolved origin path pattern for a specific bucket, determined from bucket tags or defaults
- **Stage_Identifier**: A value representing the deployment stage (e.g., prod, beta, stage, dev, test)
- **PUBLIC_PATH_SEGMENT**: A constant representing the public directory name (default: "public")
- **Consolidation**: The process of grouping invalidation paths to minimize CloudFront API calls

## Requirements

### Requirement 1: Configuration Parameters

**User Story:** As a DevOps engineer, I want to configure the origin path pattern through CloudFormation parameters, so that I can deploy the invalidator to work with different S3 bucket structures.

#### Acceptance Criteria

1. THE CloudFormation_Template SHALL define a parameter named OriginPathPattern with default value `/{stageId}/public`
2. WHEN OriginPathPattern is empty, THE Invalidator_Application SHALL use the default value from constants.py
3. THE OriginPathPattern_Parameter SHALL validate that non-empty values start with `/`
4. THE OriginPathPattern_Parameter SHALL validate that non-empty values do not end with `/`
5. THE OriginPathPattern_Parameter SHALL validate that curly braces only wrap the literal text `stageId`
6. THE OriginPathPattern_Parameter SHALL allow valid path characters in the pattern
7. THE CloudFormation_Template SHALL include OriginPathPattern in the Application Parameters metadata group

### Requirement 2: Lambda Environment Variables

**User Story:** As a developer, I want Lambda functions to receive the origin path pattern through environment variables, so that the pattern can be configured at deployment time.

#### Acceptance Criteria

1. THE CloudFormation_Template SHALL pass OriginPathPattern to Ingestor_Function as environment variable ORIGIN_PATH_PATTERN
2. THE CloudFormation_Template SHALL pass OriginPathPattern to Processor_Function as environment variable ORIGIN_PATH_PATTERN
3. WHEN ORIGIN_PATH_PATTERN environment variable is set, THE Lambda_Functions SHALL use it instead of the constants.py default
4. WHEN ORIGIN_PATH_PATTERN environment variable is empty, THE Lambda_Functions SHALL use the constants.py default value

### Requirement 3: Constants and Dynamic Depth Calculation

**User Story:** As a developer, I want the system to calculate path depth dynamically, so that it works with any origin path pattern without hardcoded depth values.

#### Acceptance Criteria

1. THE constants.py SHALL define ORIGIN_PATH_PATTERN with default value `/{stageId}/public`
2. THE constants.py SHALL define PUBLIC_PATH_SEGMENT with value `public`
3. THE constants.py SHALL define PRODUCTION_STAGE_IDENTIFIERS as `['prod', 'beta', 'stage', 'staging']`
4. THE constants.py SHALL define NON_PRODUCTION_STAGE_IDENTIFIERS as `['dev', 'test']`
5. THE Lambda_Layer SHALL provide a utility function that calculates path depth from any given path
6. WHEN given a path, THE depth_calculation_function SHALL return the count of path segments
7. THE constants.py SHALL remove the hardcoded ORIGIN_PATH_DEPTH constant

### Requirement 4: Bucket Tag Support

**User Story:** As a DevOps engineer, I want to override the origin path pattern per bucket using tags, so that I can handle buckets with different structures in the same AWS account.

#### Acceptance Criteria

1. THE Processor_Function SHALL check for bucket tag named `invalidator:OriginPathPattern`
2. WHEN `invalidator:OriginPathPattern` tag exists, THE Processor_Function SHALL use it as the Bucket_Origin_Path_Pattern
3. WHEN `invalidator:OriginPathPattern` tag does not exist, THE Processor_Function SHALL fall back to ORIGIN_PATH_PATTERN from constants.py
4. THE `invalidator:OriginPathPattern` tag SHALL follow the same validation rules as the CloudFormation parameter

### Requirement 5: Ingestor Function Pattern Matching

**User Story:** As a system, I want the Ingestor function to filter S3 events based on the origin path pattern, so that only relevant events are queued for processing.

#### Acceptance Criteria

1. WHEN Event_Object_Path matches ORIGIN_PATH_PATTERN and contains `{stageId}`, THE Ingestor_Function SHALL queue the event if the Stage_Identifier is production
2. WHEN Event_Object_Path matches ORIGIN_PATH_PATTERN and does not contain `{stageId}`, THE Ingestor_Function SHALL queue the event
3. WHEN Event_Object_Path does not match ORIGIN_PATH_PATTERN but contains PUBLIC_PATH_SEGMENT, THE Ingestor_Function SHALL queue the event if no NON_PRODUCTION_STAGE_IDENTIFIERS appear before PUBLIC_PATH_SEGMENT
4. WHEN Event_Object_Path does not match ORIGIN_PATH_PATTERN and does not contain PUBLIC_PATH_SEGMENT, THE Ingestor_Function SHALL filter out the event
5. WHEN Event_Object_Path contains NON_PRODUCTION_STAGE_IDENTIFIERS before PUBLIC_PATH_SEGMENT, THE Ingestor_Function SHALL filter out the event

### Requirement 6: Processor Function Pattern Resolution

**User Story:** As a system, I want the Processor function to determine the correct origin path pattern for each bucket, so that events are processed according to bucket-specific configurations.

#### Acceptance Criteria

1. WHEN processing events for a bucket, THE Processor_Function SHALL determine Bucket_Origin_Path_Pattern using the first event object path
2. THE Processor_Function SHALL prioritize `invalidator:OriginPathPattern` bucket tag over other methods
3. WHEN bucket tag is absent and Event_Object_Path matches ORIGIN_PATH_PATTERN, THE Processor_Function SHALL use ORIGIN_PATH_PATTERN as Bucket_Origin_Path_Pattern
4. WHEN bucket tag is absent and Event_Object_Path does not match ORIGIN_PATH_PATTERN but contains PUBLIC_PATH_SEGMENT, THE Processor_Function SHALL derive Bucket_Origin_Path_Pattern from the path up to and including PUBLIC_PATH_SEGMENT
5. WHEN deriving pattern from PUBLIC_PATH_SEGMENT placement, THE Processor_Function SHALL replace any PRODUCTION_STAGE_IDENTIFIERS or NON_PRODUCTION_STAGE_IDENTIFIERS with `{stageId}` placeholder
6. WHEN `invalidator:OriginPathPattern` tag exists and Event_Object_Path does not match it, THE Processor_Function SHALL filter out the event

### Requirement 7: Processor Function Stage Filtering

**User Story:** As a system, I want the Processor function to filter non-production stages, so that only production content triggers cache invalidations.

#### Acceptance Criteria

1. WHEN Bucket_Origin_Path_Pattern contains `{stageId}`, THE Processor_Function SHALL filter out events with NON_PRODUCTION_STAGE_IDENTIFIERS
2. WHEN Bucket_Origin_Path_Pattern contains `{stageId}`, THE Processor_Function SHALL allow events with PRODUCTION_STAGE_IDENTIFIERS
3. WHEN Bucket_Origin_Path_Pattern does not contain `{stageId}`, THE Processor_Function SHALL treat all events as production
4. THE Processor_Function SHALL use the same stage filtering logic as Ingestor_Function

### Requirement 8: Processor Function Path Filtering

**User Story:** As a system, I want the Processor function to filter event paths that don't match the bucket's origin path pattern, so that only relevant paths are consolidated.

#### Acceptance Criteria

1. WHEN processing multiple events for a bucket, THE Processor_Function SHALL filter out Event_Object_Paths that do not match Bucket_Origin_Path_Pattern
2. WHEN all Event_Object_Paths are filtered out, THE Processor_Function SHALL not trigger consolidation
3. THE Processor_Function SHALL pass the filtered list and Bucket_Origin_Path_Pattern to consolidation

### Requirement 9: Dynamic Consolidation

**User Story:** As a system, I want the consolidation logic to calculate depth dynamically from the bucket origin path pattern, so that it works with any path structure.

#### Acceptance Criteria

1. THE Consolidation_Function SHALL calculate depth from Bucket_Origin_Path_Pattern instead of using ORIGIN_PATH_DEPTH constant
2. WHEN calculating depth, THE Consolidation_Function SHALL split the pattern by `/` and count segments
3. THE Consolidation_Function SHALL use the calculated depth to determine the root path for consolidation
4. WHEN a bucket contains multiple Stage_Identifiers, THE Consolidation_Function SHALL create separate invalidation requests for each stage
5. THE Consolidation_Function SHALL maintain existing consolidation logic for grouping paths

### Requirement 10: Backward Compatibility

**User Story:** As an existing user, I want the system to work exactly as before when using default settings, so that my deployments are not disrupted.

#### Acceptance Criteria

1. WHEN OriginPathPattern is not specified, THE Invalidator_Application SHALL use `/{stageId}/public` as the default
2. WHEN no bucket tags are present, THE Invalidator_Application SHALL behave identically to the previous version
3. THE Invalidator_Application SHALL pass all existing regression tests after implementation
4. THE Invalidator_Application SHALL maintain the same CloudFront invalidation behavior for default configurations

### Requirement 11: Validation and Error Handling

**User Story:** As a developer, I want clear validation errors for invalid origin path patterns, so that I can quickly identify and fix configuration issues.

#### Acceptance Criteria

1. WHEN OriginPathPattern does not start with `/`, THE CloudFormation_Template SHALL reject the parameter with a descriptive error
2. WHEN OriginPathPattern ends with `/`, THE CloudFormation_Template SHALL reject the parameter with a descriptive error
3. WHEN OriginPathPattern contains curly braces not wrapping `stageId`, THE CloudFormation_Template SHALL reject the parameter with a descriptive error
4. WHEN OriginPathPattern contains invalid path characters, THE CloudFormation_Template SHALL reject the parameter with a descriptive error
5. THE validation_errors SHALL include constraint descriptions explaining the valid format

### Requirement 12: Documentation

**User Story:** As a user, I want clear documentation on the advanced origin path pattern feature, so that I can configure it correctly for my use case.

#### Acceptance Criteria

1. THE Documentation SHALL include an Advanced Configuration section for origin path pattern
2. THE Documentation SHALL explain that `/{stageId}/public` is the default and preferred configuration
3. THE Documentation SHALL provide examples of valid origin path patterns
4. THE Documentation SHALL explain the behavior when OriginPathPattern is set to `/`
5. THE Documentation SHALL recommend using multiple invalidator stacks for complex environments
6. THE Documentation SHALL explain the relationship between application-wide pattern and bucket tags
7. THE Documentation SHALL include troubleshooting guidance for common configuration issues
