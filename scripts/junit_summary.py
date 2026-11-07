#!/usr/bin/env python3
"""Turn one JUnit XML report into a four-number JSON summary.

Runs in the same unprivileged job that produced the report, so XML written by
a patch's own tests is parsed where it can do no harm. The job that signs the
audit bundle then reads only JSON, and treats the numbers as the test job's
claim: whether the job passed comes from GitHub's own job results.

  junit_summary.py junit.xml > junit.json
"""
import json
import sys
import xml.etree.ElementTree as ET

# Parsed in the job that already ran the patch's own tests: hostile XML here can
# do nothing that code could not. The job that signs the bundle never parses it.
root = ET.parse(sys.argv[1]).getroot()  # nosemgrep: use-defused-xml-parse
suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
summary = {k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
print(json.dumps({"file": sys.argv[1], **summary}))
