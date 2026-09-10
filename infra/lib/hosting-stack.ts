import {
  CfnOutput,
  Duration,
  RemovalPolicy,
  Stack,
  type StackProps,
} from 'aws-cdk-lib'
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront'
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins'
import * as iam from 'aws-cdk-lib/aws-iam'
import * as s3 from 'aws-cdk-lib/aws-s3'
import type { Construct } from 'constructs'

const GITHUB_REPOSITORY = 'toshiakisan1127/football-schedule'
const GITHUB_IMMUTABLE_REPOSITORY =
  'repo:toshiakisan1127@48203235/football-schedule@1364383476'
const CDK_BOOTSTRAP_QUALIFIER = 'hnb659fds'
const AWS_REGION = 'ap-northeast-1'

export class HostingStack extends Stack {
  readonly siteBucket: s3.Bucket
  readonly dataBucket: s3.Bucket
  readonly distribution: cloudfront.Distribution

  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props)

    this.siteBucket = new s3.Bucket(this, 'SiteBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.RETAIN,
    })

    this.dataBucket = new s3.Bucket(this, 'DataBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.RETAIN,
    })

    const siteOrigin = origins.S3BucketOrigin.withOriginAccessControl(this.siteBucket)
    const dataOrigin = origins.S3BucketOrigin.withOriginAccessControl(this.dataBucket)

    const fixtureDataCachePolicy = new cloudfront.CachePolicy(this, 'FixtureDataCachePolicy', {
      defaultTtl: Duration.minutes(5),
      minTtl: Duration.seconds(0),
      maxTtl: Duration.minutes(15),
      enableAcceptEncodingBrotli: true,
      enableAcceptEncodingGzip: true,
    })

    this.distribution = new cloudfront.Distribution(this, 'Distribution', {
      defaultRootObject: 'index.html',
      defaultBehavior: {
        origin: siteOrigin,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      additionalBehaviors: {
        'data/*': {
          origin: dataOrigin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          cachePolicy: fixtureDataCachePolicy,
        },
      },
      errorResponses: [403, 404].map((httpStatus) => ({
        httpStatus,
        responseHttpStatus: 200,
        responsePagePath: '/index.html',
        ttl: Duration.seconds(0),
      })),
    })

    // The account already has the standard GitHub Actions OIDC provider.
    // Reference it here rather than owning it in another application stack.
    const githubOidcProvider = iam.OpenIdConnectProvider.fromOpenIdConnectProviderArn(
      this,
      'GitHubOidcProvider',
      `arn:${this.partition}:iam::${this.account}:oidc-provider/token.actions.githubusercontent.com`,
    )

    const deployRole = new iam.Role(this, 'GitHubDeployRole', {
      roleName: 'github-actions-football-schedule-cdk-deploy',
      assumedBy: new iam.WebIdentityPrincipal(
        githubOidcProvider.openIdConnectProviderArn,
        {
          StringEquals: {
            'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
            'token.actions.githubusercontent.com:sub':
              `${GITHUB_IMMUTABLE_REPOSITORY}:ref:refs/heads/main`,
          },
        },
      ),
      description: `Deploy ${GITHUB_REPOSITORY} production CDK stacks from GitHub Actions`,
    })

    deployRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['sts:AssumeRole'],
        resources: ['deploy-role', 'file-publishing-role', 'lookup-role'].map(
          (roleType) =>
            `arn:${this.partition}:iam::${this.account}:role/cdk-${CDK_BOOTSTRAP_QUALIFIER}-${roleType}-${this.account}-${AWS_REGION}`,
        ),
      }),
    )

    deployRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['s3:ListBucket', 's3:GetBucketLocation'],
        resources: [this.siteBucket.bucketArn],
      }),
    )

    deployRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['s3:GetObject', 's3:PutObject', 's3:DeleteObject'],
        resources: [this.siteBucket.arnForObjects('*')],
      }),
    )

    deployRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['cloudformation:DescribeStacks'],
        resources: [
          `arn:${this.partition}:cloudformation:${AWS_REGION}:${this.account}:stack/${this.stackName}/*`,
        ],
      }),
    )

    deployRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['cloudfront:CreateInvalidation'],
        resources: [
          `arn:${this.partition}:cloudfront::${this.account}:distribution/${this.distribution.distributionId}`,
        ],
      }),
    )

    new CfnOutput(this, 'SiteBucketName', {
      value: this.siteBucket.bucketName,
    })

    new CfnOutput(this, 'DataBucketName', {
      value: this.dataBucket.bucketName,
    })

    new CfnOutput(this, 'CloudFrontDistributionId', {
      value: this.distribution.distributionId,
    })

    new CfnOutput(this, 'CloudFrontDomainName', {
      value: this.distribution.distributionDomainName,
    })

    new CfnOutput(this, 'GitHubDeployRoleArn', {
      value: deployRole.roleArn,
    })
  }
}
