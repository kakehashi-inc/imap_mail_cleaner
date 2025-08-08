# IMAP Mail Cleaner

Small utility to delete or move to Trash emails in IMAP mailboxes based on regex rules.

## Features

- Scan specified mailboxes
- Regex filters on subject/body/from/to with AND logic (within a field and across fields)
- Actions: default delete; set `action: "trash"` to move to Trash
- Interactive mode (`-I/--interactive`): y=yes, n=no, d=show full body, c=cancel and exit

## Requirements

- Python 3.9+
- Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

```bash
python imap_mail_cleaner.py [-C CONFIG] [-I]

Options:
  -C, --config       Path to config file (default: config.json next to the script)
  -I, --interactive  Per-message confirmation (y=yes, n=no, d=full body, c=cancel)
```

## Config format (`config.json`)

Top-level keys are account names. Each account has `server` and `cleanup`.

```json
{
  "account-name": {
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

Notes:

- `mailbox` may be a string or array; processed in order.
- Fields `subject`, `body`, `from`, `to` accept a regex string or an array of regex strings. All patterns in a field must match (AND), and fields are ANDed as well.
- Default `action` is `delete`. With `trash`, messages are moved to the Trash mailbox. If Trash cannot be detected or COPY fails, the message is skipped (not deleted).
- Trash detection is done once per account, prioritizing special-use `\\Trash`, then common names (`Trash`, `Deleted Items`, etc.).

## Safety

- Deletions are irreversible. Use `-I/--interactive` first.
- Trash move uses COPY → add `\\Deleted` → EXPUNGE (no MOVE extension).

## License

MIT
