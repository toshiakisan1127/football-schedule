import {
  CfnOutput,
  Duration,
  RemovalPolicy,
  Stack,
  type StackProps,
} from 'aws-cdk-lib'
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront'
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins'
import * as s3 from 'aws-cdk-lib/aws-s3'
import type { Construct } from 'constructs'

export class HostingStack extends Stack {
  readonly siteBucket: s3.Bucket
  readonly distribution: cloudfront.Distribution

  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props)

    this.siteBucket = new s3.Bucket(this, 'SiteBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.RETAIN,
    })

    const origin = origins.S3BucketOrigin.withOriginAccessControl(this.siteBucket)

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
        origin,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      additionalBehaviors: {
        'data/*': {
          origin,
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

    new CfnOutput(this, 'BucketName', {
      value: this.siteBucket.bucketName,
    })

    new CfnOutput(this, 'CloudFrontDistributionId', {
      value: this.distribution.distributionId,
    })

    new CfnOutput(this, 'CloudFrontDomainName', {
      value: this.distribution.distributionDomainName,
    })
  }
}
