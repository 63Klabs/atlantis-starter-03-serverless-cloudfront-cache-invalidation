# https://rewind.com/blog/automatic-cloudfront-invalidation-for-s3-origins/
# Modified to take into account origin path
# Since we have one bucket that serves multiple orgins we need to find the 
# distribution that corresponds to the origin that caused the event.
# We know the origin path is the first two elements /{stageId}/public so
# we include that with the bucket name when we do a search for a distribution
# with a matching origin domain and path.

import boto3
import json
import urllib
import time
import os

origin_path_depth = 3 # because of initial / ['',{stageId},'public'] so when we join those parts it comes back with the initial slash: /{stageId}/public
aws_region = os.environ['AWS_REGION']

cloudfront_client = boto3.client('cloudfront')

def get_cloudfront_distribution_id(bucket, origin_path):
    
    # !GetAtt Bucket.DomainName produces a Global S3 Domain while going through the Web Console in CloudFront uses a Regional S3 domain
    bucket_origin_regional = bucket + '.s3.' + aws_region + '.amazonaws.com'
    bucket_origin_global = bucket + '.s3.amazonaws.com'
    cf_distro_id = None

    # Create a reusable Paginator - https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudfront/paginator/ListDistributions.html
    paginator = cloudfront_client.get_paginator('list_distributions')

    # Create a PageIterator from the Paginator
    page_iterator = paginator.paginate()

    for page in page_iterator:
        for distribution in page['DistributionList']['Items']:
            for cf_origin in distribution['Origins']['Items']:
                if (bucket_origin_regional  == cf_origin['DomainName'] or bucket_origin_global == cf_origin['DomainName']) and origin_path == cf_origin['OriginPath']:
                    cf_distro_id = distribution['Id']
                    print("The CF distribution ID for {}{} is {}".format(bucket,origin_path,cf_distro_id))

    return cf_distro_id


# --------------- Main handler ------------------
def handler(event, context):
    '''
    Creates a cloudfront invalidation for content added to an S3 bucket
    '''
    # Log the the received event locally.
    # print("Received event: " + json.dumps(event, indent=2))

    # Get the object info from the event.
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])
    s3_event = event['Records'][0]['eventName']
    origin_path = ''
    cf_distro_id = None

    if not key.startswith('/'):
        key = '/' + key

    # Separate out Origin Path from Key
    path_parts = key.split('/',origin_path_depth)

    # Filter out non-production, non-public objects since the S3 filter event can't
    if len(path_parts) > origin_path_depth and path_parts[origin_path_depth-1] == 'public':
        stageId = path_parts[1]

        # If stageId starts with prod, beta, or stage then proceed (Atlantis assumes based upon first letter for side branches ie b-mia)
        if stageId.startswith('p') or stageId.startswith('b') or stageId.startswith('s'):
            
            # We took out the origin path, so that leaves the key as the last part of path_parts
            key = '/' + path_parts[origin_path_depth]
            origin_path = '/'.join(path_parts[:origin_path_depth])

            print("Event: {}, Bucket: {}, Origin Path: {}, Key: {}".format(s3_event,bucket,origin_path,key))
        
            cf_distro_id = get_cloudfront_distribution_id(bucket, origin_path)

            if cf_distro_id:
                print("Creating invalidation for {} on CloudFront distribution {}".format(key,cf_distro_id))

                try:
                    invalidation = cloudfront_client.create_invalidation(DistributionId=cf_distro_id,
                            InvalidationBatch={
                            'Paths': {
                                    'Quantity': 1,
                                    'Items': [key]
                            },
                            'CallerReference': str(time.time())
                    })

                    print("Submitted invalidation. ID {} Status {}".format(invalidation['Invalidation']['Id'],invalidation['Invalidation']['Status']))
                except Exception as e:
                    print("Error processing object {} from bucket {}. Event {}".format(key, bucket, json.dumps(event, indent=2)))
                    raise e
            else:
                print("No invalidation needed. Bucket {} with Path {} is not an origin for a CloudFront distribution.".format(bucket, origin_path))
        else:
            print("No invalidation needed. Event {} was not for a production environment. Bucket: {} Key: {}".format(s3_event,bucket, key))
    else:
    print("No invalidation needed. Event {} was not for a public path. Bucket: {} Key: {}".format(s3_event,bucket, key))
    
    return 'Success'