# Validation — ReelForge v0.5.0

Validated in Linux/Python 3.12 on 2026-10-16.

**82 tests passed.** The suite covers actual generated-media downloads, separate video/audio merging, multipart conversion/joining, delivery, pause/resume, naming/path safety, generic source scans, nested JSON field mapping, user-supplied reference scopes and aliases, date claims/conflicts, persistent references/reviews, and API authentication.

Browser checks cover generic sample ingestion, metadata editing, folder browsing, a locally served JSON index with custom mappings, reference-file import/clear, queue controls, date research and selection, clickable confidence/period counts, per-row period labels, unchanged selections when switching date views, manual decisions restored after rescan, CSV exports, and narrow-screen layout. The help checks cover page navigation, contextual date help, FAQ filtering and its empty state, keyboard expansion, preserved selections when leaving Help, and mobile navigation.

No subject-specific adapter, catalogue, source URL, title-prefix rule, or era is enabled in the runtime. Optional collection data lives under examples and is loaded only by user import. Old jobs and reviews use the existing database; settings initialization is additive.

Run:

~~~sh
python -m pip install -e ".[dev]"
python -m pytest -q
python -m playwright install chromium
python scripts/check_gui.py
~~~

Windows/macOS launch behavior, real network shares, and source-specific access are still hardware/source-dependent. The app does not automatically verify the visual identity or historical date of footage. The installed test client emits an httpx deprecation warning; it does not fail the checks.

Desktop checks also reject corrupt tool downloads, unsafe source archives, absent tools, and system binaries being substituted for missing bundled tools. Desktop checks cover an authenticated loopback service, shutdown with queued jobs paused, packaged child-tool command dispatch, and a macOS shortcut with escaped paths and icon metadata. DMG staging checks preserve framework symlinks and the Applications target. The dark theme passed the existing GUI smoke checks and visual inspection. A prior v0.4.0 Linux PyInstaller build passed its bundled yt-dlp command and API startup/shutdown smoke checks. Mac/Windows native GUI behavior and installer signing were not tested here.


## Bundled desktop validation for 0.5.0

A Linux PyInstaller build completed with the locked FFmpeg 8.1.3/x264 source build and Deno 2.9.7 payload. The frozen yt-dlp version command and authenticated local-service startup/shutdown passed. With system PATH emptied, the frozen app executed bundled Deno, encoded a short H.264/AAC MP4, and verified both streams using bundled ffprobe. Tool permissions are normalized before checks and Mac signing.

The publisher launcher passed a simulated GitHub flow using real local Git and a fake gh executable; it did not contact GitHub or create a remote repository. Shell syntax and workflow YAML checks passed. The companion demo passed its three Node tests. Mac/Windows native builds and GUI testing remain; the Linux check does not establish that those installers work. Deno transitive notices require review before public binary release.
