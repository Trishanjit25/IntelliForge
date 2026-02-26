/* ============================================================
   IntelliForge  -  Premium SaaS Theme System & Utilities
   Enhanced with Touch/Click Animations
   ============================================================ */

// Theme System
class ThemeManager {
    constructor() {
        this.currentTheme = this.getStoredTheme() || this.getSystemTheme();
        this.init();
    }

    getSystemTheme() {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    getStoredTheme() {
        return localStorage.getItem('theme');
    }

    setStoredTheme(theme) {
        localStorage.setItem('theme', theme);
    }

    applyTheme(theme) {
        document.documentElement.classList.add('theme-transition');
        document.documentElement.setAttribute('data-theme', theme);
        
        // Update theme toggle button
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`);
        }
        
        // Remove transition class after animation completes
        setTimeout(() => {
            document.documentElement.classList.remove('theme-transition');
        }, 500);
    }

    toggleTheme() {
        const newTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
        this.currentTheme = newTheme;
        this.setStoredTheme(newTheme);
        this.applyTheme(newTheme);
    }

    init() {
        this.applyTheme(this.currentTheme);
        
        // Add event listener to theme toggle button
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }

        // Listen for system theme changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (!this.getStoredTheme()) {
                this.currentTheme = e.matches ? 'dark' : 'light';
                this.applyTheme(this.currentTheme);
            }
        });
    }
}

// Ripple Effect Handler
function createRipple(event) {
    const button = event.currentTarget;
    const rippleContainer = document.getElementById('ripple-container');
    
    if (!rippleContainer || !button) return;
    
    // Get position relative to viewport
    const rect = button.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    
    // Create ripple element
    const ripple = document.createElement('span');
    ripple.className = 'ripple';
    ripple.style.left = x + 'px';
    ripple.style.top = y + 'px';
    
    // Add to container
    rippleContainer.appendChild(ripple);
    
    // Remove after animation
    setTimeout(() => {
        ripple.remove();
    }, 600);
}

// Initialize ripple effects on all buttons
function initRippleEffects() {
    const buttons = document.querySelectorAll('.btn, .nav-link, .theme-toggle');
    buttons.forEach(button => {
        button.addEventListener('click', createRipple);
    });
}

// Touch feedback for mobile
function initTouchFeedback() {
    const touchElements = document.querySelectorAll('.btn, .glass, .feature-card, .project-card, .skill-tag');
    
    touchElements.forEach(element => {
        element.addEventListener('touchstart', function(e) {
            this.style.transform = this.style.transform || '';
            // Store original transform
            if (!this.dataset.originalTransform) {
                this.dataset.originalTransform = this.style.transform;
            }
        }, { passive: true });
        
        element.addEventListener('touchend', function(e) {
            setTimeout(() => {
                this.style.transform = this.dataset.originalTransform || '';
            }, 150);
        }, { passive: true });
    });
}

// Parallax scroll effect
function initParallax() {
    const elements = document.querySelectorAll('.orb, .light');
    
    window.addEventListener('scroll', () => {
        const scrollY = window.scrollY;
        
        elements.forEach((element, index) => {
            const speed = (index + 1) * 0.05;
            element.style.transform = `translateY(${scrollY * speed}px)`;
        });
    }, { passive: true });
}

// Mouse move subtle parallax for hero
function initHeroParallax() {
    const hero = document.querySelector('.hero');
    if (!hero) return;
    
    hero.addEventListener('mousemove', (e) => {
        const x = (e.clientX / window.innerWidth - 0.5) * 20;
        const y = (e.clientY / window.innerHeight - 0.5) * 20;
        
        const orbs = document.querySelectorAll('.orb');
        orbs.forEach((orb, index) => {
            const speed = (index + 1) * 0.5;
            orb.style.transform = `translate(${x * speed}px, ${y * speed}px)`;
        });
    });
}

// Initialize theme manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.themeManager = new ThemeManager();
    initRippleEffects();
    initTouchFeedback();
    initParallax();
    initHeroParallax();
});

/* --- Cookie/Token sync ---
   Ensures the access_token is always available as a cookie for
   server-side page loads, even in embedded iframe contexts where
   Set-Cookie from API responses may be blocked.                */
(function syncToken() {
    const token = localStorage.getItem('access_token');
    if (token) {
        const hasC = document.cookie.split(';').some(c => c.trim().startsWith('access_token='));
        if (!hasC) {
            document.cookie = 'access_token=' + token + '; path=/; max-age=86400; samesite=lax';
        }
    }
})();

function showAlert(message, type) {
    const box = document.getElementById('alert-box');
    if (!box) return;
    
    // Clear existing classes and add new ones
    box.className = 'alert ' + type;
    box.innerHTML = `
        <span class="alert-icon">${type === 'success' ? '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>' : type === 'error' ? '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>' : '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>'}</span>
        <span>${message}</span>
    `;
    box.classList.remove('hidden');
    box.classList.remove('fade-out');
    
    // Auto hide after 5 seconds
    setTimeout(() => {
        box.classList.add('fade-out');
        setTimeout(() => box.classList.add('hidden'), 300);
    }, 5000);
}

function getAuthHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    const token = localStorage.getItem('access_token');
    if (token) {
        headers['Authorization'] = 'Bearer ' + token;
    }
    return headers;
}

async function apiFetch(url, options = {}) {
    // Handle FormData specially - don't set Content-Type header
    const isFormData = options.body instanceof FormData;
    
    const defaults = {
        headers: isFormData ? {} : getAuthHeaders(),
        credentials: 'include',
    };
    
    const merged = { ...defaults, ...options };
    
    // For FormData, let the browser set the proper Content-Type with boundary
    if (isFormData) {
        // Remove Content-Type from headers to let browser set it
        if (merged.headers['Content-Type']) {
            delete merged.headers['Content-Type'];
        }
    } else if (options.headers) {
        merged.headers = { ...getAuthHeaders(), ...options.headers };
    }
    
    let resp;
    try {
        resp = await fetch(url, merged);
    } catch (fetchError) {
        throw new Error(`Network error: ${fetchError.message}`);
    }
    
    let data;
    try {
        data = await resp.json();
    } catch (jsonError) {
        // If response is not JSON (e.g., HTML error page)
        const text = await resp.text();
        throw new Error(`Server error (${resp.status}): ${text.substring(0, 200)}...`);
    }
    
    if (!resp.ok) {
        // Handle error properly - extract detail message
        const errorMessage = data.detail || data.message || 'Request failed';
        // If detail is an array (validation errors), join them
        if (Array.isArray(errorMessage)) {
            throw new Error(errorMessage.map(e => e.msg || e).join(', '));
        }
        // If detail is an object, stringify it properly
        if (typeof errorMessage === 'object') {
            throw new Error(JSON.stringify(errorMessage));
        }
        throw new Error(errorMessage);
    }
    return data;
}

// Enhanced scroll reveal animation
function initScrollReveal() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-fade-in-up');
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });

    // Observe elements with data-animate attribute
    document.querySelectorAll('[data-animate]').forEach(el => {
        observer.observe(el);
    });
}

// Enhanced loading states
function setLoadingState(button, loading = true) {
    if (loading) {
        button.disabled = true;
        button.setAttribute('data-original-text', button.innerHTML);
        button.innerHTML = '<span class="loading-spinner"></span> Please wait...';
    } else {
        button.disabled = false;
        const originalText = button.getAttribute('data-original-text');
        if (originalText) {
            button.innerHTML = originalText;
        }
    }
}

// Form validation with real-time feedback
function initFormValidation() {
    const inputs = document.querySelectorAll('input[required], textarea[required]');
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            if (!this.value.trim()) {
                this.classList.add('invalid');
            } else {
                this.classList.remove('invalid');
                this.classList.add('valid');
            }
        });
        
        input.addEventListener('input', function() {
            if (this.value.trim()) {
                this.classList.remove('invalid');
                this.classList.add('valid');
            } else {
                this.classList.remove('valid');
            }
        });
    });
}

// Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initScrollReveal();
    initFormValidation();
    
    // Add loading spinner styles
    const style = document.createElement('style');
    style.textContent = `
        .loading-spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid transparent;
            border-top: 2px solid currentColor;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 8px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        input.invalid {
            border-color: var(--danger) !important;
            box-shadow: 0 0 0 4px var(--danger-glow) !important;
        }
        input.valid {
            border-color: var(--success) !important;
            box-shadow: 0 0 0 4px var(--success-glow) !important;
        }
    `;
    document.head.appendChild(style);
});

/* Auth form handler */
async function handleAuth(e) {
    e.preventDefault();
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const btn = document.getElementById('auth-btn');

    const isSignup = typeof AUTH_MODE !== 'undefined' && AUTH_MODE === 'signup';
    const url = isSignup ? '/api/signup' : '/api/login';
    const body = { username, password };

    if (isSignup) {
        const emailEl = document.getElementById('email');
        if (emailEl) body.email = emailEl.value.trim();
    }

    setLoadingState(btn, true);

    try {
        const data = await apiFetch(url, { method: 'POST', body: JSON.stringify(body) });
        if (data.token) {
            localStorage.setItem('access_token', data.token);
            document.cookie = 'access_token=' + data.token + '; path=/; max-age=86400; samesite=lax';
        }
        window.location.href = '/dashboard';
    } catch (err) {
        showAlert(err.message, 'error');
        setLoadingState(btn, false);
    }
}

async function logout() {
    try {
        await fetch('/api/logout', { method: 'POST', credentials: 'include' });
    } catch (e) { /* ignore */ }
    localStorage.removeItem('access_token');
    document.cookie = 'access_token=; path=/; max-age=0';
    window.location.href = '/';
}
