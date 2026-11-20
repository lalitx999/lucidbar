"""
Project-wide rule checks that run with the normal test suite.

- No emoji in source, templates, static text files or translations.
- No external CDN or remote asset references in templates and static files.
- No inline style attributes (they would be blocked by our CSP).
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

SCANNED_DIRS = ["apps", "config", "templates", "static", "locale", "docker", "tests"]
TEXT_SUFFIXES = {".py", ".html", ".txt", ".css", ".js", ".svg", ".json", ".webmanifest", ".po", ".md", ".sh", ".yml"}
# Third-party files we copy in unchanged are not ours to police.
EXCLUDED_PARTS = {"vendor", "__pycache__"}

# Emoji and pictograph blocks, plus variation selector 16 and the keycap combiner.
EMOJI_RE = re.compile(
    "["
    "\U0001f000-\U0001faff"  # mahjong .. symbols and pictographs extended-A
    "\U00002600-\U000027bf"  # misc symbols, dingbats
    "\U00002b00-\U00002bff"  # arrows and stars often rendered as emoji
    "\U0001f1e6-\U0001f1ff"  # regional indicators (flags)
    "️⃣"
    "]"
)

REMOTE_ASSET_RE = re.compile(r"""(?:src|href)\s*=\s*["']\s*(?:https?:)?//""", re.IGNORECASE)
CSS_REMOTE_RE = re.compile(r"""(?:@import|url\()\s*["']?\s*(?:https?:)?//""", re.IGNORECASE)
INLINE_STYLE_RE = re.compile(r"""\sstyle\s*=\s*["']""", re.IGNORECASE)


def _files(dirs, suffixes):
    for d in dirs:
        base = ROOT / d
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in suffixes and not EXCLUDED_PARTS.intersection(path.parts):
                yield path


def _relative(path):
    return str(path.relative_to(ROOT))


def test_no_emoji_in_project_files():
    offenders = []
    for path in _files(SCANNED_DIRS, TEXT_SUFFIXES):
        if path == Path(__file__).resolve():
            continue  # this file defines the ranges
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if EMOJI_RE.search(line):
                offenders.append(f"{_relative(path)}:{lineno}")
    assert not offenders, "Emoji found (not allowed):\n" + "\n".join(offenders)


def test_no_remote_assets_in_templates_and_static():
    offenders = []
    for path in _files(["templates", "static", "apps"], {".html", ".css", ".js"}):
        text = path.read_text(encoding="utf-8")
        if REMOTE_ASSET_RE.search(text) or CSS_REMOTE_RE.search(text):
            offenders.append(_relative(path))
    assert not offenders, "Remote asset reference found (CDN not allowed):\n" + "\n".join(offenders)


def test_no_inline_style_attributes_in_templates():
    offenders = []
    for path in _files(["templates", "apps"], {".html"}):
        if "emails" in path.parts:
            continue  # email clients need inline styles; the site CSP does not apply to email
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if INLINE_STYLE_RE.search(line):
                offenders.append(f"{_relative(path)}:{lineno}")
    assert not offenders, "Inline style attribute found (blocked by CSP):\n" + "\n".join(offenders)


@pytest.mark.parametrize("sample", ["\U0001f451", "\u2728", "\U0001f1f9\U0001f1ed"])
def test_emoji_pattern_catches_common_emoji(sample):
    assert EMOJI_RE.search(sample)
