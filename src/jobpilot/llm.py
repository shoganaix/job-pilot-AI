"""LLM backend for tailored CV generation: `opencode run --format json`.

The helper resolves the real opencode binary (skipping the Windows ``.CMD``
shim so long prompts with quotes are passed safely as argv), parses the JSONL
event stream and returns the assistant text. Callers extract JSON with
:func:`extract_json` and must handle :class:`LLMError` to fall back to the
heuristic renderer.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path


class LLMError(RuntimeError):
    """Raised when the opencode backend fails or returns unusable output."""


def resolve_opencode() -> str:
    """Path of the opencode executable (direct exe preferred over shims)."""
    exe = shutil.which("opencode")
    if not exe:
        raise LLMError("opencode CLI not found in PATH (use --no-llm for the heuristic)")
    if exe.lower().endswith(".exe"):
        return exe
    shim = Path(exe)
    candidate = shim.parent / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
    if candidate.exists():
        return str(candidate)
    return exe


def run_opencode(prompt: str, *, model: str | None = None, timeout: float = 300.0) -> str:
    """Send ``prompt`` to opencode and return the concatenated assistant text."""
    exe = resolve_opencode()
    cmd = [exe, "run", "--format", "json"]
    if model:
        cmd += ["--model", model]
    cmd.append(prompt)
    if os.name == "nt" and exe.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c", *cmd]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise LLMError(f"opencode timed out after {timeout:.0f}s") from exc
    except OSError as exc:
        raise LLMError(f"could not run opencode: {exc}") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-400:]
        raise LLMError(f"opencode exited with {proc.returncode}: {tail}")
    return _collect_text(proc.stdout)


def _collect_text(stdout: str) -> str:
    """Concatenate every ``type=="text"`` event from a JSONL stream."""
    chunks: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "text":
            chunks.append(str(event.get("part", {}).get("text", "")))
    if not chunks:
        raise LLMError("opencode produced no text events")
    return "".join(chunks)


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(text: str):
    """First balanced JSON object/array found in ``text`` (fences allowed)."""
    fenced = _FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1)
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        blob = _balanced(text[start:], opener, closer)
        if blob:
            try:
                return json.loads(blob)
            except ValueError:
                continue
    try:
        return json.loads(text.strip())
    except ValueError as exc:
        raise LLMError(f"no JSON found in model output: {text[:200]!r}") from exc


def _balanced(text: str, opener: str, closer: str) -> str:
    """Slice of ``text`` from the first opener to its matching closer."""
    depth = 0
    in_str = False
    escape = False
    for i, ch in enumerate(text):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[: i + 1]
    return ""


def complete_json(prompt: str, *, model: str | None = None, timeout: float = 300.0):
    """Run the backend and parse the first JSON value of the answer."""
    return extract_json(run_opencode(prompt, model=model, timeout=timeout))
