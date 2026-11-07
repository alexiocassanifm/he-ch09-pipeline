# installments

A small Python library that splits invoice totals into installments and
formats amounts held in cents.

- Source is in `src/installments/`, tests in `tests/`.
- Run the suite with `python -m pytest -q`. It must pass before you stop.
- Every change in behaviour adds one line under "Unreleased" in `CHANGELOG.md`.
- Do not add dependencies. The dependency list belongs to people, not to agents:
  `requirements.lock` and `deps-allowlist.txt` are reviewed by a code owner.
- Never edit `.github/`, `.claude/`, `tools/`, `evals/` or `CLAUDE.md`. They are
  the pipeline and the harness that judge your work.
