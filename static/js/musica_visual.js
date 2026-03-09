/**
 * MusicaVisual — Animações elaboradas para Música Virtual
 * Partículas, ondas, gradientes e visualização de frequência
 */
class MusicaVisual {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.pulseScale = 1.0;
        this.pulseTarget = 1.0;
        this.beatFlash = 0;
        this.gestureLabel = '';
        this.gestureLabelOpacity = 0;
        this.animFrame = null;
        this.engine = null; // será linkado com MusicaEngine

        // Paletas por estilo
        this.palettes = {
            rock:       { bg1: '#1a0000', bg2: '#330000', accent: '#ff3333', particles: ['#ff4444', '#ff6666', '#cc0000', '#ffaa00'] },
            jazz:       { bg1: '#000a1a', bg2: '#001a33', accent: '#4488ff', particles: ['#4488ff', '#66aaff', '#ffd700', '#ffffff'] },
            eletronica: { bg1: '#000a1a', bg2: '#001a2e', accent: '#00ffcc', particles: ['#00ffcc', '#00ccff', '#ff00ff', '#00ff88'] },
            samba:      { bg1: '#0a1a00', bg2: '#1a3300', accent: '#44dd44', particles: ['#00cc44', '#ffdd00', '#ff8800', '#44ff44'] },
            bossanova:  { bg1: '#1a0a00', bg2: '#332200', accent: '#ffaa44', particles: ['#ffcc88', '#ff8844', '#ffddaa', '#cc8844'] }
        };

        this.currentPalette = this.palettes.rock;
        this._resize();
        window.addEventListener('resize', () => this._resize());
    }

    _resize() {
        const parent = this.canvas.parentElement;
        this.canvas.width = parent.clientWidth || 640;
        this.canvas.height = 280;
        this.cx = this.canvas.width / 2;
        this.cy = this.canvas.height / 2;
    }

    setEngine(engine) {
        this.engine = engine;
    }

    setEstilo(estilo) {
        this.currentPalette = this.palettes[estilo] || this.palettes.rock;
    }

    // Disparar partículas por tipo de instrumento
    triggerParticles(type) {
        const p = this.currentPalette;
        const cx = this.cx;
        const cy = this.cy;

        switch (type) {
            case 'kick':
                // Grandes partículas no centro
                for (let i = 0; i < 15; i++) {
                    const angle = (Math.PI * 2 * i) / 15;
                    this.particles.push({
                        x: cx, y: cy,
                        vx: Math.cos(angle) * (3 + Math.random() * 4),
                        vy: Math.sin(angle) * (3 + Math.random() * 4),
                        size: 6 + Math.random() * 8,
                        color: p.particles[0],
                        life: 1.0,
                        decay: 0.015 + Math.random() * 0.01
                    });
                }
                this.pulseTarget = 1.4;
                this.beatFlash = 1.0;
                break;

            case 'snare':
                // Faíscas espalhadas
                for (let i = 0; i < 25; i++) {
                    this.particles.push({
                        x: cx + (Math.random() - 0.5) * this.canvas.width * 0.6,
                        y: cy + (Math.random() - 0.5) * this.canvas.height * 0.4,
                        vx: (Math.random() - 0.5) * 6,
                        vy: (Math.random() - 0.5) * 6,
                        size: 2 + Math.random() * 3,
                        color: '#ffffff',
                        life: 1.0,
                        decay: 0.02 + Math.random() * 0.015
                    });
                }
                this.beatFlash = 0.6;
                break;

            case 'hihat':
                // Pontos dourados no topo
                for (let i = 0; i < 12; i++) {
                    this.particles.push({
                        x: cx + (Math.random() - 0.5) * this.canvas.width * 0.4,
                        y: 20 + Math.random() * 40,
                        vx: (Math.random() - 0.5) * 2,
                        vy: Math.random() * 2,
                        size: 1.5 + Math.random() * 2,
                        color: p.particles[2] || '#ffd700',
                        life: 1.0,
                        decay: 0.03 + Math.random() * 0.02
                    });
                }
                break;

            case 'crash':
                // Explosão multicolor
                for (let i = 0; i < 40; i++) {
                    const angle = Math.random() * Math.PI * 2;
                    const speed = 2 + Math.random() * 8;
                    this.particles.push({
                        x: cx, y: cy,
                        vx: Math.cos(angle) * speed,
                        vy: Math.sin(angle) * speed,
                        size: 3 + Math.random() * 6,
                        color: p.particles[Math.floor(Math.random() * p.particles.length)],
                        life: 1.0,
                        decay: 0.008 + Math.random() * 0.012
                    });
                }
                this.pulseTarget = 1.6;
                this.beatFlash = 1.0;
                break;

            case 'reverb':
                // Onda expansiva
                for (let i = 0; i < 30; i++) {
                    const angle = (Math.PI * 2 * i) / 30;
                    this.particles.push({
                        x: cx, y: cy,
                        vx: Math.cos(angle) * (1 + Math.random() * 2),
                        vy: Math.sin(angle) * (1 + Math.random() * 2),
                        size: 4 + Math.random() * 4,
                        color: p.accent,
                        life: 1.0,
                        decay: 0.006
                    });
                }
                break;

            // === NOVOS EFEITOS PARA COMBOS E GESTOS ===

            case 'double_kick':
                // Dupla explosão vermelha
                for (let wave = 0; wave < 2; wave++) {
                    for (let i = 0; i < 12; i++) {
                        const angle = (Math.PI * 2 * i) / 12;
                        const r = wave * 20;
                        this.particles.push({
                            x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r,
                            vx: Math.cos(angle) * (4 + Math.random() * 3),
                            vy: Math.sin(angle) * (4 + Math.random() * 3),
                            size: 7 + Math.random() * 6,
                            color: p.particles[0],
                            life: 1.0,
                            decay: 0.012
                        });
                    }
                }
                this.pulseTarget = 1.8;
                this.beatFlash = 1.0;
                break;

            case 'clap':
                // Flash branco + faíscas simétricas
                for (let i = 0; i < 30; i++) {
                    const side = i % 2 === 0 ? -1 : 1;
                    this.particles.push({
                        x: cx + side * (20 + Math.random() * 30),
                        y: cy + (Math.random() - 0.5) * 60,
                        vx: side * (2 + Math.random() * 4),
                        vy: (Math.random() - 0.5) * 4,
                        size: 2 + Math.random() * 4,
                        color: '#ffffff',
                        life: 1.0,
                        decay: 0.025
                    });
                }
                this.beatFlash = 0.8;
                break;

            case 'double_rock':
                // Explosão massiva com todas as cores
                for (let i = 0; i < 60; i++) {
                    const angle = Math.random() * Math.PI * 2;
                    const speed = 3 + Math.random() * 10;
                    this.particles.push({
                        x: cx, y: cy,
                        vx: Math.cos(angle) * speed,
                        vy: Math.sin(angle) * speed,
                        size: 4 + Math.random() * 8,
                        color: p.particles[Math.floor(Math.random() * p.particles.length)],
                        life: 1.0,
                        decay: 0.006 + Math.random() * 0.008
                    });
                }
                this.pulseTarget = 2.0;
                this.beatFlash = 1.0;
                break;

            case 'scratch':
                // Linhas horizontais rápidas
                for (let i = 0; i < 20; i++) {
                    const y = cy + (Math.random() - 0.5) * 100;
                    this.particles.push({
                        x: Math.random() < 0.5 ? 0 : this.canvas.width,
                        y: y,
                        vx: (Math.random() < 0.5 ? 1 : -1) * (8 + Math.random() * 6),
                        vy: (Math.random() - 0.5) * 1,
                        size: 2 + Math.random() * 3,
                        color: p.accent,
                        life: 1.0,
                        decay: 0.03
                    });
                }
                break;

            case 'rise':
                // Partículas subindo
                for (let i = 0; i < 20; i++) {
                    this.particles.push({
                        x: cx + (Math.random() - 0.5) * this.canvas.width * 0.5,
                        y: this.canvas.height,
                        vx: (Math.random() - 0.5) * 2,
                        vy: -(4 + Math.random() * 6),
                        size: 3 + Math.random() * 4,
                        color: p.particles[1] || '#44ff88',
                        life: 1.0,
                        decay: 0.01
                    });
                }
                break;

            case 'drop':
                // Partículas caindo
                for (let i = 0; i < 20; i++) {
                    this.particles.push({
                        x: cx + (Math.random() - 0.5) * this.canvas.width * 0.5,
                        y: 0,
                        vx: (Math.random() - 0.5) * 2,
                        vy: 4 + Math.random() * 6,
                        size: 3 + Math.random() * 4,
                        color: p.particles[0] || '#ff4444',
                        life: 1.0,
                        decay: 0.01
                    });
                }
                break;

            case 'spin':
                // Espiral colorida
                for (let i = 0; i < 25; i++) {
                    const angle = (Math.PI * 2 * i) / 25;
                    const dist = 20 + i * 3;
                    this.particles.push({
                        x: cx + Math.cos(angle) * dist,
                        y: cy + Math.sin(angle) * dist,
                        vx: Math.cos(angle + 0.5) * 3,
                        vy: Math.sin(angle + 0.5) * 3,
                        size: 3 + Math.random() * 3,
                        color: p.particles[i % p.particles.length],
                        life: 1.0,
                        decay: 0.01
                    });
                }
                break;

            case 'shaker':
                // Pontos pequenos espalhados vibrando
                for (let i = 0; i < 15; i++) {
                    this.particles.push({
                        x: cx + (Math.random() - 0.5) * this.canvas.width * 0.8,
                        y: cy + (Math.random() - 0.5) * this.canvas.height * 0.6,
                        vx: (Math.random() - 0.5) * 8,
                        vy: (Math.random() - 0.5) * 8,
                        size: 1 + Math.random() * 2,
                        color: p.particles[2] || '#ffd700',
                        life: 1.0,
                        decay: 0.04
                    });
                }
                break;

            case 'tom':
                // Onda do centro para fora (menor que kick)
                for (let i = 0; i < 10; i++) {
                    const angle = (Math.PI * 2 * i) / 10;
                    this.particles.push({
                        x: cx, y: cy,
                        vx: Math.cos(angle) * (2 + Math.random() * 2),
                        vy: Math.sin(angle) * (2 + Math.random() * 2),
                        size: 4 + Math.random() * 4,
                        color: p.particles[1] || '#66aaff',
                        life: 1.0,
                        decay: 0.02
                    });
                }
                this.pulseTarget = 1.2;
                break;

            case 'rimshot':
                // Estrela rápida
                for (let i = 0; i < 8; i++) {
                    const angle = (Math.PI * 2 * i) / 8;
                    this.particles.push({
                        x: cx, y: cy,
                        vx: Math.cos(angle) * 6,
                        vy: Math.sin(angle) * 6,
                        size: 2 + Math.random() * 2,
                        color: '#ffffff',
                        life: 1.0,
                        decay: 0.04
                    });
                }
                break;

            case 'filter_sweep':
                // Onda que vai da esquerda pra direita
                for (let i = 0; i < 15; i++) {
                    this.particles.push({
                        x: 0,
                        y: cy + (Math.random() - 0.5) * this.canvas.height * 0.5,
                        vx: 5 + Math.random() * 5,
                        vy: (Math.random() - 0.5) * 2,
                        size: 3 + Math.random() * 3,
                        color: p.accent,
                        life: 1.0,
                        decay: 0.012
                    });
                }
                break;

            case 'piano':
                // Nota subindo
                for (let i = 0; i < 6; i++) {
                    this.particles.push({
                        x: cx + (Math.random() - 0.5) * 60,
                        y: this.canvas.height - 10,
                        vx: (Math.random() - 0.5) * 1.5,
                        vy: -(2 + Math.random() * 3),
                        size: 2 + Math.random() * 3,
                        color: p.accent,
                        life: 1.0,
                        decay: 0.015
                    });
                }
                break;
        }
    }

    showGestureLabel(text) {
        this.gestureLabel = text;
        this.gestureLabelOpacity = 1.0;
    }

    start() {
        const loop = () => {
            this._draw();
            this.animFrame = requestAnimationFrame(loop);
        };
        loop();
    }

    stop() {
        if (this.animFrame) {
            cancelAnimationFrame(this.animFrame);
            this.animFrame = null;
        }
    }

    _draw() {
        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;
        const p = this.currentPalette;

        // === FUNDO GRADIENTE ===
        const grad = ctx.createLinearGradient(0, 0, w, h);
        grad.addColorStop(0, p.bg1);
        grad.addColorStop(1, p.bg2);
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, w, h);

        // Beat flash overlay
        if (this.beatFlash > 0.01) {
            ctx.fillStyle = `rgba(255, 255, 255, ${this.beatFlash * 0.08})`;
            ctx.fillRect(0, 0, w, h);
            this.beatFlash *= 0.92;
        }

        // === VISUALIZADOR DE FREQUÊNCIA ===
        if (this.engine) {
            const freqData = this.engine.getAnalyserData();
            if (freqData) {
                const barCount = 64;
                const barWidth = w / barCount;
                ctx.save();
                for (let i = 0; i < barCount; i++) {
                    const val = freqData[i] / 255;
                    const barH = val * h * 0.5;
                    const hue = (i / barCount) * 60;
                    ctx.fillStyle = p.accent + Math.floor(val * 180 + 40).toString(16).padStart(2, '0');
                    // Barras de baixo para cima
                    ctx.fillRect(i * barWidth, h - barH, barWidth - 1, barH);
                    // Espelhadas de cima para baixo (sutil)
                    ctx.globalAlpha = 0.15;
                    ctx.fillRect(i * barWidth, 0, barWidth - 1, barH * 0.3);
                    ctx.globalAlpha = 1.0;
                }
                ctx.restore();

                // Waveform line
                const waveData = this.engine.getAnalyserWaveform();
                if (waveData) {
                    ctx.beginPath();
                    ctx.strokeStyle = p.accent;
                    ctx.lineWidth = 1.5;
                    ctx.globalAlpha = 0.4;
                    const sliceW = w / waveData.length;
                    for (let i = 0; i < waveData.length; i++) {
                        const v = waveData[i] / 128.0;
                        const y = (v * h) / 2;
                        if (i === 0) ctx.moveTo(0, y);
                        else ctx.lineTo(i * sliceW, y);
                    }
                    ctx.stroke();
                    ctx.globalAlpha = 1.0;
                }
            }
        }

        // === ANEL PULSANTE CENTRAL ===
        this.pulseScale += (this.pulseTarget - this.pulseScale) * 0.1;
        this.pulseTarget += (1.0 - this.pulseTarget) * 0.05;

        const radius = 30 * this.pulseScale;
        ctx.beginPath();
        ctx.arc(this.cx, this.cy, radius, 0, Math.PI * 2);
        ctx.strokeStyle = p.accent;
        ctx.lineWidth = 2;
        ctx.globalAlpha = 0.5;
        ctx.stroke();
        ctx.globalAlpha = 1.0;

        // Inner glow
        const glowGrad = ctx.createRadialGradient(this.cx, this.cy, 0, this.cx, this.cy, radius);
        glowGrad.addColorStop(0, p.accent + '30');
        glowGrad.addColorStop(1, p.accent + '00');
        ctx.fillStyle = glowGrad;
        ctx.fill();

        // === PARTÍCULAS ===
        for (let i = this.particles.length - 1; i >= 0; i--) {
            const pt = this.particles[i];
            pt.x += pt.vx;
            pt.y += pt.vy;
            pt.vx *= 0.98;
            pt.vy *= 0.98;
            pt.life -= pt.decay;

            if (pt.life <= 0) {
                this.particles.splice(i, 1);
                continue;
            }

            ctx.globalAlpha = pt.life;
            ctx.fillStyle = pt.color;
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, pt.size * pt.life, 0, Math.PI * 2);
            ctx.fill();

            // Trail
            ctx.globalAlpha = pt.life * 0.3;
            ctx.beginPath();
            ctx.arc(pt.x - pt.vx * 2, pt.y - pt.vy * 2, pt.size * pt.life * 0.5, 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.globalAlpha = 1.0;

        // Limitar partículas
        if (this.particles.length > 300) {
            this.particles.splice(0, this.particles.length - 300);
        }

        // === LABEL DO GESTO ===
        if (this.gestureLabelOpacity > 0.01) {
            ctx.globalAlpha = this.gestureLabelOpacity;
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 18px monospace';
            ctx.textAlign = 'center';
            ctx.fillText(this.gestureLabel, this.cx, 30);
            this.gestureLabelOpacity *= 0.97;
            ctx.globalAlpha = 1.0;
        }

        // === BPM indicator ===
        if (this.engine) {
            ctx.fillStyle = p.accent;
            ctx.font = '13px monospace';
            ctx.textAlign = 'right';
            ctx.globalAlpha = 0.6;
            ctx.fillText(`${this.engine.bpm} BPM`, w - 12, h - 10);
            ctx.textAlign = 'left';
            ctx.fillText(this.engine.estilo.toUpperCase(), 12, h - 10);
            ctx.globalAlpha = 1.0;
        }
    }
}
