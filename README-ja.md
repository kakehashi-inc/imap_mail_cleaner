# IMAP Mail Cleaner

正規表現ルールに基づいて IMAP メールボックスのメールを削除またはゴミ箱へ移動するユーティリティです。

## 機能

- 指定した mailbox を走査
- 件名/本文/From/To を正規表現で AND 判定可能（各フィールド内は AND、複数フィールド間も AND）
- アクションは既定で delete、`action: "trash"` でゴミ箱へ移動
- デフォルトで対話モード（実行前に確認）、`--force` で確認なし実行

## 必要要件

- Python 3.9+
- 依存関係のインストール:

```bash
pip install -r requirements.txt
```

## 使い方

```bash
python imap_mail_cleaner.py [-C CONFIG] [--force] [--skip-days DAYS]

オプション:
  -C, --config       コンフィグファイルのパス（省略時: スクリプトと同じディレクトリの config.json）
  --force           確認なしで実行（省略時: 削除/移動前に確認）
  --skip-days DAYS  指定した日数以内に受信したメールを除外する
                    （デフォルト: 30日、0ですべてのメールを対象）

対話モード（デフォルト）での操作:
  y: はい（実行）
  n: いいえ（スキップ）
  d: 全文表示
  c: 処理中断・正常終了
```

## コンフィグ仕様（`config.json`）

トップレベルのキーがアカウント名です。各アカウントは `server` と `cleanup` を持ちます。

```json
{
  "アカウント名": {
    "server": {
      "host": "imap.example.com",
      "port": 993,
      "tls": false,
      "ssl": true,
      "username": "user@example.com",
      "password": "password"
    },
    "cleanup": [
      {
        "mailbox": ["INBOX", "INBOX.Sub"],
        "rules": [
          {"subject": ".*Undelivered.*Mail.*"},
          {"body": ["spam-token", "another-token"], "action": "trash"}
        ]
      }
    ]
  }
}
```

注意点:

- `mailbox` は文字列または配列。複数指定時は順番に処理されます。
- `subject`/`body`/`from`/`to` は文字列（正規表現）または配列（配列内は AND 条件）。複数フィールドを併用した場合も AND です。
- `body` ルールは text/plain と text/html の両方をチェックし、いずれかにマッチすれば対象となります。
- `action` 省略時は `delete`。`trash` の場合はゴミ箱へ移動します。ゴミ箱を特定できない、または COPY に失敗した場合はスキップ（削除しない）します。
- ゴミ箱の特定はアカウントごとに最初に実施し、special-use の `\\Trash`、一般的名称（`Trash`, `Deleted Items` 等）の順で判定します。

## 安全性と注意

- 削除は元に戻せません。まずはデフォルトの対話モードで挙動を確認してください。

## ライセンス

MIT
