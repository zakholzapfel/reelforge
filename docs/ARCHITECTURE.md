# Architecture

ReelForge is a local browser GUI over a Python/FastAPI backend. A loopback-only launcher opens a session-token URL; the frontend removes the token fragment and retains the session locally.

| Component | Responsibility |
| --- | --- |
| models.py | Typed sources, settings, metadata, evidence, and API requests |
| sources.py | yt-dlp metadata, bounded HTML discovery, mapped JSON indexes, manifests |
| naming.py | Generic metadata parsing, safe templates, path/collision checks |
| dating.py | General date claims, imported references, conflicts, review, HTML evidence |
| store.py | SQLite queue, date cache, reference settings |
| engine.py | Sequential worker, subprocess controls, stream validation, delivery |
| app.py | Authenticated API, async scans/research, controls, exports, browsing |
| desktop.py / runtime.py | Native window, local server lifecycle, packaged child-tool dispatch |
| static/ | Responsive ingestion, organization, and date-review interface |

## Subject independence

The runtime contains no collection-specific catalogue, default subject, source URL, or title-prefix rule. A JSON-index adapter maps arbitrary record fields. Reference catalogues are user-selected data with exact titles, optional aliases, optional collection scopes, and source attribution.

Source-platform handling inside yt-dlp and embed normalization is separate from subject matter. Adding support for a video platform does not require a team/show-specific interface.

## State

SQLite queue entries retain the original item and delivery settings. Unfinished jobs become paused after restart. A date cache is keyed by URL and unchanged source title. Imported reference-library settings are stored separately and start empty.

Changes in v0.3 use an additive settings table and retain prior jobs/reviews.

## Jobs

Queued → Running → Merging → Completed. Pause/cancel interrupts the child process tree and retains staging. Resume/retry reuses partial work. Existing final paths are skipped without alteration.

Final media is validated with ffprobe before non-overwriting delivery. Compatible files can be joined directly; normalization establishes a common stream layout first. Network shares without hard-link support use exclusive copying.

## Date selection

Research derives claims from metadata and imported reference entries. Claims with no overlapping date range produce a conflict. Explicit reviewer decisions override automatic analysis until reset.

Selection requires the full suggested date range inside the requested interval and an accepted confidence status. Research clears earlier download selections; selecting matches is explicit.

The interface records source URLs and reasoning and does not represent metadata inference as visual verification of uploaded footage.

