/**
 * JARVIS Voice Module
 * Microphone input, audio analysis, waveform visualization
 */

window.JARVIS = window.JARVIS || {};

JARVIS.voice = {
    active: false,
    audioContext: null,
    analyser: null,
    source: null,
    stream: null,
    animFrame: null,

    // ─── Initialization ─────────────────────────────────────────────
    init() {
        if (this.audioContext) return;
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 256;
        this.analyser.smoothingTimeConstant = 0.8;
    },

    // ─── Toggle Microphone ──────────────────────────────────────────
    toggle() {
        if (this.active) {
            this.stop();
        } else {
            this.start();
        }
    },

    // ─── Start Microphone ───────────────────────────────────────────
    async start() {
        try {
            this.init();
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }

            this.stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            this.source = this.audioContext.createMediaStreamSource(this.stream);
            this.source.connect(this.analyser);

            this.active = true;
            JARVIS.state.micActive = true;
            JARVIS.events.emit('voice:start');
            console.log('[Voice] Microphone active');

        } catch (err) {
            console.error('[Voice] Failed to start:', err);
            JARVIS.events.emit('voice:error', err);
        }
    },

    // ─── Stop Microphone ────────────────────────────────────────────
    stop() {
        if (this.stream) {
            this.stream.getTracks().forEach(t => t.stop());
            this.stream = null;
        }
        if (this.source) {
            this.source.disconnect();
            this.source = null;
        }
        if (this.animFrame) {
            cancelAnimationFrame(this.animFrame);
            this.animFrame = null;
        }

        this.active = false;
        JARVIS.state.micActive = false;
        JARVIS.events.emit('voice:stop');
        console.log('[Voice] Microphone stopped');
    },

    // ─── Draw Frequency Bars ────────────────────────────────────────
    drawWaveform(canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const bufferLength = this.analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        const draw = () => {
            this.animFrame = requestAnimationFrame(draw);
            this.analyser.getByteFrequencyData(dataArray);

            ctx.clearRect(0, 0, canvas.width, canvas.height);

            const barWidth = (canvas.width / bufferLength) * 2.5;
            let x = 0;

            for (let i = 0; i < bufferLength; i++) {
                const barHeight = (dataArray[i] / 255) * canvas.height;

                // Neon blue gradient
                const gradient = ctx.createLinearGradient(0, canvas.height, 0, canvas.height - barHeight);
                gradient.addColorStop(0, 'rgba(0, 150, 255, 0.8)');
                gradient.addColorStop(0.5, 'rgba(0, 200, 255, 0.9)');
                gradient.addColorStop(1, 'rgba(100, 230, 255, 1)');

                ctx.fillStyle = gradient;
                ctx.shadowBlur = 10;
                ctx.shadowColor = '#0096ff';
                ctx.fillRect(x, canvas.height - barHeight, barWidth - 1, barHeight);

                x += barWidth;
            }

            ctx.shadowBlur = 0;
            JARVIS.events.emit('voice:data', { volume: this.getVolume(), frequencyData: dataArray });
        };

        draw();
    },

    // ─── Idle Waveform Animation ────────────────────────────────────
    drawIdleWaveform(canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        let phase = 0;

        const draw = () => {
            this.animFrame = requestAnimationFrame(draw);
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            ctx.beginPath();
            ctx.strokeStyle = 'rgba(0, 150, 255, 0.3)';
            ctx.lineWidth = 2;
            ctx.shadowBlur = 8;
            ctx.shadowColor = '#0096ff';

            const midY = canvas.height / 2;
            const amplitude = 15;

            for (let x = 0; x < canvas.width; x++) {
                const y = midY + Math.sin((x * 0.02) + phase) * amplitude
                            * Math.sin((x * 0.005) + phase * 0.5);
                if (x === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }

            ctx.stroke();
            ctx.shadowBlur = 0;
            phase += 0.03;
        };

        draw();
    },

    // ─── Audio Level Analysis ───────────────────────────────────────
    processAudio() {
        if (!this.analyser) return null;
        const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        this.analyser.getByteFrequencyData(dataArray);

        const sum = dataArray.reduce((a, b) => a + b, 0);
        const avg = sum / dataArray.length;
        const volume = avg / 255;

        // Voice activity detection threshold
        const isSpeaking = volume > 0.1;

        return { volume, isSpeaking, frequencyData: dataArray };
    },

    // ─── Get Volume Level ───────────────────────────────────────────
    getVolume() {
        if (!this.analyser) return 0;
        const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        this.analyser.getByteFrequencyData(dataArray);
        const sum = dataArray.reduce((a, b) => a + b, 0);
        return Math.min(1, (sum / dataArray.length) / 255);
    }
};

console.log('[JARVIS] Voice module loaded');
