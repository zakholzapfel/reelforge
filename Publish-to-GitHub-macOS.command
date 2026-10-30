#!/bin/bash
# One-time publisher setup; people downloading the finished app never run this.
set -euo pipefail
cd "$(dirname "$0")"
finish() { read -r -p "Press Return to close. " _ || true; }
trap finish EXIT
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
for tool in git gh; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing $tool. Install Apple Command Line Tools for git, and GitHub CLI for gh."
    echo "With Homebrew, install GitHub CLI using: brew install gh"
    exit 1
  fi
done
test -f pyproject.toml && test -f reelforge/app.py || { echo "Keep this script inside the extracted ReelForge folder."; exit 1; }
if ! gh auth status --hostname github.com >/dev/null 2>&1; then
  gh auth login --hostname github.com --git-protocol https --web --scopes repo,workflow
fi
login="$(gh api user --jq .login)"
if [ "$login" != "zakholzapfel" ]; then
  echo "Sign into zakholzapfel before publishing; current account is $login."
  exit 1
fi
repository="zakholzapfel/reelforge"
echo "This creates the PUBLIC repository https://github.com/$repository and uploads this project."
echo "The first push starts the included build checks. It does not publish a downloadable release."
read -r -p "Create and upload ReelForge? [y/N] " answer
case "$answer" in y|Y|yes|YES) ;; *) exit 0 ;; esac
if git rev-parse --show-toplevel >/dev/null 2>&1; then
  if [ "$(git rev-parse --show-toplevel)" != "$(pwd -P)" ]; then
    echo "This folder is inside another Git repository. Extract ReelForge into its own folder first."
    exit 1
  fi
else
  git init -b main
fi
if git remote get-url origin >/dev/null 2>&1; then
  echo "An origin remote is already configured. No repository was changed."
  echo "If you previously ran this script, send the repository link so we can inspect its status."
  exit 1
fi
if gh repo view "$repository" >/dev/null 2>&1; then
  echo "$repository already exists. No files were pushed; send its link so we can continue safely."
  exit 1
fi
if ! git config user.name >/dev/null; then git config user.name "Zakery Holzapfel"; fi
if ! git config user.email >/dev/null; then
  account_id="$(gh api user --jq .id)"
  git config user.email "$account_id+$login@users.noreply.github.com"
fi
git add --all
if ! git diff --cached --quiet; then git commit -m "Add ReelForge desktop app and bundled build workflow"; fi
gh auth setup-git --hostname github.com
gh repo create "$repository" --public --description "Find it. Name it. File it. A local video collection app." --source=. --remote=origin --push
echo "Published source: https://github.com/$repository"
echo "Build progress: https://github.com/$repository/actions"
echo "Send the repository link back so the platform build results can be checked."
