# Design Document

## Overview

The Dynamic Bucket Consolidation Configuration feature enhances the existing Multi-Bucket CloudFront Invalidation Service by adding per-bucket configuration capabilities for path consolidation behavior. This feature allows platform administrators to customize consolidation thresholds and introduce consolidation stop levels on a per-bucket basis through S3 bucket tags, while providing system-wide defaults through CloudFormation parameters.

The enhancement integrates seamlessly with the existing two-Lambda architecture (Ingestor and Processor), leveraging the existing bucket tag reading infrastructure in the Processor Lambda. The feature introduces two new bucket tags (`invalidator:DirectoryConsolidationThreshold` and `invalidator:ConsolidationStopLevel`) and three new CloudFormation parameters to control consolidation behavior dynamically.

Key design principles:
- **Backward Compatible**: Existing behavior is preserved when new tags are not present
- **Per-Bucket Customization**: Each bucket can override global consolidation settings
- **Centralized Defaults**: CloudFormation parameters provide system-wide default values
- **Comprehensive Logging**: All configuration decisions are logged for troubleshooting
- **Robust Error Handling**: Invalid tag values fall back to safe defaults with appropriate logging

## Architecture

### Enhanced Component Interaction

The existing architecture remains unchanged, with enhancements focused on the Processor Lambda's path consolidation logic:

```
┌─────────────────────┐
│  CloudFormation     │
│  Parameters         │
│  - DirectoryConsol  │
│  - ConsolidationStop│
│  - AggregationWindow│
└──────┬──────────────┘
       │ Environment Variables
       ▼
┌─────────────────────────────────┐
│  Processor Lambda               │
│  ┌─────────────────────────────┐│
│  │  Enhanced Tag Reader        ││
│  │  - Read existing tags       ││
│  │  - Read new config tags     ││
│  │  - Apply defaults           ││
│  │  - Validate ranges          ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │  Enhanced Path Consolidator ││
│  │  - Use bucket-specific      ││
│  │    thresholds               ││
│  │  - Apply stop level rules   ││
│  │  - Respect depth limits     ││
│  └─────────────────────────────┘│
└─────────────────────────────────┘
```

### Configuration Flow

1. **CloudFormation Deployment**: Parameters set environment variables in Lambda functions
2. **Bucket Tag Reading**: Processor Lambda reads both existing and new configuration tags
3. **Configuration Resolution**: System determines effective configuration (tags override defaults)
4. **Path Consolidation**: Enhanced consolidation algorithm applies bucket-specific settings
5. **Logging**: All configuration decisions and consolidation actions are logged

## Components and Interfaces

### 1. Enhanced Constants Module

**Purpose**: Provide dynamic configuration values that can be overridden by CloudFormation parameters.

**New Constants**:
```python
# New consolidation stop level constant
CONSOLIDATION_STOP_LEVEL = int(os.environ.get('CONSOLIDATION_STOP_LEVEL', '1'))

# Enhanced existing constants to read from environment
DIRECTORY_CONSOLIDATION_THRESHOLD = int(os.environ.get('DIRECTORY_CONSOLIDATION_THRESHOLD', '3'))
AGGREGATION_WINDOW_SECONDS = int(os.environ.get('AGGREGATION_WINDOW_SECONDS', '300'))
```

### 2. Enhanced Tag Validator Module

**Purpose**: Extended to read and validate new configuration tags from S3 buckets.

**New Functions**:
```python
def get_bucket_consolidation_config(bucket_name: str) -> Dict[str, int]:
    """Retrieve consolidation configuration from bucket tags.
    
    Returns:
        Dictionary with keys:
        - 'directory_threshold': Effective directory consolidation threshold
        - 'stop_level': Effective consolidation stop level
        - 'source': 'tag' or 'default' for each value
    """

def validate_consolidation_tag_value(tag_value: str, min_val: int, max_val: int) -> Optional[int]:
    """Validate and convert a consolidation tag value to integer.
    
    Returns:
        Valid integer value, or None if invalid
    """
```

**Enhanced Logging**: All tag reading operations will log configuration decisions in JSON format.

### 3. Enhanced Path Consolidator Module

**Purpose**: Modified to accept and use bucket-specific configuration parameters.

**Modified Function Signature**:
```python
def consolidate_paths(
    paths: List[str], 
    directory_threshold: int = None,
    stop_level: int = None
) -> List[List[str]]:
    """Consolidate invalidation paths using bucket-specific configuration.
    
    Args:
        paths: List of object paths to invalidate
        directory_threshold: Override for DIRECTORY_CONSOLIDATION_THRESHOLD
        stop_level: Consolidation stop level (depth from root)
    """
```

**New Functions**:
```python
def calculate_path_depth(path: str, root_path: str) -> int:
    """Calculate the depth of a path relative to the root directory."""

def is_consolidation_allowed_at_depth(depth: int, stop_level: int) -> bool:
    """Check if consolidation is allowed at the given depth."""

def apply_stop_level_constraints(paths: Set[str], stop_level: int, root_path: str) -> Set[str]:
    """Apply consolidation stop level constraints to path set."""
```

### 4. Enhanced Processor Lambda Handler

**Purpose**: Orchestrate the enhanced consolidation process with bucket-specific configuration.

**Modified Processing Flow**:
1. Group messages by bucket and origin path (existing)
2. For each bucket group:
   - Validate bucket tags (existing)
   - **NEW**: Read consolidation configuration from bucket tags
   - **NEW**: Log effective configuration being used
   - Find matching distributions (existing)
   - Validate distribution tags (existing)
   - **ENHANCED**: Apply consolidation with bucket-specific parameters
   - Submit invalidations (existing)

### 5. Enhanced CloudFormation Template

**New Parameters**:
```yaml
DirectoryConsolidationThreshold:
  Type: Number
  Description: "Default threshold for directory consolidation (number of files)"
  Default: 3
  MinValue: 1
  MaxValue: 1000

ConsolidationStopLevel:
  Type: Number
  Description: "Directory depth from root where consolidation stops"
  Default: 1
  MinValue: 0
  MaxValue: 1000

# AggregationWindowSeconds already exists - no changes needed
```

**Enhanced Environment Variables**:
```yaml
Environment:
  Variables:
    DIRECTORY_CONSOLIDATION_THRESHOLD: !Ref DirectoryConsolidationThreshold
    CONSOLIDATION_STOP_LEVEL: !Ref ConsolidationStopLevel
    AGGREGATION_WINDOW_SECONDS: !Ref AggregationWindowSeconds
    # ... existing variables
```

## Data Models

### Bucket Consolidation Configuration

```python
@dataclass
class BucketConsolidationConfig:
    directory_threshold: int          # Effective directory consolidation threshold
    stop_level: int                   # Effective consolidation stop level
    directory_threshold_source: str   # 'tag' or 'default'
    stop_level_source: str           # 'tag' or 'default'
    bucket_name: str                 # Source bucket name
```

### Enhanced S3 Event Message (SQS)

```python
# Existing message structure remains unchanged
# Processing will be enhanced to include configuration resolution
```

### Path Depth Analysis

```python
@dataclass
class PathDepthInfo:
    path: str                        # Original path
    depth: int                       # Depth from root directory
    can_consolidate: bool            # Whether consolidation is allowed
    consolidation_blocked_reason: str # Reason if consolidation blocked
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Bucket Tag Configuration Properties

Property 1: Directory consolidation threshold tag reading
*For any* bucket name, when the system reads bucket tags, it should check for the `invalidator:DirectoryConsolidationThreshold` tag and return the tag value if present
**Validates: Requirements 1.1**

Property 2: Valid directory threshold tag usage
*For any* bucket with `invalidator:DirectoryConsolidationThreshold` tag containing a value between 1 and 1000, the system should use that value instead of the global DIRECTORY_CONSOLIDATION_THRESHOLD
**Validates: Requirements 1.2**

Property 3: Directory threshold fallback behavior
*For any* bucket without the `invalidator:DirectoryConsolidationThreshold` tag, the system should use the default DIRECTORY_CONSOLIDATION_THRESHOLD from common.constants
**Validates: Requirements 1.3**

Property 4: Invalid directory threshold handling
*For any* bucket with `invalidator:DirectoryConsolidationThreshold` tag containing an invalid value (outside 1-1000 range or non-numeric), the system should log a warning and use the default DIRECTORY_CONSOLIDATION_THRESHOLD
**Validates: Requirements 1.4**

Property 5: Bucket-specific threshold application
*For any* set of paths from a specific bucket, the consolidation logic should apply the bucket-specific directory threshold when determining whether to consolidate files in directories
**Validates: Requirements 1.5**

Property 6: Consolidation stop level tag reading
*For any* bucket name, when the system reads bucket tags, it should check for the `invalidator:ConsolidationStopLevel` tag and return the tag value if present
**Validates: Requirements 2.1**

Property 7: Valid stop level tag usage
*For any* bucket with `invalidator:ConsolidationStopLevel` tag containing a value between 0 and 1000, the system should use that value as the consolidation stop level
**Validates: Requirements 2.2**

Property 8: Stop level fallback behavior
*For any* bucket without the `invalidator:ConsolidationStopLevel` tag, the system should use the default CONSOLIDATION_STOP_LEVEL constant set to 1
**Validates: Requirements 2.3**

### Consolidation Stop Level Properties

Property 9: Root consolidation for stop level zero
*For any* set of paths when the consolidation stop level is 0, the system should consolidate all paths to the root wildcard `/*`
**Validates: Requirements 2.4**

Property 10: Stop level consolidation prevention
*For any* set of paths and stop level greater than 1, the system should prevent any consolidation (file and sibling) from occurring at that depth or shallower from the root directory
**Validates: Requirements 2.5**

Property 11: Index file stop level interaction
*For any* path ending with index.* or default.* files, when consolidating to the parent directory would violate the consolidation stop level, the system should not perform the consolidation
**Validates: Requirements 4.4**

Property 12: Sibling directory stop level interaction
*For any* set of sibling directories, when consolidation would occur at or above the stop level depth, the system should prevent that consolidation
**Validates: Requirements 4.5**

### CloudFormation Parameter Properties

Property 13: Environment variable configuration
*For any* Lambda function startup, the system should read DIRECTORY_CONSOLIDATION_THRESHOLD, CONSOLIDATION_STOP_LEVEL, and AGGREGATION_WINDOW_SECONDS values from environment variables set by CloudFormation parameters
**Validates: Requirements 3.5**

Property 14: Backward compatibility preservation
*For any* consolidation operation when the stop level is 1 (default), the system should produce the same consolidation results as the original algorithm
**Validates: Requirements 4.1**

### Logging Properties

Property 15: Configuration logging completeness
*For any* bucket tag reading operation for consolidation configuration, the system should log the discovered tag values in valid JSON format
**Validates: Requirements 5.1**

Property 16: Default value logging
*For any* configuration value that uses a default due to missing tags, the system should log which default values are being applied
**Validates: Requirements 5.2**

Property 17: Invalid tag value logging
*For any* invalid tag value encountered, the system should log a warning containing the invalid value and the fallback behavior being applied
**Validates: Requirements 5.3**

Property 18: Stop level prevention logging
*For any* consolidation operation prevented by the stop level, the system should log the prevention decision with the affected paths
**Validates: Requirements 5.4**

Property 19: Bucket-specific threshold logging
*For any* consolidation operation using a bucket-specific threshold, the system should log the threshold value being used for that bucket
**Validates: Requirements 5.5**

## Error Handling

### Tag Value Validation Errors

1. **Invalid Directory Threshold Values**
   - Catch: Non-numeric values, values < 1 or > 1000
   - Action: Log warning with invalid value, use default DIRECTORY_CONSOLIDATION_THRESHOLD
   - Continue: Process with default value

2. **Invalid Stop Level Values**
   - Catch: Non-numeric values, values < 0 or > 1000
   - Action: Log warning with invalid value, use default CONSOLIDATION_STOP_LEVEL
   - Continue: Process with default value

3. **Tag Reading Failures**
   - Catch: S3 GetBucketTagging errors (existing error handling)
   - Action: Log error, use all default values
   - Continue: Process with defaults

### Configuration Resolution Errors

1. **Environment Variable Reading Errors**
   - Catch: Missing or invalid environment variables
   - Action: Log warning, use hardcoded defaults
   - Continue: Process with fallback values

2. **Parameter Validation Errors**
   - Catch: CloudFormation parameters outside valid ranges
   - Action: CloudFormation validation will prevent deployment
   - Fallback: Template validation ensures valid ranges

### Consolidation Logic Errors

1. **Stop Level Calculation Errors**
   - Catch: Path depth calculation failures
   - Action: Log error, allow consolidation (fail safe)
   - Continue: Process remaining paths

2. **Configuration Application Errors**
   - Catch: Errors applying bucket-specific configuration
   - Action: Log error, fall back to global defaults
   - Continue: Process with default configuration

### Logging Errors

1. **JSON Logging Failures**
   - Catch: JSON serialization errors in configuration logging
   - Action: Log plain text fallback message
   - Continue: Process normally

## Testing Strategy

### Unit Testing

Unit tests will verify the enhanced functionality in isolation:

1. **Configuration Tag Reading**
   - Test reading valid consolidation threshold tags (1-1000)
   - Test reading valid stop level tags (0-1000)
   - Test handling missing tags (fallback to defaults)
   - Test handling invalid tag values (non-numeric, out of range)
   - Test error handling for tag reading failures

2. **Enhanced Path Consolidation**
   - Test consolidation with custom directory thresholds
   - Test stop level enforcement at various depths
   - Test interaction between stop level and index/default file rules
   - Test interaction between stop level and sibling directory consolidation
   - Test backward compatibility (stop level 1 = original behavior)

3. **Configuration Resolution**
   - Test environment variable reading
   - Test default value application
   - Test configuration logging
   - Test error handling for invalid configurations

4. **CloudFormation Parameter Integration**
   - Test parameter validation ranges
   - Test environment variable setting
   - Test default parameter values

### Property-Based Testing

Property-based tests will verify universal properties using Hypothesis with 100 iterations minimum:

**Property Test Framework**: Hypothesis for Python

**Generator Strategies**:
- Bucket names with various tag configurations
- Directory threshold values (valid and invalid ranges)
- Stop level values (valid and invalid ranges)
- Path structures at various depths
- Configuration combinations (tag present/absent, valid/invalid values)

**Property Test Coverage**:
- Properties 1-19 as defined in the Correctness Properties section
- Each property implemented as a separate test function
- Edge case generation for boundary values and error conditions

### Integration Testing

Integration tests will verify the enhanced functionality with real AWS services:

1. **End-to-End Configuration Flow**
   - Deploy CloudFormation with custom parameters
   - Create test buckets with configuration tags
   - Send test events and verify consolidation behavior
   - Verify logging contains configuration decisions

2. **Backward Compatibility**
   - Test existing buckets without new tags
   - Verify consolidation behavior remains unchanged
   - Test mixed environments (some buckets with tags, some without)

3. **Error Handling Integration**
   - Test with invalid tag values in real S3 buckets
   - Verify error logging and fallback behavior
   - Test with missing CloudFormation parameters

### Test Data Management

**Mock Data**:
- Sample bucket configurations with various tag combinations
- Path structures at different depths for stop level testing
- Invalid tag value scenarios

**Test Fixtures**:
- Reusable bucket tag configurations
- Path consolidation test cases with expected results
- Configuration resolution scenarios

## Implementation Notes

### Code Changes Required

1. **constants.py**: Add CONSOLIDATION_STOP_LEVEL constant with environment variable reading
2. **tag_validator.py**: Add functions for reading and validating consolidation configuration tags
3. **path_consolidator.py**: Enhance consolidation functions to accept and use bucket-specific parameters
4. **handler.py**: Modify processing flow to read and apply bucket-specific configuration
5. **template.yml**: Add new CloudFormation parameters and environment variables

### Deployment Considerations

1. **Backward Compatibility**: Existing deployments will continue to work with default behavior
2. **Gradual Rollout**: New parameters are optional with safe defaults
3. **Configuration Validation**: CloudFormation parameter validation prevents invalid deployments
4. **Monitoring**: Enhanced logging provides visibility into configuration decisions

### Performance Considerations

1. **Tag Reading Overhead**: Minimal impact as tag reading is already performed for validation
2. **Configuration Caching**: Configuration is resolved once per bucket per processing cycle
3. **Stop Level Calculations**: Path depth calculations are O(1) operations
4. **Memory Usage**: Configuration objects are small and short-lived

### Security Considerations

1. **Tag-Based Configuration**: Uses existing S3 tag reading permissions
2. **Parameter Validation**: CloudFormation validates parameter ranges
3. **Error Handling**: Invalid configurations fall back to safe defaults
4. **Logging**: Configuration values are logged for audit purposes

## Migration Strategy

### Phase 1: Deploy Enhanced System
- Deploy updated CloudFormation template with new parameters (using defaults)
- Deploy enhanced Lambda functions with backward-compatible behavior
- Verify existing functionality continues to work

### Phase 2: Configure Buckets
- Add configuration tags to specific buckets as needed
- Monitor logs to verify configuration is being read correctly
- Validate consolidation behavior changes as expected

### Phase 3: Optimize System-Wide Defaults
- Adjust CloudFormation parameters based on operational experience
- Update documentation and runbooks
- Train operations team on new configuration options