from pathlib import Path
import pytest
from reelforge.models import Item, Rules
from reelforge.naming import plan, sanitize


def video(title="Morning Landscape (Season 1 Episode 1)", **kw):
    return Item(id="a", url="https://example.org/a.mp4", title=title, **kw)


@pytest.mark.parametrize("label", ["Season 1 Episode 1", "S01E01", "Season 1, Episode 1"])
def test_episode_name(tmp_path, label):
    row = plan([video(f"Morning Landscape ({label})")], Rules(root=str(tmp_path), preset="episodes", show="My Series"))[0]
    assert not row["error"]
    assert row["relative"] == str(Path("My Series/Season 01/My Series - S01E01 - Morning Landscape.mkv"))


def test_missing_metadata_requires_review(tmp_path):
    assert "Missing season" in plan([video("Unknown episode")], Rules(root=str(tmp_path), preset="episodes"))[0]["error"]


def test_custom_named_capture(tmp_path):
    row = plan([video("2x03 - Mountains")], Rules(root=str(tmp_path), preset="episodes", title_regex=r"(?P<season>\d+)x(?P<episode>\d+) - (?P<title>.*)"))[0]
    assert "S02E03 - Mountains" in row["relative"]


@pytest.mark.parametrize("template", ["../{title}", "/{title}", "C:/{title}", "{title.__class__}", "{title!r}", "{index:1000d}"])
def test_unsafe_templates(tmp_path, template):
    assert plan([video()], Rules(root=str(tmp_path), preset="custom", template=template))[0]["error"]


def test_metadata_cannot_add_folders(tmp_path):
    row=plan([video("../../unsafe")], Rules(root=str(tmp_path)))[0]
    assert Path(row["target"]).is_relative_to(tmp_path)
    assert len(Path(row["relative"]).parts)==2


def test_collision_case_insensitive(tmp_path):
    a=video("Same")
    b=video("same").model_copy(update={"id":"b"})
    rows=plan([a,b], Rules(root=str(tmp_path),preset="custom",template="{title}"))
    assert all("collision" in r["error"] for r in rows)


def test_archive_structure(tmp_path):
    row=plan([video("game",filename="01 - Opening Session",subfolder="Sessions/Day 1")],Rules(root=str(tmp_path),preset="archive"))[0]
    assert row["relative"].startswith(str(Path("Sessions/Day 1")))


def test_source_names_allow_root_folder_and_title_fallback(tmp_path):
    row=plan([video("Lecture One")],Rules(root=str(tmp_path),preset="archive"))[0]
    assert row["relative"]=="Lecture One.mkv" and not row["error"]


def test_invalid_regex(tmp_path):
    with pytest.raises(ValueError,match="Invalid title regex"):
        plan([video()],Rules(root=str(tmp_path),title_regex="["))


def test_windows_reserved_names():
    assert sanitize("CON")=="_CON"


def test_symlink_escape(tmp_path):
    outside=tmp_path.parent/"outside"
    outside.mkdir(exist_ok=True)
    (tmp_path/"Collection").symlink_to(outside,target_is_directory=True)
    assert "escapes" in plan([video()],Rules(root=str(tmp_path)))[0]["error"]
