"""
Unit tests for determine_base_path() function with origin path pattern support
Tests the new --origin_path functionality for custom origin path patterns
"""
import pytest
import sys
from pathlib import Path

# Add the build-scripts directory to the path for imports
build_scripts_path = Path(__file__).parent.parent.parent / "build-scripts"
sys.path.insert(0, str(build_scripts_path))

# Import the upload utility module using importlib (file has dash in name)
import importlib.util
spec = importlib.util.spec_from_file_location("upload_test_files", build_scripts_path / "upload-test-files.py")
upload_test_files = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upload_test_files)

# Import EnvironmentManager from the loaded module
EnvironmentManager = upload_test_files.EnvironmentManager


class TestDetermineBasePathDefaultPattern:
    """Test determine_base_path() with default origin path pattern"""
    
    def test_default_pattern_prod(self):
        """Test default origin path pattern with prod stage - Requirements 6.1, 6.3"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('prod')
        
        assert base_path == '/prod/public/'
    
    def test_default_pattern_staging(self):
        """Test default origin path pattern with staging stage"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('staging')
        
        assert base_path == '/staging/public/'
    
    def test_default_pattern_dev(self):
        """Test default origin path pattern with dev stage"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('dev')
        
        assert base_path == '/dev/public/'
    
    def test_default_pattern_explicit(self):
        """Test explicitly passing default pattern"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('prod', '/{stageId}/public')
        
        assert base_path == '/prod/public/'


class TestDetermineBasePathCustomPatternWithPlaceholder:
    """Test determine_base_path() with custom patterns containing {stageId} placeholder"""
    
    def test_custom_pattern_with_placeholder_prod(self):
        """Test custom origin path with stage placeholder - Requirements 1.6, 2.2"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('prod', '/app/{stageId}')
        
        assert base_path == '/app/prod/'
    
    def test_custom_pattern_with_placeholder_staging(self):
        """Test custom origin path with stage placeholder for staging"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('staging', '/app/{stageId}')
        
        assert base_path == '/app/staging/'
    
    def test_custom_pattern_with_placeholder_dev(self):
        """Test custom origin path with stage placeholder for dev"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('dev', '/app/{stageId}')
        
        assert base_path == '/app/dev/'
    
    def test_custom_pattern_multiple_directories(self):
        """Test custom pattern with multiple directory levels"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('prod', '/api/v1/{stageId}/data')
        
        assert base_path == '/api/v1/prod/data/'
    
    def test_custom_pattern_placeholder_at_start(self):
        """Test custom pattern with placeholder at start"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('prod', '/{stageId}/assets')
        
        assert base_path == '/prod/assets/'


class TestDetermineBasePathCustomPatternWithoutPlaceholder:
    """Test determine_base_path() with custom patterns without {stageId} placeholder"""
    
    def test_custom_pattern_without_placeholder(self):
        """Test custom origin path without stage placeholder - Requirements 2.2"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('prod', '/static')
        
        assert base_path == '/static/'
    
    def test_custom_pattern_without_placeholder_multiple_dirs(self):
        """Test custom pattern without placeholder with multiple directories"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('staging', '/assets/public')
        
        assert base_path == '/assets/public/'
    
    def test_custom_pattern_without_placeholder_deep_path(self):
        """Test custom pattern without placeholder with deep path"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('dev', '/content/static/files')
        
        assert base_path == '/content/static/files/'


class TestDetermineBasePathOnlyPlaceholder:
    """Test determine_base_path() with only {stageId} placeholder"""
    
    def test_only_placeholder_prod(self):
        """Test origin path with only stage placeholder - Requirements 2.2"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('prod', '/{stageId}')
        
        assert base_path == '/prod/'
    
    def test_only_placeholder_staging(self):
        """Test origin path with only stage placeholder for staging"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('staging', '/{stageId}')
        
        assert base_path == '/staging/'
    
    def test_only_placeholder_dev(self):
        """Test origin path with only stage placeholder for dev"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('dev', '/{stageId}')
        
        assert base_path == '/dev/'


class TestDetermineBasePathLeadingSlashEnforcement:
    """Test determine_base_path() leading slash enforcement"""
    
    def test_leading_slash_enforcement_with_placeholder(self):
        """Test leading slash is added when missing - Requirements 2.3"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('prod', 'app/{stageId}')
        
        assert base_path == '/app/prod/'
        assert base_path.startswith('/')
    
    def test_leading_slash_enforcement_without_placeholder(self):
        """Test leading slash is added when missing (no placeholder)"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('staging', 'static')
        
        assert base_path == '/static/'
        assert base_path.startswith('/')
    
    def test_leading_slash_enforcement_only_placeholder(self):
        """Test leading slash is added when missing (only placeholder)"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('dev', '{stageId}')
        
        assert base_path == '/dev/'
        assert base_path.startswith('/')
    
    def test_leading_slash_preserved(self):
        """Test leading slash is preserved when present"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('prod', '/app/{stageId}')
        
        assert base_path == '/app/prod/'
        assert base_path.startswith('/')


class TestDetermineBasePathTrailingSlashEnforcement:
    """Test determine_base_path() trailing slash enforcement"""
    
    def test_trailing_slash_enforcement_with_placeholder(self):
        """Test trailing slash is added when missing - Requirements 2.4"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('prod', '/app/{stageId}')
        
        assert base_path == '/app/prod/'
        assert base_path.endswith('/')
    
    def test_trailing_slash_enforcement_without_placeholder(self):
        """Test trailing slash is added when missing (no placeholder)"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('staging', '/static')
        
        assert base_path == '/static/'
        assert base_path.endswith('/')
    
    def test_trailing_slash_enforcement_only_placeholder(self):
        """Test trailing slash is added when missing (only placeholder)"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('dev', '/{stageId}')
        
        assert base_path == '/dev/'
        assert base_path.endswith('/')
    
    def test_trailing_slash_preserved(self):
        """Test trailing slash is preserved when present"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('prod', '/app/{stageId}/')
        
        assert base_path == '/app/prod/'
        assert base_path.endswith('/')


class TestDetermineBasePathMultipleStages:
    """Test determine_base_path() with multiple stages using same pattern"""
    
    def test_multiple_stages_with_custom_pattern(self):
        """Test multiple stages with custom pattern - Requirements 2.2"""
        env_mgr = EnvironmentManager()
        
        # Test prod
        base_path_prod = env_mgr.determine_base_path('prod', '/app/{stageId}')
        assert base_path_prod == '/app/prod/'
        
        # Test staging
        base_path_staging = env_mgr.determine_base_path('staging', '/app/{stageId}')
        assert base_path_staging == '/app/staging/'
    
    def test_multiple_stages_different_patterns(self):
        """Test multiple stages with different patterns"""
        env_mgr = EnvironmentManager()
        
        # Test prod with one pattern
        base_path_prod = env_mgr.determine_base_path('prod', '/api/{stageId}')
        assert base_path_prod == '/api/prod/'
        
        # Test staging with different pattern
        base_path_staging = env_mgr.determine_base_path('staging', '/static')
        assert base_path_staging == '/static/'
    
    def test_multiple_stages_default_pattern(self):
        """Test multiple stages with default pattern"""
        env_mgr = EnvironmentManager()
        
        # Test prod
        base_path_prod = env_mgr.determine_base_path('prod')
        assert base_path_prod == '/prod/public/'
        
        # Test staging
        base_path_staging = env_mgr.determine_base_path('staging')
        assert base_path_staging == '/staging/public/'
        
        # Test dev
        base_path_dev = env_mgr.determine_base_path('dev')
        assert base_path_dev == '/dev/public/'


class TestDetermineBasePathEdgeCases:
    """Test determine_base_path() edge cases"""
    
    def test_empty_stage_name(self):
        """Test with empty stage name"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('', '/app/{stageId}')
        
        # Should replace placeholder with empty string and normalize slashes
        assert base_path == '/app/'
    
    def test_stage_with_special_characters(self):
        """Test with stage containing special characters"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('prod-v2', '/app/{stageId}')
        
        assert base_path == '/app/prod-v2/'
    
    def test_pattern_with_multiple_placeholders(self):
        """Test pattern with multiple {stageId} placeholders"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('prod', '/{stageId}/data/{stageId}')
        
        # Should replace all occurrences
        assert base_path == '/prod/data/prod/'
    
    def test_pattern_with_trailing_slash_already(self):
        """Test pattern that already has trailing slash"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('prod', '/app/{stageId}/')
        
        # Should not add duplicate trailing slash
        assert base_path == '/app/prod/'
        assert base_path.count('//') == 0
    
    def test_pattern_with_both_slashes(self):
        """Test pattern that already has both leading and trailing slashes"""
        env_mgr = EnvironmentManager()
        base_path = env_mgr.determine_base_path('staging', '/static/')
        
        assert base_path == '/static/'
        assert base_path.startswith('/')
        assert base_path.endswith('/')
        assert base_path.count('//') == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
