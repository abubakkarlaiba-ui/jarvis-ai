/**
 * JARVIS Core Module
 * State management, API client, WebSocket, event bus, utilities
 */

window.JARVIS = window.JARVIS || {};

// ─── State Management ───────────────────────────────────────────────
JARVIS.state = {
    connected: false,
    micActive: false,
    theme: 'dark',
    currentTab: 'queue',
    system: {},
    workflows: [],
    tasks: []
};

// ─── Event Bus ──────────────────────────────────────────────────────
JARVIS.events = {
    _handlers: {},

    on(event, fn) {
        if (!this._handlers[event]) this._handlers[event] = [];
        this._handlers[event].push(fn);
        return () => this.off(event, fn);
    },

    off(event, fn) {
        if (!this._handlers[event]) return;
        this._handlers[event] = this._handlers[event].filter(h => h !== fn);
    },

    emit(event, data) {
        (this._handlers[event] || []).forEach(fn => {
            try { fn(data); } catch (e) { console.error(`Event "${event}" handler error:`, e); }
        });
    }
};

// ─── API Client ─────────────────────────────────────────────────────
JARVIS.api = {
    base: '/api',

    async request(method, path, data = null) {
        const url = this.base + path;
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (data && method !== 'GET') opts.body = JSON.stringify(data);

        const res = await fetch(url, opts);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `API error: ${res.status}`);
        }
        return res.json();
    },

    get(path)        { return this.request('GET', path); },
    post(path, data) { return this.request('POST', path, data); },
    put(path, data)  { return this.request('PUT', path, data); },
    del(path)        { return this.request('DELETE', path); }
};

// ─── WebSocket Manager ──────────────────────────────────────────────
JARVIS.ws = {
    socket: null,
    _reconnectDelay: 1000,
    _reconnectTimer: null,
    _messageHandlers: [],

    connect() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${location.host}/ws`;

        this.socket = new WebSocket(url);

        this.socket.onopen = () => {
            console.log('[WS] Connected');
            JARVIS.state.connected = true;
            this._reconnectDelay = 1000;
            JARVIS.events.emit('ws:connected');
        };

        this.socket.onclose = (e) => {
            console.log('[WS] Disconnected', e.code);
            JARVIS.state.connected = false;
            JARVIS.events.emit('ws:disconnected');
            this.reconnect();
        };

        this.socket.onerror = (err) => {
            console.error('[WS] Error:', err);
            JARVIS.events.emit('ws:error', err);
        };

        this.socket.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                JARVIS.events.emit('ws:message', data);
                this._messageHandlers.forEach(fn => fn(data));
            } catch (err) {
                console.error('[WS] Parse error:', err);
            }
        };
    },

    reconnect() {
        clearTimeout(this._reconnectTimer);
        console.log(`[WS] Reconnecting in ${this._reconnectDelay}ms...`);
        this._reconnectTimer = setTimeout(() => {
            this.connect();
            this._reconnectDelay = Math.min(this._reconnectDelay * 2, 30000);
        }, this._reconnectDelay);
    },

    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(typeof data === 'string' ? data : JSON.stringify(data));
        }
    },

    onMessage(fn) {
        this._messageHandlers.push(fn);
    }
};

// ─── Utilities ──────────────────────────────────────────────────────
JARVIS.utils = {
    formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    formatDuration(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        if (h > 0) return `${h}h ${m}m ${s}s`;
        if (m > 0) return `${m}m ${s}s`;
        return `${s}s`;
    },

    formatDate(date) {
        const d = new Date(date);
        return d.toLocaleString('en-US', {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    },

    generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
    },

    debounce(fn, ms) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), ms);
        };
    },

    throttle(fn, ms) {
        let last = 0;
        return (...args) => {
            const now = Date.now();
            if (now - last >= ms) {
                last = now;
                fn(...args);
            }
        };
    },

    escapeHtml(text) {
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return String(text).replace(/[&<>"']/g, c => map[c]);
    }
};

// ─── Particles ──────────────────────────────────────────────────────
JARVIS.particles = {
    init(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';
        for (let i = 0; i < 50; i++) {
            this.createParticle(container);
        }
        this.animate(container);
    },

    createParticle(container) {
        const p = document.createElement('div');
        p.className = 'particle';
        const size = Math.random() * 4 + 1;
        Object.assign(p.style, {
            width: size + 'px',
            height: size + 'px',
            left: Math.random() * 100 + '%',
            top: Math.random() * 100 + '%',
            opacity: Math.random() * 0.5 + 0.1,
            animationDuration: (Math.random() * 20 + 10) + 's',
            animationDelay: (Math.random() * 10) + 's'
        });
        container.appendChild(p);
    },

    animate(container) {
        const particles = container.querySelectorAll('.particle');
        particles.forEach(p => {
            const driftX = (Math.random() - 0.5) * 100;
            const driftY = (Math.random() - 0.5) * 100;
            p.animate([
                { transform: 'translate(0, 0)', opacity: p.style.opacity },
                { transform: `translate(${driftX}px, ${driftY}px)`, opacity: 0 }
            ], {
                duration: Math.random() * 20000 + 10000,
                iterations: Infinity,
                direction: 'alternate'
            });
        });
    }
};

// ─── Clock ──────────────────────────────────────────────────────────
JARVIS.clock = {
    _interval: null,

    init(elementId) {
        const el = document.getElementById(elementId);
        if (!el) return;
        this.update(el);
        this._interval = setInterval(() => this.update(el), 1000);
    },

    update(el) {
        const now = new Date();
        const h = String(now.getHours()).padStart(2, '0');
        const m = String(now.getMinutes()).padStart(2, '0');
        const s = String(now.getSeconds()).padStart(2, '0');
        el.textContent = `${h}:${m}:${s}`;
    }
};

console.log('[JARVIS] Core module loaded');
