#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! -f $1 ]]; then
  echo "usage: bash scripts/smoke_install.sh <wheel-or-sdist>" >&2
  exit 2
fi

artifact_dir=$(cd "$(dirname "$1")" && pwd -P)
artifact="$artifact_dir/$(basename "$1")"
smoke_dir=$(mktemp -d "${TMPDIR:-/tmp}/my-guy-smoke.XXXXXX")
trap 'rm -rf "$smoke_dir"' EXIT

python3 -m venv "$smoke_dir/venv"
"$smoke_dir/venv/bin/python" -m pip install --disable-pip-version-check "$artifact"
export MY_GUY_HOME="$smoke_dir/state"

# A source checkout can shadow an installed wheel. All CLI calls below run elsewhere.
cd "$smoke_dir"
unset PYTHONPATH
my_guy="$smoke_dir/venv/bin/my-guy"
"$smoke_dir/venv/bin/python" -c 'from pathlib import Path; import router, sys; assert Path(router.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())'
installed_version=$("$smoke_dir/venv/bin/python" -c 'from importlib.metadata import version; print(version("agent-router"))')
test "$("$my_guy" --version)" = "my-guy $installed_version"
if doctor_output=$("$my_guy" doctor); then
  doctor_exit=0
else
  doctor_exit=$?
fi
test "$doctor_exit" -eq 1
printf '%s\n' "$doctor_output" | "$smoke_dir/venv/bin/python" -c 'import json, sys; data = json.load(sys.stdin); assert data["status"] == "needs_capabilities" and data["trusted_root_count"] == 0'
printf '%s\n' 'Review authentication security' | "$my_guy" route --stdin --json | "$smoke_dir/venv/bin/python" -c 'import json, sys; assert json.load(sys.stdin)["status"] == "clarify"'

for harness in claude codex opencode; do
  root="$smoke_dir/$harness/skills"
  "$my_guy" install "$harness" --root "$root" --allow-custom-root --dry-run
  test ! -e "$root/my-guy/SKILL.md"
  "$my_guy" install "$harness" --root "$root" --allow-custom-root
  test -f "$root/my-guy/SKILL.md"
  "$my_guy" status "$harness" --root "$root" --json
  if doctor_output=$("$my_guy" doctor --harness "$harness" --root "$root"); then
    doctor_exit=0
  else
    doctor_exit=$?
  fi
  test "$doctor_exit" -eq 1
  printf '%s\n' "$doctor_output" | "$smoke_dir/venv/bin/python" -c 'import json, sys; data = json.load(sys.stdin); assert data["status"] == "needs_capabilities" and data["trusted_root_count"] == 0 and data["installation"]["state"] == "ready"'
  "$my_guy" disable "$harness" --root "$root" --allow-custom-root
  "$my_guy" rollback "$harness" --root "$root" --allow-custom-root
  test -f "$root/my-guy/SKILL.md"
  "$my_guy" uninstall "$harness" --root "$root" --allow-custom-root
  test ! -e "$root/my-guy/SKILL.md"
done
