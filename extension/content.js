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
    loopEnabled: false,
    dragging: null,
    lastVideoKey: ''
  };

  const MIN_GAP_SECONDS = 0.05;
  const LOOP_EPSILON_SECONDS = 0.08;
  const RENDER_MIN_INTERVAL_MS = 300;
  let renderTimer = null;
  let lastRenderAt = 0;
  let loopRafId = 0;


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


  function getPlaylistId() {
    try {
      return new URL(location.href).searchParams.get('list') || '';
    } catch {
      return '';
    }
  }

  function isPlaylistPageUrl() {
    return location.pathname === '/playlist' && Boolean(getPlaylistId());
  }

  function isWatchPlaylistUrl() {
    return location.pathname === '/watch' && Boolean(getPlaylistId());
  }

  function getPlaylistUrl() {
    const listId = getPlaylistId();
    if (!listId) return location.href;
    return `https://www.youtube.com/playlist?list=${encodeURIComponent(listId)}`;
  }

  function getPlaylistTitle() {
    const candidates = [
      'ytd-playlist-header-renderer h1 yt-formatted-string',
      'ytd-playlist-header-renderer h1',
      '#playlist-title',
      '#header-description h3',
      '#container h3.ytd-playlist-panel-renderer',
      'h1 yt-formatted-string',
      'h1'
    ];
    for (const selector of candidates) {
      const value = document.querySelector(selector)?.textContent?.trim();
      if (value) return value;
    }
    return getTitle() || 'YouTube playlist';
  }

  function secondsToClock(value, fractionDigits = 2) {
    const total = Math.max(0, Number(value) || 0);
    const scale = 10 ** fractionDigits;
    let whole = Math.floor(total);
    let fraction = Math.round((total - whole) * scale);
    if (fraction >= scale) {
      whole += 1;
      fraction = 0;
    }
    const hours = Math.floor(whole / 3600);
    const minutes = Math.floor((whole % 3600) / 60);
    const seconds = whole % 60;
    const base = [hours, minutes, seconds].map(n => String(n).padStart(2, '0')).join(':');
    return fractionDigits > 0 ? `${base}.${String(fraction).padStart(fractionDigits, '0')}` : base;
  }

  function clockToSeconds(text) {
    const raw = String(text || '').trim().replace(',', '.');
    if (!raw) return NaN;
    if (/^\d+(?:\.\d+)?$/.test(raw)) return Number(raw);

    const parts = raw.split(':');
    if (parts.length < 2 || parts.length > 3) return NaN;
    if (!parts.every(part => /^\d+(?:\.\d+)?$/.test(part))) return NaN;

    const nums = parts.map(Number);
    if (parts.length === 2) return nums[0] * 60 + nums[1];
    return nums[0] * 3600 + nums[1] * 60 + nums[2];
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
        display: inline-flex;
        align-items: center;
        justify-content: center;
        color: #fff;
        opacity: .9;
        padding: 0;
      }
      .cliptap-control-button.ytp-button:hover,
      .cliptap-control-button.cliptap-active {
        opacity: 1;
      }
      .cliptap-control-button .cliptap-player-icon-wrap {
        width: 26px;
        height: 26px;
        min-width: 26px;
        min-height: 26px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        line-height: 0;
        transform: translateY(-0.25px);
        pointer-events: none;
      }
      .cliptap-control-button svg {
        pointer-events: none;
        display: block;
        width: 26px;
        height: 26px;
        min-width: 26px;
        min-height: 26px;
        padding: 0 !important;
        overflow: visible;
      }
      .cliptap-control-button svg path {
        fill: #fff;
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
        bottom: 72px;
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
      #cliptap-player-panel .cliptap-title-actions {
        display: inline-flex;
        align-items: center;
        gap: 2px;
      }
      #cliptap-player-panel .cliptap-loop,
      #cliptap-player-panel .cliptap-close {
        width: 24px;
        height: 24px;
        color: #fff;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 2px;
        cursor: pointer;
        line-height: 1;
      }
      #cliptap-player-panel .cliptap-loop {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0;
      }
      #cliptap-player-panel .cliptap-loop svg {
        width: 16px;
        height: 16px;
        display: block;
        pointer-events: none;
      }
      #cliptap-player-panel .cliptap-loop[aria-pressed="true"] {
        color: #8fc5ff;
        background: rgba(47, 140, 255, .18);
        border-color: rgba(143, 197, 255, .45);
      }
      #cliptap-player-panel .cliptap-close {
        font-size: 17px;
      }
      #cliptap-player-panel .cliptap-loop:hover,
      #cliptap-player-panel .cliptap-close:hover {
        background: rgba(255, 255, 255, .12);
      }
      #cliptap-player-panel .cliptap-loop[aria-pressed="true"]:hover {
        background: rgba(47, 140, 255, .26);
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
      #cliptap-player-panel .cliptap-time-box input {
        width: 100%;
        min-width: 0;
        box-sizing: border-box;
        padding: 2px 3px;
        margin: 0;
        border: 1px solid transparent;
        border-radius: 3px;
        background: transparent;
        color: #fff;
        font: 700 13px/1.25 Arial, Helvetica, sans-serif;
        outline: none;
      }
      #cliptap-player-panel .cliptap-time-box input:focus {
        border-color: rgba(255, 255, 255, .36);
        background: rgba(255, 255, 255, .10);
      }
      #cliptap-player-panel .cliptap-time-box input::placeholder {
        color: rgba(255, 255, 255, .55);
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
        height: 4px;
        border-radius: 999px;
        transform: translateY(-50%);
        background: linear-gradient(90deg, rgba(47, 140, 255, .70), rgba(255, 157, 46, .70));
        box-shadow: 0 0 0 1px rgba(0, 0, 0, .35);
        pointer-events: none;
      }
      #cliptap-progress-overlay .cliptap-handle {
        --cliptap-handle-color: #2f8cff;
        position: absolute;
        top: 50%;
        width: 36px;
        height: 36px;
        border: 0;
        border-radius: 50%;
        transform: translate(-50%, -50%);
        background: transparent;
        box-shadow: none;
        cursor: ew-resize;
        pointer-events: auto;
        touch-action: none;
      }
      #cliptap-progress-overlay .cliptap-handle::before {
        content: '';
        position: absolute;
        left: 50%;
        top: 50%;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        transform: translate(-50%, -50%);
        background: var(--cliptap-handle-color);
        box-shadow: 0 0 0 2px #fff, 0 1px 5px rgba(0, 0, 0, .55);
        transition: transform .08s ease;
      }
      #cliptap-progress-overlay .cliptap-handle:hover::before,
      #cliptap-progress-overlay .cliptap-handle:focus-visible::before,
      #cliptap-progress-overlay .cliptap-handle.cliptap-dragging::before {
        transform: translate(-50%, -50%) scale(1.16);
      }
      #cliptap-progress-overlay .cliptap-handle::after {
        content: attr(data-label);
        position: absolute;
        left: 50%;
        bottom: 31px;
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
      #cliptap-progress-overlay .cliptap-handle:focus-visible::after,
      #cliptap-progress-overlay .cliptap-handle.cliptap-dragging::after {
        opacity: 1;
      }
      #cliptap-progress-overlay .cliptap-handle[data-kind="start"] {
        --cliptap-handle-color: #2f8cff;
      }
      #cliptap-progress-overlay .cliptap-handle[data-kind="end"] {
        --cliptap-handle-color: #ff9d2e;
      }
      .cliptap-playlist-download-button {
        color: #fff !important;
        cursor: pointer !important;
        user-select: none !important;
        -webkit-tap-highlight-color: transparent !important;
      }
      .cliptap-playlist-download-button[hidden] {
        display: none !important;
      }
      .cliptap-playlist-native-button,
      button.cliptap-playlist-native-button,
      div.cliptap-playlist-native-button {
        appearance: none !important;
        -webkit-appearance: none !important;
        position: relative !important;
        box-sizing: border-box !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        flex: 0 0 auto !important;
        width: 40px !important;
        height: 40px !important;
        min-width: 40px !important;
        min-height: 40px !important;
        max-width: 40px !important;
        max-height: 40px !important;
        padding: 8px !important;
        margin: 0 2px !important;
        border: 0 !important;
        border-radius: 50% !important;
        background: transparent !important;
        line-height: 0 !important;
        vertical-align: middle !important;
        overflow: visible !important;
        z-index: 3 !important;
      }
      .cliptap-page-playlist-button.ytFlexibleActionsViewModelActionIconOnlyButton,
      .cliptap-page-playlist-button.ytFlexibleActionsViewModelActionRowAction {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
      }
      .cliptap-playlist-native-button:hover,
      .cliptap-playlist-native-button:focus-visible {
        background-color: rgba(255, 255, 255, .10) !important;
        outline: none !important;
      }
      .cliptap-playlist-native-button:active {
        transform: scale(.96) !important;
      }
      .cliptap-playlist-icon-wrap {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 24px !important;
        height: 24px !important;
        min-width: 24px !important;
        min-height: 24px !important;
        line-height: 0 !important;
        color: #fff !important;
        pointer-events: none !important;
      }
      .cliptap-playlist-icon-wrap svg.cliptap-native-playlist-svg {
        display: inherit !important;
        width: 100% !important;
        height: 100% !important;
        min-width: 24px !important;
        min-height: 24px !important;
        margin: 0 !important;
        pointer-events: none !important;
        overflow: visible !important;
      }
      .cliptap-playlist-icon-wrap svg.cliptap-native-playlist-svg path {
        fill: #fff !important;
        stroke: none !important;
      }
      .cliptap-playlist-download-button.cliptap-sending {
        opacity: .55 !important;
        pointer-events: none !important;
      }
    `;
    document.documentElement.appendChild(style);
  }

  const PLAYER_TOOLBAR_ICON_VERSION = '43';

  function getPlayerToolbarDownloadIcon() {
    return `<span class="cliptap-player-icon-wrap" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" height="26" viewBox="0 0 24 24" width="26" focusable="false" aria-hidden="true" style="pointer-events:none;display:block;width:26px;height:26px;"><path class="ytp-svg-fill" d="M6.25 3A3.25 3.25 0 0 0 3 6.25v3.15a1 1 0 1 0 2 0V6.25C5 5.56 5.56 5 6.25 5H9.4a1 1 0 1 0 0-2H6.25Zm8.35 0a1 1 0 1 0 0 2h3.15c.69 0 1.25.56 1.25 1.25V9.4a1 1 0 1 0 2 0V6.25A3.25 3.25 0 0 0 17.75 3H14.6ZM12 6.5a1 1 0 0 0-1 1v6.09l-1.65-1.64a1 1 0 1 0-1.41 1.41L12 18.41l4.06-4.05a1 1 0 0 0-1.41-1.42L13 14.59V7.5a1 1 0 0 0-1-1ZM4 13.6a1 1 0 0 0-1 1v3.15A3.25 3.25 0 0 0 6.25 21H9.4a1 1 0 1 0 0-2H6.25C5.56 19 5 18.44 5 17.75V14.6a1 1 0 0 0-1-1Zm16 0a1 1 0 0 0-1 1v3.15c0 .69-.56 1.25-1.25 1.25H14.6a1 1 0 1 0 0 2h3.15A3.25 3.25 0 0 0 21 17.75V14.6a1 1 0 0 0-1-1Z"></path></svg></span>`;
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
    }

    button.title = 'ClipTap section downloader';
    button.setAttribute('aria-label', 'ClipTap section downloader');
    button.classList.add('ytp-button', 'cliptap-control-button');

    if (button.dataset.cliptapIconVersion !== PLAYER_TOOLBAR_ICON_VERSION) {
      button.innerHTML = getPlayerToolbarDownloadIcon();
      button.dataset.cliptapIconVersion = PLAYER_TOOLBAR_ICON_VERSION;
    }

    if (button.dataset.cliptapClickBound !== 'true') {
      button.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        state.panelOpen = !state.panelOpen;
        render();
      });
      button.dataset.cliptapClickBound = 'true';
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
          <div class="cliptap-title-actions">
            <button type="button" class="cliptap-loop" data-action="toggle-loop" aria-label="Loop selected range" aria-pressed="false" title="Loop selected range">
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path d="M7 7h9.2c2.1 0 3.8 1.7 3.8 3.8 0 1.1-.5 2.2-1.3 2.9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M17 4l3 3-3 3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M17 17H7.8C5.7 17 4 15.3 4 13.2c0-1.1.5-2.2 1.3-2.9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M7 20l-3-3 3-3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
            <button type="button" class="cliptap-close" data-action="close" aria-label="Close">×</button>
          </div>
        </div>
        <div class="cliptap-time-grid">
          <div class="cliptap-time-box">
            <span>Start</span>
            <input data-role="start" type="text" inputmode="decimal" placeholder="--:--:--.--" aria-label="ClipTap start time" spellcheck="false">
          </div>
          <div class="cliptap-time-box">
            <span>End</span>
            <input data-role="end" type="text" inputmode="decimal" placeholder="--:--:--.--" aria-label="ClipTap end time" spellcheck="false">
          </div>
        </div>
        <div class="cliptap-buttons">
          <button type="button" data-action="start">Set Start</button>
          <button type="button" data-action="end">Set End</button>
        </div>
        <div class="cliptap-download-buttons">
          <button type="button" data-action="download-section">Download Section</button>
          <button type="button" data-action="download-full">Download Full</button>
        </div>
        <div class="cliptap-message" data-role="message">You can also drag the blue/orange circles on the timeline.</div>
      `;
      panel.addEventListener('click', handlePanelClick);
      panel.addEventListener('keydown', handleTimeInputKeydown, true);
      panel.addEventListener('focusout', handleTimeInputCommit, true);
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
        <div class="cliptap-handle" data-kind="start" data-label="Start" role="slider" aria-label="ClipTap start point" tabindex="0"></div>
        <div class="cliptap-handle" data-kind="end" data-label="End" role="slider" aria-label="ClipTap end point" tabindex="0"></div>
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


  function hasValidLoopRange() {
    return state.start != null && state.end != null && state.end > state.start + MIN_GAP_SECONDS;
  }

  function startLoopWatcher() {
    if (loopRafId) return;

    const tick = () => {
      loopRafId = 0;
      handleLoopTick();
      if (state.loopEnabled) startLoopWatcher();
    };

    loopRafId = window.requestAnimationFrame(tick);
  }

  function stopLoopWatcher() {
    if (!loopRafId) return;
    window.cancelAnimationFrame(loopRafId);
    loopRafId = 0;
  }

  function setLoopEnabled(enabled) {
    const next = Boolean(enabled);

    if (next && !hasValidLoopRange()) {
      state.loopEnabled = false;
      stopLoopWatcher();
      setPanelMessage('Set a start and end range before turning on loop.');
      renderPanel();
      renderButton();
      return false;
    }

    state.loopEnabled = next;

    if (state.loopEnabled) {
      const video = getVideo();
      if (video && hasValidLoopRange()) {
        const wasPaused = video.paused;
        setCurrentTime(state.start);
        if (!wasPaused) {
          const playPromise = video.play();
          if (playPromise?.catch) playPromise.catch(() => {});
        }
      }
      startLoopWatcher();
    } else {
      stopLoopWatcher();
    }

    renderPanel();
    renderButton();
    return true;
  }

  function handleLoopTick() {
    if (!state.loopEnabled || !hasValidLoopRange()) return;

    const video = getVideo();
    if (!video || video.seeking || video.duration <= 0) return;

    const start = state.start;
    const end = state.end;
    const tooEarly = video.currentTime < start - LOOP_EPSILON_SECONDS;
    const reachedEnd = video.currentTime >= end - LOOP_EPSILON_SECONDS;

    if (!tooEarly && !reachedEnd) return;

    const wasPaused = video.paused;
    video.currentTime = start;
    if (!wasPaused) {
      const playPromise = video.play();
      if (playPromise?.catch) playPromise.catch(() => {});
    }
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

    if (state.loopEnabled && !hasValidLoopRange()) setLoopEnabled(false);
    else if (state.loopEnabled) startLoopWatcher();

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

  function getTimeInputKind(input) {
    if (!input?.matches?.('#cliptap-player-panel input[data-role="start"], #cliptap-player-panel input[data-role="end"]')) return null;
    return input.dataset.role;
  }

  function commitTimeInput(input, shouldSeek = true) {
    const kind = getTimeInputKind(input);
    if (!kind) return false;

    const seconds = clockToSeconds(input.value);
    if (!Number.isFinite(seconds)) {
      setPanelMessage('Check the time format. Example: 00:14:09.35');
      renderPanel();
      return false;
    }

    setMarker(kind, seconds, shouldSeek);
    setPanelMessage(kind === 'start' ? 'Start time updated.' : 'End time updated.');
    return true;
  }

  function handleTimeInputKeydown(event) {
    const input = event.target;
    if (!getTimeInputKind(input)) return;

    event.stopPropagation();
    if (event.key === 'Enter') {
      event.preventDefault();
      commitTimeInput(input, true);
      input.blur();
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      renderPanel();
      input.blur();
    }
  }

  function handleTimeInputCommit(event) {
    const input = event.target;
    if (!getTimeInputKind(input)) return;
    commitTimeInput(input, true);
  }

  function handlePanelClick(event) {
    const action = event.target?.dataset?.action;
    if (!action) return;

    event.preventDefault();
    event.stopPropagation();

    const video = getVideo();
    if (!video) {
      setPanelMessage('Could not find a video element.');
      return;
    }

    if (action === 'close') {
      state.panelOpen = false;
      render();
      return;
    }
    if (action === 'toggle-loop') {
      const enabled = setLoopEnabled(!state.loopEnabled);
      if (enabled) {
        setPanelMessage(state.loopEnabled ? 'Loop enabled. The selected range will repeat automatically.' : 'Loop disabled.');
      }
      return;
    }
    if (action === 'start') {
      setMarker('start', video.currentTime, false);
      setPanelMessage('Start point saved. Drag the blue circle to adjust it.');
      return;
    }
    if (action === 'end') {
      setMarker('end', video.currentTime, false);
      setPanelMessage('End point saved. Drag the orange circle to adjust it.');
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


  async function requestPlaylistDownload(button) {
    const playlistId = getPlaylistId();
    if (!playlistId) return;

    const payload = {
      mode: 'playlist',
      url: getPlaylistUrl(),
      title: getPlaylistTitle(),
      quality: state.quality,
      cookieBrowser: state.cookieBrowser,
      forceKeyframes: false
    };

    try {
      button?.classList.add('cliptap-sending');
      setPanelMessage('Sending playlist download request...');
      const res = await fetch('http://127.0.0.1:17723/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Helper error');
      setPanelMessage('Playlist download started.');
    } catch (error) {
      setPanelMessage('The helper is off or the playlist request failed.');
      console.error('[ClipTap]', error);
    } finally {
      button?.classList.remove('cliptap-sending');
    }
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
        setPanelMessage('Set the start and end points first.');
        return;
      }
      if (state.end <= state.start) {
        setPanelMessage('The end point must be after the start point.');
        return;
      }
      payload.start = state.start;
      payload.end = state.end;
    }

    try {
      setPanelMessage(mode === 'full' ? 'Sending full download request...' : 'Sending section download request...');
      const res = await fetch('http://127.0.0.1:17723/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Helper error');
      setPanelMessage(mode === 'full' ? 'Full download started.' : 'Section download started.');
    } catch (error) {
      setPanelMessage('The helper is off or an error occurred.');
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
    state.loopEnabled = false;
    stopLoopWatcher();
  }


  function getPlaylistDownloadIcon() {
    return `
      <span class="cliptap-playlist-icon-wrap" aria-hidden="true">
        <svg class="cliptap-native-playlist-svg" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 0 24 24" width="24" focusable="false" aria-hidden="true" style="pointer-events:none;display:inherit;width:100%;height:100%;">
          <path d="M4 5h10a1 1 0 110 2H4a1 1 0 010-2Zm0 6h8.25a1 1 0 110 2H4a1 1 0 110-2Zm0 6h6a1 1 0 110 2H4a1 1 0 110-2Zm13-9a1 1 0 011 1v5.586l1.293-1.293a1 1 0 111.414 1.414L17 18.414l-3.707-3.707a1 1 0 111.414-1.414L16 14.586V9a1 1 0 011-1Zm3 12h-6a1 1 0 100 2h6a1 1 0 100-2Z"></path>
        </svg>
      </span>`;
  }

  function makePlaylistButtonElement(kind, template = null) {
    const templateTag = template?.tagName?.toLowerCase?.() || '';
    const shouldUseDiv = templateTag === 'div' || templateTag.startsWith('yt') || templateTag.startsWith('ytd');
    const button = document.createElement(shouldUseDiv ? 'div' : 'button');

    if (template?.className && typeof template.className === 'string') {
      button.className = template.className;
    }

    if (button.tagName.toLowerCase() === 'button') {
      button.type = 'button';
    } else {
      button.setAttribute('role', 'button');
      button.setAttribute('tabindex', '0');
    }

    button.classList.add(
      'cliptap-playlist-download-button',
      'cliptap-playlist-native-button',
      `cliptap-${kind}-playlist-button`
    );
    button.innerHTML = getPlaylistDownloadIcon();
    button.title = 'Download playlist with ClipTap';
    button.setAttribute('aria-label', 'Download playlist with ClipTap');
    button.setAttribute('data-tooltip-text', 'Download playlist with ClipTap');
    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      requestPlaylistDownload(button);
    }, true);
    button.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      event.stopPropagation();
      requestPlaylistDownload(button);
    }, true);
    return button;
  }

  function findByTextOrLabel(root, words) {
    if (!root) return null;
    const elements = [...root.querySelectorAll('button, a, div[role="button"], yt-button-shape, ytd-button-renderer, ytd-toggle-button-renderer, tp-yt-paper-button')];
    return elements.find(el => {
      const haystack = [
        el.getAttribute('aria-label'),
        el.getAttribute('title'),
        el.getAttribute('data-tooltip-text'),
        el.textContent
      ].filter(Boolean).join(' ').toLowerCase();
      return words.some(word => haystack.includes(word));
    }) || null;
  }

  function findPlaylistShareAction() {
    const exact = document.querySelector('div.ytFlexibleActionsViewModelActionIconOnlyButton.ytFlexibleActionsViewModelActionRowAction.ytFlexibleActionsViewModelAction:nth-of-type(3)');
    if (exact) return exact;

    const header = document.querySelector('ytd-playlist-header-renderer') || document;
    const byText = findByTextOrLabel(header, ['share', '공유']);
    if (byText) return byText;

    const candidates = [
      'ytd-playlist-header-renderer yt-flexible-actions-view-model div.ytFlexibleActionsViewModelActionRowAction:nth-of-type(3)',
      'ytd-playlist-header-renderer .ytFlexibleActionsViewModelActionRowAction:nth-of-type(3)',
      'ytd-playlist-header-renderer #actions yt-button-shape:nth-of-type(3)',
      'ytd-playlist-header-renderer #buttons yt-button-shape:nth-of-type(3)',
      'ytd-playlist-header-renderer #top-level-buttons-computed > *:nth-child(3)'
    ];
    for (const selector of candidates) {
      const element = document.querySelector(selector);
      if (element) return element;
    }
    return null;
  }

  function findPlaylistActionContainer() {
    const selectors = [
      'ytd-playlist-header-renderer yt-flexible-actions-view-model',
      'ytd-playlist-header-renderer div.ytFlexibleActionsViewModelActionRow',
      'ytd-playlist-header-renderer #actions',
      'ytd-playlist-header-renderer #buttons',
      'ytd-playlist-header-renderer #top-level-buttons-computed',
      'ytd-playlist-header-renderer ytd-menu-renderer #top-level-buttons-computed',
      'ytd-playlist-header-renderer ytd-menu-renderer'
    ];
    for (const selector of selectors) {
      const element = document.querySelector(selector);
      if (element) return element;
    }
    return null;
  }

  function mountPlaylistPageButton() {
    const mounted = document.querySelector('.cliptap-page-playlist-button');
    if (!isPlaylistPageUrl()) {
      mounted?.remove();
      document.querySelectorAll('[data-cliptap-hidden-share="true"]').forEach(el => {
        el.style.display = '';
        delete el.dataset.cliptapHiddenShare;
      });
      return;
    }
    if (mounted && document.documentElement.contains(mounted)) return;

    const target = findPlaylistShareAction();
    const container = target?.parentElement || findPlaylistActionContainer();
    if (!container) return;

    const button = makePlaylistButtonElement('page', target);
    if (target?.parentElement) {
      target.parentElement.insertBefore(button, target);
      target.dataset.cliptapHiddenShare = 'true';
      target.style.display = 'none';
    } else {
      container.appendChild(button);
    }
  }

  function findWatchPlaylistToolbar() {
    const selectors = [
      '#playlist-action-menu > .ytd-playlist-panel-renderer.style-scope',
      'ytd-playlist-panel-renderer #playlist-action-menu',
      '#playlist-action-menu',
      'ytd-playlist-panel-renderer #top-level-buttons-computed',
      'ytd-playlist-panel-renderer ytd-menu-renderer #top-level-buttons-computed',
      'ytd-playlist-panel-renderer ytd-menu-renderer',
      'ytd-playlist-panel-renderer #menu'
    ];
    for (const selector of selectors) {
      const element = document.querySelector(selector);
      if (element) return element;
    }
    return null;
  }

  function mountWatchPlaylistButton() {
    const mounted = document.querySelector('.cliptap-watch-playlist-button');
    if (!isWatchPlaylistUrl()) {
      mounted?.remove();
      return;
    }
    if (mounted && document.documentElement.contains(mounted)) return;

    const toolbar = findWatchPlaylistToolbar();
    if (!toolbar || toolbar.querySelector('.cliptap-watch-playlist-button')) return;

    const template = toolbar.querySelector('button, div[role="button"], yt-button-shape, ytd-toggle-button-renderer, ytd-button-renderer, tp-yt-paper-button');
    const button = makePlaylistButtonElement('watch', template);
    toolbar.appendChild(button);
  }

  function mountPlaylistDownloadButtons() {
    mountPlaylistPageButton();
    mountWatchPlaylistButton();
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
    const startEl = panel.querySelector('input[data-role="start"]');
    const endEl = panel.querySelector('input[data-role="end"]');
    const setInputValue = (input, value) => {
      if (!input || document.activeElement === input) return;
      input.value = value == null ? '' : secondsToClock(value);
    };
    setInputValue(startEl, state.start);
    setInputValue(endEl, state.end);

    const loopButton = panel.querySelector('[data-action="toggle-loop"]');
    if (loopButton) {
      loopButton.setAttribute('aria-pressed', String(state.loopEnabled));
      loopButton.title = state.loopEnabled ? 'Turn loop off' : 'Loop selected range';
    }
  }

  function renderButton() {
    const button = document.getElementById('cliptap-control-button');
    if (!button) return;
    button.classList.toggle('cliptap-active', state.panelOpen || state.start != null || state.end != null || state.loopEnabled);
  }

  function render() {
    resetForNewVideoIfNeeded();
    ensureStyle();
    ensureControlButton();
    ensurePanel();
    ensureProgressOverlay();
    mountPlaylistDownloadButtons();
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
      loopEnabled: state.loopEnabled,
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
