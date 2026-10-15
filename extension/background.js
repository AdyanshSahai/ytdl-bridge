function runDownload(url, mode, where, folder, limit, forceSingle) {
  chrome.runtime.sendNativeMessage('com.ytdlbridge.host', { url, mode, where, folder, limit, forceSingle }, (response) => {
    if (chrome.runtime.lastError) {
      console.error('Native messaging error:', chrome.runtime.lastError.message);
      return;
    }
    console.log('Native host response:', response);
  });
}

function runSync() {
  chrome.runtime.sendNativeMessage('com.ytdlbridge.host', { action: 'sync' }, (response) => {
    if (chrome.runtime.lastError) {
      console.error('Native messaging error:', chrome.runtime.lastError.message);
      return;
    }
    console.log('Native host response:', response);
  });
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: 'audio',
      title: '🎵 Download as audio',
      contexts: ['action']
    });
    chrome.contextMenus.create({
      id: 'video',
      title: '🎬 Download as video',
      contexts: ['action']
    });
    chrome.contextMenus.create({
      id: 'sync',
      title: '📱 Sync music to phone',
      contexts: ['action']
    });
  });
});

// Right-click: no popups, default dir (auto-named for playlists/channels), full length
chrome.contextMenus.onClicked.addListener((info) => {
  if (info.menuItemId === 'sync') { runSync(); return; }
  chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
    if (!tab?.url) return;
    const mode = info.menuItemId;
    const isMulti = tab.url.includes('&list=') || tab.url.includes('?list=') ||
                    /\/(@[^/]+|channel\/[^/]+|c\/[^/]+|user\/[^/]+)\/(videos|streams|shorts)?/.test(tab.url);
    const where = isMulti ? 'auto' : 'flat';
    const url = mode === 'audio'
      ? tab.url.replace('music.youtube.com', 'www.youtube.com')
      : tab.url;
    runDownload(url, mode, where, '', null, false);
  });
});

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === 'sync') {
    runSync();
  } else if (msg.action === 'download') {
    runDownload(msg.url, msg.mode, msg.where, msg.folder, msg.limit, msg.forceSingle);
  }
});

// Keyboard shortcut (Ctrl+Shift+Y) opens the popup automatically via
// "_execute_action" in manifest.json — no extra code needed here.

// Desktop notifications for batch/playlist completion are fired directly by
// the native host's bash command via `notify-send` (see host.py) rather than
// through the extension, since the terminal window outlives the popup.
