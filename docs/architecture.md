# Architecture

## Goal

サッカーの日程情報だけを、利用者が素早く確認できることを最優先にする。

## Scope

### In scope

- Premier League
- La Liga
- 直近の日程表示
- 大会フィルター
- 複数チームのフィルター
- 日本人選手所属チームの 🇯🇵 表示
- providerから取得できるチームロゴ表示
- live / finished / postponed / cancelled の状態管理
- 試合結果の表示・非表示切り替え
- ライト / ダークテーマ
- 最終更新時刻表示

UEFA Champions Leagueは次の追加対象。J1はKickoffAPIで2026シーズンの取得を確認できていないため、一旦対象外とする。

### Out of scope

- 順位表
- ニュース
- 選手詳細
- ログイン
- サーバーサイドのユーザーDB
- Push通知

## System overview

```text
                         +----------------------+
                         | SSM SecureString     |
                         | KickoffAPI API key   |
                         +----------+-----------+
                                    |
EventBridge Scheduler               v
(rate 6 hours / ENABLED) --> Fixture Fetcher Lambda
                                    |
                     +--------------+--------------+
                     |                             |
                     v                             v
          Premier League / v1           La Liga / v2
                                             |
                                  cursor pagination
                                  canonical selection
                     |                             |
                     +--------------+--------------+
                                    |
                                    | normalize
                                    | JST window filter
                                    | document validation
                                    v
                         S3 data bucket
                         data/fixtures.json
                                    |
                                    +----------+
                                               |
Nuxt static output --> S3 site bucket          |
        |                                      |
        +------------------+-------------------+
                           v
                       CloudFront
                           |
                           v
                        Browser
```

フロントエンドから外部APIを直接呼ばない。provider差分はFixture Fetcher Lambda内に閉じ込め、フロントはアプリ独自のfixture contractだけを扱う。

## Provider strategy

### Premier League

- KickoffAPI v1を利用
- `from` / `to` をproviderへ渡す
- providerレスポンスを共通schemaへ正規化する

### La Liga

- KickoffAPI v2を利用
- cursor paginationで取得する
- v2で返る重複候補から、検証済みの `Europe/Madrid` wall-clock sibling ruleでcanonical rowを選ぶ
- relevantな候補を一意に解決できない場合はfail closedとし、その実行ではS3を更新しない

詳細は [`data-source.md`](data-source.md) と [`kickoffapi-laliga-v2-validation.md`](kickoffapi-laliga-v2-validation.md) を参照する。

## Normalized fixture schema

外部APIのレスポンスを直接フロントへ渡さず、Lambdaで以下の形へ正規化する。

```ts
export type FixtureStatus = 'scheduled' | 'live' | 'finished' | 'postponed' | 'cancelled'

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
  generatedAt: string
  range: {
    from: string
    to: string
  }
  fixtures: Fixture[]
}
```

`kickoff` と `generatedAt` はUTCのISO 8601で保存する。取得windowの最終判定と画面表示はJSTで行う。

アプリ側のcompetition id（`epl` / `laliga`）はprovider IDから独立させる。

`logo` はproviderレスポンスに `logo` / `image` / `crest` が存在する場合だけ保持するoptional field。HTTP(S) URLだけを許可し、ロゴが無い場合に別APIを叩いて補完はしない。

## Fixture document validation

S3へ公開する直前に `schemaVersion = 1` のdocument全体を検証する。

主な検証項目:

- `generatedAt` がUTC timestampであること
- `range.from <= range.to`
- fixture IDが重複していないこと
- competition IDが設定済みであること
- 同じteam IDがdocument内で複数のteam名へ変化していないこと
- home / awayが同一チームではないこと
- kickoffがUTC timestampで、JST換算後にdocument range内であること
- statusが既知の値であること
- scoreがnullまたは非負整数であること
- logoが存在する場合はHTTP(S) URLであること
- fixturesがkickoff / id順にsort済みであること

検証に失敗した場合はS3へputせず、直前の正常な `fixtures.json` を保持する。

## S3 layout

MVPでは単一ファイルで配信する。

```text
data/
  fixtures.json
```

試合数や転送量が問題になった場合のみ、日付・大会単位への分割を検討する。

## Refresh strategy

- EventBridge Schedulerから6時間おきにLambdaを実行する
- Schedulerは `ENABLED`
- Lambda runtimeはPython 3.13
- Lambda timeoutは5分
- 公開対象はJST基準で前日から30日先まで
- Premier League v1には `from` / `to` を渡す
- La Liga v2はcursorで取得し、Lambda側のJST windowを最終境界とする
- 全対象大会の取得・provider固有検証・document validationが成功した場合のみS3を更新する
- `data/fixtures.json` は `Cache-Control: public, max-age=300` で保存する

## Frontend state

サーバー側のユーザーデータは持たず、ユーザー設定はlocalStorageへ保存する。

```text
football-schedule-competitions
football-schedule-teams
football-schedule-show-results
football-schedule-theme
```

日本人選手所属チームの情報は `app/data/japanesePlayers.ts` で明示的に管理し、team名のaliasを正規化して照合する。

## AWS stacks

### HostingStack

- Nuxt static output用S3 bucket
- Fixture JSON用S3 bucket
- CloudFront distribution
- Origin Access Control
- GitHub Actions用OIDC deploy role

S3 bucketはpublic accessをblockし、CloudFront OAC経由だけで配信する。

CloudFrontはサイトと `data/*` の両方でAWS Managed `CACHING_OPTIMIZED` policyを利用する。独自Cache Policyは持たず、PriceClassも明示しないことでCloudFront Free Planと両立する構成にする。

### DataStack

- Fixture Fetcher Lambda
- EventBridge Scheduler
- KickoffAPI credentialのSSM参照
- fixture data bucketへの書き込み権限

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

## Failure handling

1. 外部APIの取得に失敗した場合は公開JSONを更新しない
2. La Liga v2のcanonical rowを一意に選択できない場合も更新しない
3. 共通fixture documentのvalidationに失敗した場合も更新しない
4. Lambdaは失敗をCloudWatch Logsへ残す
5. フロントは `generatedAt` を表示し、データ鮮度を利用者が判断できるようにする
6. team logoの読み込みに失敗した場合、フロントでは画像だけを非表示にしてteam名は維持する

## Security

- KickoffAPI keyはSSM SecureString `/football-schedule/kickoff-api-key` で管理する
- 外部APIキーはフロントへ渡さない
- Fixture Fetcher Lambdaだけにfixture data bucketへのput権限を付与する
- S3 bucketはpublic accessをblockする
- CloudFront OACから読み取る
- team logo URLは公開前validationでHTTP(S)だけ許可する
- GitHub ActionsはOIDCでAWS roleをassumeする

## Future ideas

- UEFA Champions League
- J1 / J2 / J3 / カップ戦 / 代表戦
- 欧州他リーグ / Europa League
- お気に入りだけのホーム画面
- カレンダー追加（ICS）
- PWA
- 通知
- 試合の放送・配信先情報
