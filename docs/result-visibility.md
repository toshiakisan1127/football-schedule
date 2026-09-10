# Score visibility policy

- APIレスポンスから途中経過を含むスコアを `score` としてJSONに保持する。
- `status: live` の試合は、フロントではスコアを表示せず「試合中」チップだけ表示する。
- `status: finished` の試合だけ、ユーザーが「結果を表示」をONにした場合にスコアを表示する。
- 結果表示の設定はlocalStorageに保存し、デフォルトは非表示とする。
