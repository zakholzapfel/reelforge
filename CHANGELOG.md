# Changelog

## 0.5.0 — 2026-10-16

- Added locked downloads and source builds for bundled FFmpeg/ffprobe with libx264, plus a verified Deno payload.
- Include source archives, tool versions, configuration logs, and available runtime license notices in desktop builds.
- Refuse missing, changed, or wrong-platform tool payloads before packaging.
- Exercise bundled tools with an empty system PATH, including actual H.264/AAC encoding and probing.
- Added Windows installer packaging with shortcuts and a verified Microsoft WebView2 bootstrapper.
- Added a one-time Mac publisher launcher to create the GitHub repository and upload source.
- Configure platform build jobs on the initial source push; document the free Mac DMG route without paid signing/notarization.

This download contains source and build recipes. Mac/Windows GUI checks and a review of Deno transitive dependency notices remain before public binary release.

## 0.4.1 — 2026-10-16

- Switched the app, companion website, demo, and guide to black backgrounds with charcoal panels.
- Added Mac DMG preview packaging with a drag-to-Applications target and preserved framework symlinks.
- Clarified the difference between the available source setup package and a finished standalone download.

The DMG build recipe has not yet been run or tested on a Mac. Preview builds still require separate FFmpeg/ffprobe and Deno installation. A finished no-command-line release needs bundled media tools, platform testing, and Mac signing/notarization.

## 0.4.0 — 2026-10-16

- Added an optional native desktop window, app icons, and per-user Mac/Windows shortcut setup.
- Kept browser mode available and retained the existing local queue and date-review database.
- Pause pending jobs when the desktop window closes.
- Added frozen-executable yt-dlp dispatch, native build scripts, and platform build workflows.
- Added a companion website with a fictional interactive demo, guide, and source download.
- Included ErsatzTV alongside Plex and Fieldstation42 as folder-based use cases.

Desktop downloads are source setup packages. Prebuilt signed native installers are not included.

## 0.3.2 — 2026-10-16

- Added Help & guide with a quick start, searchable FAQ, troubleshooting, project purpose, and dependency credits.
- Added contextual help beside source import and date research.
- Explained confidence totals versus date matches, hidden selections, and scan versus research behavior with a concrete example.
- Included a user guide for GitHub and offline reading.
- Adjusted narrow-screen navigation for the additional help page.

This is a documentation/UI release. The tested 0.3.1 download and date-research engine is retained. Autonomous web search, OCR, and transcription are not part of this release. No paid API or account is required.

## 0.3.1

- Made date confidence and period counts clickable.
- Added all-likely and all-documented views and per-video period labels.
- Verified that switching date views preserves download selections.

## 0.3.0

- Generalized source imports, naming defaults, and date-reference catalogues.
- Added configurable JSON-index mappings and user-imported reference libraries.
- Removed subject-specific defaults from the runtime workflow.
