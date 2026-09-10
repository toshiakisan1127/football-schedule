# Architecture

## Goal

サッカーの日程情報だけを、利用者が素早く確認できることを最優先にする。

## Scope

### In scope (MVP)

- J1 と欧州主要5リーグ
- UEFA Champions League / Europa League
- 直近の日程表示
- 大会フィルター
- お気に入りクラブ
- 延期・中止表示
- 最終更新時刻表示

### Out of scope (MVP)

- 試合結果・ライブスコア
- 順位表
- ニュース
- 選手情報
- ログイン
- サーバーサイドのユーザーDB
- Push通知

## Data flow

```text
EventBridge Scheduler
        |
        v
Fixture Fetcher Lambda
        |
        +--> Football data provider
        |
        +--> validate all responses
        |
        +--> normalize
        |
        v
S3 data/fixtures.json
        |
        v
CloudFront
        |
        v
Nuxt client
```

## Normalized fixture schema

外部APIのレスポンスを直接フロントへ返さず、Lambdaで以下の形へ正規化する。

```ts
export type FixtureStatus = 'scheduled' | 'postponed' | 'cancelled'

export interface Fixture {
  id: string
  competition: {
    id: string
    name: string
    country: string
  }
  home: {
    id: string
    name: string
  }
  away: {
    id: string
    name: string
  }
  kickoff: string
  status: FixtureStatus
}

export interface FixtureDocument {
  generatedAt: string
  range: {
    from: string
    to: string
  }
  fixtures: Fixture[]
}
```

`kickoff` と `generatedAt` はUTCのISO 8601で保存し、画面表示時に利用者のタイムゾーンへ変換する。

## S3 layout

MVPでは分割しすぎず単一ファイルから始める。

```text
data/
  fixtures.json
```

試合数や転送量が問題になった場合のみ、日付・大会単位の分割を検討する。

## Refresh strategy

- EventBridge Scheduler から数時間おきにLambdaを実行する
- 直近7日程度の過去分と、今後30日程度を取得対象とする
- 全対象大会の取得・検証が成功した場合のみS3を更新する
- 失敗時は既存の正常な `fixtures.json` を保持する
- CloudFrontではJSONのキャッシュTTLを短めに設定する

## Frontend state

サーバー側のユーザーデータはMVPでは持たない。

```text
localStorage
  favoriteCompetitionIds
  favoriteTeamIds
```

## AWS stacks

### HostingStack

- S3 bucket for static Nuxt output and generated fixture JSON
- CloudFront distribution
- Origin Access Control

### DataStack

- Fixture Fetcher Lambda
- EventBridge Scheduler
- API credential storage
- S3 write permission

## Failure handling

1. 外部APIの一部取得に失敗した場合は、その実行では公開JSONを更新しない
2. Lambdaは失敗をログへ残す
3. フロントは `generatedAt` を表示し、データ鮮度を利用者が判断できるようにする
4. 不正な日時・未知のstatusなどは正規化時に弾く

## Security

- 外部APIキーはフロントへ渡さない
- S3への書き込み権限はFixture Fetcher Lambdaだけに限定する
- CloudFrontからの読み取りのみ許可する
- GitHub ActionsからAWSへ接続する場合は長期Access KeyではなくOIDCを使う

## Future ideas

- J2 / J3 / カップ戦 / 代表戦
- お気に入りだけのホーム画面
- カレンダー追加（ICS）
- PWA
- 通知
- 試合の放送・配信先情報
