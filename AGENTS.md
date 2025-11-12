# IMAP Mail Cleaner - Autonomous Agent Guidelines

このドキュメントは、自律的なAIコーディングエージェントがこのプロジェクトで効果的にタスクを実行するための指針です。

## エージェント実行の原則

### 1. コンテキスト収集戦略

**目標**: 必要十分なコンテキストを素早く収集し、すぐに行動に移す

**方法**:
- 広範囲から開始し、並列クエリで焦点を絞る
- トップヒットの70%が1つの領域に収束したら収集を停止
- 過度な検索を避ける - シグナルが競合する場合は1回の精緻化バッチを実行後、実行に移る
- 変更する予定のシンボルか、依存する契約のみを追跡する

**早期停止基準**:
- 変更すべき正確なコンテンツを特定できた
- 検索結果が1つの領域/パスに収束した（約70%）

**深さの制御**:
- 変更するシンボルまたは依存する契約のみをトレース
- 必要でない限り、推移的な拡張は避ける

### 2. 自己省察と品質保証

実装前に以下を実行：

1. **ルーブリック作成**: タスクに対する世界クラスの解決策の条件を深く考え、5-7カテゴリの評価基準を作成（ユーザーには見せない）
2. **内部反復**: すべてのカテゴリで最高評価になるまで内部で解決策を反復改善
3. **最終確認**: ルーブリックのすべての項目で高評価を得られるまで開始しない

### 3. 自律性と粘り強さ

- **完全解決まで継続**: ユーザーに戻る前に、クエリを完全に解決する
- **不確実性での継続**: 不確実性に遭遇しても停止しない - 最も合理的なアプローチを調査または推論して継続
- **確認を求めない**: 仮定について人間に確認や明確化を求めない - 最も合理的な仮定を決定し、それで進め、完了後に文書化
- **確実な解決時のみ終了**: 問題が解決されたと確信した時のみターンを終了

## プロジェクト固有の実装パターン

### アーキテクチャ理解の必須ポイント

1. **データフロー**: `config.json` → `AccountConfig` → `ImapClient` → UID反復 → メッセージフェッチ → ルールマッチング → アクション実行
2. **UIDベース操作**: すべてのIMAP操作はUIDベースで実行（`uid SEARCH`, `uid FETCH`, `uid COPY`, `uid STORE`）
3. **チャンク処理**: 大規模メールボックス対応のため、5000 UIDごとにチャンク分割して処理
4. **バッチExpunge**: メールボックスごとに1回だけexpungeを実行（効率化のため）

### コーディング規約の厳守

```python
# 必須: future annotations import
from __future__ import annotations

# 必須: 型ヒントの完全性
def function_name(param: str, optional: Optional[int] = None) -> Tuple[str, bool]:
    ...

# 必須: dataclass使用
@dataclass
class ConfigModel:
    field: str
    optional_field: Optional[int] = None

# 必須: コンテキストマネージャー使用
with ImapClient(server_config) as client:
    client.connect()
    # 処理

# エラーハンドリング: 個別アカウント/メールボックスのエラーは全体を停止しない
try:
    process_account(account)
except ImapClient.MailboxesUnavailable as e:
    print(f"[ERROR] {e}")
    return  # このアカウントのみスキップ
```

### 言語使用の原則

**日本語を使用する箇所**:
- ユーザー向けメッセージ（`print()`, `input()` プロンプト）
- エラーメッセージ（`[INFO]`, `[WARN]`, `[ERROR]`）
- Docstring（モジュール、関数、クラスの説明）
- README.md / README-ja.md の日本語版

**英語を使用する箇所**:
- コード内コメント（明確性のため）
- 変数名、関数名、クラス名
- 型ヒント

**絶対に避けるべき**:
- 環境依存文字（特定のOSでのみ表示可能な文字）
- 絵文字
- 非標準文字列

## タスク別実行ガイド

### 新機能追加時

**Phase 1: Discovery（並列実行）**
```
- semantic_search: 類似機能の実装パターン
- grep_search: 設定スキーマのパターン
- read_file: 関連する既存コードの詳細
```

**Phase 2: Design（内部）**
- 品質ルーブリック作成（表示しない）
- 既存パターンとの整合性確認
- 後方互換性の確保計画

**Phase 3: Implementation**
```python
# 1. mods/config.py: データモデル追加
@dataclass
class CleanupRule:
    # 新フィールド追加
    new_field: Optional[Sequence[str]] = None

# 2. mods/config.py: パース処理追加
def build_rules(rule_dicts):
    new_field = _ensure_list(rd.get("new_field")) if "new_field" in rd else None

# 3. utils/imap_utils.py: マッチングロジック追加
def rule_matches_message(...):
    if rule.new_field:
        # マッチング処理

# 4. テスト: 対話モードと--forceモードの両方
```

**Phase 4: Documentation**
- README.md: 英語ドキュメント更新
- README-ja.md: 日本語ドキュメント更新
- config.jsonスキーマ例の追加

### バグ修正時

**Phase 1: Diagnosis**
```
- grep_search: エラーメッセージパターンの検索
- semantic_search: 類似エラーハンドリング
- read_file: 問題の特定箇所と周辺コード
```

**Phase 2: Root Cause Analysis**
- エラーが発生する条件の特定
- 既存のエラーハンドリングパターンとの比較
- 影響範囲の確認（他のアカウント/メールボックスへの影響）

**Phase 3: Fix Implementation**
- 既存のエラーメッセージ形式を維持（`[WARN]`, `[ERROR]`, `[INFO]`）
- 例外が他のアカウント/メールボックス処理を中断しないことを確認
- 型ヒントの更新

**Phase 4: Edge Case Testing**
- 空のメールボックス
- ネットワーク障害
- 無効な正規表現
- Trash検出失敗

### リファクタリング時

**絶対に守るべき原則**:
1. `config.json`との後方互換性維持
2. dataclass ベースの設定モデル保持
3. UID ベースの IMAP 操作パターン維持
4. 日本語UIメッセージの変更は明示的な要求がある場合のみ
5. 型ヒント完全性の維持

**リファクタリング手順**:
```
1. 現在の動作を完全に理解
2. テストシナリオの準備（手動テスト項目リスト）
3. 小さな単位で変更を実施
4. 各変更後に動作確認
5. 型チェック（Pyright）の実行
```

## デバッグ戦略

### VS Code デバッガー使用
```json
// .vscode/launch.json に設定済み
{
  "name": "Python Debugger",
  "program": "${workspaceFolder}/imap_mail_cleaner.py",
  "args": ["--config", "${workspaceFolder}/config.json"]
}
```

### ログ出力パターン
```python
# 進行状況: \r で上書き、80文字でパディング
print(f"\r[SKIP] UID:{uid} {short_subject}", end="", flush=True)

# 確定情報: 改行付き
print(f"[INFO] チェック総数: {total}")

# 警告: 処理継続
print(f"[WARN] Trash メールボックスが特定できませんでした。")

# エラー: そのアカウント/メールボックスをスキップ
print(f"[ERROR] IMAP エラー: {ex}")
```

### よくある問題と解決策

| 問題 | 原因 | 解決策 |
|------|------|--------|
| 接続失敗 | SSL/TLS/ポート設定 | `server.ssl`, `server.tls`, `server.port`を確認 |
| メールボックス未検出 | 区切り文字の違い | `.` と `/` の両方を試す、`LIST`コマンドで確認 |
| 正規表現不一致 | HTML vs テキスト | 対話モード `d` で全文表示、両方の形式を確認 |
| Trash移動失敗 | COPYコマンド非対応 | サーバーのIMAPコマンド対応状況を確認 |
| タイムアウト | 大量メッセージ | `chunk_size`を調整（デフォルト5000） |

## パフォーマンス最適化指針

### 現在の実装
- **チャンクサイズ**: 5000 UID/検索
- **フェッチ方法**: RFC822（全メッセージ）
- **処理方法**: シーケンシャル（並列なし）

### 最適化検討時
```python
# チャンクサイズ調整
def iter_all_uids(self, chunk_size: int = 5000):  # この値を調整

# 軽量フェッチへの変更検討
# RFC822 → BODY.PEEK[] (サーバー負荷軽減)
typ, data = self.conn.uid("FETCH", uid, "(BODY.PEEK[])")
```

### 最適化してはいけないもの
- IMAP接続の並列化（接続問題を引き起こす）
- Expungeの頻度増加（効率低下）
- エラーハンドリングの簡略化（堅牢性低下）

## セキュリティとベストプラクティス

### 認証情報管理
```json
// config.json には平文パスワードを保存
// 本番環境では:
// 1. ファイルパーミッション制限 (chmod 600)
// 2. 環境変数での置換を検討
// 3. git管理外に配置 (.gitignore)
```

### 安全な削除実行
```python
# デフォルトは対話モード（安全）
python imap_mail_cleaner.py

# --force は慎重に使用
python imap_mail_cleaner.py --force  # 確認なし実行
```

### テスト環境での検証
1. テストアカウントで動作確認
2. 対話モードで件名/本文確認
3. 少数メールで動作確認後、本番実行
4. バックアップまたは復元可能な環境で実施

## 完了チェックリスト

実装完了前に以下を確認：

- [ ] 型ヒントの完全性（Pyright でエラーなし）
- [ ] 日本語UIメッセージの正確性
- [ ] 既存の `config.json` との互換性
- [ ] 対話モード（デフォルト）での動作確認
- [ ] `--force` モードでの動作確認
- [ ] エラーハンドリングの適切性（部分失敗で全体停止しない）
- [ ] README.md と README-ja.md の更新
- [ ] コメントとdocstringの適切性
- [ ] 環境依存文字・絵文字の非使用

## まとめ

**エージェントとして成功するための3つの鍵**:
1. **効率的なコンテキスト収集**: 並列検索で素早く、過度な検索は避ける
2. **高品質な実装**: 内部ルーブリックで品質を保証してから実装
3. **完全な自律性**: 不確実性や障害に直面しても、推論して継続し、完全解決まで実行

このガイドラインに従うことで、エージェントはこのプロジェクトで効果的かつ自律的にタスクを完遂できます。
