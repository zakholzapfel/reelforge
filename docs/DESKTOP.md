# Desktop app and distribution

ReelForge runs in its own app window with an icon, or in a local browser tab. Both use the same authenticated local API, queue, naming planner, and media engine. No paid API or subscription is required.

## Mac DMG: the planned public download

A Mac DMG is practical for this app. Open the disk image, drag ReelForge.app onto Applications, eject the image, and launch ReelForge from Applications. Python, FFmpeg, ffprobe, and Deno are bundled by the native build. End users do not run setup scripts or install developer tools.

**Release status:** this source contains the bundled build pipeline. A finished Mac DMG is not included in the source ZIP. A successful native build and a real Mac GUI check are still required. CI artifacts are previews until those checks are complete.

We are using a free distribution route without paid Developer ID signing or Apple notarization. The build applies a local ad-hoc signature for bundle integrity; this does not identify a trusted publisher to Gatekeeper. Users can encounter a first-launch warning. If they trust the official download, Apple's supported exception is under **System Settings → Privacy & Security → Open Anyway**, after attempting to open the app. Availability depends on macOS version and device policy. Do not disable Gatekeeper or remove quarantine using Terminal as an installation step.

Apple's instructions: https://support.apple.com/102445

Signing identifies the publisher and makes tampering detectable. Notarization is Apple's automated malware/security check of a Developer ID signed app. Neither is needed to create the DMG. Apple's Developer Program currently costs US$99 per year, so it is deliberately excluded from this release process. End users pay no Apple fee to run ReelForge.

- https://developer.apple.com/developer-id/
- https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
- https://developer.apple.com/programs/enroll/

## Windows installer

The Windows build produces an application ZIP and a per-user Setup.exe. The installer places the app under the user's Programs directory, adds a Start menu shortcut, and offers a Desktop shortcut. Python and the media tools are bundled. A Microsoft-signed WebView2 bootstrapper is included; an internet connection may be needed if the runtime is missing. The bootstrapper's signature is checked on the build host before packaging. Windows publisher signing is not configured; SmartScreen warnings are possible. The Windows build and installer must be tested on Windows before being called stable.

## Publish the GitHub source once

Use **Publish-to-GitHub-macOS.command** in the extracted source package. This is a publisher tool for Zakery, not part of end-user installation.

1. Install Git and GitHub CLI (`gh`) on the Mac. Apple Command Line Tools supply Git; `brew install gh` supplies GitHub CLI if Homebrew is available.
2. Keep the launcher in the ReelForge source folder and run it. If Finder refuses execution, invoke the launcher with `bash` in Terminal.
3. Sign into GitHub in the browser when GitHub CLI asks. Use `zakholzapfel` and allow repository/workflow access.
4. Review the prompt. It creates the **public** `zakholzapfel/reelforge` repository and pushes this source. It refuses to overwrite an existing origin or repository.
5. Open the repository's **Actions** tab. The initial source push starts the build workflow for Apple Silicon Mac, Intel Mac, and Windows.
6. Download the workflow artifacts after the jobs succeed. Test the Mac GUI before adding the DMG to a public release.

The script includes no token. GitHub CLI handles account authentication. Do not paste credentials into the script, source files, or chat. If repository creation succeeded but the push failed, preserve the extracted folder and inspect the existing remote; the script intentionally stops on a repeat invocation rather than rewriting history.

No repository has been created merely by preparing this package. The connected GitHub tool cannot create repositories; this launcher performs that one-time operation on the publisher's computer.

## Build on a target platform

Use a fresh build environment with Python 3.12. Python 3.11+ remains supported for running the source app; the source-extraction/build helper targets Python 3.12.

```sh
python -m venv .build-venv
# Activate the environment using the command appropriate for your OS.
python -m pip install -e ".[desktop,build]"
python scripts/prepare_tools.py
bash scripts/build_media_tools.sh
python scripts/prepare_tools.py --finalize
python scripts/build_desktop.py
```

The media build needs a C compiler, GNU make, and pkg-config. On Windows, run only the shell media-build step in MSYS2 MINGW64. Run the Python steps with the regular Windows Python environment. The included workflow handles this distinction and prepares Inno Setup and Microsoft's WebView2 bootstrapper. On a local Windows build, also run `scripts/prepare_windows_webview.ps1` and install Inno Setup 6.3+ before the final build step.

The workflow creates preview artifacts, not a published GitHub release. Native apps must be built on the target OS and architecture. The Mac ZIP and DMG preserve framework symlinks. Generated files include SHA256SUMS.txt and per-platform preview notes. Build inputs are locked by version, commit, and SHA-256 in scripts/tools.lock.json; nothing downloads from a floating “latest” tool URL during builds.

### Build checks

The build refuses absent, changed, or wrong-platform tool payloads. It exercises the frozen yt-dlp dispatch, authenticated local API startup/shutdown, and a bundled-tools check with an empty system PATH. The latter executes Deno JavaScript and creates/probes a short H.264/AAC video using only the bundled FFmpeg and ffprobe.

These checks cannot verify native window rendering, dialogs, Gatekeeper behavior, or an installed Windows shortcut. Those require target-platform GUI testing.

### Media tool scope and notices

The media build enables libx264 and the native AAC encoder. It builds static FFmpeg libraries and disables optional auto-detected dependencies to avoid linking to build-host Homebrew/MSYS2 packages. Mac builds enable Secure Transport and Windows builds enable Schannel for native TLS support. The Linux QA recipe does not add TLS support to FFmpeg. This lean build is intended for normal downloaded files and the app's merge/convert/join workflows; specialist streaming/hardware codecs are not promised.

Native packages include the exact FFmpeg/x264 source archives, their license texts, configure instructions and logs, and a manifest recording pre-packaging tool versions and checksums. The separate programs retain their own licenses; ReelForge source is MIT licensed. Installed Python dependency metadata and available license files, including Python and PyInstaller notices, are collected into the app. Deno's own MIT license is included; its transitive dependency notices still require a distribution review before a public binary release. These are preview artifacts until that review and platform GUI testing are complete.

For an explicitly incomplete developer build only, `python scripts/build_desktop.py --without-media-tools` skips media bundling. Its output filename includes `incomplete`; it must not be advertised as the end-user download.

## Run the source preview now

The source ZIP remains runnable with Python 3.11+, FFmpeg/ffprobe, and Deno installed separately. Windows desktop mode also requires Microsoft WebView2. These setup requirements apply to the source ZIP, not the intended bundled DMG or Setup.exe.

Extract the source into a permanent folder. Run **Install-Desktop-macOS.command** or **Install-Desktop-Windows.cmd** once. Initial setup needs internet access to install Python dependencies. On Mac it creates a shortcut app in `~/Applications`; Windows receives Start menu/Desktop shortcuts. Keep the extracted folder in place because those source shortcuts use its virtual environment. Rerun source setup after moving or updating the folder.

Browser mode is still available through **Launch-macOS.command**, **Launch-Windows.cmd**, or `python -m reelforge`. Keep the terminal open while browser-mode jobs run. Linux desktop mode requires a supported pywebview GTK/Qt renderer and distribution-specific libraries.

## Closing and reopening

Closing the desktop window asks for confirmation when jobs are pending, pauses those jobs, and stops the local service. Reopen and resume explicitly. Queue state, imported references, and date reviews use the existing `~/.reelforge` database. Run one instance at a time. Logs are under `~/.reelforge/desktop.log`; session token URLs are not written there.

## Media-library use cases

Save files for **Plex, ErsatzTV, Fieldstation42**, or another local library. ReelForge prepares media and naming. It does not configure those independent projects, mount shares, refresh libraries, or create channels.
