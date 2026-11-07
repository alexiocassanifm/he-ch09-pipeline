#!/usr/bin/env python3
"""Write the audit bundle's manifest for one pipeline run.

The manifest answers the questions a reviewer who was not in the room will ask
about one change: which commit, which pipeline and harness judged it, which
checks ran and what they said, and, for agent runs, which model was asked for,
which model answered and what the run cost. It records; it does not promise a
rerun would produce the same patch.

  bundle.py --inputs DIR --out DIR [--needs JSON] [--scores FILE]

DIR is whatever the workflow downloaded: SARIF files, JUnit XML, agent run
directories with run.json. Standard library only.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

# The files that make up the pipeline and the harness. A change to any of them
# is a change to the judge, so the manifest pins each one by content hash.
JUDGE_FILES = [
    ".github/workflows/validate.yml",
    ".github/workflows/nightly.yml",
    ".github/workflows/liveness.yml",
    ".github/workflows/actions.lock",
    ".github/CODEOWNERS",
    ".semgrep.yml",
    "CLAUDE.md",
    ".claude/settings.json",
    "tools/package-lock.json",
    "requirements.lock",
    "deps-allowlist.txt",
]


def sha256(path: pathlib.Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def sarif_summary(path: pathlib.Path) -> dict:
    doc = json.loads(path.read_text())
    counts = {"error": 0, "warning": 0, "note": 0, "suppressed": 0}
    tools = []
    for run in doc.get("runs", []):
        tools.append(run.get("tool", {}).get("driver", {}).get("name", "unknown"))
        for result in run.get("results", []):
            if result.get("suppressions"):
                # Suppressed in source with a stated reason: kept visible, not counted as open.
                counts["suppressed"] += 1
                continue
            level = result.get("level", "warning")  # SARIF's default level
            counts[level if level in counts else "note"] += 1
    return {"file": path.name, "tools": tools, "results": counts}


def junit_summary(path: pathlib.Path) -> dict:
    # The test job parsed its own XML and wrote these four numbers. They are that
    # job's claim; whether it passed comes from GitHub's job results, under "jobs".
    doc = json.loads(path.read_text())
    return {k: doc.get(k) for k in ("file", "tests", "failures", "errors", "skipped")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inputs", required=True, type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--needs", default="{}", help="the workflow's toJSON(needs)")
    ap.add_argument("--scores", type=pathlib.Path, help="score.py --json output, nightly only")
    args = ap.parse_args()

    root = pathlib.Path(git("rev-parse", "--show-toplevel") or ".")
    env = os.environ.get
    manifest = {
        "schema": "he-ch09-audit-bundle/1",
        "written_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "change": {
            "repository": env("GITHUB_REPOSITORY"),
            "commit": git("rev-parse", "HEAD"),
            "ref": env("GITHUB_REF"),
            "head_ref": env("GITHUB_HEAD_REF"),
            "base_ref": env("GITHUB_BASE_REF"),
            "event": env("GITHUB_EVENT_NAME"),
            "actor": env("GITHUB_ACTOR"),
            "triggering_actor": env("GITHUB_TRIGGERING_ACTOR"),
        },
        "pipeline": {
            "workflow_ref": env("GITHUB_WORKFLOW_REF"),
            "workflow_sha": env("GITHUB_WORKFLOW_SHA"),
            "run_id": env("GITHUB_RUN_ID"),
            "run_attempt": env("GITHUB_RUN_ATTEMPT"),
            "run_url": f"{env('GITHUB_SERVER_URL')}/{env('GITHUB_REPOSITORY')}/actions/runs/{env('GITHUB_RUN_ID')}",
            "runner_image": {k: env(k) for k in ("ImageOS", "ImageVersion")},
            "jobs": {name: job.get("result") for name, job in json.loads(args.needs).items()},
        },
        "judge": {name: sha256(root / name) for name in JUDGE_FILES},
        "checks": {
            "sarif": [sarif_summary(p) for p in sorted(args.inputs.rglob("*.sarif"))],
            "junit": [junit_summary(p) for p in sorted(args.inputs.rglob("junit-*.json"))],
        },
        "agent_runs": [],
    }

    for record_path in sorted(args.inputs.rglob("run.json")):
        record = json.loads(record_path.read_text())
        record.pop("stderr_tail", None)
        record["transcript_sha256"] = sha256(record_path.parent / "transcript.jsonl")
        record["patch_sha256"] = sha256(record_path.parent / "patch.diff")
        manifest["agent_runs"].append(record)
        # The full transcript travels with the bundle; the manifest pins it by hash.
        dest = args.out / "runs" / record_path.parent.name
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("run.json", "transcript.jsonl", "patch.diff"):
            if (record_path.parent / name).exists():
                shutil.copy2(record_path.parent / name, dest / name)

    if args.scores and args.scores.exists():
        manifest["scores"] = json.loads(args.scores.read_text())

    # Readings for the Chapter 8 dashboard. CI cannot reach a collector on a
    # developer's machine, so the numbers travel in the bundle and are replayed
    # into the stack from a downloaded artifact.
    readings = {"sarif": [], "regression": None}
    for s in manifest["checks"]["sarif"]:
        readings["sarif"].append({"tools": s["tools"], **s["results"]})
    if "scores" in manifest:
        sc = manifest["scores"]
        readings["regression"] = {"passed": sc["passed"], "failed": sc["attempted"] - sc["passed"]}
    manifest["readings"] = readings

    args.out.mkdir(parents=True, exist_ok=True)
    for p in list(args.inputs.rglob("*.sarif")) + list(args.inputs.rglob("junit-*")):
        shutil.copy2(p, args.out / p.name)
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"bundle written: {len(manifest['checks']['sarif'])} SARIF, "
          f"{len(manifest['checks']['junit'])} JUnit, {len(manifest['agent_runs'])} agent runs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
