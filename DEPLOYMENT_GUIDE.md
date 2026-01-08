# Deployment Guide - Multi-Bucket CloudFront Invalidation Service

This guide provides step-by-step instructions for deploying the Multi-Bucket CloudFront Invalidation Service.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Deployment Steps](#deployment-steps)
- [Configuration](#configuration)
- [Validation](#validation)

## Overview

The enhanced system includes the following new capabilities:

- **CloudFormation Parameters**: System-wide default configuration values
- **Dynamic Configuration**: Per-bucket consolidation settings via S3 bucket tags
- **Consolidation Stop Level**: Control consolidation depth to prevent over-consolidation
- **Enhanced Logging**: Comprehensive configuration decision logging

### Features

1. **CloudFormation Parameters**:
   - `DirectoryConsolidationThreshold` (default: 3)
   - `SiblingDirectoryConsolidationThreshold` (default: 10)
   - `ConsolidationStopLevel` (default: 1)
   - `AggregationWindowSeconds` (default: 300)

2. **Bucket Tags for Configuration**:
   - `invalidator:DirectoryConsolidationThreshold` (1-1000)
   - `invalidator:SiblingDirectoryConsolidationThreshold` (1-1000)
   - `invalidator:ConsolidationStopLevel` (0-20)

3. **Backward Compatibility**: Existing deployments continue to work without changes

## Prerequisites

### Required Tools

- AWS CLI v2.0 or later
- AWS SAM CLI v1.50 or later
- Python 3.9 or later
- Git
- Highly Recommended: 63Klabs Atlantis Platform Tempates and Scripts for ready-to-run deployment

### Required Permissions

Your AWS credentials must have permissions for:

- CloudFormation stack operations
- Lambda function deployment
- IAM role creation and management
- S3 bucket operations
- SQS queue operations
- DynamoDB table operations
- EventBridge scheduler operations
- CloudWatch logs and alarms

### Environment Setup

```bash
# Verify AWS CLI configuration
aws sts get-caller-identity

# Verify SAM CLI installation
sam --version
```

## Deployment Steps

This stack is designed to be deployed "ready-to-run for CI/CD" using [Atlantis Platform Templates and Scripts from 63Klabs](https://github.com/63Klabs/atlantis-cfn-configuration-repo-for-serverless-deployments). 

Like any other project, you can skip the Atlantis platform and go at it on your own using `sam build` and `sam deploy` from the CLI within the `application-infrastructure` directory.

However, if you are managing many projects manually (especially on your own or part of a small team), the Atlantis platform is highly recommended as it implements Platform Engineering and AWS best practices. Plus it utilizes AWS native resources including SAM deployments and CloudFormation without the need of proprietary DevOps tools. Everything is API, CloudFormation template, and SAM CLI based.

If this is your first time deploying to AWS, or deployments have been difficult to manage in the past and you are looking into automating some of your tasks, _please_ look at 63Klabs Atlantis. (If you traditionally deploy applications through the Web Console, _PLEASE_ look into Atlantis! We have many, many [tutorials to get you started](https://github.com/63Klabs/atlantis-tutorials) deploying production-ready applications!) using Platform Engineering and CI/CD best practices with scripts as easy as create_repo.py, config.py, and deploy.py that all use SAM CONFIG files written in TOML.

### Step 1: Review Configuration Options

Before deployment, decide on your configuration strategy:

#### Option A: Use Default Configuration
- DirectoryConsolidationThreshold: 3
- SiblingDirectoryConsolidationThreshold: 10
- ConsolidationStopLevel: 1
- No additional parameters needed

#### Option B: Custom System-Wide Configuration
- Set CloudFormation parameters for your environment
- All buckets use these defaults unless overridden

#### Option C: Mixed Configuration
- Set reasonable CloudFormation defaults
- Use bucket tags for specific overrides

### Step 2: Plan Naming Conventions

Atlantis uses the following naming conventions:

- **PREFIX**: Pre-determined by your organization
- **PROJECT_ID**: Unique identifier for your project. Suggestion: `cdn-invalidator-svc` (Suggested max is 20 characters and the length of Prefix + Project ID should not exceed 28 characters.)
- **YOUR_REPO_NAME**: The name of your repository. Suggestion: `cloudfront-invalidator-service`
- **MY_STATIC_ASSETS**: The name of a new static assets bucket (for testing). This will be incorporated into a unique bucket name. Suggestion: `my-cool-static-assets` (You can create multiple buckets and it is always a good idea to have a few test buckets to experiment with various configurations)

### Step 3: Create and Ready the Repository

Infrastructure deployment using 63Klabs Atlantis Platform Templates and Scripts are orchestrated from your organization's SAM Configuration repository.

The following steps are performed from the command line from within the SAM Configuration repository.

```bash
## -------------------------
## CREATE THE REPO

# > From your organization's SAM CONFIG repo:

# Use the create_repo script to create, configure, and seed a repository
# With the Cache Invalidator
./cli/create_repo.py YOUR_GITHUB/YOUR_REPO_NAME --provider github
# -- OR -- if using CodeCommit:
./cli/create_repo.py YOUR_REPO_NAME --provider codecommit

# > Choose 03-serverless-cloudfront-cache-invalidation.zip 
#   From the list of Available application starters and follow the prompts

# > Copy the HTTPS URL after creation
```

Open a new terminal window and make sure you are in the directory where you store your local repositories.

Perform the following steps to clone and populate the `test` branch of your Invalidator Service repository.

```bash
## -------------------------
## MERGE and PUSH to TEST BRANCH

# > Change OUT of the SAM CONFIG repo to where you clone app repos
cd .. # Be sure to do the following OUTSIDE of the SAM CONFIG repo! Open a new terminal if necessary

# Clone your repository and perform your first deployment AS-IS just to make sure it works
git clone YOUR_REPO_HTTPS_URL
cd YOUR_REPO_NAME

# switch dev
git switch dev
# If you make any changes, ensure you commit and push the changes back to dev 
# (however, try a first-time deploy as-is to make troubleshooting easier)

# You must merge dev into test before creating the pipeline (so it has something to deploy)
git switch test
git merge dev
git push
```

### Step 4: Deploy the Invalidator Service Pipeline and Application Stack

```bash
## -------------------------
## DEPLOY INVALIDATOR STACK - TEST

# Note: We will use the ProjectId of cdn-invalidator but it can be anything
#       For now we will just deploy a test instance of the stack and have
#       Our buckets and distributions use that.

# > These next commands MUST be done from the SAM CONFIG repo 
# Go back to your SAM CONFIG repo (or SAM CONFIG terminal if you kept it open)
cd ../YOUR_DEVOPS_SAM_CONFIG_REPO

# Create the test environment and deploy
./cli/config.py pipeline PREFIX PROJECT_ID test
# > When prompted:
#   Choose template-pipeline.yml (or template-pipeline-github.yml if deploying from a gh repo)
#   Follow the stack parameter prompts (leave S3StaticHostBucket blank)

# Don't forget to deploy if you skipped deployment during config
./cli/deploy.py pipeline PREFIX PROJECT_ID test

# You can follow the deployment in the web console
# After the Pipleline stack has deployed, it will deploy the Application stack
# Once the Invalidator Application stack has deployed, 
# Go to the Invalidator Application stack Output section in the web console
# > Copy CloudFrontCacheInvalidatorArn
# You will need this for your S3 bucket configuration
```

### Step 5: Deploy the S3 Buckets

The following steps are performed from the command line from within the SAM CONFIG repository.

```bash
## -------------------------
## CREATE THE S3 BUCKET THAT WILL SERVE AS THE STATIC WEB HOST
## The bucket will store both test and prod static assets

./cli/config.py storage PREFIX MY_STATIC_ASSETS
# > CHOOSE TEMPLATE: template-storage-s3-oac-for-cloudfront.yml
# > SET PARAMETER: CloudFrontCacheInvalidatorArn
# > Copy the following from OUTPUTS
# - BucketName
# - OriginBucketDomainForCloudFront

# Don't forget to deploy if you skipped deployment during config
./cli/deploy.py storage PREFIX MY_STATIC_ASSETS
```

### Step 6: Deploy the CloudFront Distribution

- You will need the `OriginBucketDomainForCloudFront` from the storage stack outputs.
- When configuring the CloudFront distribution, you will need to add a new tag: `AllowInvalidationEvents=true`

```bash
## -------------------------
## CREATE THE CLOUDFRONT DISTRIBUTIONS
## You do not need a domain name for testing

# Note: By design, cache invalidations are processed ONLY for PROD (stage, beta, prod) instances
# To fully test you will need both a TEST (test) and PROD (stage/beta/prod) instance

# Because the bucket uses OAC for security, you will need a cloudfront distribution
# A custom domain record in Route 53 is optional
# For now you can just use the CloudFront distribution url for testing and add a custom domain later

./cli/config.py network PREFIX MY_STATIC_ASSETS test
# > Choose template-network-route53-cloudfront-s3-apigw.yml (it does not require api gateway)
# > SET PARAMETERS
# - You will need the OriginBucketDomainForCloudFront from the storage stack outputs
# > ADD NEW TAG: AllowInvalidationEvents=true

# Don't forget to deploy if you skipped deployment during config
./cli/deploy.py network PREFIX MY_STATIC_ASSETS test

# All uploads to test/public are skipped, so to actually see invalidations you will need a PROD instance

# Use the same template and prompts answers as before. 
# Don't forget:
# - PARAMETER: OriginBucketDomainForCloudFront
# - ADD NEW TAG: AllowInvalidationEvents=true
./cli/config.py network PREFIX MY_STATIC_ASSETS test
./cli/deploy.py network PREFIX MY_STATIC_ASSETS test
```

### Step 7: Test

The following are performed from the command line from within the Invalidator Service repository.

Make sure you followed the steps to deploy both a PROD and TEST network stack. Invalidations are only sent to production resources.

```bash
## -------------------------
## TEST
## Using the resource list in the invalidator stack, you should be able to go 
## In via the console and check logs and queues. 
## (You will have a 5 minute window as events are processed in 5 minutes)
## Validate both test and prod behavior in 
## DynamoDb, SQS, Events, Lambda Logs and CloudFront Dist invalidation requests

# A test file is available in the root of this repo. Increment the target file name on each copy
aws s3 cp test.html s3://BUCKET_NAME/test/public/test-1.html
# - The Ingestor function should accept and then filter OUT the event (it is in test)
# Copy to S3 prod location
aws s3 cp test.html s3://BUCKET_NAME/prod/public/test-2.html
# The Ingestor function should accept and schedule an invalidation. It should be listed in SQS and DynamoDB
# The Processor function should kick in after 5 minutes and submit an invalidation

# Test a bunch of files at once:
cd application-infrastructure/build-scripts
python3 ./upload-test-files.py --buckets BUCKET_NAME
```

### Step 8: Move to Production

The above commands using the Atlantis CLI scripts only deployed a TEST instance of the invalidator service. When ready to use it in production you should deploy a production instance and reconfigure your S3 buckets to use the PRODUCTION invalidator ARN. 

It is useful to keep a test instance of the invalidator for testing any custom changes. To have the S3 bucket submit events to a different invalidator instance just re-run the `config.py` script for that storage stack and set the `CloudFrontCacheInvalidatorArn` parameter to point to the alternate instance.

### Removing Invalidation from a Bucket

To remove invalidation from your storage stack just re-run the `config.py` script fo that storage stack and leave the `CloudFrontCacheInvalidatorArn` blank by entering a dash `-` (otherwise it will remain the set value).

## Configuration

### System-Wide Configuration (CloudFormation Parameters)

These parameters set default values for any bucket that doesn't override them.

Update the `application-infrastructure/template-configuration.json` file to include parameter overrides for your application stack.

```json
"Parameters": {
    "IngestorMemoryInMB": "1024",
    "ProcessorMemoryInMB": "1024",
    "DirectoryConsolidationThreshold": "5",
    "SiblingDirectoryConsolidationThreshold": "5",
    "ConsolidationStopLevel": "2",
    "AggregationWindowSeconds": "60"
}
```

(For valid values, see [CONFIGURATION_TROUBLESHOOTINGmd](./CONFIGURATION_TROUBLESHOOTING.md))

> Note: You may change the tag configuration in `template-configuration.json` as well. Just do not update any placeholder variables (ie `$PLACEHOLDER$`) or tags with key names starting with `atlantis`.

### Per-Bucket Configuration (S3 Bucket Tags)

Bucket tagging should be performed using the Atlantis SAM Configuration scripts `config.py` and `deploy.py` to maintain configurations specified in your SAM Configuration infrastructure repository is reflective of actual cloud state.

#### Redploy S3 Bucket with Updated Tags

```bash
./cli/config.py storage PREFIX MY_STATIC_ASSETS

# Keep all parameters the same, but when you reach TAGS add new tags with your new values:
invalidator:DirectoryConsolidationThreshold=15
invalidator:SiblingDirectoryConsolidationThreshold=15
invalidator:ConsolidationStopLevel=3

# Deploy changes if you skipped deployment during config
./cli/deploy.py storage PREFIX MY_STATIC_ASSETS
```

#### Manual (temporary) for Testing

performing these steps manually will allow you to test the bucket tagging configuration quickly, but will make your resources drift from the configuration reflected in CloudFormation and your SAM Config repository.

Any changes to the bucket tags will be lost if you redeploy the stack.

> Production systems should ONLY be updated through CloudFormation and Infrastructure as Code

You can update the bucket tags through the S3 web console, or via the CLI.

```bash
aws s3api put-bucket-tagging \
  --bucket your-bucket-name \
  --tagging 'TagSet=[
    {Key=AllowInvalidationEvents,Value=true},
    {Key=invalidator:DirectoryConsolidationThreshold,Value=10},
    {Key=invalidator:SiblingDirectoryConsolidationThreshold,Value=5},
    {Key=invalidator:ConsolidationStopLevel,Value=0}
  ]'
```

#### Configuration Examples

CloudFront charges by the number of invalidation paths received NOT by the number of files invalidated.

For example, if you need to invalidate 1,000 files within a single `sample` directory, you will be charged for 1,000 invalidations if you invalidate per file vs. if you just invalidate the entire directory `sample/*`.

Therefore, to keep your cache invalidation costs low, you want to balance how much you need precise file invalidation vs the threshold of which you begin to consolidate paths. Also, how often, and at what rate, do you expect the files to change?

> Note: The following examples are not exhaustive and are intended to give you a general idea of how to configure your buckets. You will need to adjust the thresholds and stop levels to your specific needs. Monitor your buckets and CloudFront distribution invalidations to prevent any unwanted charges.

**Entire Bucket (Scorched Earth Consolidation)**:

File level caching doesn't matter to you, so you want to invalidate everything.

```bash
# Even if only a single file changes, invalidate the entire cache at the root
invalidator:ConsolidationStopLevel=0
```

**High-Invalidation Bucket (Aggressive Consolidation)**:

Batches of files change and you want invalidation costs to be low.

```bash
# Consolidate at 2 files, 3 sibling directories, allow root consolidation
invalidator:DirectoryConsolidationThreshold=2
invalidator:SiblingDirectoryConsolidationThreshold=3
invalidator:ConsolidationStopLevel=1
```

**Low-Invalidation Bucket (Conservative Consolidation)**:

File invalidation is prefered, but if nearby files and directories change at a high rate, consolidate to reduce costs along that path.

```bash
# Consolidate at 20 files, 25 sibling directories, prevent deep consolidation
invalidator:DirectoryConsolidationThreshold=20
invalidator:SiblingDirectoryConsolidationThreshold=25
invalidator:ConsolidationStopLevel=4
```

**Media Assets Bucket (Minimal Consolidation)**:

Expected low numbers of assets (images, audio, and videos) to be changed at a time and rare.

> IMPORTANT! If you process media before uploading to S3, which may result in 10s, 100s, or 1000s separate files to be generated (such as HLS) use the Streaming Video, Audio, or Derivatives method!

```bash
# High thresholds, prevent most consolidation
invalidator:DirectoryConsolidationThreshold=100
invalidator:SiblingDirectoryConsolidationThreshold=50
invalidator:ConsolidationStopLevel=5
```

**Streaming Video, Audio, or Derivatives (High Consolidation)**:

This is a HUGE gotcha if you are processing video through Elemental Media before uploading to S3.

A single 60 second video clip, when processed and uploaded for web content delivery, can actually balloon to 100s or even 1000s of files. It is important to organize each clip within its own directory that contains all the formats (HLS, Audio, MP4, SD, HD, UHD, etc) so that consolidation can happen at the clip's directory level.

For high traffic sites (with both high volumes of viewers and uploaders) you want consolidation to occur at the clip level, but not closer to the root, otherwise you will continally invalidate your entire cache at the root `/*`.

For this, you will want to stop consolidation before it hits the root level.

```bash
# Low thresholds, prevent consolidation at root level
invalidator:DirectoryConsolidationThreshold=2
invalidator:SiblingDirectoryConsolidationThreshold=2
invalidator:ConsolidationStopLevel=2
```

Example structure:

```
public/
 | - clip-1/
 |   | - HLS/
 |   |   | - 00000.x
 |   |   | - 00001.x
 |   |   | - ....
 |   | - MP4/
 |   |   | - UHD.mp4
 |   |   | - HD.mp4
 |   |   | - SD.mp4
 |   |   | - ....
 |   | - MOV/ ....
 |   | - MKV/ ....
 | - clip-2/
 |   | - HLS/ ....
 |   | - MP4/ ....
 |   | - MOV/ ....
 |   | - MKV/ ....
 | - clip-3/
 |   | - HLS/ ....
 |   | - MP4/ ....
 |   | - MOV/ ....
 |   | - MKV/ ....
```

When `clip-4` and `clip-5` are uploaded, the cache will be invalidated at `clip-4/*` and `clip-5/*` and will not affect any existing clips as consolidation stops before root. If `invalidator:ConsolidationStopLevel=1` then it would send an invalidation for ALL video directories at the root level `/*` due to the fact that the threshold was low (`2`) and there were two sibling directories to consolidate.

## Validation

### Step 1: Verify Deployment

```bash
# Check CloudFormation stack status
aws cloudformation describe-stacks \
  --stack-name atlantis-cloudfront-invalidation-prod \
  --query 'Stacks[0].StackStatus'

# Verify Lambda functions are deployed
aws lambda list-functions \
  --query 'Functions[?contains(FunctionName, `cloudfront-invalidation`)].{Name:FunctionName,Runtime:Runtime,LastModified:LastModified}'
```

### Step 2: Verify Configuration

```bash
# Check Lambda environment variables
aws lambda get-function-configuration \
  --function-name atlantis-cloudfront-invalidation-prod-processor \
  --query 'Environment.Variables.{DirectoryThreshold:DIRECTORY_CONSOLIDATION_THRESHOLD,SiblingThreshold:SIBLING_DIRECTORY_CONSOLIDATION_THRESHOLD,StopLevel:CONSOLIDATION_STOP_LEVEL,WindowSeconds:AGGREGATION_WINDOW_SECONDS}'

# Verify bucket tags
aws s3api get-bucket-tagging --bucket your-bucket-name
```

### Step 3: Test Functionality

```bash
# A test file is available in the root of this repo. Increment the target file name on each copy
aws s3 cp test.html s3://BUCKET_NAME/test/public/test-1.html
# - The Ingestor function should accept and then filter OUT the event (it is in test)

# Copy to S3 prod location
aws s3 cp test.html s3://BUCKET_NAME/prod/public/test-2.html
# The Ingestor function should accept and schedule an invalidation. It should be listed in SQS and DynamoDB
# The Processor function should kick in after 5 minutes and submit an invalidation

# Test a bunch of files at once:
cd application-infrastructure/build-scripts
python3 ./upload-test-files.py --buckets BUCKET_NAME

# Monitor Ingestor Lambda logs
aws logs tail /aws/lambda/atlantis-cloudfront-invalidation-prod-ingestor --follow

# Wait 5+ minutes, then monitor Processor Lambda logs
aws logs tail /aws/lambda/atlantis-cloudfront-invalidation-prod-processor --follow
```

### Step 4: Verify Configuration Usage

Check logs for configuration decisions:

```bash
# Query for configuration resolution logs
aws logs start-query \
  --log-group-name /aws/lambda/atlantis-cloudfront-invalidation-prod-processor \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, bucketName, directoryThreshold, siblingThreshold, stopLevel, source | filter @message like /effective configuration/ | sort @timestamp desc'
```

Check CloudFront Distribution Invalidation Status:

```bash
aws cloudfront list-invalidations --distribution-id YOUR_DISTRIBUTION_ID
```

The output will be in JSON format (by default) and contain a list of invalidation summaries. The most recent one will typically be at the top of the Items list.

```json
{
    "InvalidationList": {
        "Items": [
            {
                "Id": "I12345EXAMPLE",
                "Status": "Completed",
                "CreateTime": "2025-01-01T12:00:00.000Z"
            },
            {
                "Id": "I67890EXAMPLE",
                "Status": "Completed",
                "CreateTime": "2024-12-31T10:00:00.000Z"
            }
        ],
        ...
    }
}
```

Take the `Id` of the most recent invalidation (e.g., `I12345EXAMPLE`) and use it with the `get-invalidation` command.

```bash
aws cloudfront get-invalidation --distribution-id YOUR_DISTRIBUTION_ID --id I12345EXAMPLE
```

```json
{
    "Invalidation": {
        "Id": "I12345EXAMPLE",
        "Status": "Completed",
        "CreateTime": "2025-01-01T12:00:00.000Z",
        "InvalidationBatch": {
            "Paths": {
                "Quantity": 2,
                "Items": [
                    "/path/to/file.css",
                    "/images/*"
                ]
            },
            "CallerReference": "cli-example-ref"
        }
    }
}
```

The `Status` field will indicate the current status (e.g., `InProgress` or `Completed`), and the `Paths` section under `InvalidationBatch` will list the specific paths that were requested for invalidation.

## Troubleshooting

### Common Deployment Issues

1. **Parameter Validation Errors**:
   - Check parameter value ranges
   - Verify parameter file format
   - Review CloudFormation template constraints

2. **IAM Permission Issues**:
   - Verify deployment role has required permissions
   - Check service role policies
   - Review resource-based policies

3. **Resource Naming Conflicts**:
   - Ensure unique stack names
   - Check for existing resources with same names
   - Verify prefix and project ID combinations

### Post-Deployment Issues

1. **Configuration Not Applied**:
   - Check Lambda environment variables
   - Verify CloudFormation parameter values
   - Review bucket tag formatting

2. **Functionality Issues**:
   - Check S3 event configuration
   - Verify bucket and distribution tags
   - Review IAM permissions for Lambda functions

For detailed troubleshooting, see [Configuration Troubleshooting Guide](CONFIGURATION_TROUBLESHOOTING.md).

## Best Practices

### Deployment

1. **Test in Non-Production First**: Always deploy to TEST environment before PROD
2. **Use Parameter Files**: Maintain consistent configuration across deployments
3. **Monitor Deployments**: Watch CloudFormation events and Lambda function updates
4. **Validate After Deployment**: Test functionality before declaring success

### Configuration Management

1. **Document Configuration Decisions**: Record why specific settings were chosen
2. **Use Consistent Naming**: Follow established patterns for resource names
3. **Monitor Configuration Usage**: Track which buckets use custom settings
4. **Regular Reviews**: Periodically review and optimize configuration

### Operations

1. **Monitor Key Metrics**: Track consolidation effectiveness and error rates
2. **Set Up Alerts**: Configure alarms for configuration issues
3. **Maintain Documentation**: Keep deployment and configuration guides current
4. **Plan for Growth**: Consider configuration needs as system scales

## Support

For deployment support:

1. **Check CloudFormation Events**: Review stack events for deployment issues
2. **Review Lambda Logs**: Check function logs for runtime issues
3. **Validate Configuration**: Verify all settings match intended behavior
4. **Contact Platform Team**: Provide deployment logs and configuration details

## Related Documentation

- [Main README](README.md) - Complete system documentation
- [Configuration Troubleshooting Guide](CONFIGURATION_TROUBLESHOOTING.md) - Detailed troubleshooting
