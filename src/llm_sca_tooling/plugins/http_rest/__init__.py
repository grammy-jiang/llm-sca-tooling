"""HTTP-REST interface plugin."""

from llm_sca_tooling.plugins.http_rest.plugin import HttpRestPlugin
from llm_sca_tooling.plugins.http_rest.url_normalizer import (
    match_paths,
    normalize_url_path,
)

__all__ = ["HttpRestPlugin", "match_paths", "normalize_url_path"]
