# Contributing

Thank you for helping improve My Guy. It is a Python 3.11+ alpha with a harness-neutral core and thin Claude Code, Codex, and OpenCode adapters. Please open an issue to discuss architecture, provider execution, or trust-boundary changes before implementing them. Report vulnerabilities privately through [GitHub Security Advisories](SECURITY.md).

Create a feature branch from current `main`, keep the change focused, and submit a PR. A local setup is:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install build pytest
.venv/bin/python -m pytest -q
.venv/bin/python -m build
```

For packaging changes, run `bash scripts/smoke_install.sh dist/*.whl` and the source-distribution equivalent. Add fixtures for routing behavior and tests for lifecycle or trust changes. Keep external skill text as untrusted input. Do not include secrets, raw private prompts, or personal data in issues, tests, or logs. Describe user-visible behavior, limits, and recovery in the PR. Maintainers review releases and publish tags manually.
