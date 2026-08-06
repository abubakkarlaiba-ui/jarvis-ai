JARVIS.notifications = {
    items: [],
    maxVisible: 5,
    container: null
};

JARVIS.notifications.init = function() {
    this.container = document.getElementById('toast-container');
};

JARVIS.notifications.show = function(message, type = 'info', duration = 4000) {
    if (!this.container) this.container = document.getElementById('toast-container');
    if (!this.container) return;
    const icons = {
        success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>',
        error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>',
        warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>',
        info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>'
    };
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type]}</span>
        <span class="toast-message">${message}</span>
        <button class="toast-close">&times;</button>
    `;
    this.container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('toast-show'));
    const remove = () => {
        toast.classList.remove('toast-show');
        toast.classList.add('toast-hide');
        setTimeout(() => toast.remove(), 300);
    };
    toast.querySelector('.toast-close').addEventListener('click', remove);
    setTimeout(remove, duration);
    while (this.container.children.length > this.maxVisible) {
        this.container.firstChild.remove();
    }
};

JARVIS.notifications.addNotification = function(notification) {
    const item = {
        id: notification.id || Date.now(),
        title: notification.title || '',
        message: notification.message || '',
        type: notification.type || 'info',
        timestamp: notification.timestamp || new Date().toISOString(),
        read: false
    };
    this.items.unshift(item);
    const list = document.getElementById('notification-list');
    if (!list) return;
    const borderColors = {
        success: '#22c55e', error: '#ef4444', warning: '#f59e0b', info: '#3b82f6'
    };
    const el = document.createElement('div');
    el.className = 'notification-item';
    el.dataset.id = item.id;
    el.style.borderLeftColor = borderColors[item.type] || borderColors.info;
    el.innerHTML = `
        <div class="notification-header">
            <span class="notification-title">${item.title}</span>
            <span class="notification-time">${new Date(item.timestamp).toLocaleTimeString()}</span>
        </div>
        <div class="notification-body">${item.message}</div>
    `;
    el.addEventListener('click', () => this.markAsRead(item.id));
    list.prepend(el);
    this.updateBadge();
};

JARVIS.notifications.markAsRead = function(notificationId) {
    const item = this.items.find(n => n.id === notificationId);
    if (item) {
        item.read = true;
        const el = document.querySelector(`.notification-item[data-id="${notificationId}"]`);
        if (el) el.classList.add('notification-read');
        this.updateBadge();
    }
};

JARVIS.notifications.clearAll = function() {
    this.items = [];
    const list = document.getElementById('notification-list');
    if (list) list.innerHTML = '';
    this.updateBadge();
};

JARVIS.notifications.getUnreadCount = function() {
    return this.items.filter(n => !n.read).length;
};

JARVIS.notifications.updateBadge = function() {
    const badge = document.getElementById('notification-badge');
    if (badge) {
        const count = this.getUnreadCount();
        badge.textContent = count;
        badge.style.display = count > 0 ? 'flex' : 'none';
    }
};

JARVIS.notifications.showToastForEvent = function(eventData) {
    this.show(eventData.message, eventData.type || 'info');
    this.addNotification({
        title: eventData.title || eventData.type,
        message: eventData.message,
        type: eventData.type
    });
};
