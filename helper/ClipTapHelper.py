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
APP_VERSION = "1.2"
OUTPUT_DIR = Path.home() / "Downloads" / "ClipTap"
FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
LOCAL_BIN_DIR = APP_DIR / "bin"

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ClipTap Helper</title>
  <link rel="stylesheet" href="/manager.css">
</head>
<body>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand top-brand">
        <div class="brand-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none"><path d="M12 4v10" stroke="currentColor" stroke-width="2.3" stroke-linecap="round"/><path d="m7.5 10 4.5 4.5L16.5 10" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/><path d="M5 18h14" stroke="currentColor" stroke-width="2.3" stroke-linecap="round"/></svg>
        </div>
        <div>
          <h1>ClipTap Helper</h1>
          <p>Local helper for ClipTap downloads</p>
        </div>
      </div>
      <div class="run-pill"><span></span>Running</div>
    </header>

    <aside class="sidebar" aria-label="ClipTap navigation">
      <nav class="nav-list">
        <a href="#dashboard" class="nav-item active"><span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M3 10.8 12 3l9 7.8"/><path d="M5.8 9.3V21h4.4v-6.3h3.6V21h4.4V9.3"/></svg></span><span>Dashboard</span></a>
        <a href="#queue" class="nav-item"><span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3.4 2"/></svg></span><span>Queue</span></a>
        <a href="#history" class="nav-item"><span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M8 6h12"/><path d="M8 12h12"/><path d="M8 18h12"/><circle cx="4.5" cy="6" r="1.2"/><circle cx="4.5" cy="12" r="1.2"/><circle cx="4.5" cy="18" r="1.2"/></svg></span><span>History</span></a>
        <a href="#tools" class="nav-item"><span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M14.7 5.3a4.2 4.2 0 0 0 4.9 5.9l-7.8 7.8a2.6 2.6 0 1 1-3.7-3.7l7.8-7.8a4.2 4.2 0 0 0-1.2-2.2Z"/><circle cx="9.9" cy="17.2" r=".9"/></svg></span><span>Tools</span></a>
        <a href="#defaults" class="nav-item"><span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 8.2a3.8 3.8 0 1 0 0 7.6 3.8 3.8 0 0 0 0-7.6Z"/><path d="M19.2 12a7.5 7.5 0 0 0-.1-1.1l2-1.5-2-3.5-2.4 1a8.3 8.3 0 0 0-1.9-1.1L14.5 3h-5l-.4 2.8c-.7.3-1.3.6-1.9 1.1l-2.4-1-2 3.5 2 1.5a7.5 7.5 0 0 0 0 2.2l-2 1.5 2 3.5 2.4-1c.6.5 1.2.8 1.9 1.1l.4 2.8h5l.4-2.8c.7-.3 1.3-.6 1.9-1.1l2.4 1 2-3.5-2-1.5c.1-.4.1-.7.1-1.1Z"/></svg></span><span>Settings</span></a>
        <a href="#logs" class="nav-item"><span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M7 3.5h7l4 4V20.5H7z"/><path d="M14 3.5V8h4"/><path d="M9.5 12h5"/><path d="M9.5 16h5"/></svg></span><span>Logs</span></a>
      </nav>

      <div class="side-note">
        <span class="note-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 10.5v5"/><path d="M12 7.8h.01"/></svg></span>
        <p>The browser extension sends requests here automatically.</p>
      </div>

      <div class="sidebar-footer">
        <p>Version <span data-role="app-version">—</span></p>
        <button id="checkUpdatesLink" type="button" class="link-button">Check for updates</button>
      </div>
    </aside>

    <main class="main" id="dashboard">
      <section class="layout-grid">
        <article class="card server-card">
          <div class="card-title"><span class="title-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m8 8-4 4 4 4"/><path d="m16 8 4 4-4 4"/><path d="m14 5-4 14"/></svg></span>SERVER STATUS</div>
          <div class="status-rows">
            <div class="status-row"><span>Local address:</span><strong data-role="server-url">http://127.0.0.1:17723</strong><button id="copyAddress" class="icon-button" type="button" title="Copy address"><svg viewBox="0 0 24 24"><path d="M8 8h10v12H8z"/><path d="M6 16H4V4h10v2"/></svg></button></div>
            <div class="status-row"><span>Extension connection:</span><strong class="ok">Connected</strong></div>
            <div class="status-row"><span>Requests today:</span><strong data-role="requests-today">0</strong></div>
          </div>
          <div class="button-row">
            <button id="openOutput" class="button" type="button"><span class="button-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M3.5 6.5h6l2 2h9v9.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M3.5 10h17"/></svg></span>Open Download Folder</button>
            <button id="copyAddressBottom" class="button" type="button"><span class="button-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M8 8h10v12H8z"/><path d="M6 16H4V4h10v2"/></svg></span>Copy Address</button>
            <button id="restartHint" class="button" type="button"><span class="button-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/></svg></span>Restart Helper</button>
            <button id="moreMenu" class="button square" type="button" aria-label="More actions"><span class="button-icon dots" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="6" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="18" cy="12" r="1.4"/></svg></span></button>
          </div>
        </article>

        <article class="card tools-card" id="tools">
          <div class="card-title"><span class="title-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M14.7 5.3a4.2 4.2 0 0 0 4.9 5.9l-7.8 7.8a2.6 2.6 0 1 1-3.7-3.7l7.8-7.8a4.2 4.2 0 0 0-1.2-2.2Z"/><circle cx="9.9" cy="17.2" r=".9"/></svg></span>TOOLS / DEPENDENCY CHECK</div>
          <div class="tool-table">
            <div class="tool-row"><span>yt-dlp</span><strong data-role="yt-state" class="pending">Checking</strong><em data-role="yt-desc">—</em><button id="installYtDlp" class="mini-button" type="button">Check Again</button></div>
            <div class="tool-row"><span>ffmpeg</span><strong data-role="ffmpeg-state" class="pending">Checking</strong><em data-role="ffmpeg-desc">—</em><button id="installFfmpeg" class="mini-button" type="button">Check Again</button></div>
            <div class="tool-row"><span>Python runtime</span><strong class="ok">Ready</strong><em data-role="python-version">Python</em><button id="refreshDeps" class="mini-button" type="button">Check Again</button></div>
            <div class="tool-row"><span>Update check</span><strong class="warn">Manual</strong><em data-role="update-version">Local build</em><button id="openReleases" class="mini-button" type="button">Update</button></div>
          </div>
        </article>

        <article class="card queue-card" id="queue">
          <div class="section-head">
            <h2>ACTIVE DOWNLOAD QUEUE (<span data-role="active-count">0</span>)</h2>
            <div class="head-actions">
              <button id="pauseQueue" class="button compact" type="button"><span class="button-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M8 5v14"/><path d="M16 5v14"/></svg></span>Pause Queue</button>
              <button id="cancelAll" class="button compact" type="button"><span class="button-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="m7 17 10-10"/></svg></span>Cancel All</button>
            </div>
          </div>
          <div class="queue-table-wrap">
            <table class="queue-table">
              <thead><tr><th>#</th><th>Title</th><th>Platform</th><th>Format</th><th>Progress</th><th>Status</th></tr></thead>
              <tbody id="queueRows"></tbody>
            </table>
          </div>
          <div class="table-footer"><span data-role="queue-summary">Showing 0 downloads</span><button id="clearCompleted" class="button compact" type="button">Clear Completed</button></div>
        </article>

        <article class="card defaults-card" id="defaults">
          <div class="card-title"><span class="title-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 8.2a3.8 3.8 0 1 0 0 7.6 3.8 3.8 0 0 0 0-7.6Z"/><path d="M19.2 12a7.5 7.5 0 0 0-.1-1.1l2-1.5-2-3.5-2.4 1a8.3 8.3 0 0 0-1.9-1.1L14.5 3h-5l-.4 2.8c-.7.3-1.3.6-1.9 1.1l-2.4-1-2 3.5 2 1.5a7.5 7.5 0 0 0 0 2.2l-2 1.5 2 3.5 2.4-1c.6.5 1.2.8 1.9 1.1l.4 2.8h5l.4-2.8c.7-.3 1.3-.6 1.9-1.1l2.4 1 2-3.5-2-1.5c.1-.4.1-.7.1-1.1Z"/></svg></span>DOWNLOAD DEFAULTS</div>
          <label class="field"><span>Save folder</span><div class="field-line"><input data-role="output-dir" readonly value="Loading..."><button id="browseOutput" class="mini-button" type="button">Browse</button></div></label>
          <label class="field"><span>Filename rule</span><input id="filenameRule" value="%(uploader)s - %(title)s.%(ext)s"></label>
          <label class="field"><span>Preferred video format</span><select id="videoFormat"><option>mp4 (h264/aac)</option><option>webm (vp9/opus)</option><option>best available</option></select></label>
          <label class="field"><span>Preferred audio format</span><select id="audioFormat"><option>m4a (aac)</option><option>opus</option><option>best audio</option></select></label>
          <label class="field"><span>Cookies from browser</span><select id="cookieBrowser"><option>None</option><option>Chrome</option><option>Edge</option><option>Firefox</option></select></label>
          <label class="check-line"><input id="autoMerge" type="checkbox" checked> <span>Auto-merge with ffmpeg</span></label>
          <button id="saveDefaults" class="button save" type="button">Save Settings</button>
        </article>

        <article class="card logs-card" id="logs">
          <div class="section-head">
            <h2><span class="title-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M7 3.5h7l4 4V20.5H7z"/><path d="M14 3.5V8h4"/><path d="M9.5 12h5"/><path d="M9.5 16h5"/></svg></span>RECENT LOGS</h2>
            <div class="head-actions"><label class="auto-scroll"><input id="autoScroll" type="checkbox" checked> Auto-scroll</label><button id="clearLogs" class="button compact" type="button">Clear</button><button id="openLogs" class="button compact" type="button"><span class="button-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M3.5 6.5h6l2 2h9v9.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M3.5 10h17"/></svg></span>Open Logs Folder</button></div>
          </div>
          <pre id="logOutput" aria-label="Recent logs"></pre>
        </article>
      </section>

      <section class="install-drawer" id="installPanel" hidden>
        <div class="install-head"><strong>Install activity</strong><span id="installState">Idle</span></div>
        <pre id="installLog"></pre>
      </section>
    </main>
  </div>
  <script src="/manager.js"></script>
</body>
</html>"""

MANAGER_CSS = r""":root {
  color-scheme: dark;
  --bg: #070c15;
  --panel: #0d1422;
  --panel-2: #111a2b;
  --panel-3: #151f33;
  --line: #263247;
  --line-soft: #1b2536;
  --text: #f4f7fb;
  --muted: #9aa8ba;
  --muted-2: #6f7e93;
  --blue: #7468ff;
  --blue-2: #4f8dff;
  --blue-soft: rgba(116, 104, 255, .22);
  --orange: #ff9c1a;
  --green: #41db78;
  --red: #ff6470;
  --yellow: #ffb23f;
}
* { box-sizing: border-box; }
html, body { min-height: 100%; }
body {
  margin: 0;
  background:
    radial-gradient(circle at 78% -10%, rgba(65, 130, 255, .13), transparent 36rem),
    radial-gradient(circle at 8% 16%, rgba(116, 104, 255, .14), transparent 26rem),
    var(--bg);
  color: var(--text);
  font-family: "Segoe UI", Arial, sans-serif;
  font-size: 14px;
}
button, input, select { font: inherit; }
button { color: inherit; }
svg { display: block; }
svg path, svg circle { vector-effect: non-scaling-stroke; }
.app-shell {
  display: grid;
  grid-template-columns: 255px 1fr;
  grid-template-rows: 86px 1fr;
  min-height: 100vh;
}
.topbar {
  grid-column: 1 / -1;
  height: 86px;
  padding: 18px 29px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  background: transparent;
  border: 0;
}
.brand { display: flex; align-items: center; gap: 14px; min-height: 50px; }
.brand-icon {
  width: 42px; height: 42px; border-radius: 7px;
  display: grid; place-items: center;
  color: white;
  background: linear-gradient(135deg, #3c64ff, #765cff);
  border: 1px solid rgba(255,255,255,.14);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.18);
}
.brand h1 { margin: 0; font-size: 24px; letter-spacing: -.02em; }
.brand p { margin: 4px 0 0; color: var(--muted); font-size: 14px; }
.sidebar {
  position: sticky; top: 86px; height: calc(100vh - 86px);
  padding: 9px 16px 18px;
  background: transparent;
  border: 0;
  display: flex; flex-direction: column; gap: 14px;
}
.nav-list { display: grid; gap: 5px; margin-top: 0; }
.nav-item {
  height: 44px;
  display: flex;
  align-items: center;
  gap: 12px;
  color: #eef3fb;
  text-decoration: none;
  padding: 0 14px;
  border-radius: 4px;
  border: 1px solid transparent;
  font-size: 16px;
  font-weight: 560;
}
.nav-item:hover { background: rgba(255,255,255,.045); }
.nav-item.active {
  color: #c2caff;
  background: linear-gradient(90deg, rgba(116, 104, 255, .34), rgba(116, 104, 255, .12));
  border-left: 3px solid var(--blue);
  padding-left: 11px;
}
.nav-icon {
  width: 25px;
  height: 25px;
  color: #dce4ff;
  display: grid;
  place-items: center;
  flex: 0 0 25px;
}
.nav-icon svg, .title-icon svg, .button-icon svg, .note-icon svg, .brand-icon svg, .icon-button svg {
  width: 100%;
  height: 100%;
}
.nav-icon svg, .title-icon svg, .button-icon svg, .note-icon svg, .icon-button svg {
  fill: none;
  stroke: currentColor;
  stroke-width: 1.9;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.side-note {
  margin-top: auto; padding: 16px 14px;
  display: grid; grid-template-columns: 22px 1fr; gap: 10px;
  border-radius: 5px; border: 1px solid rgba(116,104,255,.36);
  background: rgba(116,104,255,.1); color: #b9c3ff;
}
.side-note p { margin: 0; line-height: 1.45; }
.note-icon { width: 20px; height: 20px; color: #aeb8ff; }
.sidebar-footer { color: #ccd5e5; }
.sidebar-footer p { margin: 0 0 8px; }
.link-button { background: transparent; border: 0; padding: 0; color: #9da8ff; text-decoration: underline; cursor: pointer; }
.main { padding: 0 24px 28px; min-width: 0; }
.run-pill {
  min-width: 108px; height: 40px; padding: 0 16px; display: inline-flex; align-items: center; justify-content: center; gap: 10px;
  border: 1px solid rgba(65, 219, 120, .32); border-radius: 5px;
  background: rgba(65, 219, 120, .12); color: white; font-size: 16px;
}
.run-pill span { width: 10px; height: 10px; border-radius: 99px; background: var(--green); box-shadow: 0 0 14px rgba(65,219,120,.7); }
.layout-grid { display: grid; grid-template-columns: 1.2fr 1fr; gap: 12px; }
.card {
  background: linear-gradient(180deg, rgba(16, 24, 39, .9), rgba(9, 15, 26, .94));
  border: 1px solid var(--line); border-radius: 5px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.025);
  min-width: 0;
}
.server-card, .tools-card, .defaults-card { padding: 16px; }
.queue-card, .logs-card { padding: 12px; }
.card-title, .section-head h2 {
  margin: 0; display: flex; align-items: center; gap: 10px;
  color: #dce5f6; font-weight: 700; font-size: 14px; letter-spacing: .02em;
}
.title-icon { width: 18px; height: 18px; color: #eaf0ff; opacity: .95; display: inline-grid; place-items: center; flex: 0 0 18px; }
.status-rows { margin-top: 17px; display: grid; }
.status-row {
  display: grid; grid-template-columns: 190px minmax(0, 1fr) 34px; align-items: center;
  min-height: 40px; border-bottom: 1px solid var(--line-soft); gap: 10px;
}
.status-row span { color: #f3f6fb; }
.status-row strong { color: #aeb8ff; font-weight: 500; word-break: break-all; }
.status-row strong.ok, .ok { color: var(--green) !important; }
.warn { color: var(--orange) !important; }
.bad { color: var(--red) !important; }
.pending { color: var(--muted) !important; }
.icon-button { width: 30px; height: 30px; border: 0; border-radius: 4px; background: transparent; color: #c7d1e4; cursor: pointer; display: grid; place-items: center; padding: 6px; }
.icon-button:hover { background: rgba(255,255,255,.07); }
.button-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 18px; }
.button, .mini-button {
  height: 36px; border-radius: 5px; border: 1px solid #2c384c; background: #111a2a;
  color: #f0f4fb; padding: 0 14px; cursor: pointer; font-weight: 650; font-size: 13px;
}
.button { display: inline-flex; align-items: center; justify-content: center; gap: 8px; }
.button:hover, .mini-button:hover { background: #172237; border-color: #3a4860; }
.button.square { width: 38px; padding: 0; }
.button.compact { height: 32px; font-size: 12px; }
.button.save { display: flex; margin: 18px auto 0; min-width: 108px; }
.button-icon { width: 16px; height: 16px; color: #dce5f4; display: inline-grid; place-items: center; flex: 0 0 16px; }
.button-icon.dots { width: 18px; height: 18px; }
.button-icon.dots svg { fill: currentColor; stroke: none; }
.mini-button { height: 30px; padding: 0 12px; justify-self: end; }
.tool-table { margin-top: 13px; border-top: 1px solid var(--line-soft); }
.tool-row {
  min-height: 42px; display: grid; grid-template-columns: 125px 100px minmax(90px, 1fr) 90px; align-items: center; gap: 10px;
  border-bottom: 1px solid var(--line-soft);
}
.tool-row span { font-weight: 650; color: #f0f3f9; }
.tool-row strong { position: relative; padding-left: 22px; font-weight: 500; }
.tool-row strong::before { content: ""; position: absolute; left: 0; top: 50%; width: 12px; height: 12px; margin-top: -6px; border-radius: 50%; background: currentColor; opacity: .95; box-shadow: 0 0 12px currentColor; }
.tool-row em { color: #91a0b4; font-style: normal; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.queue-card { grid-column: span 1; }
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.head-actions { display: flex; align-items: center; gap: 8px; }
.queue-table-wrap { overflow: auto; border-top: 1px solid var(--line-soft); }
.queue-table { width: 100%; border-collapse: collapse; min-width: 640px; }
.queue-table th { height: 34px; color: #cbd5e5; font-size: 12px; text-align: left; font-weight: 700; }
.queue-table td { height: 48px; border-top: 1px solid var(--line-soft); color: #e8edf5; vertical-align: middle; }
.queue-table th:first-child, .queue-table td:first-child { width: 42px; text-align: center; }
.title-cell strong { display: block; max-width: 245px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.title-cell small { display: block; margin-top: 3px; color: #9ba9ba; font-size: 12px; }
.platform { display: inline-flex; align-items: center; gap: 6px; color: #dbe3ef; }
.youtube-dot { width: 13px; height: 9px; display: inline-grid; place-items: center; border-radius: 2px; background: #ff1d1d; font-size: 7px; color: white; }
.progress-cell { min-width: 120px; }
.progress-meta { display: flex; align-items: center; gap: 8px; }
.progress-text { min-width: 48px; text-align: right; color: #d9e1ef; font-size: 12px; }
.progress-bar { flex: 1; min-width: 80px; height: 7px; border-radius: 99px; background: #202a3a; overflow: hidden; }
.progress-fill { height: 100%; width: 0%; border-radius: inherit; background: linear-gradient(90deg, #6f65ff, #8c7dff); }
.progress-fill.live { width: 100%; background: linear-gradient(90deg, var(--orange), #ffd07a, var(--orange)); animation: pulse 1.35s linear infinite; }
.status-badge { color: var(--blue-2); }
.status-badge.done { color: var(--green); }
.status-badge.failed { color: var(--red); }
.status-badge.queued { color: #e7edf8; }
.table-footer { display: flex; align-items: center; justify-content: space-between; padding-top: 12px; color: #c1ccdb; }
.empty-row td { color: var(--muted); text-align: center !important; padding: 24px 0; }
.defaults-card { grid-column: span 1; }
.field { display: grid; gap: 8px; margin-top: 14px; color: #e9eef7; }
.field span { color: #e9eef7; }
.field input, .field select {
  width: 100%; height: 34px; border-radius: 4px; border: 1px solid #29374d;
  background: #0b1220; color: #dfe6f2; padding: 0 12px; outline: none;
}
.field input:focus, .field select:focus { border-color: #5966ff; }
.field-line { display: grid; grid-template-columns: 1fr 82px; gap: 8px; }
.check-line { display: flex; align-items: center; gap: 9px; margin-top: 16px; color: #cfd8e8; }
.check-line input, .auto-scroll input { accent-color: var(--blue); }
.logs-card { grid-column: 1 / -1; }
.logs-card pre, #installLog {
  margin: 0; height: 160px; overflow: auto; padding: 10px 16px;
  background: transparent; border-top: 1px solid var(--line-soft); color: #d1dbec;
  font: 12px/1.55 Consolas, "Cascadia Mono", monospace; white-space: pre-wrap;
}
.auto-scroll { color: #d4dcec; font-size: 12px; display: flex; align-items: center; gap: 6px; }
.install-drawer { position: fixed; right: 24px; bottom: 24px; width: min(560px, calc(100vw - 48px)); background: var(--panel); border: 1px solid var(--line); border-radius: 6px; box-shadow: 0 18px 50px rgba(0,0,0,.36); }
.install-head { display: flex; justify-content: space-between; padding: 12px 14px; border-bottom: 1px solid var(--line-soft); }
#installLog { height: 220px; border-top: 0; }
@keyframes pulse { 0% { opacity: .65; } 50% { opacity: 1; } 100% { opacity: .65; } }
@media (max-width: 1180px) {
  .app-shell { grid-template-columns: 1fr; grid-template-rows: auto auto 1fr; }
  .topbar { grid-column: 1; height: auto; padding: 16px; }
  .sidebar { position: relative; top: 0; height: auto; flex-direction: row; align-items: center; flex-wrap: wrap; padding: 0 16px 12px; }
  .nav-list { display: flex; flex-wrap: wrap; }
  .side-note, .sidebar-footer { display: none; }
  .layout-grid { grid-template-columns: 1fr; }
  .main { padding: 0 16px 20px; }
}
@media (max-width: 760px) {
  .topbar { align-items: flex-start; flex-direction: column; }
  .main { padding: 0 12px 16px; }
  .status-row, .tool-row { grid-template-columns: 1fr; gap: 5px; padding: 9px 0; }
  .section-head, .button-row, .head-actions { align-items: stretch; flex-direction: column; }
  .field-line { grid-template-columns: 1fr; }
}
"""

MANAGER_JS = r"""const $ = (selector) => document.querySelector(selector);
const queueRows = $('#queueRows');
const installPanel = $('#installPanel');
const installLog = $('#installLog');
const installState = $('#installState');
const logOutput = $('#logOutput');
const seenJobStates = new Map();
let logLines = [];
let lastJobs = [];
let queuePaused = false;
let hiddenCompleted = false;

function nowStamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function addLog(level, message) {
  const tag = `[${String(level || 'info').toUpperCase()}]`.padEnd(7, ' ');
  logLines.push(`${nowStamp()} ${tag} ${message}`);
  if (logLines.length > 120) logLines = logLines.slice(-120);
  renderLogs();
}

function renderLogs() {
  if (!logOutput) return;
  logOutput.textContent = logLines.join('\n');
  if ($('#autoScroll')?.checked) logOutput.scrollTop = logOutput.scrollHeight;
}

function text(selector, value) {
  const el = document.querySelector(selector);
  if (el) el.textContent = value;
}

async function api(path, options = {}) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed: ${res.status}`);
  return data;
}

function shortVersion(description) {
  const value = String(description || '—');
  const match = value.match(/(\d+\.\d+(?:\.\d+)?(?:[\w.-]+)?)/);
  return match ? match[1] : value.replace(/^.*?:\s*/, '').slice(0, 22) || '—';
}

function setDependency(stateSelector, descSelector, dep, installButton, installLabel) {
  const state = document.querySelector(stateSelector);
  const desc = document.querySelector(descSelector);
  const button = $(installButton);
  const ok = Boolean(dep?.ok);
  if (state) {
    state.textContent = ok ? 'Installed' : 'Missing';
    state.className = ok ? 'ok' : 'bad';
  }
  if (desc) desc.textContent = ok ? shortVersion(dep.description) : 'Not found';
  if (button) button.textContent = ok ? 'Check Again' : installLabel;
}

function renderInstallTasks(installs = {}) {
  const tasks = Object.values(installs);
  const active = tasks.find(task => task.status === 'running' || task.status === 'queued');
  const recent = active || tasks.find(task => task.log);
  installPanel.hidden = !recent;
  if (!recent) return;
  installState.textContent = `${recent.label}: ${recent.status}`;
  installLog.textContent = recent.log || '';
}

async function refreshStatus() {
  try {
    const data = await api('/api/status');
    setDependency('[data-role="yt-state"]', '[data-role="yt-desc"]', data.ytDlp, '#installYtDlp', 'Install');
    setDependency('[data-role="ffmpeg-state"]', '[data-role="ffmpeg-desc"]', data.ffmpeg, '#installFfmpeg', 'Install');
    text('[data-role="server-url"]', data.server || 'http://127.0.0.1:17723');
    text('[data-role="output-dir"]', data.outputDir || 'Downloads');
    text('[data-role="app-version"]', data.appVersion || '—');
    text('[data-role="python-version"]', navigator.userAgentData?.platform || 'Ready');
    text('[data-role="update-version"]', data.appVersion || 'Local build');
    renderInstallTasks(data.installs);
  } catch (error) {
    text('[data-role="server-url"]', 'Offline');
    addLog('error', error.message);
  }
}

function formatClock(seconds) {
  const total = Math.max(0, Number(seconds) || 0);
  const whole = Math.floor(total);
  const h = Math.floor(whole / 3600);
  const m = Math.floor((whole % 3600) / 60);
  const s = whole % 60;
  return [h, m, s].map(v => String(v).padStart(2, '0')).join(':');
}

function formatDuration(job) {
  if (job.isLive && job.payload.mode === 'full') return 'LIVE';
  if (job.payload.mode === 'section') return `${formatClock(job.payload.start)} → ${formatClock(job.payload.end)}`;
  return 'Full video';
}

function formatName(job) {
  const quality = job.payload?.quality || 'best';
  if (job.payload?.mode === 'section') return quality === 'best' ? 'section' : `section (${quality})`;
  return quality === 'best' ? 'full' : `full (${quality})`;
}

function platform(job) {
  if ((job.extractor || '').toLowerCase().includes('vimeo')) return '<span class="platform">▣ Vimeo</span>';
  return '<span class="platform"><span class="youtube-dot">▶</span>YouTube</span>';
}

function phaseClass(job) {
  if (job.phase === 'finished') return 'done';
  if (job.phase === 'failed' || job.phase === 'cancelled') return 'failed';
  if (job.phase === 'queued') return 'queued';
  return '';
}

function isActive(job) {
  return !['finished', 'failed', 'cancelled'].includes(job.phase);
}

function renderJobs(jobs) {
  lastJobs = jobs;
  const displayJobs = hiddenCompleted ? jobs.filter(isActive) : jobs;
  const activeCount = jobs.filter(isActive).length;
  text('[data-role="requests-today"]', jobs.length);
  text('[data-role="active-count"]', activeCount);
  text('[data-role="queue-summary"]', `Showing ${displayJobs.length} of ${jobs.length} downloads`);

  for (const job of jobs) {
    const stateKey = `${job.phase}:${job.status}:${Math.round(Number(job.progress) || 0)}`;
    if (seenJobStates.get(job.id) !== stateKey) {
      seenJobStates.set(job.id, stateKey);
      const level = job.phase === 'failed' ? 'error' : job.phase === 'finished' ? 'done' : 'info';
      addLog(level, `${job.title || 'Untitled video'} · ${job.status || job.phase}`);
    }
  }

  if (!displayJobs.length) {
    queueRows.innerHTML = '<tr class="empty-row"><td colspan="6">No download requests yet. Start one from the YouTube player.</td></tr>';
    return;
  }

  queueRows.innerHTML = displayJobs.map((job, index) => {
    const progress = Math.max(0, Math.min(100, Number(job.progress) || 0));
    const live = job.isLive && job.payload.mode === 'full' && isActive(job);
    const barWidth = live ? 100 : progress;
    const progressText = live ? 'LIVE' : `${progress.toFixed(progress >= 10 || progress === 0 ? 0 : 1)}%`;
    const detail = [formatDuration(job), job.speed, job.eta && !live ? `ETA ${job.eta}` : '', job.error].filter(Boolean).join(' · ');
    return `
      <tr>
        <td>${index + 1}</td>
        <td class="title-cell"><strong title="${escapeHtml(job.title || 'Untitled video')}">${escapeHtml(job.title || 'Untitled video')}</strong><small>${escapeHtml(detail || 'Queued')}</small></td>
        <td>${platform(job)}</td>
        <td>${escapeHtml(formatName(job))}</td>
        <td class="progress-cell"><div class="progress-meta"><span class="progress-text">${progressText}</span><div class="progress-bar"><div class="progress-fill ${live ? 'live' : ''}" style="width:${barWidth}%"></div></div></div></td>
        <td><span class="status-badge ${phaseClass(job)}">${escapeHtml(job.status || job.phase)}</span></td>
      </tr>`;
  }).join('');
}

function escapeHtml(value) {
  const map = {'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'};
  return String(value || '').replace(/[&<>'"]/g, char => map[char]);
}

async function refreshJobs() {
  const data = await api('/api/jobs');
  renderJobs(data.jobs || []);
}

async function startInstall(name) {
  const status = await api('/api/status');
  const dep = name === 'yt-dlp' ? status.ytDlp : status.ffmpeg;
  if (dep?.ok) {
    await refreshStatus();
    addLog('info', `${name} check completed.`);
    return;
  }
  await api(`/api/install/${name}`, { method: 'POST' });
  addLog('info', `${name} install queued.`);
  await refreshStatus();
}

async function cancelJob(id) {
  await api(`/api/jobs/${id}/cancel`, { method: 'POST' });
  addLog('info', `Cancel requested for ${id}.`);
  await refreshJobs();
}

async function cancelAll() {
  await Promise.all(lastJobs.filter(isActive).map(job => cancelJob(job.id).catch(error => addLog('error', error.message))));
}

function saveDefaults() {
  const values = {
    filenameRule: $('#filenameRule')?.value || '',
    videoFormat: $('#videoFormat')?.value || '',
    audioFormat: $('#audioFormat')?.value || '',
    cookieBrowser: $('#cookieBrowser')?.value || '',
    autoMerge: Boolean($('#autoMerge')?.checked),
  };
  localStorage.setItem('cliptap-manager-defaults', JSON.stringify(values));
  addLog('info', 'Download defaults saved locally.');
}

function loadDefaults() {
  try {
    const values = JSON.parse(localStorage.getItem('cliptap-manager-defaults') || '{}');
    for (const [key, value] of Object.entries(values)) {
      const el = document.getElementById(key);
      if (!el) continue;
      if (el.type === 'checkbox') el.checked = Boolean(value);
      else el.value = value;
    }
  } catch {}
}

function copyAddress() {
  const value = document.querySelector('[data-role="server-url"]')?.textContent || 'http://127.0.0.1:17723';
  navigator.clipboard?.writeText(value).then(() => addLog('info', 'Local address copied.')).catch(() => addLog('error', 'Clipboard copy failed.'));
}

$('#installYtDlp')?.addEventListener('click', () => startInstall('yt-dlp').catch(error => alert(error.message)));
$('#installFfmpeg')?.addEventListener('click', () => startInstall('ffmpeg').catch(error => alert(error.message)));
$('#refreshDeps')?.addEventListener('click', () => refreshStatus().then(() => addLog('info', 'Dependency check refreshed.')));
$('#openOutput')?.addEventListener('click', () => api('/api/open-output', { method: 'POST' }).catch(error => alert(error.message)));
$('#browseOutput')?.addEventListener('click', () => api('/api/open-output', { method: 'POST' }).catch(error => alert(error.message)));
$('#openLogs')?.addEventListener('click', () => api('/api/open-output', { method: 'POST' }).catch(error => alert(error.message)));
$('#copyAddress')?.addEventListener('click', copyAddress);
$('#copyAddressBottom')?.addEventListener('click', copyAddress);
$('#restartHint')?.addEventListener('click', () => alert('Close and run ClipTapHelper.exe again to restart the helper.'));
$('#moreMenu')?.addEventListener('click', () => alert('More actions will be added in a future build.'));
$('#openReleases')?.addEventListener('click', () => addLog('info', 'Update check is manual in this local build.'));
$('#pauseQueue')?.addEventListener('click', (event) => {
  queuePaused = !queuePaused;
  event.currentTarget.textContent = queuePaused ? '▶ Resume Queue' : 'Ⅱ Pause Queue';
  addLog('info', queuePaused ? 'Queue pause requested.' : 'Queue resumed.');
});
$('#cancelAll')?.addEventListener('click', () => cancelAll().catch(error => alert(error.message)));
$('#clearCompleted')?.addEventListener('click', (event) => {
  hiddenCompleted = !hiddenCompleted;
  event.currentTarget.textContent = hiddenCompleted ? 'Show Completed' : 'Clear Completed';
  renderJobs(lastJobs);
});
$('#clearLogs')?.addEventListener('click', () => { logLines = []; renderLogs(); });
$('#saveDefaults')?.addEventListener('click', saveDefaults);
$('#checkUpdatesLink')?.addEventListener('click', () => addLog('info', 'Update check is manual in this local build.'));

loadDefaults();
addLog('info', 'Server started on http://127.0.0.1:17723');
addLog('info', 'Extension requests will appear in the queue automatically.');
refreshStatus();
refreshJobs().catch(console.error);
setInterval(refreshStatus, 2500);
setInterval(() => refreshJobs().catch(console.error), 1000);
"""

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
