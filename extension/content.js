(() => {
  if (window.__cliptapLoaded) return;
  window.__cliptapLoaded = true;

  const state = {
    start: null,
    end: null,
    quality: 'best',
    cookieBrowser: '',
    forceKeyframes: false,
    panelOpen: false,
    dragging: null,
    lastVideoKey: ''
  };

  const MIN_GAP_SECONDS = 0.05;
  const RENDER_MIN_INTERVAL_MS = 300;
  let renderTimer = null;
  let lastRenderAt = 0;


  function getVideo() {
    const videos = [...document.querySelectorAll('video')];
    return videos.find(v => Number.isFinite(v.duration) && v.duration > 0) || videos[0] || null;
  }

  function getPlayer() {
    return document.querySelector('#movie_player.html5-video-player') ||
      document.querySelector('.html5-video-player') ||
      getVideo()?.closest('.html5-video-player') ||
      null;
  }

  function getRightControls() {
    return document.querySelector('.ytp-right-controls');
  }

  function getProgressBar() {
    return document.querySelector('.ytp-progress-bar');
  }

  function getVideoKey() {
    const url = new URL(location.href);
    return url.searchParams.get('v') || getVideo()?.currentSrc || location.href;
  }

  function getTitle() {
    const titleEl = document.querySelector('h1.ytd-watch-metadata yt-formatted-string') ||
      document.querySelector('h1.title') ||
      document.querySelector('title');
    return (titleEl?.textContent || document.title || '').replace(/ - YouTube$/, '').trim();
  }

  function secondsToClock(value) {
    const total = Math.max(0, Number(value) || 0);
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const seconds = Math.floor(total % 60);
    return [hours, minutes, seconds].map(n => String(n).padStart(2, '0')).join(':');
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function getDuration() {
    const duration = getVideo()?.duration;
    return Number.isFinite(duration) && duration > 0 ? duration : 0;
  }

  function ensureStyle() {
    if (document.getElementById('cliptap-style')) return;

    const style = document.createElement('style');
    style.id = 'cliptap-style';
    style.textContent = `
      .cliptap-control-button.ytp-button {
        position: relative;
        display: inline-flex !important;
        align-items: center;
        justify-content: center;
        color: #fff;
        opacity: .95;
      }
      .cliptap-control-button.ytp-button:hover,
      .cliptap-control-button.cliptap-active {
        opacity: 1;
      }
      .cliptap-control-button img {
        width: 24px;
        height: 24px;
        object-fit: contain;
        pointer-events: none;
        display: block;
      }
      .cliptap-control-button.cliptap-active::after {
        content: '';
        position: absolute;
        left: 50%;
        bottom: 7px;
        width: 4px;
        height: 4px;
        border-radius: 50%;
        transform: translateX(-50%);
        background: #fff;
      }
      #cliptap-player-panel {
        position: absolute;
        right: 12px;
        bottom: 92px;
        z-index: 84;
        width: 276px;
        color: #fff;
        background: rgba(28, 28, 28, .96);
        border: 1px solid rgba(255, 255, 255, .16);
        border-radius: 4px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, .35);
        font: 12px/1.35 Arial, Helvetica, sans-serif;
        padding: 10px;
      }
      #cliptap-player-panel[hidden] {
        display: none !important;
      }
      #cliptap-player-panel .cliptap-panel-title {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-weight: 700;
        margin-bottom: 8px;
      }
      #cliptap-player-panel .cliptap-close {
        width: 24px;
        height: 24px;
        color: #fff;
        background: transparent;
        border: 0;
        border-radius: 2px;
        cursor: pointer;
        font-size: 17px;
        line-height: 1;
      }
      #cliptap-player-panel .cliptap-close:hover {
        background: rgba(255, 255, 255, .12);
      }
      #cliptap-player-panel .cliptap-time-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 6px;
        margin-bottom: 8px;
      }
      #cliptap-player-panel .cliptap-time-box {
        border: 1px solid rgba(255, 255, 255, .16);
        border-radius: 4px;
        padding: 6px;
        background: rgba(255, 255, 255, .06);
      }
      #cliptap-player-panel .cliptap-time-box span {
        display: block;
        color: rgba(255, 255, 255, .68);
        font-size: 11px;
        margin-bottom: 2px;
      }
      #cliptap-player-panel .cliptap-time-box strong {
        font-size: 13px;
        font-weight: 700;
      }
      #cliptap-player-panel .cliptap-buttons,
      #cliptap-player-panel .cliptap-download-buttons {
        display: grid;
        gap: 6px;
      }
      #cliptap-player-panel .cliptap-buttons {
        grid-template-columns: 1fr 1fr;
        margin-bottom: 6px;
      }
      #cliptap-player-panel .cliptap-download-buttons {
        grid-template-columns: 1fr 1fr;
      }
      #cliptap-player-panel .cliptap-buttons button,
      #cliptap-player-panel .cliptap-download-buttons button {
        min-height: 30px;
        border-radius: 4px;
        border: 1px solid rgba(255, 255, 255, .18);
        background: rgba(255, 255, 255, .10);
        color: #fff;
        font: inherit;
        cursor: pointer;
      }
      #cliptap-player-panel .cliptap-buttons button:hover,
      #cliptap-player-panel .cliptap-download-buttons button:hover {
        background: rgba(255, 255, 255, .18);
      }
      #cliptap-player-panel .cliptap-download-buttons button[data-action="download-section"],
      #cliptap-player-panel .cliptap-download-buttons button[data-action="download-full"] {
        background: #e5e5e5;
        color: #111;
        border-color: #e5e5e5;
        font-weight: 700;
      }
      #cliptap-player-panel .cliptap-download-buttons button[data-action="download-full"] {
        background: #f7f7f7;
      }
      #cliptap-player-panel .cliptap-message {
        min-height: 16px;
        margin-top: 7px;
        color: rgba(255, 255, 255, .70);
        font-size: 11px;
      }
      .ytp-progress-bar {
        position: relative !important;
      }
      #cliptap-progress-overlay {
        position: absolute;
        left: 0;
        right: 0;
        top: 0;
        bottom: 0;
        z-index: 41;
        pointer-events: none;
      }
      #cliptap-progress-overlay .cliptap-range-fill {
        position: absolute;
        top: 50%;
        height: 5px;
        border-radius: 999px;
        transform: translateY(-50%);
        background: rgba(255, 255, 255, .45);
        box-shadow: 0 0 0 1px rgba(0, 0, 0, .35);
        pointer-events: none;
      }
      #cliptap-progress-overlay .cliptap-handle {
        position: absolute;
        top: 50%;
        width: 13px;
        height: 22px;
        border-radius: 2px;
        transform: translate(-50%, -50%);
        background: #fff;
        border: 1px solid rgba(0, 0, 0, .55);
        box-shadow: 0 1px 4px rgba(0, 0, 0, .45);
        cursor: ew-resize;
        pointer-events: auto;
      }
      #cliptap-progress-overlay .cliptap-handle::after {
        content: attr(data-label);
        position: absolute;
        left: 50%;
        bottom: 24px;
        transform: translateX(-50%);
        min-width: 34px;
        padding: 2px 5px;
        border-radius: 3px;
        color: #111;
        background: #fff;
        font: 10px/1.2 Arial, Helvetica, sans-serif;
        text-align: center;
        opacity: 0;
        transition: opacity .12s ease;
        pointer-events: none;
      }
      #cliptap-progress-overlay .cliptap-handle:hover::after,
      #cliptap-progress-overlay .cliptap-handle.cliptap-dragging::after {
        opacity: 1;
      }
      #cliptap-progress-overlay .cliptap-handle[data-kind="start"] {
        border-bottom: 4px solid #35a7ff;
      }
      #cliptap-progress-overlay .cliptap-handle[data-kind="end"] {
        border-bottom: 4px solid #ffcc33;
      }
    `;
    document.documentElement.appendChild(style);
  }

  function ensureControlButton() {
    const controls = getRightControls();
    if (!controls) return;

    let button = document.getElementById('cliptap-control-button');
    if (!button) {
      button = document.createElement('button');
      button.id = 'cliptap-control-button';
      button.className = 'ytp-button cliptap-control-button';
      button.type = 'button';
      button.title = 'ClipTap 구간 다운로드';
      button.setAttribute('aria-label', 'ClipTap 구간 다운로드');
      const iconUrl = chrome.runtime.getURL('icons/cliptap.png');
      button.innerHTML = `<img src="${iconUrl}" alt="" aria-hidden="true">`;
      button.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        state.panelOpen = !state.panelOpen;
        render();
      });
    }

    if (button.parentElement !== controls) {
      controls.insertBefore(button, controls.firstElementChild);
    }
  }

  function ensurePanel() {
    const player = getPlayer();
    if (!player) return;

    let panel = document.getElementById('cliptap-player-panel');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'cliptap-player-panel';
      panel.innerHTML = `
        <div class="cliptap-panel-title">
          <span>ClipTap</span>
          <button type="button" class="cliptap-close" data-action="close" aria-label="닫기">×</button>
        </div>
        <div class="cliptap-time-grid">
          <div class="cliptap-time-box">
            <span>시작</span>
            <strong data-role="start">--:--:--</strong>
          </div>
          <div class="cliptap-time-box">
            <span>끝</span>
            <strong data-role="end">--:--:--</strong>
          </div>
        </div>
        <div class="cliptap-buttons">
          <button type="button" data-action="start">시작 찍기</button>
          <button type="button" data-action="end">끝 찍기</button>
        </div>
        <div class="cliptap-download-buttons">
          <button type="button" data-action="download-section">구간 받기</button>
          <button type="button" data-action="download-full">전체 다운로드</button>
        </div>
        <div class="cliptap-message" data-role="message">진행바의 흰 손잡이를 드래그해도 돼.</div>
      `;
      panel.addEventListener('click', handlePanelClick);
    }

    if (panel.parentElement !== player) {
      player.appendChild(panel);
    }
  }

  function ensureProgressOverlay() {
    const progressBar = getProgressBar();
    if (!progressBar) return;

    let overlay = document.getElementById('cliptap-progress-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'cliptap-progress-overlay';
      overlay.innerHTML = `
        <div class="cliptap-range-fill" data-role="range"></div>
        <div class="cliptap-handle" data-kind="start" data-label="시작" role="slider" aria-label="ClipTap 시작 지점" tabindex="0"></div>
        <div class="cliptap-handle" data-kind="end" data-label="끝" role="slider" aria-label="ClipTap 끝 지점" tabindex="0"></div>
      `;
      overlay.addEventListener('pointerdown', handleDragStart, true);
      overlay.addEventListener('keydown', handleHandleKeydown, true);
    }

    if (overlay.parentElement !== progressBar) {
      progressBar.appendChild(overlay);
    }
  }

  function setPanelMessage(text) {
    const el = document.querySelector('#cliptap-player-panel [data-role="message"]');
    if (el) el.textContent = text;
  }

  function setCurrentTime(seconds) {
    const video = getVideo();
    if (!video) return;
    const duration = getDuration();
    video.currentTime = duration ? clamp(seconds, 0, duration) : Math.max(0, seconds);
  }

  function setMarker(kind, seconds, shouldSeek = false) {
    const duration = getDuration();
    const max = duration || Math.max(seconds, state.start || 0, state.end || 0);
    let value = clamp(seconds, 0, max);

    if (kind === 'start') {
      if (state.end != null) value = Math.min(value, Math.max(0, state.end - MIN_GAP_SECONDS));
      state.start = value;
    }
    if (kind === 'end') {
      if (state.start != null) value = Math.max(value, state.start + MIN_GAP_SECONDS);
      state.end = duration ? Math.min(value, duration) : value;
    }

    if (shouldSeek) setCurrentTime(value);
    render();
  }

  function positionToSeconds(clientX) {
    const bar = getProgressBar();
    const duration = getDuration();
    if (!bar || !duration) return 0;
    const rect = bar.getBoundingClientRect();
    const ratio = clamp((clientX - rect.left) / rect.width, 0, 1);
    return ratio * duration;
  }

  function handlePanelClick(event) {
    const action = event.target?.dataset?.action;
    if (!action) return;

    event.preventDefault();
    event.stopPropagation();

    const video = getVideo();
    if (!video) {
      setPanelMessage('video 태그를 못 찾았어.');
      return;
    }

    if (action === 'close') {
      state.panelOpen = false;
      render();
      return;
    }
    if (action === 'start') {
      setMarker('start', video.currentTime, false);
      setPanelMessage('시작 지점 저장됨. 진행바에서 드래그 가능.');
      return;
    }
    if (action === 'end') {
      setMarker('end', video.currentTime, false);
      setPanelMessage('끝 지점 저장됨. 진행바에서 드래그 가능.');
      return;
    }
    if (action === 'download-section') {
      requestDownload('section');
      return;
    }
    if (action === 'download-full') {
      requestDownload('full');
    }
  }

  function handleDragStart(event) {
    const handle = event.target?.closest?.('.cliptap-handle');
    if (!handle) return;

    event.preventDefault();
    event.stopPropagation();

    const kind = handle.dataset.kind;
    state.dragging = kind;
    handle.classList.add('cliptap-dragging');
    setMarker(kind, positionToSeconds(event.clientX), true);

    document.addEventListener('pointermove', handleDragMove, true);
    document.addEventListener('pointerup', handleDragEnd, true);
    document.addEventListener('pointercancel', handleDragEnd, true);
  }

  function handleDragMove(event) {
    if (!state.dragging) return;
    event.preventDefault();
    event.stopPropagation();
    setMarker(state.dragging, positionToSeconds(event.clientX), true);
  }

  function handleDragEnd(event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    document.querySelectorAll('#cliptap-progress-overlay .cliptap-handle').forEach(el => {
      el.classList.remove('cliptap-dragging');
    });
    state.dragging = null;
    document.removeEventListener('pointermove', handleDragMove, true);
    document.removeEventListener('pointerup', handleDragEnd, true);
    document.removeEventListener('pointercancel', handleDragEnd, true);
  }

  function handleHandleKeydown(event) {
    const handle = event.target?.closest?.('.cliptap-handle');
    if (!handle) return;

    const kind = handle.dataset.kind;
    const current = kind === 'start' ? state.start : state.end;
    if (current == null) return;

    const step = event.shiftKey ? 5 : 1;
    let next = current;
    if (event.key === 'ArrowLeft') next -= step;
    else if (event.key === 'ArrowRight') next += step;
    else return;

    event.preventDefault();
    event.stopPropagation();
    setMarker(kind, next, true);
  }

  async function requestDownload(mode = 'section') {
    const payload = {
      mode,
      url: location.href,
      title: getTitle(),
      quality: state.quality,
      cookieBrowser: state.cookieBrowser,
      forceKeyframes: state.forceKeyframes
    };

    if (mode === 'section') {
      if (state.start == null || state.end == null) {
        setPanelMessage('시작/끝을 먼저 찍어줘.');
        return;
      }
      if (state.end <= state.start) {
        setPanelMessage('끝이 시작보다 뒤여야 해.');
        return;
      }
      payload.start = state.start;
      payload.end = state.end;
    }

    try {
      setPanelMessage(mode === 'full' ? '전체 다운로드 요청 보내는 중...' : '구간 다운로드 요청 보내는 중...');
      const res = await fetch('http://127.0.0.1:17723/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || '헬퍼 오류');
      setPanelMessage(mode === 'full' ? '전체 다운로드 시작됨.' : '구간 다운로드 시작됨.');
    } catch (error) {
      setPanelMessage('헬퍼가 꺼졌거나 오류가 났어.');
      console.error('[ClipTap]', error);
    }
  }

  function resetForNewVideoIfNeeded() {
    const key = getVideoKey();
    if (!key || key === state.lastVideoKey) return;
    state.lastVideoKey = key;
    state.start = null;
    state.end = null;
    state.panelOpen = false;
  }

  function renderProgressOverlay() {
    const overlay = document.getElementById('cliptap-progress-overlay');
    if (!overlay) return;

    const duration = getDuration();
    const start = state.start;
    const end = state.end;
    const startHandle = overlay.querySelector('[data-kind="start"]');
    const endHandle = overlay.querySelector('[data-kind="end"]');
    const range = overlay.querySelector('[data-role="range"]');

    const setHandle = (handle, seconds) => {
      const visible = duration > 0 && seconds != null;
      handle.hidden = !visible;
      if (!visible) return;
      const left = clamp(seconds / duration, 0, 1) * 100;
      handle.style.left = `${left}%`;
      handle.setAttribute('aria-valuemin', '0');
      handle.setAttribute('aria-valuemax', String(Math.floor(duration)));
      handle.setAttribute('aria-valuenow', String(Math.floor(seconds)));
      handle.setAttribute('aria-valuetext', secondsToClock(seconds));
    };

    setHandle(startHandle, start);
    setHandle(endHandle, end);

    const rangeVisible = duration > 0 && start != null && end != null && end > start;
    range.hidden = !rangeVisible;
    if (rangeVisible) {
      const left = clamp(start / duration, 0, 1) * 100;
      const right = clamp(end / duration, 0, 1) * 100;
      range.style.left = `${left}%`;
      range.style.width = `${Math.max(0, right - left)}%`;
    }
  }

  function renderPanel() {
    const panel = document.getElementById('cliptap-player-panel');
    if (!panel) return;

    panel.hidden = !state.panelOpen;
    const startEl = panel.querySelector('[data-role="start"]');
    const endEl = panel.querySelector('[data-role="end"]');
    if (startEl) startEl.textContent = state.start == null ? '--:--:--' : secondsToClock(state.start);
    if (endEl) endEl.textContent = state.end == null ? '--:--:--' : secondsToClock(state.end);
  }

  function renderButton() {
    const button = document.getElementById('cliptap-control-button');
    if (!button) return;
    button.classList.toggle('cliptap-active', state.panelOpen || state.start != null || state.end != null);
  }

  function render() {
    resetForNewVideoIfNeeded();
    ensureStyle();
    ensureControlButton();
    ensurePanel();
    ensureProgressOverlay();
    renderButton();
    renderPanel();
    renderProgressOverlay();
  }

  function loadOptions() {
    if (!chrome?.storage?.sync) return;
    chrome.storage.sync.get(['cliptapQuality', 'cliptapCookie', 'cliptapForce'], values => {
      state.quality = values.cliptapQuality || 'best';
      state.cookieBrowser = values.cliptapCookie || '';
      state.forceKeyframes = Boolean(values.cliptapForce);
    });
  }

  if (chrome?.storage?.onChanged) {
    chrome.storage.onChanged.addListener((changes, areaName) => {
      if (areaName !== 'sync') return;
      if (changes.cliptapQuality) state.quality = changes.cliptapQuality.newValue || 'best';
      if (changes.cliptapCookie) state.cookieBrowser = changes.cliptapCookie.newValue || '';
      if (changes.cliptapForce) state.forceKeyframes = Boolean(changes.cliptapForce.newValue);
    });
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== 'CLIPTAP_GET_STATE') return;
    const video = getVideo();
    sendResponse({
      url: location.href,
      title: getTitle(),
      currentTime: video?.currentTime || 0,
      duration: video?.duration || 0,
      start: state.start,
      end: state.end,
      hasVideo: Boolean(video)
    });
    return true;
  });

  function scheduleRender() {
    if (renderTimer) return;

    const now = Date.now();
    const delay = Math.max(0, RENDER_MIN_INTERVAL_MS - (now - lastRenderAt));
    renderTimer = window.setTimeout(() => {
      renderTimer = null;
      lastRenderAt = Date.now();
      render();
    }, delay);
  }

  loadOptions();
  scheduleRender();

  // YouTube mutates a huge amount of DOM while loading/playing.
  // v1.1 rendered on every subtree mutation and could stall the page.
  // Keep discovery lightweight: listen to navigation events, throttle root changes,
  // and do a slow safety tick for controls recreated by YouTube.
  ['yt-navigate-finish', 'ytd-navigate-finish', 'yt-page-data-updated'].forEach(name => {
    window.addEventListener(name, scheduleRender, true);
  });
  window.addEventListener('popstate', scheduleRender, true);
  window.addEventListener('hashchange', scheduleRender, true);

  const observer = new MutationObserver(scheduleRender);
  observer.observe(document.documentElement, { childList: true });
  setInterval(scheduleRender, 1500);
})();
