#!/usr/bin/env python3
"""Test script for user's specific scenario."""

import sys
import os

# Add the functions directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'functions'))

# Mock the common module imports
import unittest.mock as mock

# Mock the common.constants module
mock_constants = mock.MagicMock()
mock_constants.DIRECTORY_CONSOLIDATION_THRESHOLD = 3
mock_constants.SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD = 10
mock_constants.MAX_PATHS_PER_INVALIDATION = 1000
mock_constants.INDEX_FILE_PATTERNS = ['index', 'default']
mock_constants.CONSOLIDATION_STOP_LEVEL = 1

# Mock the common.logger module
mock_logger = mock.MagicMock()
mock_logger.setup_logger.return_value = mock.MagicMock()

sys.modules['common'] = mock.MagicMock()
sys.modules['common.constants'] = mock_constants
sys.modules['common.logger'] = mock_logger

# Now import the path consolidator
from processor.path_consolidator import consolidate_paths

def test_user_scenario():
    """Test user's specific scenario."""
    print("Testing user's specific scenario...")
    
    # User's exact scenario: 4 sibling directories with threshold=2 should consolidate to parent
    paths = ['/prod/public/m/*', '/prod/public/k/*', '/prod/public/w/*', '/prod/public/x/*']
    result = consolidate_paths(paths, sibling_threshold=2, stop_level=1)
    
    print(f"Input: {paths}")
    print(f"Output: {result}")
    print(f"Expected: [['/prod/public/*']]")
    
    # Verify result
    expected = [['/prod/public/*']]
    success = result == expected
    print(f"Success: {success}")
    
    if not success:
        print(f"ERROR: Expected {expected}, got {result}")
        return False
    
    # Test boundary condition - should NOT consolidate when count equals threshold
    print("\nTesting boundary condition (threshold=4, should NOT consolidate)...")
    result_boundary = consolidate_paths(paths, sibling_threshold=4, stop_level=1)
    print(f"Output: {result_boundary}")
    
    # Should have 4 individual paths
    boundary_success = len(result_boundary) == 1 and len(result_boundary[0]) == 4
    print(f"Success: {boundary_success}")
    
    if not boundary_success:
        print(f"ERROR: Expected 4 individual paths, got {result_boundary}")
        return False
    
    # Test with threshold=3 - should consolidate since 4 > 3
    print("\nTesting threshold=3 (should consolidate since 4 > 3)...")
    result_above = consolidate_paths(paths, sibling_threshold=3, stop_level=1)
    print(f"Output: {result_above}")
    
    above_success = result_above == [['/prod/public/*']]
    print(f"Success: {above_success}")
    
    if not above_success:
        print(f"ERROR: Expected [['/prod/public/*']], got {result_above}")
        return False
    
    print("\nAll tests passed! ✅")
    return True

if __name__ == "__main__":
    success = test_user_scenario()
    sys.exit(0 if success else 1)