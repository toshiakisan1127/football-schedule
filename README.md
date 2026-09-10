# football-schedule

サッカーの**試合日程だけ**を、見やすく日本時間で確認するためのWebアプリです。

## コンセプト

> 日本時間で、見たいサッカーの試合時間だけすぐ分かる。

ニュース・順位表を主役にせず、「いつ試合があるか」を素早く確認できることに特化します。試合結果は初期状態では隠し、必要な場合だけ表示できます。

## MVP

まずはKickoffAPI v2で取得できる以下の3大会に絞ります。

- Premier League
- LaLiga
- UEFA Champions League
- 今日 / 明日 / 今週末の切り替え
- 大会フィルター
- お気に入りクラブの保存（localStorage）
- キックオフ時刻を利用者のローカル時刻で表示
- live / finished / postponed / cancelled の状態管理
- 試合結果の表示・非表示切り替え
- データ最終更新時刻の表示

J1はKickoffAPIの2026/27シーズン対応を確認できていないため、一旦MVP対象外です。

## アーキテクチャ

```text
EventBridge Scheduler
        |
        v
      Lambda  -----> KickoffAPI v2
        |
        | normalize / filter
        v
S3 (data/fixtures.json)
        |
        v
   CloudFront
        |
        v
    Nuxt / PWA
```

フロントエンドから外部APIを直接呼びません。Lambdaが定期的に日程を取得し、アプリ独自のJSON形式へ正規化してS3へ保存します。フロントエンドはCloudFront経由で静的JSONを読むだけにします。

詳細は [`docs/architecture.md`](docs/architecture.md) を参照してください。

## 方針

- DBはMVPでは持たない
- APIキーをブラウザへ露出しない
- 外部API障害時は既存の正常なJSONを残す
- 外部API固有のレスポンス形式をフロントへ漏らさない
- 保存時刻はUTC、表示時にローカルタイムへ変換する
- チームロゴ等の権利物はMVPでは依存しない

## Tech Stack

- Nuxt 4 / TypeScript
- AWS CDK / TypeScript
- Amazon S3
- Amazon CloudFront
- AWS Lambda
- Amazon EventBridge Scheduler
- KickoffAPI v2

## Status

MVP設計・初期構築中。
