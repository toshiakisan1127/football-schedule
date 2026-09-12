# Error alerting and throttling

## Purpose

Fixture refresh failures are operationally important, but the LIVE fetcher runs every five minutes. A persistent upstream or application failure must not generate one email per execution.

The alerting path therefore separates error detection from notification delivery and uses DynamoDB to throttle repeated notifications with the same normalized error identity.

## Flow

```text
FixtureFetcher Lambda (daily)
          |
          | structured ERROR logs
          v
FixtureFetcher CloudWatch Log Group
          |
          | Subscription Filter: $.level = ERROR
          +-------------------------------+
                                          |
LiveFixtureFetcher Lambda (5 min)         |
          |                               |
          | structured ERROR logs         |
          v                               |
LiveFixtureFetcher CloudWatch Log Group   |
          |                               |
          | Subscription Filter           |
          | $.level = ERROR               |
          +-------------------------------+
                                          v
                               BatchErrorNotifier Lambda
                                          |
                                  build fingerprint
                                          |
                                          v
                               DynamoDB alert-state table
                                  conditional update
                                   /             \
                         claim succeeds       same fingerprint
                              |                in cooldown
                              v                    |
                          SNS Topic                +--> suppress
                              |
                              v
                          Email alert
```

WARN and INFO logs are not sent to the notifier.

## Notification behavior

- First occurrence of an error fingerprint: notify immediately.
- Same fingerprint during the next 6 hours: suppress the email.
- Same fingerprint after the 6-hour cooldown: notify again if the failure still exists.
- Different fingerprint: notify immediately, even while another error is in cooldown.
- If DynamoDB state access fails: fail open and send the alert rather than hiding a real failure.
- If SNS publish fails after a throttle claim was acquired: release that claim so a later invocation can retry.

The LIVE fetcher currently runs every five minutes, so a persistent identical error changes from a possible 288 emails/day to at most one notification every six hours for that fingerprint.

## DynamoDB table

The table is created in `DataStack` as `BatchErrorAlertStateTable`.

| Property | Value |
| --- | --- |
| Purpose | notification throttle state only |
| Partition key | `fingerprint` (String) |
| Billing mode | `PAY_PER_REQUEST` |
| TTL attribute | `expiresAt` |
| Removal policy | `DESTROY` |
| Application cooldown | 21,600 seconds (6 hours) |
| State TTL | 86,400 seconds (24 hours) |
| IAM | `BatchErrorNotifier` has read/write data access |

No GSI or sort key is required because every independent error identity has exactly one throttle-state row.

### Item shape

```json
{
  "fingerprint": "<sha256 hex>",
  "lastNotifiedAt": 1789243200,
  "expiresAt": 1789329600
}
```

- `fingerprint`: SHA-256 of the normalized error identity.
- `lastNotifiedAt`: epoch seconds at which the notifier acquired the current notification claim.
- `expiresAt`: DynamoDB TTL timestamp, currently `lastNotifiedAt + 24h`.

DynamoDB TTL is for automatic cleanup, not for enforcing the six-hour cooldown. Cooldown enforcement uses a conditional update against `lastNotifiedAt`.

## Conditional claim

Before publishing to SNS, the notifier performs an `UpdateItem` with this logical condition:

```text
attribute_not_exists(fingerprint)
OR lastNotifiedAt <= now - 6 hours
```

On success, it writes:

```text
lastNotifiedAt = now
expiresAt      = now + 24 hours
```

A `ConditionalCheckFailedException` means another notification with the same fingerprint is still in the cooldown window, so the email is intentionally suppressed.

Using a conditional write also protects against concurrent CloudWatch Logs subscription invocations sending duplicate emails for the same fingerprint.

## Fingerprint definition

The fingerprint includes:

- CloudWatch `logGroup`, so daily and LIVE fetchers are independent alert sources.
- Normalized identities of the ERROR log events in the delivery batch.

The following volatile fields are removed before hashing:

- `timestamp`
- `requestId`
- `request_id`
- `awsRequestId`
- `stackTrace`
- `logStream`

Nested JSON strings are parsed and normalized recursively when possible. Object keys are sorted before SHA-256 hashing.

This means repeated executions with a new request ID or timestamp are still treated as the same failure, while a materially different provider/application error gets a different fingerprint and can notify immediately.

## Failure policy

### DynamoDB unavailable

The notifier logs its own error and **sends the SNS alert anyway**. Throttling is secondary to not losing operational failures.

### SNS publish failure

The notifier attempts to delete the throttle row only when `lastNotifiedAt` still equals the timestamp claimed by that invocation. This avoids deleting a newer claim written by another invocation.

The Lambda then rethrows the SNS failure.

## Configuration

The notifier receives these environment variables from CDK:

```text
ALERT_TOPIC_ARN
ALERT_STATE_TABLE_NAME
ALERT_COOLDOWN_SECONDS=21600
ALERT_STATE_TTL_SECONDS=86400
```

The email address itself is not stored in Lambda environment variables. `BATCH_ALERT_EMAIL` is supplied as a GitHub Actions repository variable at CDK synth/deploy time and is used to create the SNS email subscription.

## Related files

- `infra/lib/data-stack.ts`
- `infra/lambda/error-notifier/handler.py`
- `infra/lambda/error-notifier/tests/test_handler.py`
- [`architecture.md`](architecture.md)
- [`live-fixtures.md`](live-fixtures.md)
