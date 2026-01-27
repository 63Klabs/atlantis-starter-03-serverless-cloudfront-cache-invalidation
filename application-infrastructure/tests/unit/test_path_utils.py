"""Unit tests for path utility functions."""

import pytest
from common.path_utils import (
    calculate_path_depth,
    matches_pattern,
    derive_pattern_from_path,
    extract_stage_from_path
)


class TestCalculatePathDepth:
    """Tests for calculate_path_depth function."""
    
    def test_root_path(self):
        """Test depth calculation for root path."""
        assert calculate_path_depth('/') == 0
    
    def test_single_segment(self):
        """Test depth calculation for single segment path."""
        assert calculate_path_depth('/public') == 1
        assert calculate_path_depth('public') == 1
        assert calculate_path_depth('public/') == 1
    
    def test_two_segments(self):
        """Test depth calculation for two segment path."""
        assert calculate_path_depth('/{stageId}/public') == 2
        assert calculate_path_depth('/prod/public') == 2
        assert calculate_path_depth('prod/public/') == 2
    
    def test_multiple_segments(self):
        """Test depth calculation for multiple segment paths."""
        assert calculate_path_depth('/a/b/c') == 3
        assert calculate_path_depth('/a/b/c/d/e') == 5
    
    def test_trailing_slash_handling(self):
        """Test that trailing slashes are handled correctly."""
        assert calculate_path_depth('/prod/public/') == 2
        assert calculate_path_depth('/prod/public') == 2
    
    def test_leading_slash_handling(self):
        """Test that leading slashes are handled correctly."""
        assert calculate_path_depth('/prod/public') == 2
        assert calculate_path_depth('prod/public') == 2


class TestMatchesPattern:
    """Tests for matches_pattern function."""
    
    def test_exact_match_with@stageId@placeholder(self):
        """Test exact pattern match with {stageId} placeholder."""
        # Production stage should match
        matches, stage = matches_pattern(
            '/prod/public/file.html',
            '/{stageId}/public',
            ['prod', 'beta', 'dev']
        )
        assert matches is True
        assert stage == 'prod'
        
        # Beta stage should match
        matches, stage = matches_pattern(
            '/beta/public/file.html',
            '/{stageId}/public',
            ['prod', 'beta', 'dev']
        )
        assert matches is True
        assert stage == 'beta'
    
    def test_no_match_with@stageId@placeholder(self):
        """Test non-matching path with {stageId} placeholder."""
        matches, stage = matches_pattern(
            '/test/public/file.html',
            '/{stageId}/public',
            ['prod', 'beta']  # test not in list
        )
        assert matches is False
        assert stage is None
    
    def test_exact_match_without_placeholder(self):
        """Test exact pattern match without {stageId} placeholder."""
        matches, stage = matches_pattern(
            '/public/file.html',
            '/public',
            ['prod', 'beta']
        )
        assert matches is True
        assert stage is None
    
    def test_no_match_without_placeholder(self):
        """Test non-matching path without {stageId} placeholder."""
        matches, stage = matches_pattern(
            '/assets/file.html',
            '/public',
            ['prod', 'beta']
        )
        assert matches is False
        assert stage is None
    
    def test_pattern_with_multiple_segments(self):
        """Test pattern matching with multiple segments."""
        matches, stage = matches_pattern(
            '/prod/public/assets/file.html',
            '/{stageId}/public',
            ['prod', 'dev']
        )
        assert matches is True
        assert stage == 'prod'
    
    def test_path_must_start_with_pattern(self):
        """Test that path must start with the pattern."""
        # Path doesn't start with pattern
        matches, stage = matches_pattern(
            '/other/prod/public/file.html',
            '/{stageId}/public',
            ['prod']
        )
        assert matches is False
        assert stage is None
    
    def test_root_pattern_matches_everything(self):
        """Test that root pattern '/' matches all paths."""
        # Root pattern should match any path
        matches, stage = matches_pattern(
            '/file.html',
            '/',
            ['prod', 'dev']
        )
        assert matches is True
        assert stage is None
        
        matches, stage = matches_pattern(
            '/prod/public/file.html',
            '/',
            ['prod', 'dev']
        )
        assert matches is True
        assert stage is None
        
        matches, stage = matches_pattern(
            '/any/path/structure/file.html',
            '/',
            ['prod', 'dev']
        )
        assert matches is True
        assert stage is None


class TestDerivePatternFromPath:
    """Tests for derive_pattern_from_path function."""
    
    def test_derive_with_production_stage(self):
        """Test pattern derivation with production stage identifier."""
        pattern = derive_pattern_from_path(
            '/prod/public/file.html',
            'public',
            ['prod', 'beta'],
            ['dev', 'test']
        )
        assert pattern == '/{stageId}/public'
    
    def test_derive_with_non_production_stage(self):
        """Test pattern derivation with non-production stage identifier."""
        pattern = derive_pattern_from_path(
            '/dev/public/file.html',
            'public',
            ['prod', 'beta'],
            ['dev', 'test']
        )
        assert pattern == '/{stageId}/public'
    
    def test_derive_without_stage(self):
        """Test pattern derivation without stage identifier."""
        pattern = derive_pattern_from_path(
            '/public/file.html',
            'public',
            ['prod', 'beta'],
            ['dev', 'test']
        )
        assert pattern == '/public'
    
    def test_derive_with_nested_structure(self):
        """Test pattern derivation with nested directory structure."""
        pattern = derive_pattern_from_path(
            '/prod/public/assets/images/file.png',
            'public',
            ['prod'],
            ['dev']
        )
        assert pattern == '/{stageId}/public'
    
    def test_path_without_public_segment(self):
        """Test pattern derivation when public segment is not present."""
        pattern = derive_pattern_from_path(
            '/prod/assets/file.html',
            'public',
            ['prod'],
            ['dev']
        )
        assert pattern == ''
    
    def test_multiple_stage_identifiers(self):
        """Test pattern derivation with various stage identifiers."""
        for stage in ['prod', 'beta', 'stage', 'staging']:
            pattern = derive_pattern_from_path(
                f'/{stage}/public/file.html',
                'public',
                ['prod', 'beta', 'stage', 'staging'],
                ['dev', 'test']
            )
            assert pattern == '/{stageId}/public'


class TestExtractStageFromPath:
    """Tests for extract_stage_from_path function."""
    
    def test_extract_stage_with_placeholder(self):
        """Test stage extraction with {stageId} placeholder."""
        stage = extract_stage_from_path(
            '/prod/public/file.html',
            '/{stageId}/public'
        )
        assert stage == 'prod'
        
        stage = extract_stage_from_path(
            '/beta/public/file.html',
            '/{stageId}/public'
        )
        assert stage == 'beta'
    
    def test_extract_stage_without_placeholder(self):
        """Test stage extraction without {stageId} placeholder."""
        stage = extract_stage_from_path(
            '/public/file.html',
            '/public'
        )
        assert stage == ''
    
    def test_extract_stage_mismatched_pattern(self):
        """Test stage extraction with mismatched pattern."""
        stage = extract_stage_from_path(
            '/prod/assets/file.html',
            '/{stageId}/public'
        )
        # Pattern doesn't match, but we still extract the stage position
        assert stage == 'prod'
    
    def test_extract_stage_with_nested_structure(self):
        """Test stage extraction with nested directory structure."""
        stage = extract_stage_from_path(
            '/prod/public/assets/images/file.png',
            '/{stageId}/public'
        )
        assert stage == 'prod'
    
    def test_extract_stage_short_path(self):
        """Test stage extraction when path is shorter than pattern."""
        stage = extract_stage_from_path(
            '/prod',
            '/{stageId}/public'
        )
        assert stage == 'prod'
    
    def test_extract_stage_multiple_placeholders(self):
        """Test stage extraction with pattern at different positions."""
        # Stage at first position
        stage = extract_stage_from_path(
            '/prod/public/file.html',
            '/{stageId}/public'
        )
        assert stage == 'prod'
        
        # If pattern had stage at different position (hypothetical)
        stage = extract_stage_from_path(
            '/public/prod/file.html',
            '/public/{stageId}'
        )
        assert stage == 'prod'
