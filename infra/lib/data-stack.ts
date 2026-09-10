import { CfnOutput, Duration, Stack, type StackProps } from 'aws-cdk-lib'
import * as iam from 'aws-cdk-lib/aws-iam'
import * as lambda from 'aws-cdk-lib/aws-lambda'
import * as scheduler from 'aws-cdk-lib/aws-scheduler'
import * as s3 from 'aws-cdk-lib/aws-s3'
import * as ssm from 'aws-cdk-lib/aws-ssm'
import type { Construct } from 'constructs'
import path from 'node:path'

export interface DataStackProps extends StackProps {
  dataBucket: s3.IBucket
}

export class DataStack extends Stack {
  constructor(scope: Construct, id: string, props: DataStackProps) {
    super(scope, id, props)

    const apiKeyParameterName = '/football-schedule/api-football-key'

    const apiKeyParameter = ssm.StringParameter.fromSecureStringParameterAttributes(
      this,
      'ApiFootballKeyParameter',
      {
        parameterName: apiKeyParameterName,
        version: 1,
      },
    )

    const fixtureFetcher = new lambda.Function(this, 'FixtureFetcher', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(process.cwd(), 'lambda', 'fixture-fetcher'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_13.bundlingImage,
          command: [
            'bash',
            '-c',
            'python -m pip install --no-cache-dir -r requirements.txt -t /asset-output && cp handler.py /asset-output/handler.py',
          ],
        },
      }),
      description: 'Fetch and normalize football fixtures before publishing them to S3.',
      timeout: Duration.seconds(90),
      environment: {
        DATA_BUCKET_NAME: props.dataBucket.bucketName,
        API_KEY_PARAMETER_NAME: apiKeyParameterName,
        FIXTURE_OBJECT_KEY: 'data/fixtures.json',
        LOOKBACK_DAYS: '1',
        LOOKAHEAD_DAYS: '30',
      },
    })

    props.dataBucket.grantPut(fixtureFetcher, 'data/*')
    apiKeyParameter.grantRead(fixtureFetcher)

    const schedulerRole = new iam.Role(this, 'FixtureSchedulerRole', {
      assumedBy: new iam.ServicePrincipal('scheduler.amazonaws.com'),
    })
    fixtureFetcher.grantInvoke(schedulerRole)

    new scheduler.CfnSchedule(this, 'FixtureRefreshSchedule', {
      description: 'Refresh football fixture data every six hours.',
      flexibleTimeWindow: {
        mode: 'OFF',
      },
      scheduleExpression: 'rate(6 hours)',
      state: 'DISABLED',
      target: {
        arn: fixtureFetcher.functionArn,
        roleArn: schedulerRole.roleArn,
      },
    })

    new CfnOutput(this, 'ApiKeyParameterName', {
      value: apiKeyParameterName,
    })
  }
}
