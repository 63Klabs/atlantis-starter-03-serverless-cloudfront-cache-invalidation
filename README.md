# Serverless Multi-Bucket CloudFront Invalidation Service

> For use with [Atlantis Platform Templates and Scripts](https://github.com/63Klabs/atlantis-cfn-configuration-repo-for-serverless-deployments) using AWS SAM.

An application stack that provisions a solution to invalidate CloudFront caches when objects are updated in an S3 bucket storing static web content.

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

See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) for deployment instructions.

## Tutorials

Read the [Atlantis Tutorials introductory page](https://github.com/63Klabs/atlantis-tutorials) for overall usage of Atlantis Platform Templates and Scripts.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Security

If you discover any security related issues, please see the [SECURITY](SECURITY) file for details.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for details.

## AI Context

See [AI_CONTEXT.md](AI_CONTEXT.md) for important context and guidelines for AI-generated code in this repository.

The context file is also helpful (and perhaps essential) for HUMANS developing within the application's structured platform as well.

AI Assisted Engineering of this solution was provided by [Kiro](https://kiro.dev/). Steering documents are provided in the repository's [.kiro](./.kiro/steering/) directory. Because testing is tightly coupled with the implmenentation, it is suggested all documents, code, and tests are thouroughly reviewed before, and updated after, any changes.

## Additional Documents

- [Deployment Guide](./DEPLOYMENT_GUIDE.md)
- [Configuration Troubleshooting](./CONFIGURATION_TROUBLESHOOTING.md)
- [Architecture](./ARCHITECTURE.md)
- [Change Log](./CHANGELOG.md)
