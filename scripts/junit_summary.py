#!/usr/bin/env python3
"""Turn one JUnit XML report into a four-number JSON summary.

Runs in the same unprivileged job that produced the report. It reads the four
counters from the <testsuite> tags with a regular expression instead of an XML
parser, so no entity in a report a patch's tests wrote is ever expanded. The
job that signs the audit bundle then reads only JSON, and treats the numbers as
the test job's claim: whether the job passed comes from GitHub's job results.

  junit_summary.py junit.xml > junit.json
"""
import json
import re
import sys

KEYS = ("tests", "failures", "errors", "skipped")
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
summary = dict.fromkeys(KEYS, 0)
for attrs in re.findall(r"<testsuite\b([^>]*)>", text):
    for key in KEYS:
        m = re.search(rf'\b{key}="(\d+)"', attrs)
        summary[key] += int(m.group(1)) if m else 0
print(json.dumps({"file": sys.argv[1], **summary}))
