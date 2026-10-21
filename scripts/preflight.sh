#!/usr/bin/env bash
# Pre-submission gate: run from the repository root before pushing.
# Exits non-zero on the first failed gate.
set -euo pipefail

step() { printf '\n== %s\n' "$1"; }

step "1/6 Lint, format and types"
ruff check .
ruff format --check .
mypy src

step "2/6 Tests and coverage"
pytest

step "3/6 Dependency vulnerabilities"
pip-audit -r requirements.txt

step "4/6 Secrets in tracked files"
if git grep -nIE "(AIza[0-9A-Za-z_-]{35}|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"; then
  echo "Possible secret found" >&2
  exit 1
fi
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo ".env is tracked" >&2
  exit 1
fi
echo "none found"

step "5/6 Repository size (limit 10 MB)"
git count-objects -vH | grep -E "size-pack|size:"
kb=$(du -sk .git | cut -f1)
[ "$kb" -lt 10240 ] || { echo ".git is ${kb} KB" >&2; exit 1; }

step "6/6 Single branch"
branches=$(git branch -a --format='%(refname:short)' | grep -v '^origin/HEAD' | sed 's#^origin/##' | sort -u | wc -l)
[ "$branches" -eq 1 ] || { echo "found $branches branches" >&2; exit 1; }
git branch -a

printf '\nAll gates passed.\n'
