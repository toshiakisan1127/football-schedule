#!/usr/bin/env node
import { App } from 'aws-cdk-lib'
import { DataStack } from '../lib/data-stack.js'
import { HostingStack } from '../lib/hosting-stack.js'

const app = new App()

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION ?? 'ap-northeast-1',
}

const hostingStack = new HostingStack(app, 'FootballScheduleHostingStack', { env })

const dataStack = new DataStack(app, 'FootballScheduleDataStack', {
  env,
  dataBucket: hostingStack.siteBucket,
})

dataStack.addDependency(hostingStack)

app.synth()
