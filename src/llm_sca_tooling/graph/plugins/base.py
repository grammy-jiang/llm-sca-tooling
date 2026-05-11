"""LanguagePlugin ABC and companion dataclasses (Gap 6)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SymbolRecord:
    """A named symbol extracted from a source file."""

    name: str
    kind: str  # function, class, variable, etc.
    file_path: str
    line: int


@dataclass
class CallRecord:
    """A call edge between two symbols."""

    caller: str
    callee: str
    file_path: str
    line: int


@dataclass
class TypeRecord:
    """A type annotation attached to a symbol."""

    symbol: str
    type_annotation: str
    file_path: str
    line: int


class LanguagePlugin(ABC):
    """ABC for language-specific symbol/call/type extraction plugins."""

    @property
    @abstractmethod
    def language(self) -> str:
        """Return the language identifier (e.g. ``"python"``)."""
        ...

    @abstractmethod
    def extract_symbols(self, file_path: str) -> list[SymbolRecord]:
        """Extract all symbols from *file_path*."""
        ...

    @abstractmethod
    def extract_calls(self, file_path: str) -> list[CallRecord]:
        """Extract all call edges from *file_path*."""
        ...

    @abstractmethod
    def extract_types(self, file_path: str) -> list[TypeRecord]:
        """Extract all type annotations from *file_path*."""
        ...
