"""Clean page text and select relevant passages without an extra model call."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

from ..config import ContentProcessingConfig
from ..models import DocumentChunk, ProcessedDocument, SearchResult, SearchTask


class _TextExtractor(HTMLParser):
    BLOCKS = {"article", "br", "div", "h1", "h2", "h3", "h4", "li", "main", "p", "section", "td", "th", "tr"}
    IGNORED = {"script", "style", "noscript", "svg", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.IGNORED:
            self._ignored_depth += 1
        elif not self._ignored_depth and tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.IGNORED and self._ignored_depth:
            self._ignored_depth -= 1
        elif not self._ignored_depth and tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def clean_content(content: str) -> str:
    if not content:
        return ""
    if re.search(r"<\s*(?:html|body|article|main|p|div|h[1-6])\b", content, re.I):
        parser = _TextExtractor()
        parser.feed(content)
        content = "".join(parser.parts)
    content = html.unescape(content).replace("\u00a0", " ")
    lines = [re.sub(r"[ \t\f\v]+", " ", line).strip() for line in content.splitlines()]
    return "\n".join(line for line in lines if line)


def _terms(task: SearchTask, result: SearchResult) -> list[str]:
    text = " ".join(
        [task.question, *task.entities, *(item.description for item in task.requirements), result.title]
    ).casefold()
    latin = re.findall(r"[a-z0-9][a-z0-9._+-]{1,}", text)
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", text)
    chinese = [run for run in chinese_runs if len(run) <= 8]
    chinese.extend(run[index:index + 2] for run in chinese_runs for index in range(len(run) - 1))
    return list(dict.fromkeys(term for term in [*latin, *chinese] if len(term) > 1))


def _chunk(text: str, size: int, overlap: int) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    start = 0
    while start < len(text):
        target = min(len(text), start + size)
        end = target
        if target < len(text):
            boundary = max(text.rfind("\n", start + size // 2, target), text.rfind("。", start + size // 2, target))
            if boundary > start:
                end = boundary + 1
        value = text[start:end].strip()
        if value:
            chunks.append(DocumentChunk(f"chunk-{len(chunks) + 1}", value, start, end))
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def process_content(
    result: SearchResult,
    task: SearchTask,
    config: ContentProcessingConfig | None = None,
) -> ProcessedDocument:
    config = config or ContentProcessingConfig.from_env()
    raw = result.content or ""
    cleaned = clean_content(raw)
    if len(cleaned) <= config.direct_pass_chars:
        return ProcessedDocument(result.result_id, "direct", len(raw), len(cleaned), len(cleaned), cleaned)

    chunks = _chunk(cleaned, config.chunk_chars, config.chunk_overlap_chars)
    terms = _terms(task, result)
    for chunk in chunks:
        folded = chunk.text.casefold()
        chunk.matched_terms = [term for term in terms if term in folded]
        density = sum(folded.count(term) for term in chunk.matched_terms)
        chunk.score = round(len(chunk.matched_terms) + min(density, 10) * 0.2, 3)

    limit = config.max_selected_chunks
    if len(cleaned) <= config.semantic_compression_chars:
        limit = min(len(chunks), max(limit, 12))
    ranked = sorted(chunks, key=lambda item: (-item.score, item.start_char))[:limit]
    selected = sorted(ranked, key=lambda item: item.start_char)
    output = "\n\n".join(item.text for item in selected)
    mode = "extractive" if any(item.score > 0 for item in selected) else "head_fallback"
    return ProcessedDocument(result.result_id, mode, len(raw), len(cleaned), len(output), output, selected)
