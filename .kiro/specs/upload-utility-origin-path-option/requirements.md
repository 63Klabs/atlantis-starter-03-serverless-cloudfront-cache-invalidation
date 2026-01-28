# Requirements Document: Upload Utility Origin Path Option

## Introduction

The upload-test-files.py utility currently hard-codes the base path pattern as `/{stage}/public/` in the `determine_base_path()` function. This enhancement adds a new `--origin_path` command-line option to allow users to specify custom origin path patterns, enabling testing of CloudFront distributions with non-standard origin paths.

## Glossary

- **Upload_Utility**: The upload-test-files.py script that uploads test HTML files to S3 buckets
- **Origin_Path**: The path prefix configured in a CloudFront distribution's origin settings
- **Origin_Path_Pattern**: A template pattern that may contain placeholders like `{stageId}`
- **Stage_Id**: An environment identifier (e.g., `prod`, `staging`, `dev`) that determines the S3 base path
- **Base_Path**: The S3 path prefix used for uploading files, derived from the origin path pattern and stage

## Requirements

### Requirement 1: Add --origin_path Command-Line Option

**User Story:** As a developer, I want to specify a custom origin path pattern when uploading test files, so that I can test CloudFront distributions with non-standard origin paths.

#### Acceptance Criteria

1.1. THE Upload_Utility SHALL accept a new optional command-line argument `--origin_path` that specifies the origin path pattern

1.2. WHEN the `--origin_path` option is provided, THE Upload_Utility SHALL use the specified pattern instead of the default `/{stageId}/public/` pattern

1.3. WHEN the `--origin_path` option is not provided, THE Upload_Utility SHALL use the default pattern `/{stageId}/public/` to maintain backward compatibility

1.4. THE `--origin_path` option value SHALL require a leading `/` character

1.5. THE `--origin_path` option value SHALL NOT require a trailing `/` character (it will be added automatically)

1.6. THE `--origin_path` option SHALL support the `{stageId}` placeholder for dynamic stage substitution

### Requirement 2: Update determine_base_path Function

**User Story:** As a developer, I want the determine_base_path function to use the custom origin path pattern, so that files are uploaded to the correct S3 paths.

#### Acceptance Criteria

2.1. THE `determine_base_path()` function SHALL accept the origin path pattern as a parameter (from configuration)

2.2. WHEN the origin path pattern contains `{stageId}`, THE function SHALL replace it with the actual stage value passed to the function

2.3. THE function SHALL ensure the returned base path starts with `/`

2.4. THE function SHALL ensure the returned base path ends with `/`

2.5. WHEN the origin path pattern is `/{stageId}/public/`, THE function SHALL return `/{stage}/public/` (current behavior)

2.6. WHEN the origin path pattern is `/app/{stageId}`, THE function SHALL return `/app/{stage}/` (with trailing slash added)

2.7. WHEN the origin path pattern is `/{stageId}`, THE function SHALL return `/{stage}/` (with trailing slash added)

### Requirement 3: Validate Origin Path Pattern

**User Story:** As a developer, I want the utility to validate the origin path pattern, so that I receive clear error messages for invalid patterns.

#### Acceptance Criteria

3.1. WHEN the `--origin_path` value does not start with `/`, THE Upload_Utility SHALL display an error message and exit

3.2. THE error message SHALL clearly state that the origin path must start with `/`

3.3. THE Upload_Utility SHALL validate the pattern before processing any buckets

3.4. WHEN the pattern is valid, THE Upload_Utility SHALL proceed with normal operation

### Requirement 4: Update Configuration Data Model

**User Story:** As a maintainer, I want the Configuration dataclass to include the origin path pattern, so that it can be passed to components that need it.

#### Acceptance Criteria

4.1. THE `Configuration` dataclass SHALL include a new field `origin_path_pattern: str`

4.2. THE default value for `origin_path_pattern` SHALL be `/{stageId}/public/`

4.3. THE `EnvironmentManager` class SHALL accept the origin path pattern and pass it to the `determine_base_path()` function

4.4. THE `determine_base_path()` function signature SHALL be updated to accept the origin path pattern

### Requirement 5: Update Documentation and Tests

**User Story:** As a developer, I want updated documentation and tests, so that I understand how to use the new option and can verify it works correctly.

#### Acceptance Criteria

5.1. ALL documentation files that reference the upload-test-files.py script SHALL be updated to mention the new `--origin_path` option

5.2. ALL integration tests that use the upload-test-files.py script SHALL be reviewed and updated if necessary

5.3. NEW unit tests SHALL be added to verify the `--origin_path` option works correctly

5.4. NEW unit tests SHALL verify that `{stageId}` placeholder replacement works correctly

5.5. NEW unit tests SHALL verify that path normalization (leading/trailing slashes) works correctly

5.6. THE help text for the `--origin_path` option SHALL include examples of valid patterns

### Requirement 6: Maintain Backward Compatibility

**User Story:** As a system operator, I want existing scripts and CI/CD pipelines to continue working without modification, so that the enhancement does not break current functionality.

#### Acceptance Criteria

6.1. WHEN the `--origin_path` option is not provided, THE Upload_Utility SHALL behave exactly as it does currently

6.2. ALL existing test files SHALL continue to pass without modification

6.3. THE default behavior SHALL remain `/{stageId}/public/` pattern

6.4. THE CI/CD pipeline (buildspec-postdeploy.yml and post-deploy.sh) SHALL continue to work without modification

## Examples

### Example 1: Default Behavior (No --origin_path)
```bash
python upload-test-files.py --buckets my-bucket --stages prod
# Uses default pattern: /{stageId}/public/
# Uploads to: /prod/public/
```

### Example 2: Custom Origin Path with Stage Placeholder
```bash
python upload-test-files.py --buckets my-bucket --stages prod --origin_path /app/{stageId}
# Uses custom pattern: /app/{stageId}
# Uploads to: /app/prod/
```

### Example 3: Custom Origin Path without Stage Placeholder
```bash
python upload-test-files.py --buckets my-bucket --stages prod --origin_path /static
# Uses custom pattern: /static
# Uploads to: /static/
```

### Example 4: Multiple Stages with Custom Pattern
```bash
python upload-test-files.py --buckets my-bucket --stages prod,staging --origin_path /app/{stageId}
# For prod: uploads to /app/prod/
# For staging: uploads to /app/staging/
```

### Example 5: Invalid Pattern (Missing Leading Slash)
```bash
python upload-test-files.py --buckets my-bucket --stages prod --origin_path app/{stageId}
# Error: Origin path must start with '/'
# Exit code: 1
```

## Non-Functional Requirements

### Performance
- The addition of the `--origin_path` option SHALL NOT impact upload performance
- Pattern validation SHALL complete in < 1ms

### Usability
- The help text SHALL clearly explain the `--origin_path` option and its format
- Error messages SHALL be clear and actionable

### Maintainability
- The implementation SHALL follow existing code patterns in the upload utility
- The changes SHALL be minimal and focused on the specific enhancement
