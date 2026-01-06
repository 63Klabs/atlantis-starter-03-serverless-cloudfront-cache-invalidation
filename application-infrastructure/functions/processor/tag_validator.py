"""S3 bucket and CloudFront distribution tag validation.

This module provides functions to validate AWS resource tags to ensure
only authorized resources can trigger CloudFront invalidations.
"""

import os
from typing import Dict, Optional, List

import boto3
from botocore.exceptions import ClientError



# Import from Lambda layer
from common.logger import setup_logger # pyright: ignore[reportMissingImports]
from common.constants import DIRECTORY_CONSOLIDATION_THRESHOLD, CONSOLIDATION_STOP_LEVEL, SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD # pyright: ignore[reportMissingImports]

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
        # logger.info(
        #     f"Calling S3 get_bucket_tagging DEBUG",
        #     extra={'extra_fields': {
        #         'bucketName': bucket_name,
        #         's3ClientRegion': s3_client.meta.region_name if hasattr(s3_client, 'meta') else 'unknown'
        #     }}
        # )
        
        response = s3_client.get_bucket_tagging(Bucket=bucket_name)
        
        # DEBUG: Log S3 response
        # logger.info(
        #     f"S3 get_bucket_tagging response DEBUG",
        #     extra={'extra_fields': {
        #         'bucketName': bucket_name,
        #         'fullResponse': response,
        #         'responseKeys': list(response.keys()) if isinstance(response, dict) else 'not_dict',
        #         'responseMetadata': response.get('ResponseMetadata', {}),
        #         'hasTagSet': 'TagSet' in response
        #     }}
        # )
        
        # Convert tag list to dictionary
        tag_set = response.get('TagSet', [])
        
        # DEBUG: Log tag conversion
        logger.info(
            f"S3 tag conversion",
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
    # logger.info(
    #     f"Starting bucket tag validation DEBUG",
    #     extra={'extra_fields': {
    #         'bucketName': bucket_name,
    #         'aboutToCallGetBucketTags': True
    #     }}
    # )
    
    # Retrieve bucket tags
    tags = get_bucket_tags(bucket_name)
    
    # DEBUG: Log tag retrieval result
    # logger.info(
    #     f"Bucket tag retrieval result DEBUG",
    #     extra={'extra_fields': {
    #         'bucketName': bucket_name,
    #         'tags': tags,
    #         'tagsType': type(tags).__name__,
    #         'tagsRetrieved': tags is not None,
    #         'tagCount': len(tags) if isinstance(tags, dict) else 0,
    #         'hasAllowInvalidationEvents': 'AllowInvalidationEvents' in tags if isinstance(tags, dict) else False
    #     }}
    # )
    
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
    # logger.info(
    #     f"Bucket tag validation logic DEBUG",
    #     extra={'extra_fields': {
    #         'bucketName': bucket_name,
    #         'allowInvalidationValue': allow_invalidation,
    #         'allowInvalidationType': type(allow_invalidation).__name__,
    #         'expectedValue': 'true',
    #         'exactMatch': allow_invalidation == 'true'
    #     }}
    # )
    
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


def validate_consolidation_tag_value(tag_value: str, min_val: int, max_val: int) -> Optional[int]:
    """Validate and convert a consolidation tag value to integer.
    
    Validates that the tag value is a valid integer within the specified range.
    Used for validating DirectoryConsolidationThreshold and ConsolidationStopLevel tags.
    
    Args:
        tag_value: String value from the bucket tag
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        
    Returns:
        Valid integer value, or None if invalid
        
    **Feature: dynamic-bucket-consolidation-config, Property 4 & 17: Tag value validation**
    **Validates: Requirements 1.4, 5.3**
    """
    try:
        int_value = int(tag_value)
        if min_val <= int_value <= max_val:
            return int_value
        else:
            logger.warning(
                f"Consolidation tag value {int_value} is outside valid range [{min_val}, {max_val}]",
                extra={'extra_fields': {
                    'tag_value': tag_value,
                    'parsed_value': int_value,
                    'min_value': min_val,
                    'max_value': max_val,
                    'validation_result': False,
                    'reason': 'value_out_of_range'
                }}
            )
            return None
    except (ValueError, TypeError):
        logger.warning(
            f"Consolidation tag value '{tag_value}' is not a valid integer",
            extra={'extra_fields': {
                'tag_value': tag_value,
                'validation_result': False,
                'reason': 'invalid_integer'
            }}
        )
        return None


def get_bucket_consolidation_config(bucket_name: str) -> Dict[str, any]:
    """Retrieve consolidation configuration from bucket tags.
    
    Reads the DirectoryConsolidationThreshold, ConsolidationStopLevel, and
    SiblingDirectoryConsolidationThreshold tags from the specified bucket and
    returns the effective configuration values. Falls back to default values
    from constants when tags are missing or invalid.
    
    Args:
        bucket_name: Name of the S3 bucket
        
    Returns:
        Dictionary with keys:
        - 'directory_threshold': Effective directory consolidation threshold
        - 'stop_level': Effective consolidation stop level
        - 'sibling_directory_threshold': Effective sibling directory consolidation threshold
        - 'directory_threshold_source': 'tag' or 'default'
        - 'stop_level_source': 'tag' or 'default'
        - 'sibling_directory_threshold_source': 'tag' or 'default'
        
    **Feature: sibling-directory-consolidation-threshold, Property 4, 5, 6, 7, 8, 9, 10, 12: Configuration reading**
    **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.4, 4.2**
    """
    # logger.info(
    #     f"Reading consolidation configuration for bucket: {bucket_name}",
    #     extra={'extra_fields': {
    #         'bucket_name': bucket_name,
    #         'operation': 'get_bucket_consolidation_config'
    #     }}
    # )
    
    # Retrieve bucket tags
    tags = get_bucket_tags(bucket_name)
    
    # Initialize configuration with defaults
    config = {
        'directory_threshold': DIRECTORY_CONSOLIDATION_THRESHOLD,
        'stop_level': CONSOLIDATION_STOP_LEVEL,
        'sibling_directory_threshold': SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD,
        'directory_threshold_source': 'default',
        'stop_level_source': 'default',
        'sibling_directory_threshold_source': 'default'
    }
    
    # If tags could not be retrieved, use defaults
    if tags is None:
        logger.warning(
            f"Could not retrieve tags for bucket {bucket_name}, using default consolidation configuration",
            extra={'extra_fields': {
                'bucket_name': bucket_name,
                'directory_threshold': config['directory_threshold'],
                'stop_level': config['stop_level'],
                'sibling_directory_threshold': config['sibling_directory_threshold'],
                'directory_threshold_source': config['directory_threshold_source'],
                'stop_level_source': config['stop_level_source'],
                'sibling_directory_threshold_source': config['sibling_directory_threshold_source'],
                'reason': 'tag_retrieval_failed'
            }}
        )
        return config
    
    # Check for DirectoryConsolidationThreshold tag
    threshold_tag = tags.get('invalidator:DirectoryConsolidationThreshold')
    if threshold_tag is not None:
        validated_threshold = validate_consolidation_tag_value(threshold_tag, 1, 1000)
        if validated_threshold is not None:
            config['directory_threshold'] = validated_threshold
            config['directory_threshold_source'] = 'tag'
            logger.info(
                f"Using bucket-specific directory consolidation threshold: {validated_threshold}",
                extra={'extra_fields': {
                    'bucket_name': bucket_name,
                    'tag_value': threshold_tag,
                    'effective_value': validated_threshold,
                    'source': 'tag'
                }}
            )
        else:
            logger.warning(
                f"Invalid DirectoryConsolidationThreshold tag value '{threshold_tag}' for bucket {bucket_name}, using default: {config['directory_threshold']}",
                extra={'extra_fields': {
                    'bucket_name': bucket_name,
                    'invalid_tag_value': threshold_tag,
                    'default_value': config['directory_threshold'],
                    'fallback_reason': 'invalid_tag_value'
                }}
            )
    
    # Check for ConsolidationStopLevel tag
    stop_level_tag = tags.get('invalidator:ConsolidationStopLevel')
    if stop_level_tag is not None:
        validated_stop_level = validate_consolidation_tag_value(stop_level_tag, 0, 20)
        if validated_stop_level is not None:
            config['stop_level'] = validated_stop_level
            config['stop_level_source'] = 'tag'
            logger.info(
                f"Using bucket-specific consolidation stop level: {validated_stop_level}",
                extra={'extra_fields': {
                    'bucket_name': bucket_name,
                    'tag_value': stop_level_tag,
                    'effective_value': validated_stop_level,
                    'source': 'tag'
                }}
            )
        else:
            logger.warning(
                f"Invalid ConsolidationStopLevel tag value '{stop_level_tag}' for bucket {bucket_name}, using default: {config['stop_level']}",
                extra={'extra_fields': {
                    'bucket_name': bucket_name,
                    'invalid_tag_value': stop_level_tag,
                    'default_value': config['stop_level'],
                    'fallback_reason': 'invalid_tag_value'
                }}
            )
    
    # Check for SiblingDirectoryConsolidationThreshold tag
    sibling_threshold_tag = tags.get('invalidator:SiblingDirectoryConsolidationThreshold')
    if sibling_threshold_tag is not None:
        validated_sibling_threshold = validate_consolidation_tag_value(sibling_threshold_tag, 1, 1000)
        if validated_sibling_threshold is not None:
            config['sibling_directory_threshold'] = validated_sibling_threshold
            config['sibling_directory_threshold_source'] = 'tag'
            logger.info(
                f"Using bucket-specific sibling directory consolidation threshold: {validated_sibling_threshold}",
                extra={'extra_fields': {
                    'bucket_name': bucket_name,
                    'tag_value': sibling_threshold_tag,
                    'effective_value': validated_sibling_threshold,
                    'source': 'tag'
                }}
            )
        else:
            logger.warning(
                f"Invalid SiblingDirectoryConsolidationThreshold tag value '{sibling_threshold_tag}' for bucket {bucket_name}, using default: {config['sibling_directory_threshold']}",
                extra={'extra_fields': {
                    'bucket_name': bucket_name,
                    'invalid_tag_value': sibling_threshold_tag,
                    'default_value': config['sibling_directory_threshold'],
                    'fallback_reason': 'invalid_tag_value'
                }}
            )
    
    # Log final configuration
    logger.info(
        f"Effective consolidation configuration for bucket {bucket_name}",
        extra={'extra_fields': {
            'bucket_name': bucket_name,
            'directory_threshold': config['directory_threshold'],
            'stop_level': config['stop_level'],
            'sibling_directory_threshold': config['sibling_directory_threshold'],
            'directory_threshold_source': config['directory_threshold_source'],
            'stop_level_source': config['stop_level_source'],
            'sibling_directory_threshold_source': config['sibling_directory_threshold_source'],
            'configuration_tags_found': {
                'DirectoryConsolidationThreshold': threshold_tag,
                'ConsolidationStopLevel': stop_level_tag,
                'SiblingDirectoryConsolidationThreshold': sibling_threshold_tag
            }
        }}
    )
    
    return config