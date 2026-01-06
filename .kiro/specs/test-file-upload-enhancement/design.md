# Design Document

## Overview

The Test File Upload Enhancement extends the existing upload-test-files.py utility to generate a significantly more complex directory structure for comprehensive CloudFront invalidation testing. The enhancement adds a 5-level deep nested directory hierarchy with 10 files per level (50 total files) while preserving the existing 12 random files, resulting in 62 files per bucket per stage.

The design maintains backward compatibility with the existing utility architecture while adding new components for nested structure generation. The enhancement integrates seamlessly with the current PathGenerator component through extension rather than replacement.

## Architecture

The enhanced utility extends the existing modular architecture with new components for nested structure generation:

```
Enhanced TestFileUploader
├── ArgumentParser - Command line argument handling (unchanged)
├── EnvironmentManager - Environment variable and AWS profile management (unchanged)
├── FileGenerator - Test file content and naming generation (unchanged)
├── PathGenerator - S3 path and directory structure generation (enhanced)
├── NestedStructureGenerator - NEW: Complex directory hierarchy generation
├── S3Uploader - AWS S3 upload operations with retry logic (unchanged)
└── Logger - Structured logging and progress reporting (enhanced)
```

### New Components

**NestedStructureGenerator**: Handles the creation of the 5-level deep directory structure with files at each level.

**Enhanced PathGenerator**: Extended to coordinate between legacy path generation and nested structure generation.

**Enhanced Logger**: Updated to provide detailed progress reporting for the increased file count and complex structure.

## Components and Interfaces

### NestedStructureGenerator (New)
- **Purpose**: Generate complex nested directory structures with files at each level
- **Interface**:
  - `generate_nested_structure(base_path: str) -> List[Tuple[str, str]]`
  - `generate_root_directory_name() -> str`
  - `generate_subdirectory_name(level: int) -> str`
  - `generate_nested_filename() -> str`
- **Responsibilities**:
  - Create 5-level deep directory hierarchy
  - Generate 10 files per directory level (50 total files)
  - Create 1 subdirectory per level (levels 1-4 only)
  - Ensure unique naming within each directory level
  - Follow "nested-XXXXXX.html" and "level-X-YYYYYYYY" naming patterns

### Enhanced PathGenerator
- **Purpose**: Coordinate legacy and nested structure path generation
- **Interface**:
  - `generate_all_upload_paths(base_path: str) -> List[Tuple[str, str]]` (new)
  - `generate_upload_paths(base_path: str, count: int) -> List[Tuple[str, str]]` (existing)
- **Responsibilities**:
  - Maintain existing legacy path generation (12 files)
  - Integrate nested structure generation (50 files)
  - Return combined path list (62 total files)
  - Ensure no path conflicts between legacy and nested files

### Enhanced Logger
- **Purpose**: Provide detailed progress reporting for increased complexity
- **Interface**:
  - `log_nested_structure_start(root_dir: str)` (new)
  - `log_level_progress(level: int, files_count: int)` (new)
  - `log_enhanced_summary(results: Dict[str, EnhancedUploadResult])` (new)
  - All existing logging methods (unchanged)
- **Responsibilities**:
  - Log nested structure creation progress
  - Report file counts by type (legacy vs nested)
  - Provide detailed verbose output for complex paths
  - Maintain existing logging functionality

## Data Models

### Enhanced UploadResult
```python
@dataclass
class EnhancedUploadResult:
    bucket: str
    successful_uploads: int
    failed_uploads: int
    upload_paths: List[str]
    legacy_file_count: int  # New: count of legacy files (12)
    nested_file_count: int  # New: count of nested structure files (50)
    root_directory: str     # New: name of the nested structure root directory
```

### NestedStructureInfo
```python
@dataclass
class NestedStructureInfo:
    root_directory: str
    levels: List[DirectoryLevel]
    total_files: int  # Should always be 50
    total_directories: int  # Should always be 4 (levels 1-4 have subdirs)
```

### DirectoryLevel
```python
@dataclass
class DirectoryLevel:
    level_number: int  # 1-5
    directory_path: str
    files: List[str]  # 10 filenames
    subdirectory: Optional[str]  # None for level 5
```

## Nested Structure Generation Algorithm

The nested structure follows a deterministic pattern while using randomization for names:

### Directory Structure Pattern
```
/{base_path}/{root_dir}/
├── nested-XXXXXX.html (10 files)
└── level-1-YYYYYYYY/
    ├── nested-XXXXXX.html (10 files)
    └── level-2-YYYYYYYY/
        ├── nested-XXXXXX.html (10 files)
        └── level-3-YYYYYYYY/
            ├── nested-XXXXXX.html (10 files)
            └── level-4-YYYYYYYY/
                └── nested-XXXXXX.html (10 files, no subdirectory)
```

### Generation Algorithm
1. **Root Directory**: Generate 8-character alphanumeric name
2. **For each level (1-5)**:
   - Generate 10 unique filenames with "nested-XXXXXX.html" pattern
   - If level < 5: Generate 1 subdirectory with "level-X-YYYYYYYY" pattern
   - Create S3 paths for all files at current level
3. **Path Assembly**: Combine base_path + root_dir + level_path + filename
4. **Uniqueness**: Ensure no filename conflicts within each directory level

### Randomization Strategy
- **Root Directory**: 8 random alphanumeric characters
- **Subdirectories**: "level-{level}-{8 random alphanumeric characters}"
- **Files**: "nested-{6 random alphanumeric characters}.html"
- **Character Set**: [A-Za-z0-9] for all random components
- **Uniqueness**: Retry generation if conflicts occur within same directory level

## Integration with Existing Components

### PathGenerator Integration
The existing `generate_upload_paths()` method remains unchanged to maintain backward compatibility. A new `generate_all_upload_paths()` method coordinates both legacy and nested generation:

```python
def generate_all_upload_paths(self, base_path: str) -> List[Tuple[str, str]]:
    # Generate legacy paths (12 files)
    legacy_paths = self.generate_upload_paths(base_path, 12)
    
    # Generate nested structure paths (50 files)
    nested_paths = self.nested_generator.generate_nested_structure(base_path)
    
    # Combine and return (62 total files)
    return legacy_paths + nested_paths
```

### S3Uploader Integration
No changes required to S3Uploader component. The enhanced path list is processed using existing upload logic, maintaining retry behavior and error handling for all files.

### Logger Integration
Enhanced logging provides progress indicators for the increased file count:
- Startup: Log total expected file count (62 per bucket)
- Progress: Log completion of each directory level
- Summary: Break down counts by legacy (12) and nested (50) files

## Performance Considerations

### Upload Time Impact
- **File Count Increase**: From 12 to 62 files per bucket (5.17x increase)
- **Expected Time**: Proportional increase in upload time
- **Mitigation**: Existing retry logic and parallel processing per bucket
- **Timeout**: Requirement 4.3 specifies completion within 5 minutes

### Memory Usage
- **Path Storage**: 62 paths per bucket stored in memory
- **Content Reuse**: Single source file content reused for all uploads
- **Minimal Impact**: Path strings are small, content is shared

### S3 API Considerations
- **Request Rate**: Increased PUT requests may approach S3 rate limits
- **Path Length**: Deep nesting may approach S3 key length limits (1024 characters)
- **Validation**: Check total path length before upload attempts

## Error Handling

The enhancement maintains existing error handling patterns while adding specific handling for nested structure scenarios:

### Nested Structure Errors
- **Path Length Validation**: Check S3 key length limits before upload
- **Directory Creation**: Handle S3 path creation for deep nesting
- **Partial Failures**: Continue with legacy files if nested structure fails

### Enhanced Error Recovery
- **Level-by-Level**: If one directory level fails, continue with remaining levels
- **Isolation**: Nested structure failures don't affect legacy file uploads
- **Reporting**: Clear error messages distinguish between legacy and nested failures

## Testing Strategy

The testing approach extends existing patterns to cover the new nested structure functionality:

### Unit Testing
- **NestedStructureGenerator**: Test directory hierarchy generation with known inputs
- **Path Uniqueness**: Verify no filename conflicts within directory levels
- **Naming Patterns**: Validate "nested-XXXXXX.html" and "level-X-YYYYYYYY" formats
- **Integration**: Test coordination between legacy and nested path generation

### Property-Based Testing
- **File Count Consistency**: Verify exactly 50 nested files generated per bucket
- **Directory Depth**: Ensure exactly 5 levels in nested structure
- **Naming Compliance**: Test filename and directory name pattern adherence
- **Path Uniqueness**: Verify no duplicate paths in combined legacy + nested output
- **Total Count**: Confirm exactly 62 files per bucket across all scenarios

### Integration Testing
- **End-to-End**: Test complete upload process with real S3 buckets
- **Performance**: Verify completion within 5-minute requirement
- **Error Scenarios**: Test partial failures and recovery behavior
- **Multiple Buckets**: Validate consistent behavior across multiple target buckets

The testing framework continues to use pytest with Hypothesis for property-based testing, maintaining consistency with existing project patterns.

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Property 1: Root directory creation consistency
*For any* execution of the enhanced utility, exactly one randomly named root directory should be created at the base path level
**Validates: Requirements 1.1**

Property 2: Root directory naming pattern
*For any* generated root directory name, it should consist of exactly 8 alphanumeric characters
**Validates: Requirements 1.2**

Property 3: Nested structure depth consistency
*For any* generated nested structure, the deepest directory path should be exactly 5 levels deep from the root directory
**Validates: Requirements 1.3**

Property 4: Files per level consistency
*For any* directory level in the nested structure, exactly 10 HTML files should be generated at that level
**Validates: Requirements 1.4**

Property 5: Subdirectory creation pattern
*For any* directory levels 1-4 in the nested structure, exactly one subdirectory should be created, and level 5 should have no subdirectories
**Validates: Requirements 1.5, 1.6**

Property 6: Nested filename pattern compliance
*For any* file generated in the nested structure, the filename should follow the "nested-XXXXXX.html" pattern where XXXXXX is exactly 6 alphanumeric characters
**Validates: Requirements 2.1**

Property 7: Subdirectory naming pattern compliance
*For any* subdirectory in the nested structure, the name should follow the "level-X-YYYYYYYY" pattern where X matches the level number and YYYYYYYY is exactly 8 alphanumeric characters
**Validates: Requirements 2.2**

Property 8: Filename uniqueness within levels
*For any* directory level in the nested structure, all filenames within that level should be unique
**Validates: Requirements 2.3**

Property 9: Character set diversity
*For any* collection of randomly generated strings, the character set should include uppercase letters, lowercase letters, and digits across multiple generations
**Validates: Requirements 2.5**

Property 10: Legacy file count preservation
*For any* execution of the enhanced utility, exactly 12 legacy files should be generated per bucket using the original generation logic
**Validates: Requirements 3.1**

Property 11: Legacy filename pattern preservation
*For any* legacy file generated by the enhanced utility, the filename should follow the original "test-XXXXXX.html" pattern
**Validates: Requirements 3.2**

Property 12: Legacy directory structure preservation
*For any* set of legacy files generated by the enhanced utility, they should be distributed across directory depths 1-4 levels as in the original implementation
**Validates: Requirements 3.3**

Property 13: Total file count per bucket
*For any* bucket processed by the enhanced utility, exactly 62 files should be uploaded (12 legacy + 50 nested structure files)
**Validates: Requirements 3.4**

Property 14: Multi-stage file distribution
*For any* stage processed by the enhanced utility, the complete set of 62 files should be uploaded to that stage's base path
**Validates: Requirements 3.5**

Property 15: Retry behavior consistency
*For any* failed S3 upload operation (legacy or nested), the same exponential backoff retry logic should be applied
**Validates: Requirements 4.1**

Property 16: Path length validation
*For any* generated S3 path in the nested structure, the total path length should be validated against S3 key length limitations before upload attempts
**Validates: Requirements 4.2**

Property 17: Error isolation between file types
*For any* failure during nested structure creation, legacy file processing and other bucket processing should continue unaffected
**Validates: Requirements 4.4**

Property 18: Nested structure logging completeness
*For any* nested structure creation, the root directory name and structure overview should be logged
**Validates: Requirements 5.1**

Property 19: Directory level progress logging
*For any* nested structure upload process, progress should be logged at each directory level
**Validates: Requirements 5.2**

Property 20: Verbose mode nested file logging
*For any* execution with verbose mode enabled, detailed paths should be logged for all nested structure files
**Validates: Requirements 5.3**

Property 21: File type count reporting
*For any* completed operation, the summary should report separate counts for legacy files and nested structure files
**Validates: Requirements 5.4**

Property 22: Total count summary accuracy
*For any* completed operation, the final summary should show exactly 62 files per bucket with correct breakdown by type (12 legacy + 50 nested)
**Validates: Requirements 5.5**