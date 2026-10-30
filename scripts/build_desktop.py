"""Build on the target OS. Requires pip install -e '.[desktop,build]'."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def ensure_tool_permissions(app, filenames):
    """Normalize copied executable modes before signing and smoke testing."""
    roots = [app / "_internal/tools", app / "tools", app / "Contents/Frameworks/tools", app / "Contents/Resources/tools"]
    for filename in filenames:
        matches = [root / filename for root in roots if (root / filename).is_file()]
        if not matches:
            raise RuntimeError(f"Packaged tool is missing: {filename}")
        for path in matches:
            path.chmod(0o755)


def stage_mac_dmg(app, destination, bundled=True):
    """Keep framework symlinks intact and provide the familiar Applications target."""
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(app, destination / app.name, symlinks=True)
    (destination / "Applications").symlink_to("/Applications", target_is_directory=True)
    (destination / "READ ME FIRST.txt").write_text(
        "Drag ReelForge.app into Applications, then open it there.\n"
        "This is an unsigned developer preview, not a finished public installer.\n" +
        ("Python, FFmpeg/ffprobe, and Deno are included. No Terminal setup is required.\n" if bundled else
         "Incomplete developer build: FFmpeg/ffprobe and Deno are separate requirements.\n") +
        "If macOS blocks first launch, use System Settings > Privacy & Security > Open Anyway.\n"
        "Only do this for a download you trust. Keep Gatekeeper enabled.\n"
        "Apple instructions: https://support.apple.com/102445\n"
        "See the project desktop guide for setup and release limitations.\n"
    )


def main():
    from collect_notices import collect
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools-dir", type=Path, default=ROOT / "build/media")
    parser.add_argument("--without-media-tools", action="store_true", help="Incomplete developer build only")
    args = parser.parse_args()
    system = platform.system()
    bundled = not args.without_media_tools
    media = args.tools_dir.resolve()
    if bundled:
        manifest_path = media / "notices/manifest.json"
        if not manifest_path.is_file():
            raise SystemExit("Prepare, build, and finalize the media tools first; see docs/DESKTOP.md.")
        manifest = json.loads(manifest_path.read_text())
        if manifest["platform"] != system or manifest["architecture"] != platform.machine():
            raise SystemExit("Media tools must be built on the same platform and architecture as the app.")
        for name in ["ffmpeg", "ffprobe", "deno"]:
            record = manifest["tools"][name]
            path = media / "bin" / record["filename"]
            with path.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != record["sha256"]:
                raise SystemExit(f"Bundled {name} changed after validation; finalize the media tools again.")
        for file in ["sources/ffmpeg.tar.xz", "sources/x264.tar.gz", "Deno-LICENSE.md", "build_media_tools.sh"]:
            if not (media / "notices" / file).is_file():
                raise SystemExit(f"Required tool source/notice is missing: {file}")
    notices = ROOT / "build/python-notices"
    if notices.exists():
        shutil.rmtree(notices)
    collect(notices)
    icon = ROOT / "reelforge/static" / ("ReelForge.icns" if system == "Darwin" else "ReelForge.ico")
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--name", "ReelForge",
        "--distpath", str(ROOT/"desktop-dist"), "--workpath", str(ROOT/"build/desktop"), "--specpath", str(ROOT/"build"),
        "--add-data", str(ROOT/"reelforge/static") + os.pathsep + "reelforge/static",
        "--add-data", str(notices) + os.pathsep + "notices/python",
        "--add-data", str(ROOT/"LICENSE") + os.pathsep + "notices/reelforge",
        "--collect-all", "yt_dlp", "--collect-all", "yt_dlp_ejs", "--collect-data", "webview",
        "--collect-submodules", "uvicorn", "--copy-metadata", "yt-dlp", "--copy-metadata", "reelforge",
        "--copy-metadata", "fastapi", "--copy-metadata", "uvicorn"]
    if bundled:
        command += ["--add-data", str(media / "notices") + os.pathsep + "notices/media"]
        for name in ["ffmpeg", "ffprobe", "deno"]:
            command += ["--add-binary", str(media / "bin" / manifest["tools"][name]["filename"]) + os.pathsep + "tools"]
    if system in {"Darwin", "Windows"}:
        command += ["--windowed", "--icon", str(icon)]
    if system == "Darwin":
        command += ["--osx-bundle-identifier", "com.zakholzapfel.reelforge", "--hidden-import", "webview.platforms.cocoa"]
    elif system == "Windows":
        command += ["--hidden-import", "webview.platforms.winforms"]
    command += [str(ROOT/"desktop_entry.py")]
    subprocess.run(command, cwd=ROOT, check=True)
    output = ROOT/"desktop-dist"
    if system == "Darwin":
        app = output/"ReelForge.app"
        executable = app/"Contents/MacOS/ReelForge"
    else:
        app = output/"ReelForge"
        executable = app/("ReelForge.exe" if system == "Windows" else "ReelForge")
    if bundled:
        ensure_tool_permissions(app, [manifest["tools"][name]["filename"] for name in ["ffmpeg", "ffprobe", "deno"]])
    if system == "Darwin":
        info_path = app / "Contents/Info.plist"
        info = plistlib.loads(info_path.read_bytes())
        info.update(CFBundleShortVersionString=VERSION, CFBundleVersion=VERSION)
        info_path.write_bytes(plistlib.dumps(info))
        # Metadata must be finalized before re-signing the bundle. No paid identity is used.
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    # Real child-tool and loopback service checks, without opening a GUI on CI.
    subprocess.run([str(executable), "--reelforge-ytdlp", "--version"], check=True, timeout=90)
    subprocess.run([str(executable), "--self-test"], check=True, timeout=90)
    if bundled:
        subprocess.run([str(executable), "--bundled-self-test"], check=True, timeout=180)
    notes = f"ReelForge {VERSION} desktop preview. Not signed with a publisher identity; target GUI testing is required.\n"
    notes += ("Python, FFmpeg/ffprobe, and Deno are included.\n" if bundled else "INCOMPLETE DEVELOPER BUILD: media tools must be installed separately.\n")
    (output/"README-DESKTOP.txt").write_text(notes)
    label = "" if bundled else "-incomplete"
    archive = output/f"ReelForge-{VERSION}-{system}-{platform.machine()}{label}.zip"
    if system == "Darwin":
        # Python and Cocoa frameworks contain symlinks; ditto preserves the app bundle.
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app), str(archive)], check=True)
        dmg = output / f"ReelForge-{VERSION}-macOS-{platform.machine()}{label}.dmg"
        with tempfile.TemporaryDirectory(prefix="reelforge-dmg-") as temporary:
            stage = Path(temporary) / "ReelForge"
            stage_mac_dmg(app, stage, bundled=bundled)
            subprocess.run(["hdiutil", "create", "-volname", "ReelForge", "-srcfolder", str(stage),
                "-format", "UDZO", "-ov", str(dmg)], check=True)
        print("Built Mac disk image preview:", dmg)
    else:
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for path in sorted(app.rglob("*")):
                if path.is_file():
                    z.write(path, path.relative_to(output))
            z.write(output/"README-DESKTOP.txt", "README-DESKTOP.txt")
    print("Built desktop preview:", archive)
    if system == "Windows" and bundled:
        compiler = shutil.which("ISCC") or str(Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Inno Setup 6/ISCC.exe")
        if not Path(compiler).is_file():
            raise SystemExit("The Windows installer needs Inno Setup 6 on the build host.")
        bootstrapper = ROOT / "build/webview2/MicrosoftEdgeWebview2Setup.exe"
        if not bootstrapper.is_file():
            raise SystemExit("Prepare Microsoft's verified WebView2 bootstrapper first.")
        subprocess.run([compiler, f"/DAppVersion={VERSION}", str(ROOT / "installer/ReelForge.iss")], check=True)
    artifacts = [p for p in output.glob(f"ReelForge-{VERSION}-*") if p.is_file() and p.suffix in {".zip", ".dmg", ".exe"}]
    (output / "SHA256SUMS.txt").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in sorted(artifacts)))


if __name__ == "__main__":
    main()
