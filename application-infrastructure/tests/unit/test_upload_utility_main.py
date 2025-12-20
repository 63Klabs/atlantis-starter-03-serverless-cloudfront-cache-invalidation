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
            '--environment', 'staging',
            '--profile', 'test-profile',
            '--verbose'
        ])
        
        assert args.buckets == 'bucket1,bucket2'
        assert args.environment == 'staging'
        assert args.profile == 'test-profile'
        assert args.verbose is True
    
    def test_argument_parser_minimal_args(self):
        """Test argument parser with minimal required arguments"""
        parser = ArgumentParser()
        args = parser.parse_args(['--environment', 'prod'])
        
        assert args.buckets is None
        assert args.environment == 'prod'
        assert args.profile is None
        assert args.verbose is False
    
    def test_argument_parser_invalid_environment(self):
        """Test argument parser with invalid environment"""
        parser = ArgumentParser()
        
        with pytest.raises(SystemExit):
            parser.parse_args(['--environment', 'invalid'])


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
        
        assert base_path == '/stage/public/'


class TestFileGeneratorIntegration:
    """Test file generator integration"""
    
    def test_generate_random_filename(self):
        """Test random filename generation"""
        config = Configuration(
            buckets=['test'],
            environment='staging',
            aws_profile=None,
            verbose=False,
            base_path='/stage/public/',
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
            environment='staging',
            aws_profile=None,
            verbose=False,
            base_path='/stage/public/',
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
            environment='staging',
            aws_profile=None,
            verbose=False,
            base_path='/stage/public/',
            source_file_path='test.html'
        )
        
        path_gen = PathGenerator(config)
        paths = path_gen.generate_upload_paths('/stage/public/')
        
        assert len(paths) == 12
    
    def test_generate_upload_paths_structure(self):
        """Test that paths have correct structure"""
        config = Configuration(
            buckets=['test'],
            environment='staging',
            aws_profile=None,
            verbose=False,
            base_path='/stage/public/',
            source_file_path='test.html'
        )
        
        path_gen = PathGenerator(config)
        paths = path_gen.generate_upload_paths('/stage/public/')
        
        # All paths should start with base path
        for s3_key, filename in paths:
            assert s3_key.startswith('/stage/public/')
            assert filename.endswith('.html')
    
    def test_generate_upload_paths_invalid_count(self):
        """Test error when requesting invalid count"""
        config = Configuration(
            buckets=['test'],
            environment='staging',
            aws_profile=None,
            verbose=False,
            base_path='/stage/public/',
            source_file_path='test.html'
        )
        
        path_gen = PathGenerator(config)
        
        with pytest.raises(ValueError, match="must create exactly 12 files"):
            path_gen.generate_upload_paths('/stage/public/', count=10)


class TestConfigurationIntegration:
    """Test configuration object integration"""
    
    def test_configuration_creation(self):
        """Test configuration object creation with all fields"""
        config = Configuration(
            buckets=['bucket1', 'bucket2'],
            environment='staging',
            aws_profile='test-profile',
            verbose=True,
            base_path='/stage/public/',
            source_file_path='/path/to/test.html'
        )
        
        assert config.buckets == ['bucket1', 'bucket2']
        assert config.environment == 'staging'
        assert config.aws_profile == 'test-profile'
        assert config.verbose is True
        assert config.base_path == '/stage/public/'
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


class TestMainScriptExitCodes:
    """Test main script exit code behavior"""
    
    def test_main_exit_code_success(self):
        """Test that main exits with 0 on success"""
        test_args = [
            '--buckets', 'test-bucket',
            '--environment', 'staging'
        ]
        
        with patch('sys.argv', ['upload-test-files.py'] + test_args), \
             patch.object(upload_test_files, 'EnvironmentManager') as mock_env_mgr, \
             patch.object(upload_test_files, 'FileGenerator') as mock_file_gen, \
             patch.object(upload_test_files, 'PathGenerator') as mock_path_gen, \
             patch.object(upload_test_files, 'S3Uploader') as mock_s3_uploader, \
             patch.object(upload_test_files, 'Logger') as mock_logger, \
             patch('sys.exit') as mock_exit:
            
            # Setup successful mocks
            mock_env_instance = Mock()
            mock_env_mgr.return_value = mock_env_instance
            mock_env_instance.get_target_buckets.return_value = ['test-bucket']
            mock_env_instance.setup_aws_session.return_value = Mock()
            mock_env_instance.determine_base_path.return_value = '/stage/public/'
            
            mock_file_instance = Mock()
            mock_file_gen.return_value = mock_file_instance
            mock_file_instance.get_source_content.return_value = '<html>test</html>'
            
            mock_path_instance = Mock()
            mock_path_gen.return_value = mock_path_instance
            mock_path_instance.generate_upload_paths.return_value = [
                ('/stage/public/test/file1.html', 'file1.html')
            ]
            
            mock_s3_instance = Mock()
            mock_s3_uploader.return_value = mock_s3_instance
            mock_s3_instance.execute_upload_tasks.return_value = {
                'test-bucket': UploadResult('test-bucket', 1, 0, ['/stage/public/test/file1.html'])
            }
            
            mock_logger_instance = Mock()
            mock_logger.return_value = mock_logger_instance
            
            # Execute main
            main()
            
            # Verify successful exit
            mock_exit.assert_called_once_with(0)
    
    def test_main_exit_code_failure(self):
        """Test that main exits with 1 on failure"""
        test_args = [
            '--buckets', 'test-bucket',
            '--environment', 'staging'
        ]
        
        with patch('sys.argv', ['upload-test-files.py'] + test_args), \
             patch.object(upload_test_files, 'EnvironmentManager') as mock_env_mgr, \
             patch('sys.exit') as mock_exit:
            
            # Setup failure mock
            mock_env_instance = Mock()
            mock_env_mgr.return_value = mock_env_instance
            mock_env_instance.get_target_buckets.side_effect = ValueError("No buckets specified")
            
            # Execute main
            main()
            
            # Verify failure exit
            mock_exit.assert_called_once_with(1)


if __name__ == '__main__':
    pytest.main([__file__])