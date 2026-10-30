# ReelForge

**Find it. Name it. File it.**

A general-purpose, local media-ingestion app by **Zakery Holzapfel**. Scan supported video sources, review metadata, preview output paths, and download organized collections to your computer or an already mounted network share.

**v0.5.0 desktop source preview.** Open a native app window with a custom icon and shortcuts, or keep using the local browser interface. Processing runs on your computer. Source setup requires Python and media tools; prebuilt native installers are not included.

## Why ReelForge exists

Finding videos, merging streams, fixing names, and organizing folders used to require separate collection-specific scripts. ReelForge puts those steps into one reusable workflow with previews and a persistent queue. It grew from local collection work and can prepare media folders for Plex, ErsatzTV, and Fieldstation42. It is designed for general use.

## Help

Open **Help & guide** in the app for a quick start, searchable FAQ, date/filter examples, troubleshooting, and credits. Help is also linked beside source import and date research.

- [User guide and FAQ](docs/USER-GUIDE.md)
- [Date research and reference format](docs/DATE-RESEARCH.md)
- [Changelog](CHANGELOG.md)

This release is free to run and has no paid API, subscription, or account requirement. It does not autonomously search the web, watch videos, perform OCR, or transcribe audio.

## GitHub and bundled builds

The **Publish-to-GitHub-macOS.command** launcher creates the public `zakholzapfel/reelforge` repository and uploads the source after a review prompt. It needs GitHub CLI and the publisher’s account login. The first push starts Apple Silicon Mac, Intel Mac, and Windows build jobs. See [the desktop guide](docs/DESKTOP.md) for exact steps and current release status. End users will not run this publisher script.

The native build includes Python, FFmpeg, ffprobe, and Deno. It produces a drag-to-Applications Mac DMG or a Windows Setup.exe. This ZIP is the source package; it does not contain those finished installers. Preview builds need native GUI tests and dependency-notice review before public binary distribution.

## Desktop app setup

After installing the prerequisites below, run **Install-Desktop-macOS.command** or **Install-Desktop-Windows.cmd** once. This creates ReelForge in your home Applications folder on Mac, or Start menu/Desktop shortcuts on Windows. Keep the extracted folder in place. Subsequent launches use the icon and open their own window.

The intended finished Mac download is a DMG: drag ReelForge into Applications and launch it without Terminal setup. That download is not available yet. The build pipeline now bundles the media tools; a real Mac build and GUI test are still needed. We are using a DMG without paid signing/notarization, with documented first-launch warnings.

See [Desktop setup and native builds](docs/DESKTOP.md). The original launchers still open browser mode. A companion website and fictional interactive demo introduce the workflow; actual downloading runs locally.

## Start

Requirements: Python 3.11+, FFmpeg and ffprobe on PATH. Install Deno for current YouTube extraction. An internet connection is needed for initial installation and online sources.

### Windows

Install Python 3.11 or later, then install the media tools:

~~~powershell
winget install Gyan.FFmpeg
winget install DenoLand.Deno
~~~

Open a fresh terminal after installation. Extract the project and run **Launch-Windows.cmd**.

### macOS

~~~sh
brew install python ffmpeg deno
~~~

Extract the project and run **Launch-macOS.command**. If Finder reports execution privileges, type **bash** followed by a space in Terminal, drag the launcher into Terminal, and press Return.

### Manual installation

~~~sh
python -m venv .venv
# Windows:
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m reelforge
# macOS / Linux:
.venv/bin/python -m pip install -e .
.venv/bin/python -m reelforge
~~~

Keep the terminal open in browser mode, or the app window open in desktop mode. Closing desktop mode pauses pending jobs.

## A general workflow

1. Import a supported playlist/video URL, scan a website, map a JSON index, or load a manifest.
2. Search/exclude titles, filter by duration, select entries, and edit metadata.
3. Choose a local or mounted-network destination.
4. Pick numbered filenames, season/episode naming, supplied source filenames/folders, or a custom template.
5. Inspect the exact paths and resolve missing metadata or filename collisions.
6. Queue the selection and monitor download/merge/delivery progress.
7. Pause, resume, retry, or cancel jobs; export manifests and reports.

New scans initially select all entries. Filters affect visible rows without clearing hidden selections. Date confidence counts cover the entire collection. Click **likely**, **documented**, or another count to see those videos; click **outside target period** to see dated videos excluded by your range. Each dated row labels its relationship to the target period. Viewing a count does not change your download selection. Title and duration filters still apply.

Date research clears the download selection; its **Select matches only** button replaces earlier selections explicitly.

## Source types

| Source | Use |
| --- | --- |
| Playlist / video | A URL supported by yt-dlp, including supported channels/playlists |
| Website | Static HTML links and embeds, with a same-site link filter and bounded traversal |
| JSON index | A JSON array or nested array, using configurable URL/title/metadata paths |
| Manifest | A reusable JSON list containing video URLs, metadata, and optional ordered parts |

No sports team, show, channel, or franchise is built into the default workflow.

### JSON indexes

Paste the index URL and select JSON index. Set:

- **Array path:** blank for a root array, or a dotted path such as data.videos.
- **Video URL field:** for example media.url.
- **Title field:** for example name.
- Optional season, episode, year, filename, and subfolder mappings.
- Optional base URL for relative video links.

No source-provided JavaScript is executed. Entries with missing/invalid URLs are skipped with warnings. Review any source-specific availability rules yourself.

## Naming

~~~text
Collection/001 - Video title.mkv
My Series/Season 01/My Series - S01E01 - Episode title.mkv
Sessions/Day 1/Opening Session.mkv
~~~

Custom templates support title, show, collection, index, season, episode, year, id, filename, and subfolder. Use :02d or :03d for zero-padded numbers. Templates omit the extension.

Season/episode labels are recognized generically. Use named regex groups (season, episode, year, title) to handle unusual source conventions or remove a source-title prefix.

Source filenames / folders uses supplied filename and subfolder fields. Without those fields, it uses the video title directly in the chosen root folder.

## Date research

Research original release/air dates from explicit title claims, optional description lookups, reference records you import, and your own reviews.

- **No subject-specific catalogue is active by default.**
- Import references for any collection through Reference library.
- Review evidence links and conflicting claims.
- Set your own year range; there is no preselected decade.
- Select documented matches or documented + likely matches.
- Unknown/conflicting dates and ranges crossing the selected boundaries are excluded from automatic selection.
- Upload timestamps are not treated as original dates.
- Saved research and reviews survive rescans of an unchanged source and app restarts.

See [docs/DATE-RESEARCH.md](docs/DATE-RESEARCH.md) for the reference schema and detailed behavior. The app does not automatically watch/transcribe footage or search the whole web.

## Video and audio

- **MKV:** merge separate video/audio streams while preserving codecs.
- **MP4:** convert to H.264/AAC for broad playback compatibility.
- **Join selected videos:** combine ordered entries into one file.
- **Normalize join:** convert parts to 720p/30 fps H.264/stereo AAC; silent tracks are added for parts without audio.
- **Fast join:** require compatible source stream formats.

Joining follows collection order, not checkbox click order. TV collections are sorted by recognized season/episode. A manifest's ordered parts array can also represent one multi-part item.

Resolution preferences cap known-height formats. Direct files without resolution metadata remain at their source resolution. Conversion can take CPU time.

## Persistence and delivery

The SQLite database is stored under your home folder in .reelforge/queue.sqlite3. REELFORGE_DATA_DIR can override that location. Reference-library settings and date reviews are stored there too.

Incomplete downloads are staged under DESTINATION/.reelforge/staging/JOB-ID. Completed staging is removed. Paused/failed/cancelled staging is kept for retry and can be removed manually when no longer needed.

On restart, unfinished jobs are paused. Resuming reuses partial downloads where supported. Existing final files are kept and marked skipped; the app does not assume arbitrary existing files belong to the source.

Final delivery uses an atomic hard link where supported and an exclusive copy on filesystems that do not support links. A forced process kill during a network-share copy can leave a partial final file; inspect skipped files after such a crash.

## Updating

Stop the old app and extract this release into its own folder. The launcher installs this release once, including when an older virtual environment exists. Your existing queue and saved date reviews remain in the same home-folder database.

The former subject-specific archive control has been replaced by the generic JSON-index importer. Old queued jobs and manifests still contain their destination metadata and can continue through the normal download engine. Optional reference packs are imported explicitly; none is loaded by default.

## Limits

- Site compatibility depends on yt-dlp and source access. DRM and unsupported extractors are not handled.
- Website scanning reads static HTML, at most 100 pages at depth 0–2. Dynamic sites need a supported URL, JSON index, or manifest.
- The GUI imports up to 500 entries per scan; the API supports 1,000.
- No cloud account/API key is required; there is no GUI cookie/login import.
- No recurring scheduling, remote access, signed native installer, or automatic media-server refresh.
- Source desktop setup requires Python 3.11+, separate FFmpeg/ffprobe and Deno, and the platform webview runtime. Standalone build scripts are included; native GUI checks on Mac/Windows remain required.
- Source dates remain evidence-based suggestions rather than automatic verification of the exact footage.
- Windows/macOS execution and actual NAS behavior require checks on your hardware.

## Development

~~~sh
python -m pip install -e ".[dev]"
python -m pytest -q
python -m playwright install chromium
python scripts/check_gui.py
~~~

Tests use generated videos hosted locally to verify actual download, audio/video merging, joining, output validation, and delivery. See [docs/VALIDATION.md](docs/VALIDATION.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and [docs/PORTFOLIO.md](docs/PORTFOLIO.md).

ReelForge's contributions are its UI/API, generic source mapping, naming planner, queue, date evidence/review workflow, and delivery controls. [yt-dlp](https://github.com/yt-dlp/yt-dlp) provides extraction; [FFmpeg](https://ffmpeg.org/) provides media processing. Use media you are authorized to download. Dependencies retain their own licenses.

