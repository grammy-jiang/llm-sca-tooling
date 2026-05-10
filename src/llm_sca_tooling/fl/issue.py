"""Issue-text normalization for fault localisation."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import PurePosixPath

from pydantic import Field

from llm_sca_tooling.schemas.base import StrictBaseModel


class StackFrame(StrictBaseModel):
    file_path: str | None = None
    line: int | None = Field(default=None, ge=1)
    function_name: str | None = None
    module_name: str | None = None
    raw_text: str


class IssueText(StrictBaseModel):
    issue_id: str
    raw_text: str
    normalized_text: str
    symptoms: list[str] = Field(default_factory=list)
    expected_behaviour: str | None = None
    observed_behaviour: str | None = None
    mentioned_apis: list[str] = Field(default_factory=list)
    mentioned_files: list[str] = Field(default_factory=list)
    mentioned_symbols: list[str] = Field(default_factory=list)
    error_strings: list[str] = Field(default_factory=list)
    stack_trace_frames: list[StackFrame] = Field(default_factory=list)
    repos: list[str] | None = None
    severity_hint: str | None = None
    language_hints: list[str] = Field(default_factory=list)
    submitted_ts: str


_SECTION_PATTERNS = {
    "expected_behaviour": re.compile(
        r"(?ims)^\s*(?:#{1,3}\s*)?(?:expected|expected behaviour|expected behavior)\s*:?\s*$"
    ),
    "observed_behaviour": re.compile(
        r"(?ims)^\s*(?:#{1,3}\s*)?(?:actual|observed|observed behaviour|observed behavior|what happened)\s*:?\s*$"
    ),
    "symptoms": re.compile(
        r"(?ims)^\s*(?:#{1,3}\s*)?(?:description|symptoms|steps to reproduce|h2\.\s*(?:description|steps))\s*:?\s*$"
    ),
}
_HEADING_RE = re.compile(r"(?im)^\s*(?:#{1,3}\s*[\w ./'-]+|h2\.\s*[\w ./'-]+)\s*:?\s*$")
_PYTHON_FRAME_RE = re.compile(
    r'^\s*File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<func>[\w.<>\-]+)',
    re.MULTILINE,
)
_JS_FRAME_RE = re.compile(
    r"^\s*at\s+(?:(?P<func>[\w.$<>/:-]+)\s+)?\(?"
    r"(?P<file>[^()\s]+?\.(?:js|jsx|ts|tsx|mjs|cjs)):(?P<line>\d+)(?::\d+)?\)?",
    re.MULTILINE,
)
_CPP_FRAME_RE = re.compile(
    r"^\s*#\d+\s+(?:0x[0-9a-fA-F]+\s+)?(?:in\s+)?"
    r"(?P<func>[\w:~<>*&,\s]+?)\s*\((?P<file>[^():]+?\.(?:c|cc|cpp|cxx|h|hpp)):(?P<line>\d+)\)",
    re.MULTILINE,
)
_PATH_RE = re.compile(
    r"(?P<path>(?:[\w@.+-]+/)+[\w@.+-]+\.(?:py|pyi|js|jsx|ts|tsx|c|cc|cpp|cxx|h|hpp|java|go|rs|rb|php|cs|kt|scala|swift))"
    r"|(?P<basename>[\w@.+-]+\.(?:py|pyi|js|jsx|ts|tsx|c|cc|cpp|cxx|h|hpp|java|go|rs|rb|php|cs|kt|scala|swift))"
)
_SYMBOL_RE = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\b"
)
_ERROR_LINE_RE = re.compile(
    r"(?i)(error:|exception:|traceback|panic:|sigsegv|segmentation fault|undefined|null|none|cannot read|attributeerror|typeerror|valueerror|keyerror|runtimeerror|cwe-\d+)"
)
_URL_RE = re.compile(r"https?://([^/\s)]+)[^\s)]*")
_MARKDOWN_RE = re.compile(r"[*_`>#]+")

_LANG_BY_EXT = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".java": "java",
}

_STOP_SYMBOLS = {
    "actual",
    "and",
    "but",
    "description",
    "expected",
    "file",
    "from",
    "issue",
    "line",
    "none",
    "null",
    "observed",
    "panic",
    "steps",
    "the",
    "this",
    "traceback",
    "undefined",
}


def normalize_issue_text(
    raw_text: str,
    *,
    issue_id: str = "issue:adhoc",
    repos: list[str] | None = None,
    submitted_ts: str | None = None,
) -> IssueText:
    """Convert raw issue text into deterministic structured FL input."""

    normalized = _normalize_text(raw_text)
    sections = _extract_sections(raw_text)
    frames = _extract_stack_frames(raw_text)
    mentioned_files = _unique(
        [_repo_relative_hint(match.group(0)) for match in _PATH_RE.finditer(raw_text)]
        + [frame.file_path for frame in frames if frame.file_path]
    )
    error_strings = _extract_error_strings(raw_text)
    symbols = _extract_symbols(raw_text, frames)
    language_hints = _language_hints(raw_text, mentioned_files, error_strings)
    symptoms = sections.get("symptoms", [])
    if not symptoms and error_strings:
        symptoms = error_strings[:3]
    return IssueText(
        issue_id=issue_id,
        raw_text=raw_text,
        normalized_text=normalized,
        symptoms=symptoms,
        expected_behaviour=_empty_to_none(sections.get("expected_behaviour_text")),
        observed_behaviour=_empty_to_none(sections.get("observed_behaviour_text")),
        mentioned_apis=[
            symbol for symbol in symbols if "." in symbol or "::" in symbol
        ],
        mentioned_files=mentioned_files,
        mentioned_symbols=symbols,
        error_strings=error_strings,
        stack_trace_frames=frames,
        repos=repos,
        severity_hint=_severity_hint(raw_text),
        language_hints=language_hints,
        submitted_ts=submitted_ts or _now_ts(),
    )


def _now_ts() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _normalize_text(raw_text: str) -> str:
    code_blocks: list[str] = []

    def keep_code(match: re.Match[str]) -> str:
        code_blocks.append(match.group(0))
        return f" CODE_BLOCK_{len(code_blocks) - 1} "

    without_code = re.sub(r"(?s)```.*?```", keep_code, raw_text)
    without_urls = _URL_RE.sub(lambda match: f" {match.group(1)} ", without_code)
    without_markdown = _MARKDOWN_RE.sub(" ", without_urls)
    collapsed = re.sub(r"\s+", " ", without_markdown).strip().lower()
    for index, block in enumerate(code_blocks):
        collapsed = collapsed.replace(f"code_block_{index}", block)
    return collapsed


def _extract_sections(raw_text: str) -> dict[str, object]:
    headings = [
        (match.start(), match.end(), match.group(0))
        for match in _HEADING_RE.finditer(raw_text)
    ]
    sections: dict[str, object] = {"symptoms": []}
    if not headings:
        return sections
    for index, (start, end, heading) in enumerate(headings):
        next_start = (
            headings[index + 1][0] if index + 1 < len(headings) else len(raw_text)
        )
        body = _trim_section_body(raw_text[end:next_start].strip())
        if not body:
            continue
        key = _section_key(heading)
        if key == "symptoms":
            symptoms = sections.setdefault("symptoms", [])
            if isinstance(symptoms, list):
                symptoms.append(body)
        elif key:
            sections[f"{key}_text"] = body
        else:
            _ = start
    return sections


def _section_key(heading: str) -> str | None:
    for key, pattern in _SECTION_PATTERNS.items():
        if pattern.match(heading):
            return key
    return None


def _trim_section_body(body: str) -> str:
    for marker in ("\nTraceback (most recent call last):", "\n```"):
        if marker in body:
            body = body.split(marker, 1)[0].strip()
    return body


def _extract_stack_frames(raw_text: str) -> list[StackFrame]:
    frames: list[StackFrame] = []
    for pattern in (_PYTHON_FRAME_RE, _JS_FRAME_RE, _CPP_FRAME_RE):
        for match in pattern.finditer(raw_text):
            raw_file = match.group("file").strip()
            func = " ".join((match.group("func") or "").split()) or None
            frames.append(
                StackFrame(
                    file_path=_repo_relative_hint(raw_file),
                    line=int(match.group("line")),
                    function_name=func,
                    module_name=_module_hint(raw_file),
                    raw_text=match.group(0).strip(),
                )
            )
    return _unique_frames(frames)


def _extract_error_strings(raw_text: str) -> list[str]:
    lines = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped and _ERROR_LINE_RE.search(stripped):
            lines.append(stripped[:300])
    return _unique(lines)


def _extract_symbols(raw_text: str, frames: list[StackFrame]) -> list[str]:
    symbols = [frame.function_name for frame in frames if frame.function_name]
    for match in _SYMBOL_RE.finditer(raw_text):
        token = match.group(0)
        if token.lower() in _STOP_SYMBOLS or len(token) < 3:
            continue
        if token.isupper() and len(token) <= 4:
            continue
        if "." in token and token.startswith("http"):
            continue
        if _looks_code_symbol(token):
            symbols.append(token)
    return _unique(symbols)


def _looks_code_symbol(token: str) -> bool:
    return (
        "_" in token
        or "." in token
        or "::" in token
        or any(char.isupper() for char in token[1:])
        or token.endswith(("Error", "Exception"))
    )


def _language_hints(
    raw_text: str, mentioned_files: list[str], error_strings: list[str]
) -> list[str]:
    hints: list[str] = []
    for file_path in mentioned_files:
        suffix = PurePosixPath(file_path).suffix.lower()
        if suffix in _LANG_BY_EXT:
            hints.append(_LANG_BY_EXT[suffix])
    text = "\n".join([raw_text, *error_strings]).lower()
    if "attributeerror" in text or "traceback (most recent call last)" in text:
        hints.append("python")
    if "cannot read" in text or "typeerror" in text:
        hints.append("javascript")
    if "nullpointerexception" in text:
        hints.append("java")
    if "sigsegv" in text or "segmentation fault" in text:
        hints.append("cpp")
    return _unique(hints)


def _severity_hint(raw_text: str) -> str | None:
    lower = raw_text.lower()
    for severity in ("critical", "high", "medium", "low"):
        if severity in lower:
            return severity
    if "crash" in lower or "data loss" in lower:
        return "high"
    return None


def _repo_relative_hint(path_text: str) -> str:
    stripped = path_text.strip().strip("\"'`),.;")
    stripped = stripped.replace("\\", "/")
    if "/" not in stripped:
        return stripped
    parts = [part for part in stripped.split("/") if part and part not in {".", ".."}]
    for marker in ("src", "tests", "test", "lib", "app", "include"):
        if marker in parts:
            return "/".join(parts[parts.index(marker) :])
    return "/".join(parts[-4:])


def _module_hint(file_path: str) -> str | None:
    path = PurePosixPath(_repo_relative_hint(file_path))
    if not path.suffix:
        return None
    return ".".join(path.with_suffix("").parts)


def _unique(values: Sequence[str | None]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _unique_frames(frames: list[StackFrame]) -> list[StackFrame]:
    result: list[StackFrame] = []
    seen: set[tuple[str | None, int | None, str | None]] = set()
    for frame in frames:
        key = (frame.file_path, frame.line, frame.function_name)
        if key in seen:
            continue
        seen.add(key)
        result.append(frame)
    return result


def _empty_to_none(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
