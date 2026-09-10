# Architecture

## Goal

サッカーの日程情報だけを、利用者が素早く確認できることを最優先にする。

## Scope

### In scope (MVP)

- Premier League
- LaLiga
- UEFA Champions League
- 直近の日程表示
- 大会フィルター
- お気に入りクラブ
- live / finished / postponed / cancelled の状態管理
- 試合結果の表示・非表示切り替え
- 最終更新時刻表示

J1はKickoffAPIで2026/27シーズンの取得を確認できていないため、一旦MVP対象外とする。

### Out of scope (MVP)

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
        +--> KickoffAPI v2
        |
        +--> validate all responses
        |
        +--> normalize / JST window filter
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
export type FixtureStatus = 'scheduled' | 'live' | 'finished' | 'postponed' | 'cancelled'

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
  score: {
    home: number
    away: number
  } | null
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

`kickoff` と `generatedAt` はUTCのISO 8601で保存する。Lambdaの取得window判定はJSTで行い、画面表示時は利用者のローカルタイムへ変換する。

アプリ側のcompetition id（`epl` / `ucl` / `laliga`）は外部provider IDから独立させる。

## S3 layout

MVPでは分割しすぎず単一ファイルから始める。

```text
data/
  fixtures.json
```

試合数や転送量が問題になった場合のみ、日付・大会単位の分割を検討する。

## Refresh strategy

- EventBridge Schedulerから6時間おきにLambdaを実行する想定
- 現時点ではSchedulerは `DISABLED` のままにし、手動検証後に有効化する
- 前日から今後30日程度を公開対象とする
- KickoffAPIにも `from` / `to` を渡すが、providerが範囲外を返す場合に備えてLambda側でもJSTでfilterする
- 全対象大会の取得・検証が成功した場合のみS3を更新する
- 失敗時は既存の正常な `fixtures.json` を保持する
- CloudFrontではJSONのキャッシュTTLを短めに設定する

## Frontend state

サーバー側のユーザーデータはMVPでは持たない。

```text
localStorage
  favoriteCompetitionIds
  favoriteTeamIds
  showResults
```

## AWS stacks

### HostingStack

- Static Nuxt output用S3 bucket
- Fixture JSON用S3 bucket
- CloudFront distribution
- Origin Access Control

### DataStack

- Fixture Fetcher Lambda
- EventBridge Scheduler
- KickoffAPI credentialのSSM参照
- fixture data bucketへの書き込み権限

## Failure handling

1. 外部APIの一部取得に失敗した場合は、その実行では公開JSONを更新しない
2. Lambdaは失敗をログへ残す
3. フロントは `generatedAt` を表示し、データ鮮度を利用者が判断できるようにする
4. 不正な日時・未知のstatusなどは正規化時に弾く

## Security

- KickoffAPI keyはSSM SecureString `/football-schedule/kickoff-api-key` で管理する
- 外部APIキーはフロントへ渡さない
- S3への書き込み権限はFixture Fetcher Lambdaだけに限定する
- CloudFrontからの読み取りのみ許可する
- GitHub ActionsからAWSへ接続する場合は長期Access KeyではなくOIDCを使う

## Future ideas

- J1 / J2 / J3 / カップ戦 / 代表戦
- 欧州他リーグ / Europa League
- お気に入りだけのホーム画面
- カレンダー追加（ICS）
- PWA
- 通知
- 試合の放送・配信先情報
