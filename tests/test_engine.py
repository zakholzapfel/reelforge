"""Real yt-dlp + FFmpeg integration using tiny generated, locally hosted videos."""
import functools
import http.server
import shutil
import subprocess
import threading
import time
from pathlib import Path
import pytest
from reelforge.engine import Engine, deliver, probe, fingerprint
from reelforge.models import Item, Rules
from reelforge.naming import plan
from reelforge.store import Store


@pytest.fixture
def media_server(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Install ffmpeg and ffprobe to run media integration tests.")
    media=tmp_path/"source"
    media.mkdir()
    for name,color,size in [("one","red","320x240"),("two","blue","640x360")]:
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-f","lavfi","-i",f"color={color}:s={size}:r=30:d=1","-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=1","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",str(media/(name+".mp4"))],check=True)
    (media/"page.html").write_text('<iframe src="one.mp4"></iframe>')
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-i",str(media/"one.mp4"),"-c","copy","-f","dash",str(media/"streams.mpd")],check=True)
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
    server=http.server.ThreadingHTTPServer(("127.0.0.1",0),functools.partial(Quiet,directory=str(media)))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def wait_job(store,jid,timeout=60):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        row=store.get(jid)
        if row["state"] in {"completed","failed","skipped"}:return row
        time.sleep(.1)
    pytest.fail("Job exceeded integration timeout.")


@pytest.mark.parametrize("container,joined,dash",[("mkv",False,False),("mp4",True,False),("mkv",False,True)])
def test_real_download_merge_delivery(tmp_path,media_server,container,joined,dash):
    rules=Rules(root=str(tmp_path/"media 100%"),container=container,quality="720")
    item=Item(id="video",url=media_server+("/streams.mpd" if dash else "/page.html"),title="Local sample",parts=[media_server+"/one.mp4",media_server+"/two.mp4"] if joined else [])
    row=plan([item],rules)[0]
    payload={"item":item.model_dump(),"rules":rules.model_dump(),"target":row["target"]}
    store=Store(tmp_path/"queue.sqlite3")
    engine=Engine(store)
    try:
        jid,_=store.add(payload,fingerprint(payload))
        engine.start()
        finished=wait_job(store,jid)
        assert finished["state"]=="completed",finished["error"]
        data=probe(Path(row["target"]))
        assert any(s["codec_type"]=="audio" for s in data["streams"])
        duration=float(data["format"]["duration"])
        assert (1.9<=duration<=2.3) if joined else (.9<=duration<=1.3)
        if container=="mp4":assert data["streams"][0]["codec_name"]=="h264"
        assert not (Path(rules.root)/".reelforge/staging"/jid).exists()
    finally:
        engine.close()
        store.close()


def test_no_overwrite_delivery(tmp_path):
    source=tmp_path/"source"
    target=tmp_path/"target"
    source.write_bytes(b"new")
    target.write_bytes(b"original")
    with pytest.raises(ValueError,match="unchanged"):
        deliver(source,target)
    assert target.read_bytes()==b"original"


def test_cancel_stops_subprocess_and_resume_race(tmp_path):
    store=Store(tmp_path/"queue.sqlite3")
    engine=Engine(store)
    jid,_=store.add({},"cancel-test")
    store.update(jid,state="running")
    engine.active=jid
    errors=[]
    import sys
    from reelforge.engine import Interrupted
    def work():
        try:engine.run(jid,[sys.executable,"-c","import time; time.sleep(20)"])
        except Interrupted:errors.append("stopped")
    thread=threading.Thread(target=work)
    thread.start()
    for _ in range(50):
        if engine.process:break
        time.sleep(.02)
    engine.action(jid,"pause")
    engine.action(jid,"resume")
    thread.join(timeout=5)
    assert not thread.is_alive() and errors==["stopped"]
    assert store.get(jid)["state"]=="queued"
    engine.close()
    store.close()
