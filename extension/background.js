function runDownload(url, mode, dest, limit, forceSingle) {
  chrome.runtime.sendNativeMessage('com.ytdlaudio.host', { url, mode, dest, limit, forceSingle }, (response) => {
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
      title: '🎵 Download as audio  (ydl-audio)',
      contexts: ['action']
    });
    chrome.contextMenus.create({
      id: 'video',
      title: '🎬 Download as video  (yt-dlp)',
      contexts: ['action']
    });
  });
});

// Right-click: no popups, default dir (auto-named for playlists/channels), full length
chrome.contextMenus.onClicked.addListener((info) => {
  chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
    if (!tab?.url) return;
    const mode = info.menuItemId;
    const isMulti = tab.url.includes('&list=') || tab.url.includes('?list=') ||
                    /\/(@[^/]+|channel\/[^/]+|c\/[^/]+|user\/[^/]+)\/(videos|streams|shorts)?/.test(tab.url);
    const base = mode === 'audio'
      ? '/mnt/storage/Music/yt-rips'
      : '/mnt/storage/Videos/yt-rips';
    const dest = isMulti ? base + '/__AUTO__' : base;
    const url = mode === 'audio'
      ? tab.url.replace('music.youtube.com', 'www.youtube.com')
      : tab.url;
    runDownload(url, mode, dest, null, false);
  });
});

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === 'download') {
    runDownload(msg.url, msg.mode, msg.dest, msg.limit, msg.forceSingle);
  }
});

// Keyboard shortcut (Ctrl+Shift+Y) opens the popup automatically via
// "_execute_action" in manifest.json — no extra code needed here.

// Desktop notifications for batch/playlist completion are fired directly by
// the native host's bash command via `notify-send` (see host.py) rather than
// through the extension, since the terminal window outlives the popup.
