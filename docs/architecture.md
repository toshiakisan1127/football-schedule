# Architecture

## Goal

サッカーの日程情報だけを、利用者が素早く確認できることを最優先にする。

## Scope

### In scope

- Premier League
- La Liga
- Bundesliga
- Ligue 1
- J1 League
- 直近の日程表示
- 大会フィルター
- 複数チームのフィルター
- 日本人選手所属チームの 🇯🇵 表示
- providerまたは静的マッピングから取得できるチームロゴ表示
- live / finished / postponed / cancelled の状態管理
- 試合結果の表示・非表示切り替え
- ライト / ダークテーマ
- 最終更新時刻表示
- PWA

UEFA Champions League、Europa League、Conference League、Serie A などは順次追加対象。

### Out of scope

- 順位表
- ニュース
- 選手詳細
- ログイン
- サーバーサイドのユーザーDB
- 試合開始などのPush通知

## System overview

```text
                                      +----------------------+
                                      | SSM SecureString     |
                                      | API-Football API key |
                                      +----------+-----------+
                                                 |
                                                 v
+----------------------+              +-----------------------+
| EventBridge Scheduler|------------->| Fixture Fetcher Lambda|
| daily 05:00 JST      |              +-----------+-----------+
+----------------------+                          |
                                                 v
                                      +-----------------------+
                                      | API-Football v3       |
                                      | /fixtures             |
                                      +-----------+-----------+
                                                  |
                                      normalize / JST filter
                                      per-league validation
                                                  |
                                                  v
                                      +-----------------------+
                                      | S3 data bucket        |
                                      | data/fixtures/*.json  |
                                      +-----------+-----------+
                                                  |
                                                  |
Nuxt static output --> S3 site bucket             |
        |                                         |
        +----------------------+------------------+
                               v
                          +----------+
                          |CloudFront|
                          +----+-----+
                               |
                               v
                            Browser

Fixture Fetcher Lambda
        |
        | structured logs
        v
+----------------------+
| CloudWatch Logs      |
+----------+-----------+
           |
           | level = ERROR only
           v
+----------------------+
| Subscription Filter  |
+----------+-----------+
           |
           v
+----------------------+
| BatchErrorNotifier   |
| Lambda               |
+----------+-----------+
           |
           v
+----------------------+
| SNS Topic            |
+----------+-----------+
           |
           v
       Alert email
```

フロントエンドから外部APIを直接呼ばない。provider差分はFixture Fetcher Lambda内に閉じ込め、フロントはアプリ独自のfixture contractだけを扱う。

ERROR通知も取得処理本体から直接メール送信せず、CloudWatch LogsのERRORログをSubscription Filterで拾い、専用LambdaからSNSへ転送する。

## Provider strategy

現在の有効大会はAPI-Football v3へ統一する。

- Premier League: league `39`
- La Liga: league `140`
- Bundesliga: league `78`
- Ligue 1: league `61`
- J1 League: league `98`

欧州4リーグは共通の `GET /fixtures` 取得経路を使う。J1のみ、秋春制シーズンの識別子を終了年で扱うためseason変換を専用処理に閉じ込める。

providerレスポンスをアプリ共通schemaへ正規化し、JSTの公開windowで再フィルタしてから検証・publishする。チームロゴはAPI-Footballのfixtureレスポンスを利用できるため、ロゴ取得専用の追加リクエストは行わない。

移行前の比較結果と21日window採用理由は [`data-source.md`](data-source.md) を参照する。KickoffAPI v2のLa Liga検証は [`kickoffapi-laliga-v2-validation.md`](kickoffapi-laliga-v2-validation.md) に履歴として残す。

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

`kickoff` と `generatedAt` はUTCのISO 8601で保存する。取得windowの最終判定と画面表示はJSTで行う。

アプリ側のcompetition idはprovider IDから独立させる。

`logo` は静的マッピングを優先し、利用できない場合はproviderレスポンスの `logo` / `image` / `crest` を利用する。HTTP(S) URLだけを許可し、ロゴ補完だけのために追加APIリクエストは行わない。

## Fixture document validation

S3へ公開する直前に、リーグごとの `schemaVersion = 1` documentを検証する。

主な検証項目:

- rootのcompetition metadataが対象リーグと一致すること
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

検証に失敗したリーグはS3へputせず、そのリーグの直前の正常なJSONを保持する。他リーグの更新は独立して継続できる。

## S3 layout

fixture JSONはリーグ単位で分割して配信する。

```text
data/
  fixtures/
    premier-league.json
    laliga.json
    bundesliga.json
    ligue1.json
    j1.json
```

新しい大会を追加する場合も同じprefix配下に1大会1ファイルで追加する。

## Refresh strategy

- EventBridge Schedulerから毎日05:00 JSTにLambdaを実行する
- Schedulerは `ENABLED`
- Lambda runtimeはPython 3.13
- Lambda timeoutは5分
- 公開対象はJST基準で前日から21日先まで
- Scheduler実行では全対象大会を更新する
- 手動実行ではeventの `competitions` で対象大会を限定できる
- 大会ごとに取得・正規化・validation・S3 publishを行う
- 1大会が失敗しても、成功した大会のJSONは更新できる

21日先はMVPのデータ品質を優先した上限とする。30日などへ延長する場合は、リーグごとにAPI-Footballの対象rangeを取得し、公式日程と対戦カード・UTC kickoffを照合してから変更する。

## Frontend state

サーバー側のユーザーデータは持たず、ユーザー設定はlocalStorageへ保存する。

```text
football-schedule-competitions
football-schedule-teams
football-schedule-show-results
football-schedule-theme
```

日本人選手所属チームの情報はフロント側で明示的に管理し、team名のaliasを正規化して照合する。

## AWS stacks

### HostingStack

- Nuxt static output用S3 bucket
- Fixture JSON用S3 bucket
- CloudFront distribution
- Origin Access Control
- GitHub Actions用OIDC deploy role

S3 bucketはpublic accessをblockし、CloudFront OAC経由だけで配信する。

CloudFrontはサイトと `data/*` の両方でAWS Managed cache policyを利用し、CloudFront Free Planと両立する構成にする。

### DataStack

- Fixture Fetcher Lambda
- Fixture Fetcher専用CloudWatch Log Group
- EventBridge Scheduler
- API-Football credentialのSSM参照
- fixture data bucketへの書き込み権限
- CloudWatch Logs Subscription Filter（`level = ERROR`）
- BatchErrorNotifier Lambda
- batch error用SNS Topic
- SNS email subscription（`BATCH_ALERT_EMAIL` が設定されている場合）

`BATCH_ALERT_EMAIL` はGitHub Actionsのrepository variableからCDK deploy時に渡す。SNS email subscriptionは初回のみ受信者側でconfirmationが必要。

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

1. 外部APIの取得に失敗した大会は、その大会の公開JSONを更新しない
2. fixtureの正規化またはfixture documentのvalidationに失敗した場合も対象大会を更新しない
3. 成功した他大会の更新は継続する
4. Fixture Fetcherは処理状況をstructured logでCloudWatch Logsへ出力する
5. `level = ERROR` のログだけをSubscription FilterでBatchErrorNotifierへ転送する
6. BatchErrorNotifierはSNSへpublishし、購読済みメールアドレスへ通知する
7. WARN / INFOはメール通知しない
8. フロントはリーグごとの `generatedAt` をもとに最終更新時刻を表示する
9. team logoの読み込みに失敗した場合、フロントでは画像だけを非表示にしてteam名は維持する

## Security

- API-Football keyはSSM SecureString `/football-schedule/api-football-pro-key` で管理する
- 外部APIキーはフロントへ渡さない
- Fixture Fetcher Lambdaだけにfixture data bucketへのput権限を付与する
- BatchErrorNotifier LambdaにはSNS Topicへのpublish権限だけを付与する
- S3 bucketはpublic accessをblockする
- CloudFront OACから読み取る
- team logo URLは公開前validationでHTTP(S)だけ許可する
- GitHub ActionsはOIDCでAWS roleをassumeする

## Future ideas

- UEFA Champions League / Europa League / Conference League
- Serie A
- J2 / J3 / カップ戦 / 代表戦
- お気に入りだけのホーム画面
- カレンダー追加（ICS）
- 試合開始・お気に入り試合のPush通知
- 試合の放送・配信先情報
- fixture JSONの鮮度監視
