"""LLM-augmented Static Code Analysis tooling."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("llm-sca-tooling")
except PackageNotFoundError:
    __version__ = "0.0.0.dev0"

__all__ = ["__version__"]
