"""Property-based tests for S3 bucket tag validation in Processor."""

import sys
import os
from unittest.mock import patch, MagicMock

from hypothesis import given, settings, strategies as st
from botocore.exceptions import ClientError
from functions.processor.tag_validator import (
    validate_bucket_tags,
    get_bucket_tags,
    validate_distribution_tags,
    get_distribution_tags
)


# Custom strategies for generating test data

@st.composite
def bucket_name_strategy(draw):
    """Generate valid S3 bucket names."""
    # S3 bucket names: 3-63 chars, lowercase letters, numbers, hyphens, dots
    # Must start and end with letter or number
    length = draw(st.integers(min_value=3, max_value=63))
    
    # Start with letter or number
    first_char = draw(st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789'))
    
    # Middle characters can include hyphens and dots
    if length > 2:
        middle_chars = draw(st.text(
            min_size=length - 2,
            max_size=length - 2,
            alphabet='abcdefghijklmnopqrstuvwxyz0123456789-.'
        ))
    else:
        middle_chars = ''
    
    # End with letter or number
    if length > 1:
        last_char = draw(st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789'))
    else:
        last_char = ''
    
    bucket_name = first_char + middle_chars + last_char
    
    # Ensure no consecutive dots or dot-dash combinations (S3 rules)
    while '..' in bucket_name or '.-' in bucket_name or '-.' in bucket_name:
        bucket_name = bucket_name.replace('..', '.').replace('.-', '-').replace('-.', '-')
    
    return bucket_name


@st.composite
def tag_dict_with_allow_true(draw):
    """Generate tag dictionary with AllowInvalidationEvents=true."""
    # Generate additional random tags
    num_extra_tags = draw(st.integers(min_value=0, max_value=5))
    
    tags = {'AllowInvalidationEvents': 'true'}
    
    for _ in range(num_extra_tags):
        key = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_:'
        )))
        value = draw(st.text(min_size=0, max_size=50, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_:. '
        )))
        
        # Don't override the required tag
        if key != 'AllowInvalidationEvents':
            tags[key] = value
    
    return tags


@st.composite
def tag_dict_without_allow_or_false(draw):
    """Generate tag dictionary without AllowInvalidationEvents or with non-true value."""
    # Choose whether to include the tag with wrong value or omit it
    include_tag = draw(st.booleans())
    
    tags = {}
    
    if include_tag:
        # Include tag but with wrong value
        wrong_value = draw(st.text(min_size=0, max_size=20).filter(lambda x: x != 'true'))
        tags['AllowInvalidationEvents'] = wrong_value
    
    # Generate additional random tags
    num_extra_tags = draw(st.integers(min_value=0, max_value=5))
    
    for _ in range(num_extra_tags):
        key = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_:'
        )))
        value = draw(st.text(min_size=0, max_size=50, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_:. '
        )))
        
        # Don't override the required tag
        if key != 'AllowInvalidationEvents':
            tags[key] = value
    
    return tags


# Property Tests

@settings(max_examples=100)
@given(bucket_name_strategy(), tag_dict_with_allow_true())
def test_property_14_bucket_tag_validation_allowed(bucket_name, tags):
    """Property 14: Bucket tag validation for allowed buckets.
    
    For any bucket with the AllowInvalidationEvents tag set to "true",
    the tag validation should return true and allow processing.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 14: Bucket tag validation for allowed buckets**
    **Validates: Requirements 6.2**
    """
    # Mock the S3 client to return the generated tags
    with patch('processor.tag_validator.s3_client') as mock_s3:
        # Convert tags dict to AWS TagSet format
        tag_set = [{'Key': k, 'Value': v} for k, v in tags.items()]
        
        mock_s3.get_bucket_tagging.return_value = {
            'TagSet': tag_set
        }
        
        # Validate the bucket
        result = validate_bucket_tags(bucket_name)
        
        # Property: Bucket with AllowInvalidationEvents=true should be valid
        assert result is True, \
            f"Expected validation to pass for bucket '{bucket_name}' with tags {tags}"
        
        # Verify the S3 API was called with correct bucket name
        mock_s3.get_bucket_tagging.assert_called_once_with(Bucket=bucket_name)


@settings(max_examples=100)
@given(bucket_name_strategy(), tag_dict_with_allow_true())
def test_property_14_get_bucket_tags_returns_correct_tags(bucket_name, tags):
    """Property 14 (variant): get_bucket_tags returns correct tag dictionary.
    
    For any bucket with tags, get_bucket_tags should return a dictionary
    that matches the tags on the bucket.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 14: Bucket tag validation for allowed buckets**
    **Validates: Requirements 6.1**
    """
    # Mock the S3 client to return the generated tags
    with patch('processor.tag_validator.s3_client') as mock_s3:
        # Convert tags dict to AWS TagSet format
        tag_set = [{'Key': k, 'Value': v} for k, v in tags.items()]
        
        mock_s3.get_bucket_tagging.return_value = {
            'TagSet': tag_set
        }
        
        # Get the bucket tags
        result = get_bucket_tags(bucket_name)
        
        # Property: Returned tags should match input tags
        assert result == tags, \
            f"Expected tags {tags} but got {result}"
        
        # Verify the S3 API was called with correct bucket name
        mock_s3.get_bucket_tagging.assert_called_once_with(Bucket=bucket_name)


@settings(max_examples=100)
@given(bucket_name_strategy())
def test_property_14_empty_tags_handled_correctly(bucket_name):
    """Property 14 (variant): Buckets with no tags are handled correctly.
    
    For any bucket with no tags (NoSuchTagSet error), get_bucket_tags
    should return an empty dictionary, and validation should fail.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 14: Bucket tag validation for allowed buckets**
    **Validates: Requirements 6.4**
    """
    # Mock the S3 client to raise NoSuchTagSet error
    with patch('processor.tag_validator.s3_client') as mock_s3:
        error_response = {
            'Error': {
                'Code': 'NoSuchTagSet',
                'Message': 'The TagSet does not exist'
            }
        }
        mock_s3.get_bucket_tagging.side_effect = ClientError(
            error_response,
            'GetBucketTagging'
        )
        
        # Get the bucket tags
        tags = get_bucket_tags(bucket_name)
        
        # Property: Should return empty dict for NoSuchTagSet
        assert tags == {}, \
            f"Expected empty dict for bucket with no tags, got {tags}"
        
        # Validate the bucket (should fail with no tags)
        result = validate_bucket_tags(bucket_name)
        
        # Property: Validation should fail for bucket with no tags
        assert result is False, \
            f"Expected validation to fail for bucket '{bucket_name}' with no tags"


@settings(max_examples=100)
@given(bucket_name_strategy(), tag_dict_without_allow_or_false())
def test_property_15_bucket_tag_validation_disallowed(bucket_name, tags):
    """Property 15: Bucket tag validation for disallowed buckets.
    
    For any bucket without the AllowInvalidationEvents tag or with a value
    other than "true", the tag validation should return false and skip processing.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 15: Bucket tag validation for disallowed buckets**
    **Validates: Requirements 6.3**
    """
    # Mock the S3 client to return the generated tags
    with patch('processor.tag_validator.s3_client') as mock_s3:
        # Convert tags dict to AWS TagSet format
        tag_set = [{'Key': k, 'Value': v} for k, v in tags.items()]
        
        mock_s3.get_bucket_tagging.return_value = {
            'TagSet': tag_set
        }
        
        # Validate the bucket
        result = validate_bucket_tags(bucket_name)
        
        # Property: Bucket without AllowInvalidationEvents=true should be invalid
        assert result is False, \
            f"Expected validation to fail for bucket '{bucket_name}' with tags {tags}"
        
        # Verify the S3 API was called with correct bucket name
        mock_s3.get_bucket_tagging.assert_called_once_with(Bucket=bucket_name)


@settings(max_examples=100)
@given(bucket_name_strategy())
def test_property_15_api_errors_result_in_validation_failure(bucket_name):
    """Property 15 (variant): API errors result in validation failure.
    
    For any bucket where GetBucketTagging fails with an error (other than
    NoSuchTagSet), the validation should fail gracefully and return false.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 15: Bucket tag validation for disallowed buckets**
    **Validates: Requirements 6.4**
    """
    # Mock the S3 client to raise various errors
    error_codes = ['AccessDenied', 'NoSuchBucket', 'ServiceUnavailable', 'InternalError']
    
    for error_code in error_codes:
        with patch('processor.tag_validator.s3_client') as mock_s3:
            error_response = {
                'Error': {
                    'Code': error_code,
                    'Message': f'Test error: {error_code}'
                }
            }
            mock_s3.get_bucket_tagging.side_effect = ClientError(
                error_response,
                'GetBucketTagging'
            )
            
            # Get the bucket tags (should return None on error)
            tags = get_bucket_tags(bucket_name)
            
            # Property: Should return None for API errors
            assert tags is None, \
                f"Expected None for {error_code} error, got {tags}"
            
            # Validate the bucket (should fail on error)
            result = validate_bucket_tags(bucket_name)
            
            # Property: Validation should fail when tags cannot be retrieved
            assert result is False, \
                f"Expected validation to fail for bucket '{bucket_name}' with {error_code} error"


@settings(max_examples=100)
@given(bucket_name_strategy(), tag_dict_without_allow_or_false())
def test_property_15_case_sensitive_tag_value(bucket_name, tags):
    """Property 15 (variant): Tag value validation is case-sensitive.
    
    For any bucket with AllowInvalidationEvents set to a value other than
    exactly "true" (e.g., "True", "TRUE", "yes"), validation should fail.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 15: Bucket tag validation for disallowed buckets**
    **Validates: Requirements 6.3**
    """
    # Add variations of "true" that should NOT pass validation
    case_variations = ['True', 'TRUE', 'tRuE', 'yes', 'Yes', 'YES', '1', 'enabled']
    
    for variation in case_variations:
        with patch('processor.tag_validator.s3_client') as mock_s3:
            # Create tags with the variation
            test_tags = tags.copy()
            test_tags['AllowInvalidationEvents'] = variation
            
            # Convert tags dict to AWS TagSet format
            tag_set = [{'Key': k, 'Value': v} for k, v in test_tags.items()]
            
            mock_s3.get_bucket_tagging.return_value = {
                'TagSet': tag_set
            }
            
            # Validate the bucket
            result = validate_bucket_tags(bucket_name)
            
            # Property: Only exactly "true" should pass validation
            assert result is False, \
                f"Expected validation to fail for bucket '{bucket_name}' with " \
                f"AllowInvalidationEvents='{variation}' (case-sensitive check)"



# CloudFront Distribution Tag Validation Property Tests

@st.composite
def distribution_id_strategy(draw):
    """Generate valid CloudFront distribution IDs."""
    # CloudFront distribution IDs are alphanumeric strings, typically 13-14 chars
    # Example: E1234ABCDEFGHI
    length = draw(st.integers(min_value=10, max_value=20))
    return draw(st.text(
        min_size=length,
        max_size=length,
        alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    ))


@st.composite
def stage_id_strategy(draw):
    """Generate valid StageId values."""
    # StageIds can be prod, stage, beta, or p*, s*, b* patterns
    stage_type = draw(st.sampled_from(['prod', 'stage', 'beta', 'p', 's', 'b']))
    
    if stage_type in ['prod', 'stage', 'beta']:
        return stage_type
    else:
        # Generate p*, s*, b* patterns
        suffix = draw(st.text(min_size=1, max_size=10, alphabet='abcdefghijklmnopqrstuvwxyz0123456789-'))
        return stage_type + suffix


@st.composite
def app_tag_strategy(draw):
    """Generate valid application tag values."""
    # Application tags are typically alphanumeric with hyphens
    # Example: my-app, acme-web, static-assets
    return draw(st.text(
        min_size=3,
        max_size=30,
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789-'
    ).filter(lambda x: not x.startswith('-') and not x.endswith('-')))


@st.composite
def distribution_tags_with_valid_deployment_id(draw, bucket_app_tag, stage_id):
    """Generate distribution tag dictionary with valid AllowInvalidationEvents and ApplicationDeploymentId."""
    # Generate additional random tags
    num_extra_tags = draw(st.integers(min_value=0, max_value=5))
    
    tags = {
        'AllowInvalidationEvents': 'true',
        'atlantis:ApplicationDeploymentId': f"{bucket_app_tag}-{stage_id}"
    }
    
    for _ in range(num_extra_tags):
        key = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_:'
        )))
        value = draw(st.text(min_size=0, max_size=50, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_:. '
        )))
        
        # Don't override the required tags
        if key not in ['AllowInvalidationEvents', 'atlantis:ApplicationDeploymentId']:
            tags[key] = value
    
    return tags


@st.composite
def distribution_tags_invalid(draw, bucket_app_tag, stage_id):
    """Generate distribution tag dictionary with invalid or missing tags."""
    # Choose what to make invalid
    invalid_type = draw(st.sampled_from([
        'missing_allow',
        'wrong_allow_value',
        'missing_app_id',
        'wrong_app_id',
        'both_wrong'
    ]))
    
    tags = {}
    
    if invalid_type == 'missing_allow':
        # Missing AllowInvalidationEvents, but correct ApplicationDeploymentId
        tags['atlantis:ApplicationDeploymentId'] = f"{bucket_app_tag}-{stage_id}"
    
    elif invalid_type == 'wrong_allow_value':
        # Wrong AllowInvalidationEvents value, correct ApplicationDeploymentId
        wrong_value = draw(st.text(min_size=0, max_size=20).filter(lambda x: x != 'true'))
        tags['AllowInvalidationEvents'] = wrong_value
        tags['atlantis:ApplicationDeploymentId'] = f"{bucket_app_tag}-{stage_id}"
    
    elif invalid_type == 'missing_app_id':
        # Correct AllowInvalidationEvents, missing ApplicationDeploymentId
        tags['AllowInvalidationEvents'] = 'true'
    
    elif invalid_type == 'wrong_app_id':
        # Correct AllowInvalidationEvents, wrong ApplicationDeploymentId
        tags['AllowInvalidationEvents'] = 'true'
        # Generate a different app ID that doesn't match
        wrong_app_id = draw(st.text(min_size=1, max_size=50).filter(
            lambda x: x != f"{bucket_app_tag}-{stage_id}"
        ))
        tags['atlantis:ApplicationDeploymentId'] = wrong_app_id
    
    elif invalid_type == 'both_wrong':
        # Both tags wrong or missing
        if draw(st.booleans()):
            wrong_value = draw(st.text(min_size=0, max_size=20).filter(lambda x: x != 'true'))
            tags['AllowInvalidationEvents'] = wrong_value
        # else: missing AllowInvalidationEvents
        
        if draw(st.booleans()):
            wrong_app_id = draw(st.text(min_size=1, max_size=50).filter(
                lambda x: x != f"{bucket_app_tag}-{stage_id}"
            ))
            tags['atlantis:ApplicationDeploymentId'] = wrong_app_id
        # else: missing ApplicationDeploymentId
    
    # Generate additional random tags
    num_extra_tags = draw(st.integers(min_value=0, max_value=5))
    
    for _ in range(num_extra_tags):
        key = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_:'
        )))
        value = draw(st.text(min_size=0, max_size=50, alphabet=st.characters(
            whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='-_:. '
        )))
        
        # Don't override the required tags
        if key not in ['AllowInvalidationEvents', 'atlantis:ApplicationDeploymentId']:
            tags[key] = value
    
    return tags


@st.composite
def valid_distribution_test_data(draw):
    """Generate test data for valid distribution tag validation."""
    distribution_id = draw(distribution_id_strategy())
    bucket_app_tag = draw(app_tag_strategy())
    stage_id = draw(stage_id_strategy())
    tags = draw(distribution_tags_with_valid_deployment_id(bucket_app_tag, stage_id))
    return (distribution_id, bucket_app_tag, stage_id, tags)


@settings(max_examples=100)
@given(valid_distribution_test_data())
def test_property_16_distribution_tag_validation_allowed(test_data):
    """Property 16: Distribution tag validation for allowed distributions.
    
    For any CloudFront distribution with AllowInvalidationEvents="true" and
    atlantis:ApplicationDeploymentId matching <bucket-app-tag>-<StageId>,
    the tag validation should return true and allow invalidation.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 16: Distribution tag validation for allowed distributions**
    **Validates: Requirements 8.2**
    """
    distribution_id, bucket_app_tag, stage_id, tags = test_data
    
    # Mock both CloudFront and STS clients
    with patch('processor.tag_validator.cloudfront_client') as mock_cf, \
         patch('processor.tag_validator.boto3.client') as mock_boto3_client:
        
        # Mock STS client for account ID
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # Configure boto3.client to return appropriate mocks
        def client_factory(service_name):
            if service_name == 'sts':
                return mock_sts
            return MagicMock()
        
        mock_boto3_client.side_effect = client_factory
        
        # Convert tags dict to AWS Tags format
        tag_items = [{'Key': k, 'Value': v} for k, v in tags.items()]
        
        mock_cf.list_tags_for_resource.return_value = {
            'Tags': {
                'Items': tag_items
            }
        }
        
        # Validate the distribution
        result = validate_distribution_tags(distribution_id, bucket_app_tag, stage_id)
        
        # Property: Distribution with correct tags should be valid
        assert result is True, \
            f"Expected validation to pass for distribution '{distribution_id}' with " \
            f"bucket_app_tag='{bucket_app_tag}', stage_id='{stage_id}', tags={tags}"
        
        # Verify the CloudFront API was called
        assert mock_cf.list_tags_for_resource.called


@st.composite
def invalid_distribution_test_data(draw):
    """Generate test data for invalid distribution tag validation."""
    distribution_id = draw(distribution_id_strategy())
    bucket_app_tag = draw(app_tag_strategy())
    stage_id = draw(stage_id_strategy())
    tags = draw(distribution_tags_invalid(bucket_app_tag, stage_id))
    return (distribution_id, bucket_app_tag, stage_id, tags)


@settings(max_examples=100)
@given(invalid_distribution_test_data())
def test_property_17_distribution_tag_validation_disallowed(test_data):
    """Property 17: Distribution tag validation for disallowed distributions.
    
    For any CloudFront distribution without AllowInvalidationEvents="true" or
    with mismatched atlantis:ApplicationDeploymentId, the tag validation should
    return false and skip invalidation.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 17: Distribution tag validation for disallowed distributions**
    **Validates: Requirements 8.3**
    """
    distribution_id, bucket_app_tag, stage_id, tags = test_data
    
    # Mock both CloudFront and STS clients
    with patch('processor.tag_validator.cloudfront_client') as mock_cf, \
         patch('processor.tag_validator.boto3.client') as mock_boto3_client:
        
        # Mock STS client for account ID
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # Configure boto3.client to return appropriate mocks
        def client_factory(service_name):
            if service_name == 'sts':
                return mock_sts
            return MagicMock()
        
        mock_boto3_client.side_effect = client_factory
        
        # Convert tags dict to AWS Tags format
        tag_items = [{'Key': k, 'Value': v} for k, v in tags.items()]
        
        mock_cf.list_tags_for_resource.return_value = {
            'Tags': {
                'Items': tag_items
            }
        }
        
        # Validate the distribution
        result = validate_distribution_tags(distribution_id, bucket_app_tag, stage_id)
        
        # Property: Distribution with incorrect tags should be invalid
        assert result is False, \
            f"Expected validation to fail for distribution '{distribution_id}' with " \
            f"bucket_app_tag='{bucket_app_tag}', stage_id='{stage_id}', tags={tags}"
        
        # Verify the CloudFront API was called
        assert mock_cf.list_tags_for_resource.called


@settings(max_examples=100)
@given(
    distribution_id_strategy(),
    app_tag_strategy(),
    stage_id_strategy()
)
def test_property_17_api_errors_result_in_validation_failure(distribution_id, bucket_app_tag, stage_id):
    """Property 17 (variant): API errors result in validation failure.
    
    For any distribution where ListTagsForResource fails with an error,
    the validation should fail gracefully and return false.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 17: Distribution tag validation for disallowed distributions**
    **Validates: Requirements 8.4**
    """
    # Mock CloudFront client to raise various errors
    error_codes = ['AccessDenied', 'NoSuchDistribution', 'InvalidArgument', 'ServiceUnavailable']
    
    for error_code in error_codes:
        with patch('processor.tag_validator.cloudfront_client') as mock_cf, \
             patch('processor.tag_validator.boto3.client') as mock_boto3_client:
            
            # Mock STS client for account ID
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
            
            # Configure boto3.client to return appropriate mocks
            def client_factory(service_name):
                if service_name == 'sts':
                    return mock_sts
                return MagicMock()
            
            mock_boto3_client.side_effect = client_factory
            
            error_response = {
                'Error': {
                    'Code': error_code,
                    'Message': f'Test error: {error_code}'
                }
            }
            mock_cf.list_tags_for_resource.side_effect = ClientError(
                error_response,
                'ListTagsForResource'
            )
            
            # Get the distribution tags (should return None on error)
            tags = get_distribution_tags(distribution_id)
            
            # Property: Should return None for API errors
            assert tags is None, \
                f"Expected None for {error_code} error, got {tags}"
            
            # Validate the distribution (should fail on error)
            result = validate_distribution_tags(distribution_id, bucket_app_tag, stage_id)
            
            # Property: Validation should fail when tags cannot be retrieved
            assert result is False, \
                f"Expected validation to fail for distribution '{distribution_id}' with {error_code} error"


@settings(max_examples=100)
@given(valid_distribution_test_data())
def test_property_16_get_distribution_tags_returns_correct_tags(test_data):
    """Property 16 (variant): get_distribution_tags returns correct tag dictionary.
    
    For any distribution with tags, get_distribution_tags should return a dictionary
    that matches the tags on the distribution.
    
    **Feature: multi-bucket-cloudfront-invalidation, Property 16: Distribution tag validation for allowed distributions**
    **Validates: Requirements 8.1**
    """
    distribution_id, bucket_app_tag, stage_id, tags = test_data
    
    # Mock both CloudFront and STS clients
    with patch('processor.tag_validator.cloudfront_client') as mock_cf, \
         patch('processor.tag_validator.boto3.client') as mock_boto3_client:
        
        # Mock STS client for account ID
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # Configure boto3.client to return appropriate mocks
        def client_factory(service_name):
            if service_name == 'sts':
                return mock_sts
            return MagicMock()
        
        mock_boto3_client.side_effect = client_factory
        
        # Convert tags dict to AWS Tags format
        tag_items = [{'Key': k, 'Value': v} for k, v in tags.items()]
        
        mock_cf.list_tags_for_resource.return_value = {
            'Tags': {
                'Items': tag_items
            }
        }
        
        # Get the distribution tags
        result = get_distribution_tags(distribution_id)
        
        # Property: Returned tags should match input tags
        assert result == tags, \
            f"Expected tags {tags} but got {result}"
        
        # Verify the CloudFront API was called
        assert mock_cf.list_tags_for_resource.called
