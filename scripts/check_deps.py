#!/usr/bin/env python3
"""Fail the build on a package nobody approved.

Reads requirements.lock and deps-allowlist.txt. Every pinned package must be on
the allowlist, and every pin must carry at least one hash. The install step
then runs with --require-hashes, so pip refuses anything the lock does not
describe exactly. Standard library only.
"""
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parent.parent
lock = (root / "requirements.lock").read_text()
allowed = {
    line.strip().lower()
    for line in (root / "deps-allowlist.txt").read_text().splitlines()
    if line.strip() and not line.startswith("#")
}

problems = []
pins = 0
# A pin starts at column 0 with name==version and continues on indented lines.
for block in re.split(r"\n(?=\S)", lock):
    m = re.match(r"([A-Za-z0-9_.\-]+)==", block)
    if not m:
        continue
    pins += 1
    name = m.group(1).lower().replace("_", "-")
    if name not in allowed:
        problems.append(f"{name}: not on deps-allowlist.txt, a code owner has to approve it")
    if "--hash=sha256:" not in block:
        problems.append(f"{name}: pinned without a hash")

for p in problems:
    print(f"::error file=requirements.lock::{p}")
print(f"checked {pins} pins against {len(allowed)} approved names")
sys.exit(1 if problems else 0)
