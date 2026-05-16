(() => {
  const VERSION = '72';
  const DATA_KEY = 'cliptapPlayerTooltipBridgeLoader';

  function inject() {
    const root = document.documentElement || document.head;
    if (!root || root.dataset?.[DATA_KEY] === VERSION) return;
    const script = document.createElement('script');
    script.src = `${chrome.runtime.getURL('player-tooltip-bridge.js')}?v=${VERSION}`;
    script.dataset.cliptapPlayerTooltipBridge = VERSION;
    script.onload = () => script.remove();
    root.appendChild(script);
    if (root.dataset) root.dataset[DATA_KEY] = VERSION;
  }

  inject();
})();
