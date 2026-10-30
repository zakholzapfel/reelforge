"""Paths and child processes shared by source and packaged desktop builds."""
import os
from pathlib import Path
import subprocess
import sys


def configure_runtime():
    roots = []
    if getattr(sys, "frozen", False):
        roots += [Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "tools", Path(sys.executable).parent / "tools"]
    if sys.platform == "darwin":
        roots += [Path("/opt/homebrew/bin"), Path("/usr/local/bin")]
    existing = os.environ.get("PATH", "").split(os.pathsep)
    os.environ["PATH"] = os.pathsep.join(dict.fromkeys([str(p) for p in roots if p.is_dir()] + existing))


def ytdlp_command():
    if getattr(sys, "frozen", False):
        return [sys.executable, "--reelforge-ytdlp"]
    return [sys.executable, "-m", "yt_dlp"]


def quiet_process():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def dispatch_tool(argv):
    if argv and argv[0] == "--reelforge-ytdlp":
        restore_child_stdio()
        import yt_dlp
        yt_dlp.main(argv[1:])
        return True
    return False


def restore_child_stdio():
    """Windowed Windows executables need their inherited pipe handles restored.

    The GUI parent has no console. Its yt-dlp child still writes metadata and
    progress through Popen pipes, without opening an extra terminal window.
    """
    for name, number, mode in [("stdin",-10,"r"),("stdout",-11,"w"),("stderr",-12,"w")]:
        if getattr(sys,name) is not None:
            continue
        stream = None
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            import msvcrt
            get = ctypes.windll.kernel32.GetStdHandle
            get.argtypes = [wintypes.DWORD]
            get.restype = wintypes.HANDLE
            handle = get(number)
            if handle not in {None, 0, ctypes.c_void_p(-1).value}:
                try:
                    flags = os.O_RDONLY if mode == "r" else os.O_WRONLY
                    fd = msvcrt.open_osfhandle(handle, flags | os.O_BINARY)
                    stream = os.fdopen(fd, mode, encoding="utf-8", errors="replace", buffering=1)
                except OSError:
                    pass
        if stream is None:
            stream = open(os.devnull, mode, encoding="utf-8")
        setattr(sys,name,stream)
