#!/usr/bin/env python3
"""Manual release gate for a tagged Git URL, not a host-agent usefulness test."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import venv


TAG = "v0.1.0"
VERSION = "0.1.0"
URL = f"git+https://github.com/indhra/my-guy.git@{TAG}"
SOURCE_URL = "https://github.com/indhra/my-guy.git"
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")


class ValidationError(RuntimeError):
    """The requested release identity or installed artifact is invalid."""


def validate_gate(
    ref: str, event_sha: str, expected_sha: str, tag_type: str,
    peeled_sha: str, checkout_sha: str,
) -> None:
    if ref != "refs/heads/main":
        raise ValidationError("dispatch must run on main")
    if not SHA_RE.fullmatch(expected_sha):
        raise ValidationError("expected_sha must be a lowercase 40-character commit SHA")
    if event_sha != expected_sha or checkout_sha != expected_sha:
        raise ValidationError("dispatch, checkout, and expected SHA must match exactly")
    if tag_type != "tag":
        raise ValidationError(f"{TAG} must be an annotated tag")
    if peeled_sha != expected_sha:
        raise ValidationError(f"{TAG} does not peel to expected_sha")


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def guard() -> str:
    expected = os.environ.get("EXPECTED_SHA", "")
    try:
        tag_type = git("cat-file", "-t", f"refs/tags/{TAG}")
        peeled = git("rev-parse", f"refs/tags/{TAG}^{{}}")
        checkout = git("rev-parse", "HEAD")
    except subprocess.CalledProcessError as exc:
        raise ValidationError(f"missing or unreadable {TAG} tag/checkout") from exc
    validate_gate(
        os.environ.get("GITHUB_REF", ""),
        os.environ.get("GITHUB_SHA", ""),
        expected, tag_type, peeled, checkout,
    )
    print(f"Guard passed: {TAG} annotated tag, main and checkout all resolve to {expected}")
    return expected


def run(command: list[str], *, cwd: Path, env: dict[str, str], input_text: str | None = None,
        expected_returncode: int = 0) -> str:
    result = subprocess.run(
        command, cwd=cwd, env=env, input=input_text, text=True, capture_output=True,
    )
    if result.returncode != expected_returncode:
        raise ValidationError(
            f"{command[0]} {command[1:3]} exited {result.returncode}, "
            f"expected {expected_returncode}: {result.stderr.strip()} {result.stdout.strip()}"
        )
    return result.stdout.strip()


def assert_installed(python: Path, cli: Path, expected_sha: str, *, cwd: Path,
                     env: dict[str, str]) -> None:
    probe = """
import importlib.metadata as metadata
import json
from pathlib import Path
import router
import sys
dist = metadata.distribution('agent-router')
assert Path(router.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
print(json.dumps({'version': dist.version, 'direct_url': json.loads(dist.read_text('direct_url.json'))}))
"""
    payload = json.loads(run([str(python), "-c", probe], cwd=cwd, env=env))
    validate_provenance(payload, expected_sha)
    if run([str(cli), "--version"], cwd=cwd, env=env) != f"my-guy {VERSION}":
        raise ValidationError("CLI version differs from installed distribution")


def validate_provenance(payload: dict, expected_sha: str) -> None:
    direct = payload["direct_url"]
    if payload["version"] != VERSION:
        raise ValidationError(f"installed version is not {VERSION}")
    if direct.get("url") != SOURCE_URL or direct.get("vcs_info") != {
        "vcs": "git", "requested_revision": TAG, "commit_id": expected_sha,
    }:
        raise ValidationError(f"installed package provenance does not match {TAG}@{expected_sha}: {direct}")


def exercise_cli(cli: Path, sandbox: Path, env: dict[str, str]) -> None:
    sandbox.mkdir()
    env = env.copy()
    env["MY_GUY_HOME"] = str((sandbox / "state").resolve())
    def call(*args: str, expected_returncode: int = 0, input_text: str | None = None) -> str:
        return run([str(cli), *args], cwd=sandbox, env=env,
                   expected_returncode=expected_returncode, input_text=input_text)

    def expect_status(harness: str, root: Path, state: str, owned: bool,
                      returncode: int) -> None:
        result = json.loads(call("status", harness, "--root", str(root), "--json",
                                 expected_returncode=returncode))
        if (result.get("state"), result.get("owned")) != (state, owned):
            raise ValidationError(f"{harness} expected {state}/owned={owned}: {result}")

    route = json.loads(call("route", "--stdin", "--json", input_text="Review this request"))
    if route.get("status") != "clarify":
        raise ValidationError(f"empty-capability route should clarify: {route.get('status')}")
    for harness in ("claude", "codex", "opencode"):
        root = (sandbox / harness / "skills").resolve()
        skill = root / "my-guy" / "SKILL.md"
        call("install", harness, "--root", str(root), "--allow-custom-root", "--dry-run")
        if skill.exists():
            raise ValidationError(f"{harness} dry-run wrote a skill")
        call("install", harness, "--root", str(root), "--allow-custom-root")
        if not skill.is_file():
            raise ValidationError(f"{harness} install did not write the skill")
        expect_status(harness, root, "ready", True, 0)
        doctor = json.loads(call("doctor", "--harness", harness, "--root", str(root),
                                 expected_returncode=1))
        if (doctor.get("status"), doctor.get("trusted_root_count"),
                doctor.get("installation", {}).get("state")) != ("needs_capabilities", 0, "ready"):
            raise ValidationError(f"{harness} doctor result is unexpected: {doctor}")
        call("disable", harness, "--root", str(root), "--allow-custom-root")
        expect_status(harness, root, "disabled", True, 1)
        call("rollback", harness, "--root", str(root), "--allow-custom-root")
        if not skill.is_file():
            raise ValidationError(f"{harness} rollback did not restore the skill")
        expect_status(harness, root, "ready", True, 0)
        call("uninstall", harness, "--root", str(root), "--allow-custom-root")
        if skill.exists():
            raise ValidationError(f"{harness} uninstall left the skill")
        expect_status(harness, root, "missing", False, 1)
        print(f"{harness}: disposable install/status/doctor/disable/rollback/uninstall passed")


def install_and_verify(expected_sha: str) -> None:
    print(f"Runner: {platform.system()} {platform.release()}, Python {platform.python_version()}",
          flush=True)
    temp_root = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="my-guy-tagged-", dir=temp_root) as raw:
        sandbox = Path(raw).resolve(strict=True)
        home = sandbox / "home"
        home.mkdir()
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env.update({
            "HOME": str(home),
            "XDG_CONFIG_HOME": str((home / "config").resolve()),
            "MY_GUY_HOME": str((home / "my-guy-state").resolve()),
            "PIPX_HOME": str((sandbox / "pipx-home").resolve()),
            "PIPX_BIN_DIR": str((sandbox / "pipx-bin").resolve()),
        })
        # Both installs consume the tagged Git URL, never the checked-out source tree.
        run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "pipx"],
            cwd=sandbox, env=env)
        run([sys.executable, "-m", "pipx", "install", "--python", sys.executable, URL],
            cwd=sandbox, env=env)
        pipx_python = sandbox / "pipx-home" / "venvs" / "agent-router" / "bin" / "python"
        pipx_cli = sandbox / "pipx-bin" / "my-guy"
        assert_installed(pipx_python, pipx_cli, expected_sha, cwd=sandbox, env=env)
        print(f"pipx: agent-router {VERSION}, {TAG}@{expected_sha}, PEP 610 provenance passed",
              flush=True)
        exercise_cli(pipx_cli, sandbox / "pipx-trial", env)
        venv_dir = sandbox / "venv"
        venv.EnvBuilder(with_pip=True).create(venv_dir)
        venv_python = venv_dir / "bin" / "python"
        run([str(venv_python), "-m", "pip", "install", "--disable-pip-version-check", URL],
            cwd=sandbox, env=env)
        assert_installed(venv_python, venv_dir / "bin" / "my-guy", expected_sha,
                         cwd=sandbox, env=env)
        print(f"venv: agent-router {VERSION}, {TAG}@{expected_sha}, PEP 610 provenance passed",
              flush=True)
        exercise_cli(venv_dir / "bin" / "my-guy", sandbox / "venv-trial", env)
    print(f"PASS: {TAG}@{expected_sha} URL installed with pipx and venv; CLI lifecycles passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("guard", "run"))
    args = parser.parse_args()
    try:
        expected_sha = guard()
        if args.action == "run":
            install_and_verify(expected_sha)
    except (ValidationError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Tagged install gate failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
