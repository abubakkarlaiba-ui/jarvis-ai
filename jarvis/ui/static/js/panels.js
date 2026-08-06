JARVIS.panels = {
  collapsed: {},

  init() {
    this.loadState();
    this.setupCollapseButtons();
    window.addEventListener('resize', () => this.handleResize());
  },

  setupCollapseButtons() {
    document.querySelectorAll('[data-collapse]').forEach(btn => {
      btn.addEventListener('click', () => {
        const panelName = btn.getAttribute('data-collapse');
        this.togglePanel(panelName);
      });
    });
  },

  togglePanel(panelName) {
    const panel = document.querySelector(`[data-panel="${panelName}"]`);
    if (!panel) return;

    if (this.collapsed[panelName]) {
      this.expandPanel(panelName);
    } else {
      this.collapsePanel(panelName);
    }
  },

  collapsePanel(panelName) {
    const panel = document.querySelector(`[data-panel="${panelName}"]`);
    if (!panel) return;

    panel.style.maxHeight = panel.scrollHeight + 'px';
    requestAnimationFrame(() => {
      panel.classList.add('collapsed');
      panel.style.maxHeight = '0px';
    });

    this.collapsed[panelName] = true;
    this.saveState();
  },

  expandPanel(panelName) {
    const panel = document.querySelector(`[data-panel="${panelName}"]`);
    if (!panel) return;

    panel.classList.remove('collapsed');
    panel.style.maxHeight = panel.scrollHeight + 'px';
    setTimeout(() => {
      panel.style.maxHeight = 'none';
    }, 300);

    this.collapsed[panelName] = false;
    this.saveState();
  },

  saveState() {
    localStorage.setItem('jarvis-panel-states', JSON.stringify(this.collapsed));
  },

  loadState() {
    try {
      const saved = localStorage.getItem('jarvis-panel-states');
      if (saved) {
        this.collapsed = JSON.parse(saved);
        Object.keys(this.collapsed).forEach(panelName => {
          if (this.collapsed[panelName]) {
            const panel = document.querySelector(`[data-panel="${panelName}"]`);
            if (panel) {
              panel.classList.add('collapsed');
              panel.style.maxHeight = '0px';
            }
          }
        });
      }
    } catch (e) {
      this.collapsed = {};
    }
  },

  handleResize() {
    document.querySelectorAll('[data-panel]').forEach(panel => {
      if (!panel.classList.contains('collapsed')) {
        panel.style.maxHeight = 'none';
      }
    });
  }
};
