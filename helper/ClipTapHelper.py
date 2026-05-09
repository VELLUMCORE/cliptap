"""ClipTap standalone local manager.

This single Python file serves the ClipTap Manager Web UI, receives download
requests from the browser extension, and runs yt-dlp/FFmpeg locally.

When packaged with PyInstaller, it becomes a one-file Windows helper executable.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 17723
APP_NAME = "ClipTap Manager"
APP_VERSION = "1.4.0"
OUTPUT_DIR = Path.home() / "Downloads" / "ClipTap"
FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
LOCAL_BIN_DIR = APP_DIR / "bin"

INDEX_HTML = '<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>ClipTap Manager</title>\n  <link rel="stylesheet" href="/manager.css">\n</head>\n<body>\n  <main class="shell">\n    <section class="hero">\n      <div>\n        <p class="eyebrow">Local manager</p>\n        <h1>ClipTap Manager</h1>\n        <p class="summary">Keep this page open while downloading. ClipTap uses this local manager to run yt-dlp and FFmpeg on your computer.</p>\n      </div>\n      <div class="hero-actions">\n        <button id="openOutput" class="button secondary" type="button">Open output folder</button>\n        <button id="stopServer" class="button danger" type="button">Stop manager</button>\n      </div>\n    </section>\n\n    <section class="status-grid" aria-label="Dependency status">\n      <article class="status-card" id="ytDlpCard">\n        <div class="status-head">\n          <span class="badge">yt-dlp</span>\n          <span class="state" data-role="yt-state">Checking</span>\n        </div>\n        <p data-role="yt-desc">Checking yt-dlp...</p>\n        <button id="installYtDlp" class="button primary" type="button">Install / update yt-dlp</button>\n      </article>\n\n      <article class="status-card" id="ffmpegCard">\n        <div class="status-head">\n          <span class="badge orange">FFmpeg</span>\n          <span class="state" data-role="ffmpeg-state">Checking</span>\n        </div>\n        <p data-role="ffmpeg-desc">Checking FFmpeg...</p>\n        <button id="installFfmpeg" class="button orange" type="button">Install FFmpeg with winget</button>\n      </article>\n\n      <article class="status-card wide">\n        <div class="status-head">\n          <span class="badge muted">Server</span>\n          <span class="state ok">Online</span>\n        </div>\n        <p><strong>Manager</strong> <span data-role="server-url">http://127.0.0.1:17723</span></p>\n        <p><strong>Output</strong> <span data-role="output-dir">Loading...</span></p>\n      </article>\n    </section>\n\n    <section class="panel" id="installPanel" hidden>\n      <div class="panel-head">\n        <h2>Install activity</h2>\n        <span id="installState" class="soft">Idle</span>\n      </div>\n      <pre id="installLog"></pre>\n    </section>\n\n    <section class="panel">\n      <div class="panel-head">\n        <div>\n          <h2>Download requests</h2>\n          <p>New requests from the browser extension appear here automatically.</p>\n        </div>\n        <button id="refreshJobs" class="button secondary small" type="button">Refresh</button>\n      </div>\n      <div id="emptyJobs" class="empty">No download requests yet. Start one from the YouTube player.</div>\n      <div id="jobs" class="jobs"></div>\n    </section>\n  </main>\n\n  <script src="/manager.js"></script>\n</body>\n</html>\n'
MANAGER_CSS = ':root {\n  color-scheme: dark;\n  --bg: #08111f;\n  --bg-2: #0c1728;\n  --surface: #101d31;\n  --surface-2: #14233a;\n  --line: #273b59;\n  --text: #eef5ff;\n  --muted: #9fb2ca;\n  --blue: #2f8cff;\n  --blue-2: #1c6ed6;\n  --orange: #ff9d1f;\n  --orange-2: #d97600;\n  --red: #ff6767;\n  --green: #51d491;\n}\n\n* { box-sizing: border-box; }\n\nbody {\n  margin: 0;\n  min-height: 100vh;\n  background: radial-gradient(circle at 20% 0%, rgba(47, 140, 255, .18), transparent 32rem), var(--bg);\n  color: var(--text);\n  font-family: "Segoe UI", Arial, sans-serif;\n}\n\nbutton, input { font: inherit; }\n\n.shell {\n  width: min(1120px, calc(100% - 32px));\n  margin: 0 auto;\n  padding: 28px 0 44px;\n}\n\n.hero {\n  display: flex;\n  align-items: flex-end;\n  justify-content: space-between;\n  gap: 24px;\n  padding: 26px;\n  background: linear-gradient(135deg, rgba(20, 35, 58, .96), rgba(12, 23, 40, .96));\n  border: 1px solid var(--line);\n  border-radius: 12px;\n}\n\n.eyebrow {\n  margin: 0 0 8px;\n  color: var(--blue);\n  font-weight: 700;\n  letter-spacing: .08em;\n  text-transform: uppercase;\n  font-size: 12px;\n}\n\nh1, h2, p { margin-top: 0; }\nh1 { margin-bottom: 10px; font-size: 34px; }\nh2 { margin-bottom: 4px; font-size: 20px; }\n.summary { margin-bottom: 0; max-width: 680px; color: var(--muted); line-height: 1.55; }\n\n.hero-actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }\n\n.status-grid {\n  display: grid;\n  grid-template-columns: repeat(3, minmax(0, 1fr));\n  gap: 14px;\n  margin-top: 14px;\n}\n\n.status-card, .panel {\n  background: rgba(16, 29, 49, .94);\n  border: 1px solid var(--line);\n  border-radius: 10px;\n}\n\n.status-card {\n  padding: 18px;\n  min-height: 168px;\n}\n\n.status-card.wide { grid-column: span 1; }\n.status-card p { color: var(--muted); line-height: 1.45; word-break: break-word; }\n.status-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }\n\n.badge {\n  display: inline-flex;\n  align-items: center;\n  height: 26px;\n  padding: 0 10px;\n  border-radius: 999px;\n  background: rgba(47, 140, 255, .18);\n  color: #b9d8ff;\n  font-weight: 700;\n  font-size: 13px;\n}\n.badge.orange { background: rgba(255, 157, 31, .18); color: #ffd49a; }\n.badge.muted { background: rgba(159, 178, 202, .15); color: #c6d4e4; }\n\n.state { color: var(--muted); font-size: 13px; font-weight: 700; }\n.state.ok { color: var(--green); }\n.state.bad { color: var(--red); }\n\n.button {\n  border: 1px solid transparent;\n  border-radius: 8px;\n  min-height: 38px;\n  padding: 0 14px;\n  color: white;\n  cursor: pointer;\n  background: var(--surface-2);\n}\n.button:hover { filter: brightness(1.08); }\n.button:disabled { opacity: .55; cursor: not-allowed; }\n.button.primary { background: var(--blue); }\n.button.orange { background: var(--orange-2); }\n.button.secondary { border-color: var(--line); background: #15243b; color: var(--text); }\n.button.danger { background: transparent; border-color: rgba(255, 103, 103, .55); color: #ffc9c9; }\n.button.small { min-height: 34px; font-size: 14px; }\n\n.panel { margin-top: 14px; padding: 20px; }\n.panel-head { display: flex; justify-content: space-between; align-items: center; gap: 20px; margin-bottom: 16px; }\n.panel-head p { margin: 4px 0 0; color: var(--muted); }\n.soft { color: var(--muted); }\npre {\n  margin: 0;\n  max-height: 260px;\n  overflow: auto;\n  padding: 14px;\n  border-radius: 8px;\n  background: #07101c;\n  border: 1px solid #1b304d;\n  color: #cfe1f7;\n  white-space: pre-wrap;\n}\n\n.empty {\n  border: 1px dashed var(--line);\n  color: var(--muted);\n  border-radius: 10px;\n  padding: 28px;\n  text-align: center;\n}\n.jobs { display: grid; gap: 12px; }\n.job {\n  display: grid;\n  grid-template-columns: 160px minmax(0, 1fr) auto;\n  gap: 16px;\n  padding: 14px;\n  border: 1px solid var(--line);\n  border-radius: 10px;\n  background: var(--bg-2);\n}\n.thumb {\n  width: 160px;\n  aspect-ratio: 16 / 9;\n  border-radius: 8px;\n  object-fit: cover;\n  background: #1a2c47;\n  border: 1px solid #2a4162;\n}\n.job-title { margin: 0 0 8px; font-size: 16px; line-height: 1.35; }\n.job-meta { margin: 0 0 10px; color: var(--muted); font-size: 13px; line-height: 1.45; }\n.progress-track { height: 9px; overflow: hidden; border-radius: 999px; background: #0a1424; border: 1px solid #243a59; }\n.progress-fill { height: 100%; width: 0%; background: linear-gradient(90deg, var(--blue), #68b0ff); transition: width .2s ease; }\n.job.live .progress-fill { width: 100%; background: linear-gradient(90deg, var(--orange), #ffd17a, var(--orange)); animation: pulse 1.4s linear infinite; }\n.job.failed .progress-fill { background: var(--red); }\n.job.finished .progress-fill { background: var(--green); }\n\n@keyframes pulse {\n  0% { opacity: .55; }\n  50% { opacity: 1; }\n  100% { opacity: .55; }\n}\n\n@media (max-width: 840px) {\n  .hero { align-items: flex-start; flex-direction: column; }\n  .status-grid { grid-template-columns: 1fr; }\n  .job { grid-template-columns: 1fr; }\n  .thumb { width: 100%; }\n}\n'
MANAGER_JS = 'const $ = (selector) => document.querySelector(selector);\nconst jobsEl = $(\'#jobs\');\nconst emptyJobs = $(\'#emptyJobs\');\nconst installPanel = $(\'#installPanel\');\nconst installLog = $(\'#installLog\');\nconst installState = $(\'#installState\');\n\nfunction text(selector, value) {\n  const el = document.querySelector(selector);\n  if (el) el.textContent = value;\n}\n\nasync function api(path, options = {}) {\n  const res = await fetch(path, options);\n  const data = await res.json().catch(() => ({}));\n  if (!res.ok) throw new Error(data.error || `Request failed: ${res.status}`);\n  return data;\n}\n\nfunction setDependency(cardId, stateSelector, descSelector, dep) {\n  const card = document.getElementById(cardId);\n  const state = document.querySelector(stateSelector);\n  const desc = document.querySelector(descSelector);\n  card?.classList.toggle(\'missing\', !dep.ok);\n  if (state) {\n    state.textContent = dep.ok ? \'Ready\' : \'Missing\';\n    state.className = dep.ok ? \'state ok\' : \'state bad\';\n  }\n  if (desc) desc.textContent = dep.description || \'Unknown\';\n}\n\nfunction renderInstallTasks(installs = {}) {\n  const tasks = Object.values(installs);\n  const active = tasks.find(task => task.status === \'running\' || task.status === \'queued\');\n  const recent = active || tasks.find(task => task.log);\n  installPanel.hidden = !recent;\n  if (!recent) return;\n  installState.textContent = `${recent.label}: ${recent.status}`;\n  installLog.textContent = recent.log || \'\';\n}\n\nasync function refreshStatus() {\n  try {\n    const data = await api(\'/api/status\');\n    setDependency(\'ytDlpCard\', \'[data-role="yt-state"]\', \'[data-role="yt-desc"]\', data.ytDlp);\n    setDependency(\'ffmpegCard\', \'[data-role="ffmpeg-state"]\', \'[data-role="ffmpeg-desc"]\', data.ffmpeg);\n    text(\'[data-role="server-url"]\', data.server);\n    text(\'[data-role="output-dir"]\', data.outputDir);\n    renderInstallTasks(data.installs);\n  } catch (error) {\n    text(\'[data-role="server-url"]\', \'Offline\');\n    console.error(error);\n  }\n}\n\nfunction formatClock(seconds) {\n  const total = Math.max(0, Number(seconds) || 0);\n  const whole = Math.floor(total);\n  const h = Math.floor(whole / 3600);\n  const m = Math.floor((whole % 3600) / 60);\n  const s = whole % 60;\n  return [h, m, s].map(v => String(v).padStart(2, \'0\')).join(\':\');\n}\n\nfunction jobMode(job) {\n  if (job.payload.mode === \'full\') {\n    return job.isLive ? \'Live recording · continues until the stream ends or you cancel\' : \'Full video\';\n  }\n  return `Selected section · ${formatClock(job.payload.start)} → ${formatClock(job.payload.end)}`;\n}\n\nfunction jobClasses(job) {\n  const classes = [\'job\'];\n  if (job.isLive && job.payload.mode === \'full\' && ![\'finished\', \'failed\', \'cancelled\'].includes(job.phase)) classes.push(\'live\');\n  if (job.phase === \'finished\') classes.push(\'finished\');\n  if (job.phase === \'failed\') classes.push(\'failed\');\n  return classes.join(\' \');\n}\n\nfunction renderJobs(jobs) {\n  emptyJobs.hidden = jobs.length > 0;\n  jobsEl.innerHTML = jobs.map(job => {\n    const progress = Math.max(0, Math.min(100, Number(job.progress) || 0));\n    const thumbnail = job.thumbnailUrl || \'\';\n    const statusBits = [job.status];\n    if (job.speed) statusBits.push(job.speed);\n    if (job.eta && !job.isLive) statusBits.push(`ETA ${job.eta}`);\n    if (job.error) statusBits.push(job.error);\n    const disabled = [\'finished\', \'failed\', \'cancelled\'].includes(job.phase) ? \'disabled\' : \'\';\n    return `\n      <article class="${jobClasses(job)}">\n        ${thumbnail ? `<img class="thumb" src="${thumbnail}" alt="">` : `<div class="thumb"></div>`}\n        <div>\n          <h3 class="job-title">${escapeHtml(job.title || \'Untitled video\')}</h3>\n          <p class="job-meta">${escapeHtml(jobMode(job))}<br>${escapeHtml(statusBits.join(\' · \'))}</p>\n          <div class="progress-track" aria-label="Download progress">\n            <div class="progress-fill" style="width:${job.isLive && job.payload.mode === \'full\' ? 100 : progress}%"></div>\n          </div>\n        </div>\n        <div>\n          <button class="button danger small" data-cancel="${job.id}" ${disabled}>Cancel</button>\n        </div>\n      </article>\n    `;\n  }).join(\'\');\n}\n\nfunction escapeHtml(value) {\n  return String(value || \'\').replace(/[&<>\'"]/g, char => ({\n    \'&\': \'&amp;\', \'<\': \'&lt;\', \'>\': \'&gt;\', "\'": \'&#39;\', \'"\': \'&quot;\'\n  }[char]));\n}\n\nasync function refreshJobs() {\n  const data = await api(\'/api/jobs\');\n  renderJobs(data.jobs || []);\n}\n\nasync function startInstall(name) {\n  await api(`/api/install/${name}`, { method: \'POST\' });\n  await refreshStatus();\n}\n\n$(\'#installYtDlp\')?.addEventListener(\'click\', () => startInstall(\'yt-dlp\').catch(alert));\n$(\'#installFfmpeg\')?.addEventListener(\'click\', () => startInstall(\'ffmpeg\').catch(alert));\n$(\'#refreshJobs\')?.addEventListener(\'click\', () => refreshJobs().catch(console.error));\n$(\'#openOutput\')?.addEventListener(\'click\', () => api(\'/api/open-output\', { method: \'POST\' }).catch(error => alert(error.message)));\n$(\'#stopServer\')?.addEventListener(\'click\', async () => {\n  if (!confirm(\'Stop ClipTap Manager? Downloads in progress may fail.\')) return;\n  await api(\'/api/shutdown\', { method: \'POST\' });\n  document.body.innerHTML = \'<main class="shell"><section class="hero"><h1>ClipTap Manager stopped</h1><p class="summary">You can close this tab now.</p></section></main>\';\n});\n\njobsEl?.addEventListener(\'click\', async (event) => {\n  const button = event.target.closest(\'[data-cancel]\');\n  if (!button) return;\n  await api(`/api/jobs/${button.dataset.cancel}/cancel`, { method: \'POST\' });\n  await refreshJobs();\n});\n\nasync function tick() {\n  await Promise.allSettled([refreshStatus(), refreshJobs()]);\n}\n\ntick();\nsetInterval(tick, 1500);\n'

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


class ClipTapError(RuntimeError):
    pass


class CancelledError(RuntimeError):
    pass


@dataclass
class InstallTask:
    name: str
    label: str
    status: str = "idle"
    log: str = ""
    started_at: float | None = None
    finished_at: float | None = None
    process: subprocess.Popen | None = field(default=None, repr=False, compare=False)

    def public(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "status": self.status,
            "log": self.log[-8000:],
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
        }


@dataclass
class DownloadJob:
    id: str
    payload: dict
    title: str = "Preparing download..."
    thumbnail_url: str = ""
    webpage_url: str = ""
    extractor: str = ""
    is_live: bool = False
    status: str = "Queued"
    phase: str = "queued"
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    downloaded: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    process: subprocess.Popen | None = field(default=None, repr=False, compare=False)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False, compare=False)

    def public(self) -> dict:
        return {
            "id": self.id,
            "payload": self.payload,
            "title": self.title,
            "thumbnailUrl": self.thumbnail_url,
            "webpageUrl": self.webpage_url,
            "extractor": self.extractor,
            "isLive": self.is_live,
            "status": self.status,
            "phase": self.phase,
            "progress": self.progress,
            "speed": self.speed,
            "eta": self.eta,
            "downloaded": self.downloaded,
            "error": self.error,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }

    def touch(self):
        self.updated_at = time.time()

    def cancel(self):
        self.cancel_event.set()
        self.status = "Cancelling..."
        self.phase = "cancelling"
        self.touch()
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass


JOBS: dict[str, DownloadJob] = {}
INSTALLS: dict[str, InstallTask] = {
    "yt-dlp": InstallTask("yt-dlp", "yt-dlp"),
    "ffmpeg": InstallTask("ffmpeg", "FFmpeg"),
}
LOCK = threading.RLock()
SERVER: ThreadingHTTPServer | None = None


def first_existing(paths):
    for path in paths:
        if path and Path(path).exists():
            return Path(path)
    return None


def run_probe(command: list[str], timeout: int = 8) -> bool:
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def external_python_candidates() -> list[list[str]]:
    candidates: list[list[str]] = []
    py = shutil.which("py") or shutil.which("py.exe")
    if py:
        candidates.append([py])
    python = shutil.which("python") or shutil.which("python.exe")
    if python:
        candidates.append([python])
    if not FROZEN:
        candidates.append([sys.executable])
    return candidates


def find_python_launcher() -> list[str] | None:
    seen = set()
    for command in external_python_candidates():
        key = tuple(command)
        if key in seen:
            continue
        seen.add(key)
        if run_probe(command + ["--version"]):
            return command
    return None


def self_ytdlp_command() -> list[str]:
    if FROZEN:
        return [str(sys.executable), "--run-yt-dlp"]
    return [str(sys.executable), str(Path(__file__).resolve()), "--run-yt-dlp"]


def has_embedded_yt_dlp() -> bool:
    return importlib.util.find_spec("yt_dlp") is not None


def find_yt_dlp() -> tuple[list[str] | None, str]:
    local = first_existing([
        LOCAL_BIN_DIR / "yt-dlp.exe",
        LOCAL_BIN_DIR / "yt-dlp",
        APP_DIR / "yt-dlp.exe",
        APP_DIR / "yt-dlp",
    ])
    if local:
        return [str(local)], f"Local executable: {local}"

    executable = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    if executable:
        return [executable], f"PATH: {executable}"

    if has_embedded_yt_dlp():
        source = "bundled module" if FROZEN else "Python module"
        return self_ytdlp_command(), f"{source}: yt-dlp"

    launcher = find_python_launcher()
    if launcher and run_probe(launcher + ["-m", "yt_dlp", "--version"]):
        return launcher + ["-m", "yt_dlp"], "Python module: " + " ".join(launcher + ["-m", "yt_dlp"])

    return None, "Not installed"


def find_ffmpeg() -> tuple[Path | None, str]:
    executable = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if executable:
        return Path(executable), f"PATH: {executable}"

    local = first_existing([
        LOCAL_BIN_DIR / "ffmpeg.exe",
        LOCAL_BIN_DIR / "ffmpeg",
        APP_DIR / "ffmpeg.exe",
        APP_DIR / "ffmpeg",
    ])
    if local:
        return local, f"Local executable: {local}"

    return None, "Not installed"


def dependency_status() -> dict:
    yt_cmd, yt_desc = find_yt_dlp()
    ffmpeg_path, ffmpeg_desc = find_ffmpeg()
    return {
        "ok": True,
        "appName": APP_NAME,
        "appVersion": APP_VERSION,
        "server": f"http://{HOST}:{PORT}",
        "outputDir": str(OUTPUT_DIR),
        "ytDlp": {
            "ok": bool(yt_cmd),
            "command": yt_cmd,
            "description": yt_desc,
        },
        "ffmpeg": {
            "ok": bool(ffmpeg_path),
            "path": str(ffmpeg_path) if ffmpeg_path else None,
            "description": ffmpeg_desc,
        },
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


def build_metadata_command(payload: dict) -> list[str]:
    cmd_base, _ = find_yt_dlp()
    if not cmd_base:
        raise ClipTapError("yt-dlp is not installed.")

    command = list(cmd_base) + ["-J", "--no-warnings", "--skip-download"]
    if payload.get("cookieBrowser"):
        command += ["--cookies-from-browser", payload["cookieBrowser"]]
    command.append(payload["url"])
    return command


def build_download_command(job: DownloadJob) -> list[str]:
    yt_dlp_cmd, _ = find_yt_dlp()
    ffmpeg_path, _ = find_ffmpeg()
    if not yt_dlp_cmd:
        raise ClipTapError("yt-dlp is not installed.")
    if not ffmpeg_path:
        raise ClipTapError("FFmpeg is not installed.")

    payload = job.payload
    mode = payload["mode"]
    quality = payload["quality"]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    command = list(yt_dlp_cmd) + ["--newline", "--no-playlist"]

    if quality == "audio":
        command += ["-f", FORMAT_MAP[quality], "-x", "--audio-format", "mp3"]
    else:
        command += ["-f", FORMAT_MAP[quality], "--merge-output-format", "mp4"]

    command += ["--ffmpeg-location", str(ffmpeg_path)]

    if mode == "section":
        section = f"*{seconds_to_clock(payload['start'])}-{seconds_to_clock(payload['end'])}"
        command += ["--download-sections", section]
        output_template = str(OUTPUT_DIR / "%(title).160s [%(id)s] %(section_start)s-%(section_end)s.%(ext)s")
        if payload.get("forceKeyframes"):
            command.append("--force-keyframes-at-cuts")
    else:
        output_template = str(OUTPUT_DIR / "%(title).160s [%(id)s].%(ext)s")
        if job.is_live:
            command += ["--hls-use-mpegts"]

    if payload.get("cookieBrowser"):
        command += ["--cookies-from-browser", payload["cookieBrowser"]]

    command += ["-o", output_template, payload["url"]]
    return command


def update_job(job: DownloadJob, **changes):
    with LOCK:
        for key, value in changes.items():
            setattr(job, key, value)
        job.touch()


def prepare_metadata(job: DownloadJob):
    update_job(job, status="Reading video information...", phase="metadata")
    result = subprocess.run(
        build_metadata_command(job.payload),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    if job.cancel_event.is_set():
        raise CancelledError()
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "yt-dlp failed to read video information.").strip()
        raise ClipTapError(message[-1000:])

    info = json.loads(result.stdout)
    title = info.get("title") or job.payload.get("title") or "Untitled video"
    thumbnails = info.get("thumbnails") or []
    thumbnail_url = info.get("thumbnail") or ""
    if thumbnails:
        thumbnail_url = thumbnails[-1].get("url") or thumbnail_url

    update_job(
        job,
        title=title,
        thumbnail_url=thumbnail_url,
        webpage_url=info.get("webpage_url") or job.payload["url"],
        extractor=info.get("extractor_key") or info.get("extractor") or "",
        is_live=bool(info.get("is_live")) or str(info.get("live_status", "")).lower() in {"is_live", "is_upcoming"},
    )


def run_download(job: DownloadJob):
    try:
        prepare_metadata(job)
        status = "Recording live stream..." if job.is_live and job.payload["mode"] == "full" else "Downloading..."
        update_job(job, status=status, phase="live" if job.is_live and job.payload["mode"] == "full" else "downloading")

        command = build_download_command(job)
        job.process = popen_text(command, OUTPUT_DIR)

        percent_re = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")
        speed_re = re.compile(r"\bat\s+([^\s]+/s)")
        eta_re = re.compile(r"\bETA\s+([^\s]+)")
        size_re = re.compile(r"of\s+~?([^\s]+)")

        while True:
            if job.cancel_event.is_set():
                raise CancelledError()

            line = job.process.stdout.readline() if job.process.stdout else ""
            if not line and job.process.poll() is not None:
                break
            if not line:
                time.sleep(0.05)
                continue

            line = line.strip()
            changes = {}

            match = percent_re.search(line)
            if match and not (job.is_live and job.payload["mode"] == "full"):
                changes["progress"] = max(0.0, min(100.0, float(match.group(1))))

            speed_match = speed_re.search(line)
            eta_match = eta_re.search(line)
            size_match = size_re.search(line)
            if speed_match:
                changes["speed"] = speed_match.group(1)
            if eta_match:
                changes["eta"] = eta_match.group(1)
            if size_match:
                changes["downloaded"] = size_match.group(1)

            if "[download] Destination:" in line:
                changes["status"] = "Downloading media..."
            elif "Merger" in line or "Merging formats" in line:
                changes["status"] = "Merging video and audio..."
                changes["phase"] = "processing"
            elif "Deleting original file" in line:
                changes["status"] = "Cleaning temporary files..."
                changes["phase"] = "processing"

            if changes:
                update_job(job, **changes)

        code = job.process.wait()
        if job.cancel_event.is_set():
            raise CancelledError()
        if code != 0:
            raise ClipTapError(f"yt-dlp exited with code {code}.")
        update_job(job, status="Finished", phase="finished", progress=100.0)
    except CancelledError:
        update_job(job, status="Cancelled", phase="cancelled")
    except Exception as exc:
        update_job(job, status="Failed", phase="failed", error=str(exc))
    finally:
        if job.process and job.process.poll() is None:
            try:
                job.process.kill()
            except Exception:
                pass


def create_job(payload: dict) -> str:
    job = DownloadJob(id=uuid.uuid4().hex[:12], payload=payload)
    with LOCK:
        JOBS[job.id] = job
    threading.Thread(target=run_download, args=(job,), daemon=True).start()
    return job.id


def install_command(name: str) -> list[str]:
    if name == "yt-dlp":
        launcher = find_python_launcher()
        if not launcher:
            raise ClipTapError("No external Python installation was found. The bundled yt-dlp works with this helper, but updating it requires a newer ClipTap Helper build or a Python installation.")
        return launcher + ["-m", "pip", "install", "-U", "yt-dlp"]
    if name == "ffmpeg":
        winget = shutil.which("winget") or shutil.which("winget.exe")
        if not winget:
            raise ClipTapError("winget is not available. Install FFmpeg manually or place ffmpeg.exe next to ClipTapHelper.exe or in a bin folder beside it.")
        return [winget, "install", "-e", "--id", "Gyan.FFmpeg", "--accept-package-agreements", "--accept-source-agreements"]
    raise ValueError("Unknown install target.")


def run_install(name: str):
    task = INSTALLS[name]
    try:
        with LOCK:
            task.status = "running"
            task.log = ""
            task.started_at = time.time()
            task.finished_at = None
        command = install_command(name)
        process = popen_text(command, APP_DIR)
        with LOCK:
            task.process = process
            task.log += "> " + " ".join(command) + "\n\n"
        while True:
            line = process.stdout.readline() if process.stdout else ""
            if not line and process.poll() is not None:
                break
            if line:
                with LOCK:
                    task.log += line
            else:
                time.sleep(0.05)
        code = process.wait()
        with LOCK:
            task.status = "finished" if code == 0 else "failed"
            task.log += f"\nExited with code {code}.\n"
            task.finished_at = time.time()
            task.process = None
    except Exception as exc:
        with LOCK:
            task.status = "failed"
            task.log += f"\n{exc}\n"
            task.finished_at = time.time()
            task.process = None


def start_install(name: str):
    if name not in INSTALLS:
        raise ValueError("Unknown install target.")
    with LOCK:
        task = INSTALLS[name]
        if task.status == "running":
            return
        task.status = "queued"
        task.log = "Queued...\n"
    threading.Thread(target=run_install, args=(name,), daemon=True).start()


def json_response(handler: BaseHTTPRequestHandler, data, status=200):
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()
    handler.wfile.write(raw)


def html_response(handler: BaseHTTPRequestHandler, body: str, content_type: str):
    raw = body.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def read_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


class ClipTapHandler(BaseHTTPRequestHandler):
    server_version = f"ClipTapManager/{APP_VERSION}"

    def log_message(self, fmt, *args):
        if not FROZEN:
            print("[ClipTap] " + fmt % args)

    def cors_empty(self, status=204):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self.cors_empty(204)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in {"/health", "/api/status"}:
            data = dependency_status()
            with LOCK:
                data["installs"] = {name: task.public() for name, task in INSTALLS.items()}
            json_response(self, data)
            return

        if path == "/api/jobs":
            with LOCK:
                jobs = [job.public() for job in sorted(JOBS.values(), key=lambda item: item.created_at, reverse=True)]
            json_response(self, {"ok": True, "jobs": jobs})
            return

        if path in {"/", "/manager"}:
            html_response(self, INDEX_HTML, "text/html; charset=utf-8")
            return

        if path == "/manager.css":
            html_response(self, MANAGER_CSS, "text/css; charset=utf-8")
            return

        if path == "/manager.js":
            html_response(self, MANAGER_JS, "application/javascript; charset=utf-8")
            return

        json_response(self, {"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == "/download":
                payload = clean_payload(read_body(self))
                job_id = create_job(payload)
                json_response(self, {"ok": True, "jobId": job_id, "outputDir": str(OUTPUT_DIR)})
                return

            if path == "/api/install/yt-dlp":
                start_install("yt-dlp")
                json_response(self, {"ok": True})
                return

            if path == "/api/install/ffmpeg":
                start_install("ffmpeg")
                json_response(self, {"ok": True})
                return

            if path.startswith("/api/jobs/") and path.endswith("/cancel"):
                job_id = path.split("/")[3]
                with LOCK:
                    job = JOBS.get(job_id)
                if not job:
                    json_response(self, {"error": "job not found"}, 404)
                    return
                job.cancel()
                json_response(self, {"ok": True})
                return

            if path == "/api/open-output":
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                try:
                    if hasattr(os, "startfile"):
                        os.startfile(str(OUTPUT_DIR))
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", str(OUTPUT_DIR)])
                    else:
                        subprocess.Popen(["xdg-open", str(OUTPUT_DIR)])
                    json_response(self, {"ok": True})
                except Exception as exc:
                    json_response(self, {"error": str(exc)}, 500)
                return

            if path == "/api/shutdown":
                json_response(self, {"ok": True})
                threading.Thread(target=shutdown_server, daemon=True).start()
                return

            json_response(self, {"error": "not found"}, 404)
        except Exception as exc:
            json_response(self, {"error": str(exc)}, 500)


def shutdown_server():
    time.sleep(0.2)
    if SERVER:
        SERVER.shutdown()


def open_browser_later():
    time.sleep(0.6)
    webbrowser.open(f"http://{HOST}:{PORT}/")


def run_yt_dlp_cli(argv: list[str]) -> int:
    try:
        from yt_dlp.__main__ import main as yt_dlp_main
    except Exception as exc:
        print(f"yt-dlp is not bundled or installed: {exc}", file=sys.stderr)
        return 1
    sys.argv = [sys.argv[0]] + argv
    result = yt_dlp_main()
    return int(result or 0)


def main():
    global SERVER

    if "--run-yt-dlp" in sys.argv:
        idx = sys.argv.index("--run-yt-dlp")
        raise SystemExit(run_yt_dlp_cli(sys.argv[idx + 1:]))

    parser = argparse.ArgumentParser(description="Run the ClipTap local manager.")
    parser.add_argument("--open", action="store_true", help="Open the manager UI in the default browser.")
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser window automatically.")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    should_open = args.open or (FROZEN and not args.no_open)

    try:
        SERVER = ThreadingHTTPServer((HOST, PORT), ClipTapHandler)
    except OSError:
        webbrowser.open(f"http://{HOST}:{PORT}/")
        return

    if not FROZEN:
        print(f"{APP_NAME} {APP_VERSION}")
        print(f"Manager: http://{HOST}:{PORT}/")
        print(f"Output: {OUTPUT_DIR}")
        print("Keep this process running while using ClipTap. Use the Web UI to stop it.\n")

    if should_open:
        threading.Thread(target=open_browser_later, daemon=True).start()
    try:
        SERVER.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if not FROZEN:
            print("ClipTap Manager stopped.")


if __name__ == "__main__":
    if sys.version_info < (3, 9):
        print("Python 3.9 or later is recommended.")
    main()
