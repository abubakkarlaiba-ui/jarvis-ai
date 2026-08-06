JARVIS.chat = {
  messages: [],
  streaming: false,
  currentStream: null,

  init() {
    const input = document.getElementById('chatInput');
    const send = document.getElementById('chatSend');
    if (input) {
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });
      input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
      });
    }
    if (send) send.addEventListener('click', () => this.sendMessage());
  },

  sendMessage() {
    const input = document.getElementById('chatInput');
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    this.addMessage('user', text);
    input.value = '';
    input.style.height = 'auto';

    if (JARVIS.ws && JARVIS.ws.readyState === WebSocket.OPEN) {
      JARVIS.ws.send(JSON.stringify({ type: 'chat', content: text }));
    }
    this.showTypingIndicator();
  },

  addMessage(role, content, metadata = {}) {
    const container = document.getElementById('chatMessages');
    if (!container) return null;

    const div = document.createElement('div');
    div.className = `chat-message chat-message--${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'chat-message__avatar';
    avatar.textContent = role === 'user' ? 'U' : 'J';

    const body = document.createElement('div');
    body.className = 'chat-message__body';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'chat-message__content';
    contentDiv.innerHTML = this.renderMarkdown(content);

    const time = document.createElement('div');
    time.className = 'chat-message__time';
    time.textContent = new Date().toLocaleTimeString();

    body.appendChild(contentDiv);
    body.appendChild(time);
    div.appendChild(avatar);
    div.appendChild(body);
    container.appendChild(div);

    this.messages.push({ role, content, metadata, timestamp: Date.now() });
    this.scrollToBottom();
    return div;
  },

  startStream() {
    this.streaming = true;
    this.currentStream = this.addMessage('assistant', '');
    this.showTypingIndicator();
  },

  appendToStream(text) {
    if (!this.currentStream) return;
    this.removeTypingIndicator();
    const content = this.currentStream.querySelector('.chat-message__content');
    if (content) {
      content.innerHTML = this.renderMarkdown(content.textContent + text);
      this.scrollToBottom();
    }
  },

  endStream() {
    this.streaming = false;
    this.currentStream = null;
    this.removeTypingIndicator();
  },

  clearChat() {
    const container = document.getElementById('chatMessages');
    if (container) container.innerHTML = '';
    this.messages = [];
    this.addMessage('assistant', 'Hello! I am JARVIS. How can I assist you today?');
  },

  renderMarkdown(text) {
    let html = text;
    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    html = html.replace(/\n/g, '<br>');
    return html;
  },

  scrollToBottom() {
    const container = document.getElementById('chatMessages');
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    }
  },

  showTypingIndicator() {
    const container = document.getElementById('chatMessages');
    if (!container || document.getElementById('typingIndicator')) return;

    const indicator = document.createElement('div');
    indicator.id = 'typingIndicator';
    indicator.className = 'chat-message chat-message--assistant typing-indicator';
    indicator.innerHTML = '<div class="chat-message__avatar">J</div><div class="chat-message__body"><div class="chat-message__content">JARVIS is thinking<span class="dots"><span>.</span><span>.</span><span>.</span></span></div></div>';
    container.appendChild(indicator);
    this.scrollToBottom();
  },

  removeTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) indicator.remove();
  }
};
