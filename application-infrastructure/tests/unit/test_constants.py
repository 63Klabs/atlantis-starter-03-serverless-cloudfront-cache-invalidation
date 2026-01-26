"""Unit tests for the enhanced constants module."""

import os
import unittest
from unittest.mock import patch
import sys
from pathlib import Path

# Add the layers/common/python directory to the path for testing
test_dir = Path(__file__).parent
layers_path = test_dir.parent.parent / "layers" / "common" / "python"
sys.path.insert(0, str(layers_path))

from common import constants


class TestEnhancedConstants(unittest.TestCase):
    """Test enhanced constants module with dynamic configuration."""

    def setUp(self):
        """Set up test environment."""
        # Store original environment variables
        self.original_env = {}
        env_vars = [
            'AGGREGATION_WINDOW_SECONDS',
            'DIRECTORY_CONSOLIDATION_THRESHOLD', 
            'CONSOLIDATION_STOP_LEVEL',
            'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD',
            'ORIGIN_PATH_PATTERN'
        ]
        for var in env_vars:
            self.original_env[var] = os.environ.get(var)
            # Clear environment variables for clean testing
            if var in os.environ:
                del os.environ[var]

    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment variables
        for var, value in self.original_env.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]

    def test_aggregation_window_seconds_environment_variable_reading(self):
        """Test AGGREGATION_WINDOW_SECONDS reads from environment variable."""
        # Test with valid environment variable
        with patch.dict(os.environ, {'AGGREGATION_WINDOW_SECONDS': '600'}):
            # Reload the module to pick up new environment variable
            import importlib
            from common import constants as reloaded_constants
            importlib.reload(reloaded_constants)
            self.assertEqual(reloaded_constants.AGGREGATION_WINDOW_SECONDS, 600)

    def test_directory_consolidation_threshold_environment_variable_reading(self):
        """Test DIRECTORY_CONSOLIDATION_THRESHOLD reads from environment variable."""
        # Test with valid environment variable
        with patch.dict(os.environ, {'DIRECTORY_CONSOLIDATION_THRESHOLD': '5'}):
            import importlib
            from common import constants as reloaded_constants
            importlib.reload(reloaded_constants)
            self.assertEqual(reloaded_constants.DIRECTORY_CONSOLIDATION_THRESHOLD, 5)

    def test_consolidation_stop_level_environment_variable_reading(self):
        """Test CONSOLIDATION_STOP_LEVEL reads from environment variable."""
        # Test with valid environment variable
        with patch.dict(os.environ, {'CONSOLIDATION_STOP_LEVEL': '2'}):
            import importlib
            from common import constants as reloaded_constants
            importlib.reload(reloaded_constants)
            self.assertEqual(reloaded_constants.CONSOLIDATION_STOP_LEVEL, 2)

    def test_sibling_directory_consolidation_threshold_environment_variable_reading(self):
        """Test SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD reads from environment variable."""
        # Test with valid environment variable
        with patch.dict(os.environ, {'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD': '15'}):
            import importlib
            from common import constants as reloaded_constants
            importlib.reload(reloaded_constants)
            self.assertEqual(reloaded_constants.SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD, 15)

    def test_fallback_to_hardcoded_defaults_when_environment_variables_missing(self):
        """Test fallback to hardcoded defaults when environment variables are missing."""
        # Ensure no environment variables are set
        env_vars = ['AGGREGATION_WINDOW_SECONDS', 'DIRECTORY_CONSOLIDATION_THRESHOLD', 'CONSOLIDATION_STOP_LEVEL', 'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD']
        with patch.dict(os.environ, {}, clear=True):
            # Remove any existing env vars
            for var in env_vars:
                if var in os.environ:
                    del os.environ[var]
            
            import importlib
            from common import constants as reloaded_constants
            importlib.reload(reloaded_constants)
            
            # Check defaults
            self.assertEqual(reloaded_constants.AGGREGATION_WINDOW_SECONDS, 300)  # 5 minutes default
            self.assertEqual(reloaded_constants.DIRECTORY_CONSOLIDATION_THRESHOLD, 3)  # Default threshold
            self.assertEqual(reloaded_constants.CONSOLIDATION_STOP_LEVEL, 1)  # Default stop level
            self.assertEqual(reloaded_constants.SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD, 10)  # Default sibling threshold

    def test_handling_of_invalid_environment_variable_values(self):
        """Test handling of invalid environment variable values."""
        # Test with non-numeric values
        with patch.dict(os.environ, {
            'AGGREGATION_WINDOW_SECONDS': 'invalid',
            'DIRECTORY_CONSOLIDATION_THRESHOLD': 'not_a_number',
            'CONSOLIDATION_STOP_LEVEL': 'bad_value',
            'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD': 'invalid_sibling'
        }):
            import importlib
            from common import constants as reloaded_constants
            importlib.reload(reloaded_constants)
            
            # Should fall back to defaults
            self.assertEqual(reloaded_constants.AGGREGATION_WINDOW_SECONDS, 300)
            self.assertEqual(reloaded_constants.DIRECTORY_CONSOLIDATION_THRESHOLD, 3)
            self.assertEqual(reloaded_constants.CONSOLIDATION_STOP_LEVEL, 1)
            self.assertEqual(reloaded_constants.SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD, 10)

    def test_handling_of_out_of_range_environment_variable_values(self):
        """Test handling of out-of-range environment variable values."""
        # Test with values outside valid ranges
        with patch.dict(os.environ, {
            'AGGREGATION_WINDOW_SECONDS': '100000',  # Too high (max 86400)
            'DIRECTORY_CONSOLIDATION_THRESHOLD': '2000',  # Too high (max 1000)
            'CONSOLIDATION_STOP_LEVEL': '-1',  # Too low (min 0)
            'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD': '2000'  # Too high (max 1000)
        }):
            import importlib
            from common import constants as reloaded_constants
            importlib.reload(reloaded_constants)
            
            # Should fall back to defaults
            self.assertEqual(reloaded_constants.AGGREGATION_WINDOW_SECONDS, 300)
            self.assertEqual(reloaded_constants.DIRECTORY_CONSOLIDATION_THRESHOLD, 3)
            self.assertEqual(reloaded_constants.CONSOLIDATION_STOP_LEVEL, 1)
            self.assertEqual(reloaded_constants.SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD, 10)

    def test_boundary_values_for_environment_variables(self):
        """Test boundary values for environment variables."""
        # Test minimum valid values
        with patch.dict(os.environ, {
            'AGGREGATION_WINDOW_SECONDS': '1',  # Min value
            'DIRECTORY_CONSOLIDATION_THRESHOLD': '1',  # Min value
            'CONSOLIDATION_STOP_LEVEL': '0',  # Min value
            'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD': '1'  # Min value
        }):
            import importlib
            from common import constants as reloaded_constants
            importlib.reload(reloaded_constants)
            
            self.assertEqual(reloaded_constants.AGGREGATION_WINDOW_SECONDS, 1)
            self.assertEqual(reloaded_constants.DIRECTORY_CONSOLIDATION_THRESHOLD, 1)
            self.assertEqual(reloaded_constants.CONSOLIDATION_STOP_LEVEL, 0)
            self.assertEqual(reloaded_constants.SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD, 1)

        # Test maximum valid values
        with patch.dict(os.environ, {
            'AGGREGATION_WINDOW_SECONDS': '86400',  # Max value (24 hours)
            'DIRECTORY_CONSOLIDATION_THRESHOLD': '1000',  # Max value
            'CONSOLIDATION_STOP_LEVEL': '20',  # Max value (updated from 1000 to 20)
            'SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD': '1000'  # Max value
        }):
            import importlib
            from common import constants as reloaded_constants
            importlib.reload(reloaded_constants)
            
            self.assertEqual(reloaded_constants.AGGREGATION_WINDOW_SECONDS, 86400)
            self.assertEqual(reloaded_constants.DIRECTORY_CONSOLIDATION_THRESHOLD, 1000)
            self.assertEqual(reloaded_constants.CONSOLIDATION_STOP_LEVEL, 20)
            self.assertEqual(reloaded_constants.SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD, 1000)

    def test_validation_helper_function(self):
        """Test the _get_validated_int_env helper function directly."""
        # Test valid value
        with patch.dict(os.environ, {'TEST_VAR': '50'}):
            result = constants._get_validated_int_env('TEST_VAR', 10, 1, 100)
            self.assertEqual(result, 50)

        # Test missing environment variable
        if 'TEST_VAR' in os.environ:
            del os.environ['TEST_VAR']
        result = constants._get_validated_int_env('TEST_VAR', 10, 1, 100)
        self.assertEqual(result, 10)  # Should return default

        # Test invalid value (non-numeric)
        with patch.dict(os.environ, {'TEST_VAR': 'invalid'}):
            result = constants._get_validated_int_env('TEST_VAR', 10, 1, 100)
            self.assertEqual(result, 10)  # Should return default

        # Test out of range value (too low)
        with patch.dict(os.environ, {'TEST_VAR': '0'}):
            result = constants._get_validated_int_env('TEST_VAR', 10, 1, 100)
            self.assertEqual(result, 10)  # Should return default

        # Test out of range value (too high)
        with patch.dict(os.environ, {'TEST_VAR': '200'}):
            result = constants._get_validated_int_env('TEST_VAR', 10, 1, 100)
            self.assertEqual(result, 10)  # Should return default


class TestOriginPathPatternConstants(unittest.TestCase):
    """Test origin path pattern constants and configuration."""

    def setUp(self):
        """Set up test environment."""
        # Store original environment variable
        self.original_origin_path_pattern = os.environ.get('ORIGIN_PATH_PATTERN')
        # Clear environment variable for clean testing
        if 'ORIGIN_PATH_PATTERN' in os.environ:
            del os.environ['ORIGIN_PATH_PATTERN']

    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment variable
        if self.original_origin_path_pattern is not None:
            os.environ['ORIGIN_PATH_PATTERN'] = self.original_origin_path_pattern
        elif 'ORIGIN_PATH_PATTERN' in os.environ:
            del os.environ['ORIGIN_PATH_PATTERN']

    def test_origin_path_pattern_default_value(self):
        """Test ORIGIN_PATH_PATTERN has correct default value."""
        # Ensure no environment variable is set
        if 'ORIGIN_PATH_PATTERN' in os.environ:
            del os.environ['ORIGIN_PATH_PATTERN']
        
        import importlib
        from common import constants as reloaded_constants
        importlib.reload(reloaded_constants)
        
        self.assertEqual(reloaded_constants.ORIGIN_PATH_PATTERN, '/{stageId}/public')

    def test_origin_path_pattern_environment_variable_override(self):
        """Test ORIGIN_PATH_PATTERN reads from environment variable."""
        # Test with custom pattern
        with patch.dict(os.environ, {'ORIGIN_PATH_PATTERN': '/custom/path'}):
            import importlib
            from common import constants as reloaded_constants
            importlib.reload(reloaded_constants)
            
            self.assertEqual(reloaded_constants.ORIGIN_PATH_PATTERN, '/custom/path')

    def test_origin_path_pattern_empty_environment_variable_fallback(self):
        """Test ORIGIN_PATH_PATTERN falls back to default when environment variable is empty."""
        # Test with empty string
        with patch.dict(os.environ, {'ORIGIN_PATH_PATTERN': ''}):
            import importlib
            from common import constants as reloaded_constants
            importlib.reload(reloaded_constants)
            
            self.assertEqual(reloaded_constants.ORIGIN_PATH_PATTERN, '/{stageId}/public')

    def test_public_path_segment_constant(self):
        """Test PUBLIC_PATH_SEGMENT has correct value."""
        import importlib
        from common import constants as reloaded_constants
        importlib.reload(reloaded_constants)
        
        self.assertEqual(reloaded_constants.PUBLIC_PATH_SEGMENT, 'public')

    def test_production_stage_identifiers_constant(self):
        """Test PRODUCTION_STAGE_IDENTIFIERS has correct values."""
        import importlib
        from common import constants as reloaded_constants
        importlib.reload(reloaded_constants)
        
        expected = ['prod', 'beta', 'stage', 'staging']
        self.assertEqual(reloaded_constants.PRODUCTION_STAGE_IDENTIFIERS, expected)

    def test_non_production_stage_identifiers_constant(self):
        """Test NON_PRODUCTION_STAGE_IDENTIFIERS has correct values."""
        import importlib
        from common import constants as reloaded_constants
        importlib.reload(reloaded_constants)
        
        expected = ['dev', 'test']
        self.assertEqual(reloaded_constants.NON_PRODUCTION_STAGE_IDENTIFIERS, expected)

    def test_origin_path_depth_constant_removed(self):
        """Test ORIGIN_PATH_DEPTH constant has been removed."""
        import importlib
        from common import constants as reloaded_constants
        importlib.reload(reloaded_constants)
        
        # Verify the constant no longer exists
        self.assertFalse(hasattr(reloaded_constants, 'ORIGIN_PATH_DEPTH'))


if __name__ == '__main__':
    unittest.main()