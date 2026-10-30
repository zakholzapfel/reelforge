"""Persistent, cancellable download worker with verified, non-overwriting delivery."""
from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from .runtime import ytdlp_command, quiet_process
from .models import Item, Rules
from .sources import resolve_page, valid_url
from .store import Store


class Interrupted(Exception):
    pass


def probe(path: Path) -> dict:
    result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-show_data_hash", "sha256", "-of", "json", str(path)], capture_output=True, text=True, timeout=30, check=True, **quiet_process())
    data = json.loads(result.stdout)
    if not any(s.get("codec_type") == "video" for s in data.get("streams", [])) or float(data.get("format", {}).get("duration", 0)) <= 0:
        raise ValueError("The output is empty or does not contain a playable video stream.")
    return data


def signature(data: dict) -> list:
    fields = ("codec_type", "codec_name", "codec_tag_string", "width", "height", "pix_fmt", "r_frame_rate", "time_base", "sample_rate", "channels", "channel_layout", "extradata_hash")
    return [tuple(stream.get(k) for k in fields) for stream in data["streams"] if stream.get("codec_type") in {"video", "audio"}]


def deliver(source: Path, target: Path):
    """Publish on the same filesystem atomically, refusing existing destinations."""
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except FileExistsError:
        raise ValueError("A file already exists at the destination. It was kept unchanged.")
    except OSError:
        # SMB/exFAT may not support links. Use exclusive creation and remove an
        # interrupted copy; the source stays available for a retry.
        with target.open("xb") as output:
            try:
                with source.open("rb") as incoming:
                    shutil.copyfileobj(incoming, output)
                output.flush()
                os.fsync(output.fileno())
            except BaseException:
                target.unlink(missing_ok=True)
                raise


class Engine:
    def __init__(self, store: Store):
        self.store = store
        self.stop = threading.Event()
        self.lock = threading.RLock()
        self.process = None
        self.active = None
        self.interrupted = set()
        self.thread = threading.Thread(target=self.worker, daemon=True)

    def start(self):
        self.thread.start()

    def check(self, jid):
        row = self.store.get(jid)
        if self.stop.is_set() or jid in self.interrupted or not row or row["state"] in {"paused", "cancelled"}:
            raise Interrupted()

    def kill(self):
        process = self.process
        if process and process.poll() is None:
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=10, **quiet_process())
                else:
                    os.killpg(process.pid, signal.SIGTERM)
            except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
                process.kill()

    def action(self, jid: str, action: str):
        with self.lock:
            row = self.store.get(jid)
            if not row:
                raise ValueError("Unknown job.")
            state = row["state"]
            if action in {"pause", "cancel"} and state in {"queued", "running", "merging", "paused", "failed"}:
                self.store.update(jid, state="paused" if action == "pause" else "cancelled", detail="Paused; partial downloads kept." if action == "pause" else "Cancelled; partial downloads kept.")
                if self.active == jid:
                    self.interrupted.add(jid)
                    self.kill()
            elif action in {"resume", "retry"} and state in {"paused", "failed", "cancelled"}:
                self.store.update(jid, state="queued", error="", detail="Waiting to continue.")
            else:
                raise ValueError(f"Cannot {action} a {state} job.")

    def run(self, jid: str, command: list[str], cwd: Path | None = None, progress_base=0, progress_span=90) -> list[str]:
        with self.lock:
            self.check(jid)
            kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
            process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", **kwargs)
            self.process = process
        lines = queue.Queue()
        def read():
            try:
                for line in process.stdout:
                    lines.put(line.rstrip())
            finally:
                lines.put(None)
        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        tail, outputs = [], []
        ended = False
        try:
            while not ended:
                self.check(jid)
                try:
                    line = lines.get(timeout=.2)
                except queue.Empty:
                    continue
                if line is None:
                    ended = True
                    continue
                tail = (tail + [line])[-25:]
                if line.startswith("RF_PROGRESS:"):
                    try:
                        data = json.loads(line.partition(":")[2])
                        total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                        fraction = min(1, (data.get("downloaded_bytes") or 0) / total) if total else 0
                        speed = data.get("speed") or 0
                        self.store.update(jid, progress=progress_base + progress_span * fraction, detail=f"Downloading • {speed / 1048576:.1f} MB/s")
                    except (ValueError, TypeError):
                        pass
                elif line.startswith("RF_FILE:"):
                    outputs.append(line.partition(":")[2])
                elif line.strip():
                    self.store.update(jid, detail=line[-250:])
            code = process.wait(timeout=10)
            self.check(jid)
            if code:
                raise ValueError("\n".join(tail)[-2500:] or f"Process exited with status {code}.")
            return outputs
        finally:
            with self.lock:
                self.kill()
                self.process = None
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            process.stdout.close()

    def download(self, jid, url, item: Item, rules: Rules, stage: Path, number, count):
        self.check(jid)
        page_url = url
        url = resolve_page(valid_url(url))
        self.check(jid)
        # Direct media links often omit resolution metadata. Allow unknown
        # heights so they remain downloadable; cap known-height formats.
        height = f"[height<=?{rules.quality}]" if rules.quality != "best" else ""
        fmt = f"bv*{height}+ba/b{height}"
        # Staging names are fixed: title text never becomes a yt-dlp template.
        output = str(stage / f"part-{number:03d}").replace("%", "%%") + ".%(ext)s"
        command = ytdlp_command() + ["--ignore-config", "--compat-options", "no-certifi", "--no-playlist", "--continue", "--no-overwrites", "--retries", "5", "--fragment-retries", "5", "--socket-timeout", "20", "--newline", "--no-colors", "--progress", "--progress-delta", "0.5", "--progress-template", "download:RF_PROGRESS:%(progress)j", "--print", "after_move:RF_FILE:%(filepath)s", "--no-simulate", "-f", fmt, "--merge-output-format", "mkv", "--remux-video", "mkv", "-o", output]
        referer = item.referer or (page_url if page_url != url else "")
        if referer:
            command += ["--referer", valid_url(referer)]
        command += ["--", url]
        self.run(jid, command, progress_base=85 * (number - 1) / count, progress_span=85 / count)
        file = stage / f"part-{number:03d}.mkv"
        if not file.is_file():
            raise ValueError("Downloader finished without the expected merged file.")
        probe(file)
        return file

    def normalize_part(self, jid, source: Path, target: Path):
        data = probe(source)
        audio = any(s.get("codec_type") == "audio" for s in data["streams"])
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source)]
        if not audio:
            command += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        command += ["-map", "0:v:0", "-map", "0:a:0" if audio else "1:a:0", "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest", str(target)]
        self.run(jid, command)
        probe(target)

    def execute(self, row):
        jid, payload = row["id"], row["payload"]
        item, rules = Item(**payload["item"]), Rules(**payload["rules"])
        target = Path(payload["target"])
        # Re-resolve paths at execution too: a changed symlink cannot redirect a job.
        root = Path(rules.root).expanduser().resolve()
        if not target.resolve().is_relative_to(root):
            raise ValueError("Destination now escapes the selected root.")
        if target.exists():
            self.store.update(jid, state="skipped", progress=100, detail="Existing destination kept unchanged.")
            return
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise ValueError("FFmpeg and ffprobe are required. See Setup in the app.")
        root.mkdir(parents=True, exist_ok=True)
        stage = root / ".reelforge" / "staging" / jid
        stage.mkdir(parents=True, exist_ok=True)
        if not stage.resolve().is_relative_to(root):
            raise ValueError("Staging directory escapes the selected root.")
        urls = item.parts or [item.url]
        parts = [self.download(jid, url, item, rules, stage, i, len(urls)) for i, url in enumerate(urls, 1)]
        self.store.update(jid, state="merging", progress=88, detail="Preparing final video…")
        if len(parts) > 1:
            if rules.stitch == "normalize":
                normalized = []
                for index, part in enumerate(parts, 1):
                    self.check(jid)
                    self.store.update(jid, detail=f"Normalizing part {index}/{len(parts)} to 720p / H.264 / AAC…")
                    dest = stage / f"normalized-{index:03d}.mkv"
                    self.normalize_part(jid, part, dest)
                    normalized.append(dest)
                parts = normalized
            elif any(signature(probe(p)) != signature(probe(parts[0])) for p in parts[1:]):
                raise ValueError("Parts have incompatible codecs or stream layouts. Choose Normalize and retry with a new job.")
            concat = stage / "parts.txt"
            concat.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
            source = stage / "joined.mkv"
            self.run(jid, ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "1", "-i", "parts.txt", "-map", "0:v:0", "-map", "0:a?", "-c", "copy", source.name], cwd=stage)
            expected = sum(float(probe(p)["format"]["duration"]) for p in parts)
            actual = float(probe(source)["format"]["duration"])
            if abs(expected - actual) > max(2, expected * .02):
                raise ValueError("Joined duration does not match the sum of the parts; delivery stopped.")
        else:
            source = parts[0]
        final = stage / ("final." + rules.container)
        if rules.container == "mp4":
            # MP4 delivery uses broadly compatible codecs, rather than assuming
            # arbitrary YouTube codecs will play on an older media device.
            self.run(jid, ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(final)])
        else:
            shutil.copyfile(source, final)
        probe(final)
        self.check(jid)
        with self.lock:
            self.check(jid)
            deliver(final, target)
            self.store.update(jid, state="completed", progress=100, detail=str(target), error="")
        shutil.rmtree(stage, ignore_errors=True)

    def worker(self):
        while not self.stop.wait(.2):
            with self.lock:
                row = next((r for r in self.store.rows() if r["state"] == "queued"), None)
                if not row:
                    continue
                self.active = row["id"]
                self.store.update(row["id"], state="running", detail="Resolving source…")
            try:
                self.execute(row)
            except Interrupted:
                current = self.store.get(row["id"])
                if current and current["state"] not in {"paused", "cancelled", "queued"}:
                    self.store.update(row["id"], state="paused", detail="Interrupted; resume to continue.")
            except Exception as exc:
                current = self.store.get(row["id"])
                if current and current["state"] not in {"paused", "cancelled"}:
                    self.store.update(row["id"], state="failed", error=str(exc)[-3000:], detail="Failed; see error details.")
            finally:
                with self.lock:
                    self.interrupted.discard(row["id"])
                    self.active = None

    def close(self):
        self.stop.set()
        with self.lock:
            self.kill()
        if self.thread.is_alive():
            self.thread.join(timeout=35)


def fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps({"urls": payload["item"].get("parts") or [payload["item"]["url"]], "target": payload["target"], "rules": payload["rules"]}, sort_keys=True).encode()).hexdigest()
