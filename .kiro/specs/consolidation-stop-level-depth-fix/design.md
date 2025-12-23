# Design Document

## Overview

The ConsolidationStopLevel Depth Fix addresses a bug in the sibling directory consolidation logic where paths are not consolidating correctly when ConsolidationStopLevel=1. The issue occurs when multiple subdirectories under `/prod/public/` (like `/prod/public/m/*`, `/prod/public/k/*`, etc.) should consolidate to `/prod/public/*` but are instead remaining as separate directory wildcards.

The root cause appears to be in the interaction between the directory threshold consolidation and sibling directory consolidation phases, where the sibling consolidation logic may not be correctly evaluating the parent directory depth or the consolidation threshold.

## Architecture

### Current Flow Analysis

The current consolidation flow works as follows:

```
1. Individual files → Directory wildcards (directory threshold consolidation)
   /prod/public/m/file1.html, /prod/public/m/file2.html, ... → /prod/public/m/*
   /prod/public/k/file1.html, /prod/public/k/file2.html, ... → /prod/public/k/*
   
2. Directory wildcards → Parent wildcards (sibling directory consolidation)
   /prod/public/m/*, /prod/public/k/*, /prod/public/w/*, /prod/public/x/* → /prod/public/*
```

### Issue Identification

The problem is in step 2 - the sibling directory consolidation is not occurring when it should. Possible causes:

1. **Threshold not met**: The sibling threshold (10) may not be exceeded
2. **Depth calculation error**: The parent depth may be calculated incorrectly
3. **Stop level logic error**: The consolidation allowed check may be failing
4. **Grouping logic error**: Sibling directories may not be grouped correctly by parent

### Component Changes

The fix involves debugging and correcting the sibling directory consolidation logic:

```
┌─────────────────────────────────┐
│  Path Consolidator Module       │
│  ┌─────────────────────────────┐│
│  │  Sibling Consolidation      ││
│  │  - Enhanced debugging       ││
│  │  - Fixed threshold logic    ││
│  │  - Corrected depth calc     ││
│  │  - Improved grouping        ││
│  └─────────────────────────────┘│
└─────────────────────────────────┘
```

## Components and Interfaces

### 1. Enhanced Sibling Directory Consolidation

**Root Cause Analysis Function:**
```python
def debug_sibling_consolidation_issue(paths: Set[str], stop_level: int, root_path: str) -> Dict[str, Any]:
    """Debug why sibling consolidation is not working as expected.
    
    Returns:
        Dictionary with debugging information including:
        - wildcard_count: Number of directory wildcards found
        - parent_groups: How wildcards are grouped by parent
        - threshold_analysis: Whether threshold is met for each parent
        - depth_analysis: Depth calculations for each parent
        - stop_level_analysis: Whether stop level allows consolidation
    """
```

**Enhanced Sibling Consolidation Function:**
```python
def consolidate_sibling_directories(paths: Set[str], stop_level: int = None, root_path: str = '/') -> Set[str]:
    """Enhanced with detailed debugging and issue detection.
    
    Improvements:
    - Detailed logging of grouping logic
    - Threshold evaluation logging
    - Depth calculation verification
    - Stop level decision logging
    - Before/after comparison logging
    """
```

### 2. Threshold Configuration Analysis

**Threshold Verification Function:**
```python
def verify_sibling_threshold_configuration(bucket_tags: Dict[str, str]) -> Dict[str, Any]:
    """Verify that sibling threshold configuration is correct.
    
    Returns:
        Analysis of threshold configuration including:
        - configured_threshold: The threshold value being used
        - threshold_source: Where the threshold comes from (tag, default, etc.)
        - expected_behavior: What should happen with current threshold
    """
```

### 3. Enhanced Logging and Debugging

**Consolidation Decision Logger:**
```python
def log_consolidation_decision(
    operation: str,
    parent_dir: str,
    sibling_count: int,
    threshold: int,
    parent_depth: int,
    stop_level: int,
    decision: str,
    reason: str
) -> None:
    """Log detailed consolidation decisions for debugging."""
```

## Data Models

### Sibling Consolidation Analysis

```python
@dataclass
class SiblingConsolidationAnalysis:
    parent_directory: str           # Parent directory being evaluated
    sibling_wildcards: List[str]    # List of sibling directory wildcards
    sibling_count: int              # Number of siblings
    threshold: int                  # Configured sibling threshold
    threshold_exceeded: bool        # Whether threshold is exceeded
    parent_depth: int               # Calculated depth of parent directory
    stop_level: int                 # Configured stop level
    consolidation_allowed: bool     # Whether stop level allows consolidation
    decision: str                   # Final decision (consolidate/keep_separate)
    reason: str                     # Explanation of decision
```

### Consolidation Debug Info

```python
@dataclass
class ConsolidationDebugInfo:
    input_paths: List[str]          # Original input paths
    wildcard_paths: List[str]       # Paths that are wildcards
    parent_groups: Dict[str, List[str]]  # Wildcards grouped by parent
    threshold_analysis: List[SiblingConsolidationAnalysis]  # Analysis per parent
    final_paths: List[str]          # Final consolidated paths
    consolidation_occurred: bool    # Whether any consolidation happened
    issue_detected: bool            # Whether an issue was detected
    issue_description: str          # Description of any issue found
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Property 1: Sibling directory consolidation with stop level 1
*For any* set of sibling directory wildcards under a parent directory at depth 1, when ConsolidationStopLevel is 1 and sibling threshold is exceeded, the system should consolidate them to the parent directory wildcard
**Validates: Requirements 1.1**

Property 2: Parent directory depth calculation consistency
*For any* parent directory in sibling consolidation, the system should calculate depth using the 'public' directory as level 1
**Validates: Requirements 2.1**

Property 3: Stop level consolidation allowance
*For any* parent directory depth and stop level, when depth >= stop level, the system should allow sibling consolidation
**Validates: Requirements 2.2**

Property 4: Stop level consolidation prevention
*For any* parent directory depth and stop level, when depth < stop level, the system should prevent sibling consolidation
**Validates: Requirements 2.3**

Property 5: Multi-stage consolidation flow
*For any* set of files that first consolidate to directory wildcards, when those directory wildcards exceed sibling threshold and stop level allows, the system should further consolidate to parent wildcard
**Validates: Requirements 3.3**

## Error Handling

### Threshold Configuration Issues

1. **Missing Sibling Threshold**
   - Catch: When sibling threshold tag is missing or invalid
   - Action: Use default threshold (10), log warning
   - Continue: Process with default threshold

2. **Invalid Threshold Values**
   - Catch: Threshold values outside valid range (1-1000)
   - Action: Use default threshold, log error
   - Continue: Process with safe default

### Depth Calculation Issues

1. **Parent Directory Calculation Errors**
   - Catch: Errors in getting parent directory from wildcard paths
   - Action: Log error, skip problematic wildcard
   - Continue: Process remaining wildcards

2. **Depth Calculation Inconsistencies**
   - Catch: Inconsistent depth calculations between functions
   - Action: Log warning, use conservative approach
   - Continue: Process with fallback depth calculation

### Consolidation Logic Issues

1. **Grouping Logic Failures**
   - Catch: Errors in grouping wildcards by parent directory
   - Action: Log error, process wildcards individually
   - Continue: Skip sibling consolidation for affected paths

2. **Stop Level Logic Failures**
   - Catch: Errors in stop level evaluation
   - Action: Log error, use conservative approach (prevent consolidation)
   - Continue: Process with safe fallback behavior

## Testing Strategy

### Unit Testing

Unit tests will focus on the specific sibling consolidation logic:

1. **Sibling Grouping Logic**
   - Test wildcard grouping by parent directory
   - Test edge cases (root wildcards, malformed paths)
   - Test grouping with various path structures

2. **Threshold Evaluation**
   - Test threshold comparison with various sibling counts
   - Test boundary conditions (exactly at threshold)
   - Test with different threshold configurations

3. **Stop Level Integration**
   - Test sibling consolidation with various stop levels
   - Test depth calculation for parent directories
   - Test consolidation allowed/prevented decisions

4. **End-to-End Scenarios**
   - Test the specific user scenario that's failing
   - Test multi-stage consolidation (files → directories → parent)
   - Test with various bucket tag configurations

### Property-Based Testing

Property-based tests will verify the corrected sibling consolidation logic using Hypothesis with 100 iterations minimum:

**Property Test Framework**: Hypothesis for Python

**Generator Strategies**:
- Sibling directory wildcard sets (11-20 siblings to exceed threshold)
- Parent directory structures at various depths
- Stop level values (0-5 for testing)
- Mixed consolidation scenarios

**Property Test Coverage**:
- Properties 1-5 as defined in the Correctness Properties section
- Each property implemented as a separate test function
- Edge case generation for boundary conditions

### Integration Testing

Integration tests will verify the fix works in realistic scenarios:

1. **Bucket Tag Integration**
   - Test with actual bucket tags setting thresholds and stop levels
   - Verify configuration resolution works correctly
   - Test mixed bucket configurations

2. **Multi-Stage Consolidation**
   - Test complete flow from individual files to final wildcards
   - Verify each consolidation stage works correctly
   - Test with realistic file upload patterns

3. **Performance Testing**
   - Test with large numbers of sibling directories
   - Verify consolidation performance is acceptable
   - Test memory usage with large path sets

## Implementation Notes

### Debugging Approach

1. **Add Comprehensive Logging**
   - Log sibling grouping results
   - Log threshold evaluation for each parent
   - Log depth calculations and stop level decisions
   - Log before/after consolidation states

2. **Create Debug Functions**
   - Function to analyze why consolidation didn't occur
   - Function to verify threshold configuration
   - Function to trace consolidation flow step-by-step

3. **Enhanced Error Detection**
   - Detect when expected consolidation doesn't happen
   - Identify configuration issues automatically
   - Provide actionable error messages

### Code Changes Required

1. **path_consolidator.py**:
   - Enhance `consolidate_sibling_directories()` with detailed logging
   - Add debug functions for consolidation analysis
   - Improve error handling and edge case detection

2. **Testing Updates**:
   - Add specific test for the user's failing scenario
   - Add property tests for sibling consolidation
   - Add integration tests with realistic configurations

### Root Cause Investigation

The implementation will include systematic investigation of:

1. **Threshold Analysis**: Verify the sibling threshold is being exceeded
2. **Grouping Analysis**: Verify wildcards are grouped correctly by parent
3. **Depth Analysis**: Verify parent depth calculation is correct
4. **Stop Level Analysis**: Verify stop level logic is working correctly
5. **Configuration Analysis**: Verify bucket tags are being read correctly

### Performance Considerations

1. **Logging Overhead**: Additional debug logging may increase log volume
2. **Memory Usage**: Debug information collection may use additional memory
3. **Processing Time**: Enhanced analysis may slightly increase processing time

### Security Considerations

1. **No Security Impact**: Changes are to internal consolidation logic only
2. **Input Validation**: Existing path validation remains unchanged
3. **Error Handling**: Enhanced error handling provides better security through fail-safe behavior

## Migration Strategy

### Phase 1: Deploy Enhanced Debugging
- Deploy updated Lambda functions with enhanced logging and debugging
- Monitor logs for the specific failing scenario
- Identify root cause of consolidation failure

### Phase 2: Implement Fix
- Based on root cause analysis, implement targeted fix
- Deploy fix with continued enhanced logging
- Verify fix resolves the specific user scenario

### Phase 3: Validation and Cleanup
- Validate fix works across various scenarios
- Remove excessive debug logging if no longer needed
- Update documentation with corrected behavior examples