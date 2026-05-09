"""Flask route detector."""

from __future__ import annotations

from llm_sca_tooling.plugins.http_rest.framework_detector import detect_python_routes


def detect_flask_routes(text: str, file_path: str):
    return [route for route in detect_python_routes(text, file_path) if route["framework"] == "flask"]
