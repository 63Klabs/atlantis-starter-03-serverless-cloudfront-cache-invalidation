# Requirements Document

## Introduction

This document specifies the requirements for enhancing the existing test file upload utility to generate significantly more test files with a complex nested directory structure. The enhancement will add a randomly named root directory containing a 5-level deep hierarchy with 10 files and 1 subdirectory at each level, while preserving the existing 12 random files per bucket functionality.

## Glossary

- **Test_File_Upload_Utility**: The existing upload-test-files.py script that uploads test HTML files to S3 buckets
- **Enhancement**: The modification to add complex directory structure generation
- **Root_Directory**: A randomly named directory created at the base path level
- **Directory_Level**: A depth level in the nested structure (1-5 levels from root directory)
- **Files_Per_Level**: Exactly 10 randomly named HTML files created at each directory level
- **Subdirectory_Per_Level**: Exactly 1 randomly named subdirectory created at each level (except level 5)
- **Nested_Structure**: The complete 5-level deep directory hierarchy with files at each level
- **Legacy_Files**: The existing 12 random files that should continue to be generated
- **Total_File_Count**: The combined count of legacy files (12) plus new nested structure files (50) = 62 files per bucket

## Requirements

### Requirement 1

**User Story:** As a test engineer, I want the upload utility to generate a complex nested directory structure, so that I can test CloudFront invalidation behavior with deep hierarchical paths.

#### Acceptance Criteria

1. WHEN the utility runs THEN it SHALL create one randomly named root directory at the base path level
2. WHEN creating the root directory THEN it SHALL generate a name using 8 random alphanumeric characters
3. WHEN building the nested structure THEN it SHALL create exactly 5 directory levels deep from the root directory
4. WHEN creating each directory level THEN it SHALL generate exactly 10 randomly named HTML files at that level
5. WHEN creating each directory level (1-4) THEN it SHALL create exactly 1 randomly named subdirectory for the next level
6. WHEN reaching level 5 THEN it SHALL create 10 files but no additional subdirectory

### Requirement 2

**User Story:** As a test engineer, I want consistent file naming within the nested structure, so that the generated files follow predictable patterns for testing purposes.

#### Acceptance Criteria

1. WHEN generating files in the nested structure THEN each file SHALL follow the "nested-XXXXXX.html" pattern where XXXXXX is 6 random alphanumeric characters
2. WHEN generating subdirectory names THEN each SHALL follow the "level-X-YYYYYYYY" pattern where X is the level number and YYYYYYYY is 8 random alphanumeric characters
3. WHEN creating files at any level THEN all filenames SHALL be unique within that directory level
4. WHEN creating subdirectories THEN all subdirectory names SHALL be unique within their parent directory
5. WHEN generating random characters THEN they SHALL include both uppercase letters, lowercase letters, and digits

### Requirement 3

**User Story:** As a developer, I want the enhancement to preserve existing functionality, so that current test scenarios continue to work while adding new capabilities.

#### Acceptance Criteria

1. WHEN the enhanced utility runs THEN it SHALL continue to generate the existing 12 random files per bucket
2. WHEN generating legacy files THEN they SHALL maintain the existing "test-XXXXXX.html" naming pattern
3. WHEN creating legacy directory structures THEN they SHALL maintain the existing 1-4 level depth distribution
4. WHEN processing multiple buckets THEN each bucket SHALL receive both legacy files (12) and nested structure files (50)
5. WHEN processing multiple stages THEN each stage SHALL receive the complete set of files in its respective base path

### Requirement 4

**User Story:** As a system administrator, I want the enhanced utility to maintain the same error handling and performance characteristics, so that deployment reliability is not compromised.

#### Acceptance Criteria

1. WHEN S3 upload operations fail for nested structure files THEN the utility SHALL retry using the same exponential backoff logic as legacy files
2. WHEN creating the nested directory structure THEN the utility SHALL handle S3 path length limitations gracefully
3. WHEN uploading the increased file count THEN the utility SHALL complete within reasonable time limits (under 5 minutes for typical bucket counts)
4. WHEN errors occur during nested structure creation THEN the utility SHALL continue processing legacy files and other buckets
5. WHEN logging nested structure operations THEN the utility SHALL provide clear progress indicators for the increased file count

### Requirement 5

**User Story:** As a developer, I want enhanced logging for the new directory structure, so that I can monitor and troubleshoot the increased complexity.

#### Acceptance Criteria

1. WHEN creating the nested structure THEN the utility SHALL log the root directory name and structure overview
2. WHEN uploading nested files THEN the utility SHALL log progress at each directory level
3. WHEN verbose mode is enabled THEN the utility SHALL show detailed paths for all nested structure files
4. WHEN operations complete THEN the utility SHALL report separate counts for legacy files and nested structure files
5. WHEN displaying the final summary THEN the utility SHALL show the total file count (62 files per bucket) with breakdown by type

### Requirement 6

**User Story:** As a test engineer, I want the nested structure to create realistic invalidation scenarios, so that I can validate CloudFront behavior with complex path patterns.

#### Acceptance Criteria

1. WHEN creating the nested structure THEN it SHALL generate paths that would trigger different consolidation behaviors
2. WHEN files are placed at different levels THEN they SHALL create scenarios for testing parent directory wildcards
3. WHEN the complete structure is created THEN it SHALL include paths suitable for testing sibling directory consolidation
4. WHEN generating the 5-level structure THEN it SHALL create realistic web application directory patterns
5. WHEN combined with legacy files THEN the complete set SHALL provide comprehensive test coverage for invalidation logic