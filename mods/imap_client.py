from __future__ import annotations

import imaplib
import re
from typing import Iterable, List, Optional, Sequence, Tuple
import email
from email import policy
from email.message import Message

from mods.config import ServerConfig


class ImapClient:
    class MailboxesUnavailable(Exception):
        pass

    def __init__(self, server: Optional[ServerConfig] = None) -> None:
        self.server: Optional[ServerConfig] = server
        self.conn: Optional[imaplib.IMAP4] = None
        self._mailboxes_cache: List[Tuple[str, str, str]] = []
        self._selected_mailbox: Optional[str] = None
        self._trash_mailbox_cache: Optional[str] = None

    def __enter__(self) -> "ImapClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.disconnect()

    def connect(self) -> None:
        if self.server is None:
            raise ValueError("Server configuration is required before connect().")
        if self.server.ssl:
            self.conn = imaplib.IMAP4_SSL(self.server.host, self.server.port)
        else:
            self.conn = imaplib.IMAP4(self.server.host, self.server.port)
            if self.server.tls:
                self.conn.starttls()
        assert self.conn is not None
        self.conn.login(self.server.username, self.server.password)
        self._load_all_mailboxes()
        if not self._mailboxes_cache:
            raise ImapClient.MailboxesUnavailable(
                "メールボックス一覧を取得できませんでした"
            )

    def disconnect(self) -> None:
        try:
            if self.conn is not None:
                try:
                    self.conn.logout()
                except Exception:
                    pass
        finally:
            self.conn = None

    def _load_all_mailboxes(self) -> None:
        assert self.conn is not None
        list_data: List[object] = []
        try:
            status, data = self.conn.list()
            if status == "OK":
                list_data.extend(data or [])
        except Exception:
            pass
        try:
            status, data = self.conn.lsub()
            if status == "OK":
                list_data.extend(data or [])
        except Exception:
            pass
        self._mailboxes_cache = self._build_mailbox_cache_from_list_data(list_data)

    def _build_mailbox_cache_from_list_data(
        self, list_data: Sequence[object]
    ) -> List[Tuple[str, str, str]]:
        entries: List[Tuple[str, str, str]] = []
        regex = re.compile(
            r"^(?:\*\s+(?:LIST|LSUB)\s+)?\((?P<flags>[^)]*)\)\s+"
            r"(?:\"(?P<delim_q>[^\"]*)\"|(?P<delim_atom>[^\s]+))\s+"
            r"(?:\"(?P<name_q>[^\"]*)\"|(?P<name_atom>[^\s]+))\s*$",
            re.ASCII,
        )
        for raw in list_data:
            if raw is None:
                continue
            if isinstance(raw, (bytes, bytearray)):
                line = bytes(raw).decode("utf-8", errors="replace")
            elif isinstance(raw, tuple):
                parts: List[bytes] = []
                for seg in raw:
                    if isinstance(seg, (bytes, bytearray)):
                        parts.append(bytes(seg))
                    else:
                        parts.append(str(seg).encode("utf-8", errors="ignore"))
                line = b" ".join(parts).decode("utf-8", errors="replace")
            else:
                line = str(raw)
            m = regex.match(line.strip())
            if not m:
                continue
            flags = (m.group("flags") or "").strip()
            delim = (
                m.group("delim_q")
                if m.group("delim_q") is not None
                else m.group("delim_atom") or "/"
            )
            if delim.upper() == "NIL":
                delim = "/"
            name = (
                m.group("name_q")
                if m.group("name_q") is not None
                else m.group("name_atom") or ""
            )
            if not name or name in {".", "/"} or name == delim:
                continue
            entries.append((flags, delim or "/", name))
        seen: set[str] = set()
        result: List[Tuple[str, str, str]] = []
        for flags, delim, name in entries:
            if name in seen:
                continue
            seen.add(name)
            result.append((flags, delim, name))
        return result

    def select_mailbox(self, mailbox: str) -> bool:
        assert self.conn is not None
        status, _ = self.conn.select(mailbox)
        if status == "OK":
            self._selected_mailbox = mailbox
            return True
        return False

    def find_trash_mailbox(self) -> Optional[str]:
        if self._trash_mailbox_cache is not None:
            return self._trash_mailbox_cache
        mailboxes = self._mailboxes_cache

        def is_valid(delim: str, name: str) -> bool:
            return bool(name) and name not in {".", "/"} and name != delim

        for flags, delim, name in mailboxes:
            try:
                if "\\trash" in flags.lower() and is_valid(delim, name):
                    self._trash_mailbox_cache = name
                    return name
            except Exception:
                continue
        common = [
            "Trash",
            "INBOX.Trash",
            "INBOX/Trash",
            "Deleted Items",
            "Deleted Messages",
            "[Gmail]/Trash",
            "ゴミ箱",
            "ごみ箱",
        ]
        existing = {(d, n) for _, d, n in mailboxes}
        for cn in common:
            for delim, name in existing:
                if name == cn and is_valid(delim, name):
                    self._trash_mailbox_cache = name
                    return name
        for _, delim, name in mailboxes:
            if "trash" in name.lower() and is_valid(delim, name):
                self._trash_mailbox_cache = name
                return name
        self._trash_mailbox_cache = None
        return None

    def mailbox_exists(self, requested: str) -> bool:
        names = [name for _, _, name in self._mailboxes_cache]
        return requested in names

    def _get_uidnext_for_selected(self) -> Optional[int]:
        assert self.conn is not None
        if not self._selected_mailbox:
            return None
        try:
            typ, data = self.conn.status(self._selected_mailbox, "(UIDNEXT)")
            if typ != "OK" or not data:
                return None
            first = data[0]
            text = (
                first.decode(errors="replace")
                if isinstance(first, (bytes, bytearray))
                else str(first)
            )
            m = re.search(r"UIDNEXT\s+(\d+)", text)
            if m:
                return int(m.group(1))
        except Exception:
            return None
        return None

    def iter_all_uids(self, chunk_size: int = 5000) -> Iterable[str]:
        assert self.conn is not None
        uidnext = self._get_uidnext_for_selected()
        if uidnext and uidnext > 1:
            start = 1
            while start < uidnext:
                end = min(start + chunk_size - 1, uidnext - 1)
                try:
                    typ, data = self.conn.uid("SEARCH", "UID", f"{start}:{end}")
                except Exception:
                    data = None
                    typ = "NO"
                if typ == "OK" and data:
                    first = data[0]
                    text = (
                        first.decode(errors="replace")
                        if isinstance(first, (bytes, bytearray))
                        else str(first)
                    )
                    for uid in text.split():
                        if uid:
                            yield uid
                start = end + 1
            return
        try:
            typ, data = self.conn.uid("SEARCH", "ALL")
            if typ == "OK" and data and data[0]:
                first = data[0]
                text = (
                    first.decode(errors="replace")
                    if isinstance(first, (bytes, bytearray))
                    else str(first)
                )
                for uid in text.split():
                    if uid:
                        yield uid
        except Exception:
            return

    def fetch_message_rfc822(self, uid: str) -> Optional[Message]:
        assert self.conn is not None
        typ, data = self.conn.uid("FETCH", uid, "(RFC822)")
        if typ != "OK" or not data:
            return None
        for item in data:
            if isinstance(item, tuple) and len(item) >= 2:
                seq = list(item)
                second = seq[1]
                if isinstance(second, (bytes, bytearray)):
                    raw_bytes = bytes(second)
                    try:
                        return email.message_from_bytes(
                            raw_bytes, policy=policy.default
                        )
                    except Exception:
                        return email.message_from_bytes(raw_bytes)
        return None

    def copy_to_mailbox(self, uid: str, mailbox: str) -> bool:
        assert self.conn is not None
        quoted = f'"{mailbox}"'
        typ, _ = self.conn.uid("COPY", uid, quoted)
        return typ == "OK"

    def mark_deleted(self, uid: str) -> bool:
        assert self.conn is not None
        typ, _ = self.conn.uid("STORE", uid, "+FLAGS.SILENT", "(\\Deleted)")
        return typ == "OK"

    def expunge(self) -> None:
        assert self.conn is not None
        try:
            self.conn.expunge()
        except Exception:
            pass
