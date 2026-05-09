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


def has_command(name: str) -> bool:
    return shutil.which(name) is not None


def seconds_to_clock(value) -> str:
    value = max(0.0, float(value))
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    seconds = int(value % 60)
    millis = round((value - int(value)) * 1000)
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
    url = str(payload.get("url", "")).strip()
    if not is_allowed_url(url):
        raise ValueError("지원하는 YouTube URL이 아니야.")

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

    section = f"*{seconds_to_clock(start)}-{seconds_to_clock(end)}"
    output_template = str(OUTPUT_DIR / "%(title).160s [%(id)s] %(section_start)s-%(section_end)s.%(ext)s")

    cmd = ["yt-dlp"]

    if quality == "audio":
        cmd += ["-f", FORMAT_MAP[quality], "-x", "--audio-format", "mp3"]
    else:
        cmd += ["-f", FORMAT_MAP[quality], "--merge-output-format", "mp4"]

    cmd += ["--download-sections", section]

    if bool(payload.get("forceKeyframes")):
        cmd.append("--force-keyframes-at-cuts")

    if cookie_browser:
        cmd += ["--cookies-from-browser", cookie_browser]

    cmd += ["-o", output_template, url]
    return cmd


class Handler(BaseHTTPRequestHandler):
    server_version = "ClipTapHelper/1.0"

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
            self._json({
                "ok": True,
                "yt_dlp": has_command("yt-dlp"),
                "ffmpeg": has_command("ffmpeg"),
                "outputDir": str(OUTPUT_DIR),
            })
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/download":
            self._json({"error": "not found"}, 404)
            return

        if not has_command("yt-dlp"):
            self._json({"error": "yt-dlp를 PATH에서 찾을 수 없어."}, 500)
            return
        if not has_command("ffmpeg"):
            self._json({"error": "ffmpeg를 PATH에서 찾을 수 없어."}, 500)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
            cmd = build_command(payload)
        except Exception as exc:
            self._json({"error": str(exc)}, 400)
            return

        print("\n[ClipTap] 실행:")
        print(" ".join(f'"{part}"' if " " in part else part for part in cmd))
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
    print(f"  yt-dlp: {'OK' if has_command('yt-dlp') else 'NOT FOUND'}")
    print(f"  ffmpeg: {'OK' if has_command('ffmpeg') else 'NOT FOUND'}")
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
