"""Install a per-user app shortcut for this source checkout; no administrator rights."""
from __future__ import annotations
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def mac_app(destination: Path, python: Path):
    contents = destination / "Contents"
    (contents / "MacOS").mkdir(parents=True, exist_ok=True)
    (contents / "Resources").mkdir(exist_ok=True)
    with (contents / "Info.plist").open("wb") as output:
        plistlib.dump({"CFBundleName":"ReelForge", "CFBundleDisplayName":"ReelForge", "CFBundleIdentifier":"com.zakholzapfel.reelforge",
            "CFBundleVersion":"0.5.0", "CFBundleShortVersionString":"0.5.0", "CFBundleExecutable":"ReelForge",
            "CFBundleIconFile":"ReelForge.icns", "CFBundlePackageType":"APPL", "NSHighResolutionCapable":True,
            "LSMinimumSystemVersion":"12.0"}, output)
    shutil.copyfile(ROOT / "reelforge/static/ReelForge.icns", contents / "Resources/ReelForge.icns")
    launcher = contents / "MacOS/ReelForge"
    launcher.write_text("#!/bin/sh\nexport PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH\nexec "+shlex.quote(str(python))+" -m reelforge.desktop\n")
    launcher.chmod(0o755)


def ps_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def windows_shortcut(destination: Path, python: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    script = "$shell=New-Object -ComObject WScript.Shell\n$link=$shell.CreateShortcut("+ps_literal(destination)+")\n"
    script += "$link.TargetPath="+ps_literal(python)+"\n$link.Arguments='-m reelforge.desktop'\n"
    script += "$link.WorkingDirectory="+ps_literal(ROOT)+"\n$link.IconLocation="+ps_literal(ROOT / "reelforge/static/ReelForge.ico")+"\n$link.Save()\n"
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", "-"], input=script, text=True, check=True)


def main():
    python = Path(sys.executable)
    if sys.platform == "darwin":
        destination = Path.home() / "Applications/ReelForge.app"
        mac_app(destination, python)
        print("Installed:", destination)
        print("Keep the extracted ReelForge source folder in place; this shortcut uses its runtime.")
        subprocess.run(["open", str(destination)], check=True)
    elif os.name == "nt":
        python = python.with_name("pythonw.exe")
        start_menu = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/ReelForge.lnk"
        windows_shortcut(start_menu, python)
        print("Installed:", start_menu)
        # Ask the system for its actual Desktop directory, including OneDrive redirection.
        result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", "[Environment]::GetFolderPath('Desktop')"], capture_output=True, text=True, check=True)
        if result.stdout.strip():
            windows_shortcut(Path(result.stdout.strip()) / "ReelForge.lnk", python)
        print("Keep the extracted ReelForge source folder in place; these shortcuts use its runtime.")
        subprocess.Popen([str(python), "-m", "reelforge.desktop"])
    else:
        destination = Path.home() / ".local/share/applications/reelforge.desktop"
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Desktop-entry quoting differs from shell quoting.
        executable = str(python).replace("\\", "\\\\").replace('"', '\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
        icon = ROOT / "reelforge/static/icon-256.png"
        destination.write_text('[Desktop Entry]\nType=Application\nName=ReelForge\nComment=Prepare your local video library\nExec="'+executable+'" -m reelforge.desktop\nIcon='+str(icon)+'\nTerminal=false\nCategories=AudioVideo;Video;\n')
        destination.chmod(0o755)
        print("Installed:", destination)


if __name__ == "__main__":
    main()
