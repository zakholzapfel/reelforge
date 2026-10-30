from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, model_validator


class DateEvidence(BaseModel):
    kind: Literal["title", "description", "reference", "manual"]
    label: str
    year_start: int = Field(ge=1800, le=2100)
    year_end: int = Field(ge=1800, le=2100)
    url: str = ""
    note: str = ""
    level: Literal["documented", "likely"] = "likely"

    @model_validator(mode="after")
    def valid_range(self):
        if self.year_start > self.year_end:
            raise ValueError("Evidence start year must not exceed end year.")
        return self


class Dating(BaseModel):
    year_start: int | None = None
    year_end: int | None = None
    confidence: Literal["documented", "likely", "unknown", "conflicting"] = "unknown"
    evidence: list[DateEvidence] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    reviewed: bool = False

    @model_validator(mode="after")
    def valid_range(self):
        if self.confidence in {"documented", "likely"}:
            if self.year_start is None or self.year_end is None or not 1800 <= self.year_start <= self.year_end <= 2100:
                raise ValueError("A dated result needs a valid year or range.")
        return self


class ReferenceEntry(BaseModel):
    title: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    collection: str = ""
    year_start: int = Field(ge=1800, le=2100)
    year_end: int = Field(ge=1800, le=2100)
    url: str
    label: str = "Imported reference"
    note: str = ""

    @model_validator(mode="after")
    def validate_entry(self):
        parsed = urlsplit(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("References need a complete HTTP(S) source URL without credentials.")
        if self.year_start > self.year_end:
            raise ValueError("Reference start year must not exceed end year.")
        return self


class ReferenceCatalog(BaseModel):
    name: str = "My references"
    records: list[ReferenceEntry] = Field(default_factory=list, max_length=10000)


class DateRequest(BaseModel):
    items: list["Item"] = Field(min_length=1, max_length=1000)
    descriptions: bool = False
    references: list[ReferenceEntry] | None = Field(default=None, max_length=10000)


class DateFilter(BaseModel):
    year_start: int = Field(ge=1800, le=2100)
    year_end: int = Field(ge=1800, le=2100)
    confidence: Literal["documented", "likely", "all"] = "documented"


class DateSelectionRequest(DateFilter):
    items: list["Item"] = Field(min_length=1, max_length=1000)


class Item(BaseModel):
    id: str
    url: str
    title: str
    index: int = 1
    duration: float | None = None
    season: int | None = None
    episode: int | None = None
    year: int | None = None
    collection: str = "Collection"
    subfolder: str = ""
    filename: str = ""
    referer: str = ""
    parts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    description: str = ""
    upload_date: str = ""
    dating: Dating = Field(default_factory=Dating)


class Rules(BaseModel):
    root: str
    show: str = "Collection"
    preset: Literal["playlist", "episodes", "archive", "custom"] = "playlist"
    template: str = "{collection}/{index:03d} - {title}"
    title_regex: str = ""
    container: Literal["mkv", "mp4"] = "mkv"
    quality: Literal["best", "1080", "720", "480"] = "1080"
    stitch: Literal["copy", "normalize"] = "normalize"


class ScanRequest(BaseModel):
    mode: Literal["playlist", "website", "records", "manifest"] = "playlist"
    url: str = ""
    collection: str = "Collection"
    link_contains: str = ""
    depth: int = Field(default=1, ge=0, le=2)
    limit: int = Field(default=500, ge=1, le=1000)
    records_path: str = ""
    url_field: str = "url"
    title_field: str = "title"
    season_field: str = ""
    episode_field: str = ""
    year_field: str = ""
    filename_field: str = ""
    subfolder_field: str = ""
    base_url: str = ""
    manifest: str = ""


class PlanRequest(BaseModel):
    items: list[Item] = Field(min_length=1, max_length=1000)
    rules: Rules


class QueueRequest(PlanRequest):
    combine: bool = False
    combined_title: str = "Combined video"


class DateReviewRequest(BaseModel):
    item: Item
    year_start: int | None = None
    year_end: int | None = None
    confidence: Literal["documented", "likely", "unknown"] = "unknown"
    note: str = ""
    url: str = ""
    reset: bool = False


class ReferenceRequest(BaseModel):
    item: Item
    url: str


DateRequest.model_rebuild()
DateSelectionRequest.model_rebuild()

