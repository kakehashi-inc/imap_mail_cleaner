"""Regular expression utilities for pattern matching."""

import re
from typing import List, Optional, Sequence, Any, Tuple
from email.message import Message
from email.header import decode_header

from mods.config import CleanupRule
from utils.email import convert_html_to_text


def _compile_patterns(patterns: Optional[Sequence[str]]) -> List[re.Pattern[str]]:
    """Compile a list of regex patterns, skipping invalid ones."""
    compiled: List[re.Pattern[str]] = []
    for pat in _ensure_list(patterns):
        try:
            compiled.append(re.compile(pat, flags=re.IGNORECASE | re.DOTALL))
        except re.error as ex:
            print(f"[WARN] Skipped invalid regex pattern: {pat!r} ({ex})")
    return compiled


def _match_all(patterns: List[re.Pattern[str]], value: str) -> bool:
    """Check if all patterns match the given value."""
    for pat in patterns:
        if not pat.search(value):
            return False
    return True


def rule_matches_message(
    rule: CleanupRule,
    subject: str,
    body_text: str,
    body_html: Optional[str],
    from_addr: str,
    to_addr: str,
) -> bool:
    """Check if a cleanup rule matches the given message fields."""
    subject_patterns = (
        _compile_patterns(rule.subject) if rule.subject is not None else []
    )
    body_patterns = _compile_patterns(rule.body) if rule.body is not None else []
    from_patterns = (
        _compile_patterns(rule.from_addr) if rule.from_addr is not None else []
    )
    to_patterns = _compile_patterns(rule.to_addr) if rule.to_addr is not None else []

    # Each field specified must satisfy ALL of its patterns
    if subject_patterns and not _match_all(subject_patterns, subject):
        return False
    if body_patterns:
        # Check both text and HTML content for body patterns
        body_text_matches = _match_all(body_patterns, body_text)
        body_html_matches = body_html is not None and _match_all(
            body_patterns, body_html
        )
        if not (body_text_matches or body_html_matches):
            return False
    if from_patterns and not _match_all(from_patterns, from_addr):
        return False
    if to_patterns and not _match_all(to_patterns, to_addr):
        return False
    return True


def _ensure_list(value: Any) -> List[str]:
    """Convert value to a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def _decode_header_value(raw_value: Optional[str]) -> str:
    """Decode email header value, handling encoding properly."""
    if not raw_value:
        return ""
    try:
        decoded_parts = decode_header(raw_value)
        fragments: List[str] = []
        for part, enc in decoded_parts:
            if isinstance(part, bytes):
                try:
                    fragments.append(part.decode(enc or "utf-8", errors="replace"))
                except Exception:
                    fragments.append(part.decode("utf-8", errors="replace"))
            else:
                fragments.append(part)
        return "".join(fragments)
    except Exception:
        # Fallback: return raw
        return raw_value


def _extract_text_and_html_from_email(msg: Message) -> Tuple[str, Optional[str]]:
    """Return both text and HTML content from an email message.

    Returns:
        Tuple of (text_content, html_content_as_text)
        html_content_as_text is None if no HTML parts found
    """
    try:
        if msg.is_multipart():
            plain_text_candidates: List[str] = []
            html_text_candidates: List[str] = []
            for part in msg.walk():
                content_type = (part.get_content_type() or "").lower()
                content_disposition = (part.get("Content-Disposition") or "").lower()
                if "attachment" in content_disposition:
                    continue
                part_payload_bytes: Optional[bytes] = None
                try:
                    maybe_bytes = part.get_payload(decode=True)
                except Exception:
                    maybe_bytes = None
                if isinstance(maybe_bytes, (bytes, bytearray)):
                    part_payload_bytes = bytes(maybe_bytes)
                else:
                    part_payload_bytes = None
                if not part_payload_bytes:
                    continue
                charset = part.get_content_charset() or "utf-8"
                try:
                    text_content = part_payload_bytes.decode(charset, errors="replace")
                except Exception:
                    text_content = part_payload_bytes.decode("utf-8", errors="replace")

                if content_type == "text/plain":
                    plain_text_candidates.append(text_content)
                elif content_type == "text/html":
                    try:
                        html_text_candidates.append(convert_html_to_text(text_content))
                    except Exception:
                        html_text_candidates.append(text_content)

            text_result = (
                "\n\n".join(plain_text_candidates).strip()
                if plain_text_candidates
                else ""
            )
            html_result = (
                "\n\n".join(html_text_candidates).strip()
                if html_text_candidates
                else None
            )

            return text_result, html_result

        # not multipart
        content_type = (msg.get_content_type() or "").lower()
        payload_bytes: Optional[bytes] = None
        try:
            maybe_bytes = msg.get_payload(decode=True)
        except Exception:
            maybe_bytes = None
        if isinstance(maybe_bytes, (bytes, bytearray)):
            payload_bytes = bytes(maybe_bytes)
        else:
            payload_bytes = None
        if payload_bytes is None:
            payload_any = msg.get_payload()
            payload_str = payload_any if isinstance(payload_any, str) else ""

            # payload may be already str
            if content_type == "text/html":
                try:
                    html_as_text = convert_html_to_text(payload_str)
                    return "", html_as_text
                except Exception:
                    return "", payload_str

            return str(payload_str), None

        charset = msg.get_content_charset() or "utf-8"
        try:
            text_content = payload_bytes.decode(charset, errors="replace")
        except Exception:
            text_content = payload_bytes.decode("utf-8", errors="replace")
        if content_type == "text/html":
            try:
                html_as_text = convert_html_to_text(text_content)
                return "", html_as_text
            except Exception:
                return "", text_content

        return text_content, None
    except Exception:
        return "", None


def message_fields(msg: Message) -> Tuple[str, str, str, str, Optional[str]]:
    """Extract subject, from, to, body text and body html from a message."""
    subject = _decode_header_value(msg.get("Subject"))
    from_addr = _decode_header_value(msg.get("From"))
    to_addr = _decode_header_value(msg.get("To"))
    body_text, body_html = _extract_text_and_html_from_email(msg)
    return subject, from_addr, to_addr, body_text, body_html
