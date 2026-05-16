(() => {
  const BRIDGE_VERSION = '72';
  const EVENT_NAME = 'cliptap:bind-native-player-tooltip';
  const BUTTON_ID = 'cliptap-control-button';
  const TOOLTIP_TEXT = 'Download with ClipTap';
  const TOOLTIP_EVENT_TYPES = new Set(['mouseover', 'focus']);

  const previous = window.__cliptapNativeTooltipState || {};
  if (previous.version === BRIDGE_VERSION && previous.active) {
    previous.bind?.();
    return;
  }

  const state = {
    version: BRIDGE_VERSION,
    active: true,
    originalAddEventListener: previous.originalAddEventListener || EventTarget.prototype.addEventListener,
    originalRemoveEventListener: previous.originalRemoveEventListener || EventTarget.prototype.removeEventListener,
    captured: previous.captured || [],
    bound: previous.bound || [],
    bindTimer: 0,
    retryTimer: 0,
    retryCount: 0,
    lastLog: '',
    installedAt: Date.now()
  };

  window.__cliptapNativeTooltipState = state;
  window.__cliptapNativeTooltipDebug = {
    version: BRIDGE_VERSION,
    captured: state.captured,
    bound: state.bound,
    strategy: 'capture-native-addEventListener-handlers'
  };

  function debug(message, detail) {
    const key = `${message}:${detail?.message || detail || ''}`;
    if (state.lastLog === key) return;
    state.lastLog = key;
    try {
      console.debug?.(`[ClipTap] ${message}`, detail || '');
    } catch (_) {}
  }

  function getClassName(element) {
    try {
      return typeof element?.className === 'string' ? element.className : String(element?.className || '');
    } catch (_) {
      return '';
    }
  }

  function isElement(value) {
    return typeof Element !== 'undefined' && value instanceof Element;
  }

  function isClipTapButton(element) {
    return isElement(element) && element.id === BUTTON_ID;
  }

  function isNativeTooltipButton(element) {
    if (!isElement(element) || isClipTapButton(element)) return false;
    const className = getClassName(element);
    if (!className.includes('ytp-button')) return false;

    const hasTooltipText = element.hasAttribute('data-tooltip-title')
      || element.hasAttribute('data-title-no-tooltip')
      || element.hasAttribute('title')
      || element.hasAttribute('aria-label');

    if (!hasTooltipText) return false;

    try {
      return !!element.closest('#movie_player, .html5-video-player');
    } catch (_) {
      return true;
    }
  }

  function getSourceName(element) {
    if (!isElement(element)) return 'unknown';
    if (element.id) return `#${element.id}`;
    const className = getClassName(element).trim().replace(/\s+/g, '.');
    return className ? `.${className}` : element.tagName.toLowerCase();
  }

  function optionCapture(options) {
    if (typeof options === 'boolean') return options;
    return !!options?.capture;
  }

  function listenerExists(type, listener, capture) {
    return state.captured.some(record => record.type === type && record.listener === listener && record.capture === capture);
  }

  function captureNativeTooltipListener(target, type, listener, options) {
    if (!TOOLTIP_EVENT_TYPES.has(type)) return;
    if (!listener || (typeof listener !== 'function' && typeof listener.handleEvent !== 'function')) return;
    if (!isNativeTooltipButton(target)) return;

    const capture = optionCapture(options);
    if (listenerExists(type, listener, capture)) return;

    const record = {
      type,
      listener,
      options,
      capture,
      source: getSourceName(target),
      capturedAt: Date.now()
    };
    state.captured.push(record);
    debug('captured native YouTube tooltip listener', {
      type,
      source: record.source,
      capture,
      count: state.captured.length
    });
    scheduleBind(0);
  }

  function installAddEventListenerHook() {
    if (state.hookInstalled) return;
    const originalAdd = state.originalAddEventListener;
    if (typeof originalAdd !== 'function') return;

    const wrappedAddEventListener = function(type, listener, options) {
      const result = originalAdd.apply(this, arguments);
      try {
        captureNativeTooltipListener(this, String(type), listener, options);
      } catch (error) {
        debug('failed while capturing native tooltip listener', error);
      }
      return result;
    };

    try {
      Object.defineProperty(wrappedAddEventListener, 'name', { value: 'cliptapWrappedAddEventListener' });
    } catch (_) {}

    EventTarget.prototype.addEventListener = wrappedAddEventListener;
    state.hookInstalled = true;
    debug('installed native tooltip listener capture hook', 'EventTarget.prototype.addEventListener');
  }

  function normalizeButton(button, text, buttonId) {
    button.title = '';
    button.setAttribute('aria-label', text);
    button.setAttribute('data-tooltip-title', text);
    button.setAttribute('data-tooltip-target-id', buttonId);
    button.setAttribute('data-title-no-tooltip', text);
    button.removeAttribute('aria-describedby');
    button.removeAttribute('data-cliptap-native-tooltip-error');
  }

  function markStatus(button, status, source) {
    if (!button) return;
    button.setAttribute('data-cliptap-native-tooltip-status', status);
    if (source) button.setAttribute('data-cliptap-native-tooltip-source', source);
  }

  function parsePayload(raw) {
    if (typeof raw !== 'string') {
      return { buttonId: BUTTON_ID, text: TOOLTIP_TEXT, version: BRIDGE_VERSION };
    }
    try {
      const parsed = JSON.parse(raw);
      return {
        buttonId: parsed.buttonId || BUTTON_ID,
        text: parsed.text || TOOLTIP_TEXT,
        version: parsed.version || BRIDGE_VERSION
      };
    } catch (_) {
      return { buttonId: BUTTON_ID, text: TOOLTIP_TEXT, version: BRIDGE_VERSION };
    }
  }

  function hasInitialTooltipListeners() {
    return state.captured.some(record => record.type === 'mouseover')
      && state.captured.some(record => record.type === 'focus');
  }

  function alreadyBound(button, record) {
    return state.bound.some(item => item.button === button && item.type === record.type && item.listener === record.listener && item.capture === record.capture);
  }

  function bindCapturedListeners(buttonId = BUTTON_ID, text = TOOLTIP_TEXT, version = BRIDGE_VERSION) {
    const button = document.getElementById(buttonId);
    if (!button) return false;

    normalizeButton(button, text, buttonId);

    if (button.dataset.cliptapNativeTooltipBound === version && button.dataset.cliptapNativeTooltipStatus === 'bound-listeners') {
      return true;
    }

    if (!hasInitialTooltipListeners()) {
      button.setAttribute('data-cliptap-native-tooltip-error', 'listeners-missing');
      button.setAttribute('data-cliptap-native-tooltip-listener-count', String(state.captured.length));
      markStatus(button, 'waiting-listeners');
      return false;
    }

    let added = 0;
    const sources = new Set();
    for (const record of state.captured) {
      if (!TOOLTIP_EVENT_TYPES.has(record.type)) continue;
      if (alreadyBound(button, record)) continue;
      try {
        state.originalAddEventListener.call(button, record.type, record.listener, record.options);
        state.bound.push({
          button,
          type: record.type,
          listener: record.listener,
          capture: record.capture,
          source: record.source,
          version
        });
        sources.add(record.source);
        added += 1;
      } catch (error) {
        button.setAttribute('data-cliptap-native-tooltip-error', `bind:${error?.message || error}`);
        markStatus(button, 'bind-error');
        debug('failed to bind captured native tooltip listener', error);
        return false;
      }
    }

    button.dataset.cliptapNativeTooltipBound = version;
    button.setAttribute('data-cliptap-native-tooltip-listener-count', String(state.captured.length));
    button.removeAttribute('data-cliptap-native-tooltip-error');
    markStatus(button, 'bound-listeners', [...sources].join(',') || 'captured-native-listeners');
    debug('bound ClipTap button to captured native YouTube tooltip listeners', {
      added,
      captured: state.captured.length,
      sources: [...sources]
    });
    return true;
  }

  function scheduleBind(delay = 0, buttonId = BUTTON_ID, text = TOOLTIP_TEXT, version = BRIDGE_VERSION) {
    window.clearTimeout(state.bindTimer);
    state.bindTimer = window.setTimeout(() => bindCapturedListeners(buttonId, text, version), delay);
  }

  function retryBind() {
    scheduleBind(0);
    window.clearTimeout(state.retryTimer);
    const button = document.getElementById(BUTTON_ID);
    const bound = button?.dataset.cliptapNativeTooltipBound === BRIDGE_VERSION
      && button?.dataset.cliptapNativeTooltipStatus === 'bound-listeners';
    if (bound) {
      state.retryCount = 0;
      return;
    }

    if (state.retryCount < 80) {
      state.retryCount += 1;
      state.retryTimer = window.setTimeout(retryBind, Math.min(1500, 80 + state.retryCount * 40));
      return;
    }

    if (button) {
      button.setAttribute('data-cliptap-native-tooltip-error', button.getAttribute('data-cliptap-native-tooltip-error') || 'listener-registration-timeout');
      button.setAttribute('data-cliptap-native-tooltip-listener-count', String(state.captured.length));
      markStatus(button, 'listener-registration-timeout');
    }
    debug('native YouTube tooltip listener capture timed out', {
      captured: state.captured.map(record => ({ type: record.type, source: record.source, capture: record.capture }))
    });
  }

  installAddEventListenerHook();

  if (!state.observer) {
    state.observer = new MutationObserver(() => scheduleBind(0));
    state.observer.observe(document.documentElement || document, { childList: true, subtree: true });
  }

  if (!state.eventListenerInstalled) {
    window.addEventListener(EVENT_NAME, event => {
      const { buttonId, text, version } = parsePayload(event.detail);
      scheduleBind(0, buttonId, text, version);
    });
    state.eventListenerInstalled = true;
  }

  state.bind = () => scheduleBind(0);
  retryBind();
})();
