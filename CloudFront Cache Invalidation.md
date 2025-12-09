# CloudFront Cache Invalidation — Draft Specification (Serverless, event-driven)

## Purpose

Provide an event-driven, decoupled, multi-bucket CloudFront invalidation service that listens to S3 object-change events (buckets fronted by CloudFront via OAC), aggregates paths across events, consolidates invalidation requests according to rules, and submits CloudFront invalidations on an on-demand schedule (every ~5 minutes) without running a constant cron. This specification is written for an AI agent in Kiro IDE to generate the CloudFormation / serverless code, infra diagrams, tests, and policies.

## High level architecture

The project uses the Atlantis Platform framework parameters, tagging, and naming conventions.
- Resources are named in <Prefix>-<ProjectId>-<StageId>-<ResourceName> format.
- S3 buckets optionally are prepended with <S3BucketNameOrgPrefix>
- An example template with required parameters is in [template.yml](./application-infrastructure/template.yml)
- Projects are deployed using the method described in [README.md](./README.md)
- Tagging is imperative for access and managment.
- Useful logging is important along with a dashboard

- **Event Sources (Separate Stack-Presumed already existing)**
  - S3 PUT/POST/COPY/DELETE events (bucket notification -> Lambda). Buckets are in a separate CloudFormation stack; they are tagged with `atlantis:Application=<app-key>` and `AllowInvalidationEvents`.
  - Each application (ProjectId) has its own bucket
  - One bucket serves multiple CloudFront distributions (test, beta, stage, prod) or a single application (ProjectId).
  - S3 object key paths are structured in the <StageId>/public format where StageId represents a deployment instance (test, beta, stage, prod (main)) for a project.
  - Each StageId has its own CloudFront distribution that uses <StageId>/public as an origin.
  - The S3 bucket uses Object Access Control so that only CloudFront has access and the bucket is not public
- **Ingest (Lambda)**
  - A lightweight Lambda (`ingestor`) that receives S3 events. The ingestor extracts:
    - `bucketName`, `objectKey` (path), `eventTime`, `eventType`
    - Also extracts the StageId (first element of object key path)
    - It is up to the Lambda function to perform event filtering since S3 events and IAM policies do not support this feature natively.
      - Event filtering
        - If StageId is production-type (prod, stage, beta, p*, s*, b*) then proceed. Otherwise ignore.
        - If <StageId>/public then proceed, otherwise ignore
  - The lambda function sends the necessary data to SQS for later processing
  - The Lambda function should provide useful log information in JSON format
  - Information such as Bucket name, Origin Path, StageId, and Object Key should be recorded in the log
- **Aggregation Store (SQS)**
  - SQS with batching
- **Scheduler**
  - When the *first* event for a given Origin is received and there is no open aggregate scheduled, a **one-time scheduled invocation** is created to run at "now + 5 minutes" to process the aggregate. Implementation options:
  - **EventBridge Scheduler:** create a one-time schedule that calls the `processor` Lambda at scheduled time.
  - **Step-Function:** with 5 minute wait that then calls the processor Lambda
  - What creates the schedule? The initial lambda function? Should a step function "wrap" the scheduler and lambda function?
  - It is prefered to only run the Lambda function as needed and not have a permanent every 5 minute cron schedule
- **Processor (Lambda)**
  - A Lambda (`processor`) invoked by the scheduler. 
  - Check the queue (SQS) and batch.
  - Separate out each bucket and StageId
  - Permissions check 
    - `bucketTags` (read via `GetBucketTagging`) `atlantis:Application` and `AllowInvalidationEvents` tag keys
    - If the bucket has the tag `AllowInvalidationEvents` with value of `true` then the Lambda function proceeds with that bucket.
    - If the value is anything other than `true` or the tag does not exist, ignore.
  - Resolves the CloudFront distribution(s) to target by searching CloudFront distributions that have the Origin and Path. (`<bucket-name>/<origin-path>`)
  - Check CloudFront distribution tags for `atlantis:ApplicationDeploymentId` ensuring it matches the Bucket tag atlantis:Application with StageId appended: `<Bucket Tag: atlantis:Application>-<StageId>`. Also checks to ensure the tag `AllowInvalidationEvents` exists and is set to `true`. If no match it logs the issue and skips processing the bucket and origin path.
  - Aggregates the paths for the bucket and origin path
    - Reads paths and applies the consolidation algorithm
      - Aggregate events and reduce invalidation count by consolidating scanned paths into directory-level invalidations when thresholds are hit.
      - **Consolidation thresholds:**
        - If **> 3 events** are received for a single object's *parent directory* within the aggregation window, the entire parent directory is invalidated (i.e., `/parent/*`).
        - If more than **3 sibling directories** would individually receive full invalidations, consolidate to their parent directory. This consolidation may continue up to `/` root in the origin path.
  - Submits `CreateInvalidation` requests to each matching CloudFront distribution (separates if more than 1000 invalidations per distribution as that is the limit)
  - Successful invalidations and failures are recorded to CloudWatch Logs in JSON format
- **Failure and Retry**
  - Use dead-letter queue (SQS DLQ) for the ingestor and processor failures.
  - Retries for AWS API calls with exponential backoff.
  - If processing fails after retries, leave on queue.

## Design principles / requirements

- **Decoupled:** Single invalidator stack supports any number of S3 buckets; mapping from bucket -> distribution(s) is via the Origin and Origin Path.
- **Tag driven:** Buckets and CloudFront distributions have tags that provide permission-based processing. 
- **Aggregation:** Aggregate events and reduce invalidation count by consolidating scanned paths into directory-level invalidations when thresholds are hit.
- **Scheduling:** Invalidations are submitted at most once per aggregation window (approx every 5 minutes). The first event triggers a one-time scheduler for 5 minutes later;
- **No constant cron:** Avoid always-on scheduled cron. Use one-shot scheduling mechanisms (EventBridge Scheduler or Step Functions Wait) created (will process all waiting events no matter bucket or distribution).
- **Permissions:** Use least privilage, understanding the lambda functions will need a bit broader privilage at the `<Prefix>` resource naming level and `AllowInvalidationEvents` tag. Further permissions checked by Lambda.
- **Tag-based isolation:** The invalidator must only handle events for buckets/distributions with the same `AllowInvalidationEvents` tag (prevents cross-app invalidations). And for distributions that are associated with the origin bucket and path.
- **Multi-distribution:** A single bucket update could map to multiple CloudFront distributions with same `atlantis:Application` tag — invalidation must target all.
- **Resource Naming:** The Atlantis Platform utilizes naming conventions `<Prefix>-<ProjectId>-<StageId>-<ResourceName>` to assist in IAM policies and permissions (S3 buckets may also have an OrganizationPrefix pre-pended to the name and may not include the StageId if it serves multiple deployments of the same application and uses a path based approach)
