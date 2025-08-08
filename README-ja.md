# IMAP Mail Cleaner

正規表現ルールに基づいて IMAP メールボックスのメールを削除またはゴミ箱へ移動するユーティリティです。

## 機能

- 指定した mailbox を走査
- 件名/本文/From/To を正規表現で AND 判定可能（各フィールド内は AND、複数フィールド間も AND）
- アクションは既定で delete、`action: "trash"` でゴミ箱へ移動
- 対話モード（`-I/--interactive`）で実行前に確認（y=はい, n=いいえ, d=全文表示, c=中断）

## 必要要件

- Python 3.9+
- 依存関係のインストール:

```bash
pip install -r requirements.txt
```

## 使い方

```bash
python imap_mail_cleaner.py [-C CONFIG] [-I]

オプション:
  -C, --config       コンフィグファイルのパス（省略時: スクリプトと同じディレクトリの config.json）
  -I, --interactive  1件ごとに確認（y=はい, n=いいえ, d=全文表示, c=処理中断・正常終了）
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
- `action` 省略時は `delete`。`trash` の場合はゴミ箱へ移動します。ゴミ箱を特定できない、または COPY に失敗した場合はスキップ（削除しない）します。
- ゴミ箱の特定はアカウントごとに最初に実施し、special-use の `\\Trash`、一般的名称（`Trash`, `Deleted Items` 等）の順で判定します。

## 安全性と注意

- 削除は元に戻せません。まずは `-I/--interactive` を使用して挙動を確認してください。
- ゴミ箱移動は COPY → `\\Deleted` 付与 → EXPUNGE で実現しています（MOVE 拡張は未使用）。

## ライセンス

MIT
