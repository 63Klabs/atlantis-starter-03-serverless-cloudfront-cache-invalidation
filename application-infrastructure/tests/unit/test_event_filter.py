"""Unit tests for Ingestor event filtering with pattern matching."""

import os
from unittest.mock import patch

import pytest

from functions.ingestor.event_filter import should_process_event


class TestShouldProcessEvent:
    """Tests for should_process_event function with pattern matching.
    
    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
    """
    
    # Test exact pattern matches with production stages (Requirement 5.1)
    
    def test_exact_pattern_match_with_prod_stage(self):
        """Test exact pattern match with 'prod' production stage."""
        event_path = '/prod/public/images/logo.png'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is True
        assert 'prod' in reason
        assert 'production stage' in reason.lower()
    
    def test_exact_pattern_match_with_beta_stage(self):
        """Test exact pattern match with 'beta' production stage."""
        event_path = '/beta/public/assets/style.css'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is True
        assert 'beta' in reason
        assert 'production stage' in reason.lower()
    
    def test_exact_pattern_match_with_stage_stage(self):
        """Test exact pattern match with 'stage' production stage."""
        event_path = '/stage/public/docs/readme.html'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is True
        assert 'stage' in reason
        assert 'production stage' in reason.lower()
    
    def test_exact_pattern_match_with_staging_stage(self):
        """Test exact pattern match with 'staging' production stage."""
        event_path = '/staging/public/data/config.json'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is True
        assert 'staging' in reason
        assert 'production stage' in reason.lower()
    
    # Test exact pattern matches with non-production stages (Requirement 5.1)
    
    def test_exact_pattern_match_with_dev_stage_filtered(self):
        """Test exact pattern match with 'dev' non-production stage is filtered."""
        event_path = '/dev/public/images/logo.png'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is False
        assert 'dev' in reason
        assert 'non-production' in reason.lower()
    
    def test_exact_pattern_match_with_test_stage_filtered(self):
        """Test exact pattern match with 'test' non-production stage is filtered."""
        event_path = '/test/public/assets/style.css'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is False
        assert 'test' in reason
        assert 'non-production' in reason.lower()
    
    # Test pattern without {stageId} placeholder (Requirement 5.2)
    
    @patch('functions.ingestor.event_filter.ORIGIN_PATH_PATTERN', '/public')
    def test_pattern_without_placeholder_accepts_all(self):
        """Test pattern without {stageId} accepts all matching paths."""
        event_path = '/public/images/logo.png'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is True
        assert 'no stage filtering' in reason.lower()
    
    @patch('functions.ingestor.event_filter.ORIGIN_PATH_PATTERN', '/public')
    def test_pattern_without_placeholder_with_stage_in_path(self):
        """Test pattern without {stageId} with stage in path uses fallback."""
        # This path doesn't match /public pattern, but has public segment
        event_path = '/prod/public/images/logo.png'
        
        should_process, reason = should_process_event(event_path)
        
        # Should be accepted via public segment fallback
        assert should_process is True
        assert 'public segment' in reason.lower()
    
    @patch('functions.ingestor.event_filter.ORIGIN_PATH_PATTERN', '/')
    def test_root_pattern_accepts_all_paths(self):
        """Test root pattern '/' accepts all paths without filtering."""
        # Root pattern should match any path
        test_paths = [
            '/file.html',
            '/prod/public/file.html',
            '/assets/images/logo.png',
            '/any/nested/path/structure/file.txt'
        ]
        
        for event_path in test_paths:
            should_process, reason = should_process_event(event_path)
            
            assert should_process is True, f"Path {event_path} should be accepted with root pattern"
            assert 'no stage filtering' in reason.lower()
    
    # Test public segment fallback (Requirement 5.3)
    
    @patch('functions.ingestor.event_filter.ORIGIN_PATH_PATTERN', '/assets/{stageId}/public')
    def test_public_segment_fallback_with_prod_stage(self):
        """Test public segment fallback accepts production stages."""
        event_path = '/prod/public/images/logo.png'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is True
        assert 'public segment' in reason.lower()
    
    @patch('functions.ingestor.event_filter.ORIGIN_PATH_PATTERN', '/assets/{stageId}/public')
    def test_public_segment_fallback_with_beta_stage(self):
        """Test public segment fallback accepts beta stage."""
        event_path = '/beta/public/assets/style.css'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is True
        assert 'public segment' in reason.lower()
    
    @patch('functions.ingestor.event_filter.ORIGIN_PATH_PATTERN', '/assets/{stageId}/public')
    def test_public_segment_fallback_no_stage_before_public(self):
        """Test public segment fallback accepts paths with no stage before public."""
        event_path = '/public/images/logo.png'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is True
        assert 'public segment' in reason.lower()
    
    # Test filtering of non-production stages in fallback (Requirement 5.5)
    
    @patch('functions.ingestor.event_filter.ORIGIN_PATH_PATTERN', '/assets/{stageId}/public')
    def test_public_segment_fallback_filters_dev_stage(self):
        """Test public segment fallback filters dev stage."""
        event_path = '/dev/public/images/logo.png'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is False
        assert 'dev' in reason
        assert 'non-production' in reason.lower()
    
    @patch('functions.ingestor.event_filter.ORIGIN_PATH_PATTERN', '/assets/{stageId}/public')
    def test_public_segment_fallback_filters_test_stage(self):
        """Test public segment fallback filters test stage."""
        event_path = '/test/public/assets/style.css'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is False
        assert 'test' in reason
        assert 'non-production' in reason.lower()
    
    # Test filtering of non-matching paths (Requirement 5.4)
    
    def test_no_pattern_match_no_public_segment(self):
        """Test paths that don't match pattern and have no public segment are filtered."""
        event_path = '/prod/private/images/logo.png'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is False
        assert 'does not match pattern' in reason.lower()
        assert 'does not contain public segment' in reason.lower()
    
    def test_no_pattern_match_different_structure(self):
        """Test paths with completely different structure are filtered."""
        event_path = '/assets/images/logo.png'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is False
        assert 'does not match pattern' in reason.lower()
    
    def test_empty_path(self):
        """Test empty path is filtered."""
        event_path = ''
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is False
    
    def test_root_path(self):
        """Test root path is filtered."""
        event_path = '/'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is False
    
    # Test various path structures
    
    def test_nested_file_in_public(self):
        """Test deeply nested file in public directory."""
        event_path = '/prod/public/assets/images/icons/logo.png'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is True
    
    def test_file_at_public_root(self):
        """Test file directly in public directory."""
        event_path = '/prod/public/index.html'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is True
    
    def test_path_with_special_characters(self):
        """Test path with special characters in filename."""
        event_path = '/prod/public/files/my-file_v2.0.pdf'
        
        should_process, reason = should_process_event(event_path)
        
        assert should_process is True
    
    # Test edge cases
    
    def test_public_segment_not_at_expected_position(self):
        """Test public segment at unexpected position."""
        event_path = '/prod/assets/public/images/logo.png'
        
        should_process, reason = should_process_event(event_path)
        
        # This doesn't match the /{stageId}/public pattern
        # But it has public segment, so fallback should accept it
        assert should_process is True
        assert 'public segment' in reason.lower()
    
    def test_multiple_public_segments(self):
        """Test path with multiple 'public' segments."""
        event_path = '/prod/public/public/images/logo.png'
        
        should_process, reason = should_process_event(event_path)
        
        # Should match the pattern at the first public
        assert should_process is True
    
    def test_case_sensitive_stage_identifier(self):
        """Test that stage identifiers are case-sensitive."""
        event_path = '/PROD/public/images/logo.png'
        
        should_process, reason = should_process_event(event_path)
        
        # 'PROD' is not in PRODUCTION_STAGE_IDENTIFIERS (which has 'prod')
        # So it should fall back to public segment check
        assert should_process is True
        assert 'public segment' in reason.lower()
    
    def test_case_sensitive_public_segment(self):
        """Test that public segment is case-sensitive."""
        event_path = '/prod/PUBLIC/images/logo.png'
        
        should_process, reason = should_process_event(event_path)
        
        # 'PUBLIC' is not the same as 'public'
        assert should_process is False
