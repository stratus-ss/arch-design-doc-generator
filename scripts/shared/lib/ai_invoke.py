#!/usr/bin/env python3
"""
ai_invoke.py — Shared AI-invocation module (Cursor SDK / Claude CLI / Codex CLI).

Extracted from scripts/hld_lld/ai/ai_draft_deterministic.py and
scripts/hld_lld/ai/deterministic/slots.py so the HLD/LLD AI drafting pipeline
uses a single source of truth for invoking Cursor SDK / Claude CLI / Codex CLI.
"""

from __future__ import annotations

import getpass
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_SDK_INSTALL_TIMEOUT_SECS = 300


def ensure_cursor_sdk(project_root: Path) -> str:
    cursor_venv = project_root / ".cursor-sdk-venv"
    cursor_python = cursor_venv / "bin" / "python"
    cursor_pip = cursor_venv / "bin" / "pip"
    if not cursor_python.exists():
        print("Setting up Cursor SDK environment...")
        subprocess.run(
            ["python3", "-m", "venv", str(cursor_venv)],
            check=True,
            cwd=str(project_root),
            timeout=_SDK_INSTALL_TIMEOUT_SECS,
        )
        subprocess.run(
            [str(cursor_pip), "install", "--quiet", "--upgrade", "pip"],
            check=True,
            cwd=str(project_root),
            timeout=_SDK_INSTALL_TIMEOUT_SECS,
        )
        subprocess.run(
            [str(cursor_pip), "install", "--quiet", "cursor-sdk", "pyyaml"],
            check=True,
            cwd=str(project_root),
            timeout=_SDK_INSTALL_TIMEOUT_SECS,
        )
        print("Cursor SDK installed.")
    else:
        try:
            subprocess.run(
                [str(cursor_python), "-c", "import cursor_sdk"],
                check=True,
                cwd=str(project_root),
                timeout=_SDK_INSTALL_TIMEOUT_SECS,
            )
        except subprocess.CalledProcessError:
            print("Installing cursor-sdk into existing venv...")
            subprocess.run(
                [str(cursor_pip), "install", "--quiet", "cursor-sdk"],
                check=True,
                cwd=str(project_root),
                timeout=_SDK_INSTALL_TIMEOUT_SECS,
            )
        try:
            subprocess.run(
                [str(cursor_python), "-c", "import yaml"],
                check=True,
                cwd=str(project_root),
                timeout=_SDK_INSTALL_TIMEOUT_SECS,
            )
        except subprocess.CalledProcessError:
            subprocess.run(
                [str(cursor_pip), "install", "--quiet", "pyyaml"],
                check=True,
                cwd=str(project_root),
                timeout=_SDK_INSTALL_TIMEOUT_SECS,
            )
    return str(cursor_python)


def ensure_cursor_key() -> str:
    """Resolve CURSOR_API_KEY from env, then cache file, then interactive prompt.

    Sets os.environ["CURSOR_API_KEY"] as a side effect (existing in-process
    callers that only relied on the env var keep working unchanged) and
    returns the resolved key string.

    All status messages go to stderr (not stdout) so callers that capture
    this function's return value via a script that prints only the key to
    stdout get a clean, single-line key with no incidental output mixed in.
    """
    key_file = Path.home() / ".config" / "arch-doc-gen" / "cursor_api_key"
    api_key = os.environ.get("CURSOR_API_KEY", "")
    if not api_key and key_file.exists():
        api_key = key_file.read_text(encoding="utf-8").strip()
        print(f"Cursor API key loaded from {key_file}", file=sys.stderr)

    if not api_key:
        print("\nCursor SDK requires an API key.", file=sys.stderr)
        print("Get yours from: https://cursor.com/dashboard/api\n", file=sys.stderr)
        try:
            api_key = getpass.getpass("Paste your CURSOR_API_KEY (input hidden): ").strip()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit("Error: No API key provided. Aborting.") from None
        if not api_key:
            raise SystemExit("Error: No API key provided. Aborting.")
        if not (api_key.startswith("crsr_") or len(api_key) >= 20):
            raise SystemExit(
                "Error: CURSOR_API_KEY looks invalid. Expected a key starting with 'crsr_' or at least 20 characters."
            )
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(api_key, encoding="utf-8")
        key_file.chmod(0o600)
        print(f"API key saved to {key_file}", file=sys.stderr)
        print("  (Delete that file to be prompted again)\n", file=sys.stderr)
    os.environ["CURSOR_API_KEY"] = api_key
    return api_key


# ── AI tool invocation ────────────────────────────────────────────────────────

_HEARTBEAT_SECS = 5.0
# One Prompt A chunk produced ~21k output tokens in ~242s on Vertex Sonnet 4.6.
_CLAUDE_MIN_TIMEOUT_SECS = 420


def claude_print_cmd(model: str, *, mcp_config: str | None = None) -> list[str]:
    """Headless one-shot Claude Code argv proven to extract slots on Vertex.

    Working CLI recipe: --print --model claude-sonnet-4-6 --output-format json
    --max-turns 1 --permission-mode dontAsk --setting-sources user
    --strict-mcp-config --mcp-config <empty.json>, cwd isolated from this repo.
    """
    cmd = [
        "claude",
        "--print",
        "--model",
        model,
        "--output-format",
        "json",
        "--max-turns",
        "1",
        "--permission-mode",
        "dontAsk",
        "--setting-sources",
        "user",
    ]
    if mcp_config:
        cmd.extend(["--strict-mcp-config", "--mcp-config", mcp_config])
    return cmd


def claude_response_text(stdout: str) -> str:
    """Return model text from Claude Code print stdout.

    --output-format json wraps the reply in {"result": "<text>", "modelUsage": ...}.
    Slot extraction must unwrap .result or it will parse the envelope as slots.
    """
    payload = _claude_print_payload(stdout)
    if payload is None:
        return stdout or ""
    if payload.get("is_error"):
        raise RuntimeError(f"claude is_error: {payload.get('result') or payload.get('subtype') or 'unknown'}")
    result = payload.get("result")
    if result is None:
        return ""
    if isinstance(result, (dict, list)):
        return json.dumps(result)
    return str(result)


def _claude_print_payload(stdout: str) -> dict | None:
    raw = (stdout or "").strip()
    if not raw.startswith("{"):
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if "result" in payload and ("modelUsage" in payload or payload.get("type") == "result"):
        return payload
    return None


def run_claude(prompt: str, model: str, timeout: int) -> str:
    """Invoke `claude` CLI and return the model text (unwrapped from JSON)."""
    claude_model = (model or "").strip()
    effective_timeout = max(int(timeout), _CLAUDE_MIN_TIMEOUT_SECS)
    if effective_timeout > int(timeout):
        print(
            f"    raising claude timeout {timeout}s -> {effective_timeout}s (Prompt A needs ~4m per chunk)",
            file=sys.stderr,
            flush=True,
        )
    print(
        f"    invoking claude --print model={claude_model} (oneshot json, {effective_timeout}s timeout) ...",
        file=sys.stderr,
        flush=True,
    )
    with tempfile.TemporaryDirectory(prefix="hld-claude-") as tmp:
        mcp_path = Path(tmp) / "mcp.json"
        mcp_path.write_text('{"mcpServers": {}}\n', encoding="utf-8")
        stdout = _run_subprocess(
            claude_print_cmd(claude_model, mcp_config=str(mcp_path)),
            stdin=prompt,
            timeout=effective_timeout,
            cwd=tmp,
            inherit_stderr=True,
        )
    payload = _claude_print_payload(stdout)
    if payload is not None:
        usage = payload.get("modelUsage") or {}
        models = ",".join(usage) if isinstance(usage, dict) else ""
        print(
            f"    claude completed model={models or claude_model} duration_ms={payload.get('duration_ms')}",
            file=sys.stderr,
            flush=True,
        )
    return claude_response_text(stdout)


def run_codex(prompt: str, model: str, timeout: int) -> str:
    """Invoke `codex` CLI and return stdout."""
    cmd = ["codex", "--full-auto", "--model", model, "--stdin"]
    return _run_subprocess(cmd, stdin=prompt, timeout=timeout)


def run_cursor(prompt: str, model: str, timeout: int, cursor_python: str) -> str:
    """Invoke Cursor SDK (sync Python API) and return the response text.

    stdout is captured and returned as the JSON result.
    stderr is captured so raw tracebacks are not surfaced to end users.
    """
    script = f"""
import sys, os
try:
    from cursor_sdk import Agent, AgentOptions, LocalAgentOptions
except ImportError:
    sys.exit("cursor_sdk not installed")

# Workaround: some cursor-sdk-bridge versions reject CLI values starting
# with '-' (secrets.token_urlsafe can produce a token with a leading '-',
# causing "Missing value for --tool-callback-auth-token"). cursor-sdk
# >=1.0.26 fixes this upstream by renaming the private _new_auth_token()
# to a public new_auth_token() that already excludes leading dashes, so
# this patch is a defense-in-depth no-op against current releases —
# checking both names keeps it from hard-crashing against either the old
# or the new cursor-sdk API surface.
import cursor_sdk._tool_callback as _tc

def _patch_cursor_auth_token(_tc):
    # SDK workaround: leading '-' in auth tokens breaks CLI flags.
    _token_attr = "new_auth_token" if hasattr(_tc, "new_auth_token") else (
        "_new_auth_token" if hasattr(_tc, "_new_auth_token") else None)
    if not _token_attr:
        return
    _orig_token = getattr(_tc, _token_attr)
    def _safe_auth_token():
        for _ in range(20):
            t = _orig_token()
            if not t.startswith("-"):
                return t
        return "A" + _orig_token().lstrip("-")
    setattr(_tc, _token_attr, _safe_auth_token)

_patch_cursor_auth_token(_tc)

options = AgentOptions(
    api_key=os.environ.get("CURSOR_API_KEY", ""),
    model={model!r},
    local=LocalAgentOptions(cwd=os.getcwd()),
)
result = Agent.prompt({json.dumps(prompt)}, options)

if result.status == "error":
    print(f"cursor agent run failed: {{result.id}}", file=sys.stderr)
    sys.exit(2)
print(result.result or "", end="")
"""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(script)
        tmp = f.name
    try:
        env = {**os.environ, "CURSOR_API_KEY": os.environ.get("CURSOR_API_KEY", "")}
        proc = subprocess.Popen(
            [cursor_python, tmp],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        stdout, stderr = _wait_with_heartbeat(proc, timeout, label="cursor_sdk")
        if proc.returncode != 0:
            error_detail = ""
            if stderr:
                stderr_lines = [line.strip() for line in stderr.splitlines() if line.strip()]
                if stderr_lines:
                    error_detail = stderr_lines[-1]
            if error_detail:
                raise RuntimeError(f"cursor_sdk exited {proc.returncode}: {error_detail}")
            raise RuntimeError(f"cursor_sdk exited {proc.returncode}")
        return stdout
    finally:
        Path(tmp).unlink(missing_ok=True)


def _elapsed_label(seconds: float) -> str:
    elapsed = int(seconds)
    if elapsed >= 60:
        return f"{elapsed // 60}m {elapsed % 60}s"
    return f"{elapsed}s"


def _wait_with_heartbeat(
    proc: subprocess.Popen,
    timeout: int,
    *,
    stdin: str | None = None,
    label: str,
) -> tuple[str, str]:
    """Wait for a child process, printing the same 5s stderr heartbeat as Cursor."""
    start_time = time.monotonic()
    deadline = start_time + timeout
    input_data = stdin
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(proc.args, timeout)
            try:
                stdout, stderr = proc.communicate(input=input_data, timeout=min(_HEARTBEAT_SECS, remaining))
                return stdout or "", stderr or ""
            except subprocess.TimeoutExpired:
                input_data = None
                print(
                    f"    ... {_elapsed_label(time.monotonic() - start_time)} elapsed, "
                    f"waiting for {label} response ...",
                    file=sys.stderr,
                    flush=True,
                )
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise RuntimeError(f"{label} timed out after {timeout}s") from None


def _run_subprocess(
    cmd: list[str],
    stdin: str,
    timeout: int,
    *,
    cwd: str | None = None,
    inherit_stderr: bool = False,
) -> str:
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None if inherit_stderr else subprocess.PIPE,
        text=True,
        cwd=cwd,
    )
    stdout, stderr = _wait_with_heartbeat(proc, timeout, stdin=stdin, label=cmd[0])
    if proc.returncode != 0:
        detail = (stderr or "").strip()[:500]
        if detail:
            raise RuntimeError(f"{cmd[0]} exited {proc.returncode}: {detail}")
        raise RuntimeError(f"{cmd[0]} exited {proc.returncode}")
    return stdout


def _ai_value_disabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"", "no", "none", "off"}


def invoke_ai(
    prompt: str,
    tool: str,
    model: str,
    timeout: int,
    retries: int,
    cursor_python: str = "python3",
) -> str:
    """Invoke the selected AI tool with retry/backoff.

    Explicit parameters instead of an argparse.Namespace so this utility is
    not coupled to any caller's argparse attribute names (args.tool vs
    args.ai_tool).
    """
    if _ai_value_disabled(tool):
        raise RuntimeError("AI pathway disabled: set AI_TOOL to a real tool value to re-enable.")
    if _ai_value_disabled(model):
        raise RuntimeError(
            "AI pathway disabled: set AI_MODEL (or CURSOR_MODEL for legacy callers) to a real model to re-enable."
        )
    last_err: Exception = RuntimeError("no attempts made")
    for attempt in range(1, retries + 1):
        try:
            if tool == "claude":
                return run_claude(prompt, model, timeout)
            elif tool == "codex":
                return run_codex(prompt, model, timeout)
            elif tool == "cursor":
                return run_cursor(prompt, model, timeout, cursor_python)
            else:
                raise ValueError(f"Unknown tool: {tool}")
        except (RuntimeError, OSError, subprocess.TimeoutExpired, ValueError) as exc:
            last_err = exc
            if attempt < retries:
                wait = 2**attempt
                print(f"  [attempt {attempt}/{retries}] Error: {exc}. Retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
    raise last_err
