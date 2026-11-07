#!/usr/bin/env python3
"""Score stored predictions against a task directory.

This half of the run consults nothing and costs nothing: it is arithmetic over
two files, which is why a run recorded last month can be re-scored against a
criterion that did not exist when it was produced.

Four outcomes, not two. "oversize" means the case never reached the model at
all, usually because the rendered request did not fit the context budget, and
it is held out of the denominator instead of being counted as a wrong answer.
A case the system could not attempt is not a case it got wrong, and a scorer
that conflates the two reports a model problem to a team that has a plumbing
problem. "abstained" and "error" both mean escalate to a human and mean
entirely different things about the configuration, so they stay separate too.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

OUTCOMES = ("answered", "abstained", "oversize", "error")


def load_tasks(dataset: pathlib.Path) -> dict[str, dict]:
    try:
        import yaml
    except ModuleNotFoundError:
        sys.exit("pyyaml is required: pip install pyyaml")
    tasks = {}
    for path in sorted(dataset.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text())
        if not doc or "id" not in doc:
            sys.exit(f"{path}: task file has no id")
        tasks[doc["id"]] = doc
    if not tasks:
        sys.exit(f"no task files in {dataset}")
    return tasks


def load_predictions(path: pathlib.Path) -> list[dict]:
    rows = []
    for n, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            sys.exit(f"{path}:{n}: {exc}")
    return rows


def score(tasks: dict[str, dict], rows: list[dict]) -> dict:
    counts = dict.fromkeys(OUTCOMES, 0)
    passed = 0
    unknown = []
    for row in rows:
        task_id = row.get("task_id")
        if task_id not in tasks:
            unknown.append(task_id)
            continue
        outcome = row.get("outcome")
        if outcome not in counts:
            sys.exit(f"{task_id}: unknown outcome {outcome!r}, expected one of {OUTCOMES}")
        counts[outcome] += 1
        if outcome == "answered" and row.get("passed") is True:
            passed += 1
    if unknown:
        sys.exit(f"predictions reference tasks not in the dataset: {unknown}")
    # The denominator excludes oversize on purpose. Including it would let a
    # context-budget problem upstream look like a drop in model quality.
    attempted = counts["answered"] + counts["abstained"] + counts["error"]
    return {
        "counts": counts,
        "attempted": attempted,
        "passed": passed,
        "pass_rate": (passed / attempted) if attempted else None,
        "tasks_in_dataset": len(tasks),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dataset", required=True, type=pathlib.Path)
    ap.add_argument("--predictions", required=True, type=pathlib.Path)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    result = score(load_tasks(args.dataset), load_predictions(args.predictions))

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    c = result["counts"]
    print(f"  tasks in dataset   {result['tasks_in_dataset']}")
    print("  " + "  ".join(f"{name} {c[name]}" for name in OUTCOMES))
    print(f"  attempted          {result['attempted']}  (oversize held out)")
    rate = result["pass_rate"]
    print(f"  pass rate          {rate:.0%}" if rate is not None else
          "  pass rate          n/a, nothing was attempted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
