"""Optional Java backend."""

from llm_sca_tooling.indexing.backends.java.capability import JAVA_BACKEND_ENABLED
from llm_sca_tooling.indexing.backends.java.java_backend import JavaBackend

__all__ = ["JAVA_BACKEND_ENABLED", "JavaBackend"]
