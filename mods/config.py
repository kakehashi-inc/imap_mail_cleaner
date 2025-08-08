from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Sequence


def _ensure_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


@dataclass
class ServerConfig:
    host: str
    port: int
    tls: bool
    ssl: bool
    username: str
    password: str


@dataclass
class CleanupRule:
    subject: Optional[Sequence[str]] = None
    body: Optional[Sequence[str]] = None
    from_addr: Optional[Sequence[str]] = None
    to_addr: Optional[Sequence[str]] = None
    action: str = "delete"


@dataclass
class MailboxCleanup:
    mailboxes: List[str]
    rules: List[CleanupRule]


@dataclass
class AccountConfig:
    name: str
    server: ServerConfig
    cleanups: List[MailboxCleanup]


def build_rules(rule_dicts: Sequence[Mapping[str, Any]]) -> List[CleanupRule]:
    rules: List[CleanupRule] = []
    for rd in rule_dicts:
        subject = _ensure_list(rd.get("subject")) if "subject" in rd else None
        body = _ensure_list(rd.get("body")) if "body" in rd else None
        from_v = _ensure_list(rd.get("from")) if "from" in rd else None
        to_v = _ensure_list(rd.get("to")) if "to" in rd else None
        action = str(rd.get("action", "delete")).lower().strip() or "delete"
        rules.append(
            CleanupRule(
                subject=subject,
                body=body,
                from_addr=from_v,
                to_addr=to_v,
                action=action,
            )
        )
    return rules


def load_accounts_from_config(config_path: str) -> List[AccountConfig]:
    with open(config_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError("config.json のトップレベルはオブジェクトである必要があります")
    accounts: List[AccountConfig] = []
    for name, conf in raw.items():
        server_conf = conf.get("server", {})
        cleanup_conf = conf.get("cleanup", [])
        if not server_conf:
            # skip invalid entry
            continue
        server = ServerConfig(
            host=str(server_conf.get("host", "")),
            port=int(server_conf.get("port", 993)),
            tls=bool(server_conf.get("tls", False)),
            ssl=bool(server_conf.get("ssl", True)),
            username=str(server_conf.get("username", "")),
            password=str(server_conf.get("password", "")),
        )
        cleanups: List[MailboxCleanup] = []
        for cc in cleanup_conf:
            mbox_value = cc.get("mailbox")
            mailboxes = _ensure_list(mbox_value)
            rules = build_rules(cc.get("rules", []))
            cleanups.append(MailboxCleanup(mailboxes=mailboxes, rules=rules))
        accounts.append(AccountConfig(name=name, server=server, cleanups=cleanups))
    return accounts
