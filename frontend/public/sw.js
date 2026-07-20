/* Service worker: app-shell caching + push notifications.
   Hand-rolled and small on purpose — no build-time generation. */

const CACHE = 'todo-shell-v1'

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((c) => c.add('/'))
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  if (event.request.method !== 'GET' || url.origin !== location.origin) return
  if (url.pathname.startsWith('/api/') || url.pathname === '/healthz') return

  // Navigations: fresh HTML when online (it references the newest hashed
  // assets), cached shell when offline.
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const copy = res.clone()
          caches.open(CACHE).then((c) => c.put('/', copy))
          return res
        })
        .catch(() => caches.match('/')),
    )
    return
  }

  // Hashed build assets + icons: cache-first (filenames change per build).
  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/')) {
    event.respondWith(
      caches.match(event.request).then(
        (hit) =>
          hit ||
          fetch(event.request).then((res) => {
            const copy = res.clone()
            caches.open(CACHE).then((c) => c.put(event.request, copy))
            return res
          }),
      ),
    )
  }
})

self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch {
    /* non-JSON push — show a generic notification */
  }
  // "Mark done" straight from the notification bar for actionable pushes.
  // Android/desktop Chrome show the button; iOS ignores `actions` (no
  // support) and stays tap-to-open.
  const actionable = data.todo_id && (data.type === 'reminder' || data.type === 'assigned')
  event.waitUntil(
    self.registration.showNotification(data.title || 'Todo', {
      body: data.body || '',
      tag: data.tag,
      data: { url: data.url || '/', todo_id: data.todo_id || null },
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
      actions: actionable ? [{ action: 'complete', title: '✓ Mark done' }] : [],
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const data = event.notification.data || {}
  if (event.action === 'complete' && data.todo_id) {
    // Same-origin fetch from the SW: session cookie rides along
    // (SameSite=Lax) and the Origin header satisfies the CSRF guard.
    // On a group todo this checks off MY box — exactly what a prayer
    // reminder wants.
    event.waitUntil(
      fetch(`/api/todos/${data.todo_id}/complete`, {
        method: 'POST',
        credentials: 'include',
      }).then(
        (res) => {
          if (!res.ok) throw new Error('complete failed')
        },
        () =>
          self.registration.showNotification('Couldn’t mark it done', {
            body: 'Tap to open the app and try there.',
            tag: 'complete-failed',
            data: { url: data.url || '/' },
            icon: '/icons/icon-192.png',
            badge: '/icons/icon-192.png',
          }),
      ),
    )
    return
  }
  const url = data.url || '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ('focus' in client) {
          client.navigate(url)
          return client.focus()
        }
      }
      return self.clients.openWindow(url)
    }),
  )
})
