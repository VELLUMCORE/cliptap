"""ClipTap Helper GUI.

A small local Windows app that receives download requests from the ClipTap
browser extension and runs yt-dlp/FFmpeg without requiring a terminal window.
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.parse import urlparse
from urllib.request import urlopen

HOST = "127.0.0.1"
PORT = 17723
APP_NAME = "ClipTap Helper"
APP_VERSION = "1.2.1"
OUTPUT_DIR = Path.home() / "Downloads" / "ClipTap"
HELPER_DIR = Path(__file__).resolve().parent
LOCAL_BIN_DIR = HELPER_DIR / "bin"

FORMAT_MAP = {
    "best": "bv*+ba/b",
    "1080": "bv*[height<=1080]+ba/b[height<=1080]/b",
    "720": "bv*[height<=720]+ba/b[height<=720]/b",
    "audio": "ba/b",
}

ALLOWED_COOKIE_BROWSERS = {"", "edge", "chrome", "firefox"}
ALLOWED_HOST_SUFFIXES = (
    "youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
)

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

PALETTE = {
    "bg": "#0b1220",
    "surface": "#111c2f",
    "surface_2": "#16243a",
    "surface_3": "#1d2d46",
    "border": "#263a59",
    "text": "#edf5ff",
    "muted": "#95a7bd",
    "blue": "#2f8cff",
    "blue_dark": "#1769d1",
    "orange": "#ff9d1f",
    "orange_dark": "#db7900",
    "green": "#4fd18b",
    "red": "#ff6b6b",
    "yellow": "#ffd166",
}


class ClipTapError(RuntimeError):
    pass


class CancelledError(RuntimeError):
    pass


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return HELPER_DIR


def first_existing(paths):
    for path in paths:
        if path and Path(path).exists():
            return Path(path)
    return None


def run_probe(command: list[str], timeout: int = 8) -> bool:
    try:
        subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
            check=False,
        )
        return True
    except Exception:
        return False


def find_python_launcher() -> list[str] | None:
    candidates = []
    py = shutil.which("py") or shutil.which("py.exe")
    if py:
        candidates.append([py])
    python = shutil.which("python") or shutil.which("python.exe")
    if python:
        candidates.append([python])
    if not getattr(sys, "frozen", False):
        candidates.append([sys.executable])

    for command in candidates:
        if run_probe(command + ["--version"]):
            return command
    return None


def find_yt_dlp() -> tuple[list[str] | None, str]:
    local = first_existing([
        app_base_dir() / "yt-dlp.exe",
        app_base_dir() / "bin" / "yt-dlp.exe",
        LOCAL_BIN_DIR / "yt-dlp.exe",
    ])
    if local:
        return [str(local)], f"Local executable: {local}"

    executable = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    if executable:
        return [executable], f"PATH: {executable}"

    launcher = find_python_launcher()
    if launcher and run_probe(launcher + ["-m", "yt_dlp", "--version"]):
        return launcher + ["-m", "yt_dlp"], "Python module: " + " ".join(launcher + ["-m", "yt_dlp"])

    return None, "Not installed"


def find_ffmpeg() -> tuple[Path | None, str]:
    executable = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if executable:
        return Path(executable), f"PATH: {executable}"

    local = first_existing([
        app_base_dir() / "ffmpeg.exe",
        app_base_dir() / "bin" / "ffmpeg.exe",
        LOCAL_BIN_DIR / "ffmpeg.exe",
        HELPER_DIR / "ffmpeg.exe",
    ])
    if local:
        return local, f"Local executable: {local}"

    return None, "Not installed"


def dependency_status() -> dict:
    yt_cmd, yt_desc = find_yt_dlp()
    ffmpeg_path, ffmpeg_desc = find_ffmpeg()
    return {
        "yt_dlp": bool(yt_cmd),
        "ytDlp": {"ok": bool(yt_cmd), "command": yt_cmd, "description": yt_desc},
        "ffmpeg": bool(ffmpeg_path),
        "ffmpegInfo": {
            "ok": bool(ffmpeg_path),
            "path": str(ffmpeg_path) if ffmpeg_path else None,
            "description": ffmpeg_desc,
        },
        "outputDir": str(OUTPUT_DIR),
        "appVersion": APP_VERSION,
    }


def seconds_to_clock(value) -> str:
    value = max(0.0, float(value))
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    seconds = int(value % 60)
    millis = round((value - int(value)) * 1000)
    if millis == 1000:
        seconds += 1
        millis = 0
        if seconds == 60:
            minutes += 1
            seconds = 0
        if minutes == 60:
            hours += 1
            minutes = 0
    base = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{base}.{millis:03d}" if millis else base


def is_allowed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in ALLOWED_HOST_SUFFIXES)


def clean_payload(payload: dict) -> dict:
    url = str(payload.get("url", "")).strip()
    if not is_allowed_url(url):
        raise ValueError("Unsupported YouTube URL.")

    mode = str(payload.get("mode", "section")).strip().lower()
    if mode not in {"section", "full"}:
        raise ValueError("Unsupported download mode.")

    quality = str(payload.get("quality", "best"))
    if quality not in FORMAT_MAP:
        quality = "best"

    cookie_browser = str(payload.get("cookieBrowser", "")).strip().lower()
    if cookie_browser not in ALLOWED_COOKIE_BROWSERS:
        raise ValueError("Unsupported cookie browser value.")

    cleaned = {
        "url": url,
        "mode": mode,
        "title": str(payload.get("title", "")).strip(),
        "quality": quality,
        "cookieBrowser": cookie_browser,
        "forceKeyframes": bool(payload.get("forceKeyframes")),
    }

    if mode == "section":
        try:
            start = float(payload.get("start"))
            end = float(payload.get("end"))
        except (TypeError, ValueError):
            raise ValueError("Start/end time must be numeric.")
        if start < 0 or end <= start:
            raise ValueError("The end time must be after the start time.")
        cleaned["start"] = start
        cleaned["end"] = end

    return cleaned


def popen_text(command: list[str], cwd: Path | None = None) -> subprocess.Popen:
    return subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=CREATE_NO_WINDOW,
    )


@dataclass
class DownloadJob:
    id: str
    payload: dict
    app: "ClipTapApp"
    title: str = "Preparing download..."
    thumbnail_url: str = ""
    is_live: bool = False
    status: str = "Queued"
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    process: subprocess.Popen | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)

    def start(self):
        threading.Thread(target=self.run, daemon=True).start()

    def cancel(self):
        self.cancel_event.set()
        self.status = "Cancelling..."
        self.app.emit(("job", self))
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass

    def run(self):
        try:
            self.prepare_metadata()
            self.download()
        except CancelledError:
            self.status = "Cancelled"
            self.app.emit(("job", self))
        except Exception as exc:
            self.status = f"Failed: {exc}"
            self.app.emit(("job", self))
        finally:
            if self.process and self.process.poll() is None:
                try:
                    self.process.kill()
                except Exception:
                    pass

    def prepare_metadata(self):
        self.status = "Reading video information..."
        self.app.emit(("job", self))

        cmd_base, _ = find_yt_dlp()
        if not cmd_base:
            raise ClipTapError("yt-dlp is not installed.")

        command = list(cmd_base) + ["-J", "--no-warnings", "--skip-download"]
        if self.payload.get("cookieBrowser"):
            command += ["--cookies-from-browser", self.payload["cookieBrowser"]]
        command.append(self.payload["url"])

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                creationflags=CREATE_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                info = json.loads(result.stdout)
                self.title = info.get("title") or self.payload.get("title") or "Untitled video"
                self.thumbnail_url = info.get("thumbnail") or ""
                self.is_live = bool(info.get("is_live"))
            else:
                self.title = self.payload.get("title") or "Untitled video"
        except Exception:
            self.title = self.payload.get("title") or "Untitled video"

        self.app.emit(("job", self))

    def build_download_command(self) -> list[str]:
        yt_dlp_cmd, _ = find_yt_dlp()
        ffmpeg_path, _ = find_ffmpeg()
        if not yt_dlp_cmd:
            raise ClipTapError("yt-dlp is not installed.")
        if not ffmpeg_path:
            raise ClipTapError("FFmpeg is not installed.")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        mode = self.payload["mode"]
        quality = self.payload["quality"]

        command = list(yt_dlp_cmd)
        command += ["--newline", "--no-playlist"]

        if quality == "audio":
            command += ["-f", FORMAT_MAP[quality], "-x", "--audio-format", "mp3"]
        else:
            command += ["-f", FORMAT_MAP[quality], "--merge-output-format", "mp4"]

        command += ["--ffmpeg-location", str(ffmpeg_path)]

        if mode == "section":
            section = f"*{seconds_to_clock(self.payload['start'])}-{seconds_to_clock(self.payload['end'])}"
            command += ["--download-sections", section]
            output_template = str(OUTPUT_DIR / "%(title).160s [%(id)s] %(section_start)s-%(section_end)s.%(ext)s")
            if self.payload.get("forceKeyframes"):
                command.append("--force-keyframes-at-cuts")
        else:
            output_template = str(OUTPUT_DIR / "%(title).160s [%(id)s].%(ext)s")
            if self.is_live:
                command += ["--hls-use-mpegts"]

        if self.payload.get("cookieBrowser"):
            command += ["--cookies-from-browser", self.payload["cookieBrowser"]]

        command += ["-o", output_template, self.payload["url"]]
        return command

    def download(self):
        command = self.build_download_command()
        self.status = "Recording live stream..." if self.is_live and self.payload["mode"] == "full" else "Downloading..."
        self.app.emit(("job", self))

        self.process = popen_text(command, OUTPUT_DIR)
        percent_re = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")
        speed_re = re.compile(r"\bat\s+([^\s]+/s)")
        eta_re = re.compile(r"\bETA\s+([^\s]+)")

        while True:
            if self.cancel_event.is_set():
                raise CancelledError()

            line = self.process.stdout.readline() if self.process.stdout else ""
            if not line and self.process.poll() is not None:
                break
            if not line:
                time.sleep(0.05)
                continue

            line = line.strip()
            match = percent_re.search(line)
            if match and not (self.is_live and self.payload["mode"] == "full"):
                self.progress = max(0.0, min(100.0, float(match.group(1))))

            speed_match = speed_re.search(line)
            eta_match = eta_re.search(line)
            if speed_match:
                self.speed = speed_match.group(1)
            if eta_match:
                self.eta = eta_match.group(1)

            if "[download] Destination:" in line:
                self.status = "Downloading media..."
            elif "Merger" in line or "Merging formats" in line:
                self.status = "Merging video and audio..."
            elif "Deleting original file" in line:
                self.status = "Cleaning temporary files..."

            self.app.emit(("job", self))

        code = self.process.wait()
        if self.cancel_event.is_set():
            raise CancelledError()
        if code != 0:
            raise ClipTapError(f"yt-dlp exited with code {code}.")

        self.progress = 100.0
        self.status = "Finished"
        self.app.emit(("job", self))


class ClipTapHandler(BaseHTTPRequestHandler):
    server_version = f"ClipTapHelper/{APP_VERSION}"
    app: "ClipTapApp" | None = None

    def log_message(self, fmt, *args):
        if self.app:
            self.app.emit(("server-log", fmt % args))

    def headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def send_json(self, data, status=200):
        self.headers(status)
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self.headers(204)

    def do_GET(self):
        if self.path == "/health":
            data = {"ok": True}
            data.update(dependency_status())
            self.send_json(data)
            return
        self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/download":
            self.send_json({"error": "not found"}, 404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            payload = clean_payload(json.loads(raw.decode("utf-8")))
            if not self.app:
                raise ClipTapError("ClipTap Helper is not ready.")
            job_id = self.app.create_job(payload)
            self.send_json({"ok": True, "jobId": job_id, "outputDir": str(OUTPUT_DIR)})
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)


class JobCard:
    def __init__(self, parent, job: DownloadJob):
        self.job_id = job.id
        self.photo = None
        self.frame = ttk.Frame(parent, padding=14, style="Card.TFrame")
        self.frame.columnconfigure(1, weight=1)

        self.thumb = tk.Label(
            self.frame,
            text="No preview",
            anchor="center",
            width=18,
            height=5,
            bg=PALETTE["surface_3"],
            fg=PALETTE["muted"],
            activebackground=PALETTE["surface_3"],
            activeforeground=PALETTE["muted"],
            bd=0,
            highlightthickness=1,
            highlightbackground=PALETTE["border"],
        )
        self.thumb.grid(row=0, column=0, rowspan=4, sticky="nsew", padx=(0, 14))

        self.title = ttk.Label(self.frame, text=job.title, style="CardTitle.TLabel", wraplength=430)
        self.title.grid(row=0, column=1, sticky="ew")

        self.meta = ttk.Label(self.frame, text="Queued", style="CardMeta.TLabel", wraplength=430, justify="left")
        self.meta.grid(row=1, column=1, sticky="ew", pady=(6, 8))

        self.progress = ttk.Progressbar(self.frame, mode="determinate", maximum=100, style="Accent.Horizontal.TProgressbar")
        self.progress.grid(row=2, column=1, sticky="ew")

        self.cancel_button = ttk.Button(self.frame, text="Cancel", style="Danger.TButton", command=lambda: job.cancel())
        self.cancel_button.grid(row=0, column=2, rowspan=2, sticky="ne", padx=(12, 0))

        self.update(job)
        if job.thumbnail_url:
            self.load_thumbnail(job.thumbnail_url)

    def load_thumbnail(self, url: str):
        def worker():
            try:
                from PIL import Image, ImageTk
                import io

                with urlopen(url, timeout=10) as res:
                    data = res.read(5_000_000)
                image = Image.open(io.BytesIO(data)).convert("RGB")
                image.thumbnail((150, 84))
                photo = ImageTk.PhotoImage(image)
                self.frame.after(0, lambda: self.set_thumbnail(photo))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def set_thumbnail(self, photo):
        self.photo = photo
        self.thumb.configure(image=photo, text="")

    def update(self, job: DownloadJob):
        self.title.configure(text=job.title)

        mode = "Full video" if job.payload["mode"] == "full" else "Selected section"
        if job.payload["mode"] == "section":
            mode += f" · {seconds_to_clock(job.payload['start'])} → {seconds_to_clock(job.payload['end'])}"
        if job.is_live and job.payload["mode"] == "full":
            mode = "Live recording · continues until the stream ends or you cancel"

        details = job.status
        if job.speed:
            details += f" · {job.speed}"
        if job.eta and not job.is_live:
            details += f" · ETA {job.eta}"
        self.meta.configure(text=f"{mode}\n{details}")

        if job.is_live and job.payload["mode"] == "full" and job.status not in {"Finished", "Cancelled"} and not job.status.startswith("Failed"):
            self.progress.configure(mode="indeterminate", style="Live.Horizontal.TProgressbar")
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate", style="Accent.Horizontal.TProgressbar", value=job.progress)

        if job.status in {"Finished", "Cancelled"} or job.status.startswith("Failed"):
            self.cancel_button.state(["disabled"])

        if job.thumbnail_url and not self.photo:
            self.load_thumbnail(job.thumbnail_url)


class ClipTapApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("760x560")
        self.root.minsize(680, 480)

        self.events: queue.Queue = queue.Queue()
        self.jobs: dict[str, DownloadJob] = {}
        self.cards: dict[str, JobCard] = {}
        self.server: ThreadingHTTPServer | None = None

        self.setup_style()
        self.build_ui()
        self.refresh_dependencies()
        self.start_server()
        self.root.after(120, self.process_events)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_style(self):
        self.root.configure(bg=PALETTE["bg"])
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TFrame", background=PALETTE["bg"])
        style.configure("App.TFrame", background=PALETTE["bg"])
        style.configure("Hero.TFrame", background=PALETTE["surface"], relief="flat")
        style.configure("Card.TFrame", background=PALETTE["surface"], relief="solid", borderwidth=1)
        style.configure("Panel.TFrame", background=PALETTE["surface_2"], relief="solid", borderwidth=1)

        style.configure("TLabel", background=PALETTE["bg"], foreground=PALETTE["text"], font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=PALETTE["surface"], foreground=PALETTE["text"], font=("Segoe UI", 19, "bold"))
        style.configure("HeroSub.TLabel", background=PALETTE["surface"], foreground=PALETTE["muted"], font=("Segoe UI", 10))
        style.configure("Section.TLabel", background=PALETTE["bg"], foreground=PALETTE["text"], font=("Segoe UI", 11, "bold"))
        style.configure("Subtle.TLabel", background=PALETTE["bg"], foreground=PALETTE["muted"])
        style.configure("CardTitle.TLabel", background=PALETTE["surface"], foreground=PALETTE["text"], font=("Segoe UI", 10, "bold"))
        style.configure("CardMeta.TLabel", background=PALETTE["surface"], foreground=PALETTE["muted"], font=("Segoe UI", 9))
        style.configure("CardSubtle.TLabel", background=PALETTE["surface"], foreground=PALETTE["muted"], font=("Segoe UI", 9))
        style.configure("StatusGood.TLabel", background=PALETTE["surface"], foreground=PALETTE["green"], font=("Segoe UI", 10, "bold"))
        style.configure("StatusBad.TLabel", background=PALETTE["surface"], foreground=PALETTE["red"], font=("Segoe UI", 10, "bold"))
        style.configure("Server.TLabel", background=PALETTE["surface_2"], foreground=PALETTE["muted"], font=("Segoe UI", 9))

        style.configure("TLabelframe", background=PALETTE["bg"], bordercolor=PALETTE["border"], lightcolor=PALETTE["border"], darkcolor=PALETTE["border"])
        style.configure("TLabelframe.Label", background=PALETTE["bg"], foreground=PALETTE["text"], font=("Segoe UI", 10, "bold"))

        style.configure("TButton", font=("Segoe UI", 9), padding=(10, 6), background=PALETTE["surface_3"], foreground=PALETTE["text"], bordercolor=PALETTE["border"], lightcolor=PALETTE["surface_3"], darkcolor=PALETTE["surface_3"])
        style.map("TButton", background=[("active", PALETTE["border"]), ("disabled", PALETTE["surface_2"])], foreground=[("disabled", "#637287")])
        style.configure("Accent.TButton", background=PALETTE["blue"], foreground="#ffffff", bordercolor=PALETTE["blue_dark"], lightcolor=PALETTE["blue"], darkcolor=PALETTE["blue_dark"])
        style.map("Accent.TButton", background=[("active", PALETTE["blue_dark"]), ("disabled", PALETTE["surface_2"])])
        style.configure("Warning.TButton", background=PALETTE["orange"], foreground="#1b1202", bordercolor=PALETTE["orange_dark"], lightcolor=PALETTE["orange"], darkcolor=PALETTE["orange_dark"])
        style.map("Warning.TButton", background=[("active", PALETTE["orange_dark"]), ("disabled", PALETTE["surface_2"])])
        style.configure("Danger.TButton", background=PALETTE["surface_3"], foreground=PALETTE["red"], bordercolor=PALETTE["border"])
        style.map("Danger.TButton", background=[("active", "#3a2332"), ("disabled", PALETTE["surface_2"])], foreground=[("disabled", "#77515c")])

        style.configure("Accent.Horizontal.TProgressbar", troughcolor=PALETTE["surface_3"], background=PALETTE["blue"], bordercolor=PALETTE["surface_3"], lightcolor=PALETTE["blue"], darkcolor=PALETTE["blue_dark"])
        style.configure("Live.Horizontal.TProgressbar", troughcolor=PALETTE["surface_3"], background=PALETTE["orange"], bordercolor=PALETTE["surface_3"], lightcolor=PALETTE["orange"], darkcolor=PALETTE["orange_dark"])
        style.configure("Vertical.TScrollbar", background=PALETTE["surface_3"], troughcolor=PALETTE["bg"], bordercolor=PALETTE["bg"], arrowcolor=PALETTE["muted"])

    def build_ui(self):
        outer = ttk.Frame(self.root, padding=18, style="App.TFrame")
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        hero = ttk.Frame(outer, padding=18, style="Hero.TFrame")
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        hero.columnconfigure(0, weight=1)
        ttk.Label(hero, text="ClipTap Helper", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            hero,
            text="Ready to receive YouTube download requests from the ClipTap extension.",
            style="HeroSub.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(hero, text=f"v{APP_VERSION}", style="HeroSub.TLabel").grid(row=0, column=1, sticky="ne")

        deps = ttk.Frame(outer, style="App.TFrame")
        deps.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        deps.columnconfigure(0, weight=1)
        deps.columnconfigure(1, weight=1)

        self.ytdlp_box = ttk.Frame(deps, padding=14, style="Card.TFrame")
        self.ytdlp_box.grid(row=0, column=0, sticky="ew", padx=(0, 7))
        self.ytdlp_status = ttk.Label(self.ytdlp_box, text="yt-dlp: checking...", style="CardTitle.TLabel")
        self.ytdlp_status.pack(anchor="w")
        self.ytdlp_detail = ttk.Label(self.ytdlp_box, text="", style="CardSubtle.TLabel", wraplength=320)
        self.ytdlp_detail.pack(anchor="w", pady=(5, 10))
        self.ytdlp_button = ttk.Button(self.ytdlp_box, text="Install / Update yt-dlp", style="Accent.TButton", command=self.install_ytdlp)
        self.ytdlp_button.pack(anchor="w")

        self.ffmpeg_box = ttk.Frame(deps, padding=14, style="Card.TFrame")
        self.ffmpeg_box.grid(row=0, column=1, sticky="ew", padx=(7, 0))
        self.ffmpeg_status = ttk.Label(self.ffmpeg_box, text="FFmpeg: checking...", style="CardTitle.TLabel")
        self.ffmpeg_status.pack(anchor="w")
        self.ffmpeg_detail = ttk.Label(self.ffmpeg_box, text="", style="CardSubtle.TLabel", wraplength=320)
        self.ffmpeg_detail.pack(anchor="w", pady=(5, 10))
        self.ffmpeg_button = ttk.Button(self.ffmpeg_box, text="Install FFmpeg", style="Warning.TButton", command=self.install_ffmpeg)
        self.ffmpeg_button.pack(anchor="w")

        server_bar = ttk.Frame(outer, padding=12, style="Panel.TFrame")
        server_bar.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        server_bar.columnconfigure(0, weight=1)
        self.server_status = ttk.Label(server_bar, text=f"Server starting on http://{HOST}:{PORT}", style="Server.TLabel")
        self.server_status.grid(row=0, column=0, sticky="w")
        ttk.Button(server_bar, text="Open downloads", command=self.open_output_folder).grid(row=0, column=1, sticky="e")
        ttk.Button(server_bar, text="Refresh", command=self.refresh_dependencies).grid(row=0, column=2, sticky="e", padx=(8, 0))

        jobs_frame = ttk.LabelFrame(outer, text="Download requests", padding=10)
        jobs_frame.grid(row=3, column=0, sticky="nsew")
        jobs_frame.columnconfigure(0, weight=1)
        jobs_frame.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(jobs_frame, highlightthickness=0, bg=PALETTE["bg"], bd=0)
        self.scrollbar = ttk.Scrollbar(jobs_frame, orient="vertical", command=self.canvas.yview)
        self.jobs_inner = ttk.Frame(self.canvas, style="App.TFrame")
        self.jobs_inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.jobs_inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.canvas_window, width=e.width))

        self.empty_label = ttk.Label(
            self.jobs_inner,
            text="No download requests yet. Open a YouTube video and use ClipTap from the player controls.",
            style="Subtle.TLabel",
        )
        self.empty_label.pack(anchor="w", pady=10)

    def emit(self, item):
        self.events.put(item)

    def process_events(self):
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "job":
                self.render_job(payload)
            elif kind == "server-log":
                pass
            elif kind == "install-done":
                self.refresh_dependencies()
                messagebox.showinfo(APP_NAME, payload)
            elif kind == "install-failed":
                self.refresh_dependencies()
                messagebox.showerror(APP_NAME, payload)
        self.root.after(120, self.process_events)

    def render_job(self, job: DownloadJob):
        if self.empty_label.winfo_exists():
            self.empty_label.pack_forget()
        card = self.cards.get(job.id)
        if not card:
            card = JobCard(self.jobs_inner, job)
            card.frame.pack(fill="x", pady=(0, 10))
            self.cards[job.id] = card
        else:
            card.update(job)

    def refresh_dependencies(self):
        status = dependency_status()
        self.ytdlp_status.configure(
            text="yt-dlp ready" if status["yt_dlp"] else "yt-dlp missing",
            style="StatusGood.TLabel" if status["yt_dlp"] else "StatusBad.TLabel",
        )
        self.ytdlp_detail.configure(text=status["ytDlp"]["description"])
        self.ytdlp_button.state(["!disabled"])

        self.ffmpeg_status.configure(
            text="FFmpeg ready" if status["ffmpeg"] else "FFmpeg missing",
            style="StatusGood.TLabel" if status["ffmpeg"] else "StatusBad.TLabel",
        )
        self.ffmpeg_detail.configure(text=status["ffmpegInfo"]["description"])
        self.ffmpeg_button.state(["!disabled"])

    def install_ytdlp(self):
        launcher = find_python_launcher()
        if not launcher:
            messagebox.showerror(APP_NAME, "Python was not found. Install Python first, then try again.")
            return
        self.ytdlp_button.state(["disabled"])
        self.ytdlp_status.configure(text="yt-dlp installing...", style="CardTitle.TLabel")
        threading.Thread(target=self.run_install, args=(launcher + ["-m", "pip", "install", "-U", "yt-dlp"], "yt-dlp installed or updated."), daemon=True).start()

    def install_ffmpeg(self):
        winget = shutil.which("winget") or shutil.which("winget.exe")
        if not winget:
            messagebox.showerror(APP_NAME, "winget was not found. Install FFmpeg manually or place ffmpeg.exe in helper/bin/.")
            return
        self.ffmpeg_button.state(["disabled"])
        self.ffmpeg_status.configure(text="FFmpeg installing...", style="CardTitle.TLabel")
        command = [
            winget,
            "install",
            "-e",
            "--id",
            "Gyan.FFmpeg",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
        threading.Thread(target=self.run_install, args=(command, "FFmpeg installation finished. Restart ClipTap Helper if it is still shown as missing."), daemon=True).start()

    def run_install(self, command: list[str], success_message: str):
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW,
            )
            if result.returncode != 0:
                raise ClipTapError(result.stdout[-1200:] or f"Installer exited with code {result.returncode}.")
            self.emit(("install-done", success_message))
        except Exception as exc:
            self.emit(("install-failed", str(exc)))

    def start_server(self):
        try:
            ClipTapHandler.app = self
            self.server = ThreadingHTTPServer((HOST, PORT), ClipTapHandler)
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
            self.server_status.configure(text=f"Server running at http://{HOST}:{PORT}")
        except OSError as exc:
            self.server_status.configure(text=f"Server failed to start ({exc})")
            messagebox.showerror(APP_NAME, f"Could not start local server on port {PORT}.\n\n{exc}")

    def create_job(self, payload: dict) -> str:
        status = dependency_status()
        if not status["yt_dlp"]:
            raise ClipTapError("yt-dlp is not installed. Open ClipTap Helper and click Install / Update yt-dlp.")
        if not status["ffmpeg"]:
            raise ClipTapError("FFmpeg is not installed. Open ClipTap Helper and click Install FFmpeg.")

        job_id = str(int(time.time() * 1000))
        job = DownloadJob(id=job_id, payload=payload, app=self)
        self.jobs[job_id] = job
        self.emit(("job", job))
        job.start()
        return job_id

    def open_output_folder(self):
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(str(OUTPUT_DIR))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(OUTPUT_DIR)])
        else:
            subprocess.Popen(["xdg-open", str(OUTPUT_DIR)])

    def on_close(self):
        active = [job for job in self.jobs.values() if job.process and job.process.poll() is None]
        if active and not messagebox.askyesno(APP_NAME, "Downloads are still running. Quit and cancel them?"):
            return
        for job in active:
            job.cancel()
        if self.server:
            self.server.shutdown()
        self.root.destroy()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    app = ClipTapApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
