r"""
IMAP mailbox cleaner.

機能:
- config.json に基づき IMAP サーバへ接続し、各 mailbox のメールをルール判定 (正規表現) で抽出
- 既定の action は delete。"trash" 指定時は Trash へ移動
- --interactive/-I 指定時は実行前に件名と本文の一部を表示し確認、d で全文表示

注意:
- 本スクリプトは IMAP の RFC822 メッセージを取得してローカルで正規表現判定します
- Trash への移動は COPY → \\Deleted フラグ付与 → EXPUNGE で実現します (MOVE 拡張は未使用)
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from typing import Optional, Sequence
from datetime import datetime, timedelta, timezone

import imaplib

from mods.config import AccountConfig, load_accounts_from_config
from mods.imap_client import ImapClient
from utils.imap_utils import message_fields, rule_matches_message


# ------------------------------
# Actions and UI
# ------------------------------


class ProcessingCanceled(Exception):
    """ユーザーが対話モードで処理中断 (cancel) を選んだことを示す例外。"""


def _short_snippet(text: str, max_chars: int = 200) -> str:
    """Create a short snippet of text for display."""
    t = text.strip().replace("\r\n", "\n").replace("\r", "\n")
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 3] + "..."


def _interactive_confirm(subject: str, body_text: str, action: str) -> str:
    print("\n--- Target Email ---")
    print(f"Subject: {subject}")
    print("Body (preview):")
    print(_short_snippet(body_text))
    while True:
        if action.lower() == "trash":
            question = "Move to trash?"
        else:
            question = "Delete?"
        choice = (
            input(f"{question} (y:yes, n:no, d:show full body, c:cancel) > ")
            .strip()
            .lower()
        )
        if choice == "y":
            return "yes"
        if choice == "n":
            return "no"
        if choice == "d":
            print("--- Body (full) ---")
            print(body_text)
            continue
        if choice == "c":
            return "cancel"
        print("Please enter y / n / d / c")


def _apply_action_for_message(
    imap: ImapClient,
    uid: str,
    action: str,
    trash_mailbox: Optional[str],
    subject: str,
    body_text: str,
    interactive: bool,
) -> str:
    # trash の場合は trash_mailbox が必須
    if action == "trash":
        if not trash_mailbox:
            print(f"[INFO] Skip: Trash mailbox not found, subject: {subject}")
            return "skip"

    if interactive:
        decision = _interactive_confirm(subject, body_text, action)
        if decision == "no":
            return "skip"
        if decision == "cancel":
            raise ProcessingCanceled()

    if action == "trash" and trash_mailbox:
        copied = imap.copy_to_mailbox(uid, trash_mailbox)
        if not copied:
            print(
                f'[WARN] Failed to copy to Trash ("{trash_mailbox}"). Skipping this message.'
            )
            return "error"

        # delete original
        if imap.mark_deleted(uid):
            return "trash"
        else:
            return "error"

    # default: delete
    if imap.mark_deleted(uid):
        return "delete"
    else:
        return "error"


def process_account(
    account: AccountConfig, interactive: bool, skip_days: int = 30
) -> None:
    print(f"==== Account: {account.name} ====")

    # skip_days が 0 より大きい場合、カットオフ日時を計算
    cutoff_date: Optional[datetime] = None
    if skip_days > 0:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=skip_days)
        print(
            f"[INFO] Excluding emails received within {skip_days} days (after {cutoff_date.strftime('%Y-%m-%d %H:%M:%S %Z')})"
        )
    else:
        print("[INFO] All emails are targeted")

    try:
        with ImapClient(account.server) as client:
            client.connect()

            # Trash 特定を最初に実施
            trash_mailbox = client.find_trash_mailbox()
            if not trash_mailbox:
                print("[WARN] Could not detect Trash mailbox.")

            for cleanup in account.cleanups:
                for requested_mailbox in cleanup.mailboxes:
                    if not client.mailbox_exists(requested_mailbox):
                        print(f"[WARN] Mailbox not found: {requested_mailbox}")
                        continue
                    print(f"-- Mailbox: {requested_mailbox}")
                    if not client.select_mailbox(requested_mailbox):
                        print(f"[WARN] Failed to select mailbox: {requested_mailbox}")
                        continue

                        # 大量件数対応: UID をチャンク列挙しながら逐次処理
                    uid_iter = client.iter_all_uids()
                    counts = {"delete": 0, "trash": 0, "skip": 0, "error": 0}
                    total_checked = 0

                    for uid in uid_iter:
                        total_checked += 1

                        # skip_days が指定されている場合、受信日時をチェック
                        if cutoff_date is not None:
                            msg_date = client.fetch_message_date(uid)
                            if msg_date is not None:
                                # タイムゾーン情報がない場合はUTCとして扱う
                                if msg_date.tzinfo is None:
                                    msg_date = msg_date.replace(tzinfo=timezone.utc)
                                else:
                                    # UTCに変換して比較
                                    msg_date = msg_date.astimezone(timezone.utc)

                                # カットオフ日時より新しいメールはスキップ
                                if msg_date > cutoff_date:
                                    continue

                        msg = client.fetch_message_rfc822(uid)
                        if msg is None:
                            print(
                                f"\r[SKIP] UID:{uid} (fetch failed)", end="", flush=True
                            )
                            continue
                        subject, from_addr, to_addr, body_text, body_html = (
                            message_fields(msg)
                        )

                        # コンソール幅に合わせて件名を短縮（80文字程度）
                        short_subject = (
                            subject[:60] + "..." if len(subject) > 60 else subject
                        )

                        # ルールを順次評価。最初にマッチしたルールの action を適用
                        chosen_action: Optional[str] = None
                        for rule in cleanup.rules:
                            if rule_matches_message(
                                rule,
                                subject,
                                body_text,
                                body_html,
                                from_addr,
                                to_addr,
                            ):
                                chosen_action = rule.action or "delete"
                                break

                        if not chosen_action:
                            # 対象外メール
                            print(
                                f"\r[SKIP] UID:{uid} {short_subject}",
                                end="",
                                flush=True,
                            )
                            continue

                        # 対象メールが見つかった場合は行をクリアしてから処理
                        print("\r" + " " * 80, end="", flush=True)  # 行をクリア

                        result = _apply_action_for_message(
                            imap=client,
                            uid=uid,
                            action=chosen_action,
                            trash_mailbox=trash_mailbox,
                            subject=subject,
                            body_text=body_text,
                            interactive=interactive,
                        )
                        counts[result] += 1

                        # 結果を表示
                        if result == "trash":
                            print(f"\r[TRASH] UID:{uid} {short_subject}")
                        elif result == "delete":
                            print(f"\r[DELETE] UID:{uid} {short_subject}")
                        elif result == "skip":
                            print(f"\r[SKIP] UID:{uid} {short_subject}")
                        elif result == "error":
                            print(f"\r[ERROR] UID:{uid} {short_subject}")

                    # 最終行をクリア
                    print("\r" + " " * 80, end="", flush=True)
                    print("\r", end="")

                    if total_checked == 0:
                        print("[INFO] No target emails found.")

                    # mailbox 単位で expunge（削除・移動が1件以上の時のみ）
                    total_actions = counts["delete"] + counts["trash"]
                    if total_actions > 0:
                        client.expunge()

                    # 内訳を表示
                    print(
                        f"[INFO] Total checked: {total_checked}, Deleted: {counts['delete']}, Moved to trash: {counts['trash']}, Skipped: {counts['skip']}, Errors: {counts['error']}"
                    )
    except ImapClient.MailboxesUnavailable as e:
        print(f"[ERROR] {e}")
        return


# ------------------------------
# CLI
# ------------------------------


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IMAP Mail Cleaner")
    parser.add_argument(
        "-C",
        "--config",
        dest="config",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
        help="Path to config file (default: config.json in script directory)",
    )
    parser.add_argument(
        "--force",
        dest="force",
        action="store_true",
        help="Execute without confirmation (default: confirmation before delete/move)",
    )
    parser.add_argument(
        "--skip-days",
        dest="skip_days",
        type=int,
        default=30,
        help="Exclude emails received within specified days (default: 30, 0 for all emails)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    config_path = args.config
    interactive: bool = not bool(args.force)  # --force指定時はnon-interactive
    skip_days: int = args.skip_days

    if not os.path.exists(config_path):
        print(f"[ERROR] Config file not found: {config_path}")
        return 2

    try:
        accounts = load_accounts_from_config(config_path)
    except Exception as ex:
        print(f"[ERROR] Failed to load config: {ex}")
        return 2

    if not accounts:
        print("[WARN] No valid account settings found. Exiting.")
        return 0

    for account in accounts:
        try:
            process_account(account, interactive=interactive, skip_days=skip_days)
        except ProcessingCanceled:
            print("[INFO] Processing canceled by user.")
            return 0
        except imaplib.IMAP4.error as ex:
            print(f"[ERROR] IMAP error: {ex}")
        except Exception:
            print("[ERROR] Unexpected error occurred")
            traceback.print_exc()
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
