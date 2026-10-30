# ReelForge user guide

Open **Help & guide** in the app for the quick start, searchable FAQ, date examples, troubleshooting, and project background. Contextual help is also available beside source import and date research.

## Why it exists

Preparing a local media collection often means finding videos, pairing video and audio, cleaning filenames, organizing folders, and recovering interrupted downloads. ReelForge brings those steps into one reusable workflow, with output paths visible before downloading.

Created by Zakery Holzapfel, it grew from scripts used to prepare local collections, including a Fieldstation42 setup. Its folder-based workflow can prepare media for Plex, ErsatzTV, and Fieldstation42. Its sources, naming rules, and date references now support general collections and topics. It is a free local Python application with a browser interface and optional native desktop window. See [desktop setup](DESKTOP.md) for icons, shortcuts, and build previews.

## Quick start

1. **Import:** Paste a supported URL under Playlist / video and click Scan. Website, JSON index, and Manifest handle other source formats. Scanning lists entries; it does not download media.
2. **Review:** New scans select all entries. Check titles, use Edit to correct metadata, and use Clear followed by individual checkboxes when you want a subset. Filters hide rows without clearing hidden selections.
3. **Choose a folder:** Select a local destination or an already mounted network share under Make it yours. Set the collection name.
4. **Preview names:** Choose a naming preset, source quality, and output container. Review the path beneath each video and resolve missing metadata or filename collisions.
5. **Queue:** Click Queue selected. Leave Join selected videos off for separate files; turn it on for one combined file.
6. **Monitor:** Keep the launcher terminal open in browser mode, or keep the app window open in desktop mode. Download queue shows progress, pause/resume/retry/cancel controls, and errors. Completed files appear in the chosen destination.

**Try a sample** uses fictional metadata to preview the workflow. It deliberately disables downloads. Import real source URLs to queue media.

## Date research

Import first, then click **Research dates** for a fast title/reference pass. Entering a year range only filters results; it does not research dates. For more evidence, enable **Fetch descriptions online** and research again, or import your own reference JSON under Reference library.

This release checks titles, optional descriptions, user-imported references, and saved reviews. It does not autonomously search the web, watch footage, perform OCR, or transcribe speech. The Dates panel can open a web search and read a reference page URL you supply.

| Status | Meaning |
| --- | --- |
| Documented | An imported reference matches or you saved a documented review. The uploaded edit is not automatically verified. |
| Likely | A title, explicit original-date statement, or supplied reference page makes a date claim. |
| Unknown | Insufficient evidence, or a reviewer left the date unresolved. This does not mean outside the period. |
| Conflicting | Claims disagree. Automatic date selection excludes the item until reviewed. |

Set From year, Through year, and the accepted confidence. The entire suggested range must fit inside the target period. Upload dates are never used as original dates. Confidence labels are not statistical probabilities.

**Why can 3 likely become 2 matches?** Three likely dates of 1999, 2001, and 2005 yield two matches for 2000–2009. Confidence counts cover all imported videos; matches also meet the date and confidence rules. Visible rows additionally respect title, exclusion, and duration filters.

Click a confidence count or use **View all likely dates** to inspect all likely results. Check outside and overlapping views for exclusions. If entries are missing, clear other filters too.

**Research dates clears the download selection.** Changing a view does not select or deselect entries. **Select matches only** replaces the selection across the entire collection, even when title filters hide qualifying rows. Open **Dates** beside a video to review its evidence or save a manual date, source link, and reasoning.

Unchanged source URLs and titles restore saved reviews on rescan. Export date report creates a CSV. See [DATE-RESEARCH.md](DATE-RESEARCH.md) for reference JSON and detailed evidence behavior.

## Naming and output

| Preset | Example or behavior |
| --- | --- |
| Numbered playlist | `Collection/001 - Video title.mkv` |
| TV episodes | Season folders and season/episode labels; supply missing values with Edit. |
| Source filenames / folders | Uses supplied filename/subfolder metadata; otherwise saves by title directly under the destination. |
| Custom template | Fields such as `{collection}/{index:03d} - {title}`; leave out the extension. |

MKV preserves source codecs when merging separate video/audio. MP4 converts to H.264/AAC. Quality preferences limit known source resolutions; they do not upscale footage.

Joining uses collection order, not checkbox click order. TV episodes follow recognized season/episode order. Normalize join converts to 720p/30 fps H.264/stereo AAC; Fast join needs compatible streams. Conversion takes CPU time.

## FAQ

### Is it free? Do users need an API key?

This release has no paid API, subscription, or account requirement. Required software can be obtained without a software fee. Users supply their own computer, internet, and storage. ReelForge is MIT licensed; dependencies retain their own licenses.

### Why is Queue selected disabled?

Select at least one video and wait for filename preview to finish. Resolve metadata errors and path collisions. Scanning, research, and sample mode can also disable queueing.

### Why are hidden videos still selected?

Filters change visibility. Clear removes the whole selection; Select visible changes visible rows; Select matches only replaces the whole selection using date rules. Check the selected count before queueing.

### Does it retrieve audio as well as video?

For supported sources, yt-dlp retrieves available streams and FFmpeg merges separate audio/video as needed. Audio cannot be recovered if the source does not provide it.

### Can it save to a NAS or media-server folder?

Yes, when the folder/share is already mounted and writable. ReelForge does not configure or mount shares, refresh Plex, or manage ErsatzTV or Fieldstation42.

### Does it overwrite or deduplicate files?

Existing final paths are kept and skipped. Conflicting planned paths are flagged. This is not content-based deduplication: another filename for the same video is not automatically recognized.

### What survives closing the app?

The queue, cached dates, saved reviews, and imported reference library persist in the home-folder database. Interrupted jobs reopen paused. The current imported list and unsaved selection are not saved as a project; export a manifest before leaving if you want to reload the list.

### How do I update?

Quit ReelForge. On Mac, open the new DMG and replace the app in Applications; on Windows, run the new installer. Open the newly installed copy and check the version in the sidebar or Setup & about. Keep the home-folder database to retain saved jobs and reviews. Source users should follow the source setup instructions instead.

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| macOS execution-privileges error | In Terminal, type `bash` plus a space, drag `Launch-macOS.command` into Terminal, and press Return. |
| Browser cannot connect / Session expired | Reopen with the launcher and use its new tab. Keep the terminal running. Old addresses can refer to an expired session or port. |
| FFmpeg missing / failed join | Check Setup & about, install missing tools, and restart. Try Normalize join for incompatible inputs. |
| Download failed | Read the job's Error details. Check source availability, supported extraction, free space, and destination write access. Update yt-dlp if needed and retry after resolving the cause. |
| Collection count but no rows | Choose View all dates / statuses and clear title, exclude, and duration filters. A minimum-duration filter also hides unknown-duration entries. |
| All dates unknown | Click Research dates, check its status, then add descriptions/references or a manual review. Some originals cannot be identified from the available evidence. |
| Slow description research | Use a smaller batch with Selected videos only. Cancel keeps completed results. Lookup failures retain available title/reference evidence. |

Website scans read static HTML rather than executing page JavaScript. DRM, unsupported extractors, login/cookie import, automatic scheduling, and remote access are outside this release.

## Credits

ReelForge provides the UI/API, configurable source mapping, naming preview, queue, date review, and delivery controls. [yt-dlp](https://github.com/yt-dlp/yt-dlp) provides extraction; [FFmpeg](https://ffmpeg.org/) processes media; [FastAPI](https://fastapi.tiangolo.com/) serves the local API; [SQLite](https://www.sqlite.org/) stores state. Plex, ErsatzTV, and Fieldstation42 are separate projects. Use media you are authorized to download.


## Desktop download status

This ZIP is the source package. The bundled build workflow includes Python, FFmpeg/ffprobe, and Deno and prepares Mac DMG or Windows installer previews. Native installers are published in GitHub Releases. Apple Silicon Mac has passed hands-on installation/download checks; Intel Mac and Windows have passed automated checks and await hands-on GUI testing. Mac distribution will use the free route without paid signing/notarization, with documented first-launch instructions. See [Desktop setup and publishing](DESKTOP.md).
