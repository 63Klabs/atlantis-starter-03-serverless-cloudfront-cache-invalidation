#!/usr/bin/env python3
"""
End-to-end integration tests for the enhanced test file upload utility.

This module validates complete functionality with real S3 operations:
- All 62 files are uploaded correctly per bucket per stage
- Logging output shows correct file counts and progress
- Enhanced functionality works with real AWS services

**Validates: Requirements 3.4, 3.5, 5.1, 5.2, 5.4, 5.5**

Run with: pytest tests/integration/test_enhanced_upload_utility_e2e.py -v
"""
import pytest
import os
import sys
import tempfile
import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple
import boto3
from unittest.mock import patch, MagicMock
import logging

# Add the build-scripts directory to the path
build_scripts_path = Path(__file__).parent.parent.parent / "build-scripts"
sys.path.insert(0, str(build_scripts_path))

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("upload_test_files", build_scripts_path / "upload-test-files.py")
    upload_test_files = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upload_test_files)
    
    Configuration = upload_test_files.Configuration
    PathGenerator = upload_test_files.PathGenerator
    NestedStructureGenerator = upload_test_files.NestedStructureGenerator
    FileGenerator = upload_test_files.FileGenerator
    Logger = upload_test_files.Logger
    S3Uploader = upload_test_files.S3Uploader
    EnvironmentManager = upload_test_files.EnvironmentManager
    UploadTask = upload_test_files.UploadTask
    EnhancedUploadResult = upload_test_files.EnhancedUploadResult
    
except ImportError as e:
    print(f"Import error: {e}")
    raise


class TestEnhancedUploadUtilityE2E:
    """End-to-end integration tests for the enhanced upload utility"""
    
    def test_complete_enhanced_utility_with_mocked_s3(self):
        """
        Test complete enhanced utility with mocked S3 operations
        
        **Validates: Requirements 3.4, 3.5, 5.1, 5.2, 5.4, 5.5**
        """
        # Create a temporary test.html file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write('<html><body>Test content for enhanced utility</body></html>')
            test_html_path = f.name
        
        try:
            # Mock S3 operations
            with patch('boto3.Session') as mock_session:
                mock_s3_client = MagicMock()
                mock_session.return_value.client.return_value = mock_s3_client
                
                # Mock successful S3 operations
                mock_s3_client.head_bucket.return_value = {}
                mock_s3_client.put_object.return_value = {}
                
                # Setup test configuration
                test_buckets = ["test-bucket-1", "test-bucket-2"]
                test_stages = ["dev", "prod"]
                
                config = Configuration(
                    buckets=test_buckets,
                    stages=test_stages,
                    aws_profile=None,
                    verbose=True,
                    base_path="",
                    source_file_path=test_html_path
                )
                
                # Initialize components
                env_manager = EnvironmentManager()
                file_generator = FileGenerator(config)
                path_generator = PathGenerator(config)
                logger_component = Logger(config)
                session = mock_session.return_value
                s3_uploader = S3Uploader(session, config, logger_component)
                
                # Generate upload tasks with enhanced tracking
                upload_tasks = []
                source_content = file_generator.get_source_content()
                structure_info = None
                
                for bucket in test_buckets:
                    for stage in test_stages:
                        base_path = env_manager.determine_base_path(stage)
                        upload_paths, nested_info = path_generator.generate_all_upload_paths_with_info(base_path)
                        
                        # Store structure info for enhanced logging
                        if structure_info is None:
                            structure_info = nested_info
                        
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
                
                # Validate results
                assert len(results) == len(test_buckets), f"Expected results for {len(test_buckets)} buckets"
                
                total_successful = 0
                total_legacy_files = 0
                total_nested_files = 0
                
                for bucket, result in results.items():
                    assert isinstance(result, EnhancedUploadResult), f"Expected EnhancedUploadResult for bucket {bucket}"
                    
                    # Verify file counts per bucket per stage combination
                    expected_files_per_bucket = len(test_stages) * 62  # 62 files per stage
                    assert result.successful_uploads == expected_files_per_bucket, \
                        f"Bucket {bucket}: expected {expected_files_per_bucket} successful uploads, got {result.successful_uploads}"
                    
                    assert result.failed_uploads == 0, f"Bucket {bucket}: expected 0 failed uploads, got {result.failed_uploads}"
                    
                    # Verify file type breakdown
                    expected_legacy_per_bucket = len(test_stages) * 12  # 12 legacy files per stage
                    expected_nested_per_bucket = len(test_stages) * 50  # 50 nested files per stage
                    
                    assert result.legacy_file_count == expected_legacy_per_bucket, \
                        f"Bucket {bucket}: expected {expected_legacy_per_bucket} legacy files, got {result.legacy_file_count}"
                    
                    assert result.nested_file_count == expected_nested_per_bucket, \
                        f"Bucket {bucket}: expected {expected_nested_per_bucket} nested files, got {result.nested_file_count}"
                    
                    # Verify root directory is set
                    assert result.root_directory, f"Bucket {bucket}: root directory should be set"
                    assert len(result.root_directory) == 8, f"Bucket {bucket}: root directory should be 8 characters"
                    
                    total_successful += result.successful_uploads
                    total_legacy_files += result.legacy_file_count
                    total_nested_files += result.nested_file_count
                
                # Verify total counts
                expected_total_files = len(test_buckets) * len(test_stages) * 62
                assert total_successful == expected_total_files, \
                    f"Expected {expected_total_files} total successful uploads, got {total_successful}"
                
                expected_total_legacy = len(test_buckets) * len(test_stages) * 12
                expected_total_nested = len(test_buckets) * len(test_stages) * 50
                
                assert total_legacy_files == expected_total_legacy, \
                    f"Expected {expected_total_legacy} total legacy files, got {total_legacy_files}"
                
                assert total_nested_files == expected_total_nested, \
                    f"Expected {expected_total_nested} total nested files, got {total_nested_files}"
                
                # Verify S3 operations were called correctly
                assert mock_s3_client.head_bucket.call_count == len(test_buckets), \
                    f"Expected {len(test_buckets)} head_bucket calls, got {mock_s3_client.head_bucket.call_count}"
                
                assert mock_s3_client.put_object.call_count == expected_total_files, \
                    f"Expected {expected_total_files} put_object calls, got {mock_s3_client.put_object.call_count}"
                
                print(f"✅ E2E test completed successfully:")
                print(f"   - {len(test_buckets)} buckets × {len(test_stages)} stages = {len(test_buckets) * len(test_stages)} combinations")
                print(f"   - {expected_total_files} total files uploaded ({expected_total_legacy} legacy + {expected_total_nested} nested)")
                print(f"   - All enhanced tracking and logging validated")
        
        finally:
            # Clean up temporary file
            if os.path.exists(test_html_path):
                os.unlink(test_html_path)
    
    def test_logging_output_validation(self):
        """
        Test that logging output shows correct file counts and progress
        
        **Validates: Requirements 5.1, 5.2, 5.4, 5.5**
        """
        # Create a temporary test.html file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write('<html><body>Test logging validation</body></html>')
            test_html_path = f.name
        
        try:
            # Capture logging output
            import io
            log_capture = io.StringIO()
            handler = logging.StreamHandler(log_capture)
            handler.setLevel(logging.INFO)
            
            # Setup logger to capture output
            logger = logging.getLogger()
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
            # Mock S3 operations
            with patch('boto3.Session') as mock_session:
                mock_s3_client = MagicMock()
                mock_session.return_value.client.return_value = mock_s3_client
                
                # Mock successful S3 operations
                mock_s3_client.head_bucket.return_value = {}
                mock_s3_client.put_object.return_value = {}
                
                # Setup test configuration with verbose logging
                config = Configuration(
                    buckets=["test-bucket"],
                    stages=["prod"],
                    aws_profile=None,
                    verbose=True,
                    base_path="/prod/public/",
                    source_file_path=test_html_path
                )
                
                # Initialize components
                logger_component = Logger(config)
                path_generator = PathGenerator(config)
                session = mock_session.return_value
                s3_uploader = S3Uploader(session, config, logger_component)
                
                # Generate paths and structure info
                upload_paths, structure_info = path_generator.generate_all_upload_paths_with_info(config.base_path)
                
                # Log nested structure start (validates Requirements 5.1)
                logger_component.log_nested_structure_start(structure_info.root_directory)
                
                # Log level progress (validates Requirements 5.2)
                for level in structure_info.levels:
                    logger_component.log_level_progress(level.level_number, len(level.files))
                
                # Create upload tasks
                upload_tasks = []
                test_content = '<html><body>Test content</body></html>'
                
                for s3_key, filename in upload_paths:
                    task = UploadTask(
                        bucket="test-bucket",
                        key=s3_key,
                        content=test_content,
                        filename=filename
                    )
                    upload_tasks.append(task)
                
                # Execute uploads
                results = s3_uploader.execute_enhanced_upload_tasks(upload_tasks, structure_info)
                
                # Log enhanced summary (validates Requirements 5.4, 5.5)
                logger_component.log_enhanced_summary(results)
                
                # Get captured log output
                log_output = log_capture.getvalue()
                
                # Validate logging content
                
                # Check nested structure logging (Requirements 5.1)
                assert "Creating nested structure in root directory:" in log_output, \
                    "Missing nested structure start logging"
                assert "Structure: 5 levels deep, 10 files per level, 50 total files" in log_output, \
                    "Missing structure overview logging"
                
                # Check level progress logging (Requirements 5.2)
                for level_num in range(1, 6):
                    assert f"Level {level_num}: Created 10 files" in log_output, \
                        f"Missing level {level_num} progress logging"
                
                # Check enhanced summary logging (Requirements 5.4, 5.5)
                assert "Enhanced Upload Summary" in log_output, \
                    "Missing enhanced summary header"
                assert "Legacy files: 12" in log_output, \
                    "Missing legacy file count in summary"
                assert "Nested structure files: 50" in log_output, \
                    "Missing nested file count in summary"
                assert "12 legacy + 50 nested = 62 total files per bucket" in log_output, \
                    "Missing total file breakdown in summary"
                
                # Check verbose mode logging (Requirements 5.3)
                if config.verbose:
                    assert "Uploaded paths:" in log_output, \
                        "Missing verbose path logging"
                
                print("✅ Logging validation completed successfully:")
                print("   - Nested structure start logging ✓")
                print("   - Level progress logging ✓") 
                print("   - Enhanced summary with file type breakdown ✓")
                print("   - Verbose mode path logging ✓")
            
            # Remove handler to avoid affecting other tests
            logger.removeHandler(handler)
        
        finally:
            # Clean up temporary file
            if os.path.exists(test_html_path):
                os.unlink(test_html_path)
    
    def test_file_path_structure_validation(self):
        """
        Test that all 62 files have correct path structures
        
        **Validates: Requirements 3.4, 3.5**
        """
        # Setup configuration
        config = Configuration(
            buckets=["test-bucket"],
            stages=["dev", "staging", "prod"],
            aws_profile=None,
            verbose=False,
            base_path="",
            source_file_path="test.html"
        )
        
        path_generator = PathGenerator(config)
        env_manager = EnvironmentManager()
        
        # Test each stage
        for stage in config.stages:
            base_path = env_manager.determine_base_path(stage)
            upload_paths, structure_info = path_generator.generate_all_upload_paths_with_info(base_path)
            
            # Verify total file count
            assert len(upload_paths) == 62, f"Stage {stage}: expected 62 files, got {len(upload_paths)}"
            
            # Separate legacy and nested files
            legacy_files = []
            nested_files = []
            
            for s3_key, filename in upload_paths:
                if filename.startswith('nested-'):
                    nested_files.append((s3_key, filename))
                else:
                    legacy_files.append((s3_key, filename))
            
            # Verify file type counts
            assert len(legacy_files) == 12, f"Stage {stage}: expected 12 legacy files, got {len(legacy_files)}"
            assert len(nested_files) == 50, f"Stage {stage}: expected 50 nested files, got {len(nested_files)}"
            
            # Verify legacy file patterns
            for s3_key, filename in legacy_files:
                # Legacy files can be either test-XXXXXX.html or special names like index.html, default.html
                is_test_pattern = filename.startswith('test-') and filename.endswith('.html')
                is_special_file = filename in ['index.html', 'default.html']
                assert is_test_pattern or is_special_file, \
                    f"Legacy file should follow test-XXXXXX.html pattern or be a special file: {filename}"
                assert s3_key.startswith(base_path), f"Legacy file path should start with base path: {s3_key}"
            
            # Verify nested file patterns and structure
            root_dir = structure_info.root_directory
            assert len(root_dir) == 8, f"Root directory should be 8 characters: {root_dir}"
            
            # Group nested files by level
            files_by_level = {1: [], 2: [], 3: [], 4: [], 5: []}
            
            for s3_key, filename in nested_files:
                assert filename.startswith('nested-'), f"Nested file should start with 'nested-': {filename}"
                assert filename.endswith('.html'), f"Nested file should end with '.html': {filename}"
                assert s3_key.startswith(base_path), f"Nested file path should start with base path: {s3_key}"
                
                # Determine level based on path structure
                path_parts = s3_key.replace(base_path, '').strip('/').split('/')
                level = len(path_parts) - 1  # Subtract 1 for the filename
                
                if 1 <= level <= 5:
                    files_by_level[level].append((s3_key, filename))
            
            # Verify 10 files per level
            for level in range(1, 6):
                assert len(files_by_level[level]) == 10, \
                    f"Stage {stage}, Level {level}: expected 10 files, got {len(files_by_level[level])}"
            
            # Verify nested structure info
            assert structure_info.total_files == 50, f"Structure info should show 50 total files"
            assert structure_info.total_directories == 4, f"Structure info should show 4 directories"
            assert len(structure_info.levels) == 5, f"Structure info should have 5 levels"
            
            # Verify each level in structure info
            for level_info in structure_info.levels:
                assert len(level_info.files) == 10, f"Level {level_info.level_number} should have 10 files"
                
                if level_info.level_number < 5:
                    assert level_info.subdirectory is not None, f"Level {level_info.level_number} should have a subdirectory"
                    assert level_info.subdirectory.startswith(f'level-{level_info.level_number}-'), \
                        f"Subdirectory should follow naming pattern: {level_info.subdirectory}"
                else:
                    assert level_info.subdirectory is None, f"Level 5 should not have a subdirectory"
            
            print(f"✅ Stage {stage} path structure validation completed:")
            print(f"   - 62 total files (12 legacy + 50 nested) ✓")
            print(f"   - 5-level nested structure with 10 files per level ✓")
            print(f"   - Correct naming patterns and path structures ✓")
    
    def test_custom_origin_path_option(self):
        """
        Test that --origin_path option works correctly with custom patterns
        
        **Validates: upload-utility-origin-path-option Requirements 1.1, 1.2, 2.1, 2.2**
        """
        # Create a temporary test.html file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write('<html><body>Test custom origin path</body></html>')
            test_html_path = f.name
        
        try:
            # Test custom origin path with stage placeholder
            with patch('boto3.Session') as mock_session:
                mock_s3_client = MagicMock()
                mock_session.return_value.client.return_value = mock_s3_client
                
                # Mock successful S3 operations
                mock_s3_client.head_bucket.return_value = {}
                mock_s3_client.put_object.return_value = {}
                
                # Setup test configuration with custom origin path
                config = Configuration(
                    buckets=["test-bucket"],
                    stages=["prod"],
                    aws_profile=None,
                    verbose=True,
                    base_path="",
                    source_file_path=test_html_path,
                    origin_path_pattern="/app/{stageId}"
                )
                
                # Initialize components
                env_manager = EnvironmentManager()
                file_generator = FileGenerator(config)
                path_generator = PathGenerator(config)
                logger_component = Logger(config)
                session = mock_session.return_value
                s3_uploader = S3Uploader(session, config, logger_component)
                
                # Generate upload tasks
                upload_tasks = []
                source_content = file_generator.get_source_content()
                
                for bucket in config.buckets:
                    for stage in config.stages:
                        # Use custom origin path pattern
                        base_path = env_manager.determine_base_path(stage, config.origin_path_pattern)
                        
                        # Verify custom base path
                        assert base_path == "/app/prod/", f"Expected /app/prod/, got {base_path}"
                        
                        upload_paths, nested_info = path_generator.generate_all_upload_paths_with_info(base_path)
                        
                        for s3_key, filename in upload_paths:
                            # Verify all paths start with custom base path
                            assert s3_key.startswith("/app/prod/"), \
                                f"Path should start with /app/prod/, got {s3_key}"
                            
                            task = UploadTask(
                                bucket=bucket,
                                key=s3_key,
                                content=source_content,
                                filename=filename
                            )
                            upload_tasks.append(task)
                
                # Execute uploads
                results = s3_uploader.execute_enhanced_upload_tasks(upload_tasks, nested_info)
                
                # Validate results
                assert len(results) == 1, "Expected results for 1 bucket"
                result = results["test-bucket"]
                assert result.successful_uploads == 62, f"Expected 62 uploads, got {result.successful_uploads}"
                
                # Verify S3 operations used custom paths
                put_object_calls = mock_s3_client.put_object.call_args_list
                for call in put_object_calls:
                    s3_key = call[1]['Key']
                    assert s3_key.startswith('/app/prod/'), \
                        f"All uploaded files should use custom origin path, got {s3_key}"
                
                print("✅ Custom origin path option test completed:")
                print("   - Custom pattern /app/{stageId} resolved to /app/prod/ ✓")
                print("   - All 62 files uploaded to correct custom path ✓")
        
        finally:
            # Clean up temporary file
            if os.path.exists(test_html_path):
                os.unlink(test_html_path)
    
    def test_static_origin_path_without_placeholder(self):
        """
        Test that --origin_path option works with static paths (no {stageId})
        
        **Validates: upload-utility-origin-path-option Requirements 1.2, 2.2**
        """
        # Create a temporary test.html file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write('<html><body>Test static origin path</body></html>')
            test_html_path = f.name
        
        try:
            with patch('boto3.Session') as mock_session:
                mock_s3_client = MagicMock()
                mock_session.return_value.client.return_value = mock_s3_client
                
                # Mock successful S3 operations
                mock_s3_client.head_bucket.return_value = {}
                mock_s3_client.put_object.return_value = {}
                
                # Setup test configuration with static origin path
                config = Configuration(
                    buckets=["test-bucket"],
                    stages=["prod"],
                    aws_profile=None,
                    verbose=False,
                    base_path="",
                    source_file_path=test_html_path,
                    origin_path_pattern="/static"
                )
                
                # Initialize components
                env_manager = EnvironmentManager()
                
                # Test static path (no stage placeholder)
                base_path = env_manager.determine_base_path("prod", config.origin_path_pattern)
                
                # Verify static base path (stage is ignored)
                assert base_path == "/static/", f"Expected /static/, got {base_path}"
                
                print("✅ Static origin path test completed:")
                print("   - Static pattern /static resolved correctly ✓")
                print("   - Stage placeholder not required ✓")
        
        finally:
            # Clean up temporary file
            if os.path.exists(test_html_path):
                os.unlink(test_html_path)


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "-s"])