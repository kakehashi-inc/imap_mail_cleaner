# IMAP Mail Cleaner - AI Coding Agent Instructions

## Project Overview
A Python CLI utility that connects to IMAP mailboxes and deletes/moves emails to trash based on regex pattern matching rules. The tool supports interactive confirmation mode by default and provides batch processing with `--force`.

## Agent Workflow Principles

### Context Gathering Strategy
- **Start broad, then focus**: Use parallel searches to discover relevant code areas quickly
- **Early stop criteria**: Act when you can name exact content to change or when top hits converge (~70%) on one area
- **Avoid over-searching**: If signals conflict, run one refined parallel batch, then proceed
- **Trace selectively**: Only follow symbols you'll modify or whose contracts you rely on

### Self-Reflection Before Acting
1. Think deeply about what makes a world-class solution for the task
2. Create an internal rubric with 5-7 categories for quality assessment
3. Iterate internally until the solution hits top marks across all categories
4. Do not show the rubric to users - use it for internal validation only

### Persistence & Autonomy
- Keep going until the query is completely resolved before yielding to the user
- Never stop when encountering uncertainty - research or deduce the most reasonable approach
- Don't ask for confirmation or clarification - decide on the most reasonable assumption, proceed, and document it after completion
- Only terminate when you're sure the problem is solved

## Architecture

### Core Components
- **`imap_mail_cleaner.py`**: Main entry point with CLI parsing, interactive UI, and orchestration logic
- **`mods/config.py`**: Configuration loading from JSON with dataclass models (`ServerConfig`, `CleanupRule`, `MailboxCleanup`, `AccountConfig`)
- **`mods/imap_client.py`**: IMAP connection wrapper (`ImapClient`) handling connection lifecycle, mailbox operations, and UID-based message fetching
- **`utils/imap_utils.py`**: Regex pattern compilation and message field matching logic
- **`utils/email.py`**: HTML-to-text conversion using `inscriptis` with custom link handling

### Data Flow
1. Load `config.json` → parse into `AccountConfig` objects (multiple accounts supported)
2. For each account: connect via `ImapClient` → detect Trash mailbox once per account
3. For each cleanup rule: iterate mailboxes → fetch UIDs in chunks (5000 default) → fetch RFC822 messages
4. Extract fields (subject/from/to/body-text/body-html) → apply regex AND logic across all specified fields
5. First matching rule wins → execute action (`delete` or `trash`) with optional interactive confirmation
6. Batch expunge after processing each mailbox (if any messages were acted upon)

## Configuration Schema

**`config.json`** structure (see README.md for full examples):
```json
{
  "account-name": {
    "server": { "host": "...", "port": 993, "ssl": true, "username": "...", "password": "..." },
    "cleanup": [
      {
        "mailbox": ["INBOX", "INBOX.Sub"],  // string or array
        "rules": [
          { "subject": ".*spam.*", "action": "delete" },
          { "body": ["token1", "token2"], "from": ".*@evil.com", "action": "trash" }
        ]
      }
    ]
  }
}
```

### Key Conventions
- **Field matching**: Each field (`subject`, `body`, `from`, `to`) accepts a string or array of regex patterns. All patterns within a field must match (AND), and all specified fields must match (AND).
- **Body matching**: Checks both `text/plain` and `text/html` content; matching either counts as a match. HTML is converted to text via `inscriptis`.
- **Action types**: `"delete"` (default, immediate expunge) or `"trash"` (COPY to detected Trash mailbox → mark deleted → expunge).
- **Trash detection**: Prioritizes special-use `\\Trash` flag, then common names (`Trash`, `INBOX.Trash`, `Deleted Items`, `[Gmail]/Trash`, `ゴミ箱`), then any mailbox containing "trash" (case-insensitive). Detected once per account at connection time.

## Development Workflows

### Running the Tool
```bash
# Interactive mode (default, prompts before each action)
python imap_mail_cleaner.py -C config.json

# Batch mode (no confirmation)
python imap_mail_cleaner.py --force

# Debug in VS Code
# Use the "Python Debugger" launch config in .vscode/launch.json
# Pre-configured with --config argument
```

### Interactive Mode Controls
- `y`: Execute action (delete/trash)
- `n`: Skip this message
- `d`: Display full email body
- `c`: Cancel and exit cleanly (raises `ProcessingCanceled`)

### Environment Setup
```bash
# Python 3.9+ required
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt  # Only dependency: inscriptis
```

### Type Checking
- Project uses Pyright with `pyrightconfig.json` configured for `venv`
- All modules use `from __future__ import annotations` for forward references
- Type hints are comprehensive; maintain strict typing when editing

## Critical Implementation Details

### UID Chunking for Scalability
`ImapClient.iter_all_uids()` queries UIDs in 5000-message chunks to avoid timeouts on large mailboxes. Uses `UIDNEXT` to determine range, falls back to `SEARCH ALL` if unavailable.

### Expunge Timing
`expunge()` is called **once per mailbox** after processing all messages (only if `delete` or `trash` actions occurred). This batches deletions for efficiency.

### Error Handling Patterns
- Invalid regex patterns: Logged as `[WARN]` and skipped, not fatal
- Trash COPY failures: Message is skipped (not deleted), logged as `[WARN]`
- Mailbox selection failures: Logged and skipped to next mailbox
- IMAP errors during account processing: Caught at account level, doesn't abort other accounts

### UI Output Conventions
- Progress messages use `\r` with space padding (80 chars) to overwrite current line
- Final summary format: `[INFO] チェック総数: X, 削除: Y, ごみ箱移動: Z, スキップ: W, エラー: E`
- Subject is truncated to 60 chars in progress output to fit terminal width

## Testing & Debugging

### Manual Testing Checklist
1. Test with `config.json` containing test account credentials
2. Verify interactive mode shows correct subject/body snippets
3. Confirm `--force` skips all prompts
4. Test Trash detection with various IMAP servers (Gmail, Office365, generic)
5. Validate regex AND logic with multi-field rules
6. Test HTML email handling (ensure `inscriptis` converts links properly)

### Common Debugging Scenarios
- **Connection issues**: Check `server.ssl`, `server.tls`, `server.port` in config
- **Mailbox not found**: IMAP uses server-specific delimiters (`.` or `/`); verify exact mailbox names with `LIST` command
- **Regex not matching**: Use `d` in interactive mode to view full body; HTML may differ from plain text
- **Trash move fails**: Check if server supports COPY command; some servers require special-use flags

## Code Style & Patterns

### Guiding Principles
- **Readability**: For code including comments, avoid environment-dependent characters, emojis, or non-standard character strings
- **Maintainability**: Follow proper directory structure, maintain consistent naming conventions, organize shared logic appropriately
- **Consistency**: Maintain consistent patterns across the codebase - configuration parsing, error handling, logging formats

### Import Organization
Standard library → third-party (`imaplib`, `email`, `inscriptis`) → local modules (`mods.`, `utils.`)

### Dataclass Usage
All configuration models use `@dataclass` with explicit type hints. Use `_ensure_list()` helper to normalize string/array fields.

### Context Managers
`ImapClient` implements `__enter__`/`__exit__` for automatic connection cleanup. Always use `with ImapClient(...) as client:`.

### Japanese Language Support
- UI messages, docstrings, and error messages use Japanese (日本語)
- README files provided in both English and Japanese (`README.md`, `README-ja.md`)
- Maintain bilingual documentation when adding features
- Code comments can be in English for clarity, but user-facing text must be in Japanese

## Integration Points

### External Dependencies
- **`inscriptis`**: HTML-to-text conversion with custom `<a>` tag handling (preserves links as `[text](url)`)
- **`imaplib`** (stdlib): Direct IMAP4/IMAP4_SSL usage; no higher-level abstractions

### IMAP Protocol Specifics
- Uses UID-based operations (`uid SEARCH`, `uid FETCH`, `uid COPY`, `uid STORE`)
- Mailbox selection required before operations (`SELECT` command)
- Deletion is two-step: mark with `\\Deleted` flag → `EXPUNGE` to finalize

## When Modifying

### Adding New Rule Fields
1. Add field to `CleanupRule` dataclass in `mods/config.py`
2. Update `build_rules()` to parse new field from JSON
3. Modify `rule_matches_message()` in `utils/imap_utils.py` to handle matching
4. Extract field in `message_fields()` or `_extract_text_and_html_from_email()` as needed
5. Update README.md examples and schema documentation

### Adding New Actions
1. Add action type to `CleanupRule.action` validation in `mods/config.py`
2. Implement action logic in `_apply_action_for_message()` in main script
3. Update interactive confirmation prompt text
4. Add action counter to result tracking dict
5. Document in README.md config notes

### Performance Optimization
- Current chunk size: 5000 UIDs per SEARCH. Adjust `chunk_size` in `iter_all_uids()` if needed
- Message fetching is sequential (not parallel) to avoid IMAP connection issues
- Consider adding `BODY.PEEK[]` instead of `RFC822` if reducing server load is critical

## Agent-Specific Guidelines

### When Implementing New Features
1. **Discovery phase**: Use parallel semantic searches to understand existing patterns
2. **Design phase**: Create internal rubric for feature quality (don't show to user)
3. **Implementation phase**: Write code following existing patterns, maintain type hints
4. **Validation phase**: Test with both interactive and `--force` modes
5. **Documentation phase**: Update both README.md and README-ja.md

### When Fixing Bugs
1. Search for similar error handling patterns in the codebase
2. Maintain the existing error message format (`[WARN]`, `[ERROR]`, `[INFO]`)
3. Ensure exceptions don't abort processing of other accounts/mailboxes
4. Test with edge cases (empty mailboxes, network failures, invalid regex)

### When Refactoring
1. Preserve the dataclass-based configuration model
2. Maintain backward compatibility with existing `config.json` files
3. Keep the UID-based IMAP operations pattern
4. Don't change Japanese UI messages without explicit request
5. Update type hints if modifying function signatures
