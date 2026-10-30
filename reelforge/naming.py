"""Pure, cross-platform naming and preview planning."""
from __future__ import annotations

import html
import re
import string
from pathlib import Path, PurePosixPath

from .models import Item, Rules

FIELDS = {"title", "show", "collection", "index", "season", "episode", "year", "id", "filename", "subfolder"}
RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)


def sanitize(value: str, limit: int = 160) -> str:
    value = html.unescape(str(value))
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " - ", value)
    value = re.sub(r"\s+", " ", value).strip(" .-")[:limit].rstrip(" .-")
    value = value or "Untitled"
    return "_" + value if RESERVED.match(value) else value


def episode_metadata(item: Item, pattern: str = "") -> Item:
    item = item.model_copy(deep=True)
    if pattern:
        match = re.search(pattern, item.title, re.I)
        if match:
            for key, value in match.groupdict().items():
                if value is not None and key in {"season", "episode", "year", "title"}:
                    setattr(item, key, value if key == "title" else int(value))
    if item.season is None or item.episode is None:
        match = re.search(r"\bS(?:eason\s*)?(\d{1,3})\s*[-,x: ]*E(?:pisode\s*)?(\d{1,3})\b", item.title, re.I)
        if match:
            item.season = item.season if item.season is not None else int(match[1])
            item.episode = item.episode if item.episode is not None else int(match[2])
    # Season/episode labels may occur at either end of a source title.
    if item.season is not None and item.episode is not None:
        title = re.sub(r"\(?\bS(?:eason\s*)?\d{1,3}\s*[-,x: ]*E(?:pisode\s*)?\d{1,3}\b\)?", "", item.title, flags=re.I)
        item.title = title.strip(" -–|()") or item.title
    return item


def template_path(template: str, values: dict) -> Path:
    if not template or template.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", template):
        raise ValueError("Naming templates must be relative to the destination folder.")
    for _, field, spec, conversion in string.Formatter().parse(template):
        if field is not None:
            if field not in FIELDS or conversion or not re.fullmatch(r"(?:0?\d{0,2}d)?", spec):
                raise ValueError(f"Unsupported template field or format: {field}")
            if values.get(field) is None:
                raise ValueError(f"Missing {field}; edit metadata or select a different naming preset.")
    # Render each template segment separately: metadata cannot introduce new folders.
    parts = []
    for segment in template.replace("\\", "/").split("/"):
        if not segment or segment in {".", ".."}:
            raise ValueError("Templates cannot contain empty or traversal path segments.")
        rendered = segment.format_map(values)
        # Explicit archive subfolders are separately checked before expansion.
        if segment == "{subfolder}":
            sub = PurePosixPath(rendered.replace("\\", "/"))
            if sub.is_absolute() or any(p in {".", ".."} for p in rendered.split("/")) or not rendered:
                raise ValueError("Archive subfolder must be a relative, nonempty path.")
            parts.extend(sanitize(p) for p in sub.parts)
        else:
            parts.append(sanitize(rendered))
    return Path(*parts)


def plan(items: list[Item], rules: Rules) -> list[dict]:
    root = Path(rules.root).expanduser()
    if not root.is_absolute():
        raise ValueError("Choose an absolute destination path on this computer.")
    if rules.title_regex:
        try:
            re.compile(rules.title_regex)
        except re.error as exc:
            raise ValueError(f"Invalid title regex: {exc}") from exc
    templates = {
        "playlist": "{collection}/{index:03d} - {title}",
        "episodes": "{show}/Season {season:02d}/{show} - S{season:02d}E{episode:02d} - {title}",
        "archive": "{subfolder}/{filename}",
        "custom": rules.template,
    }
    rows = []
    for original in items:
        try:
            item = episode_metadata(original, rules.title_regex)
            if item.season is not None and item.season < 0 or item.episode is not None and item.episode < 1:
                raise ValueError("Season must be nonnegative and episode must be positive.")
            values = item.model_dump() | {"show": rules.show}
            template = templates[rules.preset]
            if rules.preset == "archive":
                values["filename"] = item.filename or item.title
                template = "{subfolder}/{filename}" if item.subfolder else "{filename}"
            relative = template_path(template, values)
            relative = relative.parent / (relative.name + "." + rules.container)
            target = (root / relative).resolve()
            if not target.is_relative_to(root.resolve()):
                raise ValueError("Destination escapes the selected root.")
            rows.append({"item": item.model_dump(), "relative": str(relative), "target": str(target), "error": "", "exists": target.exists()})
        except (ValueError, TypeError, KeyError) as exc:
            rows.append({"item": original.model_dump(), "relative": "", "target": "", "error": str(exc), "exists": False})
    groups = {}
    for row in rows:
        if row["target"]:
            groups.setdefault(row["target"].casefold(), []).append(row)
    for group in groups.values():
        if len(group) > 1:
            for row in group:
                row["error"] = "Filename collision. Edit metadata or include {index} / {id} in the template."
    return rows
