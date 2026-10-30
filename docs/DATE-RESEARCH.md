# Date research

The default research engine is content-neutral. It has no preloaded team, television show, channel, or franchise catalogue.

## Workflow

1. Import your videos.
2. Optionally import a reference library for your collection.
3. Click Research dates. Enable Fetch descriptions online if needed.
4. Enter your start and end years.
5. Choose Documented only or Documented + likely.
6. Click Select matches only.
7. Review the selected videos' evidence and queue the desired downloads.

Research clears the download selection. Select matches only replaces it across the entire collection, regardless of title-search filters.

## Evidence and confidence

| Status | Meaning |
| --- | --- |
| Documented | An imported reference record matches, or you saved a documented manual review. The uploaded edition is not automatically verified. |
| Likely | An explicit title, original-release/airing statement, or user-supplied reference page makes a date claim. |
| Unknown | Insufficient evidence, or a reviewer left the date unresolved. |
| Conflicting | Evidence claims disagree; excluded from automatic selection. |

A whole date range must fit inside the chosen years. Overlapping ranges require review. There is no preselected era, and confidence labels are not statistical probabilities.

Upload timestamps, ordinary copyright notices, soundtrack release years, and unrelated remaster dates are not treated as original dates.

## Import your own references

Open **Reference library → Import reference JSON**. The import replaces the current library; export it first if you want to keep a copy. Clearing the library retains saved per-video reviews.

~~~json
{
  "name": "My collection references",
  "records": [
    {
      "title": "Exact original title",
      "aliases": ["An alternate source title"],
      "collection": "Optional exact collection name",
      "year_start": 1995,
      "year_end": 1995,
      "url": "https://example.org/your-supporting-source",
      "label": "My source record",
      "note": "Explain what this source establishes."
    }
  ]
}
~~~

The example schema is illustrative; replace the example URL and metadata with real evidence.

- title: required primary title.
- aliases: optional alternative titles you explicitly supply.
- collection: optional exact collection scope; blank allows matching across collections.
- year_start/year_end: required date or range.
- url: required HTTP(S) evidence source.
- label/note: attribution and explanation.

Matching ignores punctuation, case, resolution tags, and isolated bracketed year labels. It preserves years inside work titles and does not perform fuzzy subject recognition. Distinct editions should have distinct titles or aliases.

Optional subject-specific reference packs can be kept as data under examples/reference-packs and imported deliberately. They are not runtime defaults.

## Descriptions and reference pages

Fetch descriptions online requests metadata without downloading video/audio. Lookups run sequentially with timeouts and cancellation. Use Selected videos only for smaller batches.

A video's Dates panel lets you:

- Open the source video.
- Open a web search for the original date.
- Read explicit airdate, release-date, or publication-date statements from a supplied HTML reference page.
- Record your own date/range, confidence, source link, and reasoning.

Ambiguous pages are left for manual review. The app does not execute site JavaScript or search the web autonomously.

## Visual/audio clues

You can watch a video and record visible release labels, product versions, logos, spoken dates, scheduling information, or other clues in the review notes. Their relevance depends on the content; reruns, reused footage, and later edits can complicate dating.

Automatic scene analysis, OCR, and speech transcription are not part of this release.

## Persistence

Research results and reviews are saved by source URL plus unchanged title in the local SQLite database. Manual decisions survive automatic research until reset.

Export Manifest preserves all metadata and evidence. Export date report creates a CSV with status, year/range, source URLs, and notes. Editing a source title or URL invalidates its displayed suggestion for re-review.

Automatic suggestions are separate from filename metadata. A manually reviewed single year can populate the {year} naming field.

