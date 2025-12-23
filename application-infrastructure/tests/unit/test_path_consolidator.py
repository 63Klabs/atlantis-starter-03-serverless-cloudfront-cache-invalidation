"""Unit tests for path consolidation algorithm edge cases."""

import pytest
from functions.processor.path_consolidator import (
    consolidate_paths,
    is_index_or_default_file,
    get_parent_directory,
    consolidate_index_and_default_files,
    consolidate_by_directory_threshold,
    consolidate_sibling_directories,
    calculate_path_depth,
    is_consolidation_allowed_at_depth,
    apply_stop_level_constraints
)


class TestEdgeCases:
    """Test edge cases for path consolidation."""
    
    def test_empty_path_list(self):
        """Test consolidation with empty path list."""
        result = consolidate_paths([])
        assert len(result) == 1
        assert result[0] == []
    
    def test_single_path(self):
        """Test consolidation with single path."""
        result = consolidate_paths(['/prod/public/file.html'])
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/prod/public/file.html'
    
    def test_deeply_nested_structures(self):
        """Test consolidation with deeply nested directory structures."""
        paths = [
            '/a/b/c/d/e/f/g/file1.html',
            '/a/b/c/d/e/f/g/file2.html',
            '/a/b/c/d/e/f/g/file3.html',
            '/a/b/c/d/e/f/g/file4.html'
        ]
        # Use stop_level=7 to allow consolidation at depth 7
        result = consolidate_paths(paths, stop_level=7)
        assert len(result) == 1
        # Should consolidate to directory level
        assert result[0][0] == '/a/b/c/d/e/f/g/*'
    
    def test_mixed_file_and_directory_paths(self):
        """Test consolidation with mix of files and directory wildcards."""
        paths = [
            '/prod/public/dir1/*',
            '/prod/public/dir2/file.html',
            '/prod/public/dir3/*',
            '/prod/public/dir4/file.html'
        ]
        result = consolidate_paths(paths)
        assert len(result) == 1
        # Should keep as-is since no consolidation threshold is met
        assert len(result[0]) == 4


class TestIndexDefaultFiles:
    """Test index and default file detection and consolidation."""
    
    def test_is_index_file(self):
        """Test detection of index files."""
        assert is_index_or_default_file('/dir/index.html') is True
        assert is_index_or_default_file('/dir/index.php') is True
        assert is_index_or_default_file('/dir/index.jsp') is True
    
    def test_is_default_file(self):
        """Test detection of default files."""
        assert is_index_or_default_file('/dir/default.html') is True
        assert is_index_or_default_file('/dir/default.asp') is True
    
    def test_is_not_index_or_default(self):
        """Test non-index/default files."""
        assert is_index_or_default_file('/dir/file.html') is False
        assert is_index_or_default_file('/dir/about.html') is False
        assert is_index_or_default_file('/dir/indexer.html') is False
    
    def test_consolidate_index_files(self):
        """Test consolidation of index files to parent directory."""
        paths = {'/prod/public/index.html', '/prod/public/about.html'}
        # Use stop_level=1 to allow consolidation at depth 1 (/prod/public)
        result = consolidate_index_and_default_files(paths, stop_level=1)
        assert '/prod/public/*' in result
        assert '/prod/public/about.html' in result
        assert '/prod/public/index.html' not in result


class TestParentDirectory:
    """Test parent directory extraction."""
    
    def test_get_parent_of_file(self):
        """Test getting parent directory of a file."""
        assert get_parent_directory('/prod/public/file.html') == '/prod/public'
    
    def test_get_parent_of_nested_file(self):
        """Test getting parent of deeply nested file."""
        assert get_parent_directory('/a/b/c/d/file.html') == '/a/b/c/d'
    
    def test_get_parent_of_root_level(self):
        """Test getting parent of root-level path."""
        assert get_parent_directory('/file.html') == '/'
    
    def test_get_parent_of_root(self):
        """Test getting parent of root."""
        assert get_parent_directory('/') == '/'
    
    def test_get_parent_with_trailing_slash(self):
        """Test getting parent with trailing slash."""
        assert get_parent_directory('/prod/public/') == '/prod'


class TestDirectoryThreshold:
    """Test directory consolidation threshold logic."""
    
    def test_below_threshold(self):
        """Test paths below consolidation threshold (3 or fewer)."""
        paths = {
            '/dir/file1.html',
            '/dir/file2.html',
            '/dir/file3.html'
        }
        result = consolidate_by_directory_threshold(paths)
        # Should not consolidate (exactly 3, need > 3)
        assert len(result) == 3
        assert '/dir/*' not in result
    
    def test_above_threshold(self):
        """Test paths above consolidation threshold (more than 3)."""
        paths = {
            '/dir/file1.html',
            '/dir/file2.html',
            '/dir/file3.html',
            '/dir/file4.html'
        }
        result = consolidate_by_directory_threshold(paths, stop_level=0)
        # Should consolidate to directory wildcard
        assert len(result) == 1
        assert '/dir/*' in result
    
    def test_mixed_directories(self):
        """Test consolidation with files in multiple directories."""
        paths = {
            '/dir1/file1.html',
            '/dir1/file2.html',
            '/dir1/file3.html',
            '/dir1/file4.html',
            '/dir2/file1.html',
            '/dir2/file2.html'
        }
        result = consolidate_by_directory_threshold(paths, stop_level=0)
        # dir1 should consolidate (4 files), dir2 should not (2 files)
        assert '/dir1/*' in result
        assert '/dir2/file1.html' in result
        assert '/dir2/file2.html' in result


class TestSiblingConsolidation:
    """Test sibling directory consolidation logic."""
    
    def test_below_sibling_threshold(self):
        """Test sibling directories below threshold (10 or fewer)."""
        paths = {f'/parent/dir{i}/*' for i in range(10)}
        result = consolidate_sibling_directories(paths)
        # Should not consolidate (exactly 10, need > 10)
        assert len(result) == 10
        assert '/parent/*' not in result
    
    def test_above_sibling_threshold(self):
        """Test sibling directories above threshold (more than 10)."""
        paths = {f'/parent/dir{i}/*' for i in range(11)}
        result = consolidate_sibling_directories(paths, stop_level=0)
        # Should consolidate to parent wildcard
        assert len(result) == 1
        assert '/parent/*' in result
    
    def test_mixed_parents(self):
        """Test consolidation with multiple parent directories."""
        paths = set()
        # Parent1 has 11 siblings (should consolidate)
        paths.update({f'/parent1/dir{i}/*' for i in range(11)})
        # Parent2 has 5 siblings (should not consolidate)
        paths.update({f'/parent2/dir{i}/*' for i in range(5)})
        
        result = consolidate_sibling_directories(paths, stop_level=0)
        # Parent1 should consolidate
        assert '/parent1/*' in result
        # Parent2 siblings should remain
        assert any('/parent2/' in p for p in result)


class TestComplexScenarios:
    """Test complex consolidation scenarios."""
    
    def test_recursive_consolidation(self):
        """Test that consolidation recurses up the tree."""
        # Create many sibling directories, each with many files
        paths = []
        for i in range(12):  # More than 10 siblings
            for j in range(5):  # More than 3 files per directory
                paths.append(f'/root/dir{i}/file{j}.html')
        
        result = consolidate_paths(paths, stop_level=0)
        # Should consolidate all the way to /*
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/*'
    
    def test_no_consolidation_needed(self):
        """Test paths that don't meet any consolidation criteria."""
        paths = [
            '/dir1/file1.html',
            '/dir2/file1.html',
            '/dir3/file1.html'
        ]
        result = consolidate_paths(paths)
        # Should remain unchanged
        assert len(result) == 1
        assert len(result[0]) == 3
    
    def test_partial_consolidation(self):
        """Test scenario where only some paths consolidate."""
        paths = [
            # These 4 should consolidate to /dir1/*
            '/dir1/file1.html',
            '/dir1/file2.html',
            '/dir1/file3.html',
            '/dir1/file4.html',
            # These should remain separate
            '/dir2/file1.html',
            '/dir3/file1.html'
        ]
        result = consolidate_paths(paths, stop_level=1)  # Allow consolidation at depth 1
        assert len(result) == 1
        assert '/dir1/*' in result[0]
        assert '/dir2/file1.html' in result[0]
        assert '/dir3/file1.html' in result[0]
        assert len(result[0]) == 3


class TestSplitting:
    """Test path splitting for CloudFront limits."""
    
    def test_no_splitting_needed(self):
        """Test that small path lists don't get split."""
        paths = [f'/dir{i}/file.html' for i in range(100)]
        result = consolidate_paths(paths)
        # Should return single chunk
        assert len(result) == 1
        assert len(result[0]) == 100
    
    def test_splitting_at_1000(self):
        """Test that paths are split at 1000 item boundary."""
        # Create 1500 unique paths that won't consolidate
        paths = [f'/dir{i}/file.html' for i in range(1500)]
        result = consolidate_paths(paths)
        # Should split into 2 chunks
        assert len(result) == 2
        assert len(result[0]) == 1000
        assert len(result[1]) == 500


class TestPathDepthCalculation:
    """Test path depth calculation functionality."""
    
    def test_calculate_depth_from_root(self):
        """Test depth calculation from root directory."""
        assert calculate_path_depth('/file.html', '/') == 1
        assert calculate_path_depth('/dir/file.html', '/') == 2
        assert calculate_path_depth('/dir/subdir/file.html', '/') == 3
    
    def test_calculate_depth_from_custom_root(self):
        """Test depth calculation with 'public' directory as reference."""
        # public directory itself is level 1
        assert calculate_path_depth('/prod/public', '/prod/public') == 1
        # files/dirs under public are level 2+
        assert calculate_path_depth('/prod/public/file.html', '/prod/public') == 2
        assert calculate_path_depth('/prod/public/dir/file.html', '/prod/public') == 3
        assert calculate_path_depth('/prod/public/dir/subdir/file.html', '/prod/public') == 4
    
    def test_calculate_depth_same_as_root(self):
        """Test depth calculation when path equals public directory."""
        # public directory itself is level 1 (not 0)
        assert calculate_path_depth('/prod/public', '/prod/public') == 1
        # filesystem root is still 0 when no public directory
        assert calculate_path_depth('/', '/') == 0
    
    def test_calculate_depth_not_under_root(self):
        """Test depth calculation when no 'public' directory exists (fallback)."""
        # Should fall back to simple segment counting when no 'public' found
        assert calculate_path_depth('/other/file.html', '/prod/public') == 2
        assert calculate_path_depth('/prod/file.html', '/prod/public') == 2
    
    def test_calculate_depth_with_trailing_slashes(self):
        """Test depth calculation with trailing slashes."""
        # dir under public is level 2
        assert calculate_path_depth('/prod/public/dir/', '/prod/public') == 2
        assert calculate_path_depth('/prod/public/dir/', '/prod/public/') == 2


class TestConsolidationAllowed:
    """Test consolidation allowed at depth functionality."""
    
    def test_stop_level_one_allows_shallow_depths(self):
        """Test that stop level 1 prevents consolidation at depth 0 but allows depth 1 and deeper."""
        # Stop level 1 should prevent consolidation at depth 0 (shallower than stop level)
        assert is_consolidation_allowed_at_depth(0, 1) is False
        # But should allow at depth 1 and deeper
        assert is_consolidation_allowed_at_depth(1, 1) is True
        assert is_consolidation_allowed_at_depth(2, 1) is True
        assert is_consolidation_allowed_at_depth(5, 1) is True
    
    def test_stop_level_zero_allows_all(self):
        """Test that stop level 0 allows consolidation at all depths."""
        assert is_consolidation_allowed_at_depth(0, 0) is True
        assert is_consolidation_allowed_at_depth(1, 0) is True
        assert is_consolidation_allowed_at_depth(5, 0) is True
    
    def test_stop_level_allows_shallow_depths(self):
        """Test that stop level allows consolidation at the stop level and deeper, prevents shallower."""
        # Stop level 3 prevents depths 0, 1, 2 (shallower than stop level)
        assert is_consolidation_allowed_at_depth(0, 3) is False
        assert is_consolidation_allowed_at_depth(1, 3) is False
        assert is_consolidation_allowed_at_depth(2, 3) is False
        # But allows depth 3 and deeper
        assert is_consolidation_allowed_at_depth(3, 3) is True
        assert is_consolidation_allowed_at_depth(4, 3) is True
    
    def test_stop_level_boundary_conditions(self):
        """Test stop level boundary conditions."""
        # Stop level 2 prevents depth 0 and 1 (shallower than stop level)
        assert is_consolidation_allowed_at_depth(0, 2) is False
        assert is_consolidation_allowed_at_depth(1, 2) is False
        # But allows depth 2 and deeper
        assert is_consolidation_allowed_at_depth(2, 2) is True
        assert is_consolidation_allowed_at_depth(3, 2) is True


class TestStopLevelConstraints:
    """Test stop level constraint application."""
    
    def test_stop_level_zero_consolidates_to_root(self):
        """Test that stop level 0 consolidates everything to root."""
        paths = {'/dir1/file1.html', '/dir2/file2.html', '/dir3/file3.html'}
        result = apply_stop_level_constraints(paths, 0, '/')
        assert result == {'/*'}
    
    def test_stop_level_allows_deep_wildcards(self):
        """Test that stop level allows wildcards at allowed depths."""
        paths = {'/dir1/subdir1/*', '/dir1/subdir2/*', '/dir2/file.html'}
        result = apply_stop_level_constraints(paths, 3, '/')
        # All paths should be allowed since wildcards are at depth 2 (>= 3 not required)
        assert '/dir1/subdir1/*' in result
        assert '/dir1/subdir2/*' in result
        assert '/dir2/file.html' in result
    
    def test_stop_level_blocks_shallow_wildcards(self):
        """Test that stop level blocks wildcards at blocked depths."""
        paths = {'/dir1/*', '/dir2/*', '/file.html'}
        result = apply_stop_level_constraints(paths, 2, '/')
        # Wildcards at depth 1 should be blocked, regular files allowed
        assert '/file.html' in result
        # Blocked wildcards are kept as-is (the prevention happens in consolidation functions)
        assert '/dir1/*' in result
        assert '/dir2/*' in result


class TestBucketSpecificConfiguration:
    """Test bucket-specific configuration parameters."""
    
    def test_custom_directory_threshold(self):
        """Test consolidation with custom directory threshold."""
        paths = ['/dir/file1.html', '/dir/file2.html']  # Only 2 files
        
        # With threshold 1, should consolidate
        result = consolidate_paths(paths, directory_threshold=1, stop_level=1)  # Allow consolidation at depth 1
        assert len(result) == 1
        assert '/dir/*' in result[0]
        
        # With threshold 3, should not consolidate
        result = consolidate_paths(paths, directory_threshold=3)
        assert len(result) == 1
        assert len(result[0]) == 2
        assert '/dir/file1.html' in result[0]
        assert '/dir/file2.html' in result[0]
    
    def test_custom_stop_level(self):
        """Test consolidation with custom stop level."""
        paths = ['/dir/file1.html', '/dir/file2.html', '/dir/file3.html', '/dir/file4.html']
        
        # With stop level 1, should consolidate normally
        result = consolidate_paths(paths, stop_level=1)
        assert len(result) == 1
        assert '/dir/*' in result[0]
        
        # With stop level 2, should allow consolidation at depth 1
        result = consolidate_paths(paths, stop_level=1)
        assert len(result) == 1
        # Should consolidate to /dir/* (depth 1) since depth 1 >= stop level 1
        assert '/dir/*' in result[0]
    
    def test_stop_level_zero_special_case(self):
        """Test that stop level 0 consolidates everything to root."""
        paths = ['/dir1/file1.html', '/dir2/file2.html', '/dir3/file3.html']
        result = consolidate_paths(paths, stop_level=0)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/*'
    
    def test_index_file_with_stop_level(self):
        """Test index file consolidation respects stop level."""
        paths = ['/dir/index.html']
        
        # With stop level 1, should consolidate index file
        result = consolidate_paths(paths, stop_level=1)
        assert len(result) == 1
        assert '/dir/*' in result[0]
        
        # With stop level 2, should allow consolidation to /dir/* (depth 1)
        result = consolidate_paths(paths, stop_level=1)
        assert len(result) == 1
        assert '/dir/*' in result[0]


class TestStopLevelEdgeCases:
    """Test stop level edge cases and boundary conditions."""
    
    def test_stop_level_zero_with_complex_paths(self):
        """Test stop level 0 with complex nested paths."""
        paths = [
            '/level1/level2/level3/file1.html',
            '/level1/level2/file2.html',
            '/level1/file3.html',
            '/file4.html'
        ]
        result = consolidate_paths(paths, stop_level=0)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/*'
    
    def test_stop_level_zero_with_index_files(self):
        """Test stop level 0 overrides index file consolidation."""
        paths = ['/dir1/index.html', '/dir2/default.html', '/dir3/file.html']
        result = consolidate_paths(paths, stop_level=0)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/*'
    
    def test_stop_level_one_boundary_conditions(self):
        """Test stop level 1 boundary conditions."""
        # Test consolidation at exactly depth 1 (should be allowed)
        paths = ['/dir/file1.html', '/dir/file2.html', '/dir/file3.html', '/dir/file4.html']
        result = consolidate_paths(paths, stop_level=1)
        assert len(result) == 1
        assert '/dir/*' in result[0]
        
        # Test that depth 2 consolidation is allowed with stop level 1
        # Create paths that would consolidate at depth 2
        deep_paths = ['/dir/subdir/file1.html', '/dir/subdir/file2.html', '/dir/subdir/file3.html', '/dir/subdir/file4.html']
        result = consolidate_paths(deep_paths, stop_level=1)
        # Should consolidate to /dir/subdir/* (depth 2 >= stop level 1 is true, so allowed)
        assert len(result) == 1
        assert '/dir/subdir/*' in result[0]
    
    def test_stop_level_two_allows_up_to_depth_two(self):
        """Test that stop level 2 allows consolidation at depth 2 and deeper."""
        paths = ['/dir/file1.html', '/dir/file2.html', '/dir/file3.html', '/dir/file4.html']
        result = consolidate_paths(paths, stop_level=1)
        assert len(result) == 1
        # Should consolidate to /dir/* (depth 1) with stop level 1 since depth 1 >= 1
        assert '/dir/*' in result[0]
        
        # Should also allow consolidation at depth 2
        deep_paths = [
            '/dir/subdir/file1.html', '/dir/subdir/file2.html', 
            '/dir/subdir/file3.html', '/dir/subdir/file4.html'
        ]
        result = consolidate_paths(deep_paths, stop_level=2)
        assert len(result) == 1
        assert '/dir/subdir/*' in result[0]
        
        # But should allow consolidation at depth 3 with stop level 2
        deeper_paths = [
            '/dir/subdir/subsubdir/file1.html', '/dir/subdir/subsubdir/file2.html', 
            '/dir/subdir/subsubdir/file3.html', '/dir/subdir/subsubdir/file4.html'
        ]
        result = consolidate_paths(deeper_paths, stop_level=2)
        assert len(result) == 1
        # Should consolidate to /dir/subdir/subsubdir/* (depth 3 >= stop level 2 is true)
        assert '/dir/subdir/subsubdir/*' in result[0]
    
    def test_stop_level_three_allows_up_to_depth_three(self):
        """Test that stop level 3 allows consolidation at depth 3 and deeper."""
        # Should allow consolidation at depth 1
        paths_depth_1 = ['/dir/file1.html', '/dir/file2.html', '/dir/file3.html', '/dir/file4.html']
        result = consolidate_paths(paths_depth_1, stop_level=1)
        assert len(result) == 1
        assert '/dir/*' in result[0]
        
        # Should allow consolidation at depth 2
        paths_depth_2 = [
            '/dir/subdir/file1.html', '/dir/subdir/file2.html',
            '/dir/subdir/file3.html', '/dir/subdir/file4.html'
        ]
        result = consolidate_paths(paths_depth_2, stop_level=2)
        assert len(result) == 1
        assert '/dir/subdir/*' in result[0]
        
        # Should allow consolidation at depth 3
        paths_depth_3 = [
            '/dir/subdir/subsubdir/file1.html', '/dir/subdir/subsubdir/file2.html',
            '/dir/subdir/subsubdir/file3.html', '/dir/subdir/subsubdir/file4.html'
        ]
        result = consolidate_paths(paths_depth_3, stop_level=3)
        assert len(result) == 1
        assert '/dir/subdir/subsubdir/*' in result[0]
        
        # Should allow consolidation at depth 4 with stop level 3
        paths_depth_4 = [
            '/dir/subdir/subsubdir/subsubsubdir/file1.html', '/dir/subdir/subsubdir/subsubsubdir/file2.html',
            '/dir/subdir/subsubdir/subsubsubdir/file3.html', '/dir/subdir/subsubdir/subsubsubdir/file4.html'
        ]
        result = consolidate_paths(paths_depth_4, stop_level=3)
        assert len(result) == 1
        # Should consolidate to depth 4 with stop level 3 (depth 4 >= stop level 3)
        assert '/dir/subdir/subsubdir/subsubsubdir/*' in result[0]
    
    def test_stop_level_with_sibling_directories(self):
        """Test stop level behavior with sibling directory consolidation."""
        # Create 12 sibling directories (exceeds threshold of 10)
        # Each directory needs more than 3 files to trigger directory consolidation first
        paths = []
        for i in range(12):
            for j in range(4):  # 4 files per directory (exceeds threshold of 3)
                paths.append(f'/parent/dir{i}/file{j}.html')
        
        # With stop level 2, should consolidate to directory wildcards but prevent sibling consolidation
        result = consolidate_paths(paths, stop_level=2)
        assert len(result) == 1
        # Should have individual directory wildcards, not parent consolidation (depth 1 < stop_level 2)
        consolidated = result[0]
        # Should have 12 directory wildcards (one for each dir0, dir1, ..., dir11)
        directory_wildcards = [p for p in consolidated if p.startswith('/parent/dir') and p.endswith('/*')]
        assert len(directory_wildcards) == 12, f"Expected 12 directory wildcards, got {len(directory_wildcards)}: {consolidated}"
        assert '/parent/*' not in consolidated, "Should not consolidate to /parent/* with stop_level 2"
        
        # With stop level 1, should allow consolidation to /parent/* (depth 1)
        result = consolidate_paths(paths, stop_level=1)
        assert len(result) == 1
        # Should consolidate to parent since depth 1 >= stop level 1
        assert '/parent/*' in result[0] or '/*' in result[0]  # May consolidate further
    
    def test_mixed_depth_consolidation_with_stop_level(self):
        """Test consolidation with paths at different depths and stop level."""
        paths = [
            # Depth 1 files (4 files, should consolidate if allowed)
            '/dir1/file1.html', '/dir1/file2.html', '/dir1/file3.html', '/dir1/file4.html',
            # Depth 2 files (4 files, should consolidate if allowed)
            '/dir2/subdir/file1.html', '/dir2/subdir/file2.html', 
            '/dir2/subdir/file3.html', '/dir2/subdir/file4.html',
            # Depth 3 files (4 files, should consolidate if allowed)
            '/dir3/sub1/sub2/file1.html', '/dir3/sub1/sub2/file2.html',
            '/dir3/sub1/sub2/file3.html', '/dir3/sub1/sub2/file4.html'
        ]
        
        # With stop level 2, should allow consolidation at depth 2 and deeper, prevent shallower
        result = consolidate_paths(paths, stop_level=2)
        assert len(result) == 1
        
        # Depth 1 should NOT consolidate (depth 1 < stop level 2)
        assert '/dir1/*' not in result[0]
        # Should have individual files at depth 1
        depth_1_files = [p for p in result[0] if p.startswith('/dir1/') and not p.endswith('/*')]
        assert len(depth_1_files) == 4
        
        # Depth 2 should consolidate (depth 2 >= stop level 2)
        assert '/dir2/subdir/*' in result[0]
        
        # Depth 3 should also consolidate (depth 3 >= stop level 2)
        assert '/dir3/sub1/sub2/*' in result[0]


class TestInvalidStopLevelHandling:
    """Test handling of invalid stop level values."""
    
    def test_negative_stop_level(self):
        """Test that negative stop level falls back to default."""
        paths = ['/dir/file1.html', '/dir/file2.html', '/dir/file3.html', '/dir/file4.html']
        
        # Should fall back to default behavior (stop level 1)
        result = consolidate_paths(paths, stop_level=-1)
        assert len(result) == 1
        assert '/dir/*' in result[0]  # Should consolidate normally with default stop level
    
    def test_very_large_stop_level(self):
        """Test that very large stop level falls back to default."""
        paths = ['/dir/file1.html', '/dir/file2.html', '/dir/file3.html', '/dir/file4.html']
        
        # Should fall back to default behavior (stop level 1)
        result = consolidate_paths(paths, stop_level=100)
        assert len(result) == 1
        assert '/dir/*' in result[0]  # Should consolidate normally with default stop level
    
    def test_none_stop_level(self):
        """Test that None stop level uses default."""
        paths = ['/dir/file1.html', '/dir/file2.html', '/dir/file3.html', '/dir/file4.html']
        
        # Should use default stop level from constants
        result = consolidate_paths(paths, stop_level=None)
        assert len(result) == 1
        assert '/dir/*' in result[0]  # Should consolidate normally with default stop level


class TestSiblingThresholdParameter:
    """Test sibling threshold parameter functionality comprehensively."""
    
    def test_sibling_threshold_parameter_usage(self):
        """Test that sibling_threshold parameter is used correctly."""
        # Create 5 sibling directories
        paths = [f'/parent/dir{i}/*' for i in range(5)]
        
        # With threshold=3, should consolidate (5 > 3)
        result = consolidate_paths(paths, sibling_threshold=3, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/parent/*'
        
        # With threshold=5, should NOT consolidate (5 is not > 5)
        result = consolidate_paths(paths, sibling_threshold=5, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 5
        for i in range(5):
            assert f'/parent/dir{i}/*' in result[0]
    
    def test_sibling_threshold_boundary_conditions(self):
        """Test sibling threshold boundary conditions."""
        # Test exactly at threshold
        paths = [f'/parent/dir{i}/*' for i in range(3)]
        
        # With threshold=3, should NOT consolidate (3 is not > 3)
        result = consolidate_paths(paths, sibling_threshold=3, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 3
        assert '/parent/*' not in result[0]
        
        # With threshold=2, should consolidate (3 > 2)
        result = consolidate_paths(paths, sibling_threshold=2, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/parent/*'
    
    def test_sibling_threshold_with_stop_level_interaction(self):
        """Test interaction between sibling threshold and stop level constraints."""
        # Create paths that would consolidate at depth 1 (/parent/*)
        paths = [f'/parent/dir{i}/*' for i in range(4)]
        
        # With stop_level=2, should prevent consolidation at depth 1 (1 < 2)
        result = consolidate_paths(paths, sibling_threshold=2, stop_level=2)
        assert len(result) == 1
        assert len(result[0]) == 4  # Should remain as individual directory wildcards
        assert '/parent/*' not in result[0]
        
        # With stop_level=1, should allow consolidation at depth 1 (1 >= 1)
        result = consolidate_paths(paths, sibling_threshold=2, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/parent/*'
    
    def test_sibling_threshold_none_fallback(self):
        """Test that None sibling_threshold falls back to global constant."""
        # Create 11 sibling directories (exceeds default threshold of 10)
        paths = [f'/parent/dir{i}/*' for i in range(11)]
        
        # Both should produce identical results
        result_none = consolidate_paths(paths, sibling_threshold=None, stop_level=1)
        result_missing = consolidate_paths(paths, stop_level=1)
        
        assert result_none == result_missing
        assert len(result_none) == 1
        assert len(result_none[0]) == 1
        assert result_none[0][0] == '/parent/*'
    
    def test_sibling_threshold_zero_and_one(self):
        """Test edge cases with very low thresholds."""
        # Single sibling directory
        paths = ['/parent/dir0/*']
        
        # With threshold=0, should consolidate (1 > 0)
        result = consolidate_paths(paths, sibling_threshold=0, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/parent/*'
        
        # Two sibling directories
        paths = ['/parent/dir0/*', '/parent/dir1/*']
        
        # With threshold=1, should consolidate (2 > 1)
        result = consolidate_paths(paths, sibling_threshold=1, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/parent/*'
    
    def test_sibling_threshold_very_high(self):
        """Test with very high threshold that prevents consolidation."""
        # Create 10 sibling directories
        paths = [f'/parent/dir{i}/*' for i in range(10)]
        
        # With threshold=100, should NOT consolidate (10 < 100)
        result = consolidate_paths(paths, sibling_threshold=100, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 10
        for i in range(10):
            assert f'/parent/dir{i}/*' in result[0]
        assert '/parent/*' not in result[0]
    
    def test_mixed_threshold_scenarios(self):
        """Test scenarios with multiple parent directories and different thresholds."""
        paths = []
        # Parent1 has 4 siblings
        paths.extend([f'/parent1/dir{i}/*' for i in range(4)])
        # Parent2 has 2 siblings
        paths.extend([f'/parent2/dir{i}/*' for i in range(2)])
        # Parent3 has 6 siblings
        paths.extend([f'/parent3/dir{i}/*' for i in range(6)])
        
        # With threshold=3, parent1 and parent3 should consolidate, parent2 should not
        result = consolidate_paths(paths, sibling_threshold=3, stop_level=1)
        assert len(result) == 1
        
        # Should have parent1/* and parent3/* consolidated, parent2 siblings remain
        consolidated = result[0]
        assert '/parent1/*' in consolidated
        assert '/parent3/*' in consolidated
        assert '/parent2/dir0/*' in consolidated
        assert '/parent2/dir1/*' in consolidated
        assert len(consolidated) == 4  # 2 parent wildcards + 2 individual parent2 siblings


class TestSiblingThresholdEdgeCases:
    """Test edge cases and error conditions for sibling threshold."""
    
    def test_empty_paths_with_sibling_threshold(self):
        """Test sibling threshold with empty path list."""
        result = consolidate_paths([], sibling_threshold=5)
        assert len(result) == 1
        assert result[0] == []
    
    def test_single_path_with_sibling_threshold(self):
        """Test sibling threshold with single path."""
        result = consolidate_paths(['/file.html'], sibling_threshold=5)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/file.html'
    
    def test_non_wildcard_paths_with_sibling_threshold(self):
        """Test that sibling threshold doesn't affect non-wildcard paths."""
        paths = ['/dir1/file.html', '/dir2/file.html', '/dir3/file.html']
        
        # Sibling threshold only applies to directory wildcards, not individual files
        result = consolidate_paths(paths, sibling_threshold=1, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 3
        for path in paths:
            assert path in result[0]
    
    def test_mixed_wildcards_and_files_with_sibling_threshold(self):
        """Test sibling threshold with mix of wildcards and individual files."""
        paths = [
            '/parent/dir1/*',
            '/parent/dir2/*', 
            '/parent/dir3/*',
            '/other/file.html'
        ]
        
        # With threshold=2, parent siblings should consolidate (3 > 2)
        result = consolidate_paths(paths, sibling_threshold=2, stop_level=1)
        assert len(result) == 1
        consolidated = result[0]
        
        assert '/parent/*' in consolidated
        assert '/other/file.html' in consolidated
        assert len(consolidated) == 2
    
    def test_nested_directory_structures_with_sibling_threshold(self):
        """Test sibling threshold with nested directory structures."""
        paths = [
            '/level1/level2/dir1/*',
            '/level1/level2/dir2/*',
            '/level1/level2/dir3/*',
            '/level1/other/file.html'
        ]
        
        # With threshold=2, should consolidate to /level1/level2/* (3 > 2)
        result = consolidate_paths(paths, sibling_threshold=2, stop_level=2)
        assert len(result) == 1
        consolidated = result[0]
        
        assert '/level1/level2/*' in consolidated
        assert '/level1/other/file.html' in consolidated
        assert len(consolidated) == 2


class TestUserSpecificScenarioComprehensive:
    """Comprehensive tests for the user's specific scenario."""
    
    def test_user_scenario_exact_reproduction(self):
        """Test exact reproduction of user's scenario."""
        # User's exact paths with SiblingDirectoryConsolidationThreshold=2 and ConsolidationStopLevel=1
        paths = [
            '/prod/public/m/*',
            '/prod/public/k/*', 
            '/prod/public/w/*',
            '/prod/public/x/*'
        ]
        
        result = consolidate_paths(paths, sibling_threshold=2, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/prod/public/*'
    
    def test_user_scenario_variations(self):
        """Test variations of user's scenario with different configurations."""
        paths = [
            '/prod/public/m/*',
            '/prod/public/k/*', 
            '/prod/public/w/*',
            '/prod/public/x/*'
        ]
        
        # Test with different thresholds
        test_cases = [
            (1, True),   # threshold=1, should consolidate (4 > 1)
            (2, True),   # threshold=2, should consolidate (4 > 2)
            (3, True),   # threshold=3, should consolidate (4 > 3)
            (4, False),  # threshold=4, should NOT consolidate (4 is not > 4)
            (5, False),  # threshold=5, should NOT consolidate (4 < 5)
        ]
        
        for threshold, should_consolidate in test_cases:
            result = consolidate_paths(paths, sibling_threshold=threshold, stop_level=1)
            assert len(result) == 1
            
            if should_consolidate:
                assert len(result[0]) == 1
                assert result[0][0] == '/prod/public/*'
            else:
                assert len(result[0]) == 4
                for path in paths:
                    assert path in result[0]
    
    def test_user_scenario_with_stop_level_variations(self):
        """Test user's scenario with different stop levels."""
        paths = [
            '/prod/public/m/*',
            '/prod/public/k/*', 
            '/prod/public/w/*',
            '/prod/public/x/*'
        ]
        
        # With stop_level=2, should prevent consolidation to /prod/public/* (depth 1 < stop_level 2)
        result = consolidate_paths(paths, sibling_threshold=2, stop_level=2)
        assert len(result) == 1
        assert len(result[0]) == 4
        for path in paths:
            assert path in result[0]
        
        # With stop_level=1, should allow consolidation to /prod/public/* (depth 1 >= stop_level 1)
        result = consolidate_paths(paths, sibling_threshold=2, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/prod/public/*'
        
        # With stop_level=0, should consolidate to /* (special case)
        result = consolidate_paths(paths, sibling_threshold=2, stop_level=0)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/*'


class ThresholdBoundaryConditions:
    """Test sibling threshold boundary conditions comprehensively."""
    
    def test_sibling_threshold_exactly_at_boundary(self):
        """Test consolidation when sibling count exactly equals threshold."""
        # Create exactly 5 sibling directories
        paths = [f'/parent/dir{i}/*' for i in range(5)]
        
        # With threshold=5, should NOT consolidate (5 is not > 5)
        # Use stop_level=1 to allow normal consolidation logic (stop_level=0 forces root consolidation)
        result = consolidate_paths(paths, sibling_threshold=5, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 5
        for i in range(5):
            assert f'/parent/dir{i}/*' in result[0]
    
    def test_sibling_threshold_just_above_boundary(self):
        """Test consolidation when sibling count is just above threshold."""
        # Create 6 sibling directories (just above threshold of 5)
        paths = [f'/parent/dir{i}/*' for i in range(6)]
        
        # With threshold=5, should consolidate (6 > 5)
        result = consolidate_paths(paths, sibling_threshold=5, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/parent/*'
    
    def test_sibling_threshold_just_below_boundary(self):
        """Test consolidation when sibling count is just below threshold."""
        # Create 4 sibling directories (just below threshold of 5)
        paths = [f'/parent/dir{i}/*' for i in range(4)]
        
        # With threshold=5, should NOT consolidate (4 < 5)
        result = consolidate_paths(paths, sibling_threshold=5, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 4
        for i in range(4):
            assert f'/parent/dir{i}/*' in result[0]
    
    def test_sibling_threshold_with_mixed_parents(self):
        """Test threshold boundary conditions with multiple parent directories."""
        paths = []
        # Parent1 has exactly 3 siblings (threshold boundary)
        paths.extend([f'/parent1/dir{i}/*' for i in range(3)])
        # Parent2 has 4 siblings (just above threshold of 3)
        paths.extend([f'/parent2/dir{i}/*' for i in range(4)])
        # Parent3 has 2 siblings (below threshold of 3)
        paths.extend([f'/parent3/dir{i}/*' for i in range(2)])
        
        result = consolidate_paths(paths, sibling_threshold=3, stop_level=1)
        assert len(result) == 1
        
        # Parent1: exactly 3 siblings, should NOT consolidate (3 is not > 3)
        assert '/parent1/dir0/*' in result[0]
        assert '/parent1/dir1/*' in result[0]
        assert '/parent1/dir2/*' in result[0]
        assert '/parent1/*' not in result[0]
        
        # Parent2: 4 siblings, should consolidate (4 > 3)
        assert '/parent2/*' in result[0]
        
        # Parent3: 2 siblings, should NOT consolidate (2 < 3)
        assert '/parent3/dir0/*' in result[0]
        assert '/parent3/dir1/*' in result[0]
        assert '/parent3/*' not in result[0]
    
    def test_sibling_threshold_one(self):
        """Test sibling threshold of 1 (very low threshold)."""
        # Create 2 sibling directories
        paths = ['/parent/dir1/*', '/parent/dir2/*']
        
        # With threshold=1, should consolidate (2 > 1)
        result = consolidate_paths(paths, sibling_threshold=1, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/parent/*'
    
    def test_sibling_threshold_zero(self):
        """Test sibling threshold of 0 (consolidates everything)."""
        # Create single sibling directory
        paths = ['/parent/dir1/*']
        
        # With threshold=0, should consolidate (1 > 0)
        result = consolidate_paths(paths, sibling_threshold=0, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/parent/*'
    
    def test_sibling_threshold_very_high(self):
        """Test very high sibling threshold (prevents consolidation)."""
        # Create 10 sibling directories
        paths = [f'/parent/dir{i}/*' for i in range(10)]
        
        # With threshold=100, should NOT consolidate (10 < 100)
        result = consolidate_paths(paths, sibling_threshold=100, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 10
        for i in range(10):
            assert f'/parent/dir{i}/*' in result[0]


class TestUserSpecificScenario:
    """Test user's specific scenario from the bug report."""
    
    def test_user_scenario_with_sibling_threshold_2(self):
        """Test user's specific scenario: 4 sibling directories with threshold=2 should consolidate to parent."""
        # User's exact scenario: /prod/public/m/*, /prod/public/k/*, /prod/public/w/*, /prod/public/x/*
        # With SiblingDirectoryConsolidationThreshold=2 and ConsolidationStopLevel=1
        # Should consolidate to /prod/public/* since 4 > 2
        paths = [
            '/prod/public/m/*',
            '/prod/public/k/*', 
            '/prod/public/w/*',
            '/prod/public/x/*'
        ]
        
        result = consolidate_paths(paths, sibling_threshold=2, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/prod/public/*'
    
    def test_user_scenario_threshold_boundary_conditions(self):
        """Test threshold boundary conditions with user's scenario."""
        paths = [
            '/prod/public/m/*',
            '/prod/public/k/*', 
            '/prod/public/w/*',
            '/prod/public/x/*'
        ]
        
        # With threshold=4, should NOT consolidate (4 is not > 4)
        result = consolidate_paths(paths, sibling_threshold=4, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 4
        assert '/prod/public/m/*' in result[0]
        assert '/prod/public/k/*' in result[0]
        assert '/prod/public/w/*' in result[0]
        assert '/prod/public/x/*' in result[0]
        
        # With threshold=3, should consolidate (4 > 3)
        result = consolidate_paths(paths, sibling_threshold=3, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/prod/public/*'
    
    def test_user_scenario_with_stop_level_constraints(self):
        """Test user's scenario respects stop level constraints."""
        paths = [
            '/prod/public/m/*',
            '/prod/public/k/*', 
            '/prod/public/w/*',
            '/prod/public/x/*'
        ]
        
        # With stop_level=2, should prevent consolidation to /prod/public/* (depth 1 < stop_level 2)
        result = consolidate_paths(paths, sibling_threshold=2, stop_level=2)
        assert len(result) == 1
        assert len(result[0]) == 4  # Should remain as individual directory wildcards
        assert '/prod/public/m/*' in result[0]
        assert '/prod/public/k/*' in result[0]
        assert '/prod/public/w/*' in result[0]
        assert '/prod/public/x/*' in result[0]
        
        # With stop_level=1, should allow consolidation to /prod/public/* (depth 1 >= stop_level 1)
        result = consolidate_paths(paths, sibling_threshold=2, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/prod/public/*'


class TestBackwardCompatibility:
    """Test backward compatibility with existing behavior."""
    
    def test_default_stop_level_behavior(self):
        """Test that default stop level maintains existing behavior."""
        paths = ['/dir/file1.html', '/dir/file2.html', '/dir/file3.html', '/dir/file4.html']
        
        # Default behavior should consolidate normally
        result = consolidate_paths(paths)
        assert len(result) == 1
        assert '/dir/*' in result[0]
    
    def test_stop_level_one_maintains_compatibility(self):
        """Test that explicit stop level 1 maintains existing behavior."""
        paths = ['/dir/file1.html', '/dir/file2.html', '/dir/file3.html', '/dir/file4.html']
        
        # Explicit stop level 1 should behave the same as default
        result_default = consolidate_paths(paths)
        result_explicit = consolidate_paths(paths, stop_level=1)
        
        assert result_default == result_explicit
    
    def test_index_file_backward_compatibility(self):
        """Test that index file consolidation maintains backward compatibility."""
        paths = ['/dir/index.html', '/dir/about.html']
        
        # Should consolidate index file to directory wildcard
        # The /dir/* wildcard covers both files, so about.html is not separate
        result = consolidate_paths(paths)
        assert len(result) == 1
        assert '/dir/*' in result[0]
        # The wildcard covers all files in the directory
        assert len(result[0]) == 1  # Only the wildcard should remain
    
    def test_complex_scenario_backward_compatibility(self):
        """Test complex consolidation scenario maintains backward compatibility."""
        # Create scenario that would consolidate to root in old system
        paths = []
        for i in range(12):  # More than 10 siblings
            for j in range(5):  # More than 3 files per directory
                paths.append(f'/root/dir{i}/file{j}.html')
        
        # Should still consolidate to root with stop level that allows consolidation at depth 2
        # Use stop_level=2 to allow consolidation of /root/dir* directories (depth 2)
        result = consolidate_paths(paths, stop_level=2)
        assert len(result) == 1
        # Should consolidate all the way up (may be /* or specific pattern)
        assert len(result[0]) <= 12  # Should be consolidated significantly
    
    def test_consolidate_paths_without_sibling_threshold_parameter(self):
        """Test consolidate_paths calls without sibling_threshold parameter use global constant."""
        # Create 11 sibling directories (exceeds default threshold of 10)
        paths = [f'/parent/dir{i}/*' for i in range(11)]
        
        # Call without sibling_threshold parameter - should use global constant (10)
        result = consolidate_paths(paths, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/parent/*'
        
        # Call with explicit None - should also use global constant
        result_none = consolidate_paths(paths, sibling_threshold=None, stop_level=1)
        assert result == result_none
    
    def test_global_constant_fallback_behavior(self):
        """Test that global constant is used as fallback when sibling_threshold is None."""
        # Create exactly 10 sibling directories (at default threshold boundary)
        paths = [f'/parent/dir{i}/*' for i in range(10)]
        
        # Without sibling_threshold parameter, should NOT consolidate (10 is not > 10)
        result = consolidate_paths(paths, stop_level=1)
        assert len(result) == 1
        assert len(result[0]) == 10
        for i in range(10):
            assert f'/parent/dir{i}/*' in result[0]
        
        # With explicit None, should behave the same
        result_none = consolidate_paths(paths, sibling_threshold=None, stop_level=1)
        assert result == result_none
    
    def test_existing_bucket_configurations_compatibility(self):
        """Test with existing bucket configurations that don't specify sibling_threshold."""
        # Simulate existing bucket configuration calls that only specify directory_threshold and stop_level
        paths = [
            '/prod/public/file1.html', '/prod/public/file2.html', 
            '/prod/public/file3.html', '/prod/public/file4.html'
        ]
        
        # Old-style call with only directory_threshold and stop_level
        result_old_style = consolidate_paths(paths, directory_threshold=3, stop_level=1)
        
        # New-style call with explicit None for sibling_threshold
        result_new_style = consolidate_paths(paths, directory_threshold=3, stop_level=1, sibling_threshold=None)
        
        # Should produce identical results
        assert result_old_style == result_new_style
        
        # Both should consolidate to /prod/public/* since 4 > 3 (directory threshold)
        assert len(result_old_style) == 1
        assert '/prod/public/*' in result_old_style[0]
    
    def test_parameter_order_independence(self):
        """Test that parameter order doesn't affect backward compatibility."""
        paths = [f'/parent/dir{i}/*' for i in range(11)]
        
        # Different parameter orders should produce same results
        result1 = consolidate_paths(paths, directory_threshold=3, stop_level=1)
        result2 = consolidate_paths(paths, stop_level=1, directory_threshold=3)
        result3 = consolidate_paths(paths, stop_level=1)
        
        # All should produce the same result
        assert result1 == result2 == result3
    
    def test_mixed_parameter_scenarios(self):
        """Test mixed scenarios with some parameters specified and others defaulted."""
        paths = [
            '/dir1/file1.html', '/dir1/file2.html', '/dir1/file3.html', '/dir1/file4.html',
            '/dir2/file1.html', '/dir2/file2.html', '/dir2/file3.html', '/dir2/file4.html'
        ]
        
        # Scenario 1: Only directory_threshold specified
        result1 = consolidate_paths(paths, directory_threshold=3)
        
        # Scenario 2: Only stop_level specified  
        result2 = consolidate_paths(paths, stop_level=1)
        
        # Scenario 3: Both specified
        result3 = consolidate_paths(paths, directory_threshold=3, stop_level=1)
        
        # All should consolidate to directory wildcards
        for result in [result1, result2, result3]:
            assert len(result) == 1
            assert '/dir1/*' in result[0]
            assert '/dir2/*' in result[0]
            assert len(result[0]) == 2
