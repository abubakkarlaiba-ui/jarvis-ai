JARVIS.keyboard = {
  shortcuts: {},

  init() {
    this.registerDefaultShortcuts();
    document.addEventListener('keydown', (e) => this.handleKeydown(e));
  },

  register(key, modifiers, callback, description) {
    this.shortcuts[key] = { modifiers, callback, description };
  },

  registerDefaultShortcuts() {
    this.register('space', { shift: false, ctrl: false, alt: false }, () => {
      if (document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        JARVIS.voice?.toggle();
      }
    }, 'Toggle microphone');

    this.register('enter', { shift: false, ctrl: false, alt: false }, (e) => {
      if (document.activeElement.id === 'chat-input') {
        e.preventDefault();
        JARVIS.chat?.sendMessage();
      }
    }, 'Send message');

    this.register('enter', { shift: true, ctrl: false, alt: false }, () => {
      // Allow default newline behavior
    }, 'New line');

    this.register('k', { shift: false, ctrl: true, alt: false }, (e) => {
      e.preventDefault();
      document.dispatchEvent(new CustomEvent('quick-command:toggle'));
    }, 'Quick command');

    this.register('/', { shift: false, ctrl: true, alt: false }, (e) => {
      e.preventDefault();
      this.toggleShortcutsOverlay();
    }, 'Toggle shortcuts');

    this.register('t', { shift: false, ctrl: false, alt: false }, () => {
      if (document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        JARVIS.app?.toggleTheme();
      }
    }, 'Toggle theme');

    this.register('f', { shift: false, ctrl: false, alt: false }, () => {
      if (document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        JARVIS.app?.toggleFullscreen();
      }
    }, 'Toggle fullscreen');

    this.register('1', { shift: false, ctrl: false, alt: false }, () => {
      if (document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        JARVIS.tasks?.switchTab(0);
      }
    }, 'Switch to tab 1');

    this.register('2', { shift: false, ctrl: false, alt: false }, () => {
      if (document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        JARVIS.tasks?.switchTab(1);
      }
    }, 'Switch to tab 2');

    this.register('3', { shift: false, ctrl: false, alt: false }, () => {
      if (document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        JARVIS.tasks?.switchTab(2);
      }
    }, 'Switch to tab 3');

    this.register('escape', { shift: false, ctrl: false, alt: false }, () => {
      this.hideShortcutsOverlay();
      document.activeElement.blur();
    }, 'Close overlays');
  },

  handleKeydown(event) {
    const key = event.key.toLowerCase();
    const modifiers = {
      shift: event.shiftKey,
      ctrl: event.ctrlKey || event.metaKey,
      alt: event.altKey
    };

    for (const [shortcutKey, shortcut] of Object.entries(this.shortcuts)) {
      if (shortcut.modifiers.ctrl === modifiers.ctrl &&
          shortcut.modifiers.alt === modifiers.alt &&
          shortcut.modifiers.shift === modifiers.shift &&
          key === shortcutKey) {
        shortcut.callback(event);
        return;
      }
    }
  },

  toggleShortcutsOverlay() {
    const overlay = document.getElementById('shortcuts-overlay');
    if (!overlay) return;
    overlay.classList.toggle('hidden');
  },

  showShortcuts() {
    const overlay = document.getElementById('shortcuts-overlay');
    if (overlay) overlay.classList.remove('hidden');
  },

  hideShortcuts() {
    const overlay = document.getElementById('shortcuts-overlay');
    if (overlay) overlay.classList.add('hidden');
  },

  announceToScreenReader(text) {
    let region = document.getElementById('sr-announcer');
    if (!region) {
      region = document.createElement('div');
      region.id = 'sr-announcer';
      region.setAttribute('aria-live', 'polite');
      region.setAttribute('aria-atomic', 'true');
      region.className = 'sr-only';
      document.body.appendChild(region);
    }
    region.textContent = text;
  }
};
