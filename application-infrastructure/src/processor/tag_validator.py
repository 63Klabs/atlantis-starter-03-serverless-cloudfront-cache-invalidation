"""S3 bucket and CloudFront distribution tag validation.

This module provides functions to validate AWS resource tags to ensure
only authorized resources can trigger CloudFront invalidations.
"""

import sys
import os
from typing import Dict, Optional, List

import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.logger import setup_logger

logger = setup_logger(__name__)

# Initialize AWS clients
s3_client = boto3.client('s3')
cloudfront_client = boto3.client('cloudfront')


def get_bucket_tags(bucket_name: str) -> Optional[Dict[str, str]]:
    """Retrieve tags for an S3 bucket.
    
    Uses the GetBucketTagging API to retrieve all tags associated with
    the specified S3 bucket. Handles missing tags and API errors gracefully.
    
    Args:
        bucket_name: Name of the S3 bucket
        
    Returns:
        Dictionary of tag key-value pairs, or None if tags cannot be retrieved.
        Returns empty dict if bucket has no tags.
        
    Raises:
        No exceptions are raised; errors are logged and None is returned.
    """
    try:
        logger.debug(
            f"Retrieving tags for bucket: {bucket_name}",
            extra={'extra_fields': {
                'bucket_name': bucket_name
            }}
        )
        
        # DEBUG: Log S3 API call
        logger.info(
            f"Calling S3 get_bucket_tagging DEBUG",
            extra={'extra_fields': {
                'bucketName': bucket_name,
                's3ClientRegion': s3_client.meta.region_name if hasattr(s3_client, 'meta') else 'unknown'
            }}
        )
        
        response = s3_client.get_bucket_tagging(Bucket=bucket_name)
        
        # DEBUG: Log S3 response
        logger.info(
            f"S3 get_bucket_tagging response DEBUG",
            extra={'extra_fields': {
                'bucketName': bucket_name,
                'fullResponse': response,
                'responseKeys': list(response.keys()) if isinstance(response, dict) else 'not_dict',
                'responseMetadata': response.get('ResponseMetadata', {}),
                'hasTagSet': 'TagSet' in response
            }}
        )
        
        # Convert tag list to dictionary
        tag_set = response.get('TagSet', [])
        
        # DEBUG: Log tag conversion
        logger.info(
            f"S3 tag conversion DEBUG",
            extra={'extra_fields': {
                'bucketName': bucket_name,
                'tagSet': tag_set,
                'tagSetLength': len(tag_set),
                'tagSetType': type(tag_set).__name__
            }}
        )
        
        tags = {tag['Key']: tag['Value'] for tag in tag_set}
        
        logger.debug(
            f"Retrieved {len(tags)} tags for bucket: {bucket_name}",
            extra={'extra_fields': {
                'bucket_name': bucket_name,
                'tag_count': len(tags),
                'tags': tags
            }}
        )
        
        return tags
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        
        # NoSuchTagSet means the bucket exists but has no tags
        if error_code == 'NoSuchTagSet':
            logger.info(
                f"Bucket {bucket_name} has no tags",
                extra={'extra_fields': {
                    'bucket_name': bucket_name
                }}
            )
            return {}
        
        # Log other errors
        logger.error(
            f"Failed to retrieve tags for bucket {bucket_name}: {error_code}",
            extra={'extra_fields': {
                'bucket_name': bucket_name,
                'error_code': error_code,
                'error_message': str(e)
            }}
        )
        return None
        
    except Exception as e:
        logger.error(
            f"Unexpected error retrieving tags for bucket {bucket_name}: {str(e)}",
            extra={'extra_fields': {
                'bucket_name': bucket_name,
                'error': str(e)
            }}
        )
        return None


def validate_bucket_tags(bucket_name: str) -> bool:
    """Validate that a bucket has the required tags for invalidation processing.
    
    Checks that the bucket has the AllowInvalidationEvents tag set to "true".
    This tag-based validation ensures only authorized buckets can trigger
    CloudFront invalidations.
    
    Args:
        bucket_name: Name of the S3 bucket to validate
        
    Returns:
        True if the bucket has AllowInvalidationEvents=true, False otherwise.
        Returns False if tags cannot be retrieved or tag is missing/incorrect.
        
    **Feature: multi-bucket-cloudfront-invalidation, Property 14 & 15: Bucket tag validation**
    **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
    """
    # DEBUG: Log validation start
    logger.info(
        f"Starting bucket tag validation DEBUG",
        extra={'extra_fields': {
            'bucketName': bucket_name,
            'aboutToCallGetBucketTags': True
        }}
    )
    
    # Retrieve bucket tags
    tags = get_bucket_tags(bucket_name)
    
    # DEBUG: Log tag retrieval result
    logger.info(
        f"Bucket tag retrieval result DEBUG",
        extra={'extra_fields': {
            'bucketName': bucket_name,
            'tags': tags,
            'tagsType': type(tags).__name__,
            'tagsRetrieved': tags is not None,
            'tagCount': len(tags) if isinstance(tags, dict) else 0,
            'hasAllowInvalidationEvents': 'AllowInvalidationEvents' in tags if isinstance(tags, dict) else False
        }}
    )
    
    # If tags could not be retrieved, fail validation
    if tags is None:
        logger.warning(
            f"Bucket tag validation failed: could not retrieve tags for {bucket_name}",
            extra={'extra_fields': {
                'bucket_name': bucket_name,
                'validation_result': False,
                'reason': 'tag_retrieval_failed'
            }}
        )
        return False
    
    # Check for AllowInvalidationEvents tag
    allow_invalidation = tags.get('AllowInvalidationEvents', '')
    
    # DEBUG: Log tag validation logic
    logger.info(
        f"Bucket tag validation logic DEBUG",
        extra={'extra_fields': {
            'bucketName': bucket_name,
            'allowInvalidationValue': allow_invalidation,
            'allowInvalidationType': type(allow_invalidation).__name__,
            'expectedValue': 'true',
            'exactMatch': allow_invalidation == 'true'
        }}
    )
    
    # Validate tag value (must be exactly "true")
    is_valid = allow_invalidation == 'true'
    
    if is_valid:
        logger.info(
            f"Bucket tag validation passed for {bucket_name}",
            extra={'extra_fields': {
                'bucket_name': bucket_name,
                'validation_result': True,
                'allow_invalidation_events': allow_invalidation
            }}
        )
    else:
        logger.warning(
            f"Bucket tag validation failed for {bucket_name}: "
            f"AllowInvalidationEvents={allow_invalidation}",
            extra={'extra_fields': {
                'bucket_name': bucket_name,
                'validation_result': False,
                'allow_invalidation_events': allow_invalidation,
                'reason': 'tag_missing_or_incorrect'
            }}
        )
    
    return is_valid


def get_distribution_tags(distribution_id: str) -> Optional[Dict[str, str]]:
    """Retrieve tags for a CloudFront distribution.
    
    Uses the ListTagsForResource API to retrieve all tags associated with
    the specified CloudFront distribution. Handles missing tags and API errors gracefully.
    
    Args:
        distribution_id: ID of the CloudFront distribution
        
    Returns:
        Dictionary of tag key-value pairs, or None if tags cannot be retrieved.
        Returns empty dict if distribution has no tags.
        
    Raises:
        No exceptions are raised; errors are logged and None is returned.
    """
    try:
        logger.debug(
            f"Retrieving tags for distribution: {distribution_id}",
            extra={'extra_fields': {
                'distribution_id': distribution_id
            }}
        )
        
        # Construct the ARN for the distribution
        # ARN format: arn:aws:cloudfront::<account-id>:distribution/<distribution-id>
        # We need to get the account ID from STS
        sts_client = boto3.client('sts')
        account_id = sts_client.get_caller_identity()['Account']
        distribution_arn = f"arn:aws:cloudfront::{account_id}:distribution/{distribution_id}"
        
        response = cloudfront_client.list_tags_for_resource(Resource=distribution_arn)
        
        # Convert tag list to dictionary
        tag_items = response.get('Tags', {}).get('Items', [])
        tags = {tag['Key']: tag['Value'] for tag in tag_items}
        
        logger.debug(
            f"Retrieved {len(tags)} tags for distribution: {distribution_id}",
            extra={'extra_fields': {
                'distribution_id': distribution_id,
                'tag_count': len(tags),
                'tags': tags
            }}
        )
        
        return tags
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        
        logger.error(
            f"Failed to retrieve tags for distribution {distribution_id}: {error_code}",
            extra={'extra_fields': {
                'distribution_id': distribution_id,
                'error_code': error_code,
                'error_message': str(e)
            }}
        )
        return None
        
    except Exception as e:
        logger.error(
            f"Unexpected error retrieving tags for distribution {distribution_id}: {str(e)}",
            extra={'extra_fields': {
                'distribution_id': distribution_id,
                'error': str(e)
            }}
        )
        return None


def validate_distribution_tags(
    distribution_id: str,
    bucket_app_tag: str,
    stage_id: str
) -> bool:
    """Validate that a distribution has the required tags for invalidation processing.
    
    Checks that the distribution has:
    1. AllowInvalidationEvents tag set to "true"
    2. atlantis:ApplicationDeploymentId matching pattern <bucket-app>-<StageId>
    
    This tag-based validation ensures only authorized distributions can receive
    CloudFront invalidations and that the distribution matches the bucket's application.
    
    Args:
        distribution_id: ID of the CloudFront distribution to validate
        bucket_app_tag: Value of the bucket's atlantis:Application tag
        stage_id: StageId extracted from the object key path
        
    Returns:
        True if the distribution has AllowInvalidationEvents=true and matching
        ApplicationDeploymentId, False otherwise.
        Returns False if tags cannot be retrieved or tags are missing/incorrect.
        
    **Feature: multi-bucket-cloudfront-invalidation, Property 16 & 17: Distribution tag validation**
    **Validates: Requirements 8.1, 8.2, 8.3, 8.4**
    """
    # Retrieve distribution tags
    tags = get_distribution_tags(distribution_id)
    
    # If tags could not be retrieved, fail validation
    if tags is None:
        logger.warning(
            f"Distribution tag validation failed: could not retrieve tags for {distribution_id}",
            extra={'extra_fields': {
                'distribution_id': distribution_id,
                'validation_result': False,
                'reason': 'tag_retrieval_failed'
            }}
        )
        return False
    
    # Check for AllowInvalidationEvents tag
    allow_invalidation = tags.get('AllowInvalidationEvents', '')
    
    # Check for atlantis:ApplicationDeploymentId tag
    app_deployment_id = tags.get('atlantis:ApplicationDeploymentId', '')
    
    # Expected ApplicationDeploymentId format: <bucket-app>-<StageId>
    expected_app_deployment_id = f"{bucket_app_tag}-{stage_id}"
    
    # Validate both tags
    allow_invalidation_valid = allow_invalidation == 'true'
    app_deployment_id_valid = app_deployment_id == expected_app_deployment_id
    
    is_valid = allow_invalidation_valid and app_deployment_id_valid
    
    if is_valid:
        logger.info(
            f"Distribution tag validation passed for {distribution_id}",
            extra={'extra_fields': {
                'distribution_id': distribution_id,
                'validation_result': True,
                'allow_invalidation_events': allow_invalidation,
                'app_deployment_id': app_deployment_id,
                'expected_app_deployment_id': expected_app_deployment_id
            }}
        )
    else:
        # Determine specific reason for failure
        reasons = []
        if not allow_invalidation_valid:
            reasons.append(f"AllowInvalidationEvents={allow_invalidation}")
        if not app_deployment_id_valid:
            reasons.append(
                f"ApplicationDeploymentId mismatch: "
                f"expected={expected_app_deployment_id}, actual={app_deployment_id}"
            )
        
        logger.warning(
            f"Distribution tag validation failed for {distribution_id}: {', '.join(reasons)}",
            extra={'extra_fields': {
                'distribution_id': distribution_id,
                'validation_result': False,
                'allow_invalidation_events': allow_invalidation,
                'app_deployment_id': app_deployment_id,
                'expected_app_deployment_id': expected_app_deployment_id,
                'reason': 'tag_missing_or_incorrect'
            }}
        )
    
    return is_valid
