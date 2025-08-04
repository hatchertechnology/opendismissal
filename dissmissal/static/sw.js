/**
 * Service Worker for OpenDismissal
 * Provides offline functionality and caching for improved mobile experience
 * Author: Nathan Clarke
 */

const CACHE_NAME = 'opendismissal-v1';
const urlsToCache = [
    // Core application assets
    '/static/dissmissal/css/main.css',
    '/static/dissmissal/js/main.js',
    
    // CDN assets (Bootstrap)
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css',
    
    // Core application pages
    '/dissmissal/',
    '/dissmissal/arrival/',
    
    // API endpoints for offline caching
    '/dissmissal/api/status/',
];

// Install event - cache resources
self.addEventListener('install', function(event) {
    console.log('OpenDismissal Service Worker: Installing...');
    
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(function(cache) {
                console.log('OpenDismissal Service Worker: Caching app shell');
                return cache.addAll(urlsToCache);
            })
            .then(function() {
                // Force the service worker to activate immediately
                return self.skipWaiting();
            })
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', function(event) {
    console.log('OpenDismissal Service Worker: Activating...');
    
    event.waitUntil(
        caches.keys().then(function(cacheNames) {
            return Promise.all(
                cacheNames.map(function(cacheName) {
                    if (cacheName !== CACHE_NAME) {
                        console.log('OpenDismissal Service Worker: Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(function() {
            // Take control of all open pages
            return self.clients.claim();
        })
    );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', function(event) {
    // Only handle GET requests
    if (event.request.method !== 'GET') {
        return;
    }
    
    // Skip non-HTTP requests
    if (!event.request.url.startsWith('http')) {
        return;
    }
    
    event.respondWith(
        caches.match(event.request)
            .then(function(response) {
                // Return cached version if available
                if (response) {
                    console.log('OpenDismissal Service Worker: Serving from cache:', event.request.url);
                    return response;
                }
                
                // Otherwise, fetch from network
                return fetch(event.request).then(function(response) {
                    // Don't cache non-successful responses
                    if (!response || response.status !== 200 || response.type !== 'basic') {
                        return response;
                    }
                    
                    // Clone response for caching
                    const responseToCache = response.clone();
                    
                    // Cache new responses for future use
                    caches.open(CACHE_NAME)
                        .then(function(cache) {
                            // Only cache GET requests for app resources
                            if (event.request.url.includes('/dissmissal/') || 
                                event.request.url.includes('/static/')) {
                                cache.put(event.request, responseToCache);
                            }
                        });
                    
                    return response;
                });
            })
            .catch(function() {
                // If both cache and network fail, provide offline fallback
                if (event.request.url.includes('/dissmissal/')) {
                    return new Response(
                        `<!DOCTYPE html>
                        <html>
                        <head>
                            <title>OpenDismissal - Offline</title>
                            <meta name="viewport" content="width=device-width, initial-scale=1">
                            <style>
                                body { 
                                    font-family: system-ui, -apple-system, sans-serif; 
                                    padding: 2rem; 
                                    text-align: center; 
                                    background-color: #f8f9fa;
                                }
                                .offline-message {
                                    max-width: 400px;
                                    margin: 2rem auto;
                                    padding: 2rem;
                                    background: white;
                                    border-radius: 8px;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                }
                                .icon { font-size: 3rem; margin-bottom: 1rem; }
                                .retry-btn {
                                    background: #0d6efd;
                                    color: white;
                                    border: none;
                                    padding: 12px 24px;
                                    border-radius: 6px;
                                    font-size: 16px;
                                    cursor: pointer;
                                    margin-top: 1rem;
                                }
                                .retry-btn:hover { background: #0b5ed7; }
                            </style>
                        </head>
                        <body>
                            <div class="offline-message">
                                <div class="icon">📱</div>
                                <h2>You're Offline</h2>
                                <p>OpenDismissal is currently unavailable. Please check your internet connection and try again.</p>
                                <button class="retry-btn" onclick="window.location.reload()">
                                    Retry Connection
                                </button>
                            </div>
                        </body>
                        </html>`,
                        {
                            headers: {
                                'Content-Type': 'text/html',
                            },
                        }
                    );
                }
                
                // For other requests, let them fail naturally
                return new Response('Offline', { status: 503 });
            })
    );
});

// Background sync for form submissions when online
self.addEventListener('sync', function(event) {
    if (event.tag === 'background-sync') {
        console.log('OpenDismissal Service Worker: Background sync triggered');
        event.waitUntil(
            // Handle any queued form submissions
            syncFormSubmissions()
        );
    }
});

// Handle queued form submissions
function syncFormSubmissions() {
    return new Promise(function(resolve) {
        // Placeholder for future offline form submission functionality
        // This would retrieve queued submissions from IndexedDB and submit them
        console.log('OpenDismissal Service Worker: Syncing form submissions...');
        resolve();
    });
}