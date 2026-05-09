(() => {
  if (window.__cliptapLoaded) return;
  window.__cliptapLoaded = true;

  const state = {
    start: null,
    end: null,
    quality: 'best',
    cookieBrowser: '',
    forceKeyframes: false,
    collapsed: false
  };

  function getVideo() {
    const videos = [...document.querySelectorAll('video')];
    return videos.find(v => !Number.isNaN(v.duration)) || videos[0] || null;
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

  function buildPanel() {
    if (document.getElementById('cliptap-panel')) return;

    const wrap = document.createElement('div');
    wrap.id = 'cliptap-panel';
    wrap.innerHTML = `
      <div class="cliptap-head">
        <b>ClipTap</b>
        <button type="button" data-action="toggle">접기</button>
      </div>
      <div class="cliptap-body">
        <div class="cliptap-line">현재 <strong data-role="now">00:00:00</strong></div>
        <div class="cliptap-line">시작 <strong data-role="start">--:--:--</strong></div>
        <div class="cliptap-line">끝 <strong data-role="end">--:--:--</strong></div>
        <div class="cliptap-buttons">
          <button type="button" data-action="start">시작 찍기</button>
          <button type="button" data-action="end">끝 찍기</button>
          <button type="button" data-action="download">받기</button>
        </div>
        <div class="cliptap-message" data-role="message"></div>
      </div>
    `;

    const style = document.createElement('style');
    style.textContent = `
      #cliptap-panel {
        position: fixed;
        right: 14px;
        bottom: 14px;
        z-index: 2147483647;
        width: 230px;
        background: #fff;
        color: #1f2937;
        border: 1px solid #cfd6df;
        border-radius: 6px;
        box-shadow: 0 2px 10px rgba(15, 23, 42, .14);
        font: 13px/1.35 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      #cliptap-panel button {
        font: inherit;
        border: 1px solid #c8ced8;
        border-radius: 5px;
        background: #f8fafc;
        color: #1f2937;
        min-height: 28px;
        cursor: pointer;
      }
      #cliptap-panel button:hover { background: #eef2f7; }
      #cliptap-panel .cliptap-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 9px;
        border-bottom: 1px solid #e1e5eb;
      }
      #cliptap-panel .cliptap-head b { font-size: 14px; }
      #cliptap-panel .cliptap-head button { width: 48px; min-height: 24px; font-size: 12px; }
      #cliptap-panel .cliptap-body { padding: 9px; }
      #cliptap-panel .cliptap-line {
        display: flex;
        justify-content: space-between;
        margin-bottom: 5px;
        color: #667085;
      }
      #cliptap-panel .cliptap-line strong { color: #1f2937; }
      #cliptap-panel .cliptap-buttons {
        display: grid;
        grid-template-columns: 1fr 1fr 52px;
        gap: 6px;
        margin-top: 8px;
      }
      #cliptap-panel .cliptap-buttons button:last-child {
        background: #245ea8;
        color: #fff;
        border-color: #245ea8;
      }
      #cliptap-panel .cliptap-message {
        min-height: 16px;
        margin-top: 7px;
        font-size: 12px;
        color: #667085;
      }
      #cliptap-panel.cliptap-collapsed { width: 112px; }
      #cliptap-panel.cliptap-collapsed .cliptap-body { display: none; }
      #cliptap-panel.cliptap-collapsed .cliptap-head { border-bottom: 0; }
    `;

    document.documentElement.appendChild(style);
    document.documentElement.appendChild(wrap);

    wrap.addEventListener('click', async event => {
      const action = event.target?.dataset?.action;
      if (!action) return;
      const video = getVideo();
      if (action === 'toggle') {
        state.collapsed = !state.collapsed;
        renderPanel();
        return;
      }
      if (!video) {
        setPanelMessage('video 태그를 못 찾았어.');
        return;
      }
      if (action === 'start') {
        state.start = video.currentTime;
        setPanelMessage('시작 지점 저장됨.');
      }
      if (action === 'end') {
        state.end = video.currentTime;
        setPanelMessage('끝 지점 저장됨.');
      }
      if (action === 'download') {
        await requestDownload();
      }
      renderPanel();
    });
  }

  function setPanelMessage(text) {
    const el = document.querySelector('#cliptap-panel [data-role="message"]');
    if (el) el.textContent = text;
  }

  function renderPanel() {
    const panel = document.getElementById('cliptap-panel');
    if (!panel) return;
    panel.classList.toggle('cliptap-collapsed', state.collapsed);
    const toggle = panel.querySelector('[data-action="toggle"]');
    if (toggle) toggle.textContent = state.collapsed ? '열기' : '접기';
    const video = getVideo();
    const now = video?.currentTime || 0;
    panel.querySelector('[data-role="now"]').textContent = secondsToClock(now);
    panel.querySelector('[data-role="start"]').textContent = state.start == null ? '--:--:--' : secondsToClock(state.start);
    panel.querySelector('[data-role="end"]').textContent = state.end == null ? '--:--:--' : secondsToClock(state.end);
  }

  async function requestDownload() {
    if (state.start == null || state.end == null) {
      setPanelMessage('시작/끝을 먼저 찍어줘.');
      return;
    }
    if (state.end <= state.start) {
      setPanelMessage('끝이 시작보다 뒤여야 해.');
      return;
    }

    try {
      setPanelMessage('헬퍼로 요청 보내는 중...');
      const res = await fetch('http://127.0.0.1:17723/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: location.href,
          title: getTitle(),
          start: state.start,
          end: state.end,
          quality: state.quality,
          cookieBrowser: state.cookieBrowser,
          forceKeyframes: state.forceKeyframes
        })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || '헬퍼 오류');
      setPanelMessage('다운로드 시작됨.');
    } catch (error) {
      setPanelMessage('헬퍼가 꺼졌거나 오류가 났어.');
      console.error('[ClipTap]', error);
    }
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== 'CLIPTAP_GET_STATE') return;
    const video = getVideo();
    sendResponse({
      url: location.href,
      title: getTitle(),
      currentTime: video?.currentTime || 0,
      duration: video?.duration || 0,
      hasVideo: Boolean(video)
    });
    return true;
  });

  buildPanel();
  setInterval(renderPanel, 500);
})();
