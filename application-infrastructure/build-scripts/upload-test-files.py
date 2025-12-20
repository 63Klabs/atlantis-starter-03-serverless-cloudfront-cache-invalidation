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
        
        return parser
    
    def parse_args(self, args: Optional[List[str]] = None) -> argparse.Namespace:
        """Parse command line arguments with validation"""
        parsed_args = self.parser.parse_args(args)
        self._validate_args(parsed_args)
        return parsed_args
    
    def _validate_args(self, args: argparse.Namespace) -> None:
        """Validate argument combinations and requirements"""
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
        return [stage.strip() for stage in stages_arg.split(',') if stage]
    
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
    
    def determine_base_path(self, stage: str) -> str:
        """
        Determine S3 base path based on stage
        
        Args:
            stage: Target stage name
            
        Returns:
            Base S3 path for uploads
        """
        return f'/{stage}/public/'

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
    
    def generate_upload_paths(self, base_path: str, count: int = 12) -> List[Tuple[str, str]]:
        """
        Generate diverse S3 paths for testing consolidation behaviors
        
        Args:
            base_path: Base S3 path (e.g., "/stage/public/")
            count: Number of paths to generate (default: 12)
            
        Returns:
            List of tuples (s3_key, filename) where:
            - s3_key is the full S3 path including base_path
            - filename is the original filename for logging
        """
        if count != 12:
            raise ValueError("Path generator must create exactly 12 files per bucket")
        
        paths = []
        used_paths = set()
        
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
            
            # Construct full path
            if depth == 1:
                # For depth 1, only one directory level
                s3_key = f"{base_path.rstrip('/')}/{dirs[0]}/{filename}"
            else:
                # For deeper levels, use all directories
                dir_path = '/'.join(dirs)
                s3_key = f"{base_path.rstrip('/')}/{dir_path}/{filename}"
            
            # Ensure uniqueness
            attempt = 0
            original_filename = filename
            while s3_key in used_paths and attempt < 10:
                # Retry with different filename
                retry_filename = self._generate_random_filename()
                if depth == 1:
                    s3_key = f"{base_path.rstrip('/')}/{dirs[0]}/{retry_filename}"
                else:
                    dir_path = '/'.join(dirs)
                    s3_key = f"{base_path.rstrip('/')}/{dir_path}/{retry_filename}"
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
    
    def upload_file(self, bucket: str, key: str, content: str) -> bool:
        """
        Upload a single file to S3
        
        Args:
            bucket: S3 bucket name
            key: S3 object key (path)
            content: File content to upload
            
        Returns:
            True if upload successful, False otherwise
        """
        try:
            # Remove leading slash from key if present
            clean_key = key.lstrip('/')
            
            self.s3_client.put_object(
                Bucket=bucket,
                Key=clean_key,
                Body=content.encode('utf-8'),
                ContentType='text/html'
            )
            
            self.logger_component.log_upload_success(bucket, key)
            return True
            
        except Exception as e:
            self.logger_component.log_upload_failure(bucket, key, str(e))
            return False
    
    def upload_with_retry(self, bucket: str, key: str, content: str, max_retries: int = 3) -> bool:
        """
        Upload a file to S3 with retry logic and exponential backoff
        
        Args:
            bucket: S3 bucket name
            key: S3 object key (path)
            content: File content to upload
            max_retries: Maximum number of retry attempts (default: 3)
            
        Returns:
            True if upload successful, False if all retries failed
        """
        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                # Remove leading slash from key if present
                clean_key = key.lstrip('/')
                
                self.s3_client.put_object(
                    Bucket=bucket,
                    Key=clean_key,
                    Body=content.encode('utf-8'),
                    ContentType='text/html'
                )
                
                if attempt > 0:
                    self.logger.info(f"Upload successful on retry {attempt}: s3://{bucket}/{clean_key}")
                else:
                    self.logger_component.log_upload_success(bucket, key)
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
                
        # Create configuration
        source_file_path = Path(__file__).parent.parent.parent / "test.html"
        config = Configuration(
            buckets=buckets,
            aws_profile=args.profile,
            verbose=args.verbose,
            base_path=base_path,
            source_file_path=str(source_file_path)
        )
        
        # Initialize Logger component
        logger_component = Logger(config)
        logger_component.log_startup(buckets, str(source_file_path))
        
        # Initialize components
        file_generator = FileGenerator(config)
        path_generator = PathGenerator(config)
        s3_uploader = S3Uploader(session, config, logger_component)
        
        # Generate upload tasks
        upload_tasks = []
        source_content = file_generator.get_source_content()
        
        for bucket in buckets:
            for stage in args.stages:
                base_path = path_generator.generate_base_path(stage)
                upload_paths = path_generator.generate_upload_paths(base_path)
                for s3_key, filename in upload_paths:
                    task = UploadTask(
                        bucket=bucket,
                        key=s3_key,
                        content=source_content,
                        filename=filename
                    )
                    upload_tasks.append(task)
        
        # Execute uploads
        results = s3_uploader.execute_upload_tasks(upload_tasks)
        
        # Log summary
        logger_component.log_summary(results)
        
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
                stages=args.stages,
                aws_profile=args.profile,
                verbose=args.verbose,
                base_path="",
                source_file_path=""
            ))
            logger_component.log_error_with_guidance(f"Upload utility failed: {e}", suggestions)
        
        sys.exit(1)


if __name__ == "__main__":
    main()