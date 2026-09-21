"""Plain-text extraction from HTML fragments in JSON APIs (not HTML scraping)."""

from __future__ import annotations

import re
from html.parser import HTMLParser

_WHITESPACE = re.compile(r"\s+")
_SKIP_TAGS = frozenset({"script", "style"})


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        text = data.strip()
        if text:
            self._parts.append(text)

    def text(self) -> str:
        return _WHITESPACE.sub(" ", " ".join(self._parts)).strip()


def html_to_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    text = re.sub(r"<[^>]+>", " ", parser.text())
    return _WHITESPACE.sub(" ", text).strip()
