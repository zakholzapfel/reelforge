"""Fetch locked tool inputs, then validate the built payload. Build-host use only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "scripts/tools.lock.json").read_text())


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url, checksum, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or digest(destination) != checksum:
        temporary = destination.with_suffix(destination.suffix + ".partial")
        try:
            with urlopen(url, timeout=120) as response, temporary.open("wb") as stream:
                shutil.copyfileobj(response, stream)
            if digest(temporary) != checksum:
                raise ValueError(f"Checksum mismatch: {destination.name}")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return destination


def extract_source(archive, destination):
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    with tarfile.open(archive) as source:
        # A source archive must contain one root, regular files, and directories.
        members = source.getmembers()
        roots = set()
        for member in members:
            parts = Path(member.name).parts
            if not parts or Path(member.name).is_absolute() or ".." in parts or not (member.isfile() or member.isdir()):
                raise ValueError("Unsafe source archive member")
            roots.add(parts[0])
        if len(roots) != 1:
            raise ValueError("Source archive must have one root")
        source.extractall(destination, members=members, filter="data")
    return destination / roots.pop()


def deno_target():
    architecture = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "aarch64", "aarch64": "aarch64"}.get(platform.machine().lower())
    system = {"Darwin": "apple-darwin", "Windows": "pc-windows-msvc", "Linux": "unknown-linux-gnu"}.get(platform.system())
    if not architecture or not system:
        raise ValueError("Unsupported desktop build platform")
    return f"deno-{architecture}-{system}.zip"


def prepare(directory, cache):
    (directory / "bin").mkdir(parents=True, exist_ok=True)
    notices = directory / "notices"
    notices.mkdir(exist_ok=True)
    sources = notices / "sources"
    sources.mkdir(exist_ok=True)
    for name, suffix in [("ffmpeg", ".tar.xz"), ("x264", ".tar.gz")]:
        item = LOCK[name]
        archive = download(item["url"], item["sha256"], cache / (name + suffix))
        shutil.copy2(archive, sources / (name + suffix))
        tree = extract_source(archive, directory / "src" / name)
        (directory / (name + "-source.txt")).write_text(str(tree.resolve()))
        for source in tree.iterdir():
            if source.is_file() and source.name.upper().startswith(("COPYING", "LICENSE", "AUTHORS")):
                shutil.copy2(source, notices / (name + "-" + source.name))
    asset = LOCK["deno"]["assets"][deno_target()]
    archive = download(asset["url"], asset["sha256"], cache / deno_target())
    executable = "deno.exe" if os.name == "nt" else "deno"
    temporary = directory / "bin" / (executable + ".partial")
    try:
        with zipfile.ZipFile(archive) as source:
            with source.open(executable) as stream, temporary.open("wb") as target:
                shutil.copyfileobj(stream, target)
        temporary.chmod(0o755)
        temporary.replace(directory / "bin" / executable)
    finally:
        temporary.unlink(missing_ok=True)
    license_url = f'https://raw.githubusercontent.com/denoland/deno/{LOCK["deno"]["version"]}/LICENSE.md'
    # Retain the runtime's own license. Dependency notices need release review.
    with urlopen(license_url, timeout=60) as response:
        (notices / "Deno-LICENSE.md").write_bytes(response.read())
    (notices / "tools.lock.json").write_text(json.dumps(LOCK, indent=2))
    (notices / "README.txt").write_text(
        "ReelForge invokes FFmpeg, ffprobe, and Deno as separate programs.\n"
        "FFmpeg and x264 sources used for this build are in sources/. Their GPL terms are included here.\n"
        "Build instructions and exact configure arguments are in build_media_tools.sh.\n"
        "Deno's own MIT license is in Deno-LICENSE.md.\n"
        "Before public distribution, review Deno's transitive dependency notices against its locked release.\n"
        "ReelForge source remains under its MIT license; dependencies retain their own licenses.\n"
    )
    shutil.copy2(ROOT / "scripts/build_media_tools.sh", notices)
    print("Locked sources and Deno prepared:", directory)


def finalize(directory):
    tools = {}
    for name in ["ffmpeg", "ffprobe", "deno"]:
        path = directory / "bin" / (name + (".exe" if os.name == "nt" else ""))
        if not path.is_file():
            raise ValueError(f"Missing bundled {name}")
        result = subprocess.run([str(path), "--version" if name == "deno" else "-version"], check=True,
                                capture_output=True, text=True, timeout=30)
        tools[name] = {"filename": path.name, "sha256": digest(path), "version": result.stdout.splitlines()[0]}
    encoders = subprocess.run([str(directory / "bin" / tools["ffmpeg"]["filename"]), "-hide_banner", "-encoders"],
                              check=True, capture_output=True, text=True, timeout=30).stdout
    if "libx264" not in encoders or " aac " not in encoders:
        raise ValueError("Bundled FFmpeg must provide libx264 and AAC")
    manifest = {"platform": platform.system(), "architecture": platform.machine(), "tools": tools,
                "inputs": LOCK, "sources_included": True}
    (directory / "notices/manifest.json").write_text(json.dumps(manifest, indent=2))
    print("All bundled tools validated.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "build/media")
    parser.add_argument("--cache", type=Path, default=ROOT / "build/downloads")
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    if args.finalize:
        finalize(args.directory.resolve())
    else:
        prepare(args.directory.resolve(), args.cache.resolve())


if __name__ == "__main__":
    main()
