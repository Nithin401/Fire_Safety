/**
 * FireShield AI - Web Push Service Worker
 * Handles background push notifications and notification click actions.
 */

self.addEventListener('install', function(event) {
  self.skipWaiting();
});

self.addEventListener('activate', function(event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', function(event) {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = {
        title: 'FireShield AI Alert',
        body: event.data.text()
      };
    }
  }

  const title = data.title || 'FireShield AI Alert';
  const options = {
    body: data.body || 'Hazard risk state updated.',
    icon: data.icon || '/static/icons/icon-192.png',
    badge: data.badge || '/static/icons/badge-72.png',
    vibrate: [200, 100, 200, 100, 400],
    tag: data.event_id || 'fireshield-alert',
    renotify: true,
    requireInteraction: data.severity === 'CRITICAL' || data.severity === 'HIGH',
    data: {
      url: data.url || '/',
      event_id: data.event_id,
      timestamp: data.timestamp || new Date().toISOString()
    }
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();

  const targetUrl = (event.notification.data && event.notification.data.url) ? event.notification.data.url : '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      // If a window is already open, focus it
      for (let i = 0; i < clientList.length; i++) {
        const client = clientList[i];
        if (client.url.includes(self.registration.scope) && 'focus' in client) {
          return client.focus();
        }
      }
      // Otherwise open a new window
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
