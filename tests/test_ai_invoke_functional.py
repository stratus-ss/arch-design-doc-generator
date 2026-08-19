"""Public-contract tests for CLI AI invocation heartbeats and Claude oneshot flags."""

from __future__ import annotations

import json
import sys

import pytest
from ai_invoke import _run_subprocess, claude_print_cmd, claude_response_text


def test_claude_print_cmd_matches_working_cli() -> None:
    cmd = claude_print_cmd("claude-sonnet-4-6", mcp_config="/tmp/mcp.json")
    assert cmd[0] == "claude"
    assert "--print" in cmd
    assert cmd[cmd.index("--model") + 1] == "claude-sonnet-4-6"
    assert cmd[cmd.index("--max-turns") + 1] == "1"
    assert cmd[cmd.index("--permission-mode") + 1] == "dontAsk"
    assert cmd[cmd.index("--setting-sources") + 1] == "user"
    assert "--strict-mcp-config" in cmd
    assert cmd[cmd.index("--mcp-config") + 1] == "/tmp/mcp.json"
    assert cmd[cmd.index("--output-format") + 1] == "json"
    assert "--disallowed-tools" not in cmd


def test_claude_response_text_unwraps_cli_json() -> None:
    wrapper = {
        "is_error": False,
        "type": "result",
        "modelUsage": {"claude-sonnet-4-6": {"canonicalModel": "claude-sonnet-4-6"}},
        "result": '{"CLIENT": {"value": "Acme", "confidence": "high"}}',
    }
    text = claude_response_text(json.dumps(wrapper))
    assert json.loads(text)["CLIENT"]["value"] == "Acme"


def test_claude_response_text_raises_on_error_envelope() -> None:
    wrapper = {"is_error": True, "type": "result", "result": "boom", "modelUsage": {}}
    with pytest.raises(RuntimeError, match="claude is_error"):
        claude_response_text(json.dumps(wrapper))


def test_run_subprocess_emits_heartbeat(capsys: pytest.CaptureFixture[str]) -> None:
    out = _run_subprocess(
        [sys.executable, "-c", "import time, sys; time.sleep(6); sys.stdout.write('done')"],
        stdin="",
        timeout=20,
    )
    assert out == "done"
    error = capsys.readouterr().err
    assert "elapsed, waiting for" in error
    assert "python" in error or sys.executable in error


def test_run_subprocess_timeout_raises_runtime_error() -> None:
    with pytest.raises(RuntimeError, match="timed out after 2s"):
        _run_subprocess(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdin="",
            timeout=2,
        )
