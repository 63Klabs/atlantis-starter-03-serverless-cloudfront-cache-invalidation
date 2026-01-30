# S3 API Optimization - Requirements

**Feature:** s3-api-optimization  
**Created:** January 30, 2026  
**Status:** Draft  
**Priority:** High

---

## Overview

Optimize the processor Lambda function to eliminate redundant S3 API calls when retrieving bucket tags. Currently, the function makes 3 separate API calls per bucket to retrieve the same tag data, creating unnecessary overhead and scalability concerns.

---

## Problem Statement

The processor function processes S3 events from multiple buckets and needs to:
1. Validate that buckets are authorized for invalidation processing
2. Extract application metadata from bucket tags
3. Retrieve bucket-specific consolidation configuration from tags

Currently, each of these operations independently calls `get_bucket_tags()`, resulting in 3 S3 API calls per bucket to retrieve identical data.

**Impact:**
- 67% unnecessary API overhead
- 500-2000ms additional latency per invocation (for 5 buckets)
- Increased risk of S3 API rate limiting
- Higher AWS costs
- Reduced scalability

---

## Goals

1. **Reduce S3 API calls by 67%** - Fetch bucket tags once per bucket per Lambda invocation
2. **Maintain backward compatibility** - Keep existing functions operational for other use cases
3. **Preserve functionality** - No changes to validation or configuration logic
4. **Improve performance** - Reduce Lambda execution time by 10-20%
5. **Enhance testability** - Make tag-dependent logic easier to unit test

---

## Non-Goals

- Cross-invocation caching (not needed for this optimization)
- Batch/parallel tag fetching (premature optimization)
- Changes to tag structure or naming conventions
- Modifications to CloudFront or distribution logic

---

## User Stories

### US-1: As a system operator, I want the processor to minimize S3 API calls
**Acceptance Criteria:**
- AC-1.1: Processor fetches bucket tags exactly once per bucket per invocation
- AC-1.2: All tag-dependent operations use the same fetched tag data
- AC-1.3: S3 API call count is reduced by at least 60% compared to current implementation
- AC-1.4: CloudWatch metrics show reduction in GetBucketTagging API calls

### US-2: As a developer, I want tag validation logic to be testable without API calls
**Acceptance Criteria:**
- AC-2.1: New functions accept pre-fetched tag dictionaries as input
- AC-2.2: Unit tests can validate logic without mocking S3 API
- AC-2.3: Test coverage for new functions is 100%
- AC-2.4: Property-based tests validate tag parsing logic

### US-3: As a system maintainer, I want backward compatibility preserved
**Acceptance Criteria:**
- AC-3.1: Existing `validate_bucket_tags()` function remains unchanged
- AC-3.2: Existing `get_bucket_consolidation_config()` function remains unchanged
- AC-3.3: All existing unit tests continue to pass
- AC-3.4: Integration tests verify both old and new code paths work

### US-4: As a system operator, I want improved Lambda performance
**Acceptance Criteria:**
- AC-4.1: Lambda execution time reduced by at least 10%
- AC-4.2: No increase in error rate after optimization
- AC-4.3: CloudWatch logs show single tag fetch per bucket
- AC-4.4: Performance metrics tracked and validated

---

## Functional Requirements

### FR-1: Single Tag Fetch Per Bucket
**Priority:** P0 (Critical)

The processor handler must fetch bucket tags exactly once per bucket during event processing.

**Details:**
- Fetch occurs after bucket grouping but before validation
- Fetch happens once per unique bucket name in the message batch
- Failed fetches are handled gracefully with appropriate logging
- Tag data is passed to all downstream operations

**Validation:**
- CloudWatch logs show single `get_bucket_tagging` call per bucket
- Unit tests verify single fetch in handler logic
- Integration tests confirm API call count

---

### FR-2: Tag Dictionary Validation Function
**Priority:** P0 (Critical)

Create a new function that validates bucket tags from a pre-fetched dictionary without making API calls.

**Function Signature:**
```python
def validate_bucket_tags_from_dict(tags: Dict[str, str]) -> bool:
    """Validate bucket tags from pre-fetched tag dictionary.
    
    Args:
        tags: Dictionary of bucket tags (key-value pairs)
        
    Returns:
        True if AllowInvalidationEvents=true, False otherwise
    """
```

**Behavior:**
- Returns `False` if tags is `None`
- Returns `True` if `AllowInvalidationEvents` tag equals `"true"`
- Returns `False` for any other value or missing tag
- Logs validation results with appropriate context

**Validation:**
- Unit tests cover all validation scenarios
- Property-based tests validate tag value handling
- Integration tests verify correct behavior in handler

---

### FR-3: Tag Dictionary Configuration Function
**Priority:** P0 (Critical)

Create a new function that extracts consolidation configuration from a pre-fetched tag dictionary without making API calls.

**Function Signature:**
```python
def get_bucket_consolidation_config_from_dict(
    tags: Dict[str, str], 
    bucket_name: str
) -> Dict[str, any]:
    """Get consolidation config from pre-fetched tag dictionary.
    
    Args:
        tags: Dictionary of bucket tags (key-value pairs)
        bucket_name: Bucket name (for logging only)
        
    Returns:
        Configuration dictionary with threshold and stop level values
    """
```

**Behavior:**
- Returns default configuration if tags is `None`
- Extracts `invalidator:DirectoryConsolidationThreshold` tag
- Extracts `invalidator:ConsolidationStopLevel` tag
- Extracts `invalidator:SiblingDirectoryConsolidationThreshold` tag
- Validates tag values and falls back to defaults for invalid values
- Logs configuration source (tag vs default) for each setting

**Validation:**
- Unit tests cover all configuration scenarios
- Property-based tests validate tag value parsing
- Integration tests verify correct configuration application

---

### FR-4: Handler Refactoring
**Priority:** P0 (Critical)

Refactor the processor handler to use the new tag dictionary functions.

**Changes Required:**
1. Fetch bucket tags once after bucket grouping
2. Handle tag fetch failures appropriately
3. Pass tags to `validate_bucket_tags_from_dict()`
4. Pass tags to `get_bucket_consolidation_config_from_dict()`
5. Remove redundant `get_bucket_tags()` calls

**Error Handling:**
- If tag fetch fails (`None` returned), skip bucket processing
- Log detailed error information for debugging
- Mark messages for deletion to prevent reprocessing
- Continue processing other buckets

**Validation:**
- Integration tests verify single API call per bucket
- Unit tests verify error handling paths
- CloudWatch logs confirm correct behavior

---

### FR-5: Backward Compatibility
**Priority:** P0 (Critical)

Maintain existing functions for backward compatibility and standalone use.

**Requirements:**
- Keep `validate_bucket_tags(bucket_name)` function unchanged
- Keep `get_bucket_consolidation_config(bucket_name)` function unchanged
- Keep `get_bucket_tags(bucket_name)` function unchanged
- All existing unit tests must pass without modification
- Existing integration tests must pass without modification

**Validation:**
- Run full test suite without changes
- Verify no regressions in existing functionality
- Confirm both old and new code paths work

---

## Non-Functional Requirements

### NFR-1: Performance
**Priority:** P0 (Critical)

- Lambda execution time must decrease by at least 10%
- S3 API call count must decrease by at least 60%
- No increase in memory usage
- No increase in error rate

**Measurement:**
- CloudWatch metrics for Lambda duration
- CloudWatch metrics for S3 API calls
- CloudWatch metrics for error rate
- Performance tests comparing before/after

---

### NFR-2: Testability
**Priority:** P0 (Critical)

- New functions must be unit testable without API mocking
- Test coverage for new code must be 100%
- Property-based tests for tag validation logic
- Integration tests for handler changes

**Measurement:**
- Code coverage reports
- Test execution results
- Property-based test pass rate

---

### NFR-3: Maintainability
**Priority:** P1 (High)

- Code must follow existing patterns and conventions
- Functions must have clear docstrings
- Logging must provide debugging context
- Error messages must be actionable

**Measurement:**
- Code review approval
- Documentation completeness
- Log clarity and usefulness

---

### NFR-4: Observability
**Priority:** P1 (High)

- CloudWatch logs must show tag fetch operations
- Logs must indicate when tags are reused
- Metrics must track API call reduction
- Errors must be logged with full context

**Measurement:**
- Log analysis
- Metric dashboards
- Error tracking

---

## Technical Constraints

### TC-1: Python Version
- Must use Python 3.12 (current Lambda runtime)
- Must be compatible with existing Lambda layer

### TC-2: AWS SDK
- Must use boto3 for S3 API calls
- Must handle botocore exceptions appropriately

### TC-3: Logging
- Must use common.logger for all logging
- Must follow existing log format and structure

### TC-4: Testing Framework
- Must use pytest for unit tests
- Must use hypothesis for property-based tests

---

## Dependencies

### Internal Dependencies
- `common.logger` - Logging functionality
- `common.constants` - Configuration constants
- Existing `tag_validator.py` module
- Existing `handler.py` module

### External Dependencies
- boto3 - AWS SDK for Python
- botocore - AWS SDK core functionality
- pytest - Testing framework
- hypothesis - Property-based testing

---

## Success Metrics

### Primary Metrics
1. **S3 API Call Reduction:** 60-70% fewer GetBucketTagging calls
2. **Lambda Duration:** 10-20% reduction in execution time
3. **Error Rate:** No increase in error rate
4. **Test Coverage:** 100% coverage for new code

### Secondary Metrics
1. **Cost Reduction:** Measurable decrease in S3 API costs
2. **Scalability:** Improved headroom for handling more buckets
3. **Code Quality:** Passing code review with no major issues
4. **Documentation:** Complete and accurate documentation

---

## Risks and Mitigation

### Risk 1: Breaking Existing Functionality
**Likelihood:** Low  
**Impact:** High  
**Mitigation:**
- Keep existing functions unchanged
- Comprehensive regression testing
- Gradual rollout with monitoring
- Rollback plan ready

### Risk 2: Error Handling Edge Cases
**Likelihood:** Medium  
**Impact:** Medium  
**Mitigation:**
- Explicit error handling for all failure modes
- Detailed logging for debugging
- Unit tests for error scenarios
- Integration tests for failure paths

### Risk 3: Performance Regression
**Likelihood:** Low  
**Impact:** High  
**Mitigation:**
- Performance testing before deployment
- CloudWatch monitoring after deployment
- Comparison metrics (before/after)
- Rollback if performance degrades

---

## Out of Scope

The following items are explicitly out of scope for this feature:

1. **Cross-invocation caching** - Not needed for single-invocation optimization
2. **Parallel tag fetching** - Premature optimization, adds complexity
3. **Tag structure changes** - No changes to tag naming or format
4. **CloudFront optimization** - Separate concern, different API
5. **DynamoDB caching** - Overkill for this use case
6. **Lambda extension caching** - Unnecessary complexity

---

## Future Considerations

Items that may be considered in future iterations:

1. **Batch tag fetching** - If processing many buckets simultaneously
2. **Tag change notifications** - EventBridge rules for tag updates
3. **Configuration validation** - Pre-deployment tag validation
4. **Monitoring dashboard** - Dedicated dashboard for tag operations

---

## Acceptance Criteria Summary

This feature is considered complete when:

✅ All user stories have passing acceptance criteria  
✅ All functional requirements are implemented  
✅ All non-functional requirements are met  
✅ S3 API calls reduced by at least 60%  
✅ Lambda execution time reduced by at least 10%  
✅ Test coverage is 100% for new code  
✅ All existing tests pass without modification  
✅ Code review approved  
✅ Documentation complete  
✅ Deployed to production with monitoring  

---

**Next Steps:**
1. Review and approve requirements
2. Create design document
3. Create implementation tasks
4. Begin development
