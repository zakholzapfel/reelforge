"""Publish the exact tested artifacts; never rebuild or replace release binaries."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

RUN_ID = 40978180712
COMMIT = "ac1eef6b758a3f75876010eb5dd3ea4ad6d6efac"
TAG = "v0.5.0"
ARTIFACTS = {
    "ReelForge-macos-15": "ReelForge-0.5.0-macOS-arm64.dmg",
    "ReelForge-macos-15-intel": "ReelForge-0.5.0-macOS-x86_64.dmg",
    "ReelForge-windows-latest": "ReelForge-0.5.0-Windows-Setup.exe",
}


def gh(*arguments, check=True):
    return subprocess.run(["gh", *map(str, arguments)], check=check, capture_output=True, text=True)


def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_payload(directory, filename):
    records = {}
    for line in (directory / "SHA256SUMS.txt").read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        name = name.removeprefix("*")
        if Path(name).name != name or len(digest) != 64:
            raise ValueError("Unsafe or invalid checksum entry")
        records[name] = digest
    payload = directory / filename
    if filename not in records or checksum(payload) != records[filename]:
        raise ValueError(f"Artifact checksum failed: {filename}")
    return payload, records[filename]


def main():
    repository = os.environ["GH_REPO"]
    if repository != "zakholzapfel/reelforge":
        raise RuntimeError("This release is bound to zakholzapfel/reelforge")
    run = json.loads(gh("api", f"repos/{repository}/actions/runs/{RUN_ID}").stdout)
    if run["status"] != "completed" or run["conclusion"] != "success" or run["head_sha"] != COMMIT:
        raise RuntimeError("Release source run must be successful and match the tested commit")
    if run["path"] != ".github/workflows/desktop-build.yml":
        raise RuntimeError("Unexpected source workflow")
    with tempfile.TemporaryDirectory(prefix="reelforge-release-") as temporary:
        directory = Path(temporary)
        gh("run", "download", RUN_ID, "--repo", repository, "--dir", directory)
        assets, sums = [], []
        for artifact, filename in ARTIFACTS.items():
            payload, digest = verify_payload(directory / artifact, filename)
            assets.append(payload)
            sums.append(f"{digest}  {filename}\n")
        checksums = directory / "SHA256SUMS.txt"
        checksums.write_text("".join(sums))
        assets.append(checksums)
        notices = Path(".github/release/THIRD-PARTY-NOTICES.md")
        assets.append(notices)
        existing = gh("release", "view", TAG, "--repo", repository, "--json", "url", check=False)
        if existing.returncode == 0:
            # An existing public asset is immutable here. Validate it instead of overwriting it.
            verification = directory / "published"
            verification.mkdir()
            gh("release", "download", TAG, "--repo", repository, "--pattern", "SHA256SUMS.txt", "--dir", verification)
            if (verification / "SHA256SUMS.txt").read_bytes() != checksums.read_bytes():
                raise RuntimeError("The existing release differs; refusing to overwrite it")
            print(json.loads(existing.stdout)["url"])
            return
        gh("release", "create", TAG, *assets, "--repo", repository, "--target", COMMIT,
           "--title", "ReelForge 0.5.0 — desktop preview", "--prerelease",
           "--notes-file", "docs/releases/v0.5.0.md")
        print(f"https://github.com/{repository}/releases/tag/{TAG}")


if __name__ == "__main__":
    main()
