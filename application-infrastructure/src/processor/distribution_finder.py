"""CloudFront distribution discovery and matching.

This module provides functions to discover CloudFront distributions that
match S3 bucket origins and paths, enabling automatic invalidation targeting.
"""

import sys
import os
from typing import List, Dict, Optional

import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.logger import setup_logger
from common.constants import MAX_RETRY_ATTEMPTS_CLOUDFRONT_LIST
from common.retry import retry_with_backoff

logger = setup_logger(__name__)

# Initialize AWS client
cloudfront_client = boto3.client('cloudfront')


@retry_with_backoff(
    max_attempts=MAX_RETRY_ATTEMPTS_CLOUDFRONT_LIST,
    exceptions=(ClientError,)
)
def list_distributions() -> List[Dict]:
    """List all CloudFront distributions with pagination support.
    
    Retrieves all CloudFront distributions in the account, handling
    pagination automatically to ensure all distributions are returned.
    
    Returns:
        List of distribution summary dictionaries, each containing:
            - Id: Distribution ID
            - ARN: Distribution ARN
            - Status: Distribution status
            - DomainName: CloudFront domain name
            - Origins: List of origin configurations
            - Enabled: Whether distribution is enabled
        Returns empty list if no distributions exist.
        
    Raises:
        ClientError: If API call fails after all retries
        
    **Feature: multi-bucket-cloudfront-invalidation, Property 18 & 19: Distribution matching**
    **Validates: Requirements 7.1**
    """
    try:
        logger.info("Listing CloudFront distributions")
        
        distributions = []
        paginator = cloudfront_client.get_paginator('list_distributions')
        
        # Paginate through all distributions
        for page in paginator.paginate():
            distribution_list = page.get('DistributionList', {})
            items = distribution_list.get('Items', [])
            distributions.extend(items)
        
        logger.info(
            f"Retrieved {len(distributions)} CloudFront distributions",
            extra={'extra_fields': {
                'distribution_count': len(distributions)
            }}
        )
        
        return distributions
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        logger.error(
            f"CloudFront list_distributions failed: {error_code} - {error_message}",
            extra={'extra_fields': {
                'error_code': error_code,
                'error_message': error_message
            }}
        )
        
        # Re-raise to trigger retry
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error listing CloudFront distributions: {str(e)}",
            extra={'extra_fields': {
                'error': str(e)
            }}
        )
        raise


def _normalize_s3_domain(bucket_name: str) -> List[str]:
    """Generate possible S3 domain name formats for a bucket.
    
    S3 buckets can be accessed via multiple domain formats:
    - Regional: <bucket>.s3.<region>.amazonaws.com
    - Global (legacy): <bucket>.s3.amazonaws.com
    - Path-style: s3.<region>.amazonaws.com/<bucket> (not used in CloudFront origins)
    
    Args:
        bucket_name: Name of the S3 bucket
        
    Returns:
        List of possible domain name formats for the bucket
    """
    # CloudFront origins typically use these formats:
    # 1. Regional format (recommended): bucket.s3.region.amazonaws.com
    # 2. Global format (legacy): bucket.s3.amazonaws.com
    
    # We'll match against both patterns by checking if the domain contains the bucket name
    # and s3.amazonaws.com, since we don't know the region in advance
    
    return [
        f"{bucket_name}.s3.amazonaws.com",  # Global format
        f"{bucket_name}.s3."  # Regional format prefix (we'll do partial matching)
    ]


def _matches_bucket_origin(origin: Dict, bucket_name: str, origin_path: str) -> bool:
    """Check if a CloudFront origin matches the bucket and origin path.
    
    Compares the origin's domain name and path against the expected values
    for the S3 bucket. Handles both regional and global S3 domain formats.
    
    Args:
        origin: CloudFront origin configuration dictionary
        bucket_name: S3 bucket name to match
        origin_path: Origin path to match (e.g., /prod/public)
        
    Returns:
        True if the origin matches both bucket and path, False otherwise
    """
    # Get origin domain name
    domain_name = origin.get('DomainName', '')
    
    # Get origin path (may be empty string)
    origin_origin_path = origin.get('OriginPath', '')
    
    # Check if domain name matches the bucket
    # Handle both regional and global formats
    domain_matches = False
    
    # Check for exact global format match
    if domain_name == f"{bucket_name}.s3.amazonaws.com":
        domain_matches = True
    # Check for regional format - must start with bucket name followed by .s3.
    elif domain_name.startswith(f"{bucket_name}.s3.") and "amazonaws.com" in domain_name:
        domain_matches = True
    
    # Check if origin path matches
    path_matches = origin_origin_path == origin_path
    
    if domain_matches and path_matches:
        logger.debug(
            f"Origin matches bucket and path",
            extra={'extra_fields': {
                'origin_id': origin.get('Id'),
                'domain_name': domain_name,
                'origin_path': origin_origin_path,
                'bucket_name': bucket_name,
                'expected_origin_path': origin_path
            }}
        )
    
    return domain_matches and path_matches


def find_matching_distributions(
    bucket_name: str,
    origin_path: str,
    distributions: Optional[List[Dict]] = None
) -> List[str]:
    """Find CloudFront distributions that match the bucket and origin path.
    
    Searches through CloudFront distributions to find those with origins
    matching the specified S3 bucket and origin path. Supports both
    regional and global S3 domain formats.
    
    Args:
        bucket_name: S3 bucket name to match
        origin_path: Origin path to match (e.g., /prod/public)
        distributions: Optional list of distributions to search.
            If None, will call list_distributions() to fetch all distributions.
            
    Returns:
        List of distribution IDs that match the bucket and origin path.
        Returns empty list if no matches are found.
        
    **Feature: multi-bucket-cloudfront-invalidation, Property 18 & 19: Distribution matching**
    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """
    try:
        logger.info(
            f"Finding distributions for bucket {bucket_name} with origin path {origin_path}",
            extra={'extra_fields': {
                'bucket_name': bucket_name,
                'origin_path': origin_path
            }}
        )
        
        # Fetch distributions if not provided
        if distributions is None:
            distributions = list_distributions()
        
        matching_distribution_ids = []
        
        # Search through all distributions
        for distribution in distributions:
            distribution_id = distribution.get('Id')
            
            # Get origins from distribution
            origins = distribution.get('Origins', {}).get('Items', [])
            
            # Check each origin for a match
            for origin in origins:
                if _matches_bucket_origin(origin, bucket_name, origin_path):
                    matching_distribution_ids.append(distribution_id)
                    
                    logger.info(
                        f"Found matching distribution: {distribution_id}",
                        extra={'extra_fields': {
                            'distribution_id': distribution_id,
                            'bucket_name': bucket_name,
                            'origin_path': origin_path,
                            'origin_id': origin.get('Id'),
                            'domain_name': origin.get('DomainName')
                        }}
                    )
                    
                    # A distribution can only match once (one origin per bucket/path combo)
                    break
        
        if not matching_distribution_ids:
            logger.info(
                f"No distributions found for bucket {bucket_name} with origin path {origin_path}",
                extra={'extra_fields': {
                    'bucket_name': bucket_name,
                    'origin_path': origin_path
                }}
            )
        else:
            logger.info(
                f"Found {len(matching_distribution_ids)} matching distribution(s)",
                extra={'extra_fields': {
                    'bucket_name': bucket_name,
                    'origin_path': origin_path,
                    'distribution_count': len(matching_distribution_ids),
                    'distribution_ids': matching_distribution_ids
                }}
            )
        
        return matching_distribution_ids
        
    except Exception as e:
        logger.error(
            f"Error finding matching distributions: {str(e)}",
            extra={'extra_fields': {
                'bucket_name': bucket_name,
                'origin_path': origin_path,
                'error': str(e)
            }}
        )
        # Return empty list on error (logged above)
        return []
