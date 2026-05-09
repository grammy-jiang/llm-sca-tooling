"""LSP subprocess lifecycle."""

from __future__ import annotations

import subprocess
from pathlib import Path

from llm_sca_tooling.indexing.lsp.errors import LspCrash


class LspLifecycle:
    def __init__(self, cmd: list[str], workspace_path: Path) -> None:
        self.cmd = cmd
        self.workspace_path = workspace_path
        self.process: subprocess.Popen[bytes] | None = None

    def start(self) -> subprocess.Popen[bytes]:
        self.process = subprocess.Popen(self.cmd, cwd=self.workspace_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if not self.process.stdin or not self.process.stdout:
            raise LspCrash("failed to open LSP stdio pipes")
        return self.process

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
