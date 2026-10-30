"""Evidence-based original-date suggestions. Upload dates are never air dates."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from html.parser import HTMLParser

from .runtime import ytdlp_command, quiet_process
from .models import DateEvidence, DateFilter, Dating, Item, ReferenceEntry
from .sources import valid_url, fetch

YEAR = re.compile(r"(?<!\d)(?:18|19|20)\d{2}(?!\d|[pi])", re.I)
DECADE = re.compile(r"(?<!\d)((?:18|19|20)\d0)['’]?s\b", re.I)
ORIGINAL = re.compile(r"(?:original(?:ly)?\s+(?:air(?:ed|ing)?|broadcast|premiere(?:d)?|released|published|recorded)|first\s+(?:air(?:ed|ing)?|broadcast|premiere(?:d)?|released|published|recorded)|premiered|(?:this\s+(?:promo|commercial|spot|video)\s+)?aired\s+(?:in|on|from|back))", re.I)


def normalized_title(title: str) -> str:
    title = re.sub(r"\b(?:2160|1080|720|480)[pi]\b|\b[48]k\b|\b(?:hd|uhd|blu[ -]?ray|remastered|remaster)\b", "", title, flags=re.I)
    title = re.sub(r"[\[(]\s*(?:18|19|20)\d{2}\s*[\])]", "", title)
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def title_evidence(item: Item) -> tuple[list[DateEvidence], list[str]]:
    years = sorted(set(int(m[0]) for m in YEAR.finditer(item.title)))
    if not years:
        return [], []
    if len(years) > 2 or len(years) == 2 and not re.search(r"(?:18|19|20)\d{2}\s*[-–—/]\s*(?:18|19|20)\d{2}", item.title):
        return [], ["Several years occur in the title; review their meaning before assigning an original date."]
    if re.search(r"\b(?:anniversary|reupload|uploaded|remaster(?:ed)?)\b", item.title, re.I):
        return [], ["Title years may describe an anniversary, remaster, or upload. Original date left unresolved without stronger evidence."]
    decade = DECADE.search(item.title)
    end = years[-1] + 9 if len(years) == 1 and decade else years[-1]
    return [DateEvidence(kind="title", label="Year or period stated in video title", year_start=years[0], year_end=end, url=item.url, note="Uploader title claim; not independently verified.")], []


def description_evidence(item: Item) -> list[DateEvidence]:
    evidence = []
    for sentence in re.split(r"(?<=[.!?])\s+|[\r\n]+", item.description):
        match = ORIGINAL.search(sentence)
        if not match:
            continue
        subject = sentence[:match.start()].lower()[-120:]
        if re.search(r"\b(?:promo|commercial|trailer|teaser|advertisement|bumper)\b", item.title, re.I) and re.search(r"\b(?:series|show|episode|film|movie|album|song|game|anime)\b", subject) and not re.search(r"\b(?:promo|commercial|spot|advertisement|bumper|ad)\b", subject):
            continue
        context = sentence[match.start():match.end()+110]
        years = sorted(set(int(m[0]) for m in YEAR.finditer(context)))
        if not years or len(years) > 2:
            continue
        if len(years) == 2 and not re.search(r"(?:18|19|20)\d{2}\s*(?:[-–—/]|to|through|and)\s*(?:18|19|20)\d{2}", context, re.I):
            continue
        end = years[-1] + 9 if len(years) == 1 and DECADE.search(context) else years[-1]
        evidence.append(DateEvidence(kind="description", label="Original-date statement in description", year_start=years[0], year_end=end, url=item.url, note=" ".join(context.split()[:20])))
    return evidence[:10]


def reference_evidence(item: Item, references: list[ReferenceEntry] | None = None) -> list[DateEvidence]:
    name = normalized_title(item.title)
    matches = [record for record in references or [] if (not record.collection or record.collection.casefold() == item.collection.casefold()) and name in {normalized_title(t) for t in [record.title, *record.aliases]}]
    return [DateEvidence(kind="reference", level="documented", label=record.label, year_start=record.year_start, year_end=record.year_end, url=record.url, note=record.note + " Imported reference match; verify the exact uploaded edition.") for record in matches]


def summarize(evidence: list[DateEvidence], notes: list[str] | None = None) -> Dating:
    notes = list(notes or [])
    if not evidence:
        return Dating(notes=notes)
    start, end = max(e.year_start for e in evidence), min(e.year_end for e in evidence)
    if start > end:
        return Dating(confidence="conflicting", evidence=evidence, notes=notes + ["Date claims disagree. Review the sources or record a manual decision."])
    documented = any(e.level == "documented" for e in evidence)
    if any(e.kind == "reference" for e in evidence):
        notes.append("Documented refers to a dated source record or review. The exact uploaded edition has not been visually verified.")
    return Dating(year_start=start, year_end=end, confidence="documented" if documented else "likely", evidence=evidence, notes=notes)


def analyze(item: Item, references: list[ReferenceEntry] | None = None) -> Item:
    out = item.model_copy(deep=True)
    if out.dating.reviewed:
        return out
    evidence, notes = title_evidence(out)
    evidence += description_evidence(out) + reference_evidence(out, references)
    evidence += [e for e in out.dating.evidence if e.label == "User-supplied reference page"]
    if out.upload_date:
        notes.append("Upload date is retained for context only; it is not used as an original air date.")
    out.dating = summarize(evidence, notes)
    return out


def classify(dating: Dating, start: int, end: int) -> str:
    if start > end:
        raise ValueError("Start year must not exceed end year.")
    if dating.confidence == "conflicting":
        return "conflicting"
    if dating.confidence == "unknown" or dating.year_start is None or dating.year_end is None:
        return "unknown"
    if dating.year_start >= start and dating.year_end <= end:
        return "inside"
    if dating.year_end < start or dating.year_start > end:
        return "outside"
    return "overlap"


def select_dates(items: list[Item], criteria: DateFilter) -> list[str]:
    if criteria.year_start > criteria.year_end:
        raise ValueError("Start year must not exceed end year.")
    allowed = {"documented"} if criteria.confidence == "documented" else {"documented", "likely"}
    return [i.id for i in items if i.dating.confidence in allowed and classify(i.dating, criteria.year_start, criteria.year_end) == "inside"]


def metadata_description(item: Item, cancel: threading.Event | None = None) -> Item:
    """Request metadata without video formats, downloads, subtitles, or thumbnails."""
    url = valid_url(item.url)
    command = ytdlp_command() + ["--ignore-config", "--compat-options", "no-certifi", "--skip-download", "--no-playlist", "--dump-single-json", "--socket-timeout", "12", "--retries", "0", "--extractor-retries", "0", "--ignore-no-formats-error", "--extractor-args", "youtube:skip=hls,dash,translated_subs;player_skip=js,configs", "--", url]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", **quiet_process())
    deadline = datetime.now(timezone.utc).timestamp() + 45
    try:
        while True:
            if cancel and cancel.is_set():
                raise InterruptedError("Research cancelled.")
            try:
                stdout, stderr = process.communicate(timeout=.25)
                break
            except subprocess.TimeoutExpired:
                if datetime.now(timezone.utc).timestamp() >= deadline:
                    raise ValueError("Description lookup timed out; local/reference evidence was retained.")
        try:
            data = json.loads(stdout)
        except (json.JSONDecodeError, TypeError):
            data = None
        if not isinstance(data, dict):
            raise ValueError((stderr or "Description metadata unavailable.")[-900:])
        out = item.model_copy(deep=True)
        out.description = str(data.get("description") or "")[:50000]
        out.upload_date = str(data.get("upload_date") or "")
        return out
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate()


def review(item: Item, start: int | None, end: int | None, confidence: str, note: str, url: str = "") -> Item:
    if confidence not in {"documented", "likely", "unknown"}:
        raise ValueError("Choose documented, likely, or unknown.")
    if url:
        valid_url(url)
    out = item.model_copy(deep=True)
    if out.dating.reviewed:
        out.year = None
    if confidence == "unknown":
        out.dating = Dating(reviewed=True, evidence=out.dating.evidence, notes=["Reviewer left the original date unresolved.", note])
        return out
    if start is None or end is None or not 1800 <= start <= end <= 2100:
        raise ValueError("Enter a valid original year or range.")
    if not note.strip():
        raise ValueError("Add the evidence or reasoning for this date decision.")
    evidence = DateEvidence(kind="manual", level=confidence, label="User-reviewed date", year_start=start, year_end=end, url=url, note=note.strip())
    out.dating = Dating(year_start=start, year_end=end, confidence=confidence, evidence=out.dating.evidence+[evidence], notes=["User-reviewed decision; earlier evidence is retained below."], reviewed=True)
    if start == end:
        out.year = start
    return out


class ReferenceText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocked = 0
        self.text = []
        self.heading = ""
        self.in_heading = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav", "footer", "aside"}:
            self.blocked += 1
        if tag == "h1" and not self.blocked:
            self.in_heading = True
        if tag in {"p", "div", "br", "h1", "h2", "h3", "li", "dt", "dd", "td", "th"} and not self.blocked:
            self.text.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav", "footer", "aside"}:
            self.blocked = max(0, self.blocked-1)
        if tag == "h1":
            self.in_heading = False
        if tag in {"p", "div", "li", "dt", "dd", "td", "th"} and not self.blocked:
            self.text.append("\n")

    def handle_data(self, text):
        if not self.blocked:
            self.text.append(text)
            if self.in_heading:
                self.heading += text


def reference_page(item: Item, url: str) -> Item:
    parser = ReferenceText()
    try:
        parser.feed(fetch(valid_url(url)))
    except OSError as exc:
        raise ValueError(f"Could not read this reference page: {exc}. You can still record a manual source review.") from exc
    text = " ".join("".join(parser.text).split())
    # Restrict extraction to an explicit airdate field or an original-airing
    # statement. Never select an arbitrary year from navigation/copyright.
    fields = re.findall(r"\b(?:original\s+air\s*date|first\s+air(?:ed|date)|airdate|release\s+date|publication\s+date)\b\s*[:\-]?\s*((?:(?!\b(?:Song|Artist|Album|Show|Genre|Network)\b).){0,80})", text, re.I)
    candidates = set()
    for field in fields:
        dates = YEAR.findall(field)
        if len(set(dates)) == 1:
            candidates.add(int(dates[0]))
    surrogate = item.model_copy(update={"description": text})
    candidates.update(e.year_start for e in description_evidence(surrogate) if e.year_start == e.year_end)
    if len(candidates) != 1:
        raise ValueError("This page does not expose one unambiguous original-airing year. Read it and record a manual decision.")
    out = item.model_copy(deep=True)
    year = candidates.pop()
    same_title = normalized_title(parser.heading) == normalized_title(item.title)
    evidence = [e for e in out.dating.evidence if not (e.label == "User-supplied reference page" and e.url == url)]
    evidence.append(DateEvidence(kind="reference", label="User-supplied reference page", year_start=year, year_end=year, url=url, note=("Page heading matches the video title. " if same_title else "Page heading differs; verify it refers to this exact video. ") + "The page states an original-airing year. Reviewer confirmation is still required.", level="likely"))
    out.dating = summarize(evidence)
    return out
