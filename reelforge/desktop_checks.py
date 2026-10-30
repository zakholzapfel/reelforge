"""Exercise packaged tools with no dependency on the user's installed tools."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .runtime import configure_runtime, quiet_process


def bundled_tools_self_test():
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Run this check from a built ReelForge executable")
    os.environ["PATH"] = ""
    configure_runtime()
    root = (Path(sys._MEIPASS) / "tools").resolve()
    tools = {}
    for name in ["ffmpeg", "ffprobe", "deno"]:
        found = shutil.which(name)
        if not found or Path(found).resolve().parent != root:
            raise RuntimeError(f"{name} is missing from the app bundle")
        tools[name] = str(Path(found).resolve())
    def run(name, arguments):
        return subprocess.run([tools[name], *arguments], capture_output=True, text=True, check=True,
                              timeout=90, **quiet_process())
    run("deno", ["eval", "if (1 + 1 !== 2) throw new Error('JavaScript failed'); console.log('ok')"])
    with tempfile.TemporaryDirectory(prefix="reelforge-tools-check-") as directory:
        video = Path(directory) / "sample.mp4"
        run("ffmpeg", ["-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=160x90:r=10",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "0.3", "-c:v", "libx264",
            "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(video)])
        result = json.loads(run("ffprobe", ["-v", "error", "-show_streams", "-of", "json", str(video)]).stdout)
        codecs = {stream["codec_name"] for stream in result["streams"]}
        if not {"h264", "aac"}.issubset(codecs):
            raise RuntimeError("The packaged encoder/probe check failed")
    if sys.stdout:
        print("Bundled FFmpeg, ffprobe, H.264/AAC, and Deno passed with an empty system PATH.")
