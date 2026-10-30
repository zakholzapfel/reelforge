import json
from reelforge.models import ScanRequest
from reelforge import sources
import pytest


def test_manifest_parts():
    items=sources.manifest_scan(json.dumps([{"title":"Combined", "parts":["https://example.org/1.mp4","https://example.org/2.mp4"]}]), "Collection")
    assert len(items[0].parts)==2


@pytest.mark.parametrize("url",["file:///etc/passwd","https://user:password@example.org/a", "javascript:alert(1)"])
def test_invalid_source_urls(url):
    with pytest.raises(ValueError):
        sources.valid_url(url)


def test_embed_normalization():
    assert sources.normalize("//www.bitchute.com/embed/abc/", "https://example.org/")=="https://www.bitchute.com/video/abc/"
    assert sources.normalize("https://www.youtube.com/embed/abc", "https://example.org/")=="https://www.youtube.com/watch?v=abc"


def test_top_definition_ignores_braces_inside_strings():
    data=sources.extract_json_object('const TOP20_PICKS = {"1970s":["game}.html"]}; anything',"TOP20_PICKS")
    assert data["1970s"]==["game}.html"]


def test_bounded_website_scan(monkeypatch):
    pages={"https://example.org/list":'<a href="/episode/1">episode</a><a href="/other">other</a>',"https://example.org/episode/1":'<title>My episode</title><iframe src="https://www.youtube.com/embed/abc"></iframe>'}
    monkeypatch.setattr(sources,"fetch",lambda url:pages[url])
    items,_=sources.website_scan(ScanRequest(mode="website",url="https://example.org/list",link_contains="/episode/",depth=1))
    assert len(items)==1 and items[0].title=="My episode"


def test_duplicate_manifest_ids_rejected():
    with pytest.raises(ValueError,match="unique"):
        sources.manifest_scan(json.dumps([{"id":"x","url":"https://example.org/a","title":"a"},{"id":"x","url":"https://example.org/b","title":"b"}]),"Collection")


def test_null_playlist_result_reports_extractor_error(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(sources.subprocess,"run",lambda *a,**k:SimpleNamespace(stdout="null\n",stderr="ERROR: source unavailable",returncode=0))
    with pytest.raises(ValueError,match="source unavailable"):
        sources.playlist_scan(ScanRequest(url="https://example.org/playlist"))


def test_json_records_nested_mapping_and_relative_urls(monkeypatch):
    records={"data":{"videos":[{"media":{"link":"/video/one.mp4"},"name":"First video","episode":"4"},{"name":"No URL"}]}}
    monkeypatch.setattr(sources,"fetch",lambda url:json.dumps(records))
    items,warnings=sources.records_scan(ScanRequest(mode="records",url="https://example.org/index.json",records_path="data.videos",url_field="media.link",title_field="name",episode_field="episode",collection="My Library"))
    assert len(items)==1 and items[0].url=="https://example.org/video/one.mp4"
    assert items[0].title=="First video" and items[0].episode==4
    assert warnings


def test_json_records_requires_array(monkeypatch):
    monkeypatch.setattr(sources,"fetch",lambda url:'{"data":{}}')
    with pytest.raises(ValueError,match="array"):
        sources.records_scan(ScanRequest(mode="records",url="https://example.org/index.json",records_path="data"))
