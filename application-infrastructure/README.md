# Serverless Application Model Demo

This sample application is just to seed your first Deploy Pipleline stack.

Place the entire application-infrastructure directory in the root of the repository that the pipeline will monitor.

This is a sample of the Serverless Application Model that deviates from the traditional "Hello World" example as instead it returns JSON formatted predictions.

If you need a basic understanding of AWS SAM I would suggest my first tutorial [Serverless Application Model 8 Ball Example](https://github.com/63klabs/serverless-sam-8ball-example)

## Related

- [AWS Documentation: AWS Serverless Application Model (SAM)](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html)

## Tutorial

Follow the [1-2-3 Set Up for the deploy pipeline](https://github.com/63klabs/serverless-deploy-pipeline-atlantis/blob/main/docs/1-2-3-Set-Up.md). If everything went well during deployment, you should be able to access your application endpoint by going to the Endpoint Test URL listed under Outputs in your CloudFormation infrastructure stack.

If it did not deploy correctly, please troubleshoot before continuing.

Once everything is tested and working correctly, follow the [deploy pipeline tutorials](https://github.com/63klabs/serverless-deploy-pipeline-atlantis/blob/main/docs/Tutorials.md) for deploying additional pipeline options.

If you want a more advanced, real-world web service application infrastructure stack with internal caching using S3, DynamoDb and access to SSM Parameter Store for keys and secrets, check out the repository: [Serverless Webservice Template for Pipeline Atlantis](https://github.com/63klabs/serverless-webservice-template-for-pipeline-atlantis). It is production ready code for a true CI/CD pipeline and I use it as the base of most of my API development.
