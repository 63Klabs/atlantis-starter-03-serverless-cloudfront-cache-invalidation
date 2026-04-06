# Serverless Multi-Bucket CloudFront Invalidation Service

An application stack that provisions a solution to invalidate CloudFront caches when objects are updated in an S3 bucket storing static web content.

| | Build/Deploy | Application Stack |
|---|---|---|
| **Languages** | Python, Shell | Python |
| **Frameworks** | Atlantis, Hypothesis | Atlantis |
| **Features** | SSM Parameters | EventBridge Scheduler, DynamoDB, SQS, Lambda, CloudWatch Logs, CloudWatch Alarms |

> **Ready-to-Deploy-and-Run** with the [63Klabs Atlantis Templates and Scripts Platform for Serverless Deployments on AWS](https://github.com/63Klabs/atlantis)

## Architecture

This application stack **operates independently** of S3 buckets hosting static web content and CloudFront distributions.

This solution actually requires at least three stacks:

1. S3 stack with Object Access Control and S3 Events
2. Multi-Bucket CloudFront Invalidation Service (this stack)
3. CloudFront Distribution with Route 53 (Route 53 optional)

This application stack can serve multiple S3 buckets and CloudFront distributions. Typically only one invalidation stack is required per `Prefix` (stack namespace) on an account and region.

Simply:

1. An object is uploaded to S3
2. An S3 event sends a notification to a Ingestor Lambda function provisioned by this stack
3. The Ingestor Lambda function analyzes the event and adds it to the queue and sets a timer allowing other subsequent events to come in before processing (since static sites typically have multipe files update at once)
4. The scheduler triggers a Processor Lambda function that gathers the events from a queue and assembles an invalidation request.
5. Once the request is assembled, it finds the corresponding distribution that serves as the CDN for the S3 bucket serving as the origin.
5. It submits an invalidation request to the distribution.

> There can be multiple buckets and multiple distributions. The buckets only need to know the ARN of the endpoint to send an event to. This application will then dynamically determine what distribution to submit the invalidation to. (Uses resource tags as the look-up)

### Advanced Features

- **Configurable Origin Path Pattern**: Support for different S3 bucket structures beyond the default `/{stageId}/public` pattern
- **Dynamic Consolidation Configuration**: Per-bucket consolidation settings via S3 bucket tags
- **Consolidation Stop Level**: Control consolidation depth to prevent over-consolidation
- **Stage Filtering**: Automatic filtering of non-production stages (dev, test)
- **Multi-Stage Support**: Separate invalidation requests for each production stage

For a complete architectural review, see [ARCHITECTURE.md](./ARCHITECTURE.md)

## Deployment

1. Deploy the Invalidation Service stack
2. Deploy the S3 stack
3. Deploy the CloudFront stack

See [DEPLOYMENT.md](./DEPLOYMENT.md) for deployment instructions.

## Tutorials

Read the [Atlantis Tutorials introductory page](https://github.com/63Klabs/atlantis-tutorials) for overall usage of Atlantis Platform Templates and Scripts.

## Tutorial

> For near production-ready examples, review the the other Atlantis starter applications.

1. Read the [Atlantis Tutorials introductory page](https://github.com/63Klabs/atlantis-tutorials)
2. Then perform the steps outlined in the [Basic API Gateway with Lambda Node.js tutorial](https://github.com/63Klabs/atlantis-tutorials/tree/main/tutorials/00-basic-api-gateway-with-lambda-written-in-node).
3. This application is based off of Starter #01 so the following tutorial will be helpful as well: [Tutorial #1: Basic API Gateway with Lambda written in Python](https://github.com/63Klabs/atlantis-tutorials/blob/main/tutorials/01-basic-api-gateway-with-lambda-written-in-python/)

## Architecture

See [Architecture](./ARCHITECTURE.md)

## Deployment Guide

See [Deployment Guide](./DEPLOYMENT.md)

- [Configuration Troubleshooting](./CONFIGURATION_TROUBLESHOOTING.md)

## Advanced Documentation

See [Docs Directory](./docs/README.md)

## AI Context

See [AGENTS.md](./AGENTS.md) for important context and guidelines for AI-generated code in this repository.

The agents file is also helpful (and perhaps essential) for HUMANS developing within the application's structured platform as well.

## Security

See [Security](./SECURITY.md)

## Changelog

See [Change Log](./CHANGELOG.md)

## Contributors

Contributions are welcome! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for details.

- [63Klabs](https://github.com/63klabs)
- [Chad Kluck](https://github.com/chadkluck)
