# Changelog

## v0.0.2 - unreleased

### Enhancements

- Added new parameter `OriginPathPattern` to allow for more flexible origin path matching
- Enhanced logging for distribution stage matching debugging:
  - Added detailed logging in distribution tag validation to show expected vs actual tag values
  - Added logging for distribution search results showing resolved origin paths
  - Added logging for validation results per distribution with stage information
  - Created `DISTRIBUTION_DEBUGGING_GUIDE.md` to help diagnose stage matching issues

### Bug Fixes

- **CRITICAL**: Fixed distribution stage matching to properly separate prod and beta stages:
  - Refactored message grouping to group by bucket only (not by origin/stage)
  - Stage and origin path now determined from bucket tags (processor independence)
  - Stage extraction happens AFTER reading bucket pattern for accuracy
  - Each stage now correctly finds and validates only its own distributions
  - Created `GROUPING_REFACTOR_SUMMARY.md` documenting the architectural change

- **CRITICAL**: Fixed multiple invalidations being sent per distribution:
  - Removed duplicate stage grouping in consolidate_paths call
  - Handler now groups by stage once, consolidate_paths only consolidates paths
  - Each stage now sends exactly ONE consolidated invalidation per distribution
  - Paths remain relative to CloudFront origin (correct behavior)
  - Created `PATH_ISSUE_ANALYSIS.md` documenting the fix

### Breaking Changes

- Renamed `group_messages_by_bucket_and_origin()` to `group_messages_by_bucket()`
- Changed return type from `Dict[Tuple[str, str, str], List]` to `Dict[str, List]`
- Processing flow restructured: bucket → validate → resolve pattern → group by stage → process stages

## v0.0.1 - 2026-01-07

- Initial release