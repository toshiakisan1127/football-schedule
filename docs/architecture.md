# Architecture

## Goal

サッカーの日程とLIVE状況を、利用者が日本時間で素早く確認できることを最優先にする。

外部APIの詳細はバックエンドに閉じ込め、フロントはS3へ公開されたアプリ独自JSONだけを読む。ユーザー個人設定はlocalStorageに保存し、サーバーサイドのユーザーDBは持たない。

## Current scope

### Enabled competitions

- Premier League
- La Liga
- Bundesliga
- Ligue 1
- J1 League
- UEFA Champions League
- UEFA Europa League
- UEFA Conference League

すべてAPI-Football v3を利用する。Serie Aなどは今後の追加対象。

### Main product capabilities

- 全日程 / 今日 / 明日 / 今週末 / 今から見る
- 複数大会フィルター
- 複数チームフィルター
- 日本人選手所属チームの 🇯🇵 表示 / 絞り込み
- JSTキックオフ表示
- 結果の表示 / 非表示
- LIVEスコア・経過時間
- LIVEイベント（ゴール / カード / 交代）の展開表示
- ライト / ダークテーマ
- PWA

## System overview

```text
                                     +----------------------+
                                     | SSM SecureString     |
                                     | API-Football Pro key |
                                     +----------+-----------+
                                                |
                         +----------------------+
                         |                      |
                         v                      v
              +-------------------+   +------------------------+
              | FixtureFetcher    |   | LiveFixtureFetcher     |
              | Lambda            |   | Lambda                 |
              | daily 05:00 JST   |   | every 5 minutes        |
              +---------+---------+   +-----------+------------+
                        |                         |
                        +------------+------------+
                                     |
                                     v
                           +--------------------+
                           | API-Football v3    |
                           | /fixtures          |
                           +---------+----------+
                                     |
                  normalize / validate / app schema
                         |                         |
                         v                         v
            +------------------------+   +------------------------+
            | S3 fixture documents   |   | S3 live snapshot       |
            | data/fixtures/*.json   |   | data/fixtures/live.json|
            +-----------+------------+   +-----------+------------+
                        |                            |
                        +-------------+--------------+
                                      |
Nuxt static output --> S3 site bucket |
        |                              |
        +------------------------------+
                                      v
                                +------------+
                                | CloudFront |
                                +------+-----+
                                       |
                                       v
                                    Browser
                           daily docs + LIVE overlay
```

フロントエンドからAPI-Footballを直接呼ばない。APIキーはSSM SecureStringに保存し、Lambdaだけが読む。

## Error alerting overview

```text
FixtureFetcher Lambda                  LiveFixtureFetcher Lambda
        |                                      |
        | structured ERROR                     | structured ERROR
        v                                      v
CloudWatch Log Group                   CloudWatch Log Group
        |                                      |
        | Subscription Filter                  | Subscription Filter
        | $.level = ERROR                      | $.level = ERROR
        +-------------------+------------------+
                            |
                            v
                  +----------------------+
                  | BatchErrorNotifier   |
                  | Lambda               |
                  +----------+-----------+
                             |
                      build fingerprint
                             |
                             v
                  +----------------------+
                  | DynamoDB             |
                  | alert throttle state |
                  +----------+-----------+
                             |
                    conditional claim
                       /           \
                acquired         cooldown
                   |                |
                   v                +--> suppress
              +----------+
              | SNS Topic|
              +----+-----+
                   |
                   v
               Alert email
```

同一エラーfingerprintは初回だけ即通知し、その後6時間は抑止する。別エラーは即通知できる。詳細は [`error-alerting.md`](error-alerting.md) を参照。

## Provider strategy

現在のcompetition mappingは以下。

| App ID | Competition | API-Football league ID |
| --- | --- | ---: |
| `epl` | Premier League | 39 |
| `laliga` | La Liga | 140 |
| `bundesliga` | Bundesliga | 78 |
| `ligue1` | Ligue 1 | 61 |
| `j1` | J1 League | 98 |
| `ucl` | UEFA Champions League | 2 |
| `uel` | UEFA Europa League | 3 |
| `uecl` | UEFA Conference League | 848 |

アプリ側competition IDはprovider IDから独立したstable slugとして扱う。

J1はAPI-Footballが秋春制シーズンを終了年で識別するため、2026年後半の日程は `season=2027` を利用する。

詳細は [`data-source.md`](data-source.md) を参照。

## Daily fixture pipeline

### Schedule

- EventBridge Scheduler: 毎日05:00 JST
- Lambda: `FixtureFetcher`
- runtime: Python 3.13
- timeout: 5分
- credential: SSM `/football-schedule/api-football-pro-key`

### Publication window

- lookback: 1日
- 欧州国内リーグ: 21日先
- UEFA CL / EL / ECL: 35日先
- J1: 100日先

provider側rangeだけを信用せず、normalize後にJST基準で再フィルタする。

### Failure isolation

大会ごとにfetch → normalize → validate → publishする。1大会が失敗しても、成功した大会は更新する。失敗大会のS3 objectは上書きせず、直前の正常JSONを維持する。

## LIVE pipeline

### Schedule and source

- EventBridge Scheduler: 5分ごと
- Lambda: `LiveFixtureFetcher`
- runtime: Python 3.13
- timeout: 1分
- API: `GET /fixtures?live=39-140-78-61-98-2-3-848&timezone=Asia/Tokyo`
- 全8大会を1リクエストで取得
- API request volume: 288 requests/day

### Published object

`data/fixtures/live.json`

```json
{
  "schemaVersion": 1,
  "generatedAt": "2026-09-13T03:40:00Z",
  "expiresAt": "2026-09-13T03:50:00Z",
  "fixtures": [
    {
      "id": "1575165",
      "competitionId": "bundesliga",
      "period": "2H",
      "elapsed": 76,
      "extra": null,
      "score": { "home": 1, "away": 1 },
      "events": []
    }
  ]
}
```

`expiresAt = generatedAt + 10分`。LIVE Lambdaが失敗し続けて古いobjectがS3へ残っても、フロントは期限切れsnapshotを無視する。

### Frontend polling

- 初回表示時: 即取得
- fresh LIVE fixtureが0件: 5分間隔
- fresh LIVE fixtureが1件以上: 1分間隔
- background tab: polling停止
- foreground復帰: 即取得して適切なintervalへ再設定

CloudFront request数を抑えつつ、試合中だけ鮮度を上げる。

詳細は [`live-fixtures.md`](live-fixtures.md) を参照。

## Daily fixture schema

```ts
export type FixtureStatus =
  | 'scheduled'
  | 'live'
  | 'finished'
  | 'postponed'
  | 'cancelled'

export interface FixtureTeam {
  id: string
  name: string
  logo?: string
}

export interface Fixture {
  id: string
  competition: {
    id: string
    name: string
    country: string
  }
  home: FixtureTeam
  away: FixtureTeam
  kickoff: string
  status: FixtureStatus
  score: {
    home: number
    away: number
  } | null
}

export interface FixtureDocument {
  schemaVersion: 1
  competition: {
    id: string
    name: string
    country: string
  }
  generatedAt: string
  range: {
    from: string
    to: string
  }
  fixtures: Fixture[]
}
```

`kickoff` と `generatedAt` はUTC ISO 8601で保存し、画面表示はJSTへ変換する。

## Fixture document validation

S3 publish直前にcompetition documentを検証する。

主な検証項目:

- competition metadata一致
- `schemaVersion = 1`
- `generatedAt` がUTC timestamp
- `range.from <= range.to`
- fixture ID重複なし
- competition ID設定済み
- team ID / team名 consistency
- home / awayが同一でない
- kickoffがUTC timestampかつJST range内
- statusが既知値
- scoreがnullまたは非負整数
- logoが存在する場合HTTP(S)
- fixturesがkickoff / id順にsort済み

validation失敗時はS3へputしない。

## S3 layout

```text
data/
  fixtures/
    premier-league.json
    laliga.json
    bundesliga.json
    ligue1.json
    j1.json
    champions-league.json
    europa-league.json
    conference-league.json
    live.json
```

通常fixtureは大会単位、LIVEは全大会横断snapshotとして分離する。

## DynamoDB

ユーザーデータ用DBは持たない。現在のDynamoDBは**運用通知の重複抑止専用**。

### `BatchErrorAlertStateTable`

| Property | Value |
| --- | --- |
| Partition key | `fingerprint` (String) |
| Sort key | なし |
| Billing mode | PAY_PER_REQUEST |
| TTL attribute | `expiresAt` |
| Removal policy | DESTROY |
| GSI | なし |
| Writer/reader | BatchErrorNotifier Lambda |

Item:

```json
{
  "fingerprint": "<sha256>",
  "lastNotifiedAt": 1789243200,
  "expiresAt": 1789329600
}
```

- notification cooldown: 21,600秒（6時間）
- state TTL: 86,400秒（24時間）
- cooldown判定はTTLではなく `lastNotifiedAt` へのconditional updateで行う
- TTLは古いfingerprint行の自動掃除にのみ利用

詳細は [`error-alerting.md`](error-alerting.md) を参照。

## Frontend state

サーバー側ユーザーデータは持たず、設定はlocalStorageへ保存する。

```text
football-schedule-competitions
football-schedule-teams
football-schedule-show-results
football-schedule-theme
```

日本人選手所属チーム情報はフロント側metadataで管理する。

## AWS stacks

### HostingStack

- Nuxt static output用S3 bucket
- Fixture JSON用S3 data bucket
- CloudFront distribution
- Origin Access Control
- GitHub Actions OIDC deploy role

S3はpublic accessをblockし、CloudFront OAC経由で配信する。CloudFrontはAWS Managed Cache Policyを利用し、Free Planで使える構成を維持する。

### DataStack

- `FixtureFetcher` Lambda
- `LiveFixtureFetcher` Lambda
- 各Lambda専用CloudWatch Log Group
- EventBridge Scheduler（日次 / 5分LIVE）
- API-Football credentialのSSM参照
- S3 fixture data write権限
- CloudWatch Logs Subscription Filter × 2
- `BatchErrorNotifier` Lambda
- `BatchErrorAlertStateTable` DynamoDB
- batch error用SNS Topic
- SNS email subscription（`BATCH_ALERT_EMAIL` 設定時）

## Error notification behavior

1. daily / LIVE Lambdaはstructured JSON logをCloudWatch Logsへ出す
2. `level = ERROR` のみSubscription FilterでNotifierへ送る
3. Notifierがlog group + normalized error identityからSHA-256 fingerprintを生成
4. DynamoDBへconditional updateして通知claimを取る
5. 初回または6時間経過済みならSNS publish
6. cooldown内ならメールを抑止
7. DynamoDB障害時はfail-openでSNS publish
8. SNS publish失敗時はclaimを可能な範囲でreleaseして再試行可能にする

WARN / INFOはメール通知しない。

## Deployment flow

### Frontend

```text
main push
   |
   v
Typecheck / Nuxt generate
   |
   v
S3 site bucket sync
   |
   v
CloudFront invalidation
```

### AWS infrastructure

```text
main push (infra changes)
        |
        v
CDK synth / diff
        |
        v
immutable deployment plan artifact
        |
        +---- Lambda function only ----> auto deploy
        |
        +---- other infra changes -----> GitHub Environment: production
                                          |
                                          v
                                       approval
                                          |
                                          v
                                verify plan/hash/input
                                          |
                                          v
                                      CDK deploy
```

GitHub ActionsからAWSへの認証はOIDCを利用し、長期Access Keyは使わない。

## Security

- API-Football Pro keyはSSM SecureStringで管理
- 外部APIキーをフロントへ渡さない
- FixtureFetcherはfixture data prefixへのput権限
- LiveFixtureFetcherは `data/fixtures/live.json` へのput権限
- BatchErrorNotifierはSNS publish + alert-state DynamoDB read/write権限
- S3 bucketはpublic access block
- CloudFront OAC経由でread
- team logo URLはHTTP(S)のみ許可
- GitHub ActionsはOIDCでAWS roleをassume

## Related docs

- [`data-source.md`](data-source.md): API-Football mapping / publication windows
- [`live-fixtures.md`](live-fixtures.md): LIVE snapshot / polling / expiry
- [`error-alerting.md`](error-alerting.md): DynamoDB throttle / fingerprint / failure policy
- [`api-football-j1-validation.md`](api-football-j1-validation.md): J1 provider検証
- [`product-vision.md`](product-vision.md): product direction
