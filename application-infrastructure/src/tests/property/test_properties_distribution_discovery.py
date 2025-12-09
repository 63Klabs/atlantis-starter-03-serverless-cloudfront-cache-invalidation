"""Property-based tests for CloudFront distribution discovery in Processor."""

import sys
import os
from unittest.mock import patch, MagicMock

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from hypothesis import given, settings, strategies as st
from botocore.exceptions import ClientError
from processor.distribution_finder import (
    find_matching_distributions,
    list_distributions,
    _matches_bucket_origin
)


# Custom strategies for generating test data

@st.composite
def bucket_name_strategy(draw):
    """Generate valid S3 bucket names."""
    # S3 bucket names: 3-63 chars, lowercase letters, numbers, hyphens
    length = draw(st.integers(min_value=3, max_value=20))  # Shorter for simplicity
    
    # Start with letter or number
    first_char = draw(st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789'))
    
    # Middle characters
    if length > 2:
        middle_chars = draw(st.text(
            min_size=length - 2,
            max_size=length - 2,
            alphabet='abcdefghijklmnopqrstuvwxyz0123456789-'
        ))
    else:
        middle_chars = ''
    
    # End with letter or number
    if length > 1:
        last_char = draw(st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789'))
    else:
        last_char = ''
    
    bucket_name = first_char + middle_chars + last_char
    
    # Clean up consecutive hyphens
    while '--' in bucket_name:
        bucket_name = bucket_name.replace('--', '-')
    
    return bucket_name


@st.composite
def stage_id_strategy(draw):
    """Generate valid StageId values."""
    prefixes = ['p', 's', 'b', 't', 'd']
    prefix = draw(st.sampled_from(prefixes))
    suffix = draw(st.text(min_size=0, max_size=5, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'))
    return prefix + suffix


@st.composite
def origin_path_strategy(draw):
    """Generate valid origin paths."""
    stage_id = draw(stage_id_strategy())
    return f"/{stage_id}/public"



# Property Tests

@settings(max_examples=100)
@given(
    bucket_name_strategy(),
    origin_path_strategy(),
    st.integers(min_value=0, max_value=5),  # num matching
    st.integers(min_value=0, max_value=5)   # num non-matching
)
def test_property_18_distribution_matching_by_origin(bucket_name, origin_path, num_matching, num_non_matching):
    """Property 18: Distribution matching by origin.
    
    For any bucket name and origin path, searching CloudFront distributions
    should return all distributions where an origin's domainName matches the
    bucket (regional or global S3 domain) and originPath matches the event
    origin path.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 18: Distribution matching by origin**
    **Validates: Requirements 7.2**
    """
    # Build distributions manually
    distributions = []
    expected_matching_ids = []
    
    # Add matching distributions
    for i in range(num_matching):
        dist_id = f"MATCH{i:03d}{bucket_name[:10].upper()}"
        domain_name = f"{bucket_name}.s3.amazonaws.com"
        
        dist = {
            'Id': dist_id,
            'ARN': f'arn:aws:cloudfront::123456789012:distribution/{dist_id}',
            'Status': 'Deployed',
            'DomainName': f'{dist_id.lower()}.cloudfront.net',
            'Origins': {
                'Quantity': 1,
                'Items': [{
                    'Id': f'origin-{i}',
                    'DomainName': domain_name,
                    'OriginPath': origin_path,
                    'S3OriginConfig': {'OriginAccessIdentity': ''}
                }]
            },
            'Enabled': True
        }
        distributions.append(dist)
        expected_matching_ids.append(dist_id)
    
    # Add non-matching distributions (different bucket)
    for i in range(num_non_matching):
        dist_id = f"NOMATCH{i:03d}{bucket_name[:10].upper()}"
        different_bucket = f"different-{bucket_name}"
        domain_name = f"{different_bucket}.s3.amazonaws.com"
        
        dist = {
            'Id': dist_id,
            'ARN': f'arn:aws:cloudfront::123456789012:distribution/{dist_id}',
            'Status': 'Deployed',
            'DomainName': f'{dist_id.lower()}.cloudfront.net',
            'Origins': {
                'Quantity': 1,
                'Items': [{
                    'Id': f'origin-{i}',
                    'DomainName': domain_name,
                    'OriginPath': origin_path,
                    'S3OriginConfig': {'OriginAccessIdentity': ''}
                }]
            },
            'Enabled': True
        }
        distributions.append(dist)
    
    # Find matching distributions
    matching_ids = find_matching_distributions(bucket_name, origin_path, distributions)
    
    # Property: All and only distributions with matching origins should be returned
    assert set(matching_ids) == set(expected_matching_ids), \
        f"Expected matching IDs {expected_matching_ids} but got {matching_ids} " \
        f"for bucket '{bucket_name}' and origin path '{origin_path}'"


@settings(max_examples=100)
@given(
    bucket_name_strategy(),
    origin_path_strategy(),
    st.sampled_from(['us-east-1', 'us-west-2', 'eu-west-1'])
)
def test_property_18_regional_and_global_domain_formats(bucket_name, origin_path, region):
    """Property 18 (variant): Both regional and global S3 domain formats are matched.
    
    For any bucket, distributions with origins using either regional
    (bucket.s3.region.amazonaws.com) or global (bucket.s3.amazonaws.com)
    domain formats should be matched correctly.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 18: Distribution matching by origin**
    **Validates: Requirements 7.2, 7.4**
    """
    distributions = []
    expected_matching_ids = []
    
    # Create distribution with regional format
    regional_dist_id = f"REGIONAL{bucket_name[:10].upper()}"
    regional_dist = {
        'Id': regional_dist_id,
        'ARN': f'arn:aws:cloudfront::123456789012:distribution/{regional_dist_id}',
        'Status': 'Deployed',
        'DomainName': f'{regional_dist_id.lower()}.cloudfront.net',
        'Origins': {
            'Quantity': 1,
            'Items': [{
                'Id': 'origin-regional',
                'DomainName': f"{bucket_name}.s3.{region}.amazonaws.com",
                'OriginPath': origin_path,
                'S3OriginConfig': {'OriginAccessIdentity': ''}
            }]
        },
        'Enabled': True
    }
    distributions.append(regional_dist)
    expected_matching_ids.append(regional_dist_id)
    
    # Create distribution with global format
    global_dist_id = f"GLOBAL{bucket_name[:10].upper()}"
    global_dist = {
        'Id': global_dist_id,
        'ARN': f'arn:aws:cloudfront::123456789012:distribution/{global_dist_id}',
        'Status': 'Deployed',
        'DomainName': f'{global_dist_id.lower()}.cloudfront.net',
        'Origins': {
            'Quantity': 1,
            'Items': [{
                'Id': 'origin-global',
                'DomainName': f"{bucket_name}.s3.amazonaws.com",
                'OriginPath': origin_path,
                'S3OriginConfig': {'OriginAccessIdentity': ''}
            }]
        },
        'Enabled': True
    }
    distributions.append(global_dist)
    expected_matching_ids.append(global_dist_id)
    
    # Find matching distributions
    matching_ids = find_matching_distributions(bucket_name, origin_path, distributions)
    
    # Property: Both regional and global format distributions should be matched
    assert set(matching_ids) == set(expected_matching_ids), \
        f"Expected both regional and global format distributions to match. " \
        f"Expected {expected_matching_ids} but got {matching_ids}"


@settings(max_examples=100)
@given(
    bucket_name_strategy(),
    origin_path_strategy(),
    st.integers(min_value=1, max_value=10)
)
def test_property_19_multiple_distribution_targeting(bucket_name, origin_path, num_matching):
    """Property 19: Multiple distribution targeting.
    
    For any bucket and origin path that match multiple CloudFront distributions,
    all matching distributions should be included in the target list.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 19: Multiple distribution targeting**
    **Validates: Requirements 7.3**
    """
    distributions = []
    expected_matching_ids = []
    
    # Create multiple matching distributions
    for i in range(num_matching):
        dist_id = f"MATCH{i:03d}{bucket_name[:10].upper()}"
        
        dist = {
            'Id': dist_id,
            'ARN': f'arn:aws:cloudfront::123456789012:distribution/{dist_id}',
            'Status': 'Deployed',
            'DomainName': f'{dist_id.lower()}.cloudfront.net',
            'Origins': {
                'Quantity': 1,
                'Items': [{
                    'Id': f'origin-{i}',
                    'DomainName': f"{bucket_name}.s3.amazonaws.com",
                    'OriginPath': origin_path,
                    'S3OriginConfig': {'OriginAccessIdentity': ''}
                }]
            },
            'Enabled': True
        }
        distributions.append(dist)
        expected_matching_ids.append(dist_id)
    
    # Find matching distributions
    matching_ids = find_matching_distributions(bucket_name, origin_path, distributions)
    
    # Property: All matching distributions should be returned
    assert set(matching_ids) == set(expected_matching_ids), \
        f"Expected all {num_matching} matching distributions to be returned. " \
        f"Expected {expected_matching_ids} but got {matching_ids}"
    
    # Property: Number of matches should equal number of matching distributions
    assert len(matching_ids) == num_matching, \
        f"Expected {num_matching} matches but got {len(matching_ids)}"


@settings(max_examples=100)
@given(bucket_name_strategy(), origin_path_strategy())
def test_property_18_empty_distribution_list(bucket_name, origin_path):
    """Property 18 (variant): Empty distribution list returns empty results.
    
    For any bucket and origin path, if the distribution list is empty,
    an empty list should be returned.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 18: Distribution matching by origin**
    **Validates: Requirements 7.4**
    """
    # Empty distribution list
    distributions = []
    
    # Find matching distributions
    matching_ids = find_matching_distributions(bucket_name, origin_path, distributions)
    
    # Property: Should return empty list for empty input
    assert matching_ids == [], \
        f"Expected empty list for empty distribution list, but got {matching_ids}"
