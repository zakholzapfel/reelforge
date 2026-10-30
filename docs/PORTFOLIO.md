# Portfolio entry

## ReelForge — general-purpose local media ingestion

**Creator:** Zakery Holzapfel  
**Stack:** Python, FastAPI, SQLite, JavaScript, HTML/CSS, yt-dlp, FFmpeg, pywebview

### Problem

Preparing organized media collections involved repeated manual work: finding source videos, extracting metadata, naming episodes consistently, merging streams, and recovering failed transfers. Separate collection-specific scripts made that work difficult to reuse.

### Solution

ReelForge provides one content-neutral workflow for supported video URLs, playlists, websites, JSON indexes, and manifests. Users review metadata and exact output paths before running a persistent download queue. Optional date research retains evidence, conflicts, and reviewer decisions.

### Contribution

Designed and implemented the GUI/API, generic source mapping, metadata/naming planner, SQLite queue, subprocess controls, output verification, non-overwriting delivery, and configurable date-reference/review workflow.

yt-dlp and FFmpeg are upstream engines used for extraction and media processing.

The optional desktop window shares the existing engine; a companion website demonstrates selection and naming using fictional data. Folder-based use cases include Plex, ErsatzTV, and Fieldstation42.

### Engineering highlights

- Content-independent source types and configurable field mapping.
- Filename preview, collision detection, and path containment before downloading.
- Persistent queue with cancellation and partial-transfer recovery.
- User-imported reference data rather than hardcoded subject catalogues.
- Source-backed date claims, conservative confidence filters, and saved reviews.
- Loopback session authentication, origin checks, and text-safe output.
- Automated tests using real generated media fixtures and browser workflows.

### Release scope

v0.5.0 is a source release validated on Linux. Native Windows/macOS behavior, NAS mounts, and live source compatibility still need checks on the user's hardware.

### Short description

Built ReelForge, a general-purpose local media-ingestion app with configurable source mapping, metadata-driven naming previews, a persistent download queue, and evidence-based date review.

