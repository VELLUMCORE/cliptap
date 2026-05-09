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
    if (!tab || !tab.id) throw new Error('탭을 찾지 못함');
    const response = await chrome.tabs.sendMessage(tab.id, { type: 'CLIPTAP_GET_STATE' });
    activeState = response;
    els.videoTitle.textContent = response.title || '제목 없음';
    els.currentTime.textContent = secondsToClock(response.currentTime || 0);
    setMessage(response.hasVideo ? '' : '이 페이지에서 video 태그를 못 찾았어.');
  } catch (error) {
    activeState = null;
    els.videoTitle.textContent = 'YouTube 영상 페이지에서 열어줘.';
    els.currentTime.textContent = '00:00:00';
    setMessage('현재 탭 정보를 못 읽었어. 페이지 새로고침 후 다시 눌러봐.');
  }
}

async function checkHelper() {
  try {
    const res = await fetch('http://127.0.0.1:17723/health', { method: 'GET' });
    if (!res.ok) throw new Error('bad status');
    els.helperStatus.textContent = '헬퍼 연결됨';
  } catch {
    els.helperStatus.textContent = '헬퍼 꺼짐';
  }
}

function getPayload(mode = 'section') {
  if (!activeState?.url) throw new Error('영상 URL을 못 찾았어.');

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
    if (!Number.isFinite(start) || !Number.isFinite(end)) throw new Error('시작/끝 시간을 확인해줘. 예: 00:01:20');
    if (end <= start) throw new Error('끝 시간이 시작 시간보다 뒤여야 해.');
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
  setMessage(mode === 'full' ? '전체 다운로드 요청 보내는 중...' : '구간 다운로드 요청 보내는 중...');
  const res = await fetch('http://127.0.0.1:17723/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || '헬퍼 오류');
  setMessage(mode === 'full' ? '전체 다운로드 시작됨. helper 창에서 진행률을 볼 수 있어.' : '구간 다운로드 시작됨. helper 창에서 진행률을 볼 수 있어.');
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
    setMessage('명령어 복사됨. PowerShell에 붙여넣으면 돼.');
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
