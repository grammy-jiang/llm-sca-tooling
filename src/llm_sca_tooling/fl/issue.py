"""Issue text normalization for fault localisation."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from pydantic import Field

from llm_sca_tooling.fl.models import StrictFlModel

__all__ = ["IssueText", "StackFrame", "normalize_issue_text"]


class StackFrame(StrictFlModel):
    file_path: str | None = None
    line: int | None = None
    function_name: str | None = None
    module_name: str | None = None
    raw_text: str


class IssueText(StrictFlModel):
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


def normalize_issue_text(raw_text: str, repos: list[str] | None = None) -> IssueText:
    normalized = _normalize(raw_text)
    frames = _stack_frames(raw_text)
    sections = _sections(raw_text)
    files = _dedupe(
        [frame.file_path for frame in frames if frame.file_path]
        + re.findall(
            r"(?<![\w./-])(?:\.?[\w-]+/)*[\w.-]+\."
            r"(?:json|ya?ml|toml|md|py|tsx?|jsx?|cpp|cc|cxx|hpp|h|idl)\b",
            raw_text,
        )
    )
    symbols = _dedupe(
        [frame.function_name for frame in frames if frame.function_name]
        + re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z0-9_.]+\b", raw_text)
        + re.findall(r"\b[A-Z][A-Za-z0-9_]+|[a-z]+_[a-z0-9_]+\b", raw_text)
    )
    errors = [
        line.strip()
        for line in raw_text.splitlines()
        if re.search(r"(error|exception|panic|sigsegv|null|undefined)", line, re.I)
    ]
    digest = hashlib.sha256(raw_text.encode()).hexdigest()[:16]
    return IssueText(
        issue_id=f"issue:{digest}",
        raw_text=raw_text,
        normalized_text=normalized,
        symptoms=errors[:3] or [normalized[:120]],
        expected_behaviour=sections.get("expected"),
        observed_behaviour=sections.get("actual") or sections.get("observed"),
        mentioned_apis=symbols[:],
        mentioned_files=files,
        mentioned_symbols=symbols,
        error_strings=errors,
        stack_trace_frames=frames,
        repos=repos,
        severity_hint=(
            "security" if re.search(r"cwe|vulnerab|injection", raw_text, re.I) else None
        ),
        language_hints=_language_hints(files, errors),
        submitted_ts=datetime.now(UTC).isoformat(),
    )


def _normalize(text: str) -> str:
    text = re.sub(r"https?://([^/\s]+)\S*", r"\1", text)
    text = re.sub(r"[*_#>`]", " ", text)
    return " ".join(text.split()).lower()


def _sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        match = re.match(
            r"(?:#+|h2\.)\s*(expected|actual|observed|steps).*", stripped, re.I
        )
        if match:
            if current and buffer:
                sections[current] = "\n".join(buffer).strip() or None  # type: ignore[assignment]
            current = match.group(1).lower()
            buffer = []
        elif current:
            buffer.append(line)
    if current and buffer:
        sections[current] = "\n".join(buffer).strip()
    return {k: v for k, v in sections.items() if v}


def _stack_frames(text: str) -> list[StackFrame]:
    frames: list[StackFrame] = []
    for line in text.splitlines():
        py = re.search(r'File "([^"]+)", line (\d+), in ([\w_<>]+)', line)
        ts = re.search(r"at\s+([\w$.<>]+)\s+\(([^:]+):(\d+)(?::\d+)?\)", line)
        cpp = re.search(r"#\d+\s+.*\s+in\s+([\w:~]+)\s+\(([^:]+):(\d+)\)", line)
        if py:
            frames.append(
                StackFrame(
                    file_path=py.group(1),
                    line=int(py.group(2)),
                    function_name=py.group(3),
                    raw_text=line,
                )
            )
        elif ts:
            frames.append(
                StackFrame(
                    file_path=ts.group(2),
                    line=int(ts.group(3)),
                    function_name=ts.group(1),
                    raw_text=line,
                )
            )
        elif cpp:
            frames.append(
                StackFrame(
                    file_path=cpp.group(2),
                    line=int(cpp.group(3)),
                    function_name=cpp.group(1),
                    raw_text=line,
                )
            )
    return frames


def _language_hints(files: list[str], errors: list[str]) -> list[str]:
    hints: set[str] = set()
    for file in files:
        suffix = file.rsplit(".", 1)[-1]
        hints.update(
            {
                "py": "python",
                "ts": "typescript",
                "js": "javascript",
                "cpp": "cpp",
                "cc": "cpp",
            }.get(suffix, "")
            for _ in [0]
        )
    joined = "\n".join(errors)
    if "AttributeError" in joined:
        hints.add("python")
    if "TypeError" in joined:
        hints.add("typescript")
    hints.discard("")
    return sorted(hints)


def _dedupe(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
