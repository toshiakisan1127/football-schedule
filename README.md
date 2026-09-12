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

主な機能:

- 全日程 / 今日 / 明日 / 今週末の切り替え
- 複数リーグの表示フィルター
- 複数のお気に入りチームによる絞り込み
- リーグ・チーム設定のlocalStorage保存
- キックオフ時刻を日本時間（JST）で表示
- live / finished / postponed / cancelled の状態管理
- 試合結果の表示・非表示切り替え
- ライト / ダークテーマ
- 日本人選手所属チームへの 🇯🇵 表示
- チームロゴの表示
- データ最終更新時刻の表示
- PWA

UEFA Champions League、Europa League、Conference League、Serie Aなどを順次追加予定です。

## アーキテクチャ

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
CloudWatch Logs
        |
        | level = ERROR only
        v
Subscription Filter
        |
        v
BatchErrorNotifier Lambda
        |
        v
SNS Topic
        |
        v
Alert email
```

フロントエンドからAPI-Footballを直接呼びません。Lambdaが毎日05:00 JSTに日程を取得し、アプリ独自のJSON形式へ正規化・検証したうえで、リーグごとのJSONをS3へ保存します。ブラウザはCloudFront経由で静的サイトと `data/fixtures/*.json` を読むだけです。

現在の取得範囲は**前日から21日先まで**です。大会ごとに取得・検証・publishするため、ある大会が失敗しても成功した大会は更新できます。失敗した大会は直前の正常なJSONを維持します。

21日先はデータ品質を優先したMVPの上限です。将来30日などへ伸ばす場合は、リーグごとにAPI-Footballの取得結果を公式日程と照合してから変更します。

詳細は [`docs/architecture.md`](docs/architecture.md) と [`docs/data-source.md`](docs/data-source.md) を参照してください。以前のLa Liga / KickoffAPI v2の検証内容は [`docs/kickoffapi-laliga-v2-validation.md`](docs/kickoffapi-laliga-v2-validation.md) に履歴として残しています。

## デプロイ

- フロントエンド: mainへの対象変更でNuxtを静的生成し、Site S3へ同期後CloudFrontをinvalidate
- AWSインフラ: CDK synth / diffを実行し、同じassemblyをimmutableなdeploy artifactとして保存
- Fixture Fetcher Lambdaだけの変更: 自動デプロイ
- それ以外のインフラ変更: GitHub Environment `production` の承認後にデプロイ
- 承認後もdeploy入力が変わっていないこととartifact hashを確認してから実行
- GitHub ActionsからAWSへの認証はOIDCを使用し、長期Access Keyは持たない

### バッチのERRORメール通知

Fixture Fetcher LambdaはJSON形式でCloudWatch Logsへ出力し、`level = ERROR` のログだけをSubscription Filterで通知用Lambdaへ渡します。通知用Lambdaはログ本文をSNS Topicへpublishし、email subscription経由でメール通知します。`WARN` / `INFO` は通知対象外です。

通知先はコードに埋め込まず、GitHubの `Settings > Secrets and variables > Actions > Variables` に repository variable `BATCH_ALERT_EMAIL` を登録します。AWSインフラのCDK synth時にこの値を利用してSNSのemail subscriptionを作成します。初回デプロイ後、AWS Notificationsから届く確認メールの `Confirm subscription` を一度実行してください。

`BATCH_ALERT_EMAIL` が未設定の場合もインフラ自体はデプロイできますが、email subscriptionは作成されないためメール通知は行われません。

## 方針

- DBはMVPでは持たない
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
- Amazon EventBridge Scheduler
- AWS Systems Manager Parameter Store
- GitHub Actions / OIDC
- API-Football v3

## Status

Premier League / La Liga / Bundesliga / Ligue 1 / J1 Leagueの日程取得・公開まで稼働中。機能追加と運用改善を継続しています。
