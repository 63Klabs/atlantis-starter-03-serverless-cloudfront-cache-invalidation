"""Unit tests for pattern_resolver module."""

import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

# Import the module under test
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'functions' / 'processor'))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'layers' / 'common' / 'python'))

from pattern_resolver import resolve_bucket_pattern


class TestResolveBucketPattern:
    """Tests for resolve_bucket_pattern function."""
    
    @patch('pattern_resolver.boto3.client')
    def test_bucket_tag_priority(self, mock_boto3_client):
        """Test that bucket tag has highest priority."""
        # Mock S3 client to return bucket tag
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        mock_s3.get_bucket_tagging.return_value = {
            'TagSet': [
                {'Key': 'invalidator:OriginPathPattern', 'Value': '/custom/pattern'}
            ]
        }
        
        # Call with a path that would match ORIGIN_PATH_PATTERN
        result = resolve_bucket_pattern('test-bucket', '/prod/public/file.html')
        
        # Should return bucket tag value, not ORIGIN_PATH_PATTERN
        assert result == '/custom/pattern'
        mock_s3.get_bucket_tagging.assert_called_once_with(Bucket='test-bucket')
    
    @patch('pattern_resolver.boto3.client')
    @patch('pattern_resolver.ORIGIN_PATH_PATTERN', '/{stageId}/public')
    def test_fallback_to_origin_path_pattern(self, mock_boto3_client):
        """Test fallback to ORIGIN_PATH_PATTERN when no bucket tag exists."""
        # Mock S3 client to raise NoSuchTagSet
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        mock_s3.get_bucket_tagging.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchTagSet'}},
            'GetBucketTagging'
        )
        
        # Call with a path that matches ORIGIN_PATH_PATTERN
        result = resolve_bucket_pattern('test-bucket', '/prod/public/file.html')
        
        # Should return ORIGIN_PATH_PATTERN
        assert result == '/{stageId}/public'
    
    @patch('pattern_resolver.boto3.client')
    @patch('pattern_resolver.ORIGIN_PATH_PATTERN', '/{stageId}/public')
    @patch('pattern_resolver.PUBLIC_PATH_SEGMENT', 'public')
    def test_pattern_derivation_from_public_segment(self, mock_boto3_client):
        """Test pattern derivation when path doesn't match ORIGIN_PATH_PATTERN."""
        # Mock S3 client to raise NoSuchTagSet
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        mock_s3.get_bucket_tagging.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchTagSet'}},
            'GetBucketTagging'
        )
        
        # Call with a path that doesn't match ORIGIN_PATH_PATTERN but has public segment
        result = resolve_bucket_pattern('test-bucket', '/site1/prod/public/file.html')
        
        # Should derive pattern from public segment placement
        assert result == '/site1/{stageId}/public'
    
    @patch('pattern_resolver.boto3.client')
    @patch('pattern_resolver.ORIGIN_PATH_PATTERN', '/{stageId}/public')
    def test_pattern_derivation_without_stage(self, mock_boto3_client):
        """Test pattern derivation for path without stage identifier."""
        # Mock S3 client to raise NoSuchTagSet
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        mock_s3.get_bucket_tagging.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchTagSet'}},
            'GetBucketTagging'
        )
        
        # Call with a path that has public but no stage
        result = resolve_bucket_pattern('test-bucket', '/public/file.html')
        
        # Should derive pattern without {stageId}
        assert result == '/public'
    
    @patch('pattern_resolver.boto3.client')
    @patch('pattern_resolver.ORIGIN_PATH_PATTERN', '/{stageId}/public')
    def test_nosuchtagset_exception_handling(self, mock_boto3_client):
        """Test that NoSuchTagSet exception is handled gracefully."""
        # Mock S3 client to raise NoSuchTagSet
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        mock_s3.get_bucket_tagging.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchTagSet'}},
            'GetBucketTagging'
        )
        
        # Should not raise exception
        result = resolve_bucket_pattern('test-bucket', '/prod/public/file.html')
        
        # Should return ORIGIN_PATH_PATTERN
        assert result == '/{stageId}/public'
    
    @patch('pattern_resolver.boto3.client')
    @patch('pattern_resolver.ORIGIN_PATH_PATTERN', '/{stageId}/public')
    def test_other_s3_errors_handled(self, mock_boto3_client):
        """Test that other S3 errors are handled gracefully."""
        # Mock S3 client to raise AccessDenied
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        mock_s3.get_bucket_tagging.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied'}},
            'GetBucketTagging'
        )
        
        # Should not raise exception
        result = resolve_bucket_pattern('test-bucket', '/prod/public/file.html')
        
        # Should fall back to ORIGIN_PATH_PATTERN
        assert result == '/{stageId}/public'
    
    @patch('pattern_resolver.boto3.client')
    @patch('pattern_resolver.ORIGIN_PATH_PATTERN', '/{stageId}/public')
    def test_fallback_when_no_public_segment(self, mock_boto3_client):
        """Test fallback to ORIGIN_PATH_PATTERN when path has no public segment."""
        # Mock S3 client to raise NoSuchTagSet
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        mock_s3.get_bucket_tagging.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchTagSet'}},
            'GetBucketTagging'
        )
        
        # Call with a path that has no public segment
        result = resolve_bucket_pattern('test-bucket', '/prod/assets/file.html')
        
        # Should fall back to ORIGIN_PATH_PATTERN
        assert result == '/{stageId}/public'
    
    @patch('pattern_resolver.boto3.client')
    def test_bucket_tag_with_multiple_tags(self, mock_boto3_client):
        """Test that correct tag is extracted when multiple tags exist."""
        # Mock S3 client to return multiple tags
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        mock_s3.get_bucket_tagging.return_value = {
            'TagSet': [
                {'Key': 'Environment', 'Value': 'prod'},
                {'Key': 'invalidator:OriginPathPattern', 'Value': '/my/pattern'},
                {'Key': 'Application', 'Value': 'myapp'}
            ]
        }
        
        # Call function
        result = resolve_bucket_pattern('test-bucket', '/prod/public/file.html')
        
        # Should return the invalidator:OriginPathPattern tag value
        assert result == '/my/pattern'
    
    @patch('pattern_resolver.boto3.client')
    def test_bucket_tag_normalizes_underscore_stageid(self, mock_boto3_client):
        """Test that @stageId@ in bucket tag is normalized to {stageId}."""
        # Mock S3 client to return tag with @stageId@ (AWS tags don't allow {})
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        mock_s3.get_bucket_tagging.return_value = {
            'TagSet': [
                {'Key': 'invalidator:OriginPathPattern', 'Value': '/@stageId@/public'}
            ]
        }
        
        # Call function
        result = resolve_bucket_pattern('test-bucket', '/prod/public/file.html')
        
        # Should normalize @stageId@ to {stageId}
        assert result == '/{stageId}/public'
        mock_s3.get_bucket_tagging.assert_called_once_with(Bucket='test-bucket')
    
    @patch('pattern_resolver.boto3.client')
    def test_bucket_tag_normalizes_complex_pattern(self, mock_boto3_client):
        """Test normalization of @stageId@ in complex patterns."""
        # Mock S3 client to return tag with @stageId@ in complex pattern
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        mock_s3.get_bucket_tagging.return_value = {
            'TagSet': [
                {'Key': 'invalidator:OriginPathPattern', 'Value': '/site1/@stageId@/public'}
            ]
        }
        
        # Call function
        result = resolve_bucket_pattern('test-bucket', '/site1/prod/public/file.html')
        
        # Should normalize @stageId@ to {stageId}
        assert result == '/site1/{stageId}/public'
    
    @patch('pattern_resolver.boto3.client')
    @patch('pattern_resolver.ORIGIN_PATH_PATTERN', '/public')
    def test_pattern_without_stage_placeholder(self, mock_boto3_client):
        """Test pattern matching when ORIGIN_PATH_PATTERN has no {stageId}."""
        # Mock S3 client to raise NoSuchTagSet
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        mock_s3.get_bucket_tagging.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchTagSet'}},
            'GetBucketTagging'
        )
        
        # Call with a path that matches pattern without stage
        result = resolve_bucket_pattern('test-bucket', '/public/file.html')
        
        # Should return ORIGIN_PATH_PATTERN
        assert result == '/public'



class TestFilterEventsByPattern:
    """Tests for filter_events_by_pattern function."""
    
    @patch('pattern_resolver.PRODUCTION_STAGE_IDENTIFIERS', ['prod', 'beta', 'stage', 'staging'])
    @patch('pattern_resolver.NON_PRODUCTION_STAGE_IDENTIFIERS', ['dev', 'test'])
    def test_pattern_matching_with_stage_placeholder(self):
        """Test pattern matching filters events correctly with {stageId}."""
        from pattern_resolver import filter_events_by_pattern
        
        events = [
            {'parsed_body': {'objectKey': '/prod/public/file1.html'}},
            {'parsed_body': {'objectKey': '/beta/public/file2.html'}},
            {'parsed_body': {'objectKey': '/dev/public/file3.html'}},
            {'parsed_body': {'objectKey': '/test/public/file4.html'}},
        ]
        
        result = filter_events_by_pattern(events, '/{stageId}/public')
        
        # Should only include prod and beta (production stages)
        assert len(result) == 2
        assert result[0]['parsed_body']['objectKey'] == '/prod/public/file1.html'
        assert result[1]['parsed_body']['objectKey'] == '/beta/public/file2.html'
    
    @patch('pattern_resolver.PRODUCTION_STAGE_IDENTIFIERS', ['prod'])
    @patch('pattern_resolver.NON_PRODUCTION_STAGE_IDENTIFIERS', ['dev'])
    def test_pattern_without_stage_placeholder(self):
        """Test pattern matching without {stageId} treats all as production."""
        from pattern_resolver import filter_events_by_pattern
        
        events = [
            {'parsed_body': {'objectKey': '/public/file1.html'}},
            {'parsed_body': {'objectKey': '/public/file2.html'}},
            {'parsed_body': {'objectKey': '/assets/file3.html'}},
        ]
        
        result = filter_events_by_pattern(events, '/public')
        
        # Should include all events that match pattern (no stage filtering)
        assert len(result) == 2
        assert result[0]['parsed_body']['objectKey'] == '/public/file1.html'
        assert result[1]['parsed_body']['objectKey'] == '/public/file2.html'
    
    @patch('pattern_resolver.PRODUCTION_STAGE_IDENTIFIERS', ['prod'])
    @patch('pattern_resolver.NON_PRODUCTION_STAGE_IDENTIFIERS', ['dev'])
    def test_tag_mismatch_filtering(self):
        """Test that events not matching bucket pattern are filtered out."""
        from pattern_resolver import filter_events_by_pattern
        
        events = [
            {'parsed_body': {'objectKey': '/prod/public/file1.html'}},
            {'parsed_body': {'objectKey': '/prod/assets/file2.html'}},
            {'parsed_body': {'objectKey': '/site1/prod/public/file3.html'}},
        ]
        
        # Bucket pattern is /{stageId}/public
        result = filter_events_by_pattern(events, '/{stageId}/public')
        
        # Should only include events matching /{stageId}/public pattern
        assert len(result) == 1
        assert result[0]['parsed_body']['objectKey'] == '/prod/public/file1.html'
    
    @patch('pattern_resolver.PRODUCTION_STAGE_IDENTIFIERS', ['prod', 'stage'])
    @patch('pattern_resolver.NON_PRODUCTION_STAGE_IDENTIFIERS', ['dev'])
    def test_production_stage_filtering(self):
        """Test that only production stages pass when pattern has {stageId}."""
        from pattern_resolver import filter_events_by_pattern
        
        events = [
            {'parsed_body': {'objectKey': '/prod/public/file1.html'}},
            {'parsed_body': {'objectKey': '/stage/public/file2.html'}},
            {'parsed_body': {'objectKey': '/dev/public/file3.html'}},
        ]
        
        result = filter_events_by_pattern(events, '/{stageId}/public')
        
        # Should only include prod and stage (production stages)
        assert len(result) == 2
        assert result[0]['parsed_body']['objectKey'] == '/prod/public/file1.html'
        assert result[1]['parsed_body']['objectKey'] == '/stage/public/file2.html'
    
    def test_empty_event_list(self):
        """Test that empty event list returns empty result."""
        from pattern_resolver import filter_events_by_pattern
        
        result = filter_events_by_pattern([], '/{stageId}/public')
        
        assert result == []
    
    def test_events_missing_object_key(self):
        """Test that events missing objectKey are filtered out."""
        from pattern_resolver import filter_events_by_pattern
        
        events = [
            {'parsed_body': {'objectKey': '/prod/public/file1.html'}},
            {'parsed_body': {}},  # Missing objectKey
            {'parsed_body': {'objectKey': ''}},  # Empty objectKey
        ]
        
        result = filter_events_by_pattern(events, '/{stageId}/public')
        
        # Should only include the valid event
        assert len(result) == 1
        assert result[0]['parsed_body']['objectKey'] == '/prod/public/file1.html'
    
    @patch('pattern_resolver.PRODUCTION_STAGE_IDENTIFIERS', ['prod'])
    @patch('pattern_resolver.NON_PRODUCTION_STAGE_IDENTIFIERS', ['dev'])
    def test_complex_pattern_matching(self):
        """Test pattern matching with complex patterns."""
        from pattern_resolver import filter_events_by_pattern
        
        events = [
            {'parsed_body': {'objectKey': '/site1/prod/public/file1.html'}},
            {'parsed_body': {'objectKey': '/site1/dev/public/file2.html'}},
            {'parsed_body': {'objectKey': '/site2/prod/public/file3.html'}},
        ]
        
        # Pattern for site1 only
        result = filter_events_by_pattern(events, '/site1/{stageId}/public')
        
        # Should only include site1 prod events
        assert len(result) == 1
        assert result[0]['parsed_body']['objectKey'] == '/site1/prod/public/file1.html'


class TestPatternMatchingWithNormalizedPaths:
    """Tests for pattern matching with normalized paths (leading slashes).
    
    These tests verify that the pattern matching logic works correctly with
    normalized S3 object keys that have leading slashes added by the event parser.
    
    Requirements tested: 2.1, 2.2, 2.3, 2.4, 5.2
    """
    
    @patch('pattern_resolver.PRODUCTION_STAGE_IDENTIFIERS', ['prod', 'production'])
    @patch('pattern_resolver.NON_PRODUCTION_STAGE_IDENTIFIERS', ['dev', 'test'])
    def test_normalized_paths_match_pattern_with_stage(self):
        """Test that normalized paths (with leading slash) match patterns correctly.
        
        Validates: Requirement 2.1, 2.2
        """
        from pattern_resolver import filter_events_by_pattern
        
        # All paths have leading slashes (normalized)
        events = [
            {'parsed_body': {'objectKey': '/prod/public/assets/file1.html'}},
            {'parsed_body': {'objectKey': '/production/public/js/file2.js'}},
            {'parsed_body': {'objectKey': '/dev/public/css/file3.css'}},
        ]
        
        result = filter_events_by_pattern(events, '/{stageId}/public')
        
        # Should match prod and production (production stages)
        assert len(result) == 2
        assert result[0]['parsed_body']['objectKey'] == '/prod/public/assets/file1.html'
        assert result[1]['parsed_body']['objectKey'] == '/production/public/js/file2.js'
    
    @patch('pattern_resolver.PRODUCTION_STAGE_IDENTIFIERS', ['prod'])
    @patch('pattern_resolver.NON_PRODUCTION_STAGE_IDENTIFIERS', ['dev'])
    def test_stage_extraction_from_normalized_paths(self):
        """Test that stage identifiers are correctly extracted from normalized paths.
        
        Validates: Requirement 2.3
        """
        from pattern_resolver import filter_events_by_pattern
        from common.path_utils import extract_stage_from_path
        
        # Normalized paths with leading slashes
        events = [
            {'parsed_body': {'objectKey': '/prod/public/file1.html'}},
            {'parsed_body': {'objectKey': '/dev/public/file2.html'}},
        ]
        
        result = filter_events_by_pattern(events, '/{stageId}/public')
        
        # Should only include prod
        assert len(result) == 1
        
        # Verify stage extraction works
        stage = extract_stage_from_path('/prod/public/file1.html', '/{stageId}/public')
        assert stage == 'prod'
        
        stage = extract_stage_from_path('/dev/public/file2.html', '/{stageId}/public')
        assert stage == 'dev'
    
    @patch('pattern_resolver.PRODUCTION_STAGE_IDENTIFIERS', ['prod'])
    @patch('pattern_resolver.NON_PRODUCTION_STAGE_IDENTIFIERS', ['dev'])
    def test_root_pattern_matches_all_normalized_paths(self):
        """Test that root pattern (/) matches all normalized paths.
        
        Validates: Requirement 2.4
        """
        from pattern_resolver import filter_events_by_pattern
        
        # Various normalized paths
        events = [
            {'parsed_body': {'objectKey': '/prod/public/file1.html'}},
            {'parsed_body': {'objectKey': '/dev/assets/file2.css'}},
            {'parsed_body': {'objectKey': '/public/file3.js'}},
            {'parsed_body': {'objectKey': '/site1/prod/public/file4.html'}},
        ]
        
        result = filter_events_by_pattern(events, '/')
        
        # Root pattern should match all paths
        assert len(result) == 4
    
    @patch('pattern_resolver.boto3.client')
    def test_bucket_tag_conversion_at_sign_to_braces(self, mock_boto3_client):
        """Test that @stageId@ in bucket tags is converted to {stageId}.
        
        Validates: Requirement 5.2
        """
        # Mock S3 client to return tag with @stageId@
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        mock_s3.get_bucket_tagging.return_value = {
            'TagSet': [
                {'Key': 'invalidator:OriginPathPattern', 'Value': '/@stageId@/public'}
            ]
        }
        
        result = resolve_bucket_pattern('test-bucket', '/prod/public/file.html')
        
        # Should convert @stageId@ to {stageId}
        assert result == '/{stageId}/public'
        assert '@stageId@' not in result
    
    @patch('pattern_resolver.PRODUCTION_STAGE_IDENTIFIERS', ['prod'])
    @patch('pattern_resolver.NON_PRODUCTION_STAGE_IDENTIFIERS', ['dev'])
    def test_normalized_paths_with_various_depths(self):
        """Test pattern matching with normalized paths at various depths.
        
        Validates: Requirement 2.2
        """
        from pattern_resolver import filter_events_by_pattern
        
        events = [
            {'parsed_body': {'objectKey': '/prod/public/file.html'}},
            {'parsed_body': {'objectKey': '/prod/public/assets/file.html'}},
            {'parsed_body': {'objectKey': '/prod/public/assets/js/file.html'}},
            {'parsed_body': {'objectKey': '/prod/public/assets/js/vendor/file.html'}},
        ]
        
        result = filter_events_by_pattern(events, '/{stageId}/public')
        
        # All should match regardless of depth after pattern
        assert len(result) == 4
    
    @patch('pattern_resolver.PRODUCTION_STAGE_IDENTIFIERS', ['prod'])
    @patch('pattern_resolver.NON_PRODUCTION_STAGE_IDENTIFIERS', ['dev'])
    def test_normalized_paths_with_special_characters(self):
        """Test pattern matching with normalized paths containing special characters.
        
        Validates: Requirement 2.2
        """
        from pattern_resolver import filter_events_by_pattern
        
        events = [
            {'parsed_body': {'objectKey': '/prod/public/file-name.html'}},
            {'parsed_body': {'objectKey': '/prod/public/file_name.html'}},
            {'parsed_body': {'objectKey': '/prod/public/file.name.html'}},
            {'parsed_body': {'objectKey': '/prod/public/file name.html'}},  # Space
        ]
        
        result = filter_events_by_pattern(events, '/{stageId}/public')
        
        # All should match
        assert len(result) == 4
    
    @patch('pattern_resolver.PRODUCTION_STAGE_IDENTIFIERS', ['prod'])
    @patch('pattern_resolver.NON_PRODUCTION_STAGE_IDENTIFIERS', ['dev'])
    def test_normalized_paths_without_leading_slash_filtered(self):
        """Test that paths without leading slashes don't match (shouldn't happen after normalization).
        
        Validates: Requirement 2.1
        """
        from pattern_resolver import filter_events_by_pattern
        
        # Mix of normalized and non-normalized paths (edge case)
        events = [
            {'parsed_body': {'objectKey': '/prod/public/file1.html'}},  # Normalized
            {'parsed_body': {'objectKey': 'prod/public/file2.html'}},   # Not normalized
        ]
        
        result = filter_events_by_pattern(events, '/{stageId}/public')
        
        # Only normalized path should match
        assert len(result) == 1
        assert result[0]['parsed_body']['objectKey'] == '/prod/public/file1.html'
    
    @patch('pattern_resolver.PRODUCTION_STAGE_IDENTIFIERS', ['prod', 'production', 'prd'])
    @patch('pattern_resolver.NON_PRODUCTION_STAGE_IDENTIFIERS', ['dev', 'development', 'test'])
    def test_multiple_production_stage_identifiers(self):
        """Test pattern matching with multiple production stage identifiers.
        
        Validates: Requirement 2.3
        """
        from pattern_resolver import filter_events_by_pattern
        
        events = [
            {'parsed_body': {'objectKey': '/prod/public/file1.html'}},
            {'parsed_body': {'objectKey': '/production/public/file2.html'}},
            {'parsed_body': {'objectKey': '/prd/public/file3.html'}},
            {'parsed_body': {'objectKey': '/dev/public/file4.html'}},
            {'parsed_body': {'objectKey': '/development/public/file5.html'}},
        ]
        
        result = filter_events_by_pattern(events, '/{stageId}/public')
        
        # Should include all production stages
        assert len(result) == 3
        assert result[0]['parsed_body']['objectKey'] == '/prod/public/file1.html'
        assert result[1]['parsed_body']['objectKey'] == '/production/public/file2.html'
        assert result[2]['parsed_body']['objectKey'] == '/prd/public/file3.html'
    
    @patch('pattern_resolver.PRODUCTION_STAGE_IDENTIFIERS', ['prod'])
    @patch('pattern_resolver.NON_PRODUCTION_STAGE_IDENTIFIERS', ['dev'])
    def test_pattern_matching_with_trailing_slashes(self):
        """Test that normalized paths with trailing slashes match correctly.
        
        Validates: Requirement 2.2
        """
        from pattern_resolver import filter_events_by_pattern
        
        events = [
            {'parsed_body': {'objectKey': '/prod/public/dir/'}},  # Trailing slash
            {'parsed_body': {'objectKey': '/prod/public/file.html'}},  # No trailing slash
        ]
        
        result = filter_events_by_pattern(events, '/{stageId}/public')
        
        # Both should match
        assert len(result) == 2
    
    @patch('pattern_resolver.boto3.client')
    def test_bucket_tag_with_complex_at_sign_pattern(self, mock_boto3_client):
        """Test conversion of @stageId@ in complex bucket tag patterns.
        
        Validates: Requirement 5.2
        """
        # Mock S3 client to return complex tag with @stageId@
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        mock_s3.get_bucket_tagging.return_value = {
            'TagSet': [
                {'Key': 'invalidator:OriginPathPattern', 'Value': '/app/@stageId@/public'}
            ]
        }
        
        result = resolve_bucket_pattern('test-bucket', '/app/prod/public/file.html')
        
        # Should convert @stageId@ to {stageId}
        assert result == '/app/{stageId}/public'
        assert '@stageId@' not in result
        assert '{stageId}' in result
