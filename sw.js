/**
 * Service Worker for OpenDismissal
 * Network-first strategy with no caching to prevent data consistency issues
 * Author: Kerry Hatcher
 */

const CACHE_VERSION = 'v2.1-no-cache-fixed';
const CACHE_NAME = 'opendismissal-' + CACHE_VERSION;

// Install event - skip caching entirely
self.addEventListener('install', function(event) {
    console.log('OpenDismissal Service Worker: Installing (No-Cache Mode)...');
    
    event.waitUntil(
        // Clear any existing caches
        caches.keys().then(function(cacheNames) {
            return Promise.all(
                cacheNames.map(function(cacheName) {
                    console.log('OpenDismissal Service Worker: Deleting cache:', cacheName);
                    return caches.delete(cacheName);
                })
            );
        }).then(function() {
            // Force the service worker to activate immediately
            return self.skipWaiting();
        })
    );
});

// Activate event - clean up all caches
self.addEventListener('activate', function(event) {
    console.log('OpenDismissal Service Worker: Activating (No-Cache Mode)...');
    
    event.waitUntil(
        caches.keys().then(function(cacheNames) {
            return Promise.all(
                cacheNames.map(function(cacheName) {
                    console.log('OpenDismissal Service Worker: Deleting cache:', cacheName);
                    return caches.delete(cacheName);
                })
            );
        }).then(function() {
            // Take control of all open pages
            return self.clients.claim();
        })
    );
});

// Fetch event - always use network, never cache
self.addEventListener('fetch', function(event) {
    // Only handle GET requests
    if (event.request.method !== 'GET') {
        return;
    }
    
    // Skip non-HTTP requests
    if (!event.request.url.startsWith('http')) {
        return;
    }
    
    console.log('OpenDismissal Service Worker: Network-only fetch for:', event.request.url);
    
    // Check if this is a CDN request (external resource)
    const isCDNRequest = !event.request.url.startsWith(self.location.origin);
    
    if (isCDNRequest) {
        // For CDN requests, fetch normally without custom headers to avoid CORS issues
        event.respondWith(
            fetch(event.request, {
                cache: 'no-store' // Still disable browser cache
            }).then(function(response) {
                return response; // Return CDN response as-is
            }).catch(function(error) {
                console.error('OpenDismissal Service Worker: CDN request failed:', error);
                throw error;
            })
        );
    } else {
        // For same-origin requests, add cache-busting headers
        event.respondWith(
            fetch(event.request, {
                cache: 'no-store', // Disable browser cache
                headers: {
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            }).then(function(response) {
                // Add no-cache headers to response for same-origin requests
                const modifiedResponse = new Response(response.body, {
                    status: response.status,
                    statusText: response.statusText,
                    headers: {
                        ...Object.fromEntries(response.headers.entries()),
                        'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0',
                        'Pragma': 'no-cache',
                        'Expires': '0'
                    }
                });
                
                return modifiedResponse;
            }).catch(function(error) {
                console.error('OpenDismissal Service Worker: Same-origin request failed:', error);
                
                // Provide offline fallback only for application pages
                if (event.request.url.includes('/dissmissal/') || 
                    event.request.url.includes('/admin/')) {
                return new Response(
                    `<!DOCTYPE html>
                    <html>
                    <head>
                        <title>OpenDismissal - Network Error</title>
                        <meta name="viewport" content="width=device-width, initial-scale=1">
                        <style>
                            body { 
                                font-family: system-ui, -apple-system, sans-serif; 
                                padding: 2rem; 
                                text-align: center; 
                                background-color: #f8f9fa;
                            }
                            .error-message {
                                max-width: 400px;
                                margin: 2rem auto;
                                padding: 2rem;
                                background: white;
                                border-radius: 8px;
                                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                border-left: 4px solid #dc3545;
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
                        <div class="error-message">
                            <div class="icon">🚫</div>
                            <h2>Network Error</h2>
                            <p>Unable to connect to OpenDismissal. Please check your internet connection and try again.</p>
                            <p><strong>Note:</strong> This app requires a live connection to ensure data accuracy.</p>
                            <button class="retry-btn" onclick="window.location.reload()">
                                Retry Connection
                            </button>
                        </div>
                    </body>
                    </html>`,
                    {
                        status: 503,
                        statusText: 'Service Unavailable',
                        headers: {
                            'Content-Type': 'text/html',
                            'Cache-Control': 'no-cache, no-store, must-revalidate',
                            'Pragma': 'no-cache',
                            'Expires': '0'
                        },
                    }
                );
            }
            
                // For other requests, let them fail naturally
                throw error;
            })
        );
    }
});

// Clear any stored data on message from main thread
self.addEventListener('message', function(event) {
    if (event.data && event.data.type === 'CLEAR_ALL_CACHES') {
        console.log('OpenDismissal Service Worker: Clearing all caches on request');
        event.waitUntil(
            caches.keys().then(function(cacheNames) {
                return Promise.all(
                    cacheNames.map(function(cacheName) {
                        return caches.delete(cacheName);
                    })
                );
            }).then(function() {
                // Notify main thread that caches are cleared
                event.ports[0].postMessage({success: true});
            })
        );
    }
});

// Disable background sync since we're not caching anything
self.addEventListener('sync', function(event) {
    console.log('OpenDismissal Service Worker: Background sync disabled in no-cache mode');
    // No-op since we're not caching form submissions
});

console.log('OpenDismissal Service Worker: Loaded in NO-CACHE mode - all requests will be fetched fresh from network');