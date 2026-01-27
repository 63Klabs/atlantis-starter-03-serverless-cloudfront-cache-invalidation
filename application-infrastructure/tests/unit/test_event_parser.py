"""Unit tests for event_parser module."""

import pytest
from functions.ingestor.event_parser import (
    normalize_s3_path,
    extract_event_metadata,
    S3EventParseError
)


class TestNormalizeS3Path:
    """Tests for normalize_s3_path function."""
    
    def test_normalize_path_without_leading_slash(self):
        """Test normalization of paths without leading slashes."""
        assert normalize_s3_path("app/prod/content/js/file.html") == "/app/prod/content/js/file.html"
        assert normalize_s3_path("prod/public/images/logo.png") == "/prod/public/images/logo.png"
        assert normalize_s3_path("stage/public/file.txt") == "/stage/public/file.txt"
    
    def test_normalize_path_with_leading_slash_idempotent(self):
        """Test idempotence - normalizing already normalized paths."""
        assert normalize_s3_path("/app/prod/content/js/file.html") == "/app/prod/content/js/file.html"
        assert normalize_s3_path("/prod/public/images/logo.png") == "/prod/public/images/logo.png"
        
        # Double normalization should produce same result
        path = "app/prod/file.html"
        normalized_once = normalize_s3_path(path)
        normalized_twice = normalize_s3_path(normalized_once)
        assert normalized_once == normalized_twice
    
    def test_normalize_empty_string(self):
        """Test edge case: empty string."""
        assert normalize_s3_path("") == ""
    
    def test_normalize_root_path(self):
        """Test edge case: root path."""
        assert normalize_s3_path("/") == "/"
    
    def test_normalize_multiple_consecutive_slashes(self):
        """Test edge case: multiple consecutive slashes."""
        assert normalize_s3_path("app//prod///file.html") == "/app/prod/file.html"
        assert normalize_s3_path("//double/slash") == "/double/slash"
        assert normalize_s3_path("///triple///slash") == "/triple/slash"
        assert normalize_s3_path("/already/leading//double") == "/already/leading/double"
    
    def test_normalize_trailing_slash_preservation(self):
        """Test trailing slash preservation."""
        assert normalize_s3_path("app/prod/") == "/app/prod/"
        assert normalize_s3_path("/app/prod/") == "/app/prod/"
        assert normalize_s3_path("folder/") == "/folder/"
    
    def test_normalize_single_segment(self):
        """Test normalization of single segment paths."""
        assert normalize_s3_path("file.html") == "/file.html"
        assert normalize_s3_path("/file.html") == "/file.html"
    
    def test_normalize_special_characters(self):
        """Test normalization with special characters in path."""
        assert normalize_s3_path("app/prod/file%20name.html") == "/app/prod/file%20name.html"
        assert normalize_s3_path("app/prod/file-name_v2.html") == "/app/prod/file-name_v2.html"


class TestExtractEventMetadataWithNormalization:
    """Tests for extract_event_metadata with path normalization."""
    
    def test_extract_metadata_normalizes_object_key(self):
        """Test that extract_event_metadata normalizes object keys."""
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': 'app/prod/content/js/file.html'}  # No leading slash
            },
            'eventTime': '2025-01-27T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        
        result = extract_event_metadata(record)
        
        assert result['bucketName'] == 'test-bucket'
        assert result['objectKey'] == '/app/prod/content/js/file.html'  # Should have leading slash
        assert result['eventTime'] == '2025-01-27T10:30:00.000Z'
        assert result['eventType'] == 'ObjectCreated:Put'
    
    def test_extract_metadata_with_already_normalized_path(self):
        """Test extraction with already normalized paths."""
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': '/prod/public/images/logo.png'}  # Already has leading slash
            },
            'eventTime': '2025-01-27T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        
        result = extract_event_metadata(record)
        
        assert result['objectKey'] == '/prod/public/images/logo.png'  # Should remain unchanged
    
    def test_extract_metadata_with_multiple_slashes(self):
        """Test extraction normalizes multiple consecutive slashes."""
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': 'app//prod///file.html'}  # Multiple slashes
            },
            'eventTime': '2025-01-27T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        
        result = extract_event_metadata(record)
        
        assert result['objectKey'] == '/app/prod/file.html'  # Slashes collapsed
    
    def test_extract_metadata_missing_bucket_name(self):
        """Test error handling for missing bucket name."""
        record = {
            's3': {
                'bucket': {},  # Missing 'name'
                'object': {'key': 'app/prod/file.html'}
            },
            'eventTime': '2025-01-27T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        
        with pytest.raises(S3EventParseError):
            extract_event_metadata(record)
    
    def test_extract_metadata_missing_object_key(self):
        """Test error handling for missing object key."""
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {}  # Missing 'key'
            },
            'eventTime': '2025-01-27T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        
        with pytest.raises(S3EventParseError):
            extract_event_metadata(record)
    
    def test_extract_metadata_empty_object_key(self):
        """Test error handling for empty object key."""
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': ''}  # Empty key
            },
            'eventTime': '2025-01-27T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        
        with pytest.raises(S3EventParseError):
            extract_event_metadata(record)
    
    def test_extract_metadata_missing_s3_section(self):
        """Test error handling for missing s3 section."""
        record = {
            'eventTime': '2025-01-27T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        
        with pytest.raises(S3EventParseError) as exc_info:
            extract_event_metadata(record)
        assert "Missing required field" in str(exc_info.value)
    
    def test_extract_metadata_missing_event_time(self):
        """Test error handling for missing eventTime."""
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': 'app/prod/file.html'}
            },
            'eventName': 'ObjectCreated:Put'
        }
        
        with pytest.raises(S3EventParseError) as exc_info:
            extract_event_metadata(record)
        assert "Missing required field" in str(exc_info.value)
    
    def test_extract_metadata_missing_event_name(self):
        """Test error handling for missing eventName."""
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': 'app/prod/file.html'}
            },
            'eventTime': '2025-01-27T10:30:00.000Z'
        }
        
        with pytest.raises(S3EventParseError) as exc_info:
            extract_event_metadata(record)
        assert "Missing required field" in str(exc_info.value)
    
    def test_extract_metadata_invalid_record_type(self):
        """Test error handling for invalid record type (not a dict)."""
        record = "invalid_string_record"
        
        with pytest.raises(S3EventParseError) as exc_info:
            extract_event_metadata(record)
        # Should raise error about invalid structure or type
        assert "Invalid S3 event structure" in str(exc_info.value) or "Missing required field" in str(exc_info.value)
    
    def test_extract_metadata_none_record(self):
        """Test error handling for None record."""
        record = None
        
        with pytest.raises(S3EventParseError) as exc_info:
            extract_event_metadata(record)
        # Should raise error about invalid structure
        assert "Invalid S3 event structure" in str(exc_info.value) or "Missing required field" in str(exc_info.value)
    
    def test_extract_metadata_empty_bucket_name(self):
        """Test error handling for empty bucket name."""
        record = {
            's3': {
                'bucket': {'name': ''},  # Empty bucket name
                'object': {'key': 'app/prod/file.html'}
            },
            'eventTime': '2025-01-27T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        
        with pytest.raises(S3EventParseError) as exc_info:
            extract_event_metadata(record)
        assert "required fields are empty" in str(exc_info.value).lower()
    
    def test_extract_metadata_empty_event_time(self):
        """Test error handling for empty eventTime."""
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': 'app/prod/file.html'}
            },
            'eventTime': '',  # Empty event time
            'eventName': 'ObjectCreated:Put'
        }
        
        with pytest.raises(S3EventParseError) as exc_info:
            extract_event_metadata(record)
        assert "required fields are empty" in str(exc_info.value).lower()
    
    def test_extract_metadata_empty_event_name(self):
        """Test error handling for empty eventName."""
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': 'app/prod/file.html'}
            },
            'eventTime': '2025-01-27T10:30:00.000Z',
            'eventName': ''  # Empty event name
        }
        
        with pytest.raises(S3EventParseError) as exc_info:
            extract_event_metadata(record)
        assert "required fields are empty" in str(exc_info.value).lower()
    
    def test_extract_metadata_with_nested_path(self):
        """Test extraction with deeply nested path that needs normalization."""
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': 'app/prod/content/js/modules/utils/helper.js'}
            },
            'eventTime': '2025-01-27T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        
        result = extract_event_metadata(record)
        
        assert result['objectKey'] == '/app/prod/content/js/modules/utils/helper.js'
        assert result['bucketName'] == 'test-bucket'
    
    def test_extract_metadata_with_special_characters(self):
        """Test extraction with special characters in path."""
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': 'app/prod/file%20name.html'}
            },
            'eventTime': '2025-01-27T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        
        result = extract_event_metadata(record)
        
        assert result['objectKey'] == '/app/prod/file%20name.html'
    
    def test_extract_metadata_with_trailing_slash(self):
        """Test extraction with trailing slash in path."""
        record = {
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': 'app/prod/folder/'}
            },
            'eventTime': '2025-01-27T10:30:00.000Z',
            'eventName': 'ObjectCreated:Put'
        }
        
        result = extract_event_metadata(record)
        
        assert result['objectKey'] == '/app/prod/folder/'  # Trailing slash preserved
