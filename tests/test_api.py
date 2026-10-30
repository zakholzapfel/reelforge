import time
from fastapi.testclient import TestClient
from reelforge.app import create_app
from reelforge.store import Store


def payload(tmp_path,title="Video"):
    return {"items":[{"id":"a","url":"https://example.org/video.mp4","title":title}],"rules":{"root":str(tmp_path/"media")}}


def test_api_auth_origin_and_host(tmp_path):
    app=create_app(tmp_path,token="test-secret",start_worker=False)
    with TestClient(app) as client:
        assert client.get("/api/status").status_code==401
        assert client.get("/api/status",headers={"X-ReelForge-Token":"test-secret"}).status_code==200
        assert client.post("/api/queue",json=payload(tmp_path),headers={"X-ReelForge-Token":"test-secret","Origin":"https://evil.example"}).status_code==403
        assert client.get("/",headers={"Host":"evil.example"}).status_code==403


def test_preview_enqueue_deduplicate_pause_resume_export(tmp_path):
    app=create_app(tmp_path,token="test",start_worker=False)
    with TestClient(app,headers={"X-ReelForge-Token":"test"}) as client:
        data=payload(tmp_path,"=SUM(1,1)")
        assert client.post("/api/preview",json=data).json()["rows"][0]["relative"]
        job=client.post("/api/queue",json=data).json()["jobs"][0]
        assert job["added"]
        assert not client.post("/api/queue",json=data).json()["jobs"][0]["added"]
        assert client.post(f'/api/queue/{job["id"]}/pause',json={}).status_code==200
        assert client.get("/api/queue").json()["jobs"][0]["state"]=="paused"
        assert client.post(f'/api/queue/{job["id"]}/resume',json={}).status_code==200
        assert "'=SUM" in client.get("/api/export").text


def test_async_manifest_scan_and_folder_browser(tmp_path):
    (tmp_path/"visible").mkdir()
    app=create_app(tmp_path/"db",token="test",start_worker=False)
    with TestClient(app,headers={"X-ReelForge-Token":"test"}) as client:
        sid=client.post("/api/scans",json={"mode":"manifest","manifest":'[{"url":"https://example.org/a.mp4","title":"A"}]'}).json()["id"]
        result=None
        for _ in range(50):
            result=client.get("/api/scans/"+sid).json()
            if result["state"]!="running":break
            time.sleep(.01)
        assert result["state"]=="completed" and len(result["items"])==1
        assert "visible" in [x["name"] for x in client.get("/api/folders",params={"path":str(tmp_path)}).json()["folders"]]


def test_queue_restart_pauses_interrupted_jobs(tmp_path):
    store=Store(tmp_path/"queue.sqlite3")
    jid,_=store.add({"a":1},"x")
    store.update(jid,state="merging")
    store.close()
    reopened=Store(tmp_path/"queue.sqlite3")
    assert reopened.get(jid)["state"]=="paused"
    reopened.close()
