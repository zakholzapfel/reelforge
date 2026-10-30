import importlib.util
from io import BytesIO
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location("tool_preparation", Path(__file__).resolve().parents[1] / "scripts/prepare_tools.py")
preparation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preparation)


def test_corrupt_download_never_replaces_previous_payload(tmp_path, monkeypatch):
    destination=tmp_path/"tool.zip"
    destination.write_bytes(b"previous")
    monkeypatch.setattr(preparation,"urlopen",lambda *a,**k:BytesIO(b"corrupt"))
    with pytest.raises(ValueError,match="Checksum mismatch"):
        preparation.download("https://example.invalid/tool","0"*64,destination)
    assert destination.read_bytes()==b"previous"
    assert not destination.with_suffix(".zip.partial").exists()


@pytest.mark.parametrize("name,kind",[("../outside",tarfile.REGTYPE),("source/link",tarfile.SYMTYPE)])
def test_source_extraction_rejects_traversal_and_links(tmp_path,name,kind):
    archive=tmp_path/"source.tar"
    with tarfile.open(archive,"w") as output:
        entry=tarfile.TarInfo(name)
        entry.type=kind
        entry.linkname="/outside"
        output.addfile(entry,BytesIO(b""))
    with pytest.raises(ValueError,match="Unsafe source"):
        preparation.extract_source(archive,tmp_path/"extract")
    assert not (tmp_path/"outside").exists()


def test_finalize_refuses_missing_media_tools(tmp_path):
    with pytest.raises(ValueError,match="Missing bundled ffmpeg"):
        preparation.finalize(tmp_path)
