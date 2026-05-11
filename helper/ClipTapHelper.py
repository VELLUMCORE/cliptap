"""ClipTap standalone local manager."""
from __future__ import annotations

import json, os, queue, re, shutil, subprocess, sys, tempfile, threading, time, uuid, webbrowser
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
ACTIVE_STATES = {"queued", "reading", "downloading", "processing"}
DONE_STATES = {"completed", "failed", "cancelled", "stopped"}

INDEX_HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ClipTap Helper</title><link rel="stylesheet" href="/manager.css"></head><body><div class="shell"><aside><h1>ClipTap Helper</h1><p>Local helper for ClipTap downloads</p><nav><button class="nav active" data-page="dashboard">Dashboard</button><button class="nav" data-page="queue">Queue</button><button class="nav" data-page="history">History</button><button class="nav" data-page="logs">Logs</button></nav><div class="note">The browser extension sends requests here automatically.</div><footer>Version <b id="version">—</b></footer></aside><main><header><span></span><b class="running">● Running</b></header><section id="dashboard" class="page active"><div class="cards"><article><h2>Server Status</h2><p>Local address <b>http://127.0.0.1:17723</b></p><p>Requests today <b id="requests">0</b></p><button id="openOutput">Open Download Folder</button><button id="copyAddress">Copy Address</button></article><article><h2>Dependencies</h2><p>yt-dlp <b id="yt">Checking</b></p><p>FFmpeg <b id="ffmpeg">Checking</b></p><button id="refreshDeps">Check Again</button></article></div><article class="wide"><div class="head"><h2>Active Download Queue (<span id="active">0</span>)</h2><div><button id="stopAll">Stop All</button><button id="cancelAll">Cancel All</button></div></div><div id="jobs"></div><div class="foot"><span id="summary">Showing 0 downloads</span><button id="clearCompleted">Clear Completed</button></div></article></section><section id="queue" class="page"><article class="wide"><div class="head"><h2>Queue</h2><div><button id="stopAll2">Stop All</button><button id="cancelAll2">Cancel All</button></div></div><div id="jobs2"></div><div class="foot"><span id="summary2">Showing 0 downloads</span><button id="clearCompleted2">Clear Completed</button></div></article></section><section id="history" class="page"><article class="wide"><div class="head"><h2>Download History</h2><button id="refreshHistory">Refresh</button></div><div id="historyRows"></div></article></section><section id="logs" class="page"><article class="wide"><div class="head"><h2>Recent Logs</h2><button id="clearLogs">Clear</button></div><pre id="logOutput"></pre></article></section></main></div><script src="/manager.js"></script></body></html>"""

MANAGER_CSS = """:root{color-scheme:dark;--line:#253247;--text:#eef3fb;--muted:#9aa8ba;--blue:#756dff;--green:#41d878;--orange:#ffae2a;--red:#ff6b78}*{box-sizing:border-box}body{margin:0;height:100vh;overflow:hidden;color:var(--text);font:13px/1.45 Segoe UI,system-ui,sans-serif;background:linear-gradient(180deg,#0b1322,#070d19)}button{height:32px;border:1px solid #2a374c;border-radius:5px;background:#101929;color:#f0f4fb;padding:0 12px;cursor:pointer;font-weight:700}button:hover{background:#162236}.shell{height:100vh;display:grid;grid-template-columns:260px 1fr}aside{padding:22px 16px;background:linear-gradient(180deg,rgba(16,19,42,.55),rgba(7,13,25,.2));border-right:1px solid rgba(93,106,140,.2);display:flex;flex-direction:column;gap:18px}h1{margin:0;font-size:22px}aside p,.note{margin:0;color:var(--muted)}nav{display:grid;gap:6px}.nav{text-align:left;border-color:transparent;background:transparent}.nav.active{background:linear-gradient(90deg,rgba(117,109,255,.35),rgba(117,109,255,.14));border-left:3px solid var(--blue)}footer{margin-top:auto;color:#ccd5e5}main{height:100vh;overflow:auto;padding:22px 28px}header{display:flex;justify-content:space-between;margin-bottom:20px}.running{color:var(--green)}.page{display:none}.page.active{display:block}.cards{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}article{padding:14px 16px;border:1px solid var(--line);border-radius:5px;background:linear-gradient(180deg,rgba(16,25,40,.93),rgba(9,15,26,.96))}h2{margin:0 0 12px;font-size:13px;text-transform:uppercase;letter-spacing:.03em}.head,.foot{display:flex;align-items:center;justify-content:space-between;gap:12px}.foot{margin-top:12px;color:var(--muted)}#jobs,#jobs2,#historyRows{display:grid;gap:8px}.row{display:grid;grid-template-columns:32px minmax(180px,1fr) 82px 82px 140px 118px;gap:10px;align-items:center;min-height:52px;padding:8px 10px;border:1px solid rgba(150,164,190,.14);border-radius:5px;background:rgba(255,255,255,.025)}.hist{grid-template-columns:minmax(200px,1fr) 90px 90px 160px}.title{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:750}.muted{color:var(--muted);font-size:12px}.bar{height:8px;border-radius:999px;background:#263248;overflow:hidden}.bar b{display:block;height:100%;width:0;background:linear-gradient(90deg,#756dff,#41d878)}.status{font-weight:750}.completed{color:var(--green)}.failed,.cancelled{color:var(--red)}.stopped{color:var(--orange)}.actions{display:flex;gap:6px;justify-content:flex-end}.actions button{height:28px;padding:0 8px;font-size:11px}.danger{border-color:rgba(255,107,120,.38);color:#ffd7dc}.warn{border-color:rgba(255,174,42,.42);color:#ffe2af}.empty{padding:20px;border:1px dashed rgba(150,164,190,.2);border-radius:5px;color:var(--muted);text-align:center}pre{height:420px;overflow:auto;margin:0;white-space:pre-wrap;color:#cfd7e8;background:#080d18;border:1px solid rgba(150,164,190,.14);border-radius:5px;padding:12px}@media(max-width:900px){.shell{grid-template-columns:1fr}.cards,.row{grid-template-columns:1fr}body{overflow:auto}.shell,main{height:auto}}"""

MANAGER_JS = """const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];let S={jobs:[],history:[],logs:[]};function esc(s){return String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]))}async function api(p,o={}){const r=await fetch(p,{headers:{'Content-Type':'application/json'},...o}),d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.error||r.statusText);return d}function pct(n){return `${Math.max(0,Math.min(100,Number(n)||0)).toFixed(0)}%`}function jobRow(j,i){const active=['queued','reading','downloading','processing'].includes(j.status);return `<div class="row"><div>${i+1}</div><div><div class="title" title="${esc(j.title)}">${esc(j.title||'Untitled')}</div><div class="muted">${esc(j.url||'')}</div></div><div>${esc(j.platform||'YouTube')}</div><div>${esc(j.format||j.mode||'video')}</div><div><div class="bar"><b style="width:${pct(j.progress)}"></b></div><div class="muted">${pct(j.progress)}</div></div><div><div class="status ${esc(j.status)}">${esc(j.statusLabel||j.status)}</div><div class="actions">${active?`<button class="warn" data-stop="${j.id}">Stop</button><button class="danger" data-cancel="${j.id}">Cancel</button>`:''}</div></div></div>`}function render(){const html=S.jobs.length?S.jobs.map(jobRow).join(''):`<div class="empty">No downloads in the queue.</div>`;$('#jobs').innerHTML=html;$('#jobs2').innerHTML=html;const active=S.jobs.filter(j=>['queued','reading','downloading','processing'].includes(j.status)).length;$('#active').textContent=active;$('#summary').textContent=`Showing ${S.jobs.length} downloads`;$('#summary2').textContent=`Showing ${S.jobs.length} downloads`;$('#historyRows').innerHTML=S.history.length?S.history.map(h=>`<div class="row hist"><div><div class="title">${esc(h.title||'Untitled')}</div><div class="muted">${esc(h.url||'')}</div></div><div>${esc(h.mode||'video')}</div><div class="status ${esc(h.status)}">${esc(h.status)}</div><div class="muted">${esc(h.finishedAt||h.createdAt||'')}</div></div>`).join(''):`<div class="empty">No saved history yet.</div>`;$('#logOutput').textContent=(S.logs||[]).join('\n');$('#version').textContent=S.version||'—';$('#requests').textContent=S.requestsToday??0;$('#yt').textContent=S.ytDlp||'Unknown';$('#ffmpeg').textContent=S.ffmpeg||'Unknown'}async function refresh(){try{S=await api('/api/status');render()}catch(e){console.error(e)}}async function post(p){try{await api(p,{method:'POST'});await refresh()}catch(e){alert(e.message)}}document.addEventListener('click',e=>{const nav=e.target.closest('.nav');if(nav){$$('.nav').forEach(n=>n.classList.toggle('active',n===nav));$$('.page').forEach(p=>p.classList.toggle('active',p.id===nav.dataset.page));return}const s=e.target.closest('[data-stop]');if(s)return post(`/api/jobs/${s.dataset.stop}/stop`);const c=e.target.closest('[data-cancel]');if(c)return post(`/api/jobs/${c.dataset.cancel}/cancel`)});$('#stopAll').onclick=$('#stopAll2').onclick=()=>post('/api/stop-all');$('#cancelAll').onclick=$('#cancelAll2').onclick=()=>post('/api/cancel-all');$('#clearCompleted').onclick=$('#clearCompleted2').onclick=()=>post('/api/clear-completed');$('#clearLogs').onclick=()=>post('/api/clear-logs');$('#refreshHistory').onclick=$('#refreshDeps').onclick=refresh;$('#copyAddress').onclick=()=>navigator.clipboard?.writeText('http://127.0.0.1:17723');$('#openOutput').onclick=()=>post('/api/open-output');refresh();setInterval(refresh,1000);"""

@dataclass
class DownloadJob:
    id: str
    payload: dict
    title: str
    url: str
    mode: str
    status: str = "queued"
    status_label: str = "Queued"
    progress: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    output: str = ""
    error: str = ""
    process: subprocess.Popen | None = None
    cancel_requested: bool = False
    stop_requested: bool = False
    history_saved: bool = False
    def to_dict(self):
        return {"id": self.id, "title": self.title, "url": self.url, "mode": self.mode, "format": self.payload.get("quality") or self.mode, "platform": "YouTube" if "youtu" in self.url.lower() else "Web", "status": self.status, "statusLabel": self.status_label, "progress": round(self.progress, 1), "createdAt": fmt_time(self.created_at), "finishedAt": fmt_time(self.finished_at), "output": self.output, "error": self.error}

jobs: dict[str, DownloadJob] = {}
lock = threading.RLock()
work_queue: queue.Queue[str] = queue.Queue()
logs: list[str] = []
history: list[dict] = []
requests_today = 0

def fmt_time(value):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(value)) if value else ""
def log(message):
    line = f"[{time.strftime('%H:%M:%S')}] {message}"
    with lock:
        logs.append(line); del logs[:-300]
    print(line, flush=True)
def ensure_dirs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True); TEMP_ROOT.mkdir(parents=True, exist_ok=True); DATA_DIR.mkdir(parents=True, exist_ok=True)
def load_history():
    global history
    try:
        if HISTORY_FILE.exists(): history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))[-500:]
    except Exception as exc:
        log(f"Could not load history: {exc}"); history = []
def save_history():
    try:
        ensure_dirs(); HISTORY_FILE.write_text(json.dumps(history[-500:], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        log(f"Could not save history: {exc}")
def add_history(job):
    if job.history_saved: return
    job.history_saved = True; item = job.to_dict(); item["finishedAt"] = fmt_time(job.finished_at or time.time()); history.insert(0, item); del history[500:]; save_history()
def ytdlp_base():
    local = LOCAL_BIN_DIR / ("yt-dlp.exe" if os.name == "nt" else "yt-dlp")
    if local.exists(): return [str(local)]
    found = shutil.which("yt-dlp")
    if found: return [found]
    if shutil.which("py"): return ["py", "-m", "yt_dlp"]
    return [sys.executable, "-m", "yt_dlp"]
def ffmpeg_path():
    local = LOCAL_BIN_DIR / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    return str(local) if local.exists() else shutil.which("ffmpeg")
def safe_name(text):
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text or "ClipTap"); text = re.sub(r"\s+", " ", text).strip(" ."); return (text or "ClipTap")[:150]
def set_status(job, status, label, progress=None):
    with lock:
        job.status = status; job.status_label = label; job.updated_at = time.time()
        if progress is not None: job.progress = progress
def finish(job, status, label, progress=None, error=""):
    with lock:
        job.status = status; job.status_label = label; job.error = error; job.finished_at = time.time(); job.updated_at = job.finished_at
        if progress is not None: job.progress = progress
        add_history(job)
def terminate(proc):
    if not proc or proc.poll() is not None: return
    try: proc.terminate(); time.sleep(.4)
    except Exception: pass
    if proc.poll() is None:
        try: proc.kill()
        except Exception: pass
def parse_progress(job, line, base=15, span=65):
    match = re.search(r"(\d+(?:\.\d+)?)%", line)
    if match:
        job.progress = max(job.progress, min(99, base + float(match.group(1)) * span / 100)); job.updated_at = time.time()
def run_command(job, command, base=15, span=65):
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
    job.process = proc; output = []
    try:
        for line in proc.stdout or []:
            output.append(line); parse_progress(job, line, base, span)
            if line.strip(): log(f"{job.id}: {line.strip()[:200]}")
            if job.cancel_requested or job.stop_requested: terminate(proc); break
        return proc.wait(timeout=5), "".join(output)
    finally:
        job.process = None
def read_metadata(job):
    set_status(job, "reading", "Reading info...", 5)
    command = ytdlp_base() + ["-J", "--no-warnings", "--skip-download", "--no-playlist"]
    if job.payload.get("cookieBrowser"): command += ["--cookies-from-browser", job.payload["cookieBrowser"]]
    command.append(job.url); code, output = run_command(job, command, 5, 5)
    if job.cancel_requested: raise RuntimeError("cancelled")
    if job.stop_requested: raise RuntimeError("stopped")
    if code: raise RuntimeError(output.strip()[-600:] or "yt-dlp metadata read failed")
    return json.loads(output)
def process_job(job):
    try:
        ensure_dirs(); meta = read_metadata(job); job.title = meta.get("title") or job.title or "ClipTap download"; base = safe_name(job.title)
        if job.mode == "section":
            start, end = float(job.payload.get("start", 0)), float(job.payload.get("end", 0))
            if end <= start: raise RuntimeError("Invalid selected range")
            tmp = TEMP_ROOT / job.id; tmp.mkdir(parents=True, exist_ok=True); source_pattern = str(tmp / "source.%(ext)s")
            set_status(job, "downloading", "Downloading source...", 15)
            command = ytdlp_base() + ["--no-playlist", "--newline", "-f", "bv*+ba/b", "-o", source_pattern, job.url]
            if job.payload.get("cookieBrowser"): command[1:1] = ["--cookies-from-browser", job.payload["cookieBrowser"]]
            code, output = run_command(job, command, 15, 65)
            if job.cancel_requested: return finish(job, "cancelled", "Cancelled", error="Cancelled by user")
            if job.stop_requested: return finish(job, "stopped", "Stopped", error="Stopped by user")
            if code: raise RuntimeError(output.strip()[-600:] or "yt-dlp download failed")
            files = [p for p in tmp.iterdir() if p.is_file()]
            if not files: raise RuntimeError("Downloaded source file was not found")
            ffmpeg = ffmpeg_path()
            if not ffmpeg: raise RuntimeError("FFmpeg is not installed")
            out_file = OUTPUT_DIR / f"{base} [{start:.2f}-{end:.2f}].mp4"; set_status(job, "processing", "Cutting section...", 82)
            code, output = run_command(job, [ffmpeg, "-y", "-ss", str(start), "-to", str(end), "-i", str(max(files, key=lambda p: p.stat().st_size)), "-c", "copy", str(out_file)], 82, 17)
            if job.cancel_requested: return finish(job, "cancelled", "Cancelled", error="Cancelled by user")
            if job.stop_requested: return finish(job, "stopped", "Stopped", error="Stopped by user")
            if code: raise RuntimeError(output.strip()[-600:] or "FFmpeg section cut failed")
            job.output = str(out_file); shutil.rmtree(tmp, ignore_errors=True); finish(job, "completed", "Completed", 100)
        else:
            set_status(job, "downloading", "Downloading...", 15)
            command = ytdlp_base() + ["--no-playlist", "--newline", "-f", "bv*+ba/b", "-o", str(OUTPUT_DIR / f"{base}.%(ext)s"), job.url]
            if job.payload.get("cookieBrowser"): command[1:1] = ["--cookies-from-browser", job.payload["cookieBrowser"]]
            code, output = run_command(job, command, 15, 80)
            if job.cancel_requested: return finish(job, "cancelled", "Cancelled", error="Cancelled by user")
            if job.stop_requested: return finish(job, "stopped", "Stopped", error="Stopped by user")
            if code: raise RuntimeError(output.strip()[-600:] or "yt-dlp download failed")
            finish(job, "completed", "Completed", 100)
    except Exception as exc:
        if str(exc) == "cancelled": finish(job, "cancelled", "Cancelled", error="Cancelled by user")
        elif str(exc) == "stopped": finish(job, "stopped", "Stopped", error="Stopped by user")
        else: finish(job, "failed", "Failed", error=str(exc)); log(f"{job.id}: failed: {exc}")
def worker_loop():
    while True:
        job_id = work_queue.get(); job = jobs.get(job_id)
        if job:
            if job.cancel_requested: finish(job, "cancelled", "Cancelled", error="Cancelled by user")
            elif job.stop_requested: finish(job, "stopped", "Stopped", error="Stopped by user")
            else: process_job(job)
        work_queue.task_done()
def list_jobs():
    with lock: return [job.to_dict() for job in sorted(jobs.values(), key=lambda item: item.created_at, reverse=True)]
def dep_state(command):
    try: subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=8); return "Ready"
    except Exception: return "Missing"
def status_payload(): return {"version": APP_VERSION, "requestsToday": requests_today, "ytDlp": dep_state(ytdlp_base() + ["--version"]), "ffmpeg": "Ready" if ffmpeg_path() else "Missing", "jobs": list_jobs(), "history": history, "logs": list(logs)}
def control_job(job_id, action):
    with lock:
        job = jobs.get(job_id)
        if not job: raise RuntimeError("Job not found")
        if job.status not in ACTIVE_STATES: return
        if action == "cancel": job.cancel_requested = True; job.status_label = "Cancelling..."
        else: job.stop_requested = True; job.status_label = "Stopping..."
        proc = job.process
    terminate(proc)
def control_all(action):
    for job_id in [job.id for job in list(jobs.values()) if job.status in ACTIVE_STATES]: control_job(job_id, action)
def clear_completed():
    with lock:
        for job_id in [key for key, job in jobs.items() if job.status in DONE_STATES]: jobs.pop(job_id, None)
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def send_body(self, code=200, body="", ctype="text/plain; charset=utf-8"):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Access-Control-Allow-Headers", "Content-Type"); self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS"); self.end_headers(); self.wfile.write(body.encode("utf-8") if isinstance(body, str) else body)
    def send_json(self, data, code=200): self.send_body(code, json.dumps(data, ensure_ascii=False), "application/json; charset=utf-8")
    def read_json(self):
        length = int(self.headers.get("Content-Length", "0") or 0); return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
    def do_OPTIONS(self): self.send_body(204)
    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"): return self.send_body(200, INDEX_HTML, "text/html; charset=utf-8")
        if path == "/manager.css": return self.send_body(200, MANAGER_CSS, "text/css; charset=utf-8")
        if path == "/manager.js": return self.send_body(200, MANAGER_JS, "application/javascript; charset=utf-8")
        if path == "/health": return self.send_json({"ok": True, "version": APP_VERSION})
        if path == "/api/status": return self.send_json(status_payload())
        if path == "/api/jobs": return self.send_json({"jobs": list_jobs()})
        if path == "/api/history": return self.send_json({"history": history})
        return self.send_json({"error": "Not found"}, 404)
    def do_POST(self):
        global requests_today
        path = urlparse(self.path).path
        try:
            if path == "/download":
                payload = self.read_json(); url = payload.get("url")
                if not url: return self.send_json({"error": "Missing URL"}, 400)
                job = DownloadJob(str(uuid.uuid4())[:8], payload, payload.get("title") or "Reading info...", url, payload.get("mode") or "section")
                with lock: jobs[job.id] = job; requests_today += 1
                work_queue.put(job.id); log(f"Queued {job.mode} download {job.id}"); return self.send_json({"ok": True, "jobId": job.id})
            if path == "/api/cancel-all": control_all("cancel"); return self.send_json({"ok": True})
            if path == "/api/stop-all": control_all("stop"); return self.send_json({"ok": True})
            if path == "/api/clear-completed": clear_completed(); return self.send_json({"ok": True})
            if path == "/api/clear-logs": logs.clear(); return self.send_json({"ok": True})
            match = re.match(r"^/api/jobs/([^/]+)/(cancel|stop)$", path)
            if match: control_job(match.group(1), match.group(2)); return self.send_json({"ok": True})
            return self.send_json({"error": "Not found"}, 404)
        except Exception as exc:
            log(f"Request failed: {exc}"); return self.send_json({"error": str(exc)}, 500)
def main():
    ensure_dirs(); load_history(); threading.Thread(target=worker_loop, daemon=True).start(); server = ThreadingHTTPServer((HOST, PORT), Handler); log(f"{APP_NAME} {APP_VERSION} running at http://{HOST}:{PORT}")
    if "--no-browser" not in sys.argv: threading.Timer(.4, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    server.serve_forever()
if __name__ == "__main__": main()
