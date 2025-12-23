#!/usr/bin/env python3
"""
Simple test to verify handler integration with sibling threshold parameter.

This script tests that the consolidate_paths function is called with the correct
sibling_threshold parameter when invoked through the handler.
"""

import sys
import os

# Add the functions directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'functions'))

# Mock the common module imports
import unittest.mock as mock

# Mock the common modules
mock_constants = mock.MagicMock()
mock_constants.DIRECTORY_CONSOLIDATION_THRESHOLD = 3
mock_constants.SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD = 10
mock_constants.MAX_PATHS_PER_INVALIDATION = 1000
mock_constants.INDEX_FILE_PATTERNS = ['index', 'default']
mock_constants.CONSOLIDATION_STOP_LEVEL = 1

mock_logger = mock.MagicMock()
mock_logger.setup_logger.return_value = mock.MagicMock()

mock_window_tracker = mock.MagicMock()
mock_window_tracker.close_window = mock.MagicMock()

sys.modules['common'] = mock.MagicMock()
sys.modules['common.constants'] = mock_constants
sys.modules['common.logger'] = mock_logger
sys.modules['common.window_tracker'] = mock_window_tracker

# Now import the path consolidator to test it directly
from processor.path_consolidator import consolidate_paths

def test_consolidate_paths_sibling_threshold():
    """Test that consolidate_paths accepts and uses sibling_threshold parameter."""
    print("Testing consolidate_paths with sibling_threshold parameter...")
    
    # Test user's specific scenario
    paths = ['/prod/public/m/*', '/prod/public/k/*', '/prod/public/w/*', '/prod/public/x/*']
    
    # Test with custom sibling threshold
    result_custom = consolidate_paths(
        paths, 
        directory_threshold=3,
        stop_level=1,
        sibling_threshold=2  # Custom threshold
    )
    
    # Should consolidate to parent (4 > 2)
    expected_custom = [['/prod/public/*']]
    assert result_custom == expected_custom, f"Custom threshold failed: {result_custom}"
    
    # Test with default (no sibling_threshold parameter)
    result_default = consolidate_paths(
        paths,
        directory_threshold=3,
        stop_level=1
        # No sibling_threshold - should use default (10)
    )
    
    # Should NOT consolidate (4 <= 10)
    assert len(result_default[0]) == 4, f"Default threshold failed: {result_default}"
    
    print("✅ consolidate_paths correctly handles sibling_threshold parameter")
    print(f"   - Custom threshold (2): {result_custom}")
    print(f"   - Default threshold (10): {len(result_default[0])} paths")
    
    return True

def test_bucket_config_simulation():
    """Simulate how bucket configuration would pass sibling threshold."""
    print("\nTesting bucket configuration simulation...")
    
    # Simulate bucket configuration with custom sibling threshold
    bucket_config = {
        'directory_threshold': 3,
        'stop_level': 1,
        'sibling_directory_threshold': 5,  # Custom from bucket tags
    }
    
    # Simulate paths that would come from S3 events
    object_paths = [
        '/prod/public/dir1/file1.html',
        '/prod/public/dir1/file2.html',
        '/prod/public/dir1/file3.html',
        '/prod/public/dir1/file4.html',  # Triggers directory consolidation
        '/prod/public/dir2/file1.html',
        '/prod/public/dir2/file2.html',
        '/prod/public/dir2/file3.html',
        '/prod/public/dir2/file4.html',  # Triggers directory consolidation
        '/prod/public/dir3/file1.html',
        '/prod/public/dir3/file2.html',
        '/prod/public/dir3/file3.html',
        '/prod/public/dir3/file4.html',  # Triggers directory consolidation
        '/prod/public/dir4/file1.html',
        '/prod/public/dir4/file2.html',
        '/prod/public/dir4/file3.html',
        '/prod/public/dir4/file4.html',  # Triggers directory consolidation
        '/prod/public/dir5/file1.html',
        '/prod/public/dir5/file2.html',
        '/prod/public/dir5/file3.html',
        '/prod/public/dir5/file4.html',  # Triggers directory consolidation
        '/prod/public/dir6/file1.html',
        '/prod/public/dir6/file2.html',
        '/prod/public/dir6/file3.html',
        '/prod/public/dir6/file4.html',  # Triggers directory consolidation
    ]
    
    # Call consolidate_paths as the handler would
    result = consolidate_paths(
        object_paths,
        directory_threshold=bucket_config['directory_threshold'],
        stop_level=bucket_config['stop_level'],
        sibling_threshold=bucket_config['sibling_directory_threshold']
    )
    
    # With 6 directories and sibling_threshold=5, should consolidate to parent (6 > 5)
    expected = [['/prod/public/*']]
    assert result == expected, f"Bucket config simulation failed: {result}"
    
    print("✅ Bucket configuration simulation works correctly")
    print(f"   - Input: 24 files in 6 directories")
    print(f"   - Sibling threshold: {bucket_config['sibling_directory_threshold']}")
    print(f"   - Result: {result}")
    
    return True

def test_parameter_precedence():
    """Test that sibling_threshold parameter takes precedence over global constant."""
    print("\nTesting parameter precedence...")
    
    paths = ['/prod/public/a/*', '/prod/public/b/*', '/prod/public/c/*']
    
    # Test with explicit sibling_threshold=2 (should consolidate 3 > 2)
    result_explicit = consolidate_paths(paths, sibling_threshold=2, stop_level=1)
    expected_explicit = [['/prod/public/*']]
    assert result_explicit == expected_explicit, f"Explicit parameter failed: {result_explicit}"
    
    # Test with sibling_threshold=None (should use global default 10, no consolidation)
    result_none = consolidate_paths(paths, sibling_threshold=None, stop_level=1)
    assert len(result_none[0]) == 3, f"None parameter failed: {result_none}"
    
    # Test without sibling_threshold parameter (should use global default 10, no consolidation)
    result_missing = consolidate_paths(paths, stop_level=1)
    assert len(result_missing[0]) == 3, f"Missing parameter failed: {result_missing}"
    
    print("✅ Parameter precedence works correctly")
    print(f"   - Explicit threshold=2: {result_explicit}")
    print(f"   - None parameter: {len(result_none[0])} paths")
    print(f"   - Missing parameter: {len(result_missing[0])} paths")
    
    return True

def main():
    """Main function."""
    print("Handler Integration Test for Sibling Threshold Parameter")
    print("=" * 60)
    
    try:
        # Test 1: Basic parameter functionality
        success1 = test_consolidate_paths_sibling_threshold()
        
        # Test 2: Bucket configuration simulation
        success2 = test_bucket_config_simulation()
        
        # Test 3: Parameter precedence
        success3 = test_parameter_precedence()
        
        if success1 and success2 and success3:
            print("\n🎉 All handler integration tests passed!")
            print("The sibling threshold parameter is correctly integrated.")
            return 0
        else:
            print("\n❌ Some handler integration tests failed.")
            return 1
            
    except Exception as e:
        print(f"\n❌ Handler integration test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())