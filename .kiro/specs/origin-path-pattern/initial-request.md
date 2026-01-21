# New Feature: Origin Path Pattern

We need a new feature for the cache invalidator function.

A **Origin Path** describes a specific subfolder or directory within your S3 bucket that CloudFront should look into for content, acting as the "root" for that particular cache behavior. For example /prod/public could be the origin path, or content source, for the root of a site served by CloudFront example.com/

A **Origin Path Pattern** is a literal string with no wildcards. Wildcards are only used in documentation or to describe testing scenarios. It may contain a placeholder for `stageId`.

An S3 object prefix is similar to a directory structure path such as /prod/public and for the purposes of describing the relationship of web content stored in S3 and presented by CloudFront will be referred to as an S3 path or Origin Path.

Currently, the application expects the S3 origin path to be the object prefix pattern of /{stageId}/public but there could be other patterns used by S3 buckets that were created using different directory or prefix structures due to other requirements.

For example, some S3 buckets might be single purpose, serving just production content from the root of the S3 bucket. For example s3://somebucket-prod/assets might use the origin path /

We need to add an *Origin Path Pattern* as a setting in config.py, CFN template, Lambda Env Variables, and as a custom bucket tag. This will replace the hard-coded /{stageId}/public origin path.

## Naming

**OriginPathPattern**: the name of the new parameter in CloudFormation templates
**ORIGIN_PATH_PATTERN**: the name of the new parameter in constants.py and Lambda environment variables
**invalidator:OriginPathPattern**: the name of the new bucket tag used by the processor function to filter, consolidate, and search for distributions
**{stageId}**: The placeholder within the Origin Path Pattern that will be replaced with the value of the stageId. The functions will use this to determine where in the path to find the `stageId`

## Origin Path Pattern

A string that represents the path structure in S3, and will be used to determine the origin path for a distribution. It is a literal string, not a regex or glob pattern. It may contain a placeholder `{stageId}`

- /{stageId}/public
- /public
- /{stagedId}
- /
- /files
- /files/web
- /web/public
- /my-cool-application/web/{stagedId}/public
- /my-sweet-application/web/{stagedId}/public
- /my-awesome-application/{stageId}

## Stage ID

While there are no wild cards, there is a placeholder for the stage identifier represented by `{stageId}`

For example, the default origin path pattern is “/{stageId}/public” but other pattern examples using `{stageId}` are:

- “/{stageId}” : “/prod” in which stageId is prod
- “/{stageId}/public” : “/test/public” in which stageId is test
- “/files/public/{stageId}” : “/files/public/prod” in which stageId is prod

StageId placeholders in the path pattern are optional. If no `{stageId}` placeholder is present then it is assumed "production" ensuring it is added to the queue and processed as only explicit non-production values are filtered out and skipped.

{stageId} will be used as an optional placeholder showing that part of the path is dynamic and should be treated as a variable. (While commonly stageId is one of "dev, test, beta, stage, prod" it can be any value such as tfeat25 for test feature 25 or tjoe for test joe (Joe the developer’s test branch))

## CloudFormation Template Parameters

Parameters added to CloudFormation which will be used as environment variables in Lambda should be added to the template parameter section, as well as added to the Metadata parameter group “Application Parameters.”

They should also have proper validation, allowing empty values (if specified in the requirements). They should have proper patterns, descriptions, and constraint descriptions.

We need to add a new template parameter: OriginPathPattern, which will be passed to the both the Ingestor and Processor Lambda functions as an environment variable, and will override the ORIGIN_PATH_PATTERN in constants.py. By default, it will be `/{stageId}/public`. If empty, the default value from constants.py will be used. It should have a Parameter Pattern constraint that will allow empty, or if not empty, must start with `/` can contain valid path characters, but may include curly braces only if they wrap stageId ( for example {stageId} ) It should not end with a `/`

For `OriginPathPattern`, examples of valid patterns are ``, `/`, `/{stageId}`, `/{stageId}/files`, `/something/{stageId}`, `/files`, `/public`.

Invalid exmples are: `files`, `{files}`, `stageId`, `{stageId}/public`, `/{stageId}/public/`

## Overrides

CloudFormation parameters are used to set Lambda environment variables. When setting environment variables use the naming convention describe for environment variables.

Continue to implement overriding defaults in constants.py with environment variables by using os.environ.get

## Lambda Constants

The lambda functions have constants set in the common lambda layer in a file called constants.py

Add a new ORIGIN_PATH_PATTERN to constants.py under “# Path patterns”, which by default will be /{stageId}/public 

Currently, we use ORIGIN_PATH_DEPTH of 3 (/stageId/public) = [‘’, stageId, ‘public’] when split into an array. However, ORIGIN_PATH_DEPTH should no longer be a constant; it should be calculated dynamically. Create a new utility/helper function that, when given a path, will perform the calculation. (given /stageId/public will return 3, given /stageId will return 2, given /files/resources/web will return 4, etc.)

PUBLIC_PATH_SEGMENT should still be used. It is currently set to “public”. When setting ORIGIN_PATH_PATTERN in constants.py, we should use it “/{stageId}/”.PUBLIC_PATH_SEGMENT

## Event Object Paths

The Ingestor Lambda function is triggered by S3 events, which may include events such as when an object is created, updated, or deleted.

The event object received by lambda includes an object key. We will refer to this as an Event Object Path since we are working in a path based application.

The ingestor function does not check bucket tags and therefore only has access to the Origin Path Pattern returned by constants.py and used in the current filtering process.

This is okay. The user will be instructed to set the application-wide origin path pattern to `/` or a common path and set up additional invalidators to accomodate both the currently supported `/{stageId}/public` and new feature.

## Ingestor Function

We will need to update the filtering performed within the Ingestor function. It currently uses ORIGIN_PATH_DEPTH and other mechnisms. It must now use the path pattern.

The ingestor function does not, and will not need to check for bucket tags. It evaluates and filters events based on the default origin path pattern or the existence of the constant PUBLIC_PATH_SEGMENT (default value `public`) in the path. If it does not match the default origin path but contains PUBLIC_PATH_SEGMENT in the path, it is passed to the queue for processing. Only the processor checks the custom bucket tags.

If the default origin path pattern specified in constants.py is “/{stageId}/public” and PUBLIC_PATH_SEGMENT is set to "public", and an event came into the Lambda Ingestor with the object key `/prod/web/public/docs/index.html`, it will fail the expected pattern match but since it has `public` in the path will sill receive a second chance. Any path that fails the match, but has PUBLIC_PATH_SEGMENT in the path will be evaluated for containing "test", or "dev" in the path before PUBLIC_PATH_SEGMENT. If any NON_PRODUCTION_STAGE_IDENTIFIERS appears in the path segments before PUBLIC_PATH_SEGMENT then they are excluded, otherwise the path is added to the queue for processing. Note we cannot check for the existence of prod, beta, or stage since the absense of them do not determine production stages. However, we can quickly exclude paths with non-production labels. So, `/prod/web/public` and `/web/public` will still be handed over to the processor while `/test/web/public` will be filtered out, and it will be up to the processor to perform additional filtering. 

There should be a constant added to constants.py for PRODUCTION_STAGE_IDENTIFIERS=['prod','beta','stage','staging'] and NON_PRODUCTION_STAGE_IDENTIFIERS = ['dev','test']

Pattern Matches will continue as follows:

- If the event object path matches the ORIGIN_PATH_PATTERN, and there is a `{stageId}` in the pattern, it is added to the queue if the stageId is considered production
- If the event object path matches the ORIGIN_PATH_PATTERN, and there is not a `{stageId}` in the pattern, it is added to the queue
- If the event object path does not match the ORIGIN_PATH_PATTERN but contains PUBLIC_PATH_SEGMENT in the path, it is added to the queue
- If the event object path does not match the ORIGIN_PATH_PATTERN and does not contain PUBLIC_PATH_SEGMENT in the path, it is not added to the queue

## Non-Production Filtering of Stage ID

Currently only the ingestor function filters based on stage ID. However the Processor function has access to more information through bucket tags. 

Because the processor function now will also be filtering once it has the bucket origin path pattern, it too must have access to the same stageID filtering the Ingestor function uses. If this filter is not currently included in the common functions in the lambda layer it should be.

## Processor Function

We need to add a per-bucket check along with the other tags we currently check for in the processor function, called invalidator:OriginPathPattern, that overrides the default origin path set in constants.py.

The ingestor function will run a first check against the default pattern and stage. Anything it passes on will need to be inspected by the processor.

The processor function should filter the event using the same process as the ingestor, but now with the added insight of the invalidator:OriginPathPattern if it exists.

For each bucket it will need to determine the calculated_bucket_origin_path based on the following priority:
1. invalidator:OriginPathPattern bucket tag
2. ORIGIN_PATH_PATTERN from constants.py
3. Placement of PUBLIC_PATH_SEGMENT in the path if no match against ORIGIN_PATH_PATTERN
4. If none of the above, then we will use `/` (root of s3 bucket) as the origin path - this will likely never be reached

The processor function will be passed a list of event object paths for a given bucket. It should use the following logic on the FIRST object path to determine the bucket origin path pattern to use for filtering and consolidation (bucket_origin_path_pattern).

- use the invalidator:OriginPathPattern bucket tag if present. 
- If the invalidator:OriginPathPattern tag is not present, it should fall back to the following:
    - Check match against ORIGIN_PATH_PATTERN, if it matches, then use that as the bucket origin path pattern
    - If no match with ORIGIN_PATH_PATTERN, then:
        - Determine if the bucket paths are public or not based on the presence of PUBLIC_PATH_SEGMENT in the path
        - If PUBLIC_PATH_SEGMENT is in the path, then it is considered a public path and the bucket origin path pattern will be the path leading up to and including PUBLIC_PATH_SEGMENT but not further. For example if PUBLIC_PATH_SEGMENT=public then `/docs/files/public/assets/index.html` would resolve to the bucket origin path pattern of `/docs/files/public`. Furthermore, determine if a NON_PRODUCTION_STAGE_IDENTIFIER or PRODUCTION_STAGE_IDENTIFIER appears in the path segements leading up to PUBLIC_PATH_SEGMENT. if so, replace it with `{stageId}`. For example: `\dev\files\public` will become `\{stageId}\files\public`

Once the bucket origin path pattern is identified, any of the remaining object paths for that bucket that do not match the pattern should be removed from the list.

Additionally, if `{stageId}` is in the pattern, all paths that are not production should be filtered out (the stage filtering logic used by ingestor function should be available in the common lambda layer).

We should now have a clean list with an identified pattern to use for consolidation. The list of bucket object paths as well as the bucket origin path pattern should be sent to the consolidation step.

## Consolidation

Consolidation logic itself does not change, however, it will need to change the way it evaluates the "root" path before consolidation.

Instead of just using the placement of `public` (or PUBLIC_PATH_SEGMENT) or expecting ORIGIN_PATH_DEPTH = 3, it will need to determine the bucket origin path depth dynamically based on the bucket origin path pattern.

The consolidation function will need to calculate the depth of the bucket origin path pattern, and use that to determine the root path for consolidation. This can be acheived by splitting the bucket origin path pattern using `/` so `/web/projects/public` will become ['','web','projects','public'] with a depth of 4 (length of array). This calculation method might already be used for determining depth.

Since depth is now calculated on the fly the constant ORIGIN_PATH_DEPTH can be removed from constants.py.

Ensure the consolidation method is able to handle multiple stages within the bucket. For example, if the bucket has origin paths for objects:

- /beta/public/index.html
- /prod/public/index.html

Then the consolidator should be able to handle both and create two separate invalidation requests.

## Note to users and documentation

Using an OriginPathPattern with value of “/” essentially turns off any ingestion filtering. It bypasses stage evaluation, bypasses public evaluation, and everything will match /. This is useful not only if all your buckets are origins at the s3 root level, but also if you want to handle filtering using the bucket tag invalidator:OriginPathPattern.

Buckets expecting the use of the invalidator:OriginPathPattern tag should set the application-wide ORIGIN_PATH_PATTERN to / (or another common path) so that the ingestion does not filter out the paths before they reach the processor.

An account can have multiple invalidator applications, each with a different default origin path pattern to accomodate varying s3 origins for cloudfront rather than setting complex rules in a single invalidator application stack. In these complex environments, users should be instructed to set up at least two invalidator stacks, one to handle s3 buckets with non-conventional paths using / (or some common path), and one to handle the conventional /{stageId}/public path. If a user requires more than 3 invalidators then they should re-evaluate the way they provision s3 buckets and ways to standardize so that s3 buckets serving as cloudfront origins are consistent and maintainable.

This should be mentioned in the advanced documentation as well as troubleshooting.

For example: if OriginPathPattern is set to /{stageId}/public but the bucket has invalidator:OriginPathPattern set to /public and the event path is /public/docs/index.html then the event will be filtered out during ingestion as it doesn’t match the application-wide OriginPathPattern. It doesn’t even make it to the processor where bucket tags are read. 

**How to handle updates and tasks**

All existing code works, and we want to ensure any changes do not affect the current test outcomes or the general documentation. All existing documentation is up to date with the current system. This is considered an advanced configuration. The default configuration `/{stageId}/public` still works and should be the generally documented method. Care should be taken to only add documentation to Advanced Configuration for this feature.

The application should be updated progressively with variables and parameters implemented and tested first, without changing logic. After tests validating the current functionality pass, small changes should be implemented. After each major task progression, the functionality tests should pass. (Regression testing is important.)

It is CRITICAL that all tests of the current implementation work (and new tests created) after the update.

Also critical: This is an advanced feature, and should have its own section of documentation. The default, and preferred operation is the way it is currently set up before this feature was added. This is a special advanced feature that, to provide brevity and ease of use, is only implemented under certain circumstances (already existing buckets that do not, and cannot be modified to, fit the default setting.

Tests: unit tests are preferred, we want the tests to run quickly. They should run locally and during deployment of the CI/CD pipeline (refer to the buildspec file)

Wild cards are NOT used in the ORIGIN_PATH_PATTERN whether set as a Parameter, Environment Variable, Bucket Tag, or constants.py. They are ONLY used to explain valid structure and may be used in tests, validation, and documentation.

Expected examples:

OriginPathPattern = /{stageId}/public
No bucket tag

Events with object keys:
- /prod/web/public/docs/index.html
    - Ingestor:
        - No match to OriginPathPattern
        - There is a match against PUBLIC_PATH_SEGMENT
        - There is no non-production stageId in the path (no match against NON_PRODUCTION_STAGE_IDENTIFIERS)
        - origin path is /prod/web/public
        - The ingestor will allow this path to be queued for processing
    - Processor:
        - Bucket tag not found
        - No match to OriginPathPattern
        - There is a match against PUBLIC_PATH_SEGMENT
        - There is a production stageId and it is prod (match against PRODUCTION_STAGE_IDENTIFIERS combined with NON_PRODUCTION_STAGE_IDENTIFIERS)
        - The bucket origin path pattern will be /{stageId}/web/public
        - The processor will filter out any paths not matching the pattern and any non-production stage
        - The consolidator will use a depth of 4 and root path of /{stageId}/web/public for consolidation
- /test/web/public/docs/index.html
    - Ingestor:
        - No match to OriginPathPattern
        - There is a match against PUBLIC_PATH_SEGMENT
        - There is a non-production stageId in the path (match against NON_PRODUCTION_STAGE_IDENTIFIERS)
        - origin path is /test/web/public
        - The ingestor will filter this path out
- /dev/web/public/docs/index.html
    - Ingestor:
        - No match to OriginPathPattern
        - There is a match against PUBLIC_PATH_SEGMENT
        - There is a non-production stageId in the path (match against NON_PRODUCTION_STAGE_IDENTIFIERS)
        - origin path is /dev/web/public
        - The ingestor will filter this path out
- /index.html
    - Ingestor:
        - No match to OriginPathPattern
        - There is no match against PUBLIC_PATH_SEGMENT
        - The ingestor will filter this path out
- /prod/index.html
    - Ingestor:
        - No match to OriginPathPattern
        - There is no match against PUBLIC_PATH_SEGMENT
        - The ingestor will filter this path out
- /prod/public/index.html
    - Ingestor:
        - Matches OriginPathPattern
        - There is no non-production stageId
        - The ingestor will allow this path to be queued for processing
    - Processor:
        - Bucket tag not found
        - Matches OriginPathPattern
        - There is a production stageId and it is prod (match against PRODUCTION_STAGE_IDENTIFIERS combined with NON_PRODUCTION_STAGE_IDENTIFIERS)
        - The bucket origin path pattern will be /{stageId}/public
        - The processor will filter out any paths not matching the pattern and any non-production stage
        - The consolidator will use a depth of 3 and root path of /{stageId}/public for consolidation

OriginPathPattern = /{stageId}/public
invalidator:OriginPathPattern = /web/projects/public

Events with object keys:
- /prod/web/projects/public/docs/index.html
    - Ingestor:
        - No match to OriginPathPattern
        - There is a match against PUBLIC_PATH_SEGMENT
        - There is no non-production stageId in the path (no match against NON_PRODUCTION_STAGE_IDENTIFIERS)
        - origin path is /prod/web/projects/public
        - The ingestor will allow this path to be queued for processing
    - Processor:
        - Does not match the bucket tag
        - Will be filtered out (if there is a invalidator:OriginPathPattern tag and an origin path does not match that tag pattern then it is automatically ignored.)
- /prod/public
    - Ingestor:
        - Since it matches the OriginPathPattern it will be allowed
        - The ingestor will allow this path to be queued for processing
    - Processor:
        - Does not match the bucket tag
        - Will be filtered out (if there is a invalidator:OriginPathPattern tag and an origin path does not match that tag pattern then it is automatically ignored.)
- /web/projects/public/index.html
    - Ingestor:
        - No match to OriginPathPattern
        - There is a match against PUBLIC_PATH_SEGMENT
        - There is no non-production stageId in the path (no match against NON_PRODUCTION_STAGE_IDENTIFIERS)
        - origin path is /web/projects/public
        - The ingestor will allow this path to be queued for processing
    - Processor:
        - Matches the bucket tag
        - The consolidator will use a depth of 4 and root path of /web/projects/public for consolidation

OriginPathPattern = /
invalidator:OriginPathPattern = /web/projects/public

- /web/projects/public
    - Ingestor: 
        - Matches OriginPathPattern
        - The ingestor will allow this path to be queued for processing
    - Processor:
        - Matches the bucket tag
        - The consolidator will use a depth of 4 and root path of /web/projects/public for consolidation

Please review the code, documentation, and tests to ensure there are no inconsistencies.

Prompt the user for clarifying questions.
