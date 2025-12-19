# Design Document

## Overview

This design implements support for configuring the sibling directory consolidation threshold through CloudFormation parameters and per-bucket S3 tags. The feature follows the established pattern used by DirectoryConsolidationThreshold and ConsolidationStopLevel, ensuring consistency in configuration management and priority resolution.

The sibling directory consolidation threshold controls when multiple sibling directories should be consolidated into a parent directory wildcard pattern during CloudFront invalidation path optimization. For example, if 10 or more sibling directories need invalidation (like `/dir1/*`, `/dir2/*`, ..., `/dir10/*`), they can be consolidated to `/*` for more efficient invalidation.

## Architecture

The feature integrates into the existing multi-bucket CloudFront invalidation service architecture:

1. **CloudFormation Template**: Adds the new `SiblingDirectoryConsolidationThreshold` parameter and updates the `ConsolidationStopLevel` range
2. **Lambda Environment Variables**: Passes the parameter value to the Processor Lambda as `SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD`
3. **Constants Module**: Reads the environment variable with validation and fallback to hardcoded default
4. **Tag Validator**: Extends bucket configuration reading to include the new `invalidator:SiblingDirectoryConsolidationThreshold` tag
5. **Path Consolidator**: Uses the resolved threshold value during sibling directory consolidation logic

## Components and Interfaces

### CloudFormation Template Changes

**New Parameter:**
```yaml
SiblingDirectoryConsolidationThreshold:
  Type: Number
  Description: "Default threshold for sibling directory consolidation (number of sibling directories that triggers consolidation to parent wildcard)"
  Default: 10
  MinValue: 1
  MaxValue: 1000
```

**Updated Parameter:**
```yaml
ConsolidationStopLevel:
  Type: Number
  Description: "Directory depth from root where consolidation stops (0 = consolidate to root, 1+ = prevent consolidation at that depth or shallower)"
  Default: 1
  MinValue: 0
  MaxValue: 20  # Changed from 1000 to 20
```

**Environment Variable Addition:**
```yaml
Environment:
  Variables:
    SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD: !Ref SiblingDirectoryConsolidationThreshold
```

### Constants Module Changes

**New Environment Variable Reading:**
```python
SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD = _get_validated_int_env('SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD', 10, 1, 1000)
```

**Updated Validation Range:**
```python
CONSOLIDATION_STOP_LEVEL = _get_validated_int_env('CONSOLIDATION_STOP_LEVEL', 1, 0, 20)
```

### Tag Validator Changes

**Extended Configuration Function:**
The `get_bucket_consolidation_config` function will be updated to include sibling directory threshold reading:

```python
def get_bucket_consolidation_config(bucket_name: str) -> Dict[str, any]:
    # ... existing code ...
    
    # Check for SiblingDirectoryConsolidationThreshold tag
    sibling_threshold_tag = tags.get('invalidator:SiblingDirectoryConsolidationThreshold')
    if sibling_threshold_tag is not None:
        validated_sibling_threshold = validate_consolidation_tag_value(sibling_threshold_tag, 1, 1000)
        if validated_sibling_threshold is not None:
            config['sibling_directory_threshold'] = validated_sibling_threshold
            config['sibling_directory_threshold_source'] = 'tag'
        else:
            # Log warning and use default
            config['sibling_directory_threshold'] = SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD
            config['sibling_directory_threshold_source'] = 'default'
    else:
        config['sibling_directory_threshold'] = SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD
        config['sibling_directory_threshold_source'] = 'default'
    
    return config
```

**Updated Validation Range:**
The `validate_consolidation_tag_value` function calls for ConsolidationStopLevel will use the new range (0, 20).

## Data Models

### Configuration Dictionary Extension

The bucket configuration dictionary returned by `get_bucket_consolidation_config` will be extended:

```python
{
    'directory_threshold': int,           # Existing
    'stop_level': int,                   # Existing  
    'sibling_directory_threshold': int,   # New
    'directory_threshold_source': str,    # Existing
    'stop_level_source': str,            # Existing
    'sibling_directory_threshold_source': str  # New
}
```

### Environment Variables

New environment variable added to Lambda functions:
- `SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD`: Integer value from CloudFormation parameter

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Property 1: CloudFormation parameter validation
*For any* SiblingDirectoryConsolidationThreshold parameter value, the CloudFormation template should accept values between 1 and 1000 inclusive and reject values outside this range
**Validates: Requirements 1.2**

Property 2: Parameter to environment variable mapping
*For any* valid SiblingDirectoryConsolidationThreshold parameter value, the Processor Lambda should receive that exact value as the SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD environment variable
**Validates: Requirements 1.3**

Property 3: Environment variable reading
*For any* valid SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD environment variable value, the constants module should use that value as the default threshold
**Validates: Requirements 1.4, 5.2**

Property 4: Bucket tag reading
*For any* bucket with the invalidator:SiblingDirectoryConsolidationThreshold tag, the system should read and attempt to validate the tag value
**Validates: Requirements 2.1**

Property 5: Valid tag value usage
*For any* bucket with a valid invalidator:SiblingDirectoryConsolidationThreshold tag value (1-1000), the system should use that value instead of the default threshold
**Validates: Requirements 2.2**

Property 6: Invalid tag value handling
*For any* bucket with an invalid invalidator:SiblingDirectoryConsolidationThreshold tag value, the system should log a warning and use the default threshold
**Validates: Requirements 2.3**

Property 7: Missing tag fallback
*For any* bucket without the invalidator:SiblingDirectoryConsolidationThreshold tag, the system should use the default threshold from the environment variable
**Validates: Requirements 2.4**

Property 8: Configuration priority resolution
*For any* bucket with both tag and parameter configurations, the tag value should take precedence over the parameter value
**Validates: Requirements 3.1**

Property 9: Parameter fallback behavior
*For any* bucket with missing or invalid tags, the system should use the CloudFormation parameter value as the fallback
**Validates: Requirements 3.2**

Property 10: Configuration source logging
*For any* configuration resolution, the system should log the source of each configuration value (tag, parameter, or default)
**Validates: Requirements 3.4**

Property 11: ConsolidationStopLevel parameter validation
*For any* ConsolidationStopLevel parameter value, the CloudFormation template should accept values between 0 and 20 inclusive and reject values outside this range
**Validates: Requirements 4.1**

Property 12: ConsolidationStopLevel tag validation
*For any* invalidator:ConsolidationStopLevel tag value, the system should accept values between 0 and 20 inclusive and reject values outside this range
**Validates: Requirements 4.2**

Property 13: ConsolidationStopLevel upper bound validation
*For any* ConsolidationStopLevel value exceeding 20, the system should reject it and use the default value
**Validates: Requirements 4.3**

Property 14: ConsolidationStopLevel lower bound validation
*For any* ConsolidationStopLevel value below 0, the system should reject it and use the default value
**Validates: Requirements 4.4**

Property 15: Environment variable validation
*For any* SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD environment variable value, the system should validate it is between 1 and 1000 inclusive
**Validates: Requirements 5.4**

Property 16: Environment variable fallback
*For any* invalid or missing SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD environment variable, the system should use the hardcoded default of 10
**Validates: Requirements 5.3**

## Error Handling

The feature implements comprehensive error handling following the established patterns:

1. **Invalid CloudFormation Parameters**: CloudFormation validates parameter ranges at deployment time and rejects invalid values
2. **Invalid Environment Variables**: The constants module validates environment variables and falls back to hardcoded defaults
3. **Invalid Bucket Tags**: The tag validator logs warnings for invalid tag values and uses default configuration
4. **Missing Bucket Tags**: The system gracefully falls back to parameter or default values
5. **S3 API Errors**: Existing error handling in `get_bucket_tags` covers API failures

## Testing Strategy

### Unit Testing
- Test CloudFormation parameter validation with boundary values
- Test environment variable reading in constants module with various inputs
- Test bucket tag reading and validation with valid/invalid values
- Test configuration priority resolution with different combinations
- Test updated ConsolidationStopLevel range validation

### Property-Based Testing
The testing strategy uses Hypothesis for property-based testing with the following approach:

**Test Framework**: Hypothesis (Python property-based testing library)
**Minimum Iterations**: 100 iterations per property test
**Property Test Tagging**: Each property-based test will be tagged with a comment referencing the design document property using the format: `**Feature: sibling-directory-consolidation-threshold, Property {number}: {property_text}**`

**Key Property Tests**:
1. CloudFormation parameter validation across valid and invalid ranges
2. Environment variable reading and validation with various inputs
3. Bucket tag reading and priority resolution with different configurations
4. Configuration fallback behavior with missing or invalid values
5. ConsolidationStopLevel range validation with updated bounds

**Test Generators**:
- Valid threshold values (1-1000)
- Invalid threshold values (outside range, non-numeric)
- Valid stop level values (0-20) 
- Invalid stop level values (outside range, non-numeric)
- Bucket configurations with various tag combinations
- Environment variable configurations

### Integration Testing
- Test end-to-end configuration resolution from CloudFormation to Lambda execution
- Test bucket-specific configuration overrides in realistic scenarios
- Test backward compatibility with existing deployments
- Test configuration logging and error reporting

The dual testing approach ensures both specific scenarios are covered (unit tests) and general correctness properties hold across all inputs (property tests).