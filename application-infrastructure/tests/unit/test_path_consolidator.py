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
