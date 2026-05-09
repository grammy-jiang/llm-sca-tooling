"""Minimal reusable LSP client."""

from __future__ import annotations

from pathlib import Path

from llm_sca_tooling.indexing.lsp.capabilities import (
    LspClientCapabilities,
    LspServerCapabilities,
)
from llm_sca_tooling.indexing.lsp.lifecycle import LspLifecycle
from llm_sca_tooling.indexing.lsp.request_dispatcher import RequestDispatcher


class LspClient:
    def __init__(
        self,
        server_id: str,
        cmd: list[str],
        workspace_path: Path,
        capabilities: LspClientCapabilities | None = None,
    ) -> None:
        self.server_id = server_id
        self.cmd = cmd
        self.workspace_path = workspace_path
        self.capabilities = capabilities or LspClientCapabilities()
        self.lifecycle = LspLifecycle(cmd, workspace_path)
        self.dispatcher: RequestDispatcher | None = None
        self.server_capabilities: LspServerCapabilities | None = None

    def start(self, *, timeout_ms: int = 5000) -> None:
        process = self.lifecycle.start()
        self.dispatcher = RequestDispatcher(process.stdin, process.stdout)  # type: ignore[arg-type]
        self.dispatcher.start()
        result = self.request(
            "initialize",
            {
                "processId": None,
                "rootUri": self.workspace_path.as_uri(),
                "capabilities": self.capabilities.as_lsp(),
            },
            timeout_ms=timeout_ms,
        )
        self.server_capabilities = LspServerCapabilities(
            server_id=self.server_id, capabilities=result.get("capabilities", {})
        )
        self.notify("initialized", {})

    def stop(self) -> None:
        if self.dispatcher:
            try:
                self.request("shutdown", {}, timeout_ms=1000)
                self.notify("exit", {})
            except Exception:
                pass
            self.dispatcher.stop()
        self.lifecycle.stop()

    def request(self, method: str, params: dict, *, timeout_ms: int = 5000) -> dict:
        if self.dispatcher is None:
            raise RuntimeError("LSP client is not started")
        return self.dispatcher.request(method, params, timeout_ms)

    def notify(self, method: str, params: dict) -> None:
        if self.dispatcher is None:
            raise RuntimeError("LSP client is not started")
        self.dispatcher.notify(method, params)

    def open_document(self, uri: str, language_id: str, text: str) -> None:
        self.notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": language_id,
                    "version": 1,
                    "text": text,
                }
            },
        )

    def close_document(self, uri: str) -> None:
        self.notify("textDocument/didClose", {"textDocument": {"uri": uri}})

    def wait_for_notification(
        self, method: str, *, timeout_ms: int = 1000
    ) -> dict | None:
        if self.dispatcher is None:
            raise RuntimeError("LSP client is not started")
        return self.dispatcher.wait_for_notification(method, timeout_ms)
