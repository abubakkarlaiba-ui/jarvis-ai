JARVIS.tasks = {
    currentTab: 'queue',
    queue: [],
    workflows: [],
    skills: []
};

JARVIS.tasks.init = function() {
    const tabs = document.querySelectorAll('.task-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => this.switchTab(tab.dataset.tab));
    });
    this.loadQueue();
    this.loadWorkflows();
    this.loadSkills();
};

JARVIS.tasks.switchTab = function(tabName) {
    this.currentTab = tabName;
    document.querySelectorAll('.task-list').forEach(el => el.style.display = 'none');
    document.querySelectorAll('.task-tab').forEach(el => el.classList.remove('active'));
    const list = document.getElementById(`task-${tabName}`);
    if (list) list.style.display = 'block';
    const tab = document.querySelector(`.task-tab[data-tab="${tabName}"]`);
    if (tab) tab.classList.add('active');
};

JARVIS.tasks.loadQueue = async function() {
    try {
        const res = await fetch('/api/workflow/list?status=RUNNING');
        this.queue = await res.json();
        this.renderQueue();
    } catch (e) {
        console.error('Failed to load queue:', e);
    }
};

JARVIS.tasks.loadWorkflows = async function() {
    try {
        const res = await fetch('/api/workflow/list');
        this.workflows = await res.json();
        this.renderWorkflows();
    } catch (e) {
        console.error('Failed to load workflows:', e);
    }
};

JARVIS.tasks.loadSkills = async function() {
    try {
        const res = await fetch('/api/skills/');
        this.skills = await res.json();
        this.renderSkills();
    } catch (e) {
        console.error('Failed to load skills:', e);
    }
};

JARVIS.tasks.renderQueue = function() {
    const container = document.getElementById('task-queue');
    if (!container) return;
    container.innerHTML = '';
    this.queue.forEach(task => {
        const el = document.createElement('div');
        el.className = 'task-item';
        el.dataset.taskId = task.id;
        const statusColor = task.status === 'RUNNING' ? '#3b82f6' :
            task.status === 'COMPLETED' ? '#22c55e' :
            task.status === 'FAILED' ? '#ef4444' : '#a855f7';
        el.innerHTML = `
            <div class="task-status-dot" style="background:${statusColor}"></div>
            <div class="task-info">
                <div class="task-name">${task.name || task.id}</div>
                <div class="task-progress-bar">
                    <div class="task-progress-fill" style="width:${task.progress || 0}%"></div>
                </div>
                <div class="task-eta">${task.estimated_time || ''}</div>
            </div>
        `;
        el.addEventListener('click', () => this.showTaskDetail(task));
        container.appendChild(el);
    });
};

JARVIS.tasks.renderWorkflows = function() {
    const container = document.getElementById('task-workflows');
    if (!container) return;
    container.innerHTML = '';
    this.workflows.forEach(wf => {
        const el = document.createElement('div');
        el.className = 'task-item';
        const statusColor = wf.status === 'running' ? '#3b82f6' :
            wf.status === 'completed' ? '#22c55e' :
            wf.status === 'failed' ? '#ef4444' : '#6b7280';
        const completed = wf.steps_completed || 0;
        const total = wf.steps_total || 0;
        const percent = total > 0 ? Math.round((completed / total) * 100) : 0;
        el.innerHTML = `
            <div class="task-info">
                <div class="task-name">${wf.name || wf.id}</div>
                <span class="status-badge" style="background:${statusColor}">${wf.status}</span>
                <div class="step-progress">${completed}/${total} steps (${percent}%)</div>
            </div>
        `;
        container.appendChild(el);
    });
};

JARVIS.tasks.renderSkills = function() {
    const container = document.getElementById('task-skills');
    if (!container) return;
    container.innerHTML = '';
    this.skills.forEach(skill => {
        const el = document.createElement('div');
        el.className = 'skill-card';
        el.innerHTML = `
            <div class="skill-name">${skill.name}</div>
            <div class="skill-description">${skill.description || ''}</div>
            <div class="skill-tags">${(skill.tags || []).map(t => `<span class="tag">${t}</span>`).join('')}</div>
            <label class="toggle">
                <input type="checkbox" ${skill.enabled ? 'checked' : ''} data-skill="${skill.name}">
                <span class="toggle-slider"></span>
            </label>
        `;
        el.querySelector('.skill-name').addEventListener('click', () => this.executeSkill(skill.name));
        container.appendChild(el);
    });
};

JARVIS.tasks.updateTask = function(taskId, status, progress) {
    const task = this.queue.find(t => t.id === taskId);
    if (task) {
        task.status = status;
        task.progress = progress;
        this.renderQueue();
    }
};

JARVIS.tasks.removeTask = function(taskId) {
    const el = document.querySelector(`.task-item[data-task-id="${taskId}"]`);
    if (el) {
        el.style.transition = 'opacity 0.3s, transform 0.3s';
        el.style.opacity = '0';
        el.style.transform = 'translateX(20px)';
        setTimeout(() => el.remove(), 300);
    }
    this.queue = this.queue.filter(t => t.id !== taskId);
};

JARVIS.tasks.addTask = function(task) {
    this.queue.unshift(task);
    this.renderQueue();
    const el = document.querySelector(`.task-item[data-task-id="${task.id}"]`);
    if (el) {
        el.style.animation = 'slideIn 0.3s ease-out';
    }
};

JARVIS.tasks.showTaskDetail = function(task) {
    const existing = document.querySelector('.task-detail-modal');
    if (existing) existing.remove();
    const modal = document.createElement('div');
    modal.className = 'task-detail-modal';
    modal.innerHTML = `
        <div class="modal-content">
            <button class="modal-close">&times;</button>
            <h3>${task.name || task.id}</h3>
            <div class="detail-row"><span>Status:</span><span>${task.status}</span></div>
            <div class="detail-row"><span>Progress:</span><span>${task.progress || 0}%</span></div>
            <div class="detail-row"><span>Created:</span><span>${task.created_at || ''}</span></div>
            <div class="detail-row"><span>Steps:</span><span>${task.steps_completed || 0}/${task.steps_total || 0}</span></div>
            <div class="detail-row"><span>Result:</span><span>${task.result || ''}</span></div>
            <div class="detail-row"><span>Error:</span><span class="error-text">${task.error || ''}</span></div>
        </div>
    `;
    modal.querySelector('.modal-close').addEventListener('click', () => modal.remove());
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
    document.body.appendChild(modal);
};

JARVIS.tasks.executeSkill = async function(skillName) {
    try {
        const res = await fetch('/api/skills/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ skill: skillName })
        });
        const data = await res.json();
        JARVIS.notifications.showToastForEvent({ type: 'success', message: `Skill ${skillName} executed` });
    } catch (e) {
        JARVIS.notifications.showToastForEvent({ type: 'error', message: `Failed to execute ${skillName}` });
    }
};
