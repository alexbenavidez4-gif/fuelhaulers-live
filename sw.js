/* fuelhaulers.live app helper.
   Always loads the newest page from the internet. If the phone has no signal,
   it shows the last copy it saved so the app (and the HOS Recap app) still opens. */
const CACHE = 'fhl-v2';
const PAGES = ['/', '/recap'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => Promise.all(PAGES.map(p => c.add(p).catch(() => {})))));
  self.skipWaiting();
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});
function pageKey(url) {
  const p = new URL(url).pathname.replace(/\.html$/, '');
  return p.startsWith('/recap') ? '/recap' : '/';
}
self.addEventListener('fetch', e => {
  if (e.request.mode !== 'navigate') return; /* only pages; data always comes live */
  const key = pageKey(e.request.url);
  e.respondWith(
    fetch(e.request).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(key, copy)); }
      return res;
    }).catch(() => caches.match(key).then(r => r || caches.match('/')))
  );
});
