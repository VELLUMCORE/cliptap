import json
import os
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 17723
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


def _first_existing(paths):
    for path in paths:
        if path and Path(path).exists():
            return Path(path)
    return None


def find_yt_dlp():
    """Return (command_list, description) for yt-dlp.

    v1.1.4 only checked PATH, so `py -m pip install yt-dlp` could still fail on
    Windows when the Scripts folder was not added to PATH. This fallback allows
    the helper to run yt-dlp as a Python module from the same Python interpreter.
    """
    executable = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    if executable:
        return [executable], f"PATH: {executable}"

    try:
        import yt_dlp  # noqa: F401
    except Exception:
        return None, "NOT FOUND"

    return [sys.executable, "-m", "yt_dlp"], f"Python module: {sys.executable} -m yt_dlp"


def find_ffmpeg():
    executable = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if executable:
        return Path(executable), f"PATH: {executable}"

    local = _first_existing([
        LOCAL_BIN_DIR / "ffmpeg.exe",
        LOCAL_BIN_DIR / "ffmpeg",
        HELPER_DIR / "ffmpeg.exe",
        HELPER_DIR / "ffmpeg",
    ])
    if local:
        return local, f"local: {local}"

    return None, "NOT FOUND"


def dependency_status():
    yt_cmd, yt_desc = find_yt_dlp()
    ffmpeg_path, ffmpeg_desc = find_ffmpeg()
    return {
        "yt_dlp": bool(yt_cmd),
        "ytDlp": {
            "ok": bool(yt_cmd),
            "command": yt_cmd,
            "description": yt_desc,
        },
        "ffmpeg": bool(ffmpeg_path),
        "ffmpegInfo": {
            "ok": bool(ffmpeg_path),
            "path": str(ffmpeg_path) if ffmpeg_path else None,
            "description": ffmpeg_desc,
        },
        "outputDir": str(OUTPUT_DIR),
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


def build_command(payload: dict) -> list[str]:
    yt_dlp_cmd, _ = find_yt_dlp()
    ffmpeg_path, _ = find_ffmpeg()
    if not yt_dlp_cmd:
        raise RuntimeError(
            "yt-dlp를 찾을 수 없어. `py -m pip install -U yt-dlp`로 설치하거나 yt-dlp.exe를 PATH에 추가해줘."
        )
    if not ffmpeg_path:
        raise RuntimeError(
            "ffmpeg.exe를 찾을 수 없어. `pip install ffmpeg`는 ffmpeg 실행 파일을 설치하지 않아. "
            "winget으로 FFmpeg를 설치하거나 helper/bin/ffmpeg.exe 위치에 넣어줘."
        )

    url = str(payload.get("url", "")).strip()
    if not is_allowed_url(url):
        raise ValueError("지원하는 YouTube URL이 아니야.")

    mode = str(payload.get("mode", "section")).strip().lower()
    if mode not in {"section", "full"}:
        raise ValueError("지원하지 않는 다운로드 모드야.")

    start = None
    end = None
    if mode == "section":
        try:
            start = float(payload.get("start"))
            end = float(payload.get("end"))
        except (TypeError, ValueError):
            raise ValueError("시작/끝 시간이 숫자가 아니야.")

        if start < 0 or end <= start:
            raise ValueError("끝 시간이 시작 시간보다 뒤여야 해.")

    quality = str(payload.get("quality", "best"))
    if quality not in FORMAT_MAP:
        quality = "best"

    cookie_browser = str(payload.get("cookieBrowser", "")).strip().lower()
    if cookie_browser not in ALLOWED_COOKIE_BROWSERS:
        raise ValueError("지원하지 않는 쿠키 브라우저 값이야.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if mode == "section":
        section = f"*{seconds_to_clock(start)}-{seconds_to_clock(end)}"
        output_template = str(OUTPUT_DIR / "%(title).160s [%(id)s] %(section_start)s-%(section_end)s.%(ext)s")
    else:
        section = None
        output_template = str(OUTPUT_DIR / "%(title).160s [%(id)s].%(ext)s")

    cmd = list(yt_dlp_cmd)

    if quality == "audio":
        cmd += ["-f", FORMAT_MAP[quality], "-x", "--audio-format", "mp3"]
    else:
        cmd += ["-f", FORMAT_MAP[quality], "--merge-output-format", "mp4"]

    cmd += ["--ffmpeg-location", str(ffmpeg_path)]

    if mode == "section":
        cmd += ["--download-sections", section]
        if bool(payload.get("forceKeyframes")):
            cmd.append("--force-keyframes-at-cuts")

    if cookie_browser:
        cmd += ["--cookies-from-browser", cookie_browser]

    cmd += ["-o", output_template, url]
    return cmd


class Handler(BaseHTTPRequestHandler):
    server_version = "ClipTapHelper/1.1.5"

    def log_message(self, fmt, *args):
        print("[ClipTap] " + fmt % args)

    def _headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json(self, data, status=200):
        self._headers(status)
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self._headers(204)

    def do_GET(self):
        if self.path == "/health":
            data = {"ok": True}
            data.update(dependency_status())
            self._json(data)
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/download":
            self._json({"error": "not found"}, 404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
            cmd = build_command(payload)
        except Exception as exc:
            self._json({"error": str(exc)}, 500)
            return

        print("\n[ClipTap] 실행:")
        print(" ".join(f'\"{part}\"' if " " in part else part for part in cmd))
        print()

        try:
            subprocess.Popen(cmd, cwd=str(OUTPUT_DIR))
        except Exception as exc:
            self._json({"error": f"실행 실패: {exc}"}, 500)
            return

        self._json({"ok": True, "outputDir": str(OUTPUT_DIR)})


def main():
    print("ClipTap helper starting...")
    print(f"Output: {OUTPUT_DIR}")
    print("Checking commands:")
    status = dependency_status()
    print(f"  yt-dlp: {'OK' if status['yt_dlp'] else 'NOT FOUND'} ({status['ytDlp']['description']})")
    print(f"  ffmpeg: {'OK' if status['ffmpeg'] else 'NOT FOUND'} ({status['ffmpegInfo']['description']})")
    if not status["yt_dlp"]:
        print("\nTip: py -m pip install -U yt-dlp")
    if not status["ffmpeg"]:
        print("Tip: pip install ffmpeg 는 ffmpeg.exe 설치가 아니야. winget/공식 빌드로 FFmpeg를 설치해야 해.")
        print(f"     또는 ffmpeg.exe를 여기에 넣어도 돼: {LOCAL_BIN_DIR}")
    print(f"\nClipTap helper running at http://{HOST}:{PORT}")
    print("이 창을 닫으면 확장 다운로드 기능도 꺼져.\n")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nClipTap helper stopped.")


if __name__ == "__main__":
    if sys.version_info < (3, 9):
        print("Python 3.9 이상 권장.")
    main()
