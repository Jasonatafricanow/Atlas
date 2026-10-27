"""Mechanical credential filtering; logs contain line numbers only."""
import logging
import re

LOG = logging.getLogger(__name__)
MARKER = "[CREDENTIAL]"
PATTERNS = re.compile(
    r"(?:sk-|ghp_|xox[a-z]-)[A-Za-z0-9_-]{8,}"
    r"|AKIA[A-Z0-9]{16}"
    r"|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
    r"|(?i:password\s*=\s*\S+|密码\s*[:：]\s*\S+)"
    r"|(?<![\w])[a-fA-F0-9]{32,}(?![\w])"
    r"|(?<![\w/+])[A-Za-z0-9/+]{40,}={0,2}(?![\w/+])")
PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----.*?"
    r"-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----", re.DOTALL)


def valid_luhn(value):
    if not re.fullmatch(r"[0-9]{13,19}", value) or len(set(value)) == 1:
        return False
    digits = [int(c) for c in value[::-1]]
    return sum(n if i % 2 == 0 else (2 * n - 9 if n > 4 else 2 * n)
               for i, n in enumerate(digits)) % 10 == 0


def valid_identity(value):
    if not re.fullmatch(r"[0-9]{17}[0-9Xx]", value):
        return False
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    return "10X98765432"[sum(int(c) * w for c, w in zip(value, weights)) % 11] == value[-1].upper()


class FilterCounter:
    """Value-free counters, scoped to one ingestion operation."""
    def __init__(self):
        self.lines = 0
        self.documents = 0


def identifier_key(key):
    return key in ("id", "ids") or key.endswith(("_id", "_ids"))


def redact(text, counter=None):
    """Replace affected lines, retaining newlines; never log matched values."""
    affected = set()
    for pattern in (PATTERNS, PRIVATE_KEY):
        for match in pattern.finditer(text):
            affected.update(range(text.count("\n", 0, match.start()),
                                  text.count("\n", 0, match.end()) + 1))
    for match in re.finditer(r"(?<!\w)[0-9]{13,19}[Xx]?(?!\w)", text):
        if valid_luhn(match[0]) or valid_identity(match[0]):
            affected.add(text.count("\n", 0, match.start()))
    lines = text.splitlines(keepends=True)
    for index in sorted(affected):
        ending = "\r\n" if lines[index].endswith("\r\n") else "\n" if lines[index].endswith("\n") else ""
        lines[index] = MARKER + ending
        if counter is None:
            LOG.warning("credential removed at line %d", index + 1)
    if counter is not None:
        counter.lines += len(affected)
    return "".join(lines)


def sanitize(value, counter=None):
    if isinstance(value, str):
        return redact(value, counter)
    if isinstance(value, list):
        return [sanitize(item, counter) for item in value]
    if isinstance(value, dict):
        return {key: item if identifier_key(key) else sanitize(item, counter) for key, item in value.items()}
    return value
