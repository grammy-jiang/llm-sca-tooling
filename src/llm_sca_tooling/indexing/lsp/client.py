"""Async JSON-RPC client for local LSP subprocesses."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import orjson

from llm_sca_tooling.indexing.lsp.capabilities import client_capabilities
from llm_sca_tooling.indexing.lsp.errors import LspError, LspTimeout
from llm_sca_tooling.indexing.lsp.protocol import decode_header, encode_message

__all__ = ["LspClient"]


class LspClient:
    def __init__(self, server_id: str, cmd: list[str], workspace_path: Path) -> None:
        self.server_id = server_id
        self.cmd = cmd
        self.workspace_path = workspace_path
        self.server_capabilities: dict[str, Any] = {}
        self._proc: asyncio.subprocess.Process | None = None
        self._next_id = 1

    async def start(self) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            *self.cmd,
            cwd=str(self.workspace_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        response = await self.request(
            "initialize",
            {
                "processId": None,
                "rootUri": self.workspace_path.as_uri(),
                "capabilities": client_capabilities(),
            },
            timeout_ms=2_000,
        )
        capabilities = response.get("capabilities")
        self.server_capabilities = (
            capabilities if isinstance(capabilities, dict) else {}
        )
        await self.notify("initialized", {})

    async def stop(self) -> None:
        if self._proc is None:
            return
        try:
            try:
                await self.request("shutdown", None, timeout_ms=1_000)
                await self.notify("exit", {})
            except LspError:
                pass
        finally:
            if self._proc.returncode is None:
                self._proc.terminate()
                try:
                    await asyncio.wait_for(self._proc.wait(), timeout=1)
                except TimeoutError:
                    self._proc.kill()
                    await self._proc.wait()
            self._proc = None

    async def request(
        self, method: str, params: dict[str, Any] | None, *, timeout_ms: int
    ) -> dict[str, Any]:
        proc = self._require_process()
        request_id = self._next_id
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        assert proc.stdin is not None
        proc.stdin.write(encode_message(payload))
        await proc.stdin.drain()
        try:
            response = await asyncio.wait_for(
                self._read_response(request_id), timeout=timeout_ms / 1000
            )
        except TimeoutError as exc:
            raise LspTimeout(f"LSP request {method!r} timed out") from exc
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError) as exc:
            raise LspError(f"LSP server {self.server_id!r} crashed") from exc
        if "error" in response:
            raise LspError(str(response["error"]))
        result = response.get("result")
        return result if isinstance(result, dict) else {}

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        proc = self._require_process()
        assert proc.stdin is not None
        proc.stdin.write(
            encode_message({"jsonrpc": "2.0", "method": method, "params": params})
        )
        await proc.stdin.drain()

    async def open_document(self, uri: str, language_id: str, text: str) -> None:
        await self.notify(
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

    async def close_document(self, uri: str) -> None:
        await self.notify("textDocument/didClose", {"textDocument": {"uri": uri}})

    async def _read_response(self, request_id: int) -> dict[str, Any]:
        proc = self._require_process()
        assert proc.stdout is not None
        while True:
            header = await proc.stdout.readuntil(b"\r\n\r\n")
            length = decode_header(header)
            body = await proc.stdout.readexactly(length)
            message: dict[str, Any] = orjson.loads(body)
            if message.get("id") == request_id:
                return message

    def _require_process(self) -> asyncio.subprocess.Process:
        if self._proc is None or self._proc.returncode is not None:
            raise LspError("LSP server is not running")
        return self._proc
