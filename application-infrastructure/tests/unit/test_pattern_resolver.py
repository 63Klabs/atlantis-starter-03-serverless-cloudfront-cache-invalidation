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
