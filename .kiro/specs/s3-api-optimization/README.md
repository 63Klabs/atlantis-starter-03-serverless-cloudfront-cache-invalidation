# S3 API Optimization Spec

**Feature:** s3-api-optimization  
**Created:** January 30, 2026  
**Status:** Ready for Implementation  
**Priority:** High

---

## Quick Links

- [Analysis Report](../s3-api-optimization-analysis.md) - Initial analysis and recommendations
- [Requirements](requirements.md) - Detailed requirements and acceptance criteria
- [Design](design.md) - Technical design and architecture
- [Tasks](tasks.md) - Implementation task list

---

## Overview

This spec implements an optimization to reduce S3 API calls in the processor Lambda function by 67%. Currently, the function makes 3 separate API calls per bucket to retrieve the same tag data. This optimization fetches tags once per bucket and passes them to all functions that need them.

---

## Problem

The processor function makes redundant S3 API calls:
1. `validate_bucket_tags()` → calls `get_bucket_tags()` 
2. Direct call to `get_bucket_tags()` for application matching
3. `get_bucket_consolidation_config()` → calls `get_bucket_tags()`

**Impact:**
- 67% unnecessary API overhead
- 500-2000ms wasted per invocation (for 5 buckets)
- Increased risk of S3 API rate limiting
- Higher costs and reduced scalability

---

## Solution

**Single Fetch with Shared State:**
- Fetch bucket tags once per bucket
- Pass tags to all functions that need them
- Add new `_from_dict()` variants of existing functions
- Keep existing functions for backward compatibility

---

## Benefits

✅ 67% reduction in S3 API calls  
✅ 10-20% faster Lambda execution  
✅ Better scalability  
✅ Lower costs  
✅ Reduced rate limit risk  
✅ Improved testability  

---

## Implementation Approach

### New Functions

1. **validate_bucket_tags_from_dict(tags)** - Validate from pre-fetched tags
2. **get_bucket_consolidation_config_from_dict(tags, name)** - Extract config from pre-fetched tags

### Handler Changes

```python
# Before (3 API calls)
validate_bucket_tags(bucket_name)          # API call #1
get_bucket_tags(bucket_name)               # API call #2
get_bucket_consolidation_config(bucket_name)  # API call #3

# After (1 API call)
tags = get_bucket_tags(bucket_name)        # API call (once)
validate_bucket_tags_from_dict(tags)
get_bucket_consolidation_config_from_dict(tags, bucket_name)
```

---

## Estimated Effort

**Total:** 7 hours

- Phase 1: Add New Functions - 2 hours
- Phase 2: Refactor Handler - 2 hours
- Phase 3: Testing and Validation - 2 hours
- Phase 4: Documentation and Deployment - 1 hour

---

## Success Criteria

✅ S3 API calls reduced by 60-70%  
✅ Lambda execution time reduced by 10-20%  
✅ No increase in error rate  
✅ 100% test coverage for new code  
✅ All existing tests pass  
✅ Production deployment stable for 48 hours  

---

## Getting Started

### Prerequisites

1. Virtual environment activated
2. All requirements installed
3. AWS credentials configured
4. Familiarity with processor Lambda function

### Development Workflow

1. **Review Documents:**
   - Read [Requirements](requirements.md) for acceptance criteria
   - Read [Design](design.md) for technical details
   - Review [Tasks](tasks.md) for implementation steps

2. **Create Feature Branch:**
   ```bash
   git checkout -b feature/s3-api-optimization
   ```

3. **Implement Tasks:**
   - Follow task order in [tasks.md](tasks.md)
   - Run tests after each task
   - Commit frequently

4. **Testing:**
   ```bash
   # Activate virtual environment
   source .venv/bin/activate
   
   # Run all tests
   pytest application-infrastructure/tests/ -v
   
   # Check coverage
   pytest application-infrastructure/tests/ --cov=application-infrastructure/functions --cov-report=html
   ```

5. **Create Pull Request:**
   - Ensure all tests pass
   - Verify coverage ≥ 100% for new code
   - Request code review

---

## Testing Strategy

### Unit Tests
- Test new functions with various inputs
- Test error handling
- Verify backward compatibility

### Property-Based Tests
- Validate functions never crash
- Test equivalence with original functions
- Verify tag value parsing

### Integration Tests
- Verify single API call per bucket
- Test error scenarios
- Validate performance improvement

### Performance Tests
- Measure API call reduction
- Measure execution time improvement
- Verify memory usage unchanged

---

## Deployment Plan

### Phase 1: Development (Week 1)
- Implement new functions
- Add comprehensive tests
- Achieve 100% coverage

### Phase 2: Integration (Week 1)
- Refactor handler
- Integration testing
- Performance validation

### Phase 3: Staging (Week 2)
- Deploy to staging
- Monitor metrics
- Verify improvements

### Phase 4: Production (Week 2)
- Deploy to production
- Monitor for 48 hours
- Document results

---

## Monitoring

### Key Metrics

**CloudWatch Metrics:**
- Lambda Duration - Track execution time
- S3 API Calls - Track GetBucketTagging calls
- Error Rate - Monitor for regressions

**Custom Metrics:**
- S3APICallsPerBucket
- TagFetchDuration
- ValidationFailures

### Alarms

**Critical:**
- Lambda error rate > 1%
- Lambda duration > P99 baseline + 20%
- S3 API throttling errors

**Warning:**
- Tag fetch failures > 5%
- Validation failures > 10%

---

## Rollback Plan

### Triggers
- Error rate increase > 5%
- Performance degradation > 20%
- S3 API throttling
- Critical bugs

### Procedure
1. Revert Lambda function code
2. Monitor for 30 minutes
3. Verify baseline restored
4. Investigate and fix
5. Redeploy when ready

---

## Documentation

### Code Documentation
- Docstrings for all new functions
- Inline comments for handler changes
- Type hints for all parameters

### Architecture Documentation
- Update ARCHITECTURE.md
- Add sequence diagrams
- Document performance characteristics

### Operational Documentation
- Update runbooks
- Document new metrics
- Update troubleshooting guides

---

## Related Documents

- [Analysis Report](../s3-api-optimization-analysis.md) - Initial investigation
- [ARCHITECTURE.md](../../../ARCHITECTURE.md) - System architecture
- [AI_CONTEXT.md](../../../AI_CONTEXT.md) - Development guidelines

---

## Questions or Issues?

If you have questions about this spec:
1. Review the [Requirements](requirements.md) for detailed acceptance criteria
2. Check the [Design](design.md) for technical details
3. Consult the [Tasks](tasks.md) for implementation guidance
4. Refer to the [Analysis Report](../s3-api-optimization-analysis.md) for background

---

## Status Updates

### January 30, 2026
- ✅ Analysis complete
- ✅ Requirements documented
- ✅ Design finalized
- ✅ Tasks created
- ⏳ Ready for implementation

---

**Next Step:** Begin Task 1.1 - Create validate_bucket_tags_from_dict() function
