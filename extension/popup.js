const els = {
  helperStatus: document.getElementById('helperStatus'),
  videoTitle: document.getElementById('videoTitle'),
  currentTime: document.getElementById('currentTime'),
  startInput: document.getElementById('startInput'),
  endInput: document.getElementById('endInput'),
  setStartBtn: document.getElementById('setStartBtn'),
  setEndBtn: document.getElementById('setEndBtn'),
  qualitySelect: document.getElementById('qualitySelect'),
  cookieSelect: document.getElementById('cookieSelect'),
  forceKeyframes: document.getElementById('forceKeyframes'),
  downloadBtn: document.getElementById('downloadBtn'),
  fullDownloadBtn: document.getElementById('fullDownloadBtn'),
  copyBtn: document.getElementById('copyBtn'),
  message: document.getElementById('message')
};

let activeState = null;

function secondsToClock(value) {
  const total = Math.max(0, Number(value) || 0);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = Math.floor(total % 60);
  const ms = Math.round((total - Math.floor(total)) * 1000);
  const base = [hours, minutes, seconds].map(n => String(n).padStart(2, '0')).join(':');
  return ms ? `${base}.${String(ms).padStart(3, '0')}` : base;
}

function clockToSeconds(text) {
  const raw = String(text || '').trim();
  if (!raw) return NaN;
  if (/^\d+(\.\d+)?$/.test(raw)) return Number(raw);
  const parts = raw.split(':').map(Number);
  if (parts.some(Number.isNaN)) return NaN;
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return NaN;
}

function setMessage(text) {
  els.message.textContent = text;
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function refreshState() {
  try {
    const tab = await getActiveTab();
    if (!tab || !tab.id) throw new Error('Could not find the active tab');
    const response = await chrome.tabs.sendMessage(tab.id, { type: 'CLIPTAP_GET_STATE' });
    activeState = response;
    els.videoTitle.textContent = response.title || 'Untitled';
    els.currentTime.textContent = secondsToClock(response.currentTime || 0);
    setMessage(response.hasVideo ? '' : 'Could not find a video element on this page.');
  } catch (error) {
    activeState = null;
    els.videoTitle.textContent = 'Open this on a YouTube video page.';
    els.currentTime.textContent = '00:00:00';
    setMessage('Could not read the current tab. Refresh the page and try again.');
  }
}

async function checkHelper() {
  try {
    const res = await fetch('http://127.0.0.1:17723/health', { method: 'GET' });
    if (!res.ok) throw new Error('bad status');
    els.helperStatus.textContent = 'Helper connected';
  } catch {
    els.helperStatus.textContent = 'Helper off';
  }
}

function getPayload(mode = 'section') {
  if (!activeState?.url) throw new Error('Could not find the video URL.');

  const payload = {
    mode,
    url: activeState.url,
    title: activeState.title || '',
    quality: els.qualitySelect.value,
    cookieBrowser: els.cookieSelect.value,
    forceKeyframes: els.forceKeyframes.checked
  };

  if (mode === 'section') {
    const start = clockToSeconds(els.startInput.value);
    const end = clockToSeconds(els.endInput.value);
    if (!Number.isFinite(start) || !Number.isFinite(end)) throw new Error('Check the start/end time. Example: 00:01:20');
    if (end <= start) throw new Error('The end time must be after the start time.');
    payload.start = start;
    payload.end = end;
  }

  return payload;
}

function buildCommand(payload) {
  const isFull = payload.mode === 'full';
  const start = secondsToClock(payload.start);
  const end = secondsToClock(payload.end);
  const formatMap = {
    best: 'bv*+ba/b',
    1080: 'bv*[height<=1080]+ba/b[height<=1080]/b',
    720: 'bv*[height<=720]+ba/b[height<=720]/b',
    audio: 'ba/b'
  };
  const parts = ['yt-dlp'];
  if (payload.quality === 'audio') {
    parts.push('-x', '--audio-format', 'mp3');
  } else {
    parts.push('-f', `"${formatMap[payload.quality] || formatMap.best}"`, '--merge-output-format', 'mp4');
  }
  if (!isFull) {
    parts.push('--download-sections', `"*${start}-${end}"`);
    if (payload.forceKeyframes) parts.push('--force-keyframes-at-cuts');
  }
  if (payload.cookieBrowser) parts.push('--cookies-from-browser', payload.cookieBrowser);
  parts.push('-P', '"%USERPROFILE%\\Downloads\\ClipTap"');
  parts.push(`"${payload.url}"`);
  return parts.join(' ');
}

els.setStartBtn.addEventListener('click', async () => {
  await refreshState();
  if (activeState) els.startInput.value = secondsToClock(activeState.currentTime || 0);
});

els.setEndBtn.addEventListener('click', async () => {
  await refreshState();
  if (activeState) els.endInput.value = secondsToClock(activeState.currentTime || 0);
});

async function sendDownloadRequest(mode) {
  await refreshState();
  const payload = getPayload(mode);
  setMessage(mode === 'full' ? 'Sending full download request...' : 'Sending section download request...');
  const res = await fetch('http://127.0.0.1:17723/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Helper error');
  setMessage(mode === 'full' ? 'Full download started. You can watch progress in the helper window.' : 'Section download started. You can watch progress in the helper window.');
}

els.downloadBtn.addEventListener('click', async () => {
  try {
    await sendDownloadRequest('section');
  } catch (error) {
    setMessage(error.message || String(error));
  }
});

els.fullDownloadBtn.addEventListener('click', async () => {
  try {
    await sendDownloadRequest('full');
  } catch (error) {
    setMessage(error.message || String(error));
  }
});

els.copyBtn.addEventListener('click', async () => {
  try {
    await refreshState();
    const payload = getPayload('section');
    await navigator.clipboard.writeText(buildCommand(payload));
    setMessage('Command copied. Paste it into PowerShell to run it.');
  } catch (error) {
    setMessage(error.message || String(error));
  }
});

chrome.storage.sync.get(['cliptapQuality', 'cliptapCookie', 'cliptapForce'], values => {
  if (values.cliptapQuality) els.qualitySelect.value = values.cliptapQuality;
  if (values.cliptapCookie !== undefined) els.cookieSelect.value = values.cliptapCookie;
  if (values.cliptapForce !== undefined) els.forceKeyframes.checked = Boolean(values.cliptapForce);
});

els.qualitySelect.addEventListener('change', () => chrome.storage.sync.set({ cliptapQuality: els.qualitySelect.value }));
els.cookieSelect.addEventListener('change', () => chrome.storage.sync.set({ cliptapCookie: els.cookieSelect.value }));
els.forceKeyframes.addEventListener('change', () => chrome.storage.sync.set({ cliptapForce: els.forceKeyframes.checked }));

refreshState();
checkHelper();
setInterval(refreshState, 1000);
setInterval(checkHelper, 3000);
