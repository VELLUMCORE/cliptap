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
    return document.querySelector('.ytp-right-controls-left') ||
      document.querySelector('.ytp-right-controls');
  }

  function getPlayerToolbarMountTarget() {
    if (location.pathname !== '/watch') return null;

    const player = getPlayer();
    const leftControls = player?.querySelector?.('.ytp-right-controls-left') ||
      document.querySelector('.ytp-right-controls-left');
    if (leftControls) {
      return { controls: leftControls, name: 'right-controls-left' };
    }

    const rightControls = player?.querySelector?.('.ytp-right-controls') ||
      document.querySelector('.ytp-right-controls');
    if (rightControls) {
      return { controls: rightControls, name: 'right-controls' };
    }

    return null;
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

  function isChannelPageUrl() {
    if (location.hostname !== 'www.youtube.com' && location.hostname !== 'youtube.com') return false;
    const path = location.pathname;
    if (path === '/watch' || path === '/playlist' || path.startsWith('/shorts/')) return false;
    return path.startsWith('/@') ||
      path.startsWith('/channel/') ||
      path.startsWith('/c/') ||
      path.startsWith('/user/');
  }

  function getChannelUrl() {
    return getChannelBaseUrl();
  }

  function getChannelBaseUrl() {
    const parts = location.pathname.split('/').filter(Boolean);
    if (!parts.length) return `${location.origin}${location.pathname}`;

    const first = parts[0];
    let baseParts = [];
    if (first.startsWith('@')) {
      baseParts = [first];
    } else if (['channel', 'c', 'user'].includes(first) && parts[1]) {
      baseParts = [first, parts[1]];
    } else {
      baseParts = [first];
    }

    return `${location.origin}/${baseParts.join('/')}`;
  }

  function getChannelDownloadTarget(kind = 'whole') {
    const base = getChannelBaseUrl();
    if (kind === 'videos') return `${base}/videos`;
    if (kind === 'shorts') return `${base}/shorts`;
    if (kind === 'lives') return `${base}/streams`;
    return base;
  }

  function getChannelDownloadLabel(kind = 'whole') {
    if (kind === 'videos') return 'videos';
    if (kind === 'shorts') return 'shorts';
    if (kind === 'lives') return 'lives';
    return 'whole channel';
  }

  function getChannelTitle() {
    const candidates = [
      'yt-page-header-view-model h1',
      'ytd-channel-name yt-formatted-string',
      '#channel-name yt-formatted-string',
      '#text.ytd-channel-name',
      'h1 yt-formatted-string',
      'h1'
    ];
    for (const selector of candidates) {
      const value = document.querySelector(selector)?.textContent?.trim();
      if (value) return value;
    }
    return (document.title || 'YouTube channel').replace(/ - YouTube$/, '').trim();
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
      .cliptap-playlist-native-button:not(.cliptap-page-playlist-button),
      button.cliptap-playlist-native-button:not(.cliptap-page-playlist-button),
      div.cliptap-playlist-native-button:not(.cliptap-page-playlist-button) {
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
        padding: 6px !important;
        margin: 0 !important;
        border: 0 !important;
        border-radius: 50% !important;
        background: transparent !important;
        line-height: 0 !important;
        vertical-align: middle !important;
        overflow: visible !important;
        z-index: 3 !important;
      }
      .cliptap-page-playlist-button {
        color: inherit !important;
      }
      .cliptap-page-playlist-button .ytIconWrapperHost {
        width: 24px !important;
        height: 24px !important;
      }
      .cliptap-page-playlist-button svg.cliptap-native-playlist-svg,
      .cliptap-page-playlist-button svg {
        display: inherit !important;
        width: 100% !important;
        height: 100% !important;
        min-width: 24px !important;
        min-height: 24px !important;
        margin: 0 !important;
        pointer-events: none !important;
      }
      .cliptap-page-playlist-button path {
        fill: currentColor !important;
        stroke: none !important;
      }
      .cliptap-watch-playlist-button {
        margin-left: -3px !important;
        margin-right: -1px !important;
      }
      .cliptap-page-playlist-button.ytFlexibleActionsViewModelActionIconOnlyButton,
      .cliptap-page-playlist-button.ytFlexibleActionsViewModelActionRowAction {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
      }
      .cliptap-playlist-native-button:not(.cliptap-page-playlist-button):hover,
      .cliptap-playlist-native-button:not(.cliptap-page-playlist-button):focus-visible {
        background-color: rgba(255, 255, 255, .10) !important;
        outline: none !important;
      }
      .cliptap-playlist-native-button:not(.cliptap-page-playlist-button):active {
        transform: scale(.96) !important;
      }
      .cliptap-share-menu-item {
        display: flex !important;
        align-items: center !important;
        gap: 16px !important;
        min-height: 36px !important;
        padding: 0 16px !important;
        box-sizing: border-box !important;
        color: inherit !important;
        cursor: pointer !important;
        font: 14px/20px Roboto, Arial, sans-serif !important;
        white-space: nowrap !important;
      }
      .cliptap-share-menu-item:hover,
      .cliptap-share-menu-item:focus-visible {
        background: rgba(255, 255, 255, .10) !important;
        outline: none !important;
      }
      .cliptap-share-menu-item svg {
        display: block !important;
        width: 24px !important;
        height: 24px !important;
        fill: currentColor !important;
        pointer-events: none !important;
      }
      .cliptap-playlist-icon-wrap {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 28px !important;
        height: 28px !important;
        min-width: 28px !important;
        min-height: 28px !important;
        line-height: 0 !important;
        color: #fff !important;
        transform: none !important;
        pointer-events: none !important;
      }
      .cliptap-playlist-icon-wrap svg.cliptap-native-playlist-svg {
        display: inherit !important;
        width: 28px !important;
        height: 28px !important;
        min-width: 28px !important;
        min-height: 28px !important;
        margin: 0 !important;
        pointer-events: none !important;
        overflow: visible !important;
      }
      .cliptap-playlist-icon-wrap svg.cliptap-native-playlist-svg path {
        fill: #fff !important;
        stroke: none !important;
      }
      .cliptap-channel-download-action {
        display: inline-flex !important;
        align-items: center !important;
        position: relative !important;
        overflow: visible !important;
      }
      .cliptap-channel-download-action > button {
        min-width: 0 !important;
      }
      .cliptap-channel-download-action .cliptap-channel-download-chevron svg {
        width: 24px !important;
        height: 24px !important;
      }
      .cliptap-channel-download-popup tp-yt-iron-dropdown {
        display: block !important;
        visibility: visible !important;
      }
      .cliptap-channel-download-popup yt-sheet-view-model {
        background: var(--yt-spec-menu-background, #282828) !important;
        color: var(--yt-spec-text-primary, #fff) !important;
        border-radius: 12px !important;
        overflow: hidden !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, .34) !important;
      }
      .cliptap-channel-download-menu-item {
        cursor: pointer !important;
      }
      .cliptap-channel-download-menu-item:hover,
      .cliptap-channel-download-menu-item:focus-visible {
        background: var(--yt-spec-badge-chip-background, rgba(255, 255, 255, .1)) !important;
        outline: none !important;
      }
      .cliptap-playlist-download-button.cliptap-sending,
      .cliptap-channel-download-action.cliptap-sending {
        opacity: .62 !important;
        pointer-events: none !important;
      }
      #cliptap-feedback-toast {
        position: fixed;
        left: 50%;
        bottom: 28px;
        z-index: 2147483647;
        max-width: min(420px, calc(100vw - 32px));
        padding: 10px 14px;
        border-radius: 4px;
        background: rgba(32, 32, 32, .96);
        color: #fff;
        font: 500 13px/1.35 Roboto, Arial, sans-serif;
        box-shadow: 0 3px 14px rgba(0, 0, 0, .32);
        opacity: 0;
        transform: translate(-50%, 10px);
        pointer-events: none;
        transition: opacity .16s ease, transform .16s ease;
      }
      #cliptap-feedback-toast.cliptap-visible {
        opacity: 1;
        transform: translate(-50%, 0);
      }
      #cliptap-feedback-toast.cliptap-error {
        background: rgba(190, 43, 43, .96);
      }
      #cliptap-feedback-toast.cliptap-success {
        background: rgba(38, 38, 38, .98);
      }
    `;
    document.documentElement.appendChild(style);
  }

  const PLAYER_TOOLBAR_ICON_VERSION = '81';
  const PLAYLIST_BUTTON_VERSION = '57';
  const CHANNEL_BUTTON_VERSION = '81';
  let cliptapToastTimer = 0;

  function ensureClipTapToast() {
    let toast = document.getElementById('cliptap-feedback-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'cliptap-feedback-toast';
      toast.setAttribute('role', 'status');
      toast.setAttribute('aria-live', 'polite');
      document.documentElement.appendChild(toast);
    }
    return toast;
  }

  function showClipTapToast(message, type = 'info') {
    const toast = ensureClipTapToast();
    window.clearTimeout(cliptapToastTimer);
    toast.textContent = message;
    toast.classList.toggle('cliptap-error', type === 'error');
    toast.classList.toggle('cliptap-success', type === 'success');
    toast.classList.add('cliptap-visible');
    cliptapToastTimer = window.setTimeout(() => {
      toast.classList.remove('cliptap-visible');
    }, type === 'error' ? 4200 : 2800);
  }

  function getNativePaperTooltip(text) {
    return `<tp-yt-paper-tooltip fit-to-visible-bounds offset="8" role="tooltip" tabindex="-1" aria-label="tooltip">${text}</tp-yt-paper-tooltip>`;
  }

  function applyNativeTooltipAttributes(element, text, targetId = '') {
    if (!element) return;
    element.title = '';
    element.setAttribute('aria-label', text);
    element.setAttribute('data-tooltip-title', text);
    if (targetId) element.setAttribute('data-tooltip-target-id', targetId);
    element.removeAttribute('data-tooltip-text');
    element.removeAttribute('data-cliptap-tooltip-text');
    element.removeAttribute('data-cliptap-tooltip-placement');
    element.removeAttribute('data-cliptap-tooltip-bound');
  }

  function ensureNativePaperTooltip(host, text) {
    if (!host) return;
    host.querySelectorAll('tp-yt-paper-tooltip.cliptap-native-tooltip').forEach(el => el.remove());
    const tooltip = document.createElement('template');
    tooltip.innerHTML = getNativePaperTooltip(text);
    const node = tooltip.content.firstElementChild;
    node.classList.add('cliptap-native-tooltip');
    node.textContent = text;
    host.appendChild(node);
  }

  function ensurePlayerTooltipBridge() {
    if (!chrome?.runtime?.getURL) return;
    const marker = document.documentElement;
    if (!marker || marker.dataset.cliptapPlayerTooltipBridge === PLAYER_TOOLBAR_ICON_VERSION) return;

    const script = document.createElement('script');
    script.src = `${chrome.runtime.getURL('player-tooltip-bridge.js')}?v=${PLAYER_TOOLBAR_ICON_VERSION}`;
    script.dataset.cliptapPlayerTooltipBridge = PLAYER_TOOLBAR_ICON_VERSION;
    script.onload = () => script.remove();
    script.onerror = () => marker.removeAttribute('data-cliptap-player-tooltip-bridge');
    (document.head || document.documentElement).appendChild(script);
    marker.dataset.cliptapPlayerTooltipBridge = PLAYER_TOOLBAR_ICON_VERSION;
  }

  function requestNativePlayerTooltipBinding() {
    const payload = JSON.stringify({
      buttonId: 'cliptap-control-button',
      text: 'Download with ClipTap',
      version: PLAYER_TOOLBAR_ICON_VERSION
    });

    const dispatch = () => {
      window.dispatchEvent(new CustomEvent('cliptap:bind-native-player-tooltip', { detail: payload }));
    };

    dispatch();
    window.setTimeout(dispatch, 80);
    window.setTimeout(dispatch, 350);
    window.setTimeout(dispatch, 1200);
  }

  function bindClipTapPlayerTooltip(button) {
    if (!button) return;
    ensurePlayerTooltipBridge();
    if (button.dataset.cliptapPlayerTooltipVersion !== PLAYER_TOOLBAR_ICON_VERSION) {
      button.dataset.cliptapPlayerTooltipVersion = PLAYER_TOOLBAR_ICON_VERSION;
    }
    requestNativePlayerTooltipBinding();
  }

  function getPlayerToolbarDownloadIcon() {
    return `<span class="cliptap-player-icon-wrap" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" height="26" viewBox="0 0 24 24" width="26" focusable="false" aria-hidden="true" style="pointer-events:none;display:block;width:26px;height:26px;"><path class="ytp-svg-fill" d="M6.25 3A3.25 3.25 0 0 0 3 6.25v3.15a1 1 0 1 0 2 0V6.25C5 5.56 5.56 5 6.25 5H9.4a1 1 0 1 0 0-2H6.25Zm8.35 0a1 1 0 1 0 0 2h3.15c.69 0 1.25.56 1.25 1.25V9.4a1 1 0 1 0 2 0V6.25A3.25 3.25 0 0 0 17.75 3H14.6ZM12 6.5a1 1 0 0 0-1 1v6.09l-1.65-1.64a1 1 0 1 0-1.41 1.41L12 18.41l4.06-4.05a1 1 0 0 0-1.41-1.42L13 14.59V7.5a1 1 0 0 0-1-1ZM4 13.6a1 1 0 0 0-1 1v3.15A3.25 3.25 0 0 0 6.25 21H9.4a1 1 0 1 0 0-2H6.25C5.56 19 5 18.44 5 17.75V14.6a1 1 0 0 0-1-1Zm16 0a1 1 0 0 0-1 1v3.15c0 .69-.56 1.25-1.25 1.25H14.6a1 1 0 1 0 0 2h3.15A3.25 3.25 0 0 0 21 17.75V14.6a1 1 0 0 0-1-1Z"></path></svg></span>`;
  }

  function ensureControlButton() {
    const target = getPlayerToolbarMountTarget();
    const existingButton = document.getElementById('cliptap-control-button');

    if (!target) {
      existingButton?.remove();
      return;
    }

    const { controls, name } = target;
    let button = existingButton;
    if (!button) {
      button = document.createElement('button');
      button.id = 'cliptap-control-button';
      button.className = 'ytp-button cliptap-control-button';
      button.type = 'button';
      applyNativeTooltipAttributes(button, 'Download with ClipTap', 'cliptap-control-button');
      button.setAttribute('data-title-no-tooltip', 'Download with ClipTap');
      button.setAttribute('aria-label', 'Download with ClipTap');
      button.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        togglePanel();
      });
    }

    if (button.dataset.cliptapIconVersion !== PLAYER_TOOLBAR_ICON_VERSION) {
      button.innerHTML = getPlayerToolbarDownloadIcon();
      button.dataset.cliptapIconVersion = PLAYER_TOOLBAR_ICON_VERSION;
      applyNativeTooltipAttributes(button, 'Download with ClipTap', 'cliptap-control-button');
      button.setAttribute('data-title-no-tooltip', 'Download with ClipTap');
    }

    if (button.parentElement !== controls) {
      const subtitlesButton = controls.querySelector('.ytp-subtitles-button');
      if (subtitlesButton?.parentElement === controls) {
        controls.insertBefore(button, subtitlesButton);
      } else {
        controls.insertBefore(button, controls.firstElementChild);
      }
    }

    button.dataset.cliptapPlayerMountedAt = name;
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
      button?.setAttribute('aria-busy', 'true');
      showClipTapToast('Sending playlist download request to ClipTap...');
      setPanelMessage('Sending playlist download request...');
      const res = await fetch('http://127.0.0.1:17723/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Helper error');
      showClipTapToast('Playlist download request sent to ClipTap.', 'success');
      setPanelMessage('Playlist download started.');
    } catch (error) {
      showClipTapToast('ClipTap Helper is not running or the request failed.', 'error');
      setPanelMessage('The helper is off or the playlist request failed.');
      console.error('[ClipTap]', error);
    } finally {
      button?.classList.remove('cliptap-sending');
      button?.removeAttribute('aria-busy');
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

  async function requestChannelDownload(button, kind = 'whole') {
    if (!isChannelPageUrl()) return;

    const label = getChannelDownloadLabel(kind);
    const titleSuffix = kind === 'whole' ? '' : ` (${label})`;
    const payload = {
      mode: 'channel',
      url: getChannelDownloadTarget(kind),
      title: `${getChannelTitle()}${titleSuffix}`,
      quality: state.quality,
      cookieBrowser: state.cookieBrowser,
      forceKeyframes: false
    };

    try {
      button?.classList.add('cliptap-sending');
      button?.setAttribute('aria-busy', 'true');
      showClipTapToast(`Sending ${label} download request to ClipTap...`);
      setPanelMessage(`Sending ${label} download request...`);
      const res = await fetch('http://127.0.0.1:17723/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Request failed.');
      showClipTapToast(`Channel ${label} download request sent to ClipTap.`, 'success');
      setPanelMessage(`Channel ${label} download started.`);
    } catch (error) {
      showClipTapToast('ClipTap Helper is not running or the request failed.', 'error');
      setPanelMessage('The helper is off or an error occurred.');
      console.error('[ClipTap]', error);
    } finally {
      button?.classList.remove('cliptap-sending');
      button?.removeAttribute('aria-busy');
    }
  }


  function getPlaylistDownloadSvg() {
    return `<svg class="cliptap-native-playlist-svg" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 0 24 24" width="24" focusable="false" aria-hidden="true" style="pointer-events:none;display:inherit;width:100%;height:100%;"><path d="M4 5h10a1 1 0 1 1 0 2H4a1 1 0 0 1 0-2Zm0 6h8.5a1 1 0 1 1 0 2H4a1 1 0 1 1 0-2Zm0 6h6.25a1 1 0 1 1 0 2H4a1 1 0 1 1 0-2Zm13-10a1 1 0 0 1 1 1v6.59l1.29-1.3a1 1 0 1 1 1.42 1.42L17 19.41l-3.71-3.7a1 1 0 1 1 1.42-1.42l1.29 1.3V8a1 1 0 0 1 1-1Z"></path></svg>`;
  }

  function getPlaylistDownloadIcon() {
    return `
      <span class="cliptap-playlist-icon-wrap" aria-hidden="true">
        ${getPlaylistDownloadSvg()}
      </span>`;
  }

  function getNativePlaylistActionIcon() {
    return `<div aria-hidden="true" class="ytSpecButtonShapeNextIcon"><span class="ytIconWrapperHost" style="width: 24px; height: 24px;"><span class="yt-icon-shape ytSpecIconShapeHost"><div style="width: 100%; height: 100%; display: block; fill: currentcolor;">${getPlaylistDownloadSvg()}</div></span></span></div>`;
  }

  function bindPlaylistButtonEvents(element) {
    if (!element || element.dataset.cliptapBound === 'true') return;
    element.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      requestPlaylistDownload(element);
    }, true);
    element.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      event.stopPropagation();
      requestPlaylistDownload(element);
    }, true);
    element.dataset.cliptapBound = 'true';
  }

  function makePlaylistPageButtonElement(template = null) {
    const wrapper = template?.cloneNode?.(true) || document.createElement('div');
    wrapper.classList.add(
      'ytFlexibleActionsViewModelAction',
      'ytFlexibleActionsViewModelActionRowAction',
      'ytFlexibleActionsViewModelActionIconOnlyButton',
      'cliptap-playlist-download-button',
      'cliptap-playlist-native-button',
      'cliptap-page-playlist-button'
    );
    wrapper.removeAttribute('hidden');
    wrapper.removeAttribute('data-cliptap-hidden-share');
    wrapper.style.display = '';

    wrapper.querySelectorAll('[id]').forEach(el => el.removeAttribute('id'));
    wrapper.querySelectorAll('tp-yt-paper-tooltip').forEach(el => el.remove());

    let clickable = wrapper.querySelector('button, a, div[role="button"]');
    if (!clickable) {
      clickable = document.createElement('button');
      clickable.className = 'ytSpecButtonShapeNextHost ytSpecButtonShapeNextTonal ytSpecButtonShapeNextOverlay ytSpecButtonShapeNextSizeM ytSpecButtonShapeNextIconButton ytSpecButtonShapeNextEnableBackdropFilterExperiment';
      wrapper.textContent = '';
      const host = document.createElement('button-view-model');
      host.className = 'ytSpecButtonViewModelHost';
      host.appendChild(clickable);
      wrapper.appendChild(host);
    }

    if (clickable.tagName.toLowerCase() === 'a') {
      clickable.removeAttribute('href');
      clickable.setAttribute('role', 'button');
      clickable.setAttribute('tabindex', '0');
    } else if (clickable.tagName.toLowerCase() === 'button') {
      clickable.type = 'button';
    } else {
      clickable.setAttribute('role', 'button');
      clickable.setAttribute('tabindex', '0');
    }

    applyNativeTooltipAttributes(clickable, 'Download playlist with ClipTap');
    clickable.setAttribute('aria-disabled', 'false');
    clickable.removeAttribute('disabled');
    clickable.removeAttribute('href');

    const oldIcon = clickable.querySelector('.ytSpecButtonShapeNextIcon');
    if (oldIcon) {
      oldIcon.outerHTML = getNativePlaylistActionIcon();
    } else {
      clickable.insertAdjacentHTML('afterbegin', getNativePlaylistActionIcon());
    }

    applyNativeTooltipAttributes(wrapper, 'Download playlist with ClipTap');
    wrapper.dataset.cliptapPlaylistVersion = PLAYLIST_BUTTON_VERSION;
    ensureNativePaperTooltip(wrapper, 'Download playlist with ClipTap');

    bindPlaylistButtonEvents(wrapper);
    bindPlaylistButtonEvents(clickable);
    return wrapper;
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
    applyNativeTooltipAttributes(button, 'Download playlist with ClipTap');
    ensureNativePaperTooltip(button, 'Download playlist with ClipTap');
    bindPlaylistButtonEvents(button);
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

  function getPlaylistActionWrapper(element) {
    return element?.closest?.('.ytFlexibleActionsViewModelActionRowAction, .ytFlexibleActionsViewModelAction') || element || null;
  }

  function getPlaylistActionRow() {
    const selectors = [
      '.ytFlexibleActionsViewModelActionRow',
      'yt-flexible-actions-view-model .ytFlexibleActionsViewModelActionRow',
      'ytd-playlist-header-renderer .ytFlexibleActionsViewModelActionRow',
      'ytd-playlist-header-renderer #actions .ytFlexibleActionsViewModelActionRow',
      'ytd-playlist-header-renderer #buttons .ytFlexibleActionsViewModelActionRow'
    ];
    for (const selector of selectors) {
      const rows = [...document.querySelectorAll(selector)];
      const row = rows.find(candidate => {
        const rect = candidate.getBoundingClientRect?.();
        const hasActions = candidate.querySelector?.('.ytFlexibleActionsViewModelActionRowAction, button, a');
        return hasActions && (!rect || rect.width > 0 || rect.height > 0);
      });
      if (row) return row;
    }
    return null;
  }

  function actionText(action) {
    if (!action) return '';
    const nodes = [
      action,
      ...action.querySelectorAll?.('button, a, div[role="button"], [aria-label], [title], [data-tooltip-text]') || []
    ];
    return nodes.map(el => [
      el.getAttribute?.('aria-label'),
      el.getAttribute?.('title'),
      el.getAttribute?.('data-tooltip-text'),
      el.textContent
    ].filter(Boolean).join(' ')).join(' ').toLowerCase();
  }

  function findPlaylistActionByLabels(words, root = null) {
    const scope = root || getPlaylistActionRow() || document.querySelector('ytd-playlist-header-renderer') || document;
    const actions = [...scope.querySelectorAll('.ytFlexibleActionsViewModelActionRowAction, .ytFlexibleActionsViewModelAction')];
    for (const action of actions) {
      if (action.classList?.contains('cliptap-page-playlist-button')) continue;
      const haystack = actionText(action);
      if (words.some(word => haystack.includes(word))) return action;
    }

    const controls = [...scope.querySelectorAll('button, a, div[role="button"]')];
    for (const control of controls) {
      if (control.closest?.('.cliptap-page-playlist-button')) continue;
      const haystack = actionText(control);
      if (words.some(word => haystack.includes(word))) return getPlaylistActionWrapper(control);
    }
    return null;
  }

  function findPlaylistShareAction(root = null) {
    const scope = root || getPlaylistActionRow();
    return findPlaylistActionByLabels(['share', '공유'], scope);
  }

  function findPlaylistMoreAction(container = null) {
    const scope = container || getPlaylistActionRow() || document.querySelector('ytd-playlist-header-renderer') || document;
    const action = findPlaylistActionByLabels(['more actions', 'more', '자세히', '더보기', '더 보기'], scope);
    if (action) return action;
    const actions = [...scope.querySelectorAll('.ytFlexibleActionsViewModelActionRowAction, .ytFlexibleActionsViewModelAction')]
      .filter(el => !el.classList?.contains('cliptap-page-playlist-button') && !el.dataset.cliptapHiddenShare);
    return actions[actions.length - 1] || null;
  }

  function getShareMenuIcon() {
    return `<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 0 24 24" width="24" focusable="false" aria-hidden="true"><path d="M10 3.158V7.51c-5.428.223-8.27 3.75-8.875 11.199-.04.487-.07.975-.09 1.464l-.014.395c-.014.473.578.684.88.32.302-.368.61-.73.925-1.086l.244-.273c1.79-1.967 3-2.677 4.93-2.917a18.011 18.011 0 012-.112v4.346a1 1 0 001.646.763l9.805-8.297 1.55-1.31-1.55-1.31-9.805-8.297A1 1 0 0010 3.158Zm2 6.27v.002-4.116l7.904 6.688L12 18.689v-4.212l-2.023.024c-1.935.022-3.587.17-5.197 1.024a9 9 0 00-1.348.893c.355-1.947.916-3.39 1.63-4.425 1.062-1.541 2.607-2.385 5.02-2.485L12 9.428Z"></path></svg>`;
  }

  function getOpenMenuContainer() {
    const candidates = [...document.querySelectorAll('ytd-menu-popup-renderer #items, ytd-menu-popup-renderer, tp-yt-paper-listbox, ytd-popup-container #items, #items.ytd-menu-popup-renderer')];
    return candidates.reverse().find(el => {
      const rect = el.getBoundingClientRect?.();
      return rect && rect.width > 0 && rect.height > 0;
    }) || null;
  }

  function openHiddenPlaylistShare() {
    const share = document.querySelector('[data-cliptap-hidden-share="true"]');
    const clickable = share?.querySelector?.('button, a, div[role="button"]') || share;
    clickable?.click?.();
  }

  function ensurePlaylistShareMenuItem() {
    const share = document.querySelector('[data-cliptap-hidden-share="true"]');
    const menu = share ? getOpenMenuContainer() : null;
    if (!menu || menu.querySelector('.cliptap-share-menu-item')) return;
    const item = document.createElement('div');
    item.className = 'cliptap-share-menu-item';
    item.setAttribute('role', 'menuitem');
    item.setAttribute('tabindex', '0');
    item.innerHTML = `${getShareMenuIcon()}<span>Share</span>`;
    item.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      openHiddenPlaylistShare();
    }, true);
    item.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      event.stopPropagation();
      openHiddenPlaylistShare();
    }, true);
    menu.insertBefore(item, menu.firstChild);
  }

  function startPlaylistMenuObserver() {
    if (document.documentElement.dataset.cliptapShareMenuObserver === PLAYLIST_BUTTON_VERSION) return;
    document.documentElement.dataset.cliptapShareMenuObserver = PLAYLIST_BUTTON_VERSION;
    const observer = new MutationObserver(() => ensurePlaylistShareMenuItem());
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }

  function bindPlaylistMoreAction(moreAction) {
    const clickable = moreAction?.querySelector?.('button, a, div[role="button"]') || moreAction;
    if (clickable && clickable.dataset.cliptapMoreBound !== PLAYLIST_BUTTON_VERSION) {
      clickable.addEventListener('click', () => {
        setTimeout(ensurePlaylistShareMenuItem, 40);
        setTimeout(ensurePlaylistShareMenuItem, 120);
        setTimeout(ensurePlaylistShareMenuItem, 280);
      }, true);
      clickable.dataset.cliptapMoreBound = PLAYLIST_BUTTON_VERSION;
    }
    startPlaylistMenuObserver();
  }

  function hidePlaylistShareAction(shareAction) {
    if (!shareAction || shareAction.classList?.contains('cliptap-page-playlist-button')) return;
    shareAction.dataset.cliptapHiddenShare = 'true';
    shareAction.style.display = 'none';
  }

  function restorePlaylistShareActions() {
    document.querySelectorAll('[data-cliptap-hidden-share="true"]').forEach(el => {
      el.style.display = '';
      delete el.dataset.cliptapHiddenShare;
    });
  }

  function findPlaylistActionContainer() {
    return getPlaylistActionRow();
  }

  function mountPlaylistPageButton() {
    const mountedButtons = [...document.querySelectorAll('.cliptap-page-playlist-button')];
    if (!isPlaylistPageUrl()) {
      mountedButtons.forEach(el => el.remove());
      restorePlaylistShareActions();
      return;
    }

    const container = findPlaylistActionContainer();
    if (!container) return;

    const shareAction = findPlaylistShareAction(container);
    const moreAction = findPlaylistMoreAction(container);
    bindPlaylistMoreAction(moreAction);

    if (!shareAction && !moreAction) return;

    let button = mountedButtons.find(el => el.parentElement === container && el.dataset.cliptapPlaylistVersion === PLAYLIST_BUTTON_VERSION) || null;
    mountedButtons.filter(el => el !== button).forEach(el => el.remove());

    if (!button) {
      const template = shareAction || moreAction || container.querySelector('.ytFlexibleActionsViewModelActionIconOnlyButton, .ytFlexibleActionsViewModelActionRowAction');
      button = makePlaylistPageButtonElement(template);
    }

    hidePlaylistShareAction(shareAction);

    const anchor = shareAction?.parentElement === container ? shareAction : moreAction;
    if (anchor?.parentElement === container) {
      if (button.nextElementSibling !== anchor) container.insertBefore(button, anchor);
    } else if (button.parentElement !== container) {
      container.appendChild(button);
    }

    button.dataset.cliptapPlaylistVersion = PLAYLIST_BUTTON_VERSION;
  }

  function findWatchPlaylistToolbar() {
    const selectors = [
      '#playlist-action-menu #top-level-buttons-computed',
      'ytd-playlist-panel-renderer ytd-menu-renderer #top-level-buttons-computed',
      'ytd-playlist-panel-renderer #top-level-buttons-computed',
      '#playlist-action-menu > .ytd-playlist-panel-renderer.style-scope',
      'ytd-playlist-panel-renderer #playlist-action-menu',
      '#playlist-action-menu',
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

    const toolbar = findWatchPlaylistToolbar();
    if (!toolbar) return;

    if (mounted && mounted.parentElement === toolbar && mounted.dataset.cliptapPlaylistVersion === PLAYLIST_BUTTON_VERSION) return;
    mounted?.remove();

    const template = toolbar.querySelector('button, div[role="button"], yt-button-shape, ytd-toggle-button-renderer, ytd-button-renderer, tp-yt-paper-button');
    const button = makePlaylistButtonElement('watch', template);
    button.dataset.cliptapPlaylistVersion = PLAYLIST_BUTTON_VERSION;
    toolbar.appendChild(button);
  }

  function getChannelDownloadIcon() {
    return `<div aria-hidden="true" class="ytSpecButtonShapeNextIcon"><span class="ytIconWrapperHost" style="width: 24px; height: 24px;"><span class="yt-icon-shape ytSpecIconShapeHost"><div style="width: 100%; height: 100%; display: block; fill: currentcolor;"><svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 0 24 24" width="24" focusable="false" aria-hidden="true" style="pointer-events:none;display:inherit;width:100%;height:100%;"><path d="M12 2a1 1 0 00-1 1v11.586l-4.293-4.293a1 1 0 10-1.414 1.414L12 18.414l6.707-6.707a1 1 0 10-1.414-1.414L13 14.586V3a1 1 0 00-1-1Zm7 18H5a1 1 0 000 2h14a1 1 0 000-2Z"></path></svg></div></span></span></div>`;
  }


  const CHANNEL_DOWNLOAD_OPTIONS = [
    ['whole', 'Download whole channel'],
    ['videos', 'Download videos'],
    ['shorts', 'Download shorts'],
    ['lives', 'Download lives']
  ];

  function getChannelDownloadMenuIcon() {
    return `<div aria-hidden="true" class="ytListItemViewModelImageContainer ytListItemViewModelLeading"><span class="ytIconWrapperHost ytListItemViewModelAccessory ytListItemViewModelImage" role="img" aria-label="" aria-hidden="true"><span class="yt-icon-shape ytSpecIconShapeHost"><div style="width: 100%; height: 100%; display: block; fill: currentcolor;"><svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 0 24 24" width="24" focusable="false" aria-hidden="true" style="pointer-events:none;display:inherit;width:100%;height:100%;"><path d="M12 2a1 1 0 00-1 1v11.586l-4.293-4.293a1 1 0 10-1.414 1.414L12 18.414l6.707-6.707a1 1 0 10-1.414-1.414L13 14.586V3a1 1 0 00-1-1Zm7 18H5a1 1 0 000 2h14a1 1 0 000-2Z"></path></svg></div></span></span></div>`;
  }

  let channelDismissController = null;

  function clearChannelDismissListeners() {
    channelDismissController?.abort?.();
    channelDismissController = null;
  }

  function startChannelDownloadMenuDismissal(wrapper) {
    clearChannelDismissListeners();
    if (!wrapper) return;

    channelDismissController = new AbortController();
    const { signal } = channelDismissController;

    document.addEventListener('pointerdown', event => {
      if (event.target?.closest?.('.cliptap-channel-download-action, .cliptap-channel-download-popup')) return;
      closeChannelDownloadMenus();
    }, { capture: true, signal });

    document.addEventListener('keydown', event => {
      if (event.key !== 'Escape') return;
      closeChannelDownloadMenus();
    }, { capture: true, signal });

    window.addEventListener('yt-navigate-start', () => closeChannelDownloadMenus(), { capture: true, signal });
    window.addEventListener('resize', () => closeChannelDownloadMenus(), { capture: true, signal });
    window.addEventListener('scroll', () => closeChannelDownloadMenus(), { capture: true, signal });
  }

  function closeChannelDownloadMenus(except = null) {
    document.querySelectorAll('.cliptap-channel-download-popup').forEach(popup => {
      if (popup === except) return;
      popup.querySelectorAll('tp-yt-iron-dropdown').forEach(dropdown => {
        try { dropdown.opened = false; } catch {}
        try { dropdown.close?.(); } catch {}
        dropdown.removeAttribute('opened');
        dropdown.setAttribute('aria-hidden', 'true');
        dropdown.style.display = 'none';
      });
      popup.remove();
    });
    document.querySelectorAll('.cliptap-channel-download-action [aria-expanded="true"]').forEach(button => {
      button.setAttribute('aria-expanded', 'false');
    });
    document.querySelectorAll('.cliptap-channel-download-action[data-cliptap-channel-menu-open="true"]').forEach(wrapper => {
      wrapper.dataset.cliptapChannelMenuOpen = 'false';
    });
    if (!except) clearChannelDismissListeners();
  }

  function dispatchNativeMenuEscape(target) {
    try {
      target.dispatchEvent(new KeyboardEvent('keydown', {
        key: 'Escape',
        code: 'Escape',
        keyCode: 27,
        which: 27,
        bubbles: true,
        cancelable: true,
        composed: true
      }));
    } catch {}
  }

  function closeOpenYouTubeNativeActionMenus() {
    dispatchNativeMenuEscape(document);
    dispatchNativeMenuEscape(window);

    document.querySelectorAll('tp-yt-iron-dropdown[opened], tp-yt-iron-dropdown[aria-hidden="false"]').forEach(dropdown => {
      if (dropdown.closest('.cliptap-channel-download-popup, .cliptap-channel-download-action')) return;
      try { dropdown.opened = false; } catch {}
      try { dropdown.close?.(); } catch {}
      dropdown.removeAttribute('opened');
      dropdown.setAttribute('aria-hidden', 'true');
      dropdown.style.display = 'none';
    });

    document.querySelectorAll('.ytFlexibleActionsViewModelAction [aria-expanded="true"], yt-flexible-actions-view-model [aria-expanded="true"]').forEach(button => {
      if (button.closest('.cliptap-channel-download-action, .cliptap-channel-download-popup')) return;
      button.setAttribute('aria-expanded', 'false');
    });
  }

  function getChannelDownloadPopup(wrapper) {
    return document.querySelector(`.cliptap-channel-download-popup[data-cliptap-owner="${wrapper.dataset.cliptapChannelMenuOwner || ''}"]`);
  }

  function makeChannelDownloadMenuItem(kind, label, wrapper) {
    const item = document.createElement('yt-list-item-view-model');
    item.className = 'ytListItemViewModelHost cliptap-channel-download-menu-item';
    item.setAttribute('role', 'menuitem');
    item.setAttribute('tabindex', '0');
    item.dataset.cliptapChannelDownloadKind = kind;
    item.innerHTML = `<div class="ytListItemViewModelLayoutWrapper ytListItemViewModelContainer ytListItemViewModelCompact ytListItemViewModelTappable ytListItemViewModelInPopup ytListItemViewModelNoTrailingText"><div class="ytListItemViewModelMainContainer">${getChannelDownloadMenuIcon()}<button type="button" class="ytButtonOrAnchorHost ytButtonOrAnchorButton ytListItemViewModelButtonOrAnchor"><div class="ytListItemViewModelTextWrapper"><div class="ytListItemViewModelTitleWrapper"><span class="ytAttributedStringHost ytListItemViewModelTitle ytAttributedStringWhiteSpacePreWrap" role="text">${label}</span></div></div></button></div></div>`;

    const activate = event => {
      event.preventDefault();
      event.stopPropagation();
      closeChannelDownloadMenus();
      requestChannelDownload(wrapper, kind);
    };
    item.addEventListener('click', activate, true);
    item.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      activate(event);
    }, true);
    return item;
  }

  function buildChannelDownloadMenuSheet(wrapper) {
    const sheet = document.createElement('yt-sheet-view-model');
    sheet.className = 'ytSheetViewModelHost ytSheetViewModelContextual cliptap-channel-download-sheet';
    sheet.setAttribute('slot', 'dropdown-content');
    sheet.setAttribute('tabindex', '-1');
    sheet.style.outline = 'none';
    sheet.style.boxSizing = 'border-box';
    sheet.style.maxWidth = '280px';

    const layout = document.createElement('yt-contextual-sheet-layout');
    layout.className = 'ytContextualSheetLayoutHost';
    layout.innerHTML = '<div class="ytContextualSheetLayoutHeaderContainer"></div>';

    const content = document.createElement('div');
    content.className = 'ytContextualSheetLayoutContentContainer';
    const list = document.createElement('yt-list-view-model');
    list.className = 'ytListViewModelHost';
    list.setAttribute('role', 'menu');

    CHANNEL_DOWNLOAD_OPTIONS.forEach(([kind, label]) => {
      list.appendChild(makeChannelDownloadMenuItem(kind, label, wrapper));
    });

    content.appendChild(list);
    layout.appendChild(content);
    sheet.appendChild(layout);
    return sheet;
  }

  function ensureChannelDownloadPopupContent(dropdown, wrapper) {
    let contentWrapper = dropdown.querySelector(':scope > #contentWrapper');
    if (!contentWrapper) {
      contentWrapper = document.createElement('div');
      contentWrapper.id = 'contentWrapper';
      contentWrapper.className = 'style-scope tp-yt-iron-dropdown';
      dropdown.appendChild(contentWrapper);
    }

    if (!contentWrapper.querySelector('yt-list-item-view-model')) {
      contentWrapper.replaceChildren(buildChannelDownloadMenuSheet(wrapper));
    }
    return contentWrapper;
  }

  function openChannelDownloadDropdown(dropdown) {
    dropdown.style.display = 'block';
    dropdown.style.visibility = 'visible';
    dropdown.removeAttribute('aria-hidden');
    dropdown.setAttribute('aria-hidden', 'false');
    dropdown.setAttribute('opened', '');
    try { dropdown.opened = true; } catch {}
    try { dropdown.open(); } catch {}
  }

  function createChannelDownloadPopup(wrapper) {
    const owner = wrapper.dataset.cliptapChannelMenuOwner || `cliptap-channel-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    wrapper.dataset.cliptapChannelMenuOwner = owner;

    const popup = document.createElement('div');
    popup.className = 'style-scope ytd-app cliptap-channel-download-popup';
    popup.dataset.cliptapOwner = owner;

    const dropdown = document.createElement('tp-yt-iron-dropdown');
    dropdown.className = 'style-scope ytd-popup-container';
    dropdown.setAttribute('horizontal-align', 'auto');
    dropdown.setAttribute('vertical-align', 'top');
    dropdown.setAttribute('aria-disabled', 'false');
    dropdown.setAttribute('prevent-autonav', 'true');
    dropdown.style.outline = 'none';
    dropdown.style.maxWidth = '320px';
    dropdown.style.position = 'fixed';
    dropdown.style.zIndex = '2202';

    ensureChannelDownloadPopupContent(dropdown, wrapper);
    popup.appendChild(dropdown);

    const host = document.querySelector('ytd-app') || document.body || document.documentElement;
    host.appendChild(popup);
    ensureChannelDownloadPopupContent(dropdown, wrapper);
    positionChannelDownloadPopup(wrapper, dropdown);
    openChannelDownloadDropdown(dropdown);

    requestAnimationFrame(() => {
      if (!popup.isConnected) return;
      ensureChannelDownloadPopupContent(dropdown, wrapper);
      positionChannelDownloadPopup(wrapper, dropdown);
      openChannelDownloadDropdown(dropdown);
    });

    return popup;
  }

  function positionChannelDownloadPopup(wrapper, dropdown) {
    const trigger = wrapper.querySelector('button, a, div[role="button"]') || wrapper;
    const sheet = dropdown.querySelector('yt-sheet-view-model');
    const rect = trigger.getBoundingClientRect();
    const width = Math.min(280, Math.max(236, Math.round(rect.width + 96)));
    if (sheet) sheet.style.width = `${width}px`;
    const left = Math.max(8, Math.min(window.innerWidth - width - 8, Math.round(rect.left)));
    const top = Math.max(8, Math.min(window.innerHeight - 8, Math.round(rect.bottom + 8)));
    dropdown.style.left = `${left}px`;
    dropdown.style.top = `${top}px`;
  }

  function toggleChannelDownloadMenu(wrapper) {
    const trigger = wrapper.querySelector('button, a, div[role="button"]') || wrapper;
    const existing = getChannelDownloadPopup(wrapper);
    if (existing) {
      closeChannelDownloadMenus();
      return;
    }

    closeOpenYouTubeNativeActionMenus();
    closeChannelDownloadMenus();
    let popup = null;
    try {
      popup = createChannelDownloadPopup(wrapper);
      const dropdown = popup.querySelector('tp-yt-iron-dropdown');
      const firstItem = popup.querySelector('[role="menuitem"]');
      if (!dropdown || !firstItem) throw new Error('channel-menu-content-missing');
      trigger.setAttribute('aria-expanded', 'true');
      wrapper.dataset.cliptapChannelMenuOpen = 'true';
      startChannelDownloadMenuDismissal(wrapper);
      window.setTimeout(() => popup?.querySelector('[role="menuitem"]')?.focus(), 0);
    } catch (error) {
      popup?.remove();
      wrapper.dataset.cliptapChannelMenuOpen = 'false';
      wrapper.dataset.cliptapChannelMenuError = String(error?.message || error || 'menu-open-failed');
      trigger.setAttribute('aria-expanded', 'false');
      showClipTapFeedback('Could not open ClipTap channel menu.', true);
    }
  }

  function bindChannelDownloadMenuDismissal() {
    // Dismissal is attached only while the ClipTap channel menu is open.
    // Permanent document click handlers can block YouTube native action menus after ClipTap closes.
  }

  function getVisibleRect(element) {
    if (!element?.getBoundingClientRect) return null;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 ? rect : null;
  }

  function hasChannelSubscribeControl(element) {
    if (!element) return false;
    if (element.querySelector?.('yt-subscribe-button-view-model, ytd-subscribe-button-renderer')) return true;
    return /\bsubscribed?\b/i.test(actionText(element));
  }

  function findChannelActionsContainer() {
    const selectors = [
      'yt-page-header-renderer yt-flexible-actions-view-model.ytPageHeaderViewModelFlexibleActions',
      'yt-page-header-renderer .ytPageHeaderViewModelFlexibleActions',
      'ytd-tabbed-page-header yt-flexible-actions-view-model.ytPageHeaderViewModelFlexibleActions',
      'ytd-tabbed-page-header .ytPageHeaderViewModelFlexibleActions',
      'yt-flexible-actions-view-model.ytPageHeaderViewModelFlexibleActions',
      '.ytFlexibleActionsViewModelHost.ytPageHeaderViewModelFlexibleActions',
      'yt-page-header-renderer yt-flexible-actions-view-model',
      'ytd-tabbed-page-header yt-flexible-actions-view-model'
    ];

    const candidates = [];
    for (const selector of selectors) {
      document.querySelectorAll(selector).forEach(element => {
        if (!candidates.includes(element)) candidates.push(element);
      });
    }

    const visible = candidates.filter(element => getVisibleRect(element));
    return visible.find(hasChannelSubscribeControl) ||
      visible.find(element => element.querySelector?.('.ytFlexibleActionsViewModelAction, button, a')) ||
      candidates.find(hasChannelSubscribeControl) ||
      candidates.find(element => element.querySelector?.('.ytFlexibleActionsViewModelAction, button, a')) ||
      null;
  }

  function getChannelActionTemplate(container) {
    const actions = [...container.querySelectorAll(':scope > .ytFlexibleActionsViewModelAction')]
      .filter(action => !action.classList.contains('cliptap-channel-download-action'));
    const preferred = actions.find(action => actionText(action).includes('community')) ||
      actions.find(action => actionText(action).includes('join')) ||
      actions[actions.length - 1];
    return preferred || null;
  }

  function makeChannelDownloadButtonElement() {
    const wrapper = document.createElement('div');
    wrapper.className = 'ytFlexibleActionsViewModelAction cliptap-channel-download-action';
    wrapper.dataset.cliptapChannelMountedAt = 'visible-flexible-actions';

    const clickable = document.createElement('button');
    clickable.type = 'button';
    clickable.className = 'ytSpecButtonShapeNextHost ytSpecButtonShapeNextTonal ytSpecButtonShapeNextMono ytSpecButtonShapeNextSizeM ytSpecButtonShapeNextIconLeadingTrailing ytSpecButtonShapeNextDisableTextEllipsis ytSpecButtonShapeNextEnableBackdropFilterExperiment';
    clickable.title = '';
    clickable.setAttribute('aria-label', 'Download channel with ClipTap');
    clickable.setAttribute('aria-haspopup', 'menu');
    clickable.setAttribute('aria-expanded', 'false');
    clickable.setAttribute('aria-disabled', 'false');
    clickable.innerHTML = `${getChannelDownloadIcon()}<div class="ytSpecButtonShapeNextButtonTextContent"><span class="ytAttributedStringHost ytAttributedStringWhiteSpaceNoWrap" role="text">Download</span></div><div aria-hidden="true" class="ytSpecButtonShapeNextSecondaryIcon cliptap-channel-download-chevron"><span class="ytIconWrapperHost" style="width: 24px; height: 24px;"><span class="yt-icon-shape ytSpecIconShapeHost"><div style="width: 100%; height: 100%; display: block; fill: currentcolor;"><svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 0 24 24" width="24" focusable="false" aria-hidden="true" style="pointer-events:none;display:inherit;width:100%;height:100%;"><path d="M18.707 8.793a1 1 0 00-1.414 0L12 14.086 6.707 8.793a1 1 0 10-1.414 1.414L12 16.914l6.707-6.707a1 1 0 000-1.414Z"></path></svg></div></span></span></div><yt-touch-feedback-shape aria-hidden="true" class="ytSpecTouchFeedbackShapeHost ytSpecTouchFeedbackShapeTouchResponse"><div class="ytSpecTouchFeedbackShapeStroke"></div><div class="ytSpecTouchFeedbackShapeFill"></div></yt-touch-feedback-shape>`;

    wrapper.appendChild(clickable);
    wrapper.title = '';
    wrapper.setAttribute('aria-label', 'Download channel with ClipTap');
    wrapper.dataset.cliptapChannelVersion = CHANNEL_BUTTON_VERSION;
    wrapper.dataset.cliptapChannelMountedAt = 'visible-flexible-actions';

    wrapper.addEventListener('pointerdown', event => {
      if (event.button !== undefined && event.button !== 0) return;
      if (getChannelDownloadPopup(wrapper)) return;
      closeOpenYouTubeNativeActionMenus();
    }, true);
    wrapper.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      toggleChannelDownloadMenu(wrapper);
    }, true);
    wrapper.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ' && event.key !== 'ArrowDown') return;
      event.preventDefault();
      event.stopPropagation();
      toggleChannelDownloadMenu(wrapper);
    }, true);
    wrapper.dataset.cliptapChannelBound = CHANNEL_BUTTON_VERSION;

    return wrapper;
  }

  function mountChannelDownloadButton() {
    bindChannelDownloadMenuDismissal();
    const mountedButtons = [...document.querySelectorAll('.cliptap-channel-download-action')];
    if (!isChannelPageUrl()) {
      mountedButtons.forEach(el => el.remove());
      return false;
    }

    const container = findChannelActionsContainer();
    if (!container) {
      document.documentElement.dataset.cliptapChannelMountStatus = 'container-missing';
      return false;
    }

    document.documentElement.dataset.cliptapChannelMountStatus = 'container-found';
    let button = mountedButtons.find(el => el.parentElement === container && el.dataset.cliptapChannelVersion === CHANNEL_BUTTON_VERSION) || null;
    mountedButtons.filter(el => el !== button).forEach(el => el.remove());

    if (!button) {
      button = makeChannelDownloadButtonElement();
    }

    if (button.parentElement !== container) {
      container.appendChild(button);
    } else if (button.nextElementSibling) {
      container.appendChild(button);
    }

    button.dataset.cliptapChannelVersion = CHANNEL_BUTTON_VERSION;
    button.dataset.cliptapChannelMountedAt = 'visible-flexible-actions';
    document.documentElement.dataset.cliptapChannelMountStatus = 'mounted';
    return true;
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

  let playerToolbarMountWatcherStarted = false;

  function startPlayerToolbarMountWatcher() {
    if (playerToolbarMountWatcherStarted) return;
    playerToolbarMountWatcherStarted = true;

    const mount = () => {
      if (location.pathname !== '/watch') return;
      try {
        ensureStyle();
        ensureControlButton();
        renderButton();
      } catch (error) {
        console.warn('[ClipTap] player toolbar mount failed', error);
      }
    };

    ['yt-navigate-finish', 'ytd-navigate-finish', 'yt-page-data-updated'].forEach(name => {
      window.addEventListener(name, mount, true);
    });
    window.addEventListener('popstate', mount, true);
    window.addEventListener('hashchange', mount, true);

    [0, 80, 200, 500, 1000, 1800, 3000].forEach(delay => {
      window.setTimeout(mount, delay);
    });
    window.setInterval(mount, 900);
  }

  function render() {
    const safe = fn => {
      try { fn(); } catch (error) { console.warn('[ClipTap] render step failed', error); }
    };
    safe(resetForNewVideoIfNeeded);
    safe(ensureStyle);
    safe(mountChannelDownloadButton);
    safe(ensureControlButton);
    safe(ensurePanel);
    safe(ensureProgressOverlay);
    safe(mountPlaylistDownloadButtons);
    safe(renderButton);
    safe(renderPanel);
    safe(renderProgressOverlay);
  }

  function loadOptions() {
    if (!chrome?.storage?.sync) return;
    chrome.storage.sync.get(['cliptapQuality', 'cliptapCookie', 'cliptapForce'], values => {
      values = values || {};
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

  function startChannelMountWatcher() {
    if (document.documentElement.dataset.cliptapChannelMountWatcher === CHANNEL_BUTTON_VERSION) return;
    document.documentElement.dataset.cliptapChannelMountWatcher = CHANNEL_BUTTON_VERSION;

    const tryMount = () => {
      if (!isChannelPageUrl()) return;
      mountChannelDownloadButton();
    };

    const observer = new MutationObserver(() => {
      if (!isChannelPageUrl()) return;
      window.clearTimeout(startChannelMountWatcher.timer);
      startChannelMountWatcher.timer = window.setTimeout(tryMount, 80);
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });

    let attempts = 0;
    const interval = window.setInterval(() => {
      attempts += 1;
      if (mountChannelDownloadButton() || attempts > 80) window.clearInterval(interval);
    }, 250);
  }

  loadOptions();
  startChannelMountWatcher();
  startPlayerToolbarMountWatcher();
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
  observer.observe(document.documentElement, { childList: true, subtree: true });
  setInterval(scheduleRender, 1500);
})();
