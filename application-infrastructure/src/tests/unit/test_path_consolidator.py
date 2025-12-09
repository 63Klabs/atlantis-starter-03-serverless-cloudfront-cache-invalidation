"""Unit tests for path consolidation algorithm edge cases."""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import pytest
from processor.path_consolidator import (
    consolidate_paths,
    is_index_or_default_file,
    get_parent_directory,
    consolidate_index_and_default_files,
    consolidate_by_directory_threshold,
    consolidate_sibling_directories
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
        result = consolidate_paths(paths)
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
        result = consolidate_index_and_default_files(paths)
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
        result = consolidate_by_directory_threshold(paths)
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
        result = consolidate_by_directory_threshold(paths)
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
        result = consolidate_sibling_directories(paths)
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
        
        result = consolidate_sibling_directories(paths)
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
        
        result = consolidate_paths(paths)
        # Should consolidate all the way to /root/*
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] == '/root/*'
    
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
        result = consolidate_paths(paths)
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
