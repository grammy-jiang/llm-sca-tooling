"""Indexing diagnostic types and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

__all__ = ["DiagnosticSeverity", "IndexingDiagnostic"]


class DiagnosticSeverity(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"


@dataclass
class IndexingDiagnostic:
    severity: DiagnosticSeverity
    code: str
    message: str
    file_path: str | None = None
    backend_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "file_path": self.file_path,
            "backend_id": self.backend_id,
            "details": self.details,
        }
