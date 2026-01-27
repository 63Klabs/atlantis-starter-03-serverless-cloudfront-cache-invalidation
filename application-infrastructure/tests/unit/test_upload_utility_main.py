"""
Unit tests for the main upload utility script integration
Tests the main execution flow, error scenarios, and exit codes
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import argparse

# Add the build-scripts directory to the path for imports
build_scripts_path = Path(__file__).parent.parent.parent / "build-scripts"
sys.path.insert(0, str(build_scripts_path))

# Import the upload utility module using importlib (file has dash in name)
import importlib.util
spec = importlib.util.spec_from_file_location("upload_test_files", build_scripts_path / "upload-test-files.py")
upload_test_files = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upload_test_files)

# Import classes and functions from the loaded module
main = upload_test_files.main
ArgumentParser = upload_test_files.ArgumentParser
EnvironmentManager = upload_test_files.EnvironmentManager
FileGenerator = upload_test_files.FileGenerator
PathGenerator = upload_test_files.PathGenerator
S3Uploader = upload_test_files.S3Uploader
Logger = upload_test_files.Logger
Configuration = upload_test_files.Configuration
UploadTask = upload_test_files.UploadTask
UploadResult = upload_test_files.UploadResult


class TestArgumentParserIntegration:
    """Test argument parser integration with main script"""
    
    def test_argument_parser_valid_args(self):
        """Test argument parser with valid arguments"""
        parser = ArgumentParser()
        args = parser.parse_args([
            '--buckets', 'bucket1,bucket2',
            '--stages', 'staging',
            '--profile', 'test-profile',
            '--verbose'
        ])
        
        assert args.buckets == 'bucket1,bucket2'
        assert args.stages == 'staging'
        assert args.profile == 'test-profile'
        assert args.verbose is True
    
    def test_argument_parser_minimal_args(self):
        """Test argument parser with minimal required arguments"""
        parser = ArgumentParser()
        args = parser.parse_args(['--stages', 'prod'])
        
        assert args.buckets is None
        assert args.stages == 'prod'
        assert args.profile is None
        assert args.verbose is False
    
    def test_argument_parser_invalid_stages(self):
        """Test argument parser with stages parameter"""
        parser = ArgumentParser()
        
        # Stages parameter should accept any string (no validation in parser)
        args = parser.parse_args(['--stages', 'custom-stage'])
        assert args.stages == 'custom-stage'


class TestEnvironmentManagerIntegration:
    """Test environment manager integration"""
    
    def test_get_target_buckets_from_args(self):
        """Test getting buckets from command line arguments"""
        env_mgr = EnvironmentManager()
        buckets = env_mgr.get_target_buckets('bucket1,bucket2,bucket3')
        
        assert buckets == ['bucket1', 'bucket2', 'bucket3']
    
    def test_get_target_buckets_from_env_var(self):
        """Test getting buckets from environment variable"""
        env_mgr = EnvironmentManager()
        
        with patch.dict(os.environ, {'S3_STATIC_HOST_BUCKET': 'env-bucket'}):
            buckets = env_mgr.get_target_buckets(None)
            assert buckets == ['env-bucket']
    
    def test_get_target_buckets_no_source(self):
        """Test error when no buckets specified"""
        env_mgr = EnvironmentManager()
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="No buckets specified"):
                env_mgr.get_target_buckets(None)
    
    def test_determine_base_path_prod(self):
        """Test base path determination for production"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('prod')
        
        assert base_path == '/prod/public/'
    
    def test_determine_base_path_staging(self):
        """Test base path determination for staging"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('staging')
        
        assert base_path == '/staging/public/'


class TestFileGeneratorIntegration:
    """Test file generator integration"""
    
    def test_generate_random_filename(self):
        """Test random filename generation"""
        config = Configuration(
            buckets=['test'],
            stages=['staging'],
            aws_profile=None,
            verbose=False,
            base_path='/staging/public/',
            source_file_path='test.html'
        )
        
        file_gen = FileGenerator(config)
        filename = file_gen.generate_random_filename()
        
        assert filename.startswith('test-')
        assert filename.endswith('.html')
        assert len(filename) == 16  # test- (5) + 6 chars + .html (5) = 16
    
    def test_get_source_content_missing_file(self):
        """Test error when source file is missing"""
        config = Configuration(
            buckets=['test'],
            stages=['staging'],
            aws_profile=None,
            verbose=False,
            base_path='/staging/public/',
            source_file_path='/nonexistent/file.html'
        )
        
        file_gen = FileGenerator(config)
        
        with pytest.raises(FileNotFoundError):
            file_gen.get_source_content()


class TestPathGeneratorIntegration:
    """Test path generator integration"""
    
    def test_generate_upload_paths_count(self):
        """Test that exactly 12 paths are generated"""
        config = Configuration(
            buckets=['test'],
            stages=['staging'],
            aws_profile=None,
            verbose=False,
            base_path='/staging/public/',
            source_file_path='test.html'
        )
        
        path_gen = PathGenerator(config)
        paths = path_gen.generate_upload_paths('/staging/public/')
        
        assert len(paths) == 12
    
    def test_generate_upload_paths_structure(self):
        """Test that paths have correct structure"""
        config = Configuration(
            buckets=['test'],
            stages=['staging'],
            aws_profile=None,
            verbose=False,
            base_path='/staging/public/',
            source_file_path='test.html'
        )
        
        path_gen = PathGenerator(config)
        paths = path_gen.generate_upload_paths('/staging/public/')
        
        # All paths should NOT start with leading slash (S3 standard format)
        # but should contain the base path components
        for s3_key, filename in paths:
            assert not s3_key.startswith('/'), f"Key should not have leading slash: {s3_key}"
            assert 'staging/public/' in s3_key
            assert filename.endswith('.html')
    
    def test_generate_upload_paths_invalid_count(self):
        """Test error when requesting invalid count"""
        config = Configuration(
            buckets=['test'],
            stages=['staging'],
            aws_profile=None,
            verbose=False,
            base_path='/staging/public/',
            source_file_path='test.html'
        )
        
        path_gen = PathGenerator(config)
        
        with pytest.raises(ValueError, match="must create exactly 12 files"):
            path_gen.generate_upload_paths('/staging/public/', count=10)


class TestConfigurationIntegration:
    """Test configuration object integration"""
    
    def test_configuration_creation(self):
        """Test configuration object creation with all fields"""
        config = Configuration(
            buckets=['bucket1', 'bucket2'],
            stages=['staging'],
            aws_profile='test-profile',
            verbose=True,
            base_path='/staging/public/',
            source_file_path='/path/to/test.html'
        )
        
        assert config.buckets == ['bucket1', 'bucket2']
        assert config.stages == ['staging']
        assert config.aws_profile == 'test-profile'
        assert config.verbose is True
        assert config.base_path == '/staging/public/'
        assert config.source_file_path == '/path/to/test.html'


class TestUploadTaskIntegration:
    """Test upload task integration"""
    
    def test_upload_task_creation(self):
        """Test upload task creation"""
        task = UploadTask(
            bucket='test-bucket',
            key='/stage/public/test/file.html',
            content='<html>test</html>',
            filename='file.html'
        )
        
        assert task.bucket == 'test-bucket'
        assert task.key == '/stage/public/test/file.html'
        assert task.content == '<html>test</html>'
        assert task.filename == 'file.html'


class TestUploadResultIntegration:
    """Test upload result integration"""
    
    def test_upload_result_creation(self):
        """Test upload result creation"""
        result = UploadResult(
            bucket='test-bucket',
            successful_uploads=10,
            failed_uploads=2,
            upload_paths=['/path1', '/path2']
        )
        
        assert result.bucket == 'test-bucket'
        assert result.successful_uploads == 10
        assert result.failed_uploads == 2
        assert result.upload_paths == ['/path1', '/path2']





if __name__ == '__main__':
    pytest.main([__file__])


class TestS3KeyNormalization:
    """Test S3 key normalization to ensure keys don't have leading slashes"""
    
    def test_generate_upload_paths_no_leading_slash(self):
        """Test that generated keys don't have leading slashes (S3 standard format)"""
        config = Configuration(
            buckets=['test'],
            stages=['prod'],
            aws_profile=None,
            verbose=False,
            base_path='/prod/public/',
            source_file_path='test.html'
        )
        
        path_gen = PathGenerator(config)
        paths = path_gen.generate_upload_paths('/prod/public/')
        
        # All paths should NOT start with leading slash (S3 standard format)
        for s3_key, filename in paths:
            assert not s3_key.startswith('/'), f"Key should not have leading slash: {s3_key}"
            assert filename.endswith('.html')
            # Verify key format: should be like "prod/public/dir/file.html"
            assert 'prod/public/' in s3_key
    
    def test_generate_nested_structure_no_leading_slash(self):
        """Test that nested structure keys don't have leading slashes"""
        config = Configuration(
            buckets=['test'],
            stages=['staging'],
            aws_profile=None,
            verbose=False,
            base_path='/staging/public/',
            source_file_path='test.html'
        )
        
        path_gen = PathGenerator(config)
        nested_paths, structure_info = path_gen.nested_generator.generate_nested_structure('/staging/public/')
        
        # All nested paths should NOT start with leading slash
        for s3_key, filename in nested_paths:
            assert not s3_key.startswith('/'), f"Nested key should not have leading slash: {s3_key}"
            assert filename.startswith('nested-')
            assert filename.endswith('.html')
            # Verify key format includes base path without leading slash
            assert 'staging/public/' in s3_key
    
    def test_generate_all_upload_paths_no_leading_slash(self):
        """Test that combined legacy and nested paths don't have leading slashes"""
        config = Configuration(
            buckets=['test'],
            stages=['prod'],
            aws_profile=None,
            verbose=False,
            base_path='/prod/public/',
            source_file_path='test.html'
        )
        
        path_gen = PathGenerator(config)
        all_paths = path_gen.generate_all_upload_paths('/prod/public/')
        
        # Should have 62 total paths (12 legacy + 50 nested)
        assert len(all_paths) == 62
        
        # None should have leading slashes
        for s3_key, filename in all_paths:
            assert not s3_key.startswith('/'), f"Key should not have leading slash: {s3_key}"
            assert 'prod/public/' in s3_key
    
    def test_upload_file_strips_leading_slash(self):
        """Test that upload function strips any leading slashes"""
        config = Configuration(
            buckets=['test-bucket'],
            stages=['prod'],
            aws_profile=None,
            verbose=False,
            base_path='/prod/public/',
            source_file_path='test.html'
        )
        
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_session.client.return_value = mock_s3_client
        
        logger_component = Logger(config)
        uploader = S3Uploader(mock_session, config, logger_component)
        
        # Test with key that has leading slash
        key_with_slash = '/prod/public/test/file.html'
        uploader.upload_file('test-bucket', key_with_slash, '<html>test</html>')
        
        # Verify put_object was called with key WITHOUT leading slash
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        actual_key = call_args[1]['Key']
        
        assert not actual_key.startswith('/'), f"Uploaded key should not have leading slash: {actual_key}"
        assert actual_key == 'prod/public/test/file.html'
    
    def test_upload_file_preserves_no_leading_slash(self):
        """Test that upload function preserves keys without leading slashes"""
        config = Configuration(
            buckets=['test-bucket'],
            stages=['prod'],
            aws_profile=None,
            verbose=False,
            base_path='/prod/public/',
            source_file_path='test.html'
        )
        
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_session.client.return_value = mock_s3_client
        
        logger_component = Logger(config)
        uploader = S3Uploader(mock_session, config, logger_component)
        
        # Test with key that already has no leading slash
        key_without_slash = 'prod/public/test/file.html'
        uploader.upload_file('test-bucket', key_without_slash, '<html>test</html>')
        
        # Verify put_object was called with same key (no leading slash)
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        actual_key = call_args[1]['Key']
        
        assert not actual_key.startswith('/'), f"Uploaded key should not have leading slash: {actual_key}"
        assert actual_key == 'prod/public/test/file.html'
    
    def test_upload_with_retry_strips_leading_slash(self):
        """Test that upload_with_retry strips leading slashes"""
        config = Configuration(
            buckets=['test-bucket'],
            stages=['staging'],
            aws_profile=None,
            verbose=False,
            base_path='/staging/public/',
            source_file_path='test.html'
        )
        
        mock_session = Mock()
        mock_s3_client = Mock()
        mock_session.client.return_value = mock_s3_client
        
        logger_component = Logger(config)
        uploader = S3Uploader(mock_session, config, logger_component)
        
        # Test with key that has leading slash
        key_with_slash = '/staging/public/assets/file.html'
        uploader.upload_with_retry('test-bucket', key_with_slash, '<html>test</html>')
        
        # Verify put_object was called with key WITHOUT leading slash
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        actual_key = call_args[1]['Key']
        
        assert not actual_key.startswith('/'), f"Uploaded key should not have leading slash: {actual_key}"
        assert actual_key == 'staging/public/assets/file.html'
    
    def test_key_format_validation(self):
        """Test that generated keys match S3 standard format"""
        config = Configuration(
            buckets=['test'],
            stages=['prod'],
            aws_profile=None,
            verbose=False,
            base_path='/prod/public/',
            source_file_path='test.html'
        )
        
        path_gen = PathGenerator(config)
        paths = path_gen.generate_upload_paths('/prod/public/')
        
        for s3_key, filename in paths:
            # Key should not start with slash
            assert not s3_key.startswith('/')
            # Key should not have double slashes
            assert '//' not in s3_key
            # Key should be reasonable length (< 1024 chars)
            assert len(s3_key) < 1024
            # Key should contain the base path components
            assert 'prod' in s3_key
            assert 'public' in s3_key
    
    def test_nested_structure_key_format(self):
        """Test that nested structure keys match S3 standard format"""
        config = Configuration(
            buckets=['test'],
            stages=['staging'],
            aws_profile=None,
            verbose=False,
            base_path='/staging/public/',
            source_file_path='test.html'
        )
        
        path_gen = PathGenerator(config)
        nested_paths, structure_info = path_gen.nested_generator.generate_nested_structure('/staging/public/')
        
        # Verify structure info
        assert structure_info.total_files == 50
        assert structure_info.total_directories == 4
        assert len(structure_info.root_directory) == 8  # 8 random chars
        
        for s3_key, filename in nested_paths:
            # Key should not start with slash
            assert not s3_key.startswith('/')
            # Key should not have double slashes
            assert '//' not in s3_key
            # Key should contain root directory
            assert structure_info.root_directory in s3_key
            # Key should contain base path components
            assert 'staging' in s3_key
            assert 'public' in s3_key
