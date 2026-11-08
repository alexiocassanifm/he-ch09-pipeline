# he-ch09-pipeline

Companion repository for Chapter 9 of *Harness Engineering with Claude Code*:
a validation pipeline that treats every agent-produced patch as an untrusted
contribution, an audit bundle for every important run, and a nightly eval-set
graded out of the agent's reach. The library itself (`src/installments/`) is a
deliberately small target for the pipeline to judge.

The runs, the refused pull requests and the attestations described in the
chapter are this repository's own: see the Actions tab and the closed pull
requests.

## Using it as a template

"Use this template" copies the files only. Rulesets, Actions policies, code
scanning settings and secrets do not travel with a template, so set them up in
your copy:

1. **Code owners.** Replace `@alexiocassanifm` in `.github/CODEOWNERS` with the
   person or team who must approve changes to the pipeline and the harness.
2. **Lockfile.** Install the GitHub CLI extension and verify the lockfile:
   `gh extension install github/gh-actions-lock`, then `gh actions-lock --no-fix`.
   Run `gh actions-lock` after any change to a `uses:` line.
3. **Ruleset on `main`.** Apply the branch ruleset from the book's companion
   code (`ch09/ruleset.json`):
   `gh api -X POST repos/OWNER/REPO/rulesets --input ruleset.json`.
   It requires pull requests with code owner review, the test and bundle checks,
   and code scanning results from `Semgrep OSS` and `Gitleaks`.
4. **Actions policy.** Allow only the events this pipeline uses
   (`ch09/actions-policy.json`):
   `gh api -X POST repos/OWNER/REPO/actions/policies --input actions-policy.json`.
   "Require lockfile" is a toggle under Settings, Actions, Policies.
5. **Claude credential for the nightly job.** Run `claude setup-token` in a
   terminal and store the result with
   `gh secret set CLAUDE_CODE_OAUTH_TOKEN -R OWNER/REPO`. Chapter 9 compares this
   with a Console API key and with workload identity federation.
6. **First run.** Push to `main`, then start the eval-set by hand:
   `gh workflow run nightly.yml -f trials=1`. Check the `nightly-bundle`
   artifact before trusting a green run.

## What runs where

| Workflow | Trigger | Holds |
|---|---|---|
| `validate.yml` | every pull request and push to `main` | a read-only token; scanners upload SARIF |
| `nightly.yml` | 03:17 UTC and by hand | the agent job holds the model credential and a read-only token; grading and the bundle run in jobs without it |
| `liveness.yml` | 11:41 UTC and by hand | `actions: read`; fails if no nightly run succeeded in 36 hours |

The nightly agent job assumes a GitHub-hosted `ubuntu-24.04` runner. It
installs `bubblewrap` and `socat` and relaxes
`kernel.apparmor_restrict_unprivileged_userns` so Claude Code's credential
scrub and sandbox can work on a runner that is discarded after the job. Do not
copy that step to a self-hosted runner that outlives the job.
