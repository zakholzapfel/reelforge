"""Source adapters for supported videos, bounded HTML discovery, JSON indexes, and manifests."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qs
from urllib.request import Request, urlopen

from .runtime import ytdlp_command, quiet_process
from .models import Item, ScanRequest

UA = "Mozilla/5.0 ReelForge/0.1"
MEDIA = (".mp4", ".mkv", ".webm", ".mov", ".m4v", ".m3u8", ".mpd")


def valid_url(url: str) -> str:
    p = urlsplit(url)
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password or any(ord(c) < 32 for c in url):
        raise ValueError("Use a complete http:// or https:// URL without embedded credentials.")
    return url


def key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def fetch(url: str) -> str:
    with urlopen(Request(valid_url(url), headers={"User-Agent": UA}), timeout=25) as response:
        data = response.read(8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024:
            raise ValueError("Page exceeds the 8 MB scan limit.")
        return data.decode(response.headers.get_content_charset() or "utf-8", errors="replace")


def normalize(raw: str, base: str) -> str | None:
    url = urljoin(base, raw)
    p = urlsplit(url)
    if p.scheme not in {"http", "https"}:
        return None
    host = (p.hostname or "").removeprefix("www.")
    if p.path.lower().endswith(MEDIA):
        return url
    if host in {"youtube.com", "m.youtube.com", "youtu.be"}:
        vid = p.path.strip("/").split("/")[0] if host == "youtu.be" else parse_qs(p.query).get("v", [""])[0]
        m = re.match(r"/(?:embed|shorts|live)/([^/]+)", p.path)
        vid = m[1] if m else vid
        return "https://www.youtube.com/watch?v=" + vid if vid else None
    if host == "bitchute.com":
        m = re.match(r"/(?:embed|video)/([^/]+)", p.path)
        return f"https://www.bitchute.com/video/{m[1]}/" if m else None
    if any(host == h or host.endswith("." + h) for h in ("vimeo.com", "dailymotion.com", "rumble.com", "archive.org")):
        return url
    return None


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.media = []
        self.links = []
        self.title = ""
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"iframe", "video", "source"}:
            source = attrs.get("src") or attrs.get("data-src")
            if source:
                self.media.append(source)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def resolve_page(url: str) -> str:
    direct = normalize(url, url)
    if direct:
        return direct
    parser = PageParser()
    parser.feed(fetch(url))
    candidates = list(dict.fromkeys(u for x in parser.media if (u := normalize(x, url))))
    if not candidates:
        # yt-dlp's generic extractor can handle additional supported embeds.
        return valid_url(url)
    candidates.sort(key=lambda x: not urlsplit(x).path.lower().endswith(MEDIA))
    return candidates[0]


def playlist_scan(req: ScanRequest) -> tuple[list[Item], list[str]]:
    valid_url(req.url)
    # Use system-trusted roots, retaining TLS verification on networks with
    # installed organizational certificates as well as ordinary public sites.
    command = ytdlp_command() + ["--ignore-config", "--compat-options", "no-certifi", "--flat-playlist", "--dump-single-json", "--skip-download", "--ignore-errors", "--socket-timeout", "20", "--playlist-end", str(req.limit), "--", req.url]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180, **quiet_process())
    if not result.stdout.strip():
        raise ValueError(result.stderr[-2000:] or "The source returned no videos.")
    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise ValueError(result.stderr[-2000:] or "The source could not be read. Update yt-dlp and check source access.")
    entries = data.get("entries") if "entries" in data else [data]
    items = []
    skipped = 0
    for index, entry in enumerate(entries or [], 1):
        if not entry or entry.get("title") in {"[Private video]", "[Deleted video]"}:
            skipped += 1
            continue
        url = entry.get("webpage_url") or entry.get("url") or ""
        if not url.startswith(("http://", "https://")) and entry.get("ie_key") == "Youtube":
            url = "https://www.youtube.com/watch?v=" + str(entry["id"])
        try:
            valid_url(url)
        except ValueError:
            skipped += 1
            continue
        items.append(Item(id=key(url + str(index)), url=url, title=entry.get("title") or str(entry.get("id", "Untitled")), index=entry.get("playlist_index") or index, duration=entry.get("duration"), season=entry.get("season_number"), episode=entry.get("episode_number"), collection=data.get("title") or req.collection))
    warnings = [f"{skipped} unavailable or unrecognized entries skipped."] if skipped else []
    if result.stderr.strip():
        warnings.append(result.stderr[-1200:])
    return items, warnings


def website_scan(req: ScanRequest) -> tuple[list[Item], list[str]]:
    valid_url(req.url)
    pending = [(req.url, 0)]
    seen, found = set(), {}
    warnings = []
    pages = 0
    while pending and pages < min(req.limit, 100):
        url, depth = pending.pop(0)
        if url in seen:
            continue
        seen.add(url)
        direct = normalize(url, url)
        if direct:
            found.setdefault(direct, Item(id=key(direct), url=direct, title=Path(urlsplit(url).path).stem or "Video", collection=req.collection))
            continue
        try:
            p = PageParser()
            p.feed(fetch(url))
            pages += 1
            for raw in p.media + p.links:
                media = normalize(raw, url)
                if media:
                    found.setdefault(media, Item(id=key(media), url=media, title=p.title.strip() or Path(urlsplit(media).path).stem, referer=url, collection=req.collection))
                elif depth < req.depth:
                    child = urljoin(url, raw)
                    parts = urlsplit(child)
                    child = urlunsplit(parts._replace(fragment=""))
                    if parts.scheme in {"http", "https"} and parts.netloc == urlsplit(req.url).netloc and (not req.link_contains or req.link_contains in child):
                        if child not in seen and len(pending) < 200:
                            pending.append((child, depth + 1))
            if len(found) >= req.limit:
                break
        except Exception as exc:
            warnings.append(f"Could not scan {url}: {exc}")
    if pending:
        warnings.append("Page/video scan limit reached; narrow the link filter or scan a smaller collection.")
    items = list(found.values())[:req.limit]
    for index, item in enumerate(items, 1):
        item.index = index
    if not items:
        warnings.append("No static video links found. Try Playlist / supported URL, or use a manifest for JavaScript-only pages.")
    return items, warnings


def manifest_scan(text: str, collection: str) -> list[Item]:
    data = json.loads(text)
    if not isinstance(data, list) or not 1 <= len(data) <= 1000:
        raise ValueError("Manifest must be an array of 1–1000 video objects.")
    items = []
    for index, row in enumerate(data, 1):
        if not isinstance(row, dict):
            raise ValueError("Every manifest entry must be an object.")
        parts = row.get("parts", [])
        url = row.get("url") or (parts[0] if parts else "")
        valid_url(url)
        for part in parts:
            valid_url(part)
        if row.get("referer"):
            valid_url(row["referer"])
        items.append(Item(**(row | {"id": str(row.get("id") or key(url + str(index))), "url": url, "index": row.get("index", index), "collection": row.get("collection", collection)})))
    if len({item.id for item in items}) != len(items):
        raise ValueError("Manifest IDs must be unique.")
    return items


def extract_json_object(text: str, marker: str) -> dict:
    start = text.find(marker)
    if start < 0:
        raise ValueError("The site's collection definition changed; adapter needs updating.")
    start = text.index("{", start + len(marker))
    return json.JSONDecoder().raw_decode(text[start:])[0]



def record_value(record, path: str):
    value = record
    for part in path.split(".") if path else []:
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return None
    return value


def records_scan(req: ScanRequest) -> tuple[list[Item], list[str]]:
    records = record_value(json.loads(fetch(req.url)), req.records_path)
    if not isinstance(records, list):
        raise ValueError("The records path must point to a JSON array. Leave it blank for a top-level array.")
    base = valid_url(req.base_url or req.url)
    items, warnings = [], []
    for number, record in enumerate(records, 1):
        if len(items) >= req.limit:
            warnings.append("Record limit reached; split the list or scan a smaller source.")
            break
        try:
            if not isinstance(record, dict):
                raise ValueError("not an object")
            raw = record_value(record, req.url_field)
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError("missing URL field")
            url = valid_url(urljoin(base, raw.strip()))
            metadata = {}
            for field in ("season", "episode", "year"):
                path = getattr(req, field + "_field")
                value = record_value(record, path) if path else None
                metadata[field] = int(value) if value is not None and str(value).strip() else None
            for field in ("filename", "subfolder"):
                path = getattr(req, field + "_field")
                value = record_value(record, path) if path else None
                metadata[field] = str(value) if value is not None else ""
            title = record_value(record, req.title_field)
            items.append(Item(id=key(url + str(number)), url=url, title=str(title or Path(urlsplit(url).path).stem or f"Video {number}"), index=number, collection=req.collection, **metadata))
        except (ValueError, TypeError) as exc:
            warnings.append(f"Record {number} skipped: {exc}")
    return items, warnings[:30]


def scan(req: ScanRequest) -> tuple[list[Item], list[str]]:
    if req.mode == "manifest":
        return manifest_scan(req.manifest, req.collection), []
    return {"playlist": playlist_scan, "website": website_scan, "records": records_scan}[req.mode](req)
