JARVIS.app = {
  initialized: false,
  ws: null,

  init() {
    if (this.initialized) return;

    JARVIS.core?.init();
    JARVIS.voice?.init();
    JARVIS.system?.init();
    JARVIS.chat?.init();
    JARVIS.tasks?.init();
    JARVIS.notifications?.init();
    JARVIS.panels?.init();
    JARVIS.keyboard?.init();

    this.connectWebSocket();
    this.setupThemeToggle();
    this.setupFullscreenToggle();
    this.setupSettingsButton();
    this.setupClearChat();
    this.setupChatInputAutoResize();
    this.setupGlobalErrorHandler();

    this.loadThemePreference();

    JARVIS.notifications?.addNotification({
      type: 'info',
      message: 'Welcome to JARVIS'
    });

    this.initialized = true;
  },

  connectWebSocket() {
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      this.ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.routeWebSocketEvent(data);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected, reconnecting...');
        setTimeout(() => this.connectWebSocket(), 3000);
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (e) {
      console.error('Failed to connect WebSocket:', e);
    }
  },

  routeWebSocketEvent(data) {
    switch (data.type) {
      case 'system:stats':
        JARVIS.system?.updateUI(data.payload);
        break;
      case 'chat:message':
        JARVIS.chat?.addMessage(data.payload);
        break;
      case 'chat:stream':
        JARVIS.chat?.appendToStream(data.payload);
        break;
      case 'chat:stream:end':
        JARVIS.chat?.endStream(data.payload);
        break;
      case 'task:update':
        JARVIS.tasks?.updateTask(data.payload);
        break;
      case 'notification':
        JARVIS.notifications?.addNotification(data.payload);
        break;
    }
  },

  setupThemeToggle() {
    const btn = document.getElementById('theme-toggle');
    if (btn) {
      btn.addEventListener('click', () => this.toggleTheme());
    }
  },

  toggleTheme() {
    const body = document.body;
    const current = body.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    body.setAttribute('data-theme', next);
    localStorage.setItem('jarvis-theme', next);

    const icon = document.querySelector('#theme-toggle .icon');
    if (icon) {
      icon.textContent = next === 'dark' ? '🌙' : '☀️';
    }
  },

  loadThemePreference() {
    const saved = localStorage.getItem('jarvis-theme');
    if (saved) {
      document.body.setAttribute('data-theme', saved);
      const icon = document.querySelector('#theme-toggle .icon');
      if (icon) {
        icon.textContent = saved === 'dark' ? '🌙' : '☀️';
      }
    }
  },

  setupFullscreenToggle() {
    const btn = document.getElementById('fullscreen-toggle');
    if (btn) {
      btn.addEventListener('click', () => this.toggleFullscreen());
    }
  },

  toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(e => {
        console.error('Fullscreen error:', e);
      });
    } else {
      document.exitFullscreen();
    }
  },

  setupSettingsButton() {
    const btn = document.getElementById('settings-btn');
    if (btn) {
      btn.addEventListener('click', () => {
        document.dispatchEvent(new CustomEvent('settings:open'));
      });
    }
  },

  setupClearChat() {
    const btn = document.getElementById('clear-chat');
    if (btn) {
      btn.addEventListener('click', () => {
        JARVIS.chat?.clearChat();
      });
    }
  },

  setupChatInputAutoResize() {
    const input = document.getElementById('chat-input');
    if (input) {
      input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 150) + 'px';
      });
    }
  },

  setupGlobalErrorHandler() {
    window.addEventListener('error', (event) => {
      console.error('Unhandled error:', event.error);
      JARVIS.notifications?.addNotification({
        type: 'error',
        message: event.error?.message || 'An unexpected error occurred'
      });
    });

    window.addEventListener('unhandledrejection', (event) => {
      console.error('Unhandled rejection:', event.reason);
      JARVIS.notifications?.addNotification({
        type: 'error',
        message: event.reason?.message || 'An unexpected error occurred'
      });
    });
  }
};

document.addEventListener('DOMContentLoaded', () => JARVIS.app.init());
