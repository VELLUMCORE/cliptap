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
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tempfile
import uuid
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HOST = "127.0.0.1"
PORT = 17723
APP_NAME = "ClipTap Manager"
APP_VERSION = "1.3"
OUTPUT_DIR = Path.home() / "Downloads" / "ClipTap"
TEMP_ROOT = Path(tempfile.gettempdir()) / "ClipTap"
FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
LOCAL_BIN_DIR = APP_DIR / "bin"
DATA_DIR = (Path(os.environ.get("APPDATA", str(Path.home()))) / "ClipTap") if os.name == "nt" else (Path.home() / ".cliptap" / "ClipTap")
HISTORY_FILE = DATA_DIR / "download-history.json"
TERMINAL_PHASES = {"finished", "failed", "cancelled", "stopped"}

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ClipTap Helper</title>
  <link rel="stylesheet" href="/manager.css">
</head>
<body data-page="dashboard">
  <div class="app-shell">
    <aside class="sidebar" aria-label="ClipTap navigation">
      <div class="brand side-brand">
        <div class="brand-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none"><path d="M12 4v10" stroke="currentColor" stroke-width="2.3" stroke-linecap="round"/><path d="m7.5 10 4.5 4.5L16.5 10" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/><path d="M5 18h14" stroke="currentColor" stroke-width="2.3" stroke-linecap="round"/></svg>
        </div>
        <div class="brand-copy">
          <h1>ClipTap Helper</h1>
          <p>Local helper for ClipTap downloads</p>
        </div>
      </div>
      <nav class="nav-list">
        <a href="#" class="nav-item active" data-page="dashboard" aria-current="page"><span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M3 10.8 12 3l9 7.8"/><path d="M5.8 9.3V21h4.4v-6.3h3.6V21h4.4V9.3"/></svg></span><span>Dashboard</span></a>
        <a href="#" class="nav-item" data-page="queue"><span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3.4 2"/></svg></span><span>Queue</span></a>
        <a href="#" class="nav-item" data-page="history"><span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M8 6h12"/><path d="M8 12h12"/><path d="M8 18h12"/><circle cx="4.5" cy="6" r="1.2"/><circle cx="4.5" cy="12" r="1.2"/><circle cx="4.5" cy="18" r="1.2"/></svg></span><span>History</span></a>
        <a href="#" class="nav-item" data-page="tools"><span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M14.7 5.3a4.2 4.2 0 0 0 4.9 5.9l-7.8 7.8a2.6 2.6 0 1 1-3.7-3.7l7.8-7.8a4.2 4.2 0 0 0-1.2-2.2Z"/><circle cx="9.9" cy="17.2" r=".9"/></svg></span><span>Tools</span></a>
        <a href="#" class="nav-item" data-page="settings"><span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 8.2a3.8 3.8 0 1 0 0 7.6 3.8 3.8 0 0 0 0-7.6Z"/><path d="M19.2 12a7.5 7.5 0 0 0-.1-1.1l2-1.5-2-3.5-2.4 1a8.3 8.3 0 0 0-1.9-1.1L14.5 3h-5l-.4 2.8c-.7.3-1.3.6-1.9 1.1l-2.4-1-2 3.5 2 1.5a7.5 7.5 0 0 0 0 2.2l-2 1.5 2 3.5 2.4-1c.6.5 1.2.8 1.9 1.1l.4 2.8h5l.4-2.8c.7-.3 1.3-.6 1.9-1.1l2.4 1 2-3.5-2-1.5c.1-.4.1-.7.1-1.1Z"/></svg></span><span>Settings</span></a>
        <a href="#" class="nav-item" data-page="logs"><span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M7 3.5h7l4 4V20.5H7z"/><path d="M14 3.5V8h4"/><path d="M9.5 12h5"/><path d="M9.5 16h5"/></svg></span><span>Logs</span></a>
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
      <header class="main-header"><div></div><div class="run-pill"><span></span>Running</div></header>
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
              <button id="cancelAll" class="button compact" type="button"><span class="button-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="m7 17 10-10"/></svg></span>Cancel All</button>
            </div>
          </div>
          <div class="queue-table-wrap">
            <table class="queue-table">
              <thead><tr><th>#</th><th>Title</th><th>Platform</th><th>Format</th><th>Progress</th><th>Status</th><th>Actions</th></tr></thead>
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

        <article class="card history-card" id="history" aria-label="Download history">
          <div class="section-head">
            <h2><span class="title-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M8 6h12"/><path d="M8 12h12"/><path d="M8 18h12"/><circle cx="4.5" cy="6" r="1.2"/><circle cx="4.5" cy="12" r="1.2"/><circle cx="4.5" cy="18" r="1.2"/></svg></span>DOWNLOAD HISTORY</h2>
          </div>
          <div class="history-list" id="historyRows">
            <div class="placeholder-panel">
              <strong>No saved history yet.</strong>
              <p>Completed, failed, and cancelled downloads will appear here.</p>
            </div>
          </div>
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
  --bg: #080d19;
  --bg-2: #0b1323;
  --panel: #101826;
  --panel-2: #0d1523;
  --panel-3: #151f31;
  --line: #253247;
  --line-soft: rgba(150, 164, 190, .14);
  --text: #eef3fb;
  --muted: #9aa8ba;
  --muted-2: #748297;
  --blue: #756dff;
  --blue-2: #8ea0ff;
  --green: #41d878;
  --orange: #ffae2a;
  --red: #ff6b78;
  --radius: 5px;
  --sidebar-width: 260px;
}
* { box-sizing: border-box; }
html, body {
  width: 100%;
  height: 100%;
  overflow: hidden;
}
body {
  margin: 0;
  color: var(--text);
  font: 13px/1.42 "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  background:
    radial-gradient(circle at 9% 12%, rgba(95, 76, 180, .19), transparent 27%),
    radial-gradient(circle at 93% 0%, rgba(45, 85, 145, .13), transparent 31%),
    linear-gradient(180deg, #0b1322 0%, #070d19 100%);
}
button, input, select { font: inherit; }
.app-shell {
  width: 100vw;
  height: 100vh;
  display: grid;
  grid-template-columns: var(--sidebar-width) minmax(0, 1fr);
  background:
    radial-gradient(circle at 16% 18%, rgba(93, 74, 175, .13), transparent 27%),
    linear-gradient(180deg, rgba(12, 20, 35, .96), rgba(7, 13, 25, .99));
  overflow: hidden;
}
.sidebar {
  grid-column: 1;
  height: 100vh;
  min-height: 0;
  position: sticky;
  top: 0;
  padding: 22px 16px 18px;
  background: linear-gradient(180deg, rgba(16, 19, 42, .55), rgba(7, 13, 25, .2));
  border-right: 1px solid rgba(93, 106, 140, .20);
  display: flex;
  flex-direction: column;
  gap: 18px;
  overflow: hidden;
}
.brand { display: flex; align-items: flex-start; gap: 10px; min-width: 0; }
.side-brand { flex: 0 0 auto; padding: 0 4px 5px; }
.brand-icon {
  width: 38px;
  height: 38px;
  border-radius: 5px;
  display: grid;
  place-items: center;
  color: white;
  background: linear-gradient(135deg, #4e6bff, #765cff);
  border: 1px solid rgba(255,255,255,.16);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.18);
  flex: 0 0 38px;
}
.brand h1 { margin: 0; font-size: 20px; line-height: 1.08; letter-spacing: -.025em; font-weight: 760; white-space: nowrap; }
.brand p { margin: 5px 0 0; color: var(--muted); font-size: 12px; line-height: 1.32; white-space: normal; overflow-wrap: anywhere; }
.nav-list { display: grid; gap: 6px; margin: 7px 0 0; flex: 0 0 auto; }
.nav-item {
  min-height: 38px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 12px;
  color: #eef3fb;
  text-decoration: none;
  border: 1px solid transparent;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 650;
  line-height: 1;
}
.nav-item:hover { background: rgba(255,255,255,.04); }
.nav-item.active {
  color: #c6ccff;
  background: linear-gradient(90deg, rgba(117, 109, 255, .35), rgba(117, 109, 255, .14));
  border-left: 3px solid var(--blue);
  padding-left: 9px;
}
.nav-icon {
  width: 21px;
  height: 21px;
  color: #dce4ff;
  display: grid;
  place-items: center;
  flex: 0 0 21px;
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
  margin-top: auto;
  padding: 13px 12px;
  display: grid;
  grid-template-columns: 20px 1fr;
  gap: 10px;
  border-radius: 5px;
  border: 1px solid rgba(117,109,255,.36);
  background: rgba(117,109,255,.105);
  color: #b9c4ff;
  flex: 0 0 auto;
}
.side-note p { margin: 0; line-height: 1.42; font-size: 13px; }
.note-icon { width: 19px; height: 19px; color: #aeb8ff; }
.sidebar-footer { color: #ccd5e5; padding-top: 1px; flex: 0 0 auto; }
.sidebar-footer p { margin: 0 0 6px; font-size: 13px; }
.link-button { background: transparent; border: 0; padding: 0; color: #a8b1ff; text-decoration: underline; cursor: pointer; font-size: 13px; }
.main {
  grid-column: 2;
  min-width: 0;
  width: 100%;
  height: 100vh;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 22px 28px 28px 18px;
  scrollbar-color: #2a3750 transparent;
}
.main-header {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 38px;
  margin-bottom: 20px;
}
.run-pill {
  min-width: 106px;
  height: 38px;
  padding: 0 15px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 1px solid rgba(65, 216, 120, .34);
  border-radius: 5px;
  background: rgba(65, 216, 120, .12);
  color: #f5fff8;
  font-size: 14px;
  font-weight: 560;
}
.run-pill span {
  width: 10px;
  height: 10px;
  border-radius: 99px;
  background: var(--green);
  box-shadow: 0 0 12px rgba(65,216,120,.56);
}
.layout-grid {
  width: 100%;
  max-width: none;
  display: grid;
  grid-template-columns: minmax(0, 1.18fr) minmax(380px, .82fr);
  gap: 12px;
  align-items: start;
}
.card {
  min-width: 0;
  background: linear-gradient(180deg, rgba(16, 25, 40, .93), rgba(9, 15, 26, .96));
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.022);
}
.server-card, .tools-card, .defaults-card { padding: 15px 16px; }
.queue-card, .history-card, .logs-card { padding: 12px; }
.card-title, .section-head h2 {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #dce5f6;
  font-weight: 760;
  font-size: 13px;
  letter-spacing: .025em;
  text-transform: uppercase;
}
.title-icon { width: 18px; height: 18px; color: #eaf0ff; opacity: .95; display: inline-grid; place-items: center; flex: 0 0 18px; }
.status-rows { margin-top: 15px; display: grid; }
.status-row {
  display: grid;
  grid-template-columns: 174px minmax(0, 1fr) 30px;
  align-items: center;
  min-height: 36px;
  border-bottom: 1px solid var(--line-soft);
  gap: 10px;
}
.status-row span { color: #f2f5fa; }
.status-row strong { color: #aeb8ff; font-weight: 520; word-break: break-all; }
.status-row strong.ok, .ok { color: var(--green) !important; }
.warn { color: var(--orange) !important; }
.bad { color: var(--red) !important; }
.pending { color: var(--muted) !important; }
.icon-button { width: 30px; height: 30px; border: 0; border-radius: 4px; background: transparent; color: #c7d1e4; cursor: pointer; display: grid; place-items: center; padding: 6px; }
.icon-button:hover { background: rgba(255,255,255,.065); }
.button-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 16px; }
.button, .mini-button {
  height: 33px;
  border-radius: 5px;
  border: 1px solid #2a374c;
  background: #101929;
  color: #f0f4fb;
  padding: 0 12px;
  cursor: pointer;
  font-weight: 700;
  font-size: 12px;
}
.button { display: inline-flex; align-items: center; justify-content: center; gap: 8px; }
.button:hover, .mini-button:hover { background: #162236; border-color: #3a4860; }
.button.square { width: 36px; padding: 0; }
.button.compact { height: 30px; font-size: 12px; padding-inline: 11px; }
.button.save { display: flex; margin: 16px auto 0; min-width: 108px; }
.button-icon { width: 16px; height: 16px; color: #dce5f4; display: inline-grid; place-items: center; flex: 0 0 16px; }
.button-icon.dots { width: 18px; height: 18px; }
.button-icon.dots svg { fill: currentColor; stroke: none; }
.mini-button { min-width: 86px; height: 30px; padding: 0 11px; justify-self: end; white-space: nowrap; }
.tool-table { margin-top: 13px; border-top: 1px solid var(--line-soft); }
.tool-row {
  min-height: 37px;
  display: grid;
  grid-template-columns: 118px 96px minmax(84px, 1fr) 88px;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid var(--line-soft);
}
.tool-row span { font-weight: 760; color: #f0f3f9; }
.tool-row strong { position: relative; padding-left: 22px; font-weight: 520; }
.tool-row strong::before { content: ""; position: absolute; left: 0; top: 50%; width: 11px; height: 11px; margin-top: -5.5px; border-radius: 50%; background: currentColor; opacity: .95; box-shadow: 0 0 10px currentColor; }
.tool-row em { color: #91a0b4; font-style: normal; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.queue-card { grid-column: span 1; align-self: stretch; }
.defaults-card { grid-column: span 1; align-self: stretch; }
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.head-actions { display: flex; align-items: center; gap: 8px; }
.queue-table-wrap { overflow: auto; border-top: 1px solid var(--line-soft); }
.queue-table { width: 100%; border-collapse: collapse; min-width: 760px; table-layout: fixed; }
.queue-table th { height: 32px; color: #cbd5e5; font-size: 12px; text-align: left; font-weight: 760; padding: 0 10px; }
.queue-table td { height: 43px; border-top: 1px solid var(--line-soft); color: #e8edf5; vertical-align: middle; padding: 0 10px; }
.queue-table th:first-child, .queue-table td:first-child { width: 42px; text-align: center; padding-inline: 4px; }
.queue-table th:nth-child(3), .queue-table td:nth-child(3) { width: 150px; padding-left: 14px; padding-right: 18px; }
.queue-table th:nth-child(4), .queue-table td:nth-child(4) { width: 150px; padding-left: 14px; padding-right: 18px; }
.queue-table th:nth-child(5), .queue-table td:nth-child(5) { width: 160px; }
.queue-table th:nth-child(6), .queue-table td:nth-child(6) { width: 136px; }
.queue-table th:nth-child(7), .queue-table td:nth-child(7) { width: 132px; text-align: right; }
.job-actions { display: inline-flex; justify-content: flex-end; gap: 6px; }
.job-actions button { height: 26px; padding: 0 8px; border-radius: 4px; font-size: 11px; }
.job-actions .cancel-job { color: #ffd7dc; border-color: rgba(255, 107, 120, .38); }
.history-list { display: grid; gap: 8px; }
.history-row { display: grid; grid-template-columns: minmax(0, 1fr) 100px 100px 150px; gap: 10px; align-items: center; min-height: 44px; padding: 9px 10px; border: 1px solid var(--line-soft); border-radius: 5px; background: rgba(255,255,255,.025); }
.history-row strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.history-row small { color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.history-row .done { color: var(--green); }
.history-row .failed, .history-row .cancelled { color: var(--red); }
.history-row .stopped { color: var(--orange); }
.title-cell strong { display: block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.title-cell small { display: block; margin-top: 2px; color: #9ba9ba; font-size: 11px; }
.platform { display: inline-flex; align-items: center; gap: 6px; color: #dbe3ef; }
.youtube-dot { width: 13px; height: 9px; display: inline-grid; place-items: center; border-radius: 2px; background: #ff1d1d; font-size: 7px; color: white; }
.progress-cell { min-width: 120px; }
.progress-meta { display: flex; align-items: center; gap: 8px; }
.progress-text { min-width: 48px; text-align: right; color: #d9e1ef; font-size: 12px; }
.progress-bar { flex: 1; min-width: 80px; height: 7px; border-radius: 99px; background: #202a3a; overflow: hidden; }
.progress-fill { height: 100%; width: 0%; border-radius: inherit; background: linear-gradient(90deg, #6f65ff, #8c7dff); }
.progress-fill.live { width: 100%; background: linear-gradient(90deg, var(--orange), #ffd07a, var(--orange)); animation: pulse 1.35s linear infinite; }
.status-badge { color: var(--blue-2); display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.status-badge.done { color: var(--green); }
.status-badge.failed { color: var(--red); }
.status-badge.queued { color: #e7edf8; }
.table-footer { display: flex; align-items: center; justify-content: space-between; padding-top: 11px; color: #c1ccdb; }
.empty-row td { color: var(--muted); text-align: center !important; padding: 24px 0; }
.field { display: grid; gap: 7px; margin-top: 13px; color: #e9eef7; }
.field span { color: #e9eef7; }
.field input, .field select {
  width: 100%;
  height: 32px;
  border-radius: 4px;
  border: 1px solid #29374d;
  background: #0a1220;
  color: #dfe6f2;
  padding: 0 11px;
  outline: none;
}
.field input:focus, .field select:focus { border-color: #5966ff; }
.field-line { display: grid; grid-template-columns: 1fr 76px; gap: 8px; }
.check-line { display: flex; align-items: center; gap: 9px; margin-top: 15px; color: #cfd8e8; }
.check-line input, .auto-scroll input { accent-color: var(--blue); }
.logs-card { grid-column: 1 / -1; }
.logs-card pre, #installLog {
  margin: 0;
  height: 156px;
  overflow: auto;
  padding: 10px 15px;
  background: #0a111d;
  border-top: 1px solid var(--line-soft);
  color: #d1dbec;
  font: 12px/1.55 Consolas, "Cascadia Mono", monospace;
  white-space: pre-wrap;
}
.auto-scroll { color: #d4dcec; font-size: 12px; display: flex; align-items: center; gap: 6px; }
.install-drawer { position: fixed; right: 24px; bottom: 24px; width: min(560px, calc(100vw - 48px)); background: var(--panel); border: 1px solid var(--line); border-radius: 6px; box-shadow: 0 18px 50px rgba(0,0,0,.36); }
.install-head { display: flex; justify-content: space-between; padding: 12px 14px; border-bottom: 1px solid var(--line-soft); }
#installLog { height: 220px; border-top: 0; }

.brand-copy {
  min-width: 0;
  flex: 1 1 auto;
}
body[data-page="dashboard"] .history-card {
  display: none;
}
body:not([data-page="dashboard"]) .layout-grid {
  grid-template-columns: minmax(0, 1fr);
}
body:not([data-page="dashboard"]) .layout-grid > .card {
  display: none;
}
body[data-page="queue"] .layout-grid > .queue-card,
body[data-page="history"] .layout-grid > .history-card,
body[data-page="tools"] .layout-grid > .tools-card,
body[data-page="settings"] .layout-grid > .defaults-card,
body[data-page="logs"] .layout-grid > .logs-card {
  display: block;
  grid-column: 1 / -1;
}
body[data-page="queue"] .queue-card,
body[data-page="logs"] .logs-card {
  min-height: min(620px, calc(100vh - 98px));
}
body[data-page="history"] .history-card {
  min-height: min(420px, calc(100vh - 98px));
}
body[data-page="settings"] .defaults-card,
body[data-page="tools"] .tools-card {
  min-height: auto;
}
body[data-page="tools"] .tools-card,
body[data-page="settings"] .defaults-card {
  max-width: 980px;
}
body[data-page="logs"] .logs-card pre {
  height: calc(100vh - 175px);
  min-height: 360px;
}
.placeholder-panel {
  margin-top: 10px;
  min-height: 260px;
  display: grid;
  align-content: center;
  justify-items: center;
  text-align: center;
  gap: 7px;
  color: var(--muted);
  border-top: 1px solid var(--line-soft);
}
.placeholder-panel strong {
  color: #e7edf8;
  font-size: 14px;
}
.placeholder-panel p {
  margin: 0;
}

@keyframes pulse { 0% { opacity: .65; } 50% { opacity: 1; } 100% { opacity: .65; } }
@media (max-width: 1180px) {
  html, body { overflow: hidden; }
  .app-shell { grid-template-columns: 1fr; grid-template-rows: auto minmax(0, 1fr); }
  .sidebar {
    position: relative;
    grid-column: 1;
    height: auto;
    min-height: 0;
    flex-direction: row;
    align-items: center;
    flex-wrap: wrap;
    padding: 14px 16px 10px;
    border-right: 0;
    border-bottom: 1px solid rgba(93, 106, 140, .20);
  }
  .side-brand { padding: 0; }
  .nav-list { display: flex; flex-wrap: wrap; margin: 0; }
  .side-note, .sidebar-footer { display: none; }
  .main { grid-column: 1; height: calc(100vh - 78px); min-height: 0; overflow-y: auto; padding: 12px 16px 20px; }
  .main-header { margin-bottom: 12px; }
  .layout-grid { grid-template-columns: 1fr; }
}
@media (max-width: 760px) {
  .sidebar { align-items: flex-start; }
  .brand { width: 100%; }
  .main { padding: 12px 12px 16px; }
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
  if (!el) return;
  if (el.matches('input, textarea, select')) el.value = value;
  else el.textContent = value;
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
  const labels = {
    best: 'best available',
    '1080': 'mp4 (1080p)',
    '720': 'mp4 (720p)',
    audio: 'audio (mp3)',
  };
  return labels[quality] || quality;
}

function platform(job) {
  if ((job.extractor || '').toLowerCase().includes('vimeo')) return '<span class="platform">▣ Vimeo</span>';
  return '<span class="platform"><span class="youtube-dot">▶</span>YouTube</span>';
}

function phaseClass(job) {
  if (job.phase === 'finished') return 'done';
  if (job.phase === 'failed' || job.phase === 'cancelled') return 'failed';
  if (job.phase === 'stopped') return 'stopped';
  if (job.phase === 'queued') return 'queued';
  return '';
}

function isActive(job) {
  return !['finished', 'failed', 'cancelled', 'stopped'].includes(job.phase);
}

function renderJobs(jobs) {
  lastJobs = jobs;
  const displayJobs = jobs;
  const activeCount = jobs.filter(isActive).length;
  text('[data-role="requests-today"]', jobs.length);
  text('[data-role="active-count"]', activeCount);
  text('[data-role="queue-summary"]', `Showing ${displayJobs.length} downloads`);

  for (const job of jobs) {
    const stateKey = `${job.phase}:${job.status}:${Math.round(Number(job.progress) || 0)}`;
    if (seenJobStates.get(job.id) !== stateKey) {
      seenJobStates.set(job.id, stateKey);
      const level = job.phase === 'failed' ? 'error' : job.phase === 'finished' ? 'done' : 'info';
      addLog(level, `${job.title || 'Untitled video'} · ${job.status || job.phase}`);
    }
  }

  if (!displayJobs.length) {
    queueRows.innerHTML = '<tr class="empty-row"><td colspan="7">No download requests yet. Start one from the YouTube player.</td></tr>';
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
        <td>${isActive(job) ? `<span class="job-actions"><button class="cancel-job" data-cancel-job="${job.id}">Cancel</button></span>` : ''}</td>
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

async function clearCompletedJobs() {
  const data = await api('/api/jobs/clear-completed', { method: 'POST' });
  addLog('info', `Cleared ${data.cleared || 0} completed queue rows.`);
  await refreshJobs();
  await refreshHistory();
}

function renderHistory(items = []) {
  const root = document.getElementById('historyRows');
  if (!root) return;
  if (!items.length) {
    root.innerHTML = '<div class="placeholder-panel"><strong>No saved history yet.</strong><p>Completed, failed, and cancelled downloads will appear here.</p></div>';
    return;
  }
  root.innerHTML = items.map(item => `<div class="history-row"><strong title="${escapeHtml(item.title || 'Untitled video')}">${escapeHtml(item.title || 'Untitled video')}</strong><small>${escapeHtml(formatName(item))}</small><span class="${escapeHtml(phaseClass(item))}">${escapeHtml(item.status || item.phase || '')}</span><small>${escapeHtml(item.finishedAt || '')}</small></div>`).join('');
}

async function refreshHistory() {
  const data = await api('/api/history');
  renderHistory(data.history || []);
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
$('#cancelAll')?.addEventListener('click', () => cancelAll().catch(error => alert(error.message)));
document.addEventListener('click', (event) => {
  const cancelButton = event.target.closest('[data-cancel-job]');
  if (cancelButton) {
    cancelJob(cancelButton.dataset.cancelJob).catch(error => alert(error.message));
  }
});
$('#clearCompleted')?.addEventListener('click', () => clearCompletedJobs().catch(error => alert(error.message)));
$('#clearLogs')?.addEventListener('click', () => { logLines = []; renderLogs(); });
$('#saveDefaults')?.addEventListener('click', saveDefaults);
$('#checkUpdatesLink')?.addEventListener('click', () => addLog('info', 'Update check is manual in this local build.'));


function pageFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const page = params.get('page') || 'dashboard';
  return ['dashboard', 'queue', 'history', 'tools', 'settings', 'logs'].includes(page) ? page : 'dashboard';
}

function setPage(page, push = true) {
  document.body.dataset.page = page;
  document.querySelectorAll('.nav-item[data-page]').forEach((item) => {
    const active = item.dataset.page === page;
    item.classList.toggle('active', active);
    if (active) item.setAttribute('aria-current', 'page');
    else item.removeAttribute('aria-current');
  });
  if (push) {
    const url = new URL(window.location.href);
    url.searchParams.set('page', page);
    history.pushState({ page }, '', url);
  }
  document.querySelector('.main')?.scrollTo({ top: 0, behavior: 'instant' });
}

document.querySelectorAll('.nav-item[data-page]').forEach((item) => {
  item.addEventListener('click', (event) => {
    event.preventDefault();
    setPage(item.dataset.page || 'dashboard');
  });
});

window.addEventListener('popstate', () => setPage(pageFromUrl(), false));

setPage(pageFromUrl(), false);
loadDefaults();
addLog('info', 'Server started on http://127.0.0.1:17723');
addLog('info', 'Extension requests will appear in the queue automatically.');
refreshStatus();
refreshJobs().catch(console.error);
refreshHistory().catch(console.error);
setInterval(refreshStatus, 2500);
setInterval(() => refreshJobs().catch(console.error), 1000);
setInterval(() => refreshHistory().catch(console.error), 2500);
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
    history_recorded: bool = False

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
            "finishedAt": format_history_time(self.updated_at) if self.phase in TERMINAL_PHASES else "",
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
HISTORY: list[dict] = []


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

    launcher = find_python_launcher()
    if launcher and run_probe(launcher + ["-m", "yt_dlp", "--version"]):
        return launcher + ["-m", "yt_dlp"], "Python module: " + " ".join(launcher + ["-m", "yt_dlp"])

    if has_embedded_yt_dlp():
        source = "bundled module" if FROZEN else "Python module"
        return self_ytdlp_command(), f"{source}: yt-dlp"

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

    command = list(cmd_base) + ["-J", "--no-warnings", "--skip-download", "--no-playlist"]
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

    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    command = list(yt_dlp_cmd) + [
        "--newline",
        "--no-playlist",
        "--force-overwrites",
        "--paths", f"temp:{TEMP_ROOT}",
    ]

    if quality == "audio":
        command += ["-f", FORMAT_MAP[quality], "-x", "--audio-format", "mp3"]
    else:
        command += ["-f", FORMAT_MAP[quality], "--merge-output-format", "mp4"]

    command += ["--ffmpeg-location", str(ffmpeg_path)]

    if mode == "section":
        section = f"*{seconds_to_clock(payload['start'])}-{seconds_to_clock(payload['end'])}"
        command += ["--download-sections", section]
        # yt-dlp uses FFmpeg for selected time ranges. On Windows, FFmpeg can
        # update progress with carriage-return or key=value progress records
        # instead of normal yt-dlp percentage lines, so ask FFmpeg to emit a
        # machine-readable progress stream that the manager can parse.
        command += ["--downloader-args", "ffmpeg:-progress pipe:1 -stats_period 0.5 -nostats"]
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



def safe_filename(value: str, fallback: str = "cliptap") -> str:
    value = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", " ", value or "")
    value = re.sub(r"\s+", " ", value).strip(" .")
    if not value:
        value = fallback
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if value.upper() in reserved:
        value = f"{value}_file"
    return value[:150].rstrip(" .") or fallback


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for index in range(2, 1000):
        candidate = parent / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
    return parent / f"{stem} {uuid.uuid4().hex[:8]}{suffix}"


def build_source_download_command(job: DownloadJob, temp_dir: Path) -> list[str]:
    yt_dlp_cmd, _ = find_yt_dlp()
    ffmpeg_path, _ = find_ffmpeg()
    if not yt_dlp_cmd:
        raise ClipTapError("yt-dlp is not installed.")
    if not ffmpeg_path:
        raise ClipTapError("FFmpeg is not installed.")

    payload = job.payload
    quality = payload["quality"]
    temp_dir.mkdir(parents=True, exist_ok=True)

    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    command = list(yt_dlp_cmd) + [
        "--newline",
        "--no-playlist",
        "--force-overwrites",
        "--paths", f"temp:{TEMP_ROOT}",
    ]
    if quality == "audio":
        command += ["-f", FORMAT_MAP[quality], "-x", "--audio-format", "mp3"]
    else:
        command += ["-f", FORMAT_MAP[quality], "--merge-output-format", "mp4"]
    command += ["--ffmpeg-location", str(ffmpeg_path)]
    if payload.get("cookieBrowser"):
        command += ["--cookies-from-browser", payload["cookieBrowser"]]
    command += ["-o", str(temp_dir / "source.%(ext)s"), payload["url"]]
    return command


def find_source_media_file(temp_dir: Path) -> Path:
    ignored_suffixes = {".part", ".ytdl", ".temp", ".tmp"}
    candidates = [
        item for item in temp_dir.iterdir()
        if item.is_file() and item.suffix.lower() not in ignored_suffixes and not item.name.endswith(".part-Frag")
    ]
    if not candidates:
        raise ClipTapError("The source media download finished, but no media file was found.")
    candidates.sort(key=lambda item: (item.stat().st_size, item.stat().st_mtime), reverse=True)
    return candidates[0]


def section_output_path(job: DownloadJob, source_file: Path) -> Path:
    payload = job.payload
    title = safe_filename(job.title, "cliptap")
    start = seconds_to_clock(payload["start"]).replace(":", "-")
    end = seconds_to_clock(payload["end"]).replace(":", "-")
    suffix = ".mp3" if payload.get("quality") == "audio" else ".mp4"
    return unique_path(OUTPUT_DIR / f"{title} [{job.id}] {start}-{end}{suffix}")


def ffmpeg_trim_command(job: DownloadJob, source_file: Path, output_file: Path) -> list[str]:
    ffmpeg_path, _ = find_ffmpeg()
    if not ffmpeg_path:
        raise ClipTapError("FFmpeg is not installed.")

    start_time = float(job.payload["start"])
    duration = max(0.1, float(job.payload["end"]) - start_time)

    # Re-encode the selected range. Stream-copy cuts are keyframe-aligned and
    # can export a different start/end than the handles selected in YouTube.
    # With transcoding, FFmpeg's default accurate seeking discards pre-roll
    # frames while still avoiding a full decode from the beginning.
    command = [
        str(ffmpeg_path),
        "-hide_banner",
        "-y",
        "-ss", seconds_to_clock(start_time),
        "-i", str(source_file),
        "-t", seconds_to_clock(duration),
        "-progress", "pipe:1",
        "-nostats",
    ]

    if job.payload.get("quality") == "audio":
        command += [
            "-vn",
            "-map", "0:a:0?",
            "-c:a", "libmp3lame",
            "-q:a", "2",
        ]
    else:
        command += [
            "-map", "0:v:0?",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
        ]

    command.append(str(output_file))
    return command


TEMP_FILE_SUFFIXES = (".part", ".ytdl", ".temp", ".tmp")


def is_temporary_download_file(path: Path) -> bool:
    name = path.name.lower()
    return (
        path.is_file()
        and (
            name.endswith(TEMP_FILE_SUFFIXES)
            or ".part-" in name
            or name.endswith(".part-frag")
        )
    )


def has_other_active_jobs(current_job_id: str | None = None) -> bool:
    active_phases = {"queued", "downloading", "processing", "live", "cancelling"}
    with LOCK:
        return any(
            job.id != current_job_id and job.phase in active_phases
            for job in JOBS.values()
        )


def cleanup_output_temporary_files(current_job_id: str | None = None):
    if has_other_active_jobs(current_job_id):
        return
    try:
        legacy_temp = OUTPUT_DIR / ".cliptap-temp"
        if legacy_temp.exists():
            shutil.rmtree(legacy_temp, ignore_errors=True)
    except Exception:
        pass
    try:
        if not OUTPUT_DIR.exists():
            return
        for item in OUTPUT_DIR.iterdir():
            if is_temporary_download_file(item):
                try:
                    item.unlink()
                except Exception:
                    pass
    except Exception:
        pass


def format_history_time(value: float | None) -> str:
    if not value:
        return ""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(value))


def load_history():
    global HISTORY
    try:
        if HISTORY_FILE.exists():
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            HISTORY = data[-500:] if isinstance(data, list) else []
    except Exception:
        HISTORY = []


def save_history():
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(HISTORY[-500:], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def record_history(job: DownloadJob):
    if job.history_recorded or job.phase not in TERMINAL_PHASES:
        return
    item = job.public()
    if not item.get("finishedAt"):
        item["finishedAt"] = format_history_time(time.time())
    HISTORY.insert(0, item)
    del HISTORY[500:]
    job.history_recorded = True
    save_history()


def update_job(job: DownloadJob, **changes):
    with LOCK:
        for key, value in changes.items():
            setattr(job, key, value)
        job.touch()
        record_history(job)



def clock_to_seconds(value: str) -> float:
    value = value.strip()
    parts = value.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(parts[0])
    except (TypeError, ValueError, IndexError):
        return 0.0


def iter_process_records(process: subprocess.Popen, cancel_event: threading.Event):
    """Yield process output records split by either newlines or carriage returns.

    ffmpeg often updates progress using carriage returns instead of full lines.
    A blocking readline() can make section downloads look stuck at 0%, so the
    pipe is read character-by-character on a small background reader thread.
    """
    output_queue: queue.Queue[str | None] = queue.Queue()

    def reader():
        try:
            if not process.stdout:
                return
            while True:
                chunk = process.stdout.read(1)
                if chunk == "":
                    break
                output_queue.put(chunk)
        finally:
            output_queue.put(None)

    threading.Thread(target=reader, daemon=True).start()
    buffer = ""
    reader_done = False

    while True:
        if cancel_event.is_set():
            break
        try:
            chunk = output_queue.get(timeout=0.15)
        except queue.Empty:
            if reader_done and process.poll() is not None:
                break
            continue

        if chunk is None:
            reader_done = True
            if buffer.strip():
                yield buffer.strip()
                buffer = ""
            if process.poll() is not None:
                break
            continue

        if chunk in {"\n", "\r"}:
            if buffer.strip():
                yield buffer.strip()
                buffer = ""
            continue

        buffer += chunk
        if len(buffer) >= 4000:
            yield buffer.strip()
            buffer = ""

def prepare_metadata(job: DownloadJob):
    update_job(job, status="Reading info...", phase="metadata")
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



def run_section_download(job: DownloadJob):
    payload = job.payload
    temp_dir = TEMP_ROOT / "section" / job.id
    percent_re = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")
    speed_re = re.compile(r"\bat\s+([^\s]+/s)")
    eta_re = re.compile(r"\bETA\s+([^\s]+)")
    size_re = re.compile(r"of\s+~?([^\s]+)")
    ffmpeg_out_time_re = re.compile(r"\bout_time=(\d+:\d+:\d+(?:\.\d+)?)")
    ffmpeg_out_time_raw_re = re.compile(r"\bout_time_(?:ms|us)=(\d+)")
    ffmpeg_time_re = re.compile(r"\btime=(\d+:\d+:\d+(?:\.\d+)?)")
    duration = max(0.1, float(payload["end"]) - float(payload["start"]))

    def update_from_download_line(line: str):
        changes = {}
        match = percent_re.search(line)
        if match:
            source_progress = max(0.0, min(100.0, float(match.group(1))))
            changes["progress"] = max(1.0, min(85.0, source_progress * 0.84 + 1.0))
            changes["status"] = "Downloading..."
        speed_match = speed_re.search(line)
        eta_match = eta_re.search(line)
        size_match = size_re.search(line)
        if speed_match:
            changes["speed"] = speed_match.group(1)
        if eta_match:
            changes["eta"] = eta_match.group(1)
        if size_match:
            changes["downloaded"] = size_match.group(1)
        if "Merger" in line or "Merging formats" in line:
            changes["status"] = "Preparing..."
            changes["phase"] = "processing"
        if changes:
            update_job(job, **changes)

    def update_from_trim_line(line: str):
        elapsed = None
        raw_match = ffmpeg_out_time_raw_re.search(line)
        out_time_match = ffmpeg_out_time_re.search(line)
        time_match = ffmpeg_time_re.search(line)
        if raw_match:
            raw_time = float(raw_match.group(1))
            elapsed = raw_time / 1_000_000.0
            if elapsed < 0.01 and raw_time > 0:
                elapsed = raw_time / 1000.0
        elif out_time_match:
            elapsed = clock_to_seconds(out_time_match.group(1))
        elif time_match:
            elapsed = clock_to_seconds(time_match.group(1))
        if elapsed is not None:
            trim_progress = max(0.0, min(100.0, (elapsed / duration) * 100.0))
            update_job(
                job,
                status="Trimming...",
                phase="processing",
                progress=max(job.progress, min(99.0, 86.0 + trim_progress * 0.13)),
            )

    try:
        update_job(job, status="Downloading...", phase="downloading", progress=1.0)
        source_command = build_source_download_command(job, temp_dir)
        job.process = popen_text(source_command, temp_dir)
        for line in iter_process_records(job.process, job.cancel_event):
            if job.cancel_event.is_set():
                raise CancelledError()
            update_from_download_line(line)
        if job.cancel_event.is_set():
            raise CancelledError()
        code = job.process.wait()
        if code != 0:
            raise ClipTapError(f"yt-dlp exited with code {code} while downloading source media.")

        source_file = find_source_media_file(temp_dir)
        output_file = section_output_path(job, source_file)
        update_job(job, status="Trimming...", phase="processing", progress=max(job.progress, 86.0), speed="", eta="")
        trim_command = ffmpeg_trim_command(job, source_file, output_file)
        job.process = popen_text(trim_command, temp_dir)
        for line in iter_process_records(job.process, job.cancel_event):
            if job.cancel_event.is_set():
                raise CancelledError()
            update_from_trim_line(line)
        if job.cancel_event.is_set():
            raise CancelledError()
        code = job.process.wait()
        if code != 0:
            raise ClipTapError(f"FFmpeg exited with code {code} while cutting the selected section.")
        update_job(job, status="Finished", phase="finished", progress=100.0, downloaded=str(output_file))
    finally:
        if job.process and job.process.poll() is None:
            try:
                job.process.kill()
            except Exception:
                pass
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


def run_download(job: DownloadJob):
    try:
        prepare_metadata(job)
        if job.payload["mode"] == "section":
            run_section_download(job)
            return

        if job.is_live and job.payload["mode"] == "full":
            status = "Recording..."
            phase = "live"
        else:
            status = "Downloading..."
            phase = "downloading"
        update_job(job, status=status, phase=phase)

        command = build_download_command(job)
        job.process = popen_text(command, OUTPUT_DIR)

        percent_re = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")
        speed_re = re.compile(r"\bat\s+([^\s]+/s)")
        eta_re = re.compile(r"\bETA\s+([^\s]+)")
        size_re = re.compile(r"of\s+~?([^\s]+)")

        ffmpeg_time_re = re.compile(r"\btime=(\d+:\d+:\d+(?:\.\d+)?)")
        ffmpeg_out_time_re = re.compile(r"\bout_time=(\d+:\d+:\d+(?:\.\d+)?)")
        ffmpeg_out_time_raw_re = re.compile(r"\bout_time_(?:ms|us)=(\d+)")
        section_duration = None
        section_start = 0.0
        section_end = 0.0
        if job.payload["mode"] == "section":
            section_start = float(job.payload["start"])
            section_end = float(job.payload["end"])
            section_duration = max(0.1, section_end - section_start)

        def section_progress_from_elapsed(elapsed: float) -> float:
            # FFmpeg may report either output-relative time such as 00:00:12
            # or source-relative time such as 00:09:13 depending on the input.
            if section_duration and elapsed > section_duration and section_start <= elapsed <= section_end + 5:
                elapsed -= section_start
            return max(1.0, min(99.0, (elapsed / section_duration) * 100.0))

        for line in iter_process_records(job.process, job.cancel_event):
            if job.cancel_event.is_set():
                raise CancelledError()

            changes = {}

            match = percent_re.search(line)
            if match and not (job.is_live and job.payload["mode"] == "full"):
                changes["progress"] = max(0.0, min(100.0, float(match.group(1))))

            if section_duration and not changes.get("progress"):
                elapsed = None
                ffmpeg_out_time_raw_match = ffmpeg_out_time_raw_re.search(line)
                ffmpeg_out_time_match = ffmpeg_out_time_re.search(line)
                ffmpeg_time_match = ffmpeg_time_re.search(line)
                if ffmpeg_out_time_raw_match:
                    raw_time = float(ffmpeg_out_time_raw_match.group(1))
                    # FFmpeg's out_time_ms is historically microseconds in many
                    # builds despite the name. Prefer microseconds, but fall back
                    # to milliseconds if the result is implausibly tiny.
                    elapsed = raw_time / 1_000_000.0
                    if elapsed < 0.01 and raw_time > 0:
                        elapsed = raw_time / 1000.0
                elif ffmpeg_out_time_match:
                    elapsed = clock_to_seconds(ffmpeg_out_time_match.group(1))
                elif ffmpeg_time_match:
                    elapsed = clock_to_seconds(ffmpeg_time_match.group(1))
                if elapsed is not None:
                    changes["progress"] = section_progress_from_elapsed(elapsed)
                    changes["status"] = "Downloading..."

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
                changes["status"] = "Downloading..."
                if section_duration and job.progress <= 0:
                    changes["progress"] = 1.0
            elif "Merger" in line or "Merging formats" in line:
                changes["status"] = "Merging..."
                changes["phase"] = "processing"
            elif "Deleting original file" in line:
                changes["status"] = "Cleaning..."
                changes["phase"] = "processing"

            if changes:
                update_job(job, **changes)

        if job.cancel_event.is_set():
            raise CancelledError()

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
        cleanup_output_temporary_files(job.id)


def clear_completed_jobs() -> int:
    with LOCK:
        completed_ids = [job_id for job_id, job in JOBS.items() if job.phase in TERMINAL_PHASES]
        for job_id in completed_ids:
            job = JOBS.get(job_id)
            if job:
                record_history(job)
            JOBS.pop(job_id, None)
    return len(completed_ids)



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

        if path == "/api/history":
            with LOCK:
                entries = list(HISTORY)
            json_response(self, {"ok": True, "history": entries})
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

            if path == "/api/jobs/clear-completed":
                json_response(self, {"ok": True, "cleared": clear_completed_jobs()})
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
        import yt_dlp
    except Exception as exc:
        print(f"yt-dlp is not bundled or installed: {exc}", file=sys.stderr)
        return 1

    old_argv = sys.argv[:]
    sys.argv = ["yt-dlp"] + argv
    try:
        yt_dlp_main = getattr(yt_dlp, "main", None)
        if callable(yt_dlp_main):
            try:
                result = yt_dlp_main(argv)
            except TypeError:
                result = yt_dlp_main()
            return int(result or 0)

        real_main = getattr(yt_dlp, "_real_main", None)
        if callable(real_main):
            result = real_main(argv)
            if isinstance(result, tuple):
                return int(result[0] or 0)
            return int(result or 0)

        print("yt-dlp is installed, but no supported CLI entry point was found.", file=sys.stderr)
        return 1
    except SystemExit as exc:
        return int(exc.code or 0) if isinstance(exc.code, int) else 1
    except Exception as exc:
        print(f"yt-dlp failed to start: {exc}", file=sys.stderr)
        return 1
    finally:
        sys.argv = old_argv


def main():
    global SERVER
    load_history()

    if "--run-yt-dlp" in sys.argv:
        idx = sys.argv.index("--run-yt-dlp")
        raise SystemExit(run_yt_dlp_cli(sys.argv[idx + 1:]))

    parser = argparse.ArgumentParser(description="Run the ClipTap local manager.")
    parser.add_argument("--open", action="store_true", help="Open the manager UI in the default browser.")
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser window automatically.")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    cleanup_output_temporary_files()
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
