#!/usr/bin/env python3
"""
Comprehensive validation test for the sibling threshold parameter fix.

This script validates all aspects of the consolidation-stop-level-depth-fix
to ensure the implementation is correct and complete.
"""

import sys
import os
import time
import traceback
from typing import List, Dict, Any

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

# Mock the common.window_tracker module
mock_window_tracker = mock.MagicMock()
mock_window_tracker.close_window = mock.MagicMock()

sys.modules['common'] = mock.MagicMock()
sys.modules['common.constants'] = mock_constants
sys.modules['common.logger'] = mock_logger
sys.modules['common.window_tracker'] = mock_window_tracker

# Now import the modules we need to test
from processor.path_consolidator import consolidate_paths, consolidate_sibling_directories


class ValidationTest:
    """Base class for validation tests."""
    
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error = None
    
    def run(self) -> bool:
        """Run the test and return True if passed."""
        try:
            self.execute()
            self.passed = True
            return True
        except Exception as e:
            self.error = str(e)
            self.passed = False
            return False
    
    def execute(self):
        """Override this method to implement the test."""
        raise NotImplementedError
    
    def report(self):
        """Report test results."""
        status = "✅ PASS" if self.passed else "❌ FAIL"
        print(f"{status} {self.name}")
        if not self.passed and self.error:
            print(f"    Error: {self.error}")


class UserScenarioTest(ValidationTest):
    """Test the user's specific scenario."""
    
    def __init__(self):
        super().__init__("User's Specific Scenario (4 siblings, threshold=2)")
    
    def execute(self):
        # User's exact scenario: 4 sibling directories with threshold=2 should consolidate to parent
        paths = ['/prod/public/m/*', '/prod/public/k/*', '/prod/public/w/*', '/prod/public/x/*']
        result = consolidate_paths(paths, sibling_threshold=2, stop_level=1)
        
        expected = [['/prod/public/*']]
        if result != expected:
            raise AssertionError(f"Expected {expected}, got {result}")


class BoundaryConditionTest(ValidationTest):
    """Test boundary conditions for sibling threshold."""
    
    def __init__(self):
        super().__init__("Sibling Threshold Boundary Conditions")
    
    def execute(self):
        paths = ['/prod/public/m/*', '/prod/public/k/*', '/prod/public/w/*', '/prod/public/x/*']
        
        # Test at threshold (should NOT consolidate)
        result_at = consolidate_paths(paths, sibling_threshold=4, stop_level=1)
        if len(result_at[0]) != 4:
            raise AssertionError(f"At threshold=4, should have 4 paths, got {len(result_at[0])}")
        
        # Test above threshold (should consolidate)
        result_above = consolidate_paths(paths, sibling_threshold=3, stop_level=1)
        expected_above = [['/prod/public/*']]
        if result_above != expected_above:
            raise AssertionError(f"Above threshold=3, expected {expected_above}, got {result_above}")


class BackwardCompatibilityTest(ValidationTest):
    """Test backward compatibility with missing parameter."""
    
    def __init__(self):
        super().__init__("Backward Compatibility (missing sibling_threshold)")
    
    def execute(self):
        paths = ['/prod/public/m/*', '/prod/public/k/*', '/prod/public/w/*', '/prod/public/x/*']
        
        # Test without sibling_threshold parameter (should use default 10)
        result_no_param = consolidate_paths(paths, stop_level=1)
        # With default threshold 10, 4 siblings should NOT consolidate
        if len(result_no_param[0]) != 4:
            raise AssertionError(f"Without sibling_threshold, should have 4 paths, got {len(result_no_param[0])}")
        
        # Test with sibling_threshold=None (should use default 10)
        result_none = consolidate_paths(paths, sibling_threshold=None, stop_level=1)
        if result_none != result_no_param:
            raise AssertionError("sibling_threshold=None should behave same as missing parameter")


class ParameterPassingTest(ValidationTest):
    """Test that sibling_threshold parameter is passed correctly through the call chain."""
    
    def __init__(self):
        super().__init__("Parameter Passing Through Call Chain")
    
    def execute(self):
        # Test consolidate_sibling_directories directly
        paths = {'/prod/public/m/*', '/prod/public/k/*', '/prod/public/w/*'}
        
        # With threshold=2, should consolidate (3 > 2)
        result_low = consolidate_sibling_directories(paths, sibling_threshold=2, stop_level=1)
        if '/prod/public/*' not in result_low:
            raise AssertionError(f"Direct call with threshold=2 should consolidate, got {result_low}")
        
        # With threshold=5, should NOT consolidate (3 <= 5)
        result_high = consolidate_sibling_directories(paths, sibling_threshold=5, stop_level=1)
        if len(result_high) != 3:
            raise AssertionError(f"Direct call with threshold=5 should not consolidate, got {result_high}")


class StopLevelInteractionTest(ValidationTest):
    """Test interaction between sibling threshold and stop level."""
    
    def __init__(self):
        super().__init__("Sibling Threshold + Stop Level Interaction")
    
    def execute(self):
        paths = ['/prod/public/m/*', '/prod/public/k/*', '/prod/public/w/*', '/prod/public/x/*']
        
        # With stop_level=2, should prevent consolidation at depth 1 (public level)
        result_blocked = consolidate_paths(paths, sibling_threshold=2, stop_level=2)
        if len(result_blocked[0]) != 4:
            raise AssertionError(f"Stop level=2 should prevent consolidation, got {result_blocked}")
        
        # With stop_level=1, should allow consolidation at depth 1 (public level)
        result_allowed = consolidate_paths(paths, sibling_threshold=2, stop_level=1)
        expected_allowed = [['/prod/public/*']]
        if result_allowed != expected_allowed:
            raise AssertionError(f"Stop level=1 should allow consolidation, got {result_allowed}")


class EdgeCaseTest(ValidationTest):
    """Test edge cases for sibling threshold."""
    
    def __init__(self):
        super().__init__("Edge Cases (empty paths, single path, extreme values)")
    
    def execute(self):
        # Empty paths
        result_empty = consolidate_paths([], sibling_threshold=2)
        if result_empty != [[]]:
            raise AssertionError(f"Empty paths should return [[]], got {result_empty}")
        
        # Single path
        result_single = consolidate_paths(['/prod/public/test.html'], sibling_threshold=2)
        if result_single != [['/prod/public/test.html']]:
            raise AssertionError(f"Single path should be unchanged, got {result_single}")
        
        # Very low threshold (0)
        paths = ['/prod/public/m/*', '/prod/public/k/*']
        result_zero = consolidate_paths(paths, sibling_threshold=0, stop_level=1)
        # With threshold=0, any siblings consolidate, and it may recurse up further
        # The important thing is that consolidation occurred
        if len(result_zero[0]) >= 2:
            raise AssertionError(f"Threshold=0 should consolidate siblings, got {result_zero}")
        
        # Very high threshold (1000)
        result_high = consolidate_paths(paths, sibling_threshold=1000, stop_level=1)
        if len(result_high[0]) != 2:
            raise AssertionError(f"Threshold=1000 should not consolidate 2 siblings, got {result_high}")


class PerformanceTest(ValidationTest):
    """Test performance with large numbers of sibling directories."""
    
    def __init__(self):
        super().__init__("Performance with Large Input")
    
    def execute(self):
        # Create 100 sibling directories
        paths = [f'/prod/public/sibling{i:03d}/*' for i in range(100)]
        
        start_time = time.time()
        result = consolidate_paths(paths, sibling_threshold=50, stop_level=1)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # Should consolidate to parent (100 > 50)
        expected = [['/prod/public/*']]
        if result != expected:
            raise AssertionError(f"Large input should consolidate to parent, got {result}")
        
        # Should complete in reasonable time (< 1 second for 100 paths)
        if execution_time > 1.0:
            raise AssertionError(f"Performance test took too long: {execution_time:.2f} seconds")


class ComplexScenarioTest(ValidationTest):
    """Test complex scenarios with mixed consolidation."""
    
    def __init__(self):
        super().__init__("Complex Mixed Consolidation Scenarios")
    
    def execute(self):
        # Mix of files and directories that should trigger multiple consolidation phases
        paths = [
            # These should consolidate to /prod/public/dir1/*
            '/prod/public/dir1/file1.html',
            '/prod/public/dir1/file2.html', 
            '/prod/public/dir1/file3.html',
            '/prod/public/dir1/file4.html',
            # These should consolidate to /prod/public/dir2/*
            '/prod/public/dir2/file1.html',
            '/prod/public/dir2/file2.html',
            '/prod/public/dir2/file3.html',
            '/prod/public/dir2/file4.html',
            # These should consolidate to /prod/public/dir3/*
            '/prod/public/dir3/file1.html',
            '/prod/public/dir3/file2.html',
            '/prod/public/dir3/file3.html',
            '/prod/public/dir3/file4.html',
        ]
        
        # With sibling_threshold=2, the 3 directory wildcards should consolidate to parent
        result = consolidate_paths(paths, sibling_threshold=2, stop_level=1)
        expected = [['/prod/public/*']]
        
        if result != expected:
            raise AssertionError(f"Complex scenario should consolidate to parent, got {result}")


def run_all_tests() -> bool:
    """Run all validation tests and return True if all pass."""
    tests = [
        UserScenarioTest(),
        BoundaryConditionTest(),
        BackwardCompatibilityTest(),
        ParameterPassingTest(),
        StopLevelInteractionTest(),
        EdgeCaseTest(),
        PerformanceTest(),
        ComplexScenarioTest(),
    ]
    
    print("🧪 Running Comprehensive Validation Tests for Sibling Threshold Fix")
    print("=" * 70)
    
    passed_count = 0
    total_count = len(tests)
    
    for test in tests:
        success = test.run()
        test.report()
        if success:
            passed_count += 1
    
    print("=" * 70)
    print(f"Results: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("🎉 All validation tests passed! The sibling threshold fix is working correctly.")
        return True
    else:
        print("❌ Some validation tests failed. Please review the implementation.")
        return False


def main():
    """Main function."""
    print("Comprehensive Validation Test for Consolidation Stop Level Depth Fix")
    print("Feature: consolidation-stop-level-depth-fix")
    print("Task: 7.2 Performance and error handling validation")
    print()
    
    success = run_all_tests()
    
    if success:
        print("\n✅ VALIDATION COMPLETE: All tests passed!")
        print("The sibling threshold parameter fix is ready for production.")
    else:
        print("\n❌ VALIDATION FAILED: Some tests did not pass.")
        print("Please review the implementation before deploying.")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())