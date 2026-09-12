# football-schedule

サッカーの**試合日程だけ**を、見やすく日本時間で確認するためのWebアプリです。

## CI

mainブランチで直近に完了したWorkflowの実行時間です。Workflow完了時に自動更新されます。

<!-- ci-duration-lambda:start -->
- **Lambda tests:** ✅ **37s** · [run #21](https://github.com/toshiakisan1127/football-schedule/actions/runs/34523418424) · 2026-09-11 04:57 JST
<!-- ci-duration-lambda:end -->
<!-- ci-duration-deploy:start -->
- **Deploy AWS infrastructure:** ✅ **2m 52s** · [run #12](https://github.com/toshiakisan1127/football-schedule/actions/runs/34523418427) · 2026-09-11 05:00 JST
<!-- ci-duration-deploy:end -->

### Performance history

直近30回までの成功したmainブランチ実行時間を可視化しています。対象Workflow完了時に自動更新されます。

![CI performance history](https://raw.githubusercontent.com/toshiakisan1127/football-schedule/ci-metrics/ci-performance.svg)

## コンセプト

> 日本時間で、見たいサッカーの試合時間だけすぐ分かる。

ニュース・順位表を主役にせず、「いつ試合があるか」を素早く確認できることに特化します。試合結果は初期状態では隠し、必要な場合だけ表示できます。

プロダクトとしての差別化方針と今後の方向性は [`docs/product-vision.md`](docs/product-vision.md) にまとめています。

## 現在の対応範囲

現在は以下の大会を有効化しています。

- Premier League
- La Liga
- Bundesliga
- Ligue 1
- J1 League
- UEFA Champions League
- UEFA Europa League
- UEFA Conference League

主な機能:

- 全日程 / 今日 / 明日 / 今週末 / 今から見る
- 複数リーグの表示フィルター
- 複数のお気に入りチームによる絞り込み
- リーグ・チーム設定のlocalStorage保存
- キックオフ時刻を日本時間（JST）で表示
- 試合結果の表示・非表示切り替え
- LIVEスコア / 経過時間 / ゴール・カード・交代イベント
- ライト / ダークテーマ
- 日本人選手所属チームへの 🇯🇵 表示 / 絞り込み
- チームロゴの表示
- データ最終更新時刻の表示
- PWA

Serie Aなどを順次追加予定です。

## アーキテクチャ

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
                        normalize / validate
                         |                         |
                         v                         v
            +------------------------+   +------------------------+
            | S3 daily fixtures      |   | S3 live.json           |
            | data/fixtures/*.json   |   | expiresAt +10 min      |
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
```

フロントエンドからAPI-Footballを直接呼びません。LambdaがAPI-Footballを取得し、アプリ独自JSONへ正規化・検証したうえでS3へ保存します。ブラウザはCloudFront経由で静的サイトとfixture JSONを読むだけです。

日次fixtureは毎日05:00 JST更新。取得rangeはPremier League / La Liga / Bundesliga / Ligue 1が前日〜21日先、CL / EL / ECLが前日〜35日先、J1が前日〜100日先です。

LIVEは別Lambdaで5分ごとに8大会を1リクエストで取得し、`data/fixtures/live.json` へ公開します。snapshotには `expiresAt = generatedAt + 10分` を持たせ、Lambda障害で古いobjectが残ってもフロントが期限切れLIVEを表示し続けないようにしています。

フロント側のLIVE pollingは、LIVEなしなら5分、LIVEありなら1分、background中は停止、foreground復帰時は即取得です。

詳細:

- [`docs/architecture.md`](docs/architecture.md): 全体構成 / AWS resource / S3 / DynamoDB / failure handling
- [`docs/data-source.md`](docs/data-source.md): provider mapping / lookahead / publication contract
- [`docs/live-fixtures.md`](docs/live-fixtures.md): LIVE snapshot / polling / expiry
- [`docs/error-alerting.md`](docs/error-alerting.md): ERROR通知 / DynamoDB throttle / fingerprint / TTL

## ERRORメール通知

日次FixtureFetcherとLiveFixtureFetcherはstructured JSON logをCloudWatch Logsへ出力し、`level = ERROR` のログだけをSubscription Filterで `BatchErrorNotifier` Lambdaへ渡します。

```text
FixtureFetcher / LiveFixtureFetcher
             |
             v
       CloudWatch Logs
             |
      ERROR only filter
             v
     BatchErrorNotifier
             |
      fingerprint生成
             v
   DynamoDB alert state
       /           \
  notify          suppress
     |
     v
    SNS
     |
     v
   email
```

同一エラーfingerprintは**初回即通知、その後6時間は抑止**します。別エラーは即通知できます。DynamoDBは通知重複抑止専用で、ユーザーデータは保存しません。

### DynamoDB alert-state table

`DataStack` の `BatchErrorAlertStateTable`:

| Property | Value |
| --- | --- |
| Partition key | `fingerprint` (String) |
| Billing | PAY_PER_REQUEST |
| TTL | `expiresAt` |
| Cooldown | 6時間 |
| State TTL | 24時間 |
| Removal policy | DESTROY |

Itemは `fingerprint`, `lastNotifiedAt`, `expiresAt` の3項目です。6時間cooldownは `lastNotifiedAt` に対するconditional writeで制御し、DynamoDB TTLは古い状態の自動削除に使います。

DynamoDBへのアクセスに失敗した場合は**fail-open**で通知を送ります。通知抑止基盤の障害によって本来の障害メールを落とさないためです。

通知先はコードに埋め込まず、GitHubの `Settings > Secrets and variables > Actions > Variables` に repository variable `BATCH_ALERT_EMAIL` を登録します。初回デプロイ後、AWS Notificationsから届く確認メールの `Confirm subscription` を一度実行してください。

`BATCH_ALERT_EMAIL` が未設定の場合もインフラ自体はデプロイできますが、email subscriptionは作成されません。

## デプロイ

- フロントエンド: mainへの対象変更でNuxtを静的生成し、Site S3へ同期後CloudFrontをinvalidate
- AWSインフラ: CDK synth / diffを実行し、同じassemblyをimmutableなdeploy artifactとして保存
- Fixture Lambdaだけの変更: 自動デプロイ
- それ以外のインフラ変更: GitHub Environment `production` の承認後にデプロイ
- 承認後もdeploy入力が変わっていないこととartifact hashを確認してから実行
- GitHub ActionsからAWSへの認証はOIDCを使用し、長期Access Keyは持たない

## 方針

- ユーザーデータ用DBはMVPでは持たない
- DynamoDBは運用通知の重複抑止だけに利用する
- APIキーをブラウザへ露出しない
- 外部API障害時は対象大会の既存の正常なJSONを残す
- 外部API固有のレスポンス形式をフロントへ漏らさない
- `schemaVersion` 付きのJSON契約をLambdaで検証してから公開する
- 保存時刻はUTC、日程のwindow判定と画面表示はJSTで行う
- S3 bucketは非公開とし、CloudFront Origin Access Control経由で配信する
- CloudFrontはAWS Managed Cache Policyを利用し、Free Planで使える構成を維持する
- チームロゴは静的マッピングを優先し、providerレスポンスも利用するが、欠損補完のための追加API呼び出しはしない
- 日本人選手情報はフロント側の明示的なメタデータとして管理する

## Tech Stack

- Nuxt 4 / Vue 3 / TypeScript
- Tailwind CSS 4
- AWS CDK / TypeScript
- Python 3.13
- Amazon S3
- Amazon CloudFront
- AWS Lambda
- Amazon CloudWatch Logs
- Amazon SNS
- Amazon DynamoDB
- Amazon EventBridge Scheduler
- AWS Systems Manager Parameter Store
- GitHub Actions / OIDC
- API-Football v3

## Status

Premier League / La Liga / Bundesliga / Ligue 1 / J1 League / UEFA Champions League / UEFA Europa League / UEFA Conference Leagueの日程取得・公開とLIVE表示に対応。機能追加と運用改善を継続しています。
