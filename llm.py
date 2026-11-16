"""Claude calls via the `claude` CLI, using the user's subscription (no API key).

Every call is a one-shot headless invocation. Tools are disabled: these are pure
text -> JSON transformations and we do not want the agent wandering the filesystem.
"""

import json
import re
import subprocess
import sys

MODEL = "claude-opus-5-5"
EFFORT = "medium"
TIMEOUT = 300


class LLMError(RuntimeError):
    pass


def call(prompt, system=None, timeout=TIMEOUT, model=MODEL, effort=EFFORT):
    """Run one headless Claude call. Returns the response text."""
    cmd = [
        "claude",
        "-p",
        "--model", model,
        "--effort", effort,
        "--output-format", "json",
        "--disallowed-tools", "Bash", "Read", "Write", "Edit", "WebSearch", "WebFetch",
    ]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise LLMError(f"claude call timed out after {timeout}s")
    if proc.returncode != 0:
        raise LLMError(f"claude exited {proc.returncode}: {proc.stderr[-800:]}")
    raw = proc.stdout.strip()
    if not raw:
        raise LLMError("claude returned nothing")
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(envelope, dict):
        if envelope.get("is_error"):
            raise LLMError(f"claude reported an error: {envelope.get('result')}")
        return envelope.get("result", raw)
    return raw


def call_json(prompt, system=None, **kw):
    """Run one call and parse the response as JSON.

    The model is told to emit bare JSON, but we tolerate fenced blocks and
    leading prose because a demo should not die on a stray sentence.
    """
    text = call(prompt, system=system, **kw)
    return parse_json(text)


def parse_json(text):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back to the outermost {...} or [...] span.
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise LLMError(f"could not parse JSON from model output: {text[:400]}")


JSON_RULE = (
    "You respond with bare JSON only: no prose before or after it, no markdown "
    "code fences. If you cannot answer, return JSON with an \"error\" key."
)


if __name__ == "__main__":
    # Smoke test: python3 llm.py
    out = call_json(
        'Return JSON: {"ok": true, "model_said": "<one word>"}',
        system=JSON_RULE,
    )
    print(json.dumps(out, indent=2), file=sys.stdout)
