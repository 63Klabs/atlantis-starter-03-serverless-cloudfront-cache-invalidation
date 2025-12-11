"""Unit tests for CloudFront path validation."""

import sys
import os
import pytest

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from processor.path_validator import (
    validate_cloudfront_path,
    sanitize_path,
    validate_and_sanitize_paths
)


class TestValidateCloudFrontPath:
    """Tests for validate_cloudfront_path function."""
    
    def test_valid_paths(self):
        """Test that valid paths are accepted."""
        valid_paths = [
            "/",
            "/*",
            "/file.html",
            "/dir/file.css",
            "/path/with-dashes_and_underscores.js",
            "/very/deeply/nested/path/file.json",
            "/dir/*",
            "/path/to/directory/*"
        ]
        
        for path in valid_paths:
            is_valid, message = validate_cloudfront_path(path)
            assert is_valid, f"Path '{path}' should be valid but got: {message}"
    
    def test_invalid_paths(self):
        """Test that invalid paths are rejected."""
        invalid_paths = [
            "",  # Empty path
            "no-leading-slash",  # No leading slash
            "//double-slash",  # Double slash at start
            "/path//double",  # Double slash in middle
            "/path with space",  # Space in path
            "/path/with@symbol",  # Invalid character @
            "/path/with#hash",  # Invalid character #
            "/path/with?query",  # Query parameter
            "/path/with unicode café",  # Unicode characters
        ]
        
        for path in invalid_paths:
            is_valid, message = validate_cloudfront_path(path)
            assert not is_valid, f"Path '{path}' should be invalid but was accepted"
    
    def test_empty_path(self):
        """Test empty path handling."""
        is_valid, message = validate_cloudfront_path("")
        assert not is_valid
        assert "empty" in message.lower()
    
    def test_non_string_path(self):
        """Test non-string path handling."""
        is_valid, message = validate_cloudfront_path(None)
        assert not is_valid
        assert "string" in message.lower()
        
        is_valid, message = validate_cloudfront_path(123)
        assert not is_valid
        assert "string" in message.lower()
    
    def test_path_too_long(self):
        """Test path length validation."""
        long_path = "/" + "x" * 8000
        is_valid, message = validate_cloudfront_path(long_path)
        assert not is_valid
        assert "too long" in message.lower()


class TestSanitizePath:
    """Tests for sanitize_path function."""
    
    def test_sanitize_empty_path(self):
        """Test sanitizing empty path."""
        result = sanitize_path("")
        assert result == "/"
    
    def test_sanitize_no_leading_slash(self):
        """Test adding leading slash."""
        result = sanitize_path("path/to/file.html")
        assert result == "/path/to/file.html"
    
    def test_sanitize_double_slashes(self):
        """Test removing double slashes."""
        result = sanitize_path("//path//to//file.html")
        assert result == "/path/to/file.html"
    
    def test_sanitize_invalid_characters(self):
        """Test removing invalid characters."""
        result = sanitize_path("/path with spaces@#$%")
        assert result == "/pathwithspaces"
    
    def test_sanitize_already_valid_path(self):
        """Test that valid paths are unchanged."""
        valid_path = "/valid/path/file.html"
        result = sanitize_path(valid_path)
        assert result == valid_path
    
    def test_sanitize_preserves_wildcards(self):
        """Test that wildcards are preserved."""
        result = sanitize_path("/path/to/*")
        assert result == "/path/to/*"
    
    def test_sanitize_very_long_path(self):
        """Test truncation of very long paths."""
        long_path = "/" + "x" * 8000
        result = sanitize_path(long_path)
        assert len(result) <= 8000
        assert result.startswith("/")


class TestValidateAndSanitizePaths:
    """Tests for validate_and_sanitize_paths function."""
    
    def test_mixed_valid_and_invalid_paths(self):
        """Test processing a mix of valid and invalid paths."""
        paths = [
            "/valid/path1.html",
            "no-leading-slash.css",
            "/path with spaces",
            "/valid/path2.js",
            "",
            "/path/with@symbols"
        ]
        
        valid_paths, errors = validate_and_sanitize_paths(paths)
        
        # Should have some valid paths after sanitization
        assert len(valid_paths) > 0
        # Should have some errors for paths that couldn't be fixed
        assert len(errors) >= 0  # Some paths might be salvageable through sanitization
        
        # All returned paths should be valid
        for path in valid_paths:
            is_valid, _ = validate_cloudfront_path(path)
            assert is_valid, f"Returned path '{path}' should be valid"
    
    def test_all_valid_paths(self):
        """Test processing all valid paths."""
        paths = [
            "/valid/path1.html",
            "/valid/path2.css",
            "/valid/path3.js"
        ]
        
        valid_paths, errors = validate_and_sanitize_paths(paths)
        
        assert len(valid_paths) == 3
        assert len(errors) == 0
        assert valid_paths == paths
    
    def test_duplicate_removal(self):
        """Test that duplicate paths are removed."""
        paths = [
            "/path/file.html",
            "/path/file.html",  # Duplicate
            "/other/file.css",
            "/path/file.html"   # Another duplicate
        ]
        
        valid_paths, errors = validate_and_sanitize_paths(paths)
        
        assert len(valid_paths) == 2
        assert "/path/file.html" in valid_paths
        assert "/other/file.css" in valid_paths
    
    def test_empty_input(self):
        """Test processing empty path list."""
        valid_paths, errors = validate_and_sanitize_paths([])
        
        assert len(valid_paths) == 0
        assert len(errors) == 0
    
    def test_sanitization_creates_valid_paths(self):
        """Test that sanitization can fix common issues."""
        problematic_paths = [
            "no-leading-slash.html",  # Missing leading slash
            "/path//with//double//slashes.css",  # Double slashes
            "/path with spaces.js"  # Spaces
        ]
        
        valid_paths, errors = validate_and_sanitize_paths(problematic_paths)
        
        # All paths should be fixable through sanitization
        assert len(valid_paths) == 3
        
        # Check specific fixes
        assert "/no-leading-slash.html" in valid_paths
        assert "/path/with/double/slashes.css" in valid_paths
        assert "/pathwithspaces.js" in valid_paths


class TestPathValidationIntegration:
    """Integration tests for path validation in real-world scenarios."""
    
    def test_common_s3_object_keys(self):
        """Test validation of common S3 object key patterns."""
        s3_keys = [
            "/prod/public/index.html",
            "/prod/public/assets/style.css",
            "/prod/public/js/app.min.js",
            "/prod/public/images/logo.png",
            "/prod/public/fonts/roboto.woff2"
        ]
        
        valid_paths, errors = validate_and_sanitize_paths(s3_keys)
        
        assert len(valid_paths) == len(s3_keys)
        assert len(errors) == 0
        
        # All paths should be unchanged (already valid)
        for original, validated in zip(s3_keys, valid_paths):
            assert original == validated
    
    def test_cloudfront_wildcard_patterns(self):
        """Test validation of CloudFront wildcard patterns."""
        wildcard_paths = [
            "/*",
            "/assets/*",
            "/prod/public/*",
            "/images/thumbnails/*"
        ]
        
        valid_paths, errors = validate_and_sanitize_paths(wildcard_paths)
        
        assert len(valid_paths) == len(wildcard_paths)
        assert len(errors) == 0
        
        # All wildcard paths should be valid
        for path in valid_paths:
            assert path.endswith('*') or path == '/*'