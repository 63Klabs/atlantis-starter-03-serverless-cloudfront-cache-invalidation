#!/usr/bin/env python3
"""
Test File Upload Utility

Uploads test HTML files to S3 buckets with diverse naming patterns and directory structures.
Designed to test CloudFront invalidation capabilities by creating files that trigger
different consolidation behaviors in the invalidation system.

Supports both local development and CI/CD environments.
"""
import argparse
import logging
import sys
import os
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
import boto3
import json
import random
import string
import time


@dataclass
class Configuration:
    """Configuration data for the upload utility"""
    buckets: List[str]
    stages: List[str]
    aws_profile: Optional[str]
    verbose: bool
    base_path: str
    source_file_path: str
    origin_path_pattern: str = '/{stageId}/public'


@dataclass
class UploadTask:
    """Represents a single file upload task"""
    bucket: str
    key: str
    content: str
    filename: str  # Original filename for logging


@dataclass
class UploadResult:
    """Results from uploading to a bucket"""
    bucket: str
    successful_uploads: int
    failed_uploads: int
    upload_paths: List[str]


@dataclass
class EnhancedUploadResult:
    """Enhanced results from uploading to a bucket with file type breakdown"""
    bucket: str
    successful_uploads: int
    failed_uploads: int
    upload_paths: List[str]
    legacy_file_count: int  # Count of legacy files (12)
    nested_file_count: int  # Count of nested structure files (50)
    root_directory: str     # Name of the nested structure root directory


@dataclass
class DirectoryLevel:
    """Represents a single directory level in the nested structure"""
    level_number: int  # 1-5
    directory_path: str
    files: List[str]  # 10 filenames
    subdirectory: Optional[str]  # None for level 5


@dataclass
class NestedStructureInfo:
    """Information about the generated nested directory structure"""
    root_directory: str
    levels: List[DirectoryLevel]
    total_files: int  # Should always be 50
    total_directories: int  # Should always be 4 (levels 1-4 have subdirs)


class ArgumentParser:
    """Handles command line argument parsing and validation"""
    
    def __init__(self):
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """Create and configure the argument parser"""
        parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        
        parser.add_argument(
            '--buckets',
            type=str,
            help='Comma-delimited list of S3 bucket names to upload test files to'
        )
        
        parser.add_argument(
            '--stages',
            type=str,
            default='prod',
            help='Comma-delimited list of stages (determines base path: /prod/public/ or /stage/public/)'
        )
        
        parser.add_argument(
            '--profile',
            type=str,
            help='AWS profile to use for authentication (required for local development)'
        )
        
        parser.add_argument(
            '-v', '--verbose',
            action='store_true',
            help='Enable verbose logging with detailed AWS and bucket information'
        )
        
        parser.add_argument(
            '--origin_path',
            type=str,
            default='/{stageId}/public',
            help=(
                'Origin path pattern for S3 uploads (default: /{stageId}/public). '
                'Must start with "/". Can include {stageId} placeholder for dynamic substitution. '
                'Examples: /app/{stageId}, /static, /{stageId}/public'
            )
        )
        
        return parser
    
    def parse_args(self, args: Optional[List[str]] = None) -> argparse.Namespace:
        """Parse command line arguments with validation"""
        parsed_args = self.parser.parse_args(args)
        self._validate_args(parsed_args)
        return parsed_args
    
    def _validate_args(self, args: argparse.Namespace) -> None:
        """Validate argument combinations and requirements"""
        # Validate origin_path format
        if not args.origin_path.startswith('/'):
            raise ValueError(
                "Origin path must start with '/'. "
                f"Invalid value: '{args.origin_path}'. "
                "Examples: /app/{{stageId}}, /static, /{{stageId}}/public"
            )
        
        # Bucket validation will be handled by EnvironmentManager
        # since it needs to check environment variables
        pass


class EnvironmentManager:
    """Manages environment configuration and AWS credentials"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_target_buckets(self, buckets_arg: Optional[str]) -> List[str]:
        """
        Resolve bucket list from arguments or environment variables
        
        Args:
            buckets_arg: Comma-delimited bucket string from --buckets argument
            
        Returns:
            List of bucket names
            
        Raises:
            ValueError: If no buckets specified and no environment variable found
        """
        if buckets_arg:
            # Parse comma-delimited bucket list
            buckets = [bucket.strip() for bucket in buckets_arg.split(',')]
            buckets = [bucket for bucket in buckets if bucket]  # Remove empty strings
            if not buckets:
                raise ValueError("Invalid bucket list: no valid bucket names found")
            return buckets
        
        # Try environment variable
        env_bucket = os.environ.get('S3_STATIC_HOST_BUCKET')
        if env_bucket:
            return [env_bucket.strip()]
        
        # No buckets specified
        raise ValueError(
            "No buckets specified. Use --buckets parameter or set S3_STATIC_HOST_BUCKET environment variable."
        )

    def get_target_stages(self, stages_arg: str) -> List[str]:
        """
        Resolve stage list from arguments

        Args:
            stages_arg: Comma-delimited stage string from --stages argument

        Returns:
            List of stage names
        """
        stages = [stage.strip() for stage in stages_arg.split(',') if stage.strip()]
        return stages if stages else ['prod']  # Default to prod if no valid stages
    
    def setup_aws_session(self, profile: Optional[str]) -> boto3.Session:
        """
        Setup AWS session with optional profile support
        
        Args:
            profile: AWS profile name (None for default)
            
        Returns:
            Configured boto3 session
        """
        if profile:
            os.environ['AWS_PROFILE'] = profile
            self.logger.info(f"Using AWS profile: {profile}")
            return boto3.Session(profile_name=profile)
        else:
            self.logger.info("Using default AWS profile (CI/CD mode)")
            return boto3.Session()
    
    def determine_base_path(self, stage: str, origin_path_pattern: str = '/{stageId}/public') -> str:
        """
        Determine S3 base path based on stage and origin path pattern
        
        Args:
            stage: Target stage name
            origin_path_pattern: Origin path pattern with optional {stageId} placeholder
            
        Returns:
            Base S3 path for uploads (always starts and ends with '/')
            
        Examples:
            >>> determine_base_path('prod', '/{stageId}/public')
            '/prod/public/'
            
            >>> determine_base_path('prod', '/app/{stageId}')
            '/app/prod/'
            
            >>> determine_base_path('prod', '/static')
            '/static/'
            
            >>> determine_base_path('prod', '/{stageId}')
            '/prod/'
        """
        # Replace {stageId} placeholder with actual stage value
        base_path = origin_path_pattern.replace('{stageId}', stage)
        
        # Ensure path starts with '/'
        if not base_path.startswith('/'):
            base_path = '/' + base_path
        
        # Ensure path ends with '/'
        if not base_path.endswith('/'):
            base_path = base_path + '/'
        
        return base_path

class FileGenerator:
    """Generates test file content and random naming"""
    
    def __init__(self, config: Configuration):
        """
        Initialize FileGenerator with configuration
        
        Args:
            config: Configuration object containing source file path
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._source_content = None
    
    def get_source_content(self) -> str:
        """
        Read and return the source test.html file content
        
        Returns:
            Content of the source HTML file
            
        Raises:
            FileNotFoundError: If source file doesn't exist
            IOError: If file cannot be read
        """
        if self._source_content is None:
            source_path = Path(self.config.source_file_path)
            
            if not source_path.exists():
                raise FileNotFoundError(f"Source file not found: {source_path}")
            
            try:
                with open(source_path, 'r', encoding='utf-8') as f:
                    self._source_content = f.read()
                self.logger.debug(f"Loaded source file: {source_path}")
            except IOError as e:
                raise IOError(f"Failed to read source file {source_path}: {e}")
        
        return self._source_content
    
    def generate_random_filename(self) -> str:
        """
        Generate a random filename following the test-*.html pattern
        
        Returns:
            Filename with 6 random alphanumeric characters (e.g., "test-A1b2C3.html")
        """
        # Generate 6 random alphanumeric characters
        random_chars = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        return f"test-{random_chars}.html"


class NestedStructureGenerator:
    """Generates complex nested directory structures for testing"""
    
    def __init__(self):
        """Initialize NestedStructureGenerator"""
        self.logger = logging.getLogger(__name__)
    
    def generate_root_directory_name(self) -> str:
        """
        Generate a randomly named root directory with 8 alphanumeric characters
        
        Returns:
            Root directory name (8 random alphanumeric characters)
        """
        # Generate 8 random alphanumeric characters (uppercase, lowercase, digits)
        random_chars = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        return random_chars
    
    def generate_subdirectory_name(self, level: int) -> str:
        """
        Generate a subdirectory name following "level-X-YYYYYYYY" pattern
        
        Args:
            level: Directory level number (1-4)
            
        Returns:
            Subdirectory name following "level-X-YYYYYYYY" pattern
        """
        if not (1 <= level <= 4):
            raise ValueError(f"Level must be between 1 and 4, got {level}")
        
        # Generate 8 random alphanumeric characters (uppercase, lowercase, digits)
        random_chars = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        return f"level-{level}-{random_chars}"
    
    def generate_nested_filename(self) -> str:
        """
        Generate a nested filename following "nested-XXXXXX.html" pattern
        
        Returns:
            Filename following "nested-XXXXXX.html" pattern where XXXXXX is 6 random alphanumeric characters
        """
        # Generate 6 random alphanumeric characters (uppercase, lowercase, digits)
        random_chars = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        return f"nested-{random_chars}.html"
    
    def generate_nested_structure(self, base_path: str) -> Tuple[List[Tuple[str, str]], NestedStructureInfo]:
        """
        Generate a complete 5-level deep nested directory structure with files at each level
        
        Args:
            base_path: Base S3 path (e.g., "/stage/public/")
            
        Returns:
            Tuple containing:
            - List of tuples (s3_key, filename) where:
              - s3_key is the full S3 path WITHOUT leading slash (S3 standard format)
              - filename is the original filename for logging
              Total of 50 files (10 files per level × 5 levels)
            - NestedStructureInfo object with structure details
        """
        paths = []
        levels = []
        
        # Remove leading slash from base_path to generate S3-compliant keys
        clean_base = base_path.strip('/')
        
        # Generate root directory name
        root_dir = self.generate_root_directory_name()
        
        # Build the nested structure level by level
        current_path = f"{clean_base}/{root_dir}" if clean_base else root_dir
        
        for level in range(1, 6):  # Levels 1-5
            # Generate 10 files at this level
            level_filenames = set()  # Track filenames to ensure uniqueness
            level_files = []
            
            for _ in range(10):
                # Generate unique filename for this level
                attempt = 0
                while attempt < 100:  # Prevent infinite loop
                    filename = self.generate_nested_filename()
                    if filename not in level_filenames:
                        level_filenames.add(filename)
                        break
                    attempt += 1
                
                if attempt >= 100:
                    raise RuntimeError(f"Could not generate unique filename at level {level} after 100 attempts")
                
                level_files.append(filename)
                
                # Create full S3 path without leading slash
                s3_key = f"{current_path}/{filename}"
                paths.append((s3_key, filename))
            
            # Create subdirectory for next level (except at level 5)
            subdirectory = None
            if level < 5:
                subdir_name = self.generate_subdirectory_name(level)
                subdirectory = subdir_name
                current_path = f"{current_path}/{subdir_name}"
            
            # Create DirectoryLevel object
            directory_level = DirectoryLevel(
                level_number=level,
                directory_path=current_path if level < 5 else current_path.rsplit('/', 1)[0],
                files=level_files,
                subdirectory=subdirectory
            )
            levels.append(directory_level)
        
        # Create NestedStructureInfo
        structure_info = NestedStructureInfo(
            root_directory=root_dir,
            levels=levels,
            total_files=len(paths),  # Should be 50
            total_directories=sum(1 for level in levels if level.subdirectory is not None)  # Should be 4
        )
        
        self.logger.debug(f"Generated nested structure with {len(paths)} files in root directory: {root_dir}")
        return paths, structure_info


class PathGenerator:
    """Creates diverse S3 path structures for testing"""
    
    def __init__(self, config: Configuration):
        """
        Initialize PathGenerator with configuration
        
        Args:
            config: Configuration object containing base path
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.nested_generator = NestedStructureGenerator()
    
    def generate_all_upload_paths(self, base_path: str) -> List[Tuple[str, str]]:
        """
        Generate combined legacy and nested structure paths for comprehensive testing
        
        Args:
            base_path: Base S3 path (e.g., "/stage/public/")
            
        Returns:
            List of tuples (s3_key, filename) where:
            - s3_key is the full S3 path including base_path
            - filename is the original filename for logging
            Total of 62 files (12 legacy + 50 nested structure files)
        """
        # Generate legacy paths (12 files)
        legacy_paths = self.generate_upload_paths(base_path, 12)
        
        # Generate nested structure paths (50 files)
        nested_paths, _ = self.nested_generator.generate_nested_structure(base_path)
        
        # Combine and return (62 total files)
        all_paths = legacy_paths + nested_paths
        
        self.logger.debug(f"Generated {len(all_paths)} total upload paths: {len(legacy_paths)} legacy + {len(nested_paths)} nested")
        return all_paths
    
    def generate_all_upload_paths_with_info(self, base_path: str) -> Tuple[List[Tuple[str, str]], NestedStructureInfo]:
        """
        Generate combined legacy and nested structure paths with structure information
        
        Args:
            base_path: Base S3 path (e.g., "/stage/public/")
            
        Returns:
            Tuple containing:
            - List of tuples (s3_key, filename) where:
              - s3_key is the full S3 path including base_path
              - filename is the original filename for logging
              Total of 62 files (12 legacy + 50 nested structure files)
            - NestedStructureInfo object with nested structure details
        """
        # Generate legacy paths (12 files)
        legacy_paths = self.generate_upload_paths(base_path, 12)
        
        # Generate nested structure paths (50 files)
        nested_paths, structure_info = self.nested_generator.generate_nested_structure(base_path)
        
        # Combine and return (62 total files)
        all_paths = legacy_paths + nested_paths
        
        self.logger.debug(f"Generated {len(all_paths)} total upload paths: {len(legacy_paths)} legacy + {len(nested_paths)} nested")
        return all_paths, structure_info
    
    def generate_upload_paths(self, base_path: str, count: int = 12) -> List[Tuple[str, str]]:
        """
        Generate diverse S3 paths for testing consolidation behaviors
        
        Args:
            base_path: Base S3 path (e.g., "/stage/public/")
            count: Number of paths to generate (default: 12)
            
        Returns:
            List of tuples (s3_key, filename) where:
            - s3_key is the full S3 path WITHOUT leading slash (S3 standard format)
            - filename is the original filename for logging
        """
        if count != 12:
            raise ValueError("Path generator must create exactly 12 files per bucket")
        
        paths = []
        used_paths = set()
        
        # Remove leading slash from base_path to generate S3-compliant keys
        clean_base = base_path.strip('/')
        
        # Ensure we have files at different directory depths (1-4 levels)
        # Use deterministic approach to guarantee all depths are covered
        depth_requirements = [1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4]  # Exactly 3 files at each depth
        
        # Special filenames to include
        special_filenames = ['index.html', 'default.html']
        special_used = 0
        
        # Directory name pools for each level
        level_0_dirs = ['assets', 'content', 'pages', 'static']
        level_1_dirs = ['css', 'js', 'images', 'fonts', 'data']
        level_2_dirs = ['level2_a', 'level2_b', 'level2_c']
        level_3_dirs = ['level3_a', 'level3_b', 'level3_c']
        
        for i, depth in enumerate(depth_requirements):
            # Generate directory structure deterministically
            dirs = []
            
            # Use index to create variety while ensuring deterministic behavior
            dir_index_base = i % 10  # Use file index for variety
            
            for level in range(depth):
                if level == 0:
                    dir_name = level_0_dirs[dir_index_base % len(level_0_dirs)]
                elif level == 1:
                    dir_name = level_1_dirs[(dir_index_base + level) % len(level_1_dirs)]
                elif level == 2:
                    dir_name = level_2_dirs[(dir_index_base + level) % len(level_2_dirs)]
                else:  # level == 3
                    dir_name = level_3_dirs[(dir_index_base + level) % len(level_3_dirs)]
                dirs.append(dir_name)
            
            # Choose filename type
            if special_used < len(special_filenames) and i % 4 == 0:
                # Use special filename deterministically
                filename = special_filenames[special_used]
                special_used += 1
            else:
                # Use random filename
                filename = self._generate_random_filename()
            
            # Construct full path without leading slash (S3 standard format)
            if depth == 1:
                # For depth 1, only one directory level
                s3_key = f"{clean_base}/{dirs[0]}/{filename}" if clean_base else f"{dirs[0]}/{filename}"
            else:
                # For deeper levels, use all directories
                dir_path = '/'.join(dirs)
                s3_key = f"{clean_base}/{dir_path}/{filename}" if clean_base else f"{dir_path}/{filename}"
            
            # Ensure uniqueness
            attempt = 0
            original_filename = filename
            while s3_key in used_paths and attempt < 10:
                # Retry with different filename
                retry_filename = self._generate_random_filename()
                if depth == 1:
                    s3_key = f"{clean_base}/{dirs[0]}/{retry_filename}" if clean_base else f"{dirs[0]}/{retry_filename}"
                else:
                    dir_path = '/'.join(dirs)
                    s3_key = f"{clean_base}/{dir_path}/{retry_filename}" if clean_base else f"{dir_path}/{retry_filename}"
                filename = retry_filename
                attempt += 1
            
            if s3_key not in used_paths:
                paths.append((s3_key, filename))
                used_paths.add(s3_key)
        
        self.logger.debug(f"Generated {len(paths)} upload paths")
        return paths[:12]  # Ensure exactly 12 paths
    
    def _generate_random_filename(self) -> str:
        """Generate a random filename for internal use"""
        random_chars = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        return f"test-{random_chars}.html"


class Logger:
    """Provides structured logging and progress feedback for upload operations"""
    
    def __init__(self, config: Configuration):
        """
        Initialize Logger with configuration
        
        Args:
            config: Configuration object containing verbose flag and other settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def log_startup(self, buckets: List[str], source_file_path: str) -> None:
        """
        Log startup information including source file and bucket list
        
        Args:
            buckets: List of target bucket names
            source_file_path: Path to the source HTML file
        """
        self.logger.info("=== Test File Upload Utility ===")
        self.logger.info(f"Source file: {source_file_path}")
        self.logger.info(f"Target buckets: {', '.join(buckets)}")
        self.logger.info(f"Target stages: {', '.join(self.config.stages)}")
        self.logger.info(f"Origin path pattern: {self.config.origin_path_pattern}")
        self.logger.info(f"Base path: {self.config.base_path}")
        
        if self.config.verbose:
            self.logger.info(f"AWS profile: {self.config.aws_profile or 'default'}")
            self.logger.info(f"Verbose mode: enabled")
    
    def log_bucket_validation(self, bucket: str, success: bool, error: Optional[str] = None) -> None:
        """
        Log bucket validation results
        
        Args:
            bucket: Bucket name being validated
            success: Whether validation succeeded
            error: Error message if validation failed
        """
        if success:
            if self.config.verbose:
                self.logger.info(f"Bucket validation successful: {bucket}")
        else:
            self.logger.error(f"Bucket validation failed for {bucket}: {error}")
    
    def log_upload_success(self, bucket: str, key: str) -> None:
        """
        Log successful file upload
        
        Args:
            bucket: S3 bucket name
            key: S3 object key (full path)
        """
        clean_key = key.lstrip('/')
        s3_path = f"s3://{bucket}/{clean_key}"
        self.logger.info(f"Uploaded: {s3_path}")
        
        if self.config.verbose:
            self.logger.debug(f"Upload details - Bucket: {bucket}, Key: {clean_key}")
    
    def log_upload_failure(self, bucket: str, key: str, error: str, attempt: Optional[int] = None) -> None:
        """
        Log failed file upload
        
        Args:
            bucket: S3 bucket name
            key: S3 object key (full path)
            error: Error message
            attempt: Retry attempt number (None for final failure)
        """
        clean_key = key.lstrip('/')
        s3_path = f"s3://{bucket}/{clean_key}"
        
        if attempt is not None:
            self.logger.warning(f"Upload attempt {attempt} failed for {s3_path}: {error}")
        else:
            self.logger.error(f"Upload failed for {s3_path}: {error}")
    
    def log_retry_info(self, bucket: str, key: str, attempt: int, max_retries: int, delay: int) -> None:
        """
        Log retry attempt information
        
        Args:
            bucket: S3 bucket name
            key: S3 object key (full path)
            attempt: Current attempt number (1-based)
            max_retries: Maximum number of retries
            delay: Delay before next retry in seconds
        """
        clean_key = key.lstrip('/')
        s3_path = f"s3://{bucket}/{clean_key}"
        self.logger.info(f"Retrying {s3_path} in {delay} seconds... (attempt {attempt + 1}/{max_retries + 1})")
    
    def log_bucket_processing_start(self, bucket: str) -> None:
        """
        Log start of bucket processing
        
        Args:
            bucket: Bucket name being processed
        """
        self.logger.info(f"Processing bucket: {bucket}")
    
    def log_bucket_processing_complete(self, bucket: str, successful: int, failed: int) -> None:
        """
        Log completion of bucket processing
        
        Args:
            bucket: Bucket name that was processed
            successful: Number of successful uploads
            failed: Number of failed uploads
        """
        self.logger.info(f"Bucket {bucket} completed: {successful} successful, {failed} failed")
    
    def log_summary(self, results: Dict[str, UploadResult]) -> None:
        """
        Log summary of all upload operations
        
        Args:
            results: Dictionary mapping bucket names to UploadResult objects
        """
        self.logger.info("\n=== Upload Summary ===")
        
        total_successful = 0
        total_failed = 0
        
        for bucket, result in results.items():
            total_successful += result.successful_uploads
            total_failed += result.failed_uploads
            
            self.logger.info(f"{bucket}: {result.successful_uploads} successful, {result.failed_uploads} failed")
            
            if self.config.verbose and result.upload_paths:
                self.logger.info(f"  Uploaded paths:")
                for path in result.upload_paths:
                    clean_path = path.lstrip('/')
                    self.logger.info(f"    s3://{bucket}/{clean_path}")
        
        self.logger.info(f"\nTotal: {total_successful} successful, {total_failed} failed uploads")
        
        if total_failed > 0:
            self.logger.error(f"\n{total_failed} uploads failed. Check bucket permissions and network connectivity.")
            self.logger.error("Retry suggestions:")
            self.logger.error("  - Verify AWS credentials and permissions")
            self.logger.error("  - Check bucket names and existence")
            self.logger.error("  - Ensure network connectivity to AWS")
    
    def log_enhanced_summary(self, results: Dict[str, 'EnhancedUploadResult']) -> None:
        """
        Log enhanced summary of all upload operations with file type breakdown
        
        Args:
            results: Dictionary mapping bucket names to EnhancedUploadResult objects
        """
        self.logger.info("\n=== Enhanced Upload Summary ===")
        
        total_successful = 0
        total_failed = 0
        total_legacy_files = 0
        total_nested_files = 0
        
        for bucket, result in results.items():
            total_successful += result.successful_uploads
            total_failed += result.failed_uploads
            total_legacy_files += result.legacy_file_count
            total_nested_files += result.nested_file_count
            
            # Basic bucket summary
            self.logger.info(f"{bucket}: {result.successful_uploads} successful, {result.failed_uploads} failed")
            
            # File type breakdown
            self.logger.info(f"  Legacy files: {result.legacy_file_count}")
            self.logger.info(f"  Nested structure files: {result.nested_file_count}")
            self.logger.info(f"  Root directory: {result.root_directory}")
            
            if self.config.verbose and result.upload_paths:
                self.logger.info(f"  Uploaded paths:")
                for path in result.upload_paths:
                    clean_path = path.lstrip('/')
                    self.logger.info(f"    s3://{bucket}/{clean_path}")
        
        # Enhanced total summary with file type breakdown
        total_files = total_legacy_files + total_nested_files
        self.logger.info(f"\nTotal: {total_successful} successful, {total_failed} failed uploads")
        self.logger.info(f"File breakdown: {total_legacy_files} legacy + {total_nested_files} nested = {total_files} total files per bucket")
        
        if total_failed > 0:
            self.logger.error(f"\n{total_failed} uploads failed. Check bucket permissions and network connectivity.")
            self.logger.error("Retry suggestions:")
            self.logger.error("  - Verify AWS credentials and permissions")
            self.logger.error("  - Check bucket names and existence")
            self.logger.error("  - Ensure network connectivity to AWS")
    
    def log_nested_structure_start(self, root_dir: str) -> None:
        """
        Log the start of nested structure creation with root directory and overview
        
        Args:
            root_dir: Name of the root directory being created
        """
        self.logger.info(f"Creating nested structure in root directory: {root_dir}")
        self.logger.info("Structure: 5 levels deep, 10 files per level, 50 total files")
        
        if self.config.verbose:
            self.logger.info("Nested structure pattern:")
            self.logger.info("  Level 1: 10 files + 1 subdirectory")
            self.logger.info("  Level 2: 10 files + 1 subdirectory") 
            self.logger.info("  Level 3: 10 files + 1 subdirectory")
            self.logger.info("  Level 4: 10 files + 1 subdirectory")
            self.logger.info("  Level 5: 10 files (no subdirectory)")
    
    def log_level_progress(self, level: int, files_count: int) -> None:
        """
        Log progress for directory level creation
        
        Args:
            level: Directory level number (1-5)
            files_count: Number of files created at this level
        """
        self.logger.info(f"Level {level}: Created {files_count} files")
        
        if self.config.verbose:
            if level < 5:
                self.logger.debug(f"Level {level}: Also created 1 subdirectory for next level")
            else:
                self.logger.debug(f"Level {level}: Final level, no subdirectory created")
    
    def log_error_with_guidance(self, error_message: str, suggestions: List[str]) -> None:
        """
        Log error message with actionable guidance
        
        Args:
            error_message: Main error message
            suggestions: List of actionable suggestions for resolution
        """
        self.logger.error(error_message)
        if suggestions:
            self.logger.error("Suggestions:")
            for suggestion in suggestions:
                self.logger.error(f"  - {suggestion}")


class S3Uploader:
    """Handles S3 upload operations with error handling and retry logic"""
    
    # S3 key length limit (1024 characters)
    MAX_S3_KEY_LENGTH = 1024
    
    def __init__(self, session: boto3.Session, config: Configuration, logger: Logger):
        """
        Initialize S3Uploader with AWS session, configuration, and logger
        
        Args:
            session: Configured boto3 session
            config: Configuration object
            logger: Logger instance for structured logging
        """
        self.session = session
        self.config = config
        self.logger_component = logger
        self.s3_client = session.client('s3')
        self.logger = logging.getLogger(__name__)
    
    def validate_bucket_exists(self, bucket: str) -> bool:
        """
        Validate that a bucket exists and is accessible
        
        Args:
            bucket: S3 bucket name
            
        Returns:
            True if bucket exists and is accessible, False otherwise
        """
        try:
            self.s3_client.head_bucket(Bucket=bucket)
            self.logger_component.log_bucket_validation(bucket, True)
            return True
        except Exception as e:
            self.logger_component.log_bucket_validation(bucket, False, str(e))
            return False
    
    def validate_s3_key_length(self, key: str) -> bool:
        """
        Validate that an S3 key does not exceed the maximum length limit
        
        Args:
            key: S3 object key (path)
            
        Returns:
            True if key length is valid, False otherwise
        """
        clean_key = key.lstrip('/')
        key_length = len(clean_key)
        
        if key_length > self.MAX_S3_KEY_LENGTH:
            self.logger.error(
                f"S3 key length exceeds limit: {key_length} > {self.MAX_S3_KEY_LENGTH} characters. "
                f"Key: {clean_key[:100]}{'...' if key_length > 100 else ''}"
            )
            return False
        
        return True
    
    def upload_file(self, bucket: str, key: str, content: str) -> bool:
        """
        Upload a single file to S3
        
        Args:
            bucket: S3 bucket name
            key: S3 object key (path) - will be stripped of leading slashes
            content: File content to upload
            
        Returns:
            True if upload successful, False otherwise
        """
        try:
            # Validate S3 key length before upload attempt
            if not self.validate_s3_key_length(key):
                self.logger_component.log_upload_failure(
                    bucket, key, 
                    f"S3 key length exceeds {self.MAX_S3_KEY_LENGTH} character limit"
                )
                return False
            
            # Remove leading slash from key if present (S3 standard format)
            clean_key = key.lstrip('/')
            
            # Validate that key doesn't start with slash after cleaning
            if clean_key != key:
                self.logger.debug(f"Stripped leading slash from key: {key} -> {clean_key}")
            
            # Additional validation: ensure clean_key doesn't start with slash
            if clean_key.startswith('/'):
                self.logger.error(f"Key still has leading slash after stripping: {clean_key}")
                return False
            
            self.s3_client.put_object(
                Bucket=bucket,
                Key=clean_key,
                Body=content.encode('utf-8'),
                ContentType='text/html'
            )
            
            # Log with actual S3 key format (no leading slash)
            self.logger.debug(f"Uploaded to S3 with key: {clean_key}")
            self.logger_component.log_upload_success(bucket, clean_key)
            return True
            
        except Exception as e:
            self.logger_component.log_upload_failure(bucket, key, str(e))
            return False
    
    def upload_with_retry(self, bucket: str, key: str, content: str, max_retries: int = 3) -> bool:
        """
        Upload a file to S3 with retry logic and exponential backoff
        
        Args:
            bucket: S3 bucket name
            key: S3 object key (path) - will be stripped of leading slashes
            content: File content to upload
            max_retries: Maximum number of retry attempts (default: 3)
            
        Returns:
            True if upload successful, False if all retries failed
        """
        # Validate S3 key length before any upload attempts
        if not self.validate_s3_key_length(key):
            self.logger_component.log_upload_failure(
                bucket, key, 
                f"S3 key length exceeds {self.MAX_S3_KEY_LENGTH} character limit"
            )
            return False
        
        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                # Remove leading slash from key if present (S3 standard format)
                clean_key = key.lstrip('/')
                
                # Validate that key doesn't start with slash after cleaning
                if clean_key.startswith('/'):
                    self.logger.error(f"Key still has leading slash after stripping: {clean_key}")
                    return False
                
                self.s3_client.put_object(
                    Bucket=bucket,
                    Key=clean_key,
                    Body=content.encode('utf-8'),
                    ContentType='text/html'
                )
                
                if attempt > 0:
                    self.logger.info(f"Upload successful on retry {attempt}: s3://{bucket}/{clean_key}")
                else:
                    # Log with actual S3 key format (no leading slash)
                    self.logger.debug(f"Uploaded to S3 with key: {clean_key}")
                    self.logger_component.log_upload_success(bucket, clean_key)
                return True
                
            except Exception as e:
                if attempt < max_retries:
                    # Calculate exponential backoff delay: 2^attempt seconds
                    delay = 2 ** attempt
                    self.logger_component.log_upload_failure(bucket, key, str(e), attempt + 1)
                    self.logger_component.log_retry_info(bucket, key, attempt, max_retries, delay)
                    time.sleep(delay)
                else:
                    self.logger_component.log_upload_failure(bucket, key, str(e))
                    return False
        
        return False
    
    def execute_upload_tasks(self, tasks: List[UploadTask]) -> Dict[str, UploadResult]:
        """
        Execute a list of upload tasks, handling errors per bucket
        
        Args:
            tasks: List of UploadTask objects to execute
            
        Returns:
            Dictionary mapping bucket names to UploadResult objects
        """
        results = {}
        
        # Group tasks by bucket
        tasks_by_bucket = {}
        for task in tasks:
            if task.bucket not in tasks_by_bucket:
                tasks_by_bucket[task.bucket] = []
            tasks_by_bucket[task.bucket].append(task)
        
        # Process each bucket
        for bucket, bucket_tasks in tasks_by_bucket.items():
            self.logger_component.log_bucket_processing_start(bucket)
            
            # Validate bucket exists
            if not self.validate_bucket_exists(bucket):
                self.logger.error(f"Skipping bucket {bucket} - validation failed")
                results[bucket] = UploadResult(
                    bucket=bucket,
                    successful_uploads=0,
                    failed_uploads=len(bucket_tasks),
                    upload_paths=[]
                )
                continue
            
            # Execute uploads for this bucket
            successful_uploads = 0
            failed_uploads = 0
            upload_paths = []
            
            for task in bucket_tasks:
                if self.upload_with_retry(task.bucket, task.key, task.content):
                    successful_uploads += 1
                    upload_paths.append(task.key)
                else:
                    failed_uploads += 1
            
            results[bucket] = UploadResult(
                bucket=bucket,
                successful_uploads=successful_uploads,
                failed_uploads=failed_uploads,
                upload_paths=upload_paths
            )
            
            self.logger_component.log_bucket_processing_complete(bucket, successful_uploads, failed_uploads)
        
        return results
    
    def execute_enhanced_upload_tasks(self, tasks: List[UploadTask], structure_info: NestedStructureInfo) -> Dict[str, EnhancedUploadResult]:
        """
        Execute a list of upload tasks with enhanced tracking, handling errors per bucket
        
        Args:
            tasks: List of UploadTask objects to execute
            structure_info: NestedStructureInfo object with nested structure details
            
        Returns:
            Dictionary mapping bucket names to EnhancedUploadResult objects
        """
        results = {}
        
        # Group tasks by bucket
        tasks_by_bucket = {}
        for task in tasks:
            if task.bucket not in tasks_by_bucket:
                tasks_by_bucket[task.bucket] = []
            tasks_by_bucket[task.bucket].append(task)
        
        # Process each bucket
        for bucket, bucket_tasks in tasks_by_bucket.items():
            self.logger_component.log_bucket_processing_start(bucket)
            
            # Validate bucket exists
            if not self.validate_bucket_exists(bucket):
                self.logger.error(f"Skipping bucket {bucket} - validation failed")
                results[bucket] = EnhancedUploadResult(
                    bucket=bucket,
                    successful_uploads=0,
                    failed_uploads=len(bucket_tasks),
                    upload_paths=[],
                    legacy_file_count=0,
                    nested_file_count=0,
                    root_directory=structure_info.root_directory
                )
                continue
            
            # Separate legacy and nested file tasks for error isolation
            legacy_tasks = []
            nested_tasks = []
            
            for task in bucket_tasks:
                if task.filename.startswith('nested-'):
                    nested_tasks.append(task)
                else:
                    legacy_tasks.append(task)
            
            # Process legacy files first (maintain backward compatibility)
            legacy_successful = 0
            legacy_failed = 0
            legacy_paths = []
            
            self.logger.info(f"Processing {len(legacy_tasks)} legacy files for bucket {bucket}")
            
            for task in legacy_tasks:
                try:
                    if self.upload_with_retry(task.bucket, task.key, task.content):
                        legacy_successful += 1
                        legacy_paths.append(task.key)
                    else:
                        legacy_failed += 1
                        self.logger.warning(f"Legacy file upload failed: {task.filename}")
                except Exception as e:
                    legacy_failed += 1
                    self.logger.error(f"Legacy file upload error for {task.filename}: {e}")
            
            # Process nested structure files separately (error isolation)
            nested_successful = 0
            nested_failed = 0
            nested_paths = []
            
            self.logger.info(f"Processing {len(nested_tasks)} nested structure files for bucket {bucket}")
            
            try:
                for task in nested_tasks:
                    try:
                        if self.upload_with_retry(task.bucket, task.key, task.content):
                            nested_successful += 1
                            nested_paths.append(task.key)
                        else:
                            nested_failed += 1
                            self.logger.warning(f"Nested structure file upload failed: {task.filename}")
                    except Exception as e:
                        nested_failed += 1
                        self.logger.error(f"Nested structure file upload error for {task.filename}: {e}")
            except Exception as e:
                # If nested structure processing fails completely, log but continue
                self.logger.error(f"Nested structure processing failed for bucket {bucket}: {e}")
                nested_failed = len(nested_tasks)
                nested_successful = 0
                nested_paths = []
            
            # Combine results
            total_successful = legacy_successful + nested_successful
            total_failed = legacy_failed + nested_failed
            all_paths = legacy_paths + nested_paths
            
            results[bucket] = EnhancedUploadResult(
                bucket=bucket,
                successful_uploads=total_successful,
                failed_uploads=total_failed,
                upload_paths=all_paths,
                legacy_file_count=len(legacy_tasks),
                nested_file_count=len(nested_tasks),
                root_directory=structure_info.root_directory
            )
            
            # Log detailed completion status with file type breakdown
            self.logger.info(f"Bucket {bucket} completed: {total_successful} successful, {total_failed} failed")
            self.logger.info(f"  Legacy files: {legacy_successful} successful, {legacy_failed} failed")
            self.logger.info(f"  Nested files: {nested_successful} successful, {nested_failed} failed")
            
            # Provide clear error reporting distinguishing between file types
            if legacy_failed > 0:
                self.logger.error(f"Legacy file processing had {legacy_failed} failures in bucket {bucket}")
            if nested_failed > 0:
                self.logger.error(f"Nested structure processing had {nested_failed} failures in bucket {bucket}")
        
        return results


def setup_console_logging(verbose: bool = False) -> logging.Logger:
    """Configure informative console logging"""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger(__name__)


def main():
    """Main script execution"""
    # Parse arguments
    arg_parser = ArgumentParser()
    args = arg_parser.parse_args()
    
    # Setup logging
    logger = setup_console_logging(args.verbose)
    
    try:
        # Setup environment manager
        env_manager = EnvironmentManager()
        
        # Get target buckets
        buckets = env_manager.get_target_buckets(args.buckets)
        
        # Setup AWS session
        session = env_manager.setup_aws_session(args.profile)
                
        # Get target stages
        stages = env_manager.get_target_stages(args.stages)
        
        # Create configuration
        source_file_path = Path(__file__).parent.parent.parent / "test.html"
        config = Configuration(
            buckets=buckets,
            stages=stages,
            aws_profile=args.profile,
            verbose=args.verbose,
            base_path="",  # Will be calculated per stage
            source_file_path=str(source_file_path),
            origin_path_pattern=args.origin_path
        )
        
        # Initialize Logger component
        logger_component = Logger(config)
        logger_component.log_startup(buckets, str(source_file_path))
        
        # Initialize components
        file_generator = FileGenerator(config)
        path_generator = PathGenerator(config)
        s3_uploader = S3Uploader(session, config, logger_component)
        
        # Generate upload tasks with enhanced tracking
        upload_tasks = []
        source_content = file_generator.get_source_content()
        structure_info = None
        
        for bucket in buckets:
            for stage in stages:
                base_path = env_manager.determine_base_path(stage, config.origin_path_pattern)
                
                # Log resolved base path in verbose mode
                if config.verbose:
                    logger.info(f"Resolved base path for {bucket}/{stage}: {base_path}")
                
                upload_paths, nested_info = path_generator.generate_all_upload_paths_with_info(base_path)
                
                # Store structure info for enhanced logging (same for all buckets/stages)
                if structure_info is None:
                    structure_info = nested_info
                    logger_component.log_nested_structure_start(nested_info.root_directory)
                
                for s3_key, filename in upload_paths:
                    task = UploadTask(
                        bucket=bucket,
                        key=s3_key,
                        content=source_content,
                        filename=filename
                    )
                    upload_tasks.append(task)
        
        # Execute uploads with enhanced tracking
        results = s3_uploader.execute_enhanced_upload_tasks(upload_tasks, structure_info)
        
        # Log enhanced summary
        logger_component.log_enhanced_summary(results)
        
        # Determine exit code
        total_failed = sum(result.failed_uploads for result in results.values())
        if total_failed > 0:
            logger.error(f"Upload completed with {total_failed} failures")
            sys.exit(1)
        else:
            logger.info("All uploads completed successfully!")
            sys.exit(0)
        
    except Exception as e:
        logger.error(f"Upload utility failed: {e}")
        if args.verbose:
            logger.exception("Full error details:")
        
        # Provide actionable guidance for common errors
        suggestions = []
        error_str = str(e).lower()
        
        if "no buckets specified" in error_str:
            suggestions.extend([
                "Use --buckets parameter with comma-delimited bucket names",
                "Set S3_STATIC_HOST_BUCKET environment variable",
                "Example: --buckets bucket1,bucket2,bucket3"
            ])
        elif "credentials" in error_str or "access" in error_str:
            suggestions.extend([
                "Verify AWS credentials are configured",
                "Use --profile parameter for local development",
                "Check IAM permissions for S3 access"
            ])
        elif "not found" in error_str and "test.html" in error_str:
            suggestions.extend([
                "Ensure test.html file exists in repository root",
                "Check file permissions and accessibility"
            ])
        else:
            suggestions.extend([
                "Check network connectivity to AWS",
                "Verify bucket names and permissions",
                "Run with --verbose flag for detailed information"
            ])
        
        if suggestions:
            logger_component = Logger(Configuration(
                buckets=[],
                stages=env_manager.get_target_stages(args.stages),
                aws_profile=args.profile,
                verbose=args.verbose,
                base_path="",
                source_file_path=""
            ))
            logger_component.log_error_with_guidance(f"Upload utility failed: {e}", suggestions)
        
        sys.exit(1)


if __name__ == "__main__":
    main()