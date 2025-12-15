"""CloudFront invalidation client for submitting cache invalidation requests."""

import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError

# Import from Lambda layer
from common.logger import setup_logger # pyright: ignore[reportMissingImports]
from common.retry import retry_with_backoff # pyright: ignore[reportMissingImports]
from common.constants import MAX_RETRY_ATTEMPTS_CLOUDFRONT_INVALIDATION # pyright: ignore[reportMissingImports]

# Import path validator (compatible with both Lambda and test environments)
try:
    # Lambda environment - files are at root level
    from path_validator import validate_and_sanitize_paths
except ImportError:
    # Development/test environment - use relative import
    from .path_validator import validate_and_sanitize_paths

logger = setup_logger(__name__)

# Initialize CloudFront client
cloudfront_client = boto3.client('cloudfront')


def generate_caller_reference() -> str:
    """Generate a unique CallerReference for CloudFront invalidation.
    
    Uses a combination of timestamp and UUID to ensure uniqueness across
    all invalidation requests.
    
    Returns:
        Unique caller reference string
    """
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
    unique_id = str(uuid.uuid4())[:8]
    return f"{timestamp}-{unique_id}"


@retry_with_backoff(
    max_attempts=MAX_RETRY_ATTEMPTS_CLOUDFRONT_INVALIDATION,
    exceptions=(ClientError,)
)
def create_invalidation(distribution_id: str, paths: List[str]) -> Optional[dict]:
    """Submit a CloudFront cache invalidation request.
    
    Creates an invalidation request for the specified distribution with the
    given paths. Automatically retries on failures with exponential backoff
    and jitter.
    
    Args:
        distribution_id: CloudFront distribution ID
        paths: List of paths to invalidate (max 1000 per request)
        
    Returns:
        Invalidation response dict containing:
            - Id: Invalidation ID
            - Status: Invalidation status
            - CreateTime: When the invalidation was created
        Returns None if the request fails after all retries
        
    Raises:
        ClientError: If the request fails after all retry attempts
    """
    if not paths:
        logger.warning(
            "No paths provided for invalidation",
            extra={'extra_fields': {
                'distribution_id': distribution_id
            }}
        )
        return None
    
    # Validate and sanitize paths before sending to CloudFront
    valid_paths, validation_errors = validate_and_sanitize_paths(paths)
    
    if validation_errors:
        logger.warning(
            f"Path validation issues found for distribution {distribution_id}",
            extra={'extra_fields': {
                'distribution_id': distribution_id,
                'original_path_count': len(paths),
                'valid_path_count': len(valid_paths),
                'validation_errors': validation_errors[:10]  # Log first 10 errors
            }}
        )
    
    if not valid_paths:
        logger.error(
            f"No valid paths remaining after validation for distribution {distribution_id}",
            extra={'extra_fields': {
                'distribution_id': distribution_id,
                'original_paths': paths[:10],  # Log first 10 original paths
                'validation_errors': validation_errors[:10]
            }}
        )
        return None
    
    # Use validated paths for invalidation
    paths = valid_paths
    
    # Generate unique caller reference
    caller_reference = generate_caller_reference()
    
    # Prepare invalidation batch
    invalidation_batch = {
        'Paths': {
            'Quantity': len(paths),
            'Items': paths
        },
        'CallerReference': caller_reference
    }
    
    # DEBUG: Log invalidation request details
    logger.info(
        f"Submitting invalidation request for distribution {distribution_id} DEBUG",
        extra={'extra_fields': {
            'distribution_id': distribution_id,
            'path_count': len(paths),
            'caller_reference': caller_reference,
            'paths': paths[:10] if len(paths) > 10 else paths,  # Log first 10 paths
            'invalidationBatch': invalidation_batch,
            'cloudfrontClientRegion': cloudfront_client.meta.region_name if hasattr(cloudfront_client, 'meta') else 'unknown'
        }}
    )
    
    try:
        # Submit invalidation request
        response = cloudfront_client.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch=invalidation_batch
        )
        
        # DEBUG: Log CloudFront response
        logger.info(
            f"CloudFront create_invalidation response DEBUG",
            extra={'extra_fields': {
                'distributionId': distribution_id,
                'fullResponse': response,
                'responseKeys': list(response.keys()) if isinstance(response, dict) else 'not_dict',
                'responseMetadata': response.get('ResponseMetadata', {}),
                'hasInvalidation': 'Invalidation' in response if isinstance(response, dict) else False
            }}
        )
        
        # Extract invalidation details
        invalidation = response.get('Invalidation', {})
        
        # DEBUG: Log invalidation extraction
        logger.info(
            f"Invalidation details extraction DEBUG",
            extra={'extra_fields': {
                'distributionId': distribution_id,
                'invalidation': invalidation,
                'invalidationKeys': list(invalidation.keys()) if isinstance(invalidation, dict) else 'not_dict'
            }}
        )
        
        invalidation_id = invalidation.get('Id')
        status = invalidation.get('Status')
        create_time = invalidation.get('CreateTime')
        
        # DEBUG: Log extracted values
        logger.info(
            f"Extracted invalidation values DEBUG",
            extra={'extra_fields': {
                'distributionId': distribution_id,
                'invalidationId': invalidation_id,
                'status': status,
                'createTime': str(create_time) if create_time else None,
                'invalidationIdType': type(invalidation_id).__name__,
                'statusType': type(status).__name__
            }}
        )
        
        # Log success
        logger.info(
            f"Successfully created invalidation {invalidation_id} for distribution {distribution_id}",
            extra={'extra_fields': {
                'distribution_id': distribution_id,
                'invalidation_id': invalidation_id,
                'status': status,
                'create_time': str(create_time) if create_time else None,
                'path_count': len(paths)
            }}
        )
        
        return {
            'Id': invalidation_id,
            'Status': status,
            'CreateTime': create_time
        }
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        logger.error(
            f"Failed to create invalidation for distribution {distribution_id}: {error_code} - {error_message}",
            extra={'extra_fields': {
                'distribution_id': distribution_id,
                'error_code': error_code,
                'error_message': error_message,
                'path_count': len(paths),
                'caller_reference': caller_reference
            }}
        )
        
        # Re-raise to trigger retry
        raise