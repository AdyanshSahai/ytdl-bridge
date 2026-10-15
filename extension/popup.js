let currentURL = '';
let currentMode = null;
let contentType = 'single'; // 'single' | 'playlist' | 'channel'
let currentVideoId = null;  // the one video "just this one" means, if any

let whereMode = 'ytrips'; // 'ytrips' | 'auto' | 'custom'
let customFolder = '';

let howMode = 'one'; // 'all' | 'one' | 'count'  (default: just this one)

function getMode(url) {
  if (url.includes('music.youtube.com')) return 'audio';
  if (url.includes('youtube.com') || url.includes('youtu.be')) return 'video';
  return null;
}

function detectContentType(url) {
  if (url.includes('&list=') || url.includes('?list=')) return 'playlist';
  if (/\/(@[^/]+|channel\/[^/]+|c\/[^/]+|user\/[^/]+)\/(videos|streams|shorts)?/.test(url)) return 'channel';
  return 'single';
}

// video id straight from the url: watch?v=ID, youtu.be/ID, /shorts/ID, /live/ID
function videoIdFromUrl(url) {
  try {
    const u = new URL(url);
    if (u.hostname === 'youtu.be') return u.pathname.slice(1) || null;
    const m = u.pathname.match(/^\/(?:shorts|live)\/([\w-]{11})/);
    if (m) return m[1];
    return u.searchParams.get('v');
  } catch { return null; }
}

// what the player is actually playing. needed on YT Music, where playing a
// song from a playlist page leaves the url on /playlist?list=... with no v=.
// only used on music.youtube.com: on youtube.com the hidden watch player can
// hold a stale video from earlier in the session (e.g. while on a short).
async function videoIdFromPlayer(tabId) {
  try {
    const [res] = await chrome.scripting.executeScript({
      target: { tabId },
      world: 'MAIN',
      func: () => {
        const p = document.getElementById('movie_player');
        return (p && p.getVideoData && p.getVideoData().video_id) || null;
      },
    });
    return (res && res.result) || null;
  } catch { return null; }
}

function stripToVideo(url) {
  return currentVideoId ? `https://www.youtube.com/watch?v=${currentVideoId}` : url;
}

function convertMusicURL(url) {
  return url.replace('music.youtube.com', 'www.youtube.com');
}

function sanitizeFolderName(name) {
  // strip anything that isn't safe inside a double-quoted shell string:
  // quotes, backticks, $, backslashes, and path separators
  return name.replace(/["'`$\\/]/g, '').trim();
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  setTimeout(() => { t.textContent = ''; }, 2500);
}

// what was picked for "where to save". host.py turns this into a real folder
// using config.ini, so no paths live in the extension.
//   flat   -> the flat default folder
//   auto   -> a folder named after the playlist/channel (yt-dlp template)
//   custom -> a folder with the name the user typed
function getDestChoice() {
  if (whereMode === 'custom' && customFolder.trim()) {
    return { where: 'custom', folder: customFolder.trim() };
  }
  if (whereMode === 'auto') return { where: 'auto', folder: '' };
  return { where: 'flat', folder: '' };
}

function buildFinalURL() {
  // silent single-video override: if this page is just one video (not a
  // playlist/channel), always download it as a single video regardless of
  // what "how many" option is visually selected in the popup.
  if (contentType === 'single' || howMode === 'one') return stripToVideo(currentURL);
  return currentMode === 'audio' ? convertMusicURL(currentURL) : currentURL;
}

function download() {
  const url    = buildFinalURL();
  const { where, folder } = getDestChoice();
  const isSingleContent = contentType === 'single';
  const limit  = (!isSingleContent && howMode === 'count')
    ? (parseInt(document.getElementById('countInput').value) || 10)
    : null;
  // same silent override applied to forceSingle
  const single = isSingleContent || howMode === 'one';

  chrome.runtime.sendMessage({
    action: 'download',
    url,
    mode: currentMode,
    where,
    folder,
    limit,
    forceSingle: single
  });
  showToast('✓ Sent to terminal!');
}

document.getElementById('whereYtRips').addEventListener('click', () => {
  whereMode = 'ytrips';
  document.getElementById('whereYtRips').classList.add('selected');
  document.getElementById('whereAuto').classList.remove('selected');
  document.getElementById('whereCustom').classList.remove('selected');
  document.getElementById('folderInputRow').style.display = 'none';
});

document.getElementById('whereAuto').addEventListener('click', () => {
  whereMode = 'auto';
  document.getElementById('whereAuto').classList.add('selected');
  document.getElementById('whereYtRips').classList.remove('selected');
  document.getElementById('whereCustom').classList.remove('selected');
  document.getElementById('folderInputRow').style.display = 'none';
});

document.getElementById('whereCustom').addEventListener('click', () => {
  whereMode = 'custom';
  document.getElementById('whereCustom').classList.add('selected');
  document.getElementById('whereYtRips').classList.remove('selected');
  document.getElementById('whereAuto').classList.remove('selected');
  document.getElementById('folderInputRow').style.display = 'flex';
  document.getElementById('folderInput').focus();
});

document.getElementById('folderInput').addEventListener('input', (e) => {
  customFolder = sanitizeFolderName(e.target.value);
});

function setHowMode(mode) {
  howMode = mode;
  ['howAll','howOne','howCount'].forEach(id => {
    document.getElementById(id).classList.remove('selected');
  });
  document.getElementById(
    mode === 'all' ? 'howAll' : mode === 'one' ? 'howOne' : 'howCount'
  ).classList.add('selected');
  document.getElementById('countInputRow').style.display = mode === 'count' ? 'flex' : 'none';
}

document.getElementById('howAll').addEventListener('click',   () => setHowMode('all'));
document.getElementById('howOne').addEventListener('click',   () => setHowMode('one'));
document.getElementById('howCount').addEventListener('click', () => setHowMode('count'));

document.getElementById('btnConfirm').addEventListener('click', download);

function startDownload(mode) {
  currentMode = mode;

  // highlight the chosen mode button (and dim the other one)
  document.getElementById('btnAudio').classList.toggle('active', mode === 'audio');
  document.getElementById('btnVideo').classList.toggle('active', mode === 'video');
  document.getElementById('btnRow').classList.add('has-active');

  // labels follow the mode
  document.getElementById('howOne').textContent =
    mode === 'audio' ? '🎵 Just this song' : '🎬 Just this video';
  document.getElementById('btnConfirm').textContent =
    mode === 'audio' ? '⬇ Download audio' : '⬇ Download video';

  document.getElementById('wherePopup').classList.add('visible');
  document.getElementById('howPopup').classList.add('visible');
  document.getElementById('btnConfirm').style.display = 'block';
}

chrome.tabs.query({ active: true, currentWindow: true }, async ([tab]) => {
  const url = tab?.url || '';
  currentURL  = url;
  contentType = detectContentType(url);

  document.getElementById('urlBox').textContent = url || 'No URL';

  const mode = getMode(url);
  const badge = document.getElementById('modeBadge');
  const label = document.getElementById('modeLabel');
  const typeBadge = document.getElementById('typeBadge');

  if (mode === 'audio') {
    badge.className = 'mode-badge audio';
    label.textContent = 'YT Music → audio';
  } else if (mode === 'video') {
    badge.className = 'mode-badge video';
    label.textContent = 'YouTube → video';
  } else {
    badge.className = 'mode-badge none';
    label.textContent = 'Not a YouTube page';
    document.getElementById('controls').style.display = 'none';
    document.getElementById('unsupported').style.display = 'block';
    return;
  }

  if (contentType !== 'single') {
    typeBadge.style.display = 'inline-flex';
    typeBadge.textContent = contentType === 'channel' ? '📡 Channel' : '📃 Playlist';
  }

  currentVideoId = videoIdFromUrl(url);
  if (!currentVideoId && url.includes('music.youtube.com') && tab?.id != null) {
    currentVideoId = await videoIdFromPlayer(tab.id);
  }

  // "just this one" only makes sense when there's a video to pick. On a
  // bare playlist/channel page with nothing playing, hide it and default
  // to the whole thing instead.
  if (!currentVideoId) {
    document.getElementById('howOne').style.display = 'none';
    setHowMode('all');
  }

  document.getElementById('btnAudio').addEventListener('click', () => startDownload('audio'));
  document.getElementById('btnVideo').addEventListener('click', () => startDownload('video'));
});

document.getElementById('btnSync').addEventListener('click', () => {
  chrome.runtime.sendMessage({ action: 'sync' });
  showToast('Sync started in a terminal');
});
