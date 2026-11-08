#!/usr/bin/env python3
"""The half of an eval run that costs money: run the agent on one task, once.

Runs Claude Code headless against the working tree, keeps the whole event
stream, and writes three files to --out:

  transcript.jsonl  every stream-json event, as emitted
  patch.diff        what the agent changed, tracked and untracked files
  run.json          the record: what was asked, what loaded, what answered

It never grades anything. The grader lives in a different job that this one
cannot read, which is the point of splitting them. Standard library only.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time


def sh(*args: str, check: bool = True) -> str:
    return subprocess.run(args, check=check, capture_output=True, text=True).stdout


def task_prompt(path: pathlib.Path) -> tuple[str, str]:
    # The task files are YAML, but the agent job installs nothing it does not
    # need, so read the two fields it uses without a YAML parser.
    text = path.read_text()
    task_id = next(l.split(":", 1)[1].strip() for l in text.splitlines() if l.startswith("id:"))
    block = text.split("prompt: |", 1)[1]
    lines = []
    for line in block.splitlines()[1:]:
        if line and not line.startswith("  "):
            break
        lines.append(line[2:])
    return task_id, "\n".join(lines).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--task", required=True, type=pathlib.Path)
    ap.add_argument("--trial", required=True, type=int)
    ap.add_argument("--model", required=True)
    ap.add_argument("--claude", default="claude", help="path to the pinned claude binary")
    ap.add_argument("--max-turns", default="40")
    ap.add_argument("--max-budget-usd", default="1.00")
    ap.add_argument("--out", required=True, type=pathlib.Path)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    task_id, prompt = task_prompt(args.task)
    base = sh("git", "rev-parse", "HEAD").strip()

    cmd = [
        args.claude, "-p", prompt,
        "--model", args.model,
        "--output-format", "stream-json", "--verbose",
        # The documented CI shape: deny anything not on an exact allowlist.
        "--permission-mode", "dontAsk",
        "--allowedTools", "Read", "Glob", "Grep", "Edit", "Write", "Bash(python -m pytest *)",
        "--max-turns", args.max_turns,
        "--max-budget-usd", args.max_budget_usd,
    ]
    started = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = round(time.time() - started, 1)
    # Last line of defence on a public repository: whatever the agent printed,
    # the credential this job holds never reaches a stored file.
    for name in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"):
        secret = os.environ.get(name)
        if secret:
            proc.stdout = proc.stdout.replace(secret, f"[{name} REDACTED]")
            proc.stderr = proc.stderr.replace(secret, f"[{name} REDACTED]")
    (args.out / "transcript.jsonl").write_text(proc.stdout)

    init, result, served = {}, {}, set()
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            init = event
        elif event.get("type") == "assistant":
            # The model that answered, read from each response, not the one we asked for.
            model = (event.get("message") or {}).get("model")
            if model:
                served.add(model)
        elif event.get("type") == "result":
            result = event

    # Untracked files count as changes too: mark them intent-to-add, then diff.
    # The pinned Claude Code lives in tools/node_modules inside the checkout;
    # it is gitignored, and excluded here as well so a patch never carries it.
    sh("git", "add", "--intent-to-add", "--all", check=False)
    patch = sh("git", "diff", "--binary", base, "--", ".", ":(exclude)tools/node_modules")
    for name in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"):
        if os.environ.get(name):
            patch = patch.replace(os.environ[name], f"[{name} REDACTED]")
    (args.out / "patch.diff").write_text(patch)

    record = {
        "task_id": task_id,
        "trial": args.trial,
        "base_commit": base,
        "model_requested": args.model,
        "model_configured": init.get("model"),
        "models_served": sorted(served),
        "model_usage": result.get("modelUsage", {}),
        "claude_code_version": init.get("claude_code_version"),
        "permission_mode": init.get("permissionMode"),
        "api_key_source": init.get("apiKeySource"),
        "skills": init.get("skills", []),
        "tools": init.get("tools", []),
        "mcp_servers": init.get("mcp_servers", []),
        "plugins": init.get("plugins", []),
        "session_id": result.get("session_id") or init.get("session_id"),
        "num_turns": result.get("num_turns"),
        "is_error": result.get("is_error", True),
        "terminal_reason": result.get("terminal_reason") or result.get("subtype"),
        "total_cost_usd_estimate": result.get("total_cost_usd"),
        "exit_code": proc.returncode,
        "wall_seconds": elapsed,
        "stderr_tail": proc.stderr[-2000:],
        "runner": {k: os.environ.get(k) for k in ("ImageOS", "ImageVersion", "RUNNER_OS")},
    }
    (args.out / "run.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({k: record[k] for k in ("task_id", "trial", "models_served", "is_error",
                                               "num_turns", "terminal_reason", "exit_code")}))
    if record["is_error"]:
        # The log is public on a public repository: print the tail, never the environment.
        print("claude stderr (tail):\n" + proc.stderr[-1500:])
    # Always exit 0: a failed agent run is a result to grade, not a broken job.
    return 0


if __name__ == "__main__":
    sys.exit(main())
