"""Unit tests for distribution_finder module."""

import pytest
from unittest.mock import patch, MagicMock

from functions.processor.distribution_finder import (
    _matches_bucket_origin,
    find_matching_distributions
)


class TestMatchesBucketOrigin:
    """Tests for _matches_bucket_origin function."""
    
    def test_root_origin_path_with_empty_string(self):
        """Test that root origin path matches when CloudFront uses empty string."""
        origin = {
            'Id': 'S3-my-bucket',
            'DomainName': 'my-bucket.s3.us-east-1.amazonaws.com',
            'OriginPath': ''  # CloudFront uses empty string for root
        }
        
        # Our code uses "/" for root
        matches = _matches_bucket_origin(origin, 'my-bucket', '/')
        
        assert matches is True
    
    def test_root_origin_path_with_slash(self):
        """Test that root origin path matches when both use slash."""
        origin = {
            'Id': 'S3-my-bucket',
            'DomainName': 'my-bucket.s3.us-east-1.amazonaws.com',
            'OriginPath': '/'
        }
        
        matches = _matches_bucket_origin(origin, 'my-bucket', '/')
        
        assert matches is True
    
    def test_non_root_origin_path_matches(self):
        """Test that non-root origin paths match correctly."""
        origin = {
            'Id': 'S3-my-bucket',
            'DomainName': 'my-bucket.s3.us-east-1.amazonaws.com',
            'OriginPath': '/prod/public'
        }
        
        matches = _matches_bucket_origin(origin, 'my-bucket', '/prod/public')
        
        assert matches is True
    
    def test_non_root_origin_path_does_not_match(self):
        """Test that non-matching origin paths return False."""
        origin = {
            'Id': 'S3-my-bucket',
            'DomainName': 'my-bucket.s3.us-east-1.amazonaws.com',
            'OriginPath': '/prod/public'
        }
        
        matches = _matches_bucket_origin(origin, 'my-bucket', '/beta/public')
        
        assert matches is False
    
    def test_global_s3_domain_format(self):
        """Test matching with global S3 domain format."""
        origin = {
            'Id': 'S3-my-bucket',
            'DomainName': 'my-bucket.s3.amazonaws.com',
            'OriginPath': '/prod/public'
        }
        
        matches = _matches_bucket_origin(origin, 'my-bucket', '/prod/public')
        
        assert matches is True
    
    def test_regional_s3_domain_format(self):
        """Test matching with regional S3 domain format."""
        origin = {
            'Id': 'S3-my-bucket',
            'DomainName': 'my-bucket.s3.us-west-2.amazonaws.com',
            'OriginPath': '/prod/public'
        }
        
        matches = _matches_bucket_origin(origin, 'my-bucket', '/prod/public')
        
        assert matches is True
    
    def test_wrong_bucket_name(self):
        """Test that wrong bucket name returns False."""
        origin = {
            'Id': 'S3-other-bucket',
            'DomainName': 'other-bucket.s3.us-east-1.amazonaws.com',
            'OriginPath': '/prod/public'
        }
        
        matches = _matches_bucket_origin(origin, 'my-bucket', '/prod/public')
        
        assert matches is False
    
    def test_non_s3_domain(self):
        """Test that non-S3 domains return False."""
        origin = {
            'Id': 'Custom-Origin',
            'DomainName': 'example.com',
            'OriginPath': '/prod/public'
        }
        
        matches = _matches_bucket_origin(origin, 'my-bucket', '/prod/public')
        
        assert matches is False


class TestFindMatchingDistributions:
    """Tests for find_matching_distributions function."""
    
    def test_find_distribution_with_root_origin_path(self):
        """Test finding distributions with root origin path."""
        distributions = [
            {
                'Id': 'DIST123',
                'Origins': {
                    'Items': [
                        {
                            'Id': 'S3-my-bucket',
                            'DomainName': 'my-bucket.s3.us-east-1.amazonaws.com',
                            'OriginPath': ''  # CloudFront uses empty string
                        }
                    ]
                }
            }
        ]
        
        # Our code uses "/" for root
        result = find_matching_distributions('my-bucket', '/', distributions)
        
        assert result == ['DIST123']
    
    def test_find_distribution_with_non_root_origin_path(self):
        """Test finding distributions with non-root origin path."""
        distributions = [
            {
                'Id': 'DIST456',
                'Origins': {
                    'Items': [
                        {
                            'Id': 'S3-my-bucket',
                            'DomainName': 'my-bucket.s3.us-east-1.amazonaws.com',
                            'OriginPath': '/prod/public'
                        }
                    ]
                }
            }
        ]
        
        result = find_matching_distributions('my-bucket', '/prod/public', distributions)
        
        assert result == ['DIST456']
    
    def test_no_matching_distributions(self):
        """Test when no distributions match."""
        distributions = [
            {
                'Id': 'DIST789',
                'Origins': {
                    'Items': [
                        {
                            'Id': 'S3-other-bucket',
                            'DomainName': 'other-bucket.s3.us-east-1.amazonaws.com',
                            'OriginPath': '/prod/public'
                        }
                    ]
                }
            }
        ]
        
        result = find_matching_distributions('my-bucket', '/prod/public', distributions)
        
        assert result == []
    
    def test_multiple_matching_distributions(self):
        """Test finding multiple distributions that match."""
        distributions = [
            {
                'Id': 'DIST001',
                'Origins': {
                    'Items': [
                        {
                            'Id': 'S3-my-bucket',
                            'DomainName': 'my-bucket.s3.us-east-1.amazonaws.com',
                            'OriginPath': ''
                        }
                    ]
                }
            },
            {
                'Id': 'DIST002',
                'Origins': {
                    'Items': [
                        {
                            'Id': 'S3-my-bucket',
                            'DomainName': 'my-bucket.s3.us-west-2.amazonaws.com',
                            'OriginPath': ''
                        }
                    ]
                }
            }
        ]
        
        result = find_matching_distributions('my-bucket', '/', distributions)
        
        assert len(result) == 2
        assert 'DIST001' in result
        assert 'DIST002' in result
