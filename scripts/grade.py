#!/usr/bin/env python3
"""The half of an eval run that is arithmetic: grade stored agent runs.

For every run directory under --runs, reset a clean worktree to the run's base
commit, apply the agent's patch, run the task's checks, and append one line to
--out in the Chapter 7 predictions format. Then print pass^k per task: a task
counts only if every one of its trials passed.

This job can read evals/checks/ because the agent job could not.
"""
import argparse
import collections
import json
import pathlib
import subprocess
import sys

import yaml

# Paths that judge the agent. A patch that touches any of them fails, whatever else it does.
PROTECTED = (".github/", ".claude/", "evals/", "tools/", "CLAUDE.md")


def run(cmd: str, cwd: pathlib.Path) -> bool:
    # Task checks are shell commands written by the people who own evals/, never by the agent.
    return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True).returncode == 0  # nosemgrep: subprocess-shell-true


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", required=True, type=pathlib.Path)
    ap.add_argument("--tasks", required=True, type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    args = ap.parse_args()

    repo = pathlib.Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    tasks = {}
    for path in args.tasks.glob("*.yaml"):
        doc = yaml.safe_load(path.read_text())
        tasks[doc["id"]] = doc

    rows, by_task = [], collections.defaultdict(list)
    for record_path in sorted(args.runs.glob("*/run.json")):
        record = json.loads(record_path.read_text())
        task = tasks[record["task_id"]]
        work = repo.parent / f"grade-{record['task_id']}-{record['trial']}"
        subprocess.run(["git", "worktree", "add", "--detach", str(work), record["base_commit"]],
                       cwd=repo, check=True, capture_output=True)

        # Absolute: git apply runs inside the worktree, not where the runs were downloaded.
        patch = (record_path.parent / "patch.diff").resolve()
        failed = []
        if record["is_error"] and patch.stat().st_size == 0:
            outcome, failed = "error", ["the agent run ended in error and changed nothing"]
        elif patch.stat().st_size and not run(f"git apply --binary {patch}", work):
            outcome, failed = "error", ["the patch did not apply"]
        else:
            outcome = "answered"
            changed = subprocess.run(["git", "status", "--porcelain"], cwd=work,
                                     capture_output=True, text=True).stdout.split("\n")
            touched = [l[3:] for l in changed if l[3:].startswith(PROTECTED)]
            if touched:
                failed.append("the harness was touched: " + ", ".join(touched))
            # Graders come from the commit under test, never from the agent's patch.
            subprocess.run(["git", "checkout", record["base_commit"], "--", "evals/checks"],
                           cwd=work, check=True, capture_output=True)
            failed += [c["name"] for c in task["checks"] if not run(c["run"], work)]

        passed = outcome == "answered" and not failed
        by_task[record["task_id"]].append(passed)
        rows.append({
            "task_id": record["task_id"],
            "outcome": outcome,
            "passed": passed if outcome == "answered" else None,
            "confidence": None,  # pass/fail tasks: there is no raw signal to store
            "notes": "all checks passed" if passed else "; ".join(failed),
            "trial": record["trial"],
            "models_served": record["models_served"],
        })
        subprocess.run(["git", "worktree", "remove", "--force", str(work)], cwd=repo, check=True)

    args.out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    for task_id in sorted(tasks):
        trials = by_task.get(task_id, [])
        verdict = "no runs" if not trials else ("pass" if all(trials) else "FAIL")
        print(f"  {task_id:32} {sum(trials)}/{len(trials)} trials  pass^k {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
