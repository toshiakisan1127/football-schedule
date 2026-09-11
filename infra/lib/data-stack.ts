import { CfnOutput, Duration, RemovalPolicy, Stack, type StackProps } from 'aws-cdk-lib'
import * as iam from 'aws-cdk-lib/aws-iam'
import * as lambda from 'aws-cdk-lib/aws-lambda'
import * as logs from 'aws-cdk-lib/aws-logs'
import * as logsDestinations from 'aws-cdk-lib/aws-logs-destinations'
import * as scheduler from 'aws-cdk-lib/aws-scheduler'
import * as s3 from 'aws-cdk-lib/aws-s3'
import * as sns from 'aws-cdk-lib/aws-sns'
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions'
import * as ssm from 'aws-cdk-lib/aws-ssm'
import type { Construct } from 'constructs'
import path from 'node:path'

export interface DataStackProps extends StackProps {
  dataBucket: s3.IBucket
}

export class DataStack extends Stack {
  constructor(scope: Construct, id: string, props: DataStackProps) {
    super(scope, id, props)

    const apiKeyParameterName = '/football-schedule/kickoff-api-key'

    const apiKeyParameter = ssm.StringParameter.fromSecureStringParameterAttributes(
      this,
      'KickoffApiKeyParameter',
      {
        parameterName: apiKeyParameterName,
        version: 1,
      },
    )

    const fixtureFetcherLogGroup = new logs.LogGroup(this, 'FixtureFetcherLogGroup', {
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: RemovalPolicy.RETAIN,
    })

    const fixtureFetcher = new lambda.Function(this, 'FixtureFetcher', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'split_handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(process.cwd(), 'lambda', 'fixture-fetcher'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_13.bundlingImage,
          command: ['bash', '-c', 'bash package.sh /asset-output'],
        },
      }),
      description: 'Fetch and normalize football fixtures before publishing them to S3.',
      timeout: Duration.minutes(5),
      loggingFormat: lambda.LoggingFormat.JSON,
      applicationLogLevelV2: lambda.ApplicationLogLevel.INFO,
      systemLogLevelV2: lambda.SystemLogLevel.INFO,
      logGroup: fixtureFetcherLogGroup,
      environment: {
        DATA_BUCKET_NAME: props.dataBucket.bucketName,
        API_KEY_PARAMETER_NAME: apiKeyParameterName,
        FIXTURE_OBJECT_PREFIX: 'data/fixtures',
        LOOKBACK_DAYS: '1',
        LOOKAHEAD_DAYS: '30',
      },
    })

    props.dataBucket.grantPut(fixtureFetcher, 'data/*')
    apiKeyParameter.grantRead(fixtureFetcher)

    const batchErrorTopic = new sns.Topic(this, 'BatchErrorTopic', {
      displayName: 'Match Calendar batch errors',
    })

    const alertEmail = process.env.BATCH_ALERT_EMAIL?.trim()
    if (alertEmail) {
      batchErrorTopic.addSubscription(new subscriptions.EmailSubscription(alertEmail))
    }

    const errorNotifier = new lambda.Function(this, 'BatchErrorNotifier', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(process.cwd(), 'lambda', 'error-notifier')),
      description: 'Forward FixtureFetcher ERROR logs to the batch alert SNS topic.',
      timeout: Duration.seconds(30),
      environment: {
        ALERT_TOPIC_ARN: batchErrorTopic.topicArn,
      },
    })

    batchErrorTopic.grantPublish(errorNotifier)

    new logs.SubscriptionFilter(this, 'FixtureFetcherErrorSubscription', {
      logGroup: fixtureFetcherLogGroup,
      destination: new logsDestinations.LambdaDestination(errorNotifier),
      filterPattern: logs.FilterPattern.stringValue('$.level', '=', 'ERROR'),
    })

    const schedulerRole = new iam.Role(this, 'FixtureSchedulerRole', {
      assumedBy: new iam.ServicePrincipal('scheduler.amazonaws.com'),
    })
    fixtureFetcher.grantInvoke(schedulerRole)

    new scheduler.CfnSchedule(this, 'FixtureRefreshSchedule', {
      description: 'Refresh football fixture data daily at 05:00 JST.',
      flexibleTimeWindow: {
        mode: 'OFF',
      },
      scheduleExpression: 'cron(0 5 * * ? *)',
      scheduleExpressionTimezone: 'Asia/Tokyo',
      state: 'ENABLED',
      target: {
        arn: fixtureFetcher.functionArn,
        roleArn: schedulerRole.roleArn,
      },
    })

    new CfnOutput(this, 'ApiKeyParameterName', {
      value: apiKeyParameterName,
    })

    new CfnOutput(this, 'FixtureFetcherFunctionName', {
      value: fixtureFetcher.functionName,
    })

    new CfnOutput(this, 'BatchErrorTopicArn', {
      value: batchErrorTopic.topicArn,
    })

    new CfnOutput(this, 'BatchAlertEmailConfigured', {
      value: alertEmail ? 'true' : 'false',
    })
  }
}
