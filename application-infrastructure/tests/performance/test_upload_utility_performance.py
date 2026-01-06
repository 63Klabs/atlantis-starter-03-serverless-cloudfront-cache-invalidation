#!/usr/bin/env python3
"""
Performance validation tests for the enhanced test file upload utility.

This module validates that the enhanced utility meets performance requirements:
- Upload time with increased file count (62 files per bucket)
- Memory usage remains reasonable with enhanced path generation
- Scalability with multiple buckets and stages

**Validates: Requirements 4.3**

Run with: pytest tests/performance/test_upload_utility_performance.py -v
"""
import pytest
import time
import psutil
import os
import sys
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple
import boto3
from unittest.mock import patch, MagicMock

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
    
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Build scripts path: {build_scripts_path}")
    print(f"Path exists: {build_scripts_path.exists()}")
    if build_scripts_path.exists():
        print(f"Contents: {list(build_scripts_path.iterdir())}")
    raise


class TestUploadUtilityPerformance:
    """Performance validation tests for the enhanced upload utility"""
    
    def test_path_generation_performance_62_files(self):
        """
        Test that path generation for 62 files per bucket completes quickly
        
        **Validates: Requirements 4.3**
        """
        # Setup configuration
        config = Configuration(
            buckets=["test-bucket"],
            stages=["prod"],
            aws_profile=None,
            verbose=False,
            base_path="/prod/public/",
            source_file_path="test.html"
        )
        
        path_generator = PathGenerator(config)
        
        # Measure path generation time
        start_time = time.time()
        
        # Generate paths for multiple iterations to get reliable timing
        iterations = 10
        for _ in range(iterations):
            paths = path_generator.generate_all_upload_paths("/prod/public/")
            
            # Verify we get exactly 62 files
            assert len(paths) == 62, f"Expected 62 files, got {len(paths)}"
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_generation = total_time / iterations
        
        # Performance assertion: should generate 62 paths in under 0.1 seconds
        assert avg_time_per_generation < 0.1, f"Path generation too slow: {avg_time_per_generation:.3f}s per generation"
        
        print(f"Path generation performance: {avg_time_per_generation:.3f}s average for 62 files")
    
    def test_memory_usage_with_enhanced_path_generation(self):
        """
        Test that memory usage remains reasonable with enhanced path generation
        
        **Validates: Requirements 4.3**
        """
        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Setup configuration
        config = Configuration(
            buckets=["test-bucket"],
            stages=["prod"],
            aws_profile=None,
            verbose=False,
            base_path="/prod/public/",
            source_file_path="test.html"
        )
        
        path_generator = PathGenerator(config)
        
        # Generate paths for multiple buckets and stages to simulate realistic usage
        all_paths = []
        bucket_count = 5
        stage_count = 3
        
        for bucket_idx in range(bucket_count):
            for stage_idx in range(stage_count):
                base_path = f"/stage{stage_idx}/public/"
                paths = path_generator.generate_all_upload_paths(base_path)
                all_paths.extend(paths)
        
        # Get memory usage after path generation
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        total_files = len(all_paths)
        expected_files = bucket_count * stage_count * 62
        
        assert total_files == expected_files, f"Expected {expected_files} files, got {total_files}"
        
        # Memory usage should be reasonable (less than 50MB increase for path generation)
        assert memory_increase < 50, f"Memory usage too high: {memory_increase:.2f}MB increase"
        
        print(f"Memory usage: {memory_increase:.2f}MB increase for {total_files} file paths")
    
    def test_scalability_multiple_buckets_and_stages(self):
        """
        Test scalability with multiple buckets and stages
        
        **Validates: Requirements 4.3**
        """
        # Setup configuration for multiple buckets and stages
        buckets = [f"test-bucket-{i}" for i in range(3)]
        stages = ["dev", "staging", "prod"]
        
        config = Configuration(
            buckets=buckets,
            stages=stages,
            aws_profile=None,
            verbose=False,
            base_path="",
            source_file_path="test.html"
        )
        
        path_generator = PathGenerator(config)
        env_manager = EnvironmentManager()
        
        # Measure time to generate paths for all bucket/stage combinations
        start_time = time.time()
        
        total_paths = []
        for bucket in buckets:
            for stage in stages:
                base_path = env_manager.determine_base_path(stage)
                paths = path_generator.generate_all_upload_paths(base_path)
                total_paths.extend([(bucket, path) for path in paths])
        
        end_time = time.time()
        generation_time = end_time - start_time
        
        # Verify total file count
        expected_total = len(buckets) * len(stages) * 62
        assert len(total_paths) == expected_total, f"Expected {expected_total} total paths, got {len(total_paths)}"
        
        # Performance assertion: should complete in under 1 second for 3x3x62 = 558 files
        assert generation_time < 1.0, f"Path generation for multiple buckets/stages too slow: {generation_time:.3f}s"
        
        print(f"Scalability test: {len(total_paths)} paths generated in {generation_time:.3f}s")
        print(f"Rate: {len(total_paths) / generation_time:.0f} paths/second")
    
    def test_nested_structure_generation_performance(self):
        """
        Test that nested structure generation (50 files) performs well
        
        **Validates: Requirements 4.3**
        """
        nested_generator = NestedStructureGenerator()
        
        # Measure nested structure generation time
        start_time = time.time()
        
        iterations = 20
        for _ in range(iterations):
            paths, structure_info = nested_generator.generate_nested_structure("/prod/public/")
            
            # Verify structure
            assert len(paths) == 50, f"Expected 50 nested files, got {len(paths)}"
            assert structure_info.total_files == 50
            assert structure_info.total_directories == 4
            assert len(structure_info.levels) == 5
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time = total_time / iterations
        
        # Performance assertion: should generate nested structure in under 0.05 seconds
        assert avg_time < 0.05, f"Nested structure generation too slow: {avg_time:.3f}s average"
        
        print(f"Nested structure generation: {avg_time:.3f}s average for 50 files")
    
    def test_filename_uniqueness_performance(self):
        """
        Test that filename uniqueness checking doesn't cause performance issues
        
        **Validates: Requirements 4.3**
        """
        nested_generator = NestedStructureGenerator()
        
        # Generate multiple nested structures to test uniqueness performance
        start_time = time.time()
        
        all_structures = []
        for _ in range(10):
            paths, structure_info = nested_generator.generate_nested_structure("/prod/public/")
            all_structures.append((paths, structure_info))
        
        end_time = time.time()
        generation_time = end_time - start_time
        
        # Verify all structures have unique filenames within each level
        for paths, structure_info in all_structures:
            # Check that each level has 10 unique files
            for level in structure_info.levels:
                assert len(level.files) == 10
                assert len(set(level.files)) == 10, f"Level {level.level_number} has duplicate filenames"
        
        # Performance assertion: 10 structures (500 files total) in under 0.5 seconds
        assert generation_time < 0.5, f"Multiple structure generation too slow: {generation_time:.3f}s"
        
        print(f"Uniqueness performance: 10 structures (500 files) in {generation_time:.3f}s")


class TestUploadUtilityIntegration:
    """Integration performance tests with mocked S3 operations"""
    
    @patch('boto3.Session')
    def test_upload_simulation_performance_62_files(self, mock_session):
        """
        Test simulated upload performance for 62 files per bucket
        
        **Validates: Requirements 4.3**
        """
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_session.return_value.client.return_value = mock_s3_client
        
        # Mock successful uploads (no actual S3 calls)
        mock_s3_client.head_bucket.return_value = {}
        mock_s3_client.put_object.return_value = {}
        
        # Setup configuration
        config = Configuration(
            buckets=["test-bucket-1", "test-bucket-2"],
            stages=["prod"],
            aws_profile=None,
            verbose=False,
            base_path="/prod/public/",
            source_file_path="test.html"
        )
        
        # Create test content
        test_content = "<html><body>Test content</body></html>"
        
        # Initialize components
        logger_component = Logger(config)
        session = mock_session.return_value
        s3_uploader = S3Uploader(session, config, logger_component)
        path_generator = PathGenerator(config)
        
        # Measure upload simulation time
        start_time = time.time()
        
        # Generate upload tasks
        upload_tasks = []
        for bucket in config.buckets:
            paths, structure_info = path_generator.generate_all_upload_paths_with_info(config.base_path)
            for s3_key, filename in paths:
                task = UploadTask(
                    bucket=bucket,
                    key=s3_key,
                    content=test_content,
                    filename=filename
                )
                upload_tasks.append(task)
        
        # Execute simulated uploads
        results = s3_uploader.execute_enhanced_upload_tasks(upload_tasks, structure_info)
        
        end_time = time.time()
        upload_time = end_time - start_time
        
        # Verify results
        total_files = sum(result.successful_uploads for result in results.values())
        expected_files = len(config.buckets) * 62
        
        assert total_files == expected_files, f"Expected {expected_files} successful uploads, got {total_files}"
        
        # Performance assertion: simulated uploads should complete quickly
        # (This tests the upload logic overhead, not actual S3 network time)
        assert upload_time < 2.0, f"Upload simulation too slow: {upload_time:.3f}s for {total_files} files"
        
        print(f"Upload simulation: {total_files} files processed in {upload_time:.3f}s")
        print(f"Rate: {total_files / upload_time:.0f} files/second (simulated)")
    
    def test_memory_usage_during_upload_tasks(self):
        """
        Test memory usage during upload task creation and processing
        
        **Validates: Requirements 4.3**
        """
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Setup for large number of upload tasks
        buckets = [f"bucket-{i}" for i in range(5)]
        stages = ["dev", "staging", "prod"]
        
        config = Configuration(
            buckets=buckets,
            stages=stages,
            aws_profile=None,
            verbose=False,
            base_path="",
            source_file_path="test.html"
        )
        
        path_generator = PathGenerator(config)
        env_manager = EnvironmentManager()
        
        # Create large number of upload tasks
        upload_tasks = []
        test_content = "<html><body>Test content</body></html>"
        
        for bucket in buckets:
            for stage in stages:
                base_path = env_manager.determine_base_path(stage)
                paths = path_generator.generate_all_upload_paths(base_path)
                
                for s3_key, filename in paths:
                    task = UploadTask(
                        bucket=bucket,
                        key=s3_key,
                        content=test_content,
                        filename=filename
                    )
                    upload_tasks.append(task)
        
        # Check memory usage after task creation
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        total_tasks = len(upload_tasks)
        expected_tasks = len(buckets) * len(stages) * 62
        
        assert total_tasks == expected_tasks, f"Expected {expected_tasks} tasks, got {total_tasks}"
        
        # Memory usage should be reasonable (less than 100MB for ~930 tasks)
        assert memory_increase < 100, f"Memory usage too high: {memory_increase:.2f}MB for {total_tasks} tasks"
        
        print(f"Memory usage: {memory_increase:.2f}MB for {total_tasks} upload tasks")
        print(f"Average: {(memory_increase * 1024) / total_tasks:.2f}KB per task")


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "-s"])