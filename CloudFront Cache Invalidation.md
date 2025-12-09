# CloudFront Cache Invalidation — Draft Specification (Serverless, event-driven)

**Purpose:**
Provide an event-driven, decoupled, multi-bucket CloudFront invalidation service that listens to S3 object-change events (buckets fronted by CloudFront via OAC), aggregates paths across events, consolidates invalidation requests according to rules, and submits CloudFront invalidations on an on-demand schedule (every ~5 minutes) without running a constant cron. This specification is written for an AI agent in Kiro IDE to generate the CloudFormation / serverless code, infra diagrams, tests, and policies.

---

# 1 — High level architecture

* **Event Sources**

  * S3 PUT/POST/COPY/DELETE events (bucket notification -> SNS/SQS/Lambda). Buckets are in a separate CloudFormation stack; they are tagged with `Application=<app-key>`.

* **Ingress Layer**

  * A lightweight Lambda (`ingestor`) or S3 -> SQS notification that receives S3 events. The ingestor extracts:

    * `bucketName`, `objectKey` (path), `eventTime`, `eventType`, `bucketTags` (read via `GetBucketTagging` if not included), and `Application` tag value.
  * The ingestor writes/updates an aggregation record in a shared store (DynamoDB) keyed by application/distribution (see Data Model).

* **Aggregation Store**

  * **DynamoDB table** (`InvalidationAggregates`) — stores per-application (and per-distribution if known) aggregation records:

    * Primary Key: `AppKey` (string)
    * Sort Key: `AggregateId` (e.g., `dist:<distributionId>` or `scheduled:<timestamp>`) — design options below
    * Attributes: `paths` (set/list), `pathCounts` (map), `scheduledAt` (epoch), `state` (`open` | `scheduled` | `processing` | `done`), `lockToken` (for optimistic lock), `lastUpdated`
  * TTL not required but optional retention cleanup.

* **Scheduler**

  * When the *first* event for a given AppKey is received and there is no open aggregate scheduled, a **one-time scheduled invocation** is created to run at "now + 5 minutes" to process the aggregate. Implementation options:

    1. **EventBridge Scheduler (recommended):** create a one-time schedule that calls the `processor` Lambda at scheduled time.
    2. **Step Functions Wait state:** Start a Step Function execution with `Wait 5 minutes`, then continue. (Use careful concurrency control.)
    3. **DynamoDB + timer poller:** less preferred because it becomes cron-like.
  * Subsequent events update the existing aggregate until the scheduled time is reached.

* **Processor**

  * A Lambda (`processor`) invoked by the scheduler. It:

    * Atomically flips the aggregate `state` from `scheduled` to `processing` (conditional update) to prevent race conditions.
    * Reads the aggregated paths from DynamoDB and applies the consolidation algorithm (see section 4).
    * Resolves the CloudFront distribution(s) to target by searching CloudFront distributions that have the same `Application` tag value (via `ListDistributions` and `ListTagsForResource` — or CloudFront tagging API).
    * Submits `CreateInvalidation` requests to each matching CloudFront distribution with the consolidated path list.
    * Marks the aggregate `state = done` and writes results (invalidation IDs, timestamps).
    * Ensures incoming events that arrive during processing are not lost — see concurrency guarantees.

* **Notification / Auditing**

  * Successful invalidations and failures are recorded to CloudWatch Logs and optionally to a central SNS topic or DynamoDB audit table for observability.

* **Failure and Retry**

  * Use dead-letter queue (SQS DLQ) for the ingestor and processor failures.
  * Retries for AWS API calls with exponential backoff.
  * If processing fails after retries, mark aggregate as failed and optionally reschedule.

---

# 2 — Design principles / requirements

* **Decoupled:** Single invalidator stack supports any number of S3 buckets; mapping from bucket -> distribution(s) is via the `Application` tag.
* **Tag driven:** Buckets and CloudFront distributions have `Application=<app-key>` tag. The invalidator reads bucket tag and finds distributions with the same `Application` tag. If none found: ignore event.
* **Aggregation:** Aggregate events and reduce invalidation count by consolidating scanned paths into directory-level invalidations when thresholds are hit.
* **Consolidation thresholds:**

  * If **> 3 events** are received for a single object's *parent directory* within the aggregation window, the entire parent directory is invalidated (i.e., `/parent/*`).
  * If more than **3 sibling directories** would individually receive full invalidations, consolidate to their parent directory. This consolidation may continue up to `/` root.
* **Scheduling:** Invalidations are submitted at most once per aggregation window (approx every 5 minutes). The first event triggers a one-time scheduler for 5 minutes later; additional events before that update the aggregate.
* **No constant cron:** Avoid always-on scheduled cron. Use one-shot scheduling mechanisms (EventBridge Scheduler or Step Functions Wait) created per aggregate.
* **Idempotency & Race conditions:** Use DynamoDB conditional updates and optimistic locking to avoid duplicate invalidations and to ensure no events lost.
* **Permissions:** The invalidator stack needs:

  * `s3:GetBucketTagging`
  * `cloudfront:ListDistributions`, `cloudfront:GetDistribution`, `cloudfront:ListTagsForResource` (or equivalent), `cloudfront:CreateInvalidation`
  * `dynamodb:*` for aggregate store or least privilege for reads/writes
  * `events:PutRule`, `events:PutTargets` (if using EventBridge Scheduler), or `scheduler:CreateSchedule` for EventBridge Scheduler.
  * Logging & metrics (CloudWatch)
* **Tag-based isolation:** The invalidator must only handle events for buckets/distributions with the same `Application` tag (prevents cross-app invalidations).
* **Multi-distribution:** A single bucket update could map to multiple CloudFront distributions with same `Application` tag — invalidation must target all.

---

# 3 — Data model (DynamoDB) — concrete suggestion

Table: `InvalidationAggregates`

* **PK:** `AppKey` (string) — `Application` tag value
* **SK:** `AggregateId` (string) — e.g. `agg#<epoch-ms>` or `dist#<distributionId>` (if you maintain per-dist aggregates)
* **Attributes:**

  * `paths`: set<string> — normalized object paths (e.g. `/images/2025/12/01/photo.jpg`)
  * `pathCounts`: map<string,int> — counts of events per path or per parent dir (optional)
  * `scheduledAt`: number (epoch ms)
  * `state`: string enum `open|scheduled|processing|done|failed`
  * `lockToken`: string — used for optimistic lock (if needed)
  * `createdAt` / `lastUpdatedAt`
  * `invalidations`: list of results (CloudFront invalidation IDs)
* **Indexes:**

  * GSI on `state` or `scheduledAt` if you need secondary queries.

**Why DynamoDB?**

* Low-latency atomic updates (`UpdateItem` with `ADD` for sets and `ConditionExpression`), highly available, supports TTL/cleanup.

---

# 4 — Consolidation algorithm (detailed)

**Input:** set of object keys (paths) within an aggregation window (5 minutes) for a given AppKey.

**Definitions:**

* `path` is normalized with leading slash, no duplicate slashes, percent-decoded as appropriate (normalization rules must be defined).
* `parent directory` of `/a/b/c.txt` is `/a/b/`.
* `sibling directories` are directories that share same parent.

**Step 0 — Preprocessing**

* Normalize all paths.
* Strip query strings if present; only use object key.
* Deduplicate exact paths.

**Step 1 — Count per parent directory**

* For each path, increment `count[parentDir]` (count of distinct object events in that directory).

**Step 2 — Apply threshold for directory full invalidation**

* For each parentDir where `count[parentDir] > 3`:

  * Replace all individual `path` entries under that parent with a single invalidation entry: `parentDir + '*'` (e.g., `/a/b/*`).
* Remove all child path entries subsumed by directory invalidations.

**Step 3 — Sibling consolidation**

* For each parent of directories (grandparent):

  * Let `dirs` = set of child directories under that parent that are currently marked for full invalidation (`/a/b/*`, `/a/c/*`, ...).
  * If `count(dirs) > 3`, then replace all those sibling `dir/*` entries with single `parent/*` (`/a/*`).
* Continue this consolidation iteratively up the tree:

  * After replacing with `parent/*`, check parent’s parent for sibling consolidation, etc., until root or no change.

**Step 4 — Final dedupe and limit**

* Deduplicate final invalidation paths.
* CloudFront accepts up to 1000 paths per invalidation — if over limit, split into multiple invalidations (but keep consolidation rules applied first). Consider chunking by path count or by directory group.

**Examples**

* Events: `/a/b/1.jpg`, `/a/b/2.jpg`, `/a/b/3.jpg`, `/a/b/4.jpg` → parent `/a/b/*` (because >3)
* If `/a/c/*`, `/a/d/*`, `/a/e/*`, `/a/f/*` would all be produced (>3 sibling dirs) → consolidate to `/a/*`.
* This can propagate up to `/` if needed.

**Edge cases**

* Root-level many independent file updates → may yield `/*` invalidation. That is allowed but should be documented and monitored for cost.

---

# 5 — Concurrency, race conditions, and correctness

**Goals**

* No path lost.
* No duplicate invalidations (or duplicates recorded and tolerated).
* Ensure that events arriving just before processing are either included or safely handled.

**Key mechanisms**

1. **Atomic updates on DynamoDB:**

   * Use `UpdateItem` with `ADD` for sets or `SET` with `list_append` and a `ConditionExpression` on `state = 'open' OR attribute_not_exists(state)`.
   * When scheduling, set `state = 'scheduled'` and `scheduledAt = <now + 5min>` using a conditional put that only creates schedule if `state` was not `scheduled` or `processing`.

2. **One-shot scheduler + atomic switching:**

   * Scheduler invokes `processor` at scheduled time.
   * `processor` does a conditional update: set `state = 'processing'` only if `state = 'scheduled' AND lastUpdatedAt <= scheduledAt`. This avoids race where new events flip the `scheduledAt`.
   * If conditional update fails, the processor fetches the latest aggregate and either aborts (if schedule moved) or retries with new window.

3. **Events arriving during processing:**

   * When `processor` starts, it atomically flips to `processing`. Any incoming events must see the `state` change and, by policy, either:

     * Create a **new** aggregate scheduled for next 5-minute window (i.e., `scheduledAt = now + 5min`) OR
     * Append to a `pending` list attached to the existing aggregate that will be processed in next cycle.
   * Recommended: incoming events that detect `state != open && state != scheduled` create a new aggregate and schedule a new one-shot invocation. This ensures events are not lost; they just go into next window.

4. **Idempotency token for invalidation submission:**

   * The `CreateInvalidation` call returns an invalidation ID. Store it. If a duplicate submission occurs (same path list), the CloudFront API will still create a new invalidation but storing the ID prevents re-submitting if the aggregate was already marked `done`.

5. **Optimistic locking / conditional writes**

   * All state transitions use conditional updates (`ConditionExpression`) to guarantee single-writer semantics.

6. **Retries and DLQ**

   * If processing fails, mark aggregate `failed` and push to DLQ for manual reprocessing.

---

# 6 — Permissions / IAM (minimum required)

**Principal:** Lambda execution role(s), Step Functions, EventBridge Scheduler as needed.

**S3**

* `s3:GetBucketTagging` on `arn:aws:s3:::*` (or narrow to known buckets)
* (Optional) `s3:GetObject` if you must inspect objects (not required for tags only)

**CloudFront**

* `cloudfront:ListDistributions` (read)
* `cloudfront:ListTagsForResource` (read tags)
* `cloudfront:GetDistribution` (read config if needed)
* `cloudfront:CreateInvalidation` (write)
* `cloudfront:GetInvalidation` (optional, for status)
* **Resource scope:** Prefer `arn:aws:cloudfront::account-id:distribution/*` for distributions in-account.

**DynamoDB**

* `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:Query`, `dynamodb:DescribeTable` on the `InvalidationAggregates` table.

**EventBridge Scheduler / Events / StepFunctions**

* `scheduler:CreateSchedule`, `scheduler:DeleteSchedule`, `scheduler:Invoke` if using EventBridge Scheduler (or Events `PutRule`, `PutTargets` if older approach).
* Or Step Functions StartExecution.

**CloudWatch**

* `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
* `cloudwatch:PutMetricData` for custom metrics (optional)

**Tag inspection cross-account note**

* If distributions or buckets are in different accounts, you must add cross-account permissions or use a centralized role that has permission to read tags across accounts.

**Policy snippet (example)** — minimal illustrative (must be hardened in implementation):

```yaml
PolicyName: InvalidationLambdaPolicy
PolicyDocument:
  Statement:
    - Effect: Allow
      Action:
        - s3:GetBucketTagging
      Resource: "arn:aws:s3:::*"
    - Effect: Allow
      Action:
        - cloudfront:ListDistributions
        - cloudfront:ListTagsForResource
        - cloudfront:CreateInvalidation
        - cloudfront:GetDistribution
      Resource: "arn:aws:cloudfront::ACCOUNT_ID:distribution/*"
    - Effect: Allow
      Action:
        - dynamodb:GetItem
        - dynamodb:UpdateItem
        - dynamodb:PutItem
        - dynamodb:Query
      Resource: "arn:aws:dynamodb:REGION:ACCOUNT_ID:table/InvalidationAggregates"
    - Effect: Allow
      Action:
        - scheduler:CreateSchedule
        - scheduler:DeleteSchedule
        - scheduler:Invoke
      Resource: "*"
```

---

# 7 — CloudFormation / Serverless stack boundaries & resources

**Stacks (existing):**

1. `Stack-Buckets` — owns S3 buckets; tag `Application=<app-key>`.
2. `Stack-CloudFront` — owns CloudFront distributions and Route53 records; distributions are tagged `Application=<app-key>`.

**New stack: `Stack-Invalidator` (this spec)**

* **Parameters**

  * `ApplicationTagKey` (default `Application`)
  * `AggregationWindowMinutes` (default `5`)
  * `ConsolidationThreshold` (default `3`)
  * `DynamoDBTableName` (or create table)
  * `LogRetentionDays`
* **Resources**

  * DynamoDB table `InvalidationAggregates` (or reference existing)
  * SQS DLQ (standard) for lambdas
  * Lambda `ingestor` (S3 -> ingest) — has event source mapping from SQS if buckets push to SQS, or S3 event directly (but prefer SQS to decouple).
  * Lambda `processor` — invoked by EventBridge Scheduler or Step Functions
  * EventBridge Scheduler permissions / role (if used)
  * IAM Roles & policies described above
  * CloudWatch Alarms and metrics; optional SNS topic for alerts
* **Outputs**

  * `InvalidatorDynamoDBTable`
  * `InvalidatorRoleArn`
  * `EventBridgeSchedulerRole`

**Implementation notes**

* Prefer S3 → SQS → Ingestor pattern: S3 sends events to an SQS queue (owned by bucket stack or created here via cross-stack reference); ingestor reads SQS and writes to DynamoDB.
* If bucket stack cannot send to SQS, use S3 → SNS → Lambda in this stack (requires cross-stack config).
* All resources must be tagged: include the `Application` tag (or allow wildcard/none).

---

# 8 — Event structure example (ingestor input)

```json
{
  "eventTime": "2025-12-08T12:34:56Z",
  "bucket": "my-app-bucket",
  "objectKey": "images/2025/12/08/photo.jpg",
  "eventName": "ObjectCreated:Put",
  "applicationTag": "awesome-app"
}
```

---

# 9 — Pseudocode for ingestor & processor

**Ingestor (on S3 event)**

```python
def handle_s3_event(event):
    record = parse_event(event)
    app_key = get_bucket_application_tag(record.bucket)  # s3:GetBucketTagging
    if not app_key:
        return  # ignore
    aggregate_key = app_key
    now = epoch_ms()
    # Try to update existing open aggregate
    res = dynamodb.update_item(
       Key={PK: aggregate_key, SK: 'current'},
       UpdateExpression="ADD paths :p SET lastUpdatedAt = :u",
       ExpressionAttributeValues={":p": set([normalize(record.objectKey)]), ":u": now},
       ReturnValues="UPDATED_NEW"
    )
    # If aggregate didn't exist or no scheduledAt, schedule one-time EventBridge invocation at now + window
    if not res.get('scheduledAt'):
       scheduled_at = now + AggregationWindowMinutes*60000
       create_one_time_schedule(app_key, scheduled_at)
       dynamodb.update_item(... SET scheduledAt = scheduled_at, state='scheduled' ...)
```

**Processor (invoked at scheduled time)**

```python
def processor(event):
    app_key = event.app_key
    # Atomically move state scheduled -> processing
    success = dynamodb.conditional_update(
      Key={PK: app_key, SK: 'current'},
      ConditionExpression="state = :scheduled",
      UpdateExpression="SET state = :processing"
    )
    if not success:
       return  # another worker beat us, or new schedule exists
    aggregate = dynamodb.get_item(...)
    paths = aggregate.paths
    consolidated_paths = consolidate_paths(paths)  # apply algorithm
    dists = find_distributions_by_tag(app_key)
    if not dists: 
       mark_done(aggregate, reason="no distributions")
       return
    for dist in dists:
       resp = cloudfront.create_invalidation(DistributionId=dist.Id, Paths=consolidated_paths)
       record_invalidation(resp, dist)
    mark_done(aggregate)
```

---

# 10 — Observability & metrics

* **Metrics**

  * `InvalidationsSubmittedCount` (per app)
  * `InvalidationPathsPerRequest` (distribution)
  * `AggregatesScheduled` / `AggregatesFailed`
  * `EventsReceived` (per bucket/app)
* **Logs**

  * Lambda logs for ingestor & processor
  * Timeline logs for aggregate state changes
* **Alarms**

  * High `AggregatesFailed` rate
  * High number of invalidations per hour (cost signal)
* **Dashboards**

  * Show latest invalidations, path consolidation counts, distribution mapping.

---

# 11 — Testing & QA plan

* **Unit tests**

  * Consolidation algorithm edge cases: small sets, >3 rule, multi-level consolidation.
  * Normalize path inputs and dedupe.
* **Integration tests**

  * End-to-end with a test bucket and a test CloudFront distribution: create events and assert that invalidation is created with expected paths after ~5 minutes.
  * Tests for race conditions: fire multiple events across window edges and ensure no events lost and correct scheduling.
* **Chaos tests**

  * Force concurrent processors, delayed scheduler invocation, failed API calls — ensure system recovers and no double invalidation beyond accepted tolerance.
* **Security tests**

  * Validate IAM least-privilege: ensure lambdas can only read tags for distributions/buckets and create invalidations.
* **Performance**

  * Test with burst events (hundreds/minute) — ensure DynamoDB scales and ingestion handles backlog (SQS + lambda concurrency).

---

# 12 — Deployment & configuration considerations

* **Parameters to expose**

  * Aggregation window (minutes)
  * Consolidation threshold (default 3)
  * Max invalidation paths per request (CloudFront limit)
  * Role ARNs and permitted accounts (if multi-account)
* **Cross-stack references**

  * Provide an output from `Stack-Buckets` listing buckets (or have buckets tag with `Application` and allow S3 to send events to an SQS queue in invalidator stack).
  * Provide distribution ARNs or rely on CloudFront tag discovery (recommended).
* **Multi-account**

  * If buckets and distributions live in different accounts, a cross-account role and trust must be established; the invalidator needs read access to tags across accounts.
* **Costs**

  * DynamoDB read/writes, Lambda invocation, CloudFront invalidation costs. Monitor and limit large `/*` invalidations.

---

# 13 — Example CloudFormation / SAM resources (outline)

* `InvalidationAggregates` (AWS::DynamoDB::Table)
* `InvalidatorIngestor` (AWS::Lambda::Function) + `InvalidatorProcessor`
* `InvalidatorRole` (AWS::IAM::Role) + PolicyDocument (s3:GetBucketTagging, cloudfront:CreateInvalidation, dynamodb:*, scheduler:CreateSchedule)
* `InvalidatorSqsQueue` (AWS::SQS::Queue) + DLQ
* `EventBridgeSchedulerRole` (if EventBridge Scheduler used)
* `CloudWatchDashboard` / `MetricFilters` / `Alarms`

> The AI agent should generate full SAM or CloudFormation templates with parameters, outputs, and proper dependencies.

---

# 14 — Acceptance criteria (what “done” looks like)

1. When a bucket object is updated and the bucket has `Application=<app-key>` tag, the invalidator schedules an invalidation run at `now + aggregationWindow` and aggregates subsequent events into the same window.
2. After the scheduled window, a processor Lambda runs exactly once for the aggregate (atomic state change) and submits CloudFront invalidation(s) to all distributions with `Application=<app-key>` tag.
3. Consolidation rules are applied: >3 events for a parent directory => `parent/*`; >3 sibling directory full-invalidations => collapse to parent; propagate up as needed.
4. No bucket events for which there is *no* distribution with the same tag should produce invalidations.
5. Events arriving during processing are not lost — they are scheduled into the next window.
6. System includes metrics, logging, and alarms. IAM policies are least-privilege for required actions.
7. CloudFormation/SAM templates validate with cfn-lint and deploy cleanly.

---

# 15 — Appendices

## A — Consolidation pseudocode (concise)

```python
def consolidate(paths, threshold=3):
    paths = normalize_and_dedup(paths)
    # build tree counts per directory
    dir_counts = defaultdict(int)
    for p in paths:
        parent = parent_dir(p)
        dir_counts[parent] += 1
    # mark full-dir invalidation if count > threshold
    full_dirs = set(d for d,c in dir_counts.items() if c > threshold)
    # remove paths under full_dirs
    remaining = [p for p in paths if not any(p.startswith(fd) for fd in full_dirs)]
    invalidations = set(f"{d}*" for d in full_dirs) | set(remaining)
    # sibling consolidation
    while True:
        parents = group_by_parent(invalidations)  # maps parent->list(child dir*)
        changed = False
        for parent, childs in parents.items():
            if len(childs) > threshold:
                # replace childs with parent/*
                invalidations -= set(childs)
                invalidations.add(f"{parent}*")
                changed = True
        if not changed:
            break
    return sorted(invalidations)
```

## B — Example path normalization rules

* Ensure leading `/` (e.g., `images/foo` -> `/images/foo`)
* Remove duplicate slashes
* Trim whitespace
* Do not include query string or fragments
* Percent-decode or canonicalize using S3 key rules (document chosen approach)

---

# 16 — Next steps for the Kiro AI agent

1. Generate detailed CloudFormation (SAM) templates:

   * Parameterized `Stack-Invalidator` with all resources described above.
2. Generate Lambda code stubs (Python/Node.js) for `ingestor` and `processor` implementing pseudocode, DynamoDB I/O, event parsing, consolidation algorithm, and CloudFront API calls.
3. Generate unit tests for algorithm and integration tests using localstack (or test harness).
4. Generate IAM policy documents, and an IAM least-privilege report.
5. Generate deployment instructions and rollback plan.
6. Generate runbook for operations (how to inspect aggregates, re-run failed aggregates, revoke permissions).
7. Generate monitoring & dashboard CloudFormation fragment.

---

If you want, I can now:

* produce the SAM/CloudFormation template skeleton (full resource definitions) for `Stack-Invalidator`, or
* generate Lambda handler code (Python or Node.js) for `ingestor` and `processor` including DynamoDB conditional updates and consolidation algorithm, or
* produce the IAM policy JSON and sample cfn-lint–valid snippet.

Tell me which artifact you want first and I will generate it directly (template, lambda code, or tests).
