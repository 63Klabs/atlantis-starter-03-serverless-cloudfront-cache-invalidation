"""CloudFront distribution discovery and matching.

This module provides functions to discover CloudFront distributions that
match S3 bucket origins and paths, enabling automatic invalidation targeting.
"""

import os
from typing import List, Dict, Optional

import boto3
from botocore.exceptions import ClientError

# Import from Lambda layer
from common.logger import setup_logger # pyright: ignore[reportMissingImports]
from common.constants import MAX_RETRY_ATTEMPTS_CLOUDFRONT_LIST # pyright: ignore[reportMissingImports]
from common.retry import retry_with_backoff # pyright: ignore[reportMissingImports]

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
        # DEBUG: Log CloudFront API call
        # logger.info(
        #     "Listing CloudFront distributions DEBUG",
        #     extra={'extra_fields': {
        #         'cloudfrontClientRegion': cloudfront_client.meta.region_name if hasattr(cloudfront_client, 'meta') else 'unknown',
        #         'aboutToCallListDistributions': True
        #     }}
        # )
        
        distributions = []
        paginator = cloudfront_client.get_paginator('list_distributions')
        page_count = 0
        
        # Paginate through all distributions
        for page in paginator.paginate():
            page_count += 1
            
            # DEBUG: Log each page
            # logger.info(
            #     f"Processing distributions page {page_count} DEBUG",
            #     extra={'extra_fields': {
            #         'pageNumber': page_count,
            #         'pageKeys': list(page.keys()) if isinstance(page, dict) else 'not_dict',
            #         'hasDistributionList': 'DistributionList' in page if isinstance(page, dict) else False
            #     }}
            # )
            
            distribution_list = page.get('DistributionList', {})
            items = distribution_list.get('Items', [])
            
            # DEBUG: Log page details
            # logger.info(
            #     f"Page {page_count} distribution details DEBUG",
            #     extra={'extra_fields': {
            #         'pageNumber': page_count,
            #         'distributionList': distribution_list,
            #         'distributionListKeys': list(distribution_list.keys()) if isinstance(distribution_list, dict) else 'not_dict',
            #         'itemsCount': len(items),
            #         'itemsType': type(items).__name__,
            #         'distributionIds': [item.get('Id', 'no_id') for item in items[:5]] if items else []  # First 5 IDs
            #     }}
            # )
            
            distributions.extend(items)
        
        # DEBUG: Log final results
        # logger.info(
        #     f"CloudFront distribution listing complete DEBUG",
        #     extra={'extra_fields': {
        #         'totalPages': page_count,
        #         'totalDistributions': len(distributions),
        #         'allDistributionIds': [dist.get('Id', 'no_id') for dist in distributions],
        #         'distributionSample': distributions[0] if distributions else None
        #     }}
        # )
        
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
    # DEBUG: Log matching function entry
    # logger.info(
    #     "Origin matching analysis DEBUG",
    #     extra={'extra_fields': {
    #         'origin': origin,
    #         'bucketName': bucket_name,
    #         'expectedOriginPath': origin_path
    #     }}
    # )
    
    # Get origin domain name
    domain_name = origin.get('DomainName', '')
    
    # Get origin path (may be empty string)
    origin_origin_path = origin.get('OriginPath', '')
    
    # DEBUG: Log extracted values
    # logger.info(
    #     "Origin values extraction DEBUG",
    #     extra={'extra_fields': {
    #         'extractedDomainName': domain_name,
    #         'extractedOriginPath': origin_origin_path,
    #         'bucketName': bucket_name,
    #         'expectedOriginPath': origin_path
    #     }}
    # )
    
    # Check if domain name matches the bucket
    # Handle both regional and global formats
    domain_matches = False
    
    # Check for exact global format match
    global_format = f"{bucket_name}.s3.amazonaws.com"
    regional_prefix = f"{bucket_name}.s3."
    
    if domain_name == global_format:
        domain_matches = True
        # logger.info(
        #     "Domain matches global format DEBUG",
        #     extra={'extra_fields': {
        #         'domainName': domain_name,
        #         'globalFormat': global_format,
        #         'matchType': 'global'
        #     }}
        # )
    # Check for regional format - must start with bucket name followed by .s3.
    elif domain_name.startswith(regional_prefix) and "amazonaws.com" in domain_name:
        domain_matches = True
        # logger.info(
        #     "Domain matches regional format DEBUG",
        #     extra={'extra_fields': {
        #         'domainName': domain_name,
        #         'regionalPrefix': regional_prefix,
        #         'matchType': 'regional'
        #     }}
        # )
    # else:
    #     logger.info(
    #         "Domain does not match DEBUG",
    #         extra={'extra_fields': {
    #             'domainName': domain_name,
    #             'globalFormat': global_format,
    #             'regionalPrefix': regional_prefix,
    #             'startsWithRegional': domain_name.startswith(regional_prefix),
    #             'containsAmazonaws': "amazonaws.com" in domain_name
    #         }}
    #     )
    
    # Check if origin path matches
    path_matches = origin_origin_path == origin_path
    
    # DEBUG: Log path matching
    # logger.info(
    #     "Path matching analysis DEBUG",
    #     extra={'extra_fields': {
    #         'originOriginPath': origin_origin_path,
    #         'expectedOriginPath': origin_path,
    #         'pathMatches': path_matches,
    #         'pathsEqual': origin_origin_path == origin_path
    #     }}
    # )
    
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
        # DEBUG: Log function entry
        # logger.info(
        #     f"Starting distribution matching DEBUG",
        #     extra={'extra_fields': {
        #         'bucketName': bucket_name,
        #         'originPath': origin_path,
        #         'distributionsProvided': distributions is not None,
        #         'distributionCount': len(distributions) if distributions else 0
        #     }}
        # )
        
        logger.info(
            f"Finding distributions for bucket {bucket_name} with origin path {origin_path}",
            extra={'extra_fields': {
                'bucket_name': bucket_name,
                'origin_path': origin_path
            }}
        )
        
        # Fetch distributions if not provided
        if distributions is None:
            # DEBUG: Log distribution fetching
            # logger.info(
            #     "Fetching distributions from CloudFront API DEBUG",
            #     extra={'extra_fields': {
            #         'aboutToCallListDistributions': True
            #     }}
            # )
            
            distributions = list_distributions()
            
            # DEBUG: Log fetching result
            logger.info(
                "Distribution fetching complete",
                extra={'extra_fields': {
                    'fetchedDistributionCount': len(distributions),
                    'distributionIds': [dist.get('Id', 'no_id') for dist in distributions]
                }}
            )
        
        matching_distribution_ids = []
        
        # DEBUG: Log search start
        # logger.info(
        #     "Starting distribution search DEBUG",
        #     extra={'extra_fields': {
        #         'totalDistributionsToSearch': len(distributions),
        #         'bucketName': bucket_name,
        #         'originPath': origin_path
        #     }}
        # )
        
        # Search through all distributions
        for i, distribution in enumerate(distributions):
            distribution_id = distribution.get('Id')
            
            # DEBUG: Log each distribution analysis
            # logger.info(
            #     f"Analyzing distribution {i+1}/{len(distributions)} DEBUG",
            #     extra={'extra_fields': {
            #         'distributionIndex': i,
            #         'distributionId': distribution_id,
            #         'distributionKeys': list(distribution.keys()) if isinstance(distribution, dict) else 'not_dict',
            #         'hasOrigins': 'Origins' in distribution if isinstance(distribution, dict) else False
            #     }}
            # )
            
            # Get origins from distribution
            origins_section = distribution.get('Origins', {})
            origins = origins_section.get('Items', [])
            
            # DEBUG: Log origins analysis
            # logger.info(
            #     f"Distribution {distribution_id} origins analysis DEBUG",
            #     extra={'extra_fields': {
            #         'distributionId': distribution_id,
            #         'originsSection': origins_section,
            #         'originsSectionKeys': list(origins_section.keys()) if isinstance(origins_section, dict) else 'not_dict',
            #         'originsCount': len(origins),
            #         'originsType': type(origins).__name__,
            #         'originIds': [origin.get('Id', 'no_id') for origin in origins] if origins else []
            #     }}
            # )
            
            # Check each origin for a match
            for j, origin in enumerate(origins):
                # DEBUG: Log origin matching attempt
                # logger.info(
                #     f"Checking origin {j+1}/{len(origins)} for distribution {distribution_id} DEBUG",
                #     extra={'extra_fields': {
                #         'distributionId': distribution_id,
                #         'originIndex': j,
                #         'origin': origin,
                #         'originKeys': list(origin.keys()) if isinstance(origin, dict) else 'not_dict',
                #         'originDomainName': origin.get('DomainName', 'no_domain'),
                #         'originPath': origin.get('OriginPath', 'no_path'),
                #         'aboutToCallMatchesBucketOrigin': True
                #     }}
                # )
                
                matches = _matches_bucket_origin(origin, bucket_name, origin_path)
                
                # DEBUG: Log matching result
                # logger.info(
                #     f"Origin matching result DEBUG",
                #     extra={'extra_fields': {
                #         'distributionId': distribution_id,
                #         'originIndex': j,
                #         'originId': origin.get('Id', 'no_id'),
                #         'originDomainName': origin.get('DomainName', 'no_domain'),
                #         'originPath': origin.get('OriginPath', 'no_path'),
                #         'bucketName': bucket_name,
                #         'expectedOriginPath': origin_path,
                #         'matches': matches
                #     }}
                # )
                
                if matches:
                    matching_distribution_ids.append(distribution_id)
                    
                    # logger.info(
                    #     f"Found matching distribution: {distribution_id}",
                    #     extra={'extra_fields': {
                    #         'distribution_id': distribution_id,
                    #         'bucket_name': bucket_name,
                    #         'origin_path': origin_path,
                    #         'origin_id': origin.get('Id'),
                    #         'domain_name': origin.get('DomainName')
                    #     }}
                    # )
                    
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