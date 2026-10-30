from __future__ import annotations

import csv
import io
import json
import os
import secrets
import shutil
import threading
import uuid
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .engine import Engine, fingerprint
from .models import Item, PlanRequest, QueueRequest, ScanRequest, DateRequest, DateSelectionRequest, DateReviewRequest, ReferenceRequest, ReferenceCatalog
from .dating import analyze, metadata_description, review, select_dates, reference_page
from .naming import plan
from .sources import scan, valid_url
from .store import Store

STATIC = Path(__file__).with_name("static")


def create_app(data_dir: Path | None = None, token: str | None = None, start_worker=True) -> FastAPI:
    token = token or secrets.token_urlsafe(32)
    data_dir = data_dir or Path(os.environ.get("REELFORGE_DATA_DIR", Path.home() / ".reelforge"))
    store = Store(data_dir / "queue.sqlite3")
    engine = Engine(store)
    scans, scan_lock = {}, threading.RLock()
    research, research_lock = {}, threading.RLock()
    closing = threading.Event()

    @asynccontextmanager
    async def lifespan(app):
        if start_worker:
            engine.start()
        yield
        closing.set()
        with research_lock:
            active_research = list(research.values())
            for task in active_research:
                task["_cancel"].set()
        for task in active_research:
            task["_thread"].join(timeout=5)
        engine.close()
        # Scan threads may still run for a bounded source timeout; they do not use SQLite.
        store.close()

    app = FastAPI(title="ReelForge", version="0.5.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.token, app.state.store, app.state.engine = token, store, engine

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        host = urlsplit("http://" + request.headers.get("host", "")).hostname
        if host not in {"127.0.0.1", "localhost", "::1", "testserver"}:
            return JSONResponse({"detail": "ReelForge accepts local connections only."}, status_code=403)
        origin = request.headers.get("origin")
        if origin and (urlsplit(origin).netloc != request.headers.get("host") or urlsplit(origin).scheme != "http"):
            return JSONResponse({"detail": "Cross-origin requests are blocked."}, status_code=403)
        if request.url.path.startswith("/api/") and not secrets.compare_digest(request.headers.get("x-reelforge-token", ""), token):
            return JSONResponse({"detail": "Session expired. Reopen ReelForge using its launcher."}, status_code=401)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.get("/")
    def home():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/status")
    def status():
        return {"version": "0.5.0", "yt_dlp": version("yt-dlp"), "ffmpeg": bool(shutil.which("ffmpeg")), "ffprobe": bool(shutil.which("ffprobe")), "deno": bool(shutil.which("deno")), "default_root": str(Path.home() / "Downloads" / "ReelForge")}

    @app.post("/api/scans")
    def start_scan(req: ScanRequest):
        sid = uuid.uuid4().hex
        with scan_lock:
            if sum(x["state"] == "running" for x in scans.values()) >= 2:
                raise HTTPException(429, "Two scans are already running. Wait for one to finish.")
            # Retain a bounded number of completed previews.
            for old in list(scans):
                if len(scans) < 20:
                    break
                if scans[old]["state"] != "running":
                    del scans[old]
            scans[sid] = {"state": "running", "items": [], "warnings": [], "error": ""}
        def run_scan():
            try:
                items, warnings = scan(req)
                result = {"state": "completed", "items": [i.model_dump() for i in items], "warnings": warnings, "error": ""}
            except Exception as exc:
                result = {"state": "failed", "items": [], "warnings": [], "error": str(exc)[-2500:]}
            with scan_lock:
                scans[sid] = result
        threading.Thread(target=run_scan, daemon=True).start()
        return {"id": sid}

    @app.get("/api/folders")
    def folders(path: str = ""):
        directory = Path(path).expanduser() if path else Path.home()
        if not directory.is_absolute() or not directory.is_dir():
            raise ValueError("Enter an existing absolute folder path.")
        try:
            children = sorted((p for p in directory.iterdir() if not p.name.startswith(".") and p.is_dir()), key=lambda p: p.name.lower())
        except OSError as exc:
            raise ValueError(f"Cannot open this folder: {exc}") from exc
        return {"path": str(directory), "parent": str(directory.parent), "folders": [{"name": p.name, "path": str(p)} for p in children[:200]], "truncated": len(children) > 200}

    @app.get("/api/scans/{sid}")
    def scan_status(sid: str):
        with scan_lock:
            if sid not in scans:
                raise HTTPException(404, "Scan not found.")
            result = scans[sid].copy()
        if result["state"] == "completed":
            result["items"] = [store.restored_date(Item(**i)).model_dump() for i in result["items"]]
        return result

    @app.post("/api/dates/research")
    def start_research(req: DateRequest):
        rid = uuid.uuid4().hex
        references = req.references if req.references is not None else store.references().records
        with research_lock:
            if any(t["state"] == "running" for t in research.values()):
                raise HTTPException(429, "Date research is already running. Finish or cancel it first.")
            for old in list(research):
                if len(research) < 10:
                    break
                if research[old]["state"] != "running":
                    del research[old]
            task = {"state": "running", "done": 0, "total": len(req.items), "items": [], "warnings": [], "current": "", "_cancel": threading.Event()}
            research[rid] = task
            def work():
                try:
                    for item in req.items:
                        if closing.is_set() or task["_cancel"].is_set():
                            break
                        with research_lock:
                            task["current"] = item.title
                        # Preserve an explicit reviewer decision; fresh scans also
                        # restore saved decisions by URL and unchanged source title.
                        cached = store.restored_date(item)
                        current = cached if cached.dating.reviewed else item.model_copy(deep=True)
                        warning = ""
                        if req.descriptions and not current.dating.reviewed and not current.description:
                            try:
                                current = metadata_description(current, task["_cancel"])
                            except InterruptedError:
                                break
                            except Exception as exc:
                                warning = f"{item.title}: {exc}"
                        result = analyze(current, references)
                        if warning:
                            result.dating.notes.append("Description lookup failed; available title/reference evidence was kept.")
                        if closing.is_set():
                            break
                        store.cache_date(result)
                        with research_lock:
                            task["items"].append(result.model_dump())
                            task["done"] += 1
                            if warning:
                                task["warnings"].append(warning)
                except Exception as exc:
                    with research_lock:
                        task["warnings"].append(str(exc))
                        task["state"] = "failed"
                finally:
                    with research_lock:
                        if task["state"] == "running":
                            task["state"] = "cancelled" if closing.is_set() or task["_cancel"].is_set() else "completed"
                        task["current"] = ""
            task["_thread"] = threading.Thread(target=work, daemon=True)
            task["_thread"].start()
        return {"id": rid}

    @app.get("/api/dates/research/{rid}")
    def research_status(rid: str):
        with research_lock:
            task = research.get(rid)
            if not task:
                raise HTTPException(404, "Research task not found.")
            return {key: value.copy() if isinstance(value, list) else value for key, value in task.items() if not key.startswith("_")}

    @app.post("/api/dates/research/{rid}/cancel")
    def cancel_research(rid: str):
        with research_lock:
            if rid not in research:
                raise HTTPException(404, "Research task not found.")
            research[rid]["_cancel"].set()
        return {"ok": True}

    @app.post("/api/dates/select")
    def select_by_date(req: DateSelectionRequest):
        return {"ids": select_dates(req.items, req)}

    @app.post("/api/dates/review")
    def review_date(req: DateReviewRequest):
        if req.reset:
            req.item.dating.reviewed = False
            result = analyze(req.item, store.references().records)
        else:
            result = review(req.item, req.year_start, req.year_end, req.confidence, req.note, req.url)
        store.cache_date(result)
        return {"item": result.model_dump()}

    @app.post("/api/dates/reference")
    def read_reference(req: ReferenceRequest):
        if req.item.dating.reviewed:
            raise ValueError("Reset the manual decision before adding automatic reference evidence.")
        result = reference_page(analyze(req.item, store.references().records), req.url)
        store.cache_date(result)
        return {"item": result.model_dump()}

    @app.get("/api/references")
    def references():
        return store.references().model_dump()

    @app.post("/api/references")
    def save_references(req: ReferenceCatalog):
        store.save_references(req)
        return req.model_dump()

    @app.post("/api/preview")
    def preview(req: PlanRequest):
        return {"rows": plan(req.items, req.rules)}

    @app.post("/api/queue")
    def enqueue(req: QueueRequest):
        items = req.items
        for item in items:
            valid_url(item.url)
            for url in item.parts:
                valid_url(url)
            if item.referer:
                valid_url(item.referer)
        if req.combine:
            first = items[0].model_copy(deep=True)
            first.title = req.combined_title
            first.filename = req.combined_title
            first.id = uuid.uuid4().hex
            first.parts = [url for item in items for url in (item.parts or [item.url])]
            # Different source pages need individual resolution, no shared referer.
            first.referer = ""
            items = [first]
        rows = plan(items, req.rules)
        errors = [r["error"] for r in rows if r["error"]]
        if errors:
            raise ValueError("Fix filename preview errors first: " + errors[0])
        # Preflight obvious file-vs-folder conflicts before adding any jobs.
        root = Path(req.rules.root).expanduser()
        if root.exists() and not root.is_dir():
            raise ValueError("Destination root is a file, not a folder.")
        output = []
        for row in rows:
            payload = {"item": row["item"], "target": row["target"], "rules": req.rules.model_dump()}
            jid, added = store.add(payload, fingerprint(payload))
            output.append({"id": jid, "added": added})
        return {"jobs": output}

    @app.get("/api/queue")
    def jobs():
        return {"jobs": store.rows()}

    @app.post("/api/queue/{jid}/{action}")
    def control(jid: str, action: str):
        if action not in {"pause", "resume", "retry", "cancel"}:
            raise HTTPException(404, "Unknown action.")
        engine.action(jid, action)
        return {"ok": True}

    @app.get("/api/export")
    def export():
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(["title", "source", "destination", "status", "error"])
        for row in store.rows():
            values = [row["payload"]["item"]["title"], row["payload"]["item"]["url"], row["payload"]["target"], row["state"], row["error"]]
            # Prevent spreadsheet formulas in imported titles/URLs.
            writer.writerow(["'" + v if v.startswith(("=", "+", "-", "@")) else v for v in values])
        return Response(buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="reelforge-download-report.csv"'})

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
