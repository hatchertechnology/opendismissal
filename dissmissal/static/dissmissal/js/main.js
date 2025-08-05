/**
 * OpenDismissal Main JavaScript
 * Mobile-first interactive functionality for school dismissal management
 * Author: Nathan Clarke
 */

// Global utilities and configuration
const OpenDismissal = {
    config: {
        refreshInterval: 30000, // 30 seconds
        apiTimeout: 10000, // 10 seconds
        maxRetries: 3,
        apiEndpoints: {
            validateCode: '/dissmissal/api/validate-code/',
            status: '/dissmissal/api/status/'
        }
    },
    
    // Utility functions
    utils: {
        // Get CSRF token for Django forms
        getCsrfToken() {
            const token = document.querySelector('[name=csrfmiddlewaretoken]');
            return token ? token.value : '';
        },
        
        // Show user feedback messages
        showMessage(message, type = 'info', duration = 5000) {
            const alertClass = {
                'success': 'alert-success',
                'error': 'alert-danger',
                'warning': 'alert-warning',
                'info': 'alert-info'
            }[type] || 'alert-info';
            
            const icon = {
                'success': 'bi-check-circle',
                'error': 'bi-exclamation-triangle',
                'warning': 'bi-exclamation-circle',
                'info': 'bi-info-circle'
            }[type] || 'bi-info-circle';
            
            const alertHtml = `
                <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
                    <i class="bi ${icon} me-2"></i>
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;
            
            // Insert at top of messages container or create one
            let container = document.getElementById('messages-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'messages-container';
                document.querySelector('main').insertBefore(container, document.querySelector('main').firstChild);
            }
            
            container.insertAdjacentHTML('afterbegin', alertHtml);
            
            // Auto-dismiss after duration
            if (duration > 0) {
                setTimeout(() => {
                    const alert = container.querySelector('.alert');
                    if (alert) {
                        const bsAlert = new bootstrap.Alert(alert);
                        bsAlert.close();
                    }
                }, duration);
            }
        },
        
        // Format time for display
        formatTime(date) {
            return new Intl.DateTimeFormat('en-US', {
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            }).format(date);
        },
        
        // Format relative time (e.g., "5 minutes ago")
        formatRelativeTime(date) {
            const now = new Date();
            const diff = now - date;
            const minutes = Math.floor(diff / 60000);
            
            if (minutes < 1) return 'Just now';
            if (minutes === 1) return '1 minute ago';
            if (minutes < 60) return `${minutes} minutes ago`;
            
            const hours = Math.floor(minutes / 60);
            if (hours === 1) return '1 hour ago';
            if (hours < 24) return `${hours} hours ago`;
            
            return date.toLocaleDateString();
        },
        
        // Debounce function for performance
        debounce(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        },
        
        // Throttle function for performance
        throttle(func, limit) {
            let inThrottle;
            return function() {
                const args = arguments;
                const context = this;
                if (!inThrottle) {
                    func.apply(context, args);
                    inThrottle = true;
                    setTimeout(() => inThrottle = false, limit);
                }
            };
        }
    },
    
    // API interaction methods
    api: {
        async request(url, options = {}) {
            const defaultOptions = {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                timeout: OpenDismissal.config.apiTimeout
            };
            
            // Add CSRF token for POST requests
            if (options.method === 'POST') {
                defaultOptions.headers['X-CSRFToken'] = OpenDismissal.utils.getCsrfToken();
            }
            
            const config = { ...defaultOptions, ...options };
            
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), config.timeout);
                
                const response = await fetch(url, {
                    ...config,
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                return data;
            } catch (error) {
                if (error.name === 'AbortError') {
                    throw new Error('Request timed out');
                }
                throw error;
            }
        },
        
        async validateDismissalCode(code) {
            return this.request(OpenDismissal.config.apiEndpoints.validateCode, {
                method: 'POST',
                body: `code=${encodeURIComponent(code)}`
            });
        },
        
        async getDashboardStatus() {
            return this.request(OpenDismissal.config.apiEndpoints.status);
        },
        
        async refreshDashboard() {
            return this.request(OpenDismissal.config.apiEndpoints.status);
        }
    },
    
    // Initialize application
    init() {
        // Merge configuration from template if available
        if (window.OpenDismissalConfig) {
            this.config = { ...this.config, ...window.OpenDismissalConfig };
        }
        
        this.setupGlobalEventListeners();
        this.setupServiceWorker();
        this.setupNetworkMonitoring();
        this.setupPerformanceMonitoring();
        
        // Initialize page-specific functionality
        this.initializePage();
    },
    
    setupGlobalEventListeners() {
        // Global form handling
        document.addEventListener('submit', function(e) {
            const form = e.target;
            if (form.tagName === 'FORM') {
                const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
                if (submitBtn && !submitBtn.disabled) {
                    const originalText = submitBtn.innerHTML;
                    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
                    submitBtn.disabled = true;
                    
                    // Re-enable button after a timeout in case form doesn't redirect
                    setTimeout(() => {
                        submitBtn.innerHTML = originalText;
                        submitBtn.disabled = false;
                    }, 10000);
                }
            }
        });
        
        // Global keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            // Alt + D = Dashboard
            if (e.altKey && e.key === 'd') {
                e.preventDefault();
                window.location.href = '/dissmissal/';
            }
            
            // Alt + A = Parent Arrival
            if (e.altKey && e.key === 'a') {
                e.preventDefault();
                window.location.href = '/dissmissal/arrival/';
            }
            
            // Alt + P = Student Pickup
            if (e.altKey && e.key === 'p') {
                e.preventDefault();
                window.location.href = '/dissmissal/pickup/';
            }
            
            // Escape = Close modals
            if (e.key === 'Escape') {
                const openModal = document.querySelector('.modal.show');
                if (openModal) {
                    const modalInstance = bootstrap.Modal.getInstance(openModal);
                    if (modalInstance) {
                        modalInstance.hide();
                    }
                }
            }
        });
        
        // Touch and gesture handling for mobile
        if ('ontouchstart' in window) {
            this.setupTouchHandling();
        }
    },
    
    setupTouchHandling() {
        // Prevent double-tap zoom on buttons
        document.addEventListener('touchend', function(e) {
            if (e.target.tagName === 'BUTTON' || e.target.closest('button')) {
                e.preventDefault();
            }
        });
        
        // Swipe gestures for navigation
        let touchStartX = 0;
        let touchStartY = 0;
        
        document.addEventListener('touchstart', function(e) {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
        });
        
        document.addEventListener('touchend', function(e) {
            if (!touchStartX || !touchStartY) return;
            
            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;
            
            const deltaX = touchEndX - touchStartX;
            const deltaY = touchEndY - touchStartY;
            
            // Only process horizontal swipes
            if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 100) {
                // Swipe right = back
                if (deltaX > 0 && window.history.length > 1) {
                    window.history.back();
                }
                // Could add swipe left for forward navigation
            }
            
            touchStartX = 0;
            touchStartY = 0;
        });
    },
    
    setupServiceWorker() {
        // Register service worker for offline functionality
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/static/sw.js').then(function(registration) {
                console.log('OpenDismissal Service Worker registered successfully');
                
                // Listen for service worker updates
                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    if (newWorker) {
                        newWorker.addEventListener('statechange', () => {
                            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                                // New service worker available, notify user
                                OpenDismissal.utils.showMessage(
                                    'App updated! Refresh to use the latest version.', 
                                    'info', 
                                    10000
                                );
                            }
                        });
                    }
                });
            }).catch(function(error) {
                console.log('OpenDismissal Service Worker registration failed:', error);
            });
        }
    },
    
    setupNetworkMonitoring() {
        // Online/offline status monitoring
        window.addEventListener('online', () => {
            OpenDismissal.utils.showMessage('Connection restored', 'success');
            // Refresh data when back online
            if (typeof refreshDashboard === 'function') {
                refreshDashboard();
            }
        });
        
        window.addEventListener('offline', () => {
            OpenDismissal.utils.showMessage('You are offline. Some features may be limited.', 'warning', 0);
        });
        
        // Connection quality monitoring
        if ('connection' in navigator) {
            const connection = navigator.connection;
            
            if (connection.effectiveType === 'slow-2g' || connection.effectiveType === '2g') {
                OpenDismissal.utils.showMessage('Slow connection detected. Some features may be delayed.', 'warning');
            }
            
            connection.addEventListener('change', () => {
                if (connection.effectiveType === 'slow-2g' || connection.effectiveType === '2g') {
                    OpenDismissal.utils.showMessage('Connection quality changed. Performance may be affected.', 'info');
                }
            });
        }
    },
    
    setupPerformanceMonitoring() {
        // Performance monitoring for development and debugging
        if ('PerformanceObserver' in window) {
            const observer = new PerformanceObserver((list) => {
                list.getEntries().forEach((entry) => {
                    // Log slow operations for debugging
                    if (entry.duration > 100) {
                        console.warn(`OpenDismissal Performance: Slow operation detected - ${entry.name} took ${entry.duration.toFixed(2)}ms`);
                    }
                    
                    // Track API request performance
                    if (entry.name.includes('/dissmissal/api/')) {
                        console.log(`OpenDismissal API Performance: ${entry.name} - ${entry.duration.toFixed(2)}ms`);
                    }
                });
            });
            
            try {
                observer.observe({entryTypes: ['measure', 'navigation', 'resource']});
            } catch (e) {
                console.log('OpenDismissal: Performance monitoring not fully supported');
            }
        }
        
        // Track page load performance
        window.addEventListener('load', () => {
            if ('performance' in window && 'timing' in performance) {
                const timing = performance.timing;
                const loadTime = timing.loadEventEnd - timing.navigationStart;
                
                if (loadTime > 0) {
                    console.log(`OpenDismissal Page Load: ${loadTime}ms`);
                    
                    // Log slow page loads
                    if (loadTime > 3000) {
                        console.warn(`OpenDismissal: Slow page load detected - ${loadTime}ms`);
                    }
                }
            }
        });
    },
    
    initializePage() {
        const path = window.location.pathname;
        
        if (path.includes('/dissmissal/') && !path.includes('/admin/')) {
            if (path.endsWith('/') || path.includes('/dashboard')) {
                this.initDashboard();
            } else if (path.includes('/arrival/')) {
                this.initParentArrival();
            } else if (path.includes('/pickup/')) {
                this.initStudentPickup();
            }
        }
    },
    
    initDashboard() {
        // Dashboard-specific initialization handled in template
        console.log('Dashboard initialized');
    },
    
    initParentArrival() {
        // Parent arrival form enhancements
        const codeInput = document.querySelector('input[name="dismissal_code"]');
        if (codeInput) {
            // Auto-uppercase and format input
            codeInput.addEventListener('input', function(e) {
                let value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
                if (value.length > 8) value = value.substring(0, 8);
                e.target.value = value;
            });
            
            // Focus on load for quick entry
            codeInput.focus();
        }
    },
    
    initStudentPickup() {
        // Student pickup form enhancements
        console.log('Student pickup initialized');
    }
};

// Global utility functions (for backward compatibility)
function getCsrfToken() {
    return OpenDismissal.utils.getCsrfToken();
}

function showMessage(message, type, duration) {
    return OpenDismissal.utils.showMessage(message, type, duration);
}

function formatTime(date) {
    return OpenDismissal.utils.formatTime(date);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    OpenDismissal.init();
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = OpenDismissal;
}