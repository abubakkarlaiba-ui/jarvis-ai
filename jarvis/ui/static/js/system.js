JARVIS.system = {
  interval: null,
  history: { cpu: [], ram: [] },
  maxHistory: 60,

  init() {
    this.interval = setInterval(() => this.fetchStats(), 2000);
    this.fetchStats();
  },

  async fetchStats() {
    try {
      const res = await fetch('/api/system/stats');
      const stats = await res.json();
      this.updateUI(stats);
    } catch (e) {
      console.error('Failed to fetch system stats:', e);
    }
  },

  updateUI(stats) {
    const circumference = 264;

    const cpuPercent = stats.cpu?.usage ?? 0;
    const ramPercent = stats.ram?.usage ?? 0;
    const gpuPercent = stats.gpu?.usage ?? 0;
    const netDown = stats.network?.download ?? 0;
    const netUp = stats.network?.upload ?? 0;

    this.history.cpu.push(cpuPercent);
    this.history.ram.push(ramPercent);
    if (this.history.cpu.length > this.maxHistory) this.history.cpu.shift();
    if (this.history.ram.length > this.maxHistory) this.history.ram.shift();

    const rings = [
      { id: 'cpuRing', percent: cpuPercent, valueId: 'cpuValue', detailId: 'cpuDetail', detailText: `${stats.cpu?.cores ?? 0} cores` },
      { id: 'ramRing', percent: ramPercent, valueId: 'ramValue', detailId: 'ramDetail', detailText: `${stats.ram?.used ?? 0}/${stats.ram?.total ?? 0} GB` },
      { id: 'gpuRing', percent: gpuPercent, valueId: 'gpuValue', detailId: 'gpuDetail', detailText: stats.gpu?.name ?? 'N/A' },
    ];

    rings.forEach(({ id, percent, valueId, detailId, detailText }) => {
      const ring = document.getElementById(id);
      const value = document.getElementById(valueId);
      const detail = document.getElementById(detailId);
      if (ring) {
        const offset = circumference - (circumference * percent / 100);
        ring.style.strokeDashoffset = offset;
        ring.setAttribute('aria-valuenow', Math.round(percent));
      }
      if (value) value.textContent = `${Math.round(percent)}%`;
      if (detail) detail.textContent = detailText;
    });

    const netValue = document.getElementById('netValue');
    const netDetail = document.getElementById('netDetail');
    const netRing = document.getElementById('netRing');
    if (netValue) netValue.textContent = `${netDown.toFixed(1)}`;
    if (netDetail) netDetail.textContent = `↓${netDown.toFixed(1)} / ↑${netUp.toFixed(1)} Mbps`;
    if (netRing) {
      const netPercent = Math.min(100, (netDown + netUp) / 2);
      netRing.style.strokeDashoffset = circumference - (circumference * netPercent / 100);
      netRing.setAttribute('aria-valuenow', Math.round(netPercent));
    }

    this.updateSparkline('cpuSparkline', this.history.cpu);
    this.updateSparkline('ramSparkline', this.history.ram);
    this.updateSystemInfo(stats);
  },

  updateSparkline(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    if (data.length < 2) return;

    const step = w / (this.maxHistory - 1);
    ctx.beginPath();
    ctx.moveTo(0, h - (data[0] / 100) * h);
    for (let i = 1; i < data.length; i++) {
      const x = i * step;
      const y = h - (data[i] / 100) * h;
      const prevX = (i - 1) * step;
      const prevY = h - (data[i - 1] / 100) * h;
      const cpx = (prevX + x) / 2;
      ctx.bezierCurveTo(cpx, prevY, cpx, y, x, y);
    }
    ctx.strokeStyle = '#00f0ff';
    ctx.lineWidth = 2;
    ctx.stroke();

    const gradient = ctx.createLinearGradient(0, 0, 0, h);
    gradient.addColorStop(0, 'rgba(0, 240, 255, 0.3)');
    gradient.addColorStop(1, 'rgba(0, 240, 255, 0)');
    ctx.lineTo((data.length - 1) * step, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();
  },

  updateSystemInfo(stats) {
    const osInfo = document.getElementById('osInfo');
    const uptimeInfo = document.getElementById('uptimeInfo');
    const processInfo = document.getElementById('processInfo');
    if (osInfo && stats.os) osInfo.textContent = `${stats.os.name ?? ''} ${stats.os.version ?? ''}`;
    if (uptimeInfo && stats.uptime) uptimeInfo.textContent = stats.uptime;
    if (processInfo && stats.processes) processInfo.textContent = `${stats.processes} running`;
  },

  animateRings() {
    document.querySelectorAll('.progress-ring circle').forEach(ring => {
      ring.style.transition = 'stroke-dashoffset 0.6s ease';
    });
  },

  destroy() {
    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
    }
  }
};
