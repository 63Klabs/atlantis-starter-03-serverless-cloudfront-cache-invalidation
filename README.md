# Serverless CloudFront Distribution Cache Invalidation

> For use with template-pipeline.yml which can be deployed using [Atlantis Configuration Repository for Serverless Deployments using AWS SAM](https://github.com/63Klabs/atlantis-cfn-configuration-repo-for-serverless-deployments)

An application that demonstrates Atlantis Platform Templates for provisioning a method to invalidate CloudFront caches when object are updated in an S3 bucket used to store static web content.

## Architecture

This application stack operates independently of S3 buckets hosting static web content and CloudFront distributions.

This solution actually requires at least three stacks:

1. S3 stack with Object Access Control and S3 Events
2. Central Cache Invalidator (this stack)
3. CloudFront Distribution with Route 53 (Route 53 optional)

This application stack can serve multiple S3 buckets and CloudFront distributions. Typically only one invalidation stack is required per `Prefix` (stack namespace) on an account and region.

Simply:

1. An object is uploaded to S3
2. An S3 event sends a notification to this application stack
3. This application stack gathers the recent events from the bucket and assemples an invalidation request.
4. Once the request is assembled, it finds the corresponding distribution that serves as the CDN for the S3 bucket.
5. It submits an invalidation request to the distribution.

> There can be multiple buckets and multiple distributions. The buckets only need to know the ARN of the endpoint to send an event to. This application will then dynamically determine what distribution to submit the invalidation to. (Uses resource tags as the look-up)

## Deployment

This stack is designed to be deployed using the [63Klabs Atlantis developer platform](https://github.com/63Klabs/atlantis-cfn-configuration-repo-for-serverless-deployments). 

Like any other project, you can skip the Atlantis platform and go at it on your own by modifying the code and templates to fit your needs. However, if you are managing many projects manually (especially on your own or part of a small team), the Atlantis platform is highly recommended as it implements Platform Engineering and AWS best practices. Plus it utilizes AWS native resources including SAM deployments and CloudFormation without the need of proprietary DevOps tools. Everything is API, CloudFormation template, and SAM CLI based. There are a lot of logging, metrics, and security features already baked into the templates so you don't need to start from scratch.

### Deployment Using 63Klabs Atlantis

Deploy using the Atlantis CLI scripts from your DevOps SAM Config repo:

```bash
# Create the Cache Invalidator repo and seed it from the @63klabs/atlantis-starter-03-serverless-cloudfront-cache-invalidation repo
./cli/create_repo.py YOUR_GITHUB/YOUR_REPO_NAME --provider github

# OR, if using CodeCommit:
./cli/create_repo.py YOUR_REPO_NAME --provider codecommit

# Choose atlantis-starter-03-serverless-cloudfront-cache-invalidation
# From the list of starter applications and follow the prompts

# Clone your repository and perform your first deployment AS-IS just to make sure it works
cd .. # Be sure to do this OUTSIDE of the DevOps SAM Config repo! Either from same command line or in a separate window
git clone YOUR_REPO_HTTPS_URL
cd YOUR_REPO_NAME

# checkout dev
git checkout dev
# If you make any changes, ensure you commit and push the changes back to dev (however, try a first-time deploy as-is to make troubleshooting easier)

# You must merge dev into test before creating the pipeline (so it has something to deploy)
git checkout test
git merge dev
git push

# Note: We will use the ProjectId of cdn-invalidator but it can be anything

# Create the test environment and deploy
# Go back to your DevOps SAM Config repo
cd ../YOUR_DEVOPS_SAM_CONFIG_REPO
./cli/config.py pipeline PREFIX cdn-invalidator test
# choose the template-pipeline.yml template when asked (or -github if deploying from a gh repo)
# Follow the prompts (leave S3StaticHostBucket blank)

# Don't forget to deploy if you skipped deployment during config
./cli/deploy.py pipeline PREFIX cdn-invalidator test

## THE FOLLOWING STEPS WILL NEED TO BE COMPLETED FOR EACH BUCKET
## AND CLOUDFRONT DISTRIBUTION YOU CREATE

# After the one-time set-up of the invalidator, copy the 
# CloudFrontCacheInvalidatorArn from the invalidator stack's Output section

# Create the storage stack that will serve as the static web host
./cli/config.py storage PREFIX MY_STATIC_ASSETS
# CHOOSE TEMPLATE: template-storage-s3-oac-for-cloudfront.yml
# SET PARAMETER: CloudFrontCacheInvalidatorArn
# ADD TAG: AllowInvalidationEvents=true
# FROM THE OUTPUTS AFTER DEPLOY YOU WILL NEED FOR LATER:
# - BucketName
# - OriginBucketDomainForCloudFront

# Don't forget to deploy if you skipped deployment during config
./cli/deploy.py storage PREFIX MY_STATIC_ASSETS

# Because the bucket uses OAC for security, you will need a cloudfront distribution
# A custom domain record in Route 53 is optional, you can just use the CloudFront distribution url for testing and add a custom domain later
cd ../YOUR_DEVOPS_SAM_CONFIG_REPO
./cli/config.py network PREFIX YOUR_PROJECT_NAME test
# choose the template-network-route53-cloudfront-s3-apigw.yml template when asked (it does not require api gateway)
# Follow the prompts (You will need the OriginBucketDomainForCloudFront from the storage stack)
# ADD TAG: AllowInvalidationEvents=true

# Don't forget to deploy if you skipped deployment during config
./cli/deploy.py network PREFIX YOUR_PROJECT_NAME test
```

That's it! Now check the pipeline and CloudFormation progress in the console!

When you are confident with the way the application performs, you can set up a production instance that deploys from the `main` branch. Just replace `test` with `prod` in the above `config.py` and `deploy.py` commands.

You should have all your S3 buckets use the invalidator's production ARN. If you used the TEST ARN for testing, go back and reconfigure each storage stack to use the production ARN.

If you make any changes to how the invalidator works, you can set up a temporary bucket that uses the test instance of the invalidator.

### Deployment Without 63Klabs Atlantis

You will have to have a firm understanding of multi-stack, micro-service architecture as well as permissions and template configuration.

If this is your first time deploying to AWS, or deployments have been difficult to manage in the past and you are looking into automating some of your tasks, please look at 63Klabs Atlantis. (If you traditionally deploy applications through the Web Console, PLEASE look into Atlantis or at least Infrastructure as Code! I have many, many [tutorials to get you started](https://github.com/63Klabs/atlantis-tutorials) deploying production-ready applications!)

If you have a process that works or are using Terraform or other workflow to manage your deployments, then modify the template and function to suit your needs. You can use the template and configurations as guides.

## Tutorials

Read the [Atlantis Tutorials introductory page](https://github.com/63Klabs/atlantis-tutorials) for usage information.

## AI Context

See [AI_CONTEXT.md](AI_CONTEXT.md) for important context and guidelines for AI-generated code in this repository.

The context file is also helpful (and perhaps essential) for HUMANS developing within the application's structured platform as well.
