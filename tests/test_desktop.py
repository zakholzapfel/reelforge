import json
from pathlib import Path
import plistlib
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from reelforge.desktop import DesktopSession
from reelforge.runtime import ytdlp_command


def test_desktop_service_auth_shutdown_and_pending_job_pause(tmp_path):
    session=DesktopSession(tmp_path, start_worker=False).start()
    base=session.url.split("#")[0]
    with pytest.raises(HTTPError) as error:
        urlopen(base+"api/status", timeout=5)
    assert error.value.code==401
    request=Request(base+"api/status", headers={"X-ReelForge-Token":session.token})
    with urlopen(request,timeout=5) as response:
        assert json.load(response)["version"]=="0.5.0"
    job,_=session.app.state.store.add({"test":True},"desktop-job")
    session.close()
    assert not session.thread.is_alive()
    from reelforge.store import Store
    store=Store(tmp_path/"queue.sqlite3")
    assert store.get(job)["state"]=="paused"
    store.close()
    session.close() # Window cleanup may be called more than once.


def test_packaged_child_tool_uses_dispatch_flag(monkeypatch):
    assert ytdlp_command()==[sys.executable,"-m","yt_dlp"]
    monkeypatch.setattr(sys,"frozen",True,raising=False)
    assert ytdlp_command()==[sys.executable,"--reelforge-ytdlp"]


def test_mac_shortcut_escapes_paths_and_declares_icon(tmp_path):
    import importlib.util
    spec=importlib.util.spec_from_file_location("desktop_installer",Path(__file__).resolve().parents[1]/"scripts/install_desktop.py")
    installer=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    app=tmp_path/"ReelForge.app"
    python=tmp_path/"An odd ' folder"/"python"
    installer.mac_app(app,python)
    info=plistlib.loads((app/"Contents/Info.plist").read_bytes())
    assert info["CFBundleIconFile"]=="ReelForge.icns"
    assert (app/"Contents/Resources/ReelForge.icns").is_file()
    launcher=app/"Contents/MacOS/ReelForge"
    import shlex
    line=launcher.read_text().splitlines()[-1]
    assert shlex.split(line)==["exec",str(python),"-m","reelforge.desktop"]
    assert launcher.stat().st_mode & 0o111


def test_mac_dmg_stage_preserves_framework_links_and_application_target(tmp_path):
    import importlib.util
    spec=importlib.util.spec_from_file_location("desktop_builder",Path(__file__).resolve().parents[1]/"scripts/build_desktop.py")
    builder=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    app=tmp_path/"built"/"ReelForge.app"
    framework=app/"Contents/Frameworks/Python.framework"
    (framework/"Versions/A").mkdir(parents=True)
    (framework/"Versions/A/Python").write_bytes(b"binary fixture")
    (framework/"Versions/Current").symlink_to("A")
    (framework/"Python").symlink_to("Versions/Current/Python")
    stage=tmp_path/"disk-image"
    builder.stage_mac_dmg(app,stage)
    copied=stage/"ReelForge.app/Contents/Frameworks/Python.framework"
    assert (copied/"Versions/Current").is_symlink()
    assert (copied/"Python").is_symlink()
    assert (copied/"Python").read_bytes()==b"binary fixture"
    assert (stage/"Applications").readlink()==Path("/Applications")
    assert "No Terminal setup" in (stage/"READ ME FIRST.txt").read_text()


def test_frozen_runtime_prefers_bundled_tools_to_system_path(tmp_path, monkeypatch):
    import os
    from reelforge.runtime import configure_runtime
    tools=tmp_path/"frozen/tools"
    tools.mkdir(parents=True)
    monkeypatch.setattr(sys,"frozen",True,raising=False)
    monkeypatch.setattr(sys,"_MEIPASS",str(tools.parent),raising=False)
    monkeypatch.setenv("PATH","/some/system/tools")
    configure_runtime()
    assert os.environ["PATH"].split(os.pathsep)[0]==str(tools)


def test_bundle_check_rejects_system_ffmpeg_in_place_of_missing_bundle(tmp_path, monkeypatch):
    import shutil
    from reelforge.desktop_checks import bundled_tools_self_test
    monkeypatch.setattr(sys,"frozen",True,raising=False)
    monkeypatch.setattr(sys,"_MEIPASS",str(tmp_path),raising=False)
    monkeypatch.setenv("PATH","")
    monkeypatch.setattr(shutil,"which",lambda name:"/system/bin/"+name)
    with pytest.raises(RuntimeError, match="missing from the app bundle"):
        bundled_tools_self_test()


def test_packaged_tool_modes_are_executable_before_self_test(tmp_path):
    import importlib.util
    import os
    spec=importlib.util.spec_from_file_location("desktop_builder_modes",Path(__file__).resolve().parents[1]/"scripts/build_desktop.py")
    builder=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    tool=tmp_path/"ReelForge/_internal/tools/deno"
    tool.parent.mkdir(parents=True)
    tool.write_bytes(b"fixture")
    tool.chmod(0o644)
    builder.ensure_tool_permissions(tmp_path/"ReelForge",["deno"])
    assert os.access(tool,os.X_OK)
    with pytest.raises(RuntimeError,match="Packaged tool is missing"):
        builder.ensure_tool_permissions(tmp_path/"ReelForge",["absent"])
