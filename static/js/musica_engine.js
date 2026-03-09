/**
 * MusicaEngine — Motor de áudio híbrido para Música Virtual
 * Percussão sintetizada via Web Audio API + samples para melodia/baixo
 */
class MusicaEngine {
    constructor() {
        this.ctx = null;
        this.masterGain = null;
        this.analyser = null;
        this.panNode = null;
        this.compressor = null;

        this.bpm = 120;
        this.playing = false;
        this.estilo = 'rock';

        // Sample buffers por estilo
        this.samples = {};
        this.bassSource = null;
        this.melodySource = null;
        this.bassPlaying = false;
        this.melodyPlaying = false;

        // Sequencer
        this.sequencerTimer = null;
        this.beatIndex = 0;

        // Cooldowns para evitar spam
        this._lastTrigger = {};
        this._cooldownMs = 120;

        // Estilos disponíveis e suas configurações de samples
        this.estilos = ['rock', 'jazz', 'eletronica', 'samba', 'bossanova'];
        this.estiloIndex = 0;

        // Reverb
        this.convolver = null;
        this.reverbGain = null;
        this.dryGain = null;
    }

    async init() {
        this.ctx = new (window.AudioContext || window.webkitAudioContext)();

        // Compressor para normalizar volume
        this.compressor = this.ctx.createDynamicsCompressor();
        this.compressor.threshold.value = -20;
        this.compressor.knee.value = 20;
        this.compressor.ratio.value = 8;
        this.compressor.attack.value = 0.003;
        this.compressor.release.value = 0.15;

        // Master gain
        this.masterGain = this.ctx.createGain();
        this.masterGain.gain.value = 0.7;

        // Pan
        this.panNode = this.ctx.createStereoPanner();
        this.panNode.pan.value = 0;

        // Analyser para visualização
        this.analyser = this.ctx.createAnalyser();
        this.analyser.fftSize = 256;

        // Reverb (convolutional)
        this.convolver = this.ctx.createConvolver();
        this.reverbGain = this.ctx.createGain();
        this.reverbGain.gain.value = 0.15;
        this.dryGain = this.ctx.createGain();
        this.dryGain.gain.value = 0.85;

        // Gerar impulse response sintético
        this._createReverbIR();

        // Routing: source → masterGain → [dry + reverb] → compressor → analyser → destination
        this.masterGain.connect(this.dryGain);
        this.masterGain.connect(this.convolver);
        this.convolver.connect(this.reverbGain);
        this.dryGain.connect(this.compressor);
        this.reverbGain.connect(this.compressor);
        this.compressor.connect(this.analyser);
        this.analyser.connect(this.ctx.destination);

        // Carregar samples para todos os estilos
        await this._loadAllSamples();
    }

    _createReverbIR() {
        const rate = this.ctx.sampleRate;
        const length = rate * 1.5;
        const impulse = this.ctx.createBuffer(2, length, rate);
        for (let ch = 0; ch < 2; ch++) {
            const data = impulse.getChannelData(ch);
            for (let i = 0; i < length; i++) {
                data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / length, 2.5);
            }
        }
        this.convolver.buffer = impulse;
    }

    async _loadAllSamples() {
        for (const estilo of this.estilos) {
            this.samples[estilo] = {};
            for (const tipo of ['bass_loop', 'melody_loop']) {
                try {
                    const url = `/static/audio/${estilo}/${tipo}.wav`;
                    const resp = await fetch(url);
                    if (resp.ok) {
                        const buf = await resp.arrayBuffer();
                        this.samples[estilo][tipo] = await this.ctx.decodeAudioData(buf);
                    }
                } catch (e) {
                    // Sample não disponível — usar sintetizador como fallback
                }
            }
        }
    }

    // === SINTETIZADOR DE PERCUSSÃO ===

    playKick() {
        if (!this._canTrigger('kick')) return;
        const t = this.ctx.currentTime;
        // Oscillator (sine sweep)
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(150, t);
        osc.frequency.exponentialRampToValueAtTime(40, t + 0.12);
        gain.gain.setValueAtTime(1.0, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.35);
        osc.connect(gain);
        gain.connect(this.masterGain);
        osc.start(t);
        osc.stop(t + 0.35);
        return 'kick';
    }

    playSnare() {
        if (!this._canTrigger('snare')) return;
        const t = this.ctx.currentTime;
        // Noise burst
        const bufferSize = this.ctx.sampleRate * 0.15;
        const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
            data[i] = Math.random() * 2 - 1;
        }
        const noise = this.ctx.createBufferSource();
        noise.buffer = buffer;

        // Bandpass filter for body
        const filter = this.ctx.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.value = 3000;
        filter.Q.value = 0.7;

        const gain = this.ctx.createGain();
        gain.gain.setValueAtTime(0.8, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.15);

        // Tone component
        const osc = this.ctx.createOscillator();
        const oscGain = this.ctx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(180, t);
        osc.frequency.exponentialRampToValueAtTime(60, t + 0.08);
        oscGain.gain.setValueAtTime(0.6, t);
        oscGain.gain.exponentialRampToValueAtTime(0.001, t + 0.08);

        noise.connect(filter);
        filter.connect(gain);
        gain.connect(this.masterGain);
        osc.connect(oscGain);
        oscGain.connect(this.masterGain);

        noise.start(t);
        noise.stop(t + 0.15);
        osc.start(t);
        osc.stop(t + 0.08);
        return 'snare';
    }

    playHiHat() {
        if (!this._canTrigger('hihat')) return;
        const t = this.ctx.currentTime;
        const bufferSize = this.ctx.sampleRate * 0.06;
        const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
            data[i] = Math.random() * 2 - 1;
        }
        const noise = this.ctx.createBufferSource();
        noise.buffer = buffer;

        const hp = this.ctx.createBiquadFilter();
        hp.type = 'highpass';
        hp.frequency.value = 7000;

        const gain = this.ctx.createGain();
        gain.gain.setValueAtTime(0.4, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.06);

        noise.connect(hp);
        hp.connect(gain);
        gain.connect(this.masterGain);
        noise.start(t);
        noise.stop(t + 0.06);
        return 'hihat';
    }

    playCrash() {
        if (!this._canTrigger('crash')) return;
        const t = this.ctx.currentTime;
        const bufferSize = this.ctx.sampleRate * 0.8;
        const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
            data[i] = Math.random() * 2 - 1;
        }
        const noise = this.ctx.createBufferSource();
        noise.buffer = buffer;

        const hp = this.ctx.createBiquadFilter();
        hp.type = 'highpass';
        hp.frequency.value = 4000;

        const gain = this.ctx.createGain();
        gain.gain.setValueAtTime(0.6, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.8);

        noise.connect(hp);
        hp.connect(gain);
        gain.connect(this.masterGain);
        noise.start(t);
        noise.stop(t + 0.8);
        return 'crash';
    }

    // === SAMPLES (Baixo / Melodia) ===

    toggleBass() {
        if (this.bassPlaying) {
            this._stopBass();
        } else {
            this._startBass();
        }
        return this.bassPlaying;
    }

    toggleMelody() {
        if (this.melodyPlaying) {
            this._stopMelody();
        } else {
            this._startMelody();
        }
        return this.melodyPlaying;
    }

    _startBass() {
        const buf = this.samples[this.estilo]?.bass_loop;
        if (!buf) {
            // Fallback: synth bass loop
            this._startSynthBass();
            return;
        }
        this._stopBass();
        this.bassSource = this.ctx.createBufferSource();
        this.bassSource.buffer = buf;
        this.bassSource.loop = true;
        const g = this.ctx.createGain();
        g.gain.value = 0.5;
        this.bassSource.connect(g);
        g.connect(this.masterGain);
        this.bassSource.start();
        this.bassPlaying = true;
    }

    _stopBass() {
        if (this.bassSource) {
            try { this.bassSource.stop(); } catch (e) {}
            this.bassSource = null;
        }
        if (this._synthBassTimer) {
            clearInterval(this._synthBassTimer);
            this._synthBassTimer = null;
        }
        this.bassPlaying = false;
    }

    _startSynthBass() {
        this._stopBass();
        this.bassPlaying = true;
        const notes = this._getBassNotes();
        let idx = 0;
        const interval = (60 / this.bpm) * 1000;
        this._synthBassTimer = setInterval(() => {
            if (!this.bassPlaying) return;
            const t = this.ctx.currentTime;
            const osc = this.ctx.createOscillator();
            const g = this.ctx.createGain();
            osc.type = 'sawtooth';
            osc.frequency.value = notes[idx % notes.length];
            g.gain.setValueAtTime(0.25, t);
            g.gain.exponentialRampToValueAtTime(0.001, t + 0.3);

            const lp = this.ctx.createBiquadFilter();
            lp.type = 'lowpass';
            lp.frequency.value = 400;

            osc.connect(lp);
            lp.connect(g);
            g.connect(this.masterGain);
            osc.start(t);
            osc.stop(t + 0.3);
            idx++;
        }, interval);
    }

    _startMelody() {
        const buf = this.samples[this.estilo]?.melody_loop;
        if (!buf) {
            this._startSynthMelody();
            return;
        }
        this._stopMelody();
        this.melodySource = this.ctx.createBufferSource();
        this.melodySource.buffer = buf;
        this.melodySource.loop = true;
        const g = this.ctx.createGain();
        g.gain.value = 0.4;
        this.melodySource.connect(g);
        g.connect(this.masterGain);
        this.melodySource.start();
        this.melodyPlaying = true;
    }

    _stopMelody() {
        if (this.melodySource) {
            try { this.melodySource.stop(); } catch (e) {}
            this.melodySource = null;
        }
        if (this._synthMelodyTimer) {
            clearInterval(this._synthMelodyTimer);
            this._synthMelodyTimer = null;
        }
        this.melodyPlaying = false;
    }

    _startSynthMelody() {
        this._stopMelody();
        this.melodyPlaying = true;
        const notes = this._getMelodyNotes();
        let idx = 0;
        const interval = (60 / this.bpm) * 500;
        this._synthMelodyTimer = setInterval(() => {
            if (!this.melodyPlaying) return;
            const t = this.ctx.currentTime;
            const osc = this.ctx.createOscillator();
            const g = this.ctx.createGain();
            osc.type = this._getMelodyWaveform();
            osc.frequency.value = notes[idx % notes.length];
            g.gain.setValueAtTime(0.15, t);
            g.gain.exponentialRampToValueAtTime(0.001, t + 0.2);
            osc.connect(g);
            g.connect(this.masterGain);
            osc.start(t);
            osc.stop(t + 0.25);
            idx++;
        }, interval);
    }

    _getBassNotes() {
        const patterns = {
            rock:       [82.41, 82.41, 110.00, 98.00],      // E2, E2, A2, G2
            jazz:       [65.41, 73.42, 87.31, 98.00],       // C2, D2, F2, G2
            eletronica: [55.00, 55.00, 73.42, 65.41],       // A1, A1, D2, C2
            samba:      [73.42, 87.31, 98.00, 110.00],      // D2, F2, G2, A2
            bossanova:  [65.41, 82.41, 73.42, 87.31]        // C2, E2, D2, F2
        };
        return patterns[this.estilo] || patterns.rock;
    }

    _getMelodyNotes() {
        const patterns = {
            rock:       [329.63, 392.00, 440.00, 392.00, 329.63, 293.66, 329.63, 392.00],
            jazz:       [261.63, 329.63, 392.00, 440.00, 493.88, 440.00, 392.00, 329.63],
            eletronica: [440.00, 523.25, 659.25, 523.25, 440.00, 349.23, 440.00, 523.25],
            samba:      [392.00, 440.00, 493.88, 523.25, 493.88, 440.00, 392.00, 349.23],
            bossanova:  [261.63, 293.66, 329.63, 392.00, 440.00, 392.00, 329.63, 293.66]
        };
        return patterns[this.estilo] || patterns.rock;
    }

    _getMelodyWaveform() {
        const map = {
            rock: 'square',
            jazz: 'sine',
            eletronica: 'sawtooth',
            samba: 'triangle',
            bossanova: 'sine'
        };
        return map[this.estilo] || 'sine';
    }

    // === CONTROLES ===

    setVolume(v) {
        // v: 0-1 (invertido — y=0 é topo = volume alto)
        if (this.masterGain) {
            this.masterGain.gain.setTargetAtTime(
                Math.max(0, Math.min(1.0, 1.0 - v)),
                this.ctx.currentTime, 0.05
            );
        }
    }

    setPan(x) {
        // x: 0-1 → pan -1 to 1
        if (this.panNode) {
            this.panNode.pan.setTargetAtTime(
                (x - 0.5) * 2,
                this.ctx.currentTime, 0.05
            );
        }
    }

    setBPM(newBpm) {
        this.bpm = Math.max(60, Math.min(200, newBpm));
        // Se loops sintetizados estão rodando, reiniciar com novo BPM
        if (this.bassPlaying && this._synthBassTimer) {
            this._startSynthBass();
        }
        if (this.melodyPlaying && this._synthMelodyTimer) {
            this._startSynthMelody();
        }
    }

    increaseBPM(amount = 5) {
        this.setBPM(this.bpm + amount);
    }

    decreaseBPM(amount = 5) {
        this.setBPM(this.bpm - amount);
    }

    setEstilo(nome) {
        const n = nome.toLowerCase().replace(/\s/g, '').replace('ô', 'o');
        if (this.estilos.includes(n)) {
            const wasBasPlaying = this.bassPlaying;
            const wasMelPlaying = this.melodyPlaying;
            this._stopBass();
            this._stopMelody();
            this.estilo = n;
            this.estiloIndex = this.estilos.indexOf(n);
            if (wasBasPlaying) this._startBass();
            if (wasMelPlaying) this._startMelody();
        }
    }

    nextEstilo() {
        this.estiloIndex = (this.estiloIndex + 1) % this.estilos.length;
        this.setEstilo(this.estilos[this.estiloIndex]);
        return this.estilos[this.estiloIndex];
    }

    togglePlay() {
        this.playing = !this.playing;
        if (!this.playing) {
            this._stopBass();
            this._stopMelody();
        }
        return this.playing;
    }

    reverbBurst() {
        // Efeito especial: aumentar reverb momentaneamente
        if (!this.reverbGain) return;
        const t = this.ctx.currentTime;
        this.reverbGain.gain.setValueAtTime(0.8, t);
        this.reverbGain.gain.linearRampToValueAtTime(0.15, t + 1.5);
        this.dryGain.gain.setValueAtTime(0.3, t);
        this.dryGain.gain.linearRampToValueAtTime(0.85, t + 1.5);
    }

    // Processar estado dos gestos vindo do polling
    processGestureState(state) {
        if (!this.ctx || this.ctx.state === 'suspended') return null;

        const triggered = [];

        // === GESTOS COMBINADOS (prioridade mais alta) ===
        const combo = state.gesto_combinado || 'Nenhum';
        if (combo !== 'Nenhum') {
            if (combo === 'Double Kick' && this._canTrigger('double_kick')) {
                this.playKick();
                // Segundo kick com delay sutil
                setTimeout(() => this.playKick(), 50);
                triggered.push('double_kick');
            } else if (combo === 'Palmas' && this._canTrigger('clap')) {
                this._playClap();
                triggered.push('clap');
            } else if (combo === 'Double Rock' && this._canTrigger('double_rock')) {
                this.playCrash();
                if (!this.melodyPlaying) this._startMelody();
                if (!this.bassPlaying) this._startBass();
                triggered.push('double_rock');
            } else if (combo === 'Double Peace' && this._canTrigger('double_peace')) {
                this._playRimshot();
                triggered.push('rimshot');
            } else if (combo === 'Punch Clap' && this._canTrigger('punch_clap')) {
                this.playKick();
                this.playSnare();
                triggered.push('punch_clap');
            } else if (combo === 'DJ Mode' && this._canTrigger('dj_mode')) {
                this._playFilterSweep();
                triggered.push('filter_sweep');
            } else if (combo === 'Shake' && this._canTrigger('shake')) {
                this._playShaker();
                triggered.push('shaker');
            } else if (combo === 'Scratch' && this._canTrigger('scratch')) {
                this._playScratch();
                triggered.push('scratch');
            } else if (combo === 'Rise' && this._canTrigger('rise')) {
                this.increaseBPM(5);
                this._playRiser();
                triggered.push('rise');
            } else if (combo === 'Drop' && this._canTrigger('drop')) {
                this.decreaseBPM(5);
                this._playDrop();
                triggered.push('drop');
            } else if (combo === 'Spin' && this._canTrigger('spin')) {
                this._playFilterSweep();
                triggered.push('spin');
            } else if (combo === 'Aloha' && this._canTrigger('aloha')) {
                this.reverbBurst();
                triggered.push('aloha');
            }
        }

        // === MÃO DIREITA (se combo não consumiu) ===
        if (triggered.length === 0) {
            const gDir = state.gesto_direita;
            if (gDir === 'Punho Fechado') {
                const r = this.playKick();
                if (r) triggered.push(r);
            } else if (gDir === 'Num5') {
                const r = this.playSnare();
                if (r) triggered.push(r);
            } else if (gDir === 'Paz e Amor') {
                const r = this.playHiHat();
                if (r) triggered.push(r);
            } else if (gDir === 'Rock') {
                const r = this.playCrash();
                if (r) triggered.push(r);
                if (!this.melodyPlaying) {
                    this._startMelody();
                    triggered.push('melody_on');
                }
            } else if (gDir === 'OK') {
                if (this._canTrigger('toggle_play')) {
                    const playing = this.togglePlay();
                    triggered.push(playing ? 'play' : 'pause');
                }
            } else if (gDir === 'LIKE') {
                if (this._canTrigger('next_estilo')) {
                    const next = this.nextEstilo();
                    triggered.push('estilo_' + next);
                }
            } else if (gDir === 'Num1') {
                if (this._canTrigger('toggle_bass')) {
                    this.toggleBass();
                    triggered.push(this.bassPlaying ? 'bass_on' : 'bass_off');
                }
            } else if (gDir === 'Num3') {
                const r = this._playTom();
                if (r) triggered.push(r);
            } else if (gDir === 'Num4') {
                const r = this._playRimshot();
                if (r) triggered.push(r);
            } else if (gDir === 'Tres Dedos') {
                const r = this._playTom();
                if (r) triggered.push(r);
            } else if (gDir === 'Quatro Dedos') {
                const r = this._playRimshot();
                if (r) triggered.push(r);
            } else if (gDir === 'Hang Loose') {
                if (this._canTrigger('toggle_melody')) {
                    this.toggleMelody();
                    triggered.push(this.melodyPlaying ? 'melody_on' : 'melody_off');
                }
            }

            // === MÃO ESQUERDA ===
            const gEsq = state.gesto_esquerda;
            if (gEsq === 'Num1') {
                if (this._canTrigger('toggle_bass_l')) {
                    this.toggleBass();
                    triggered.push(this.bassPlaying ? 'bass_on' : 'bass_off');
                }
            } else if (gEsq === 'Punho Fechado') {
                const r = this.playKick();
                if (r) triggered.push(r);
            } else if (gEsq === 'Num5') {
                const r = this.playSnare();
                if (r) triggered.push(r);
            } else if (gEsq === 'Paz e Amor') {
                const r = this.playHiHat();
                if (r) triggered.push(r);
            } else if (gEsq === 'Num3' || gEsq === 'Tres Dedos') {
                const r = this._playTom();
                if (r) triggered.push(r);
            } else if (gEsq === 'Num4' || gEsq === 'Quatro Dedos') {
                const r = this._playRimshot();
                if (r) triggered.push(r);
            } else if (gEsq === 'Hang Loose') {
                if (this._canTrigger('toggle_melody_l')) {
                    this.toggleMelody();
                    triggered.push(this.melodyPlaying ? 'melody_on' : 'melody_off');
                }
            }
        }

        // === MOVIMENTO → efeitos (independente de combo) ===
        const movDir = state.movimento_direita || 'Parado';
        const movEsq = state.movimento_esquerda || 'Parado';
        const velDir = state.velocidade_direita || 0;
        const velEsq = state.velocidade_esquerda || 0;

        // Movimento rápido individual
        if (movDir.startsWith('Rapido') && this._canTrigger('rapid_right')) {
            this._playShaker();
            triggered.push('shaker');
        }
        if (movEsq.startsWith('Rapido') && this._canTrigger('rapid_left')) {
            this._playShaker();
            triggered.push('shaker');
        }

        // Posição da mão direita → volume
        if (state.pos_direita) {
            this.setVolume(state.pos_direita.y);
        }
        // Posição da mão esquerda → pan
        if (state.pos_esquerda) {
            this.setPan(state.pos_esquerda.x);
        }

        // === EXPRESSÃO FACIAL ===
        if (state.expressao === 'Sorriso') {
            if (this._canTrigger('bpm_up')) {
                this.increaseBPM(3);
                triggered.push('bpm_up');
            }
        } else if (state.expressao === 'Surpresa') {
            if (this._canTrigger('reverb')) {
                this.reverbBurst();
                triggered.push('reverb');
            }
        } else if (state.expressao === 'Olhos Fechados') {
            if (this._canTrigger('bpm_down')) {
                this.decreaseBPM(3);
                triggered.push('bpm_down');
            }
        }

        return triggered.length > 0 ? triggered : null;
    }

    // === NOVOS SONS ===

    _playClap() {
        if (!this._canTrigger('clap_snd')) return;
        const t = this.ctx.currentTime;
        // Noise burst filtrado (brighter than snare)
        const bufSize = this.ctx.sampleRate * 0.08;
        const buf = this.ctx.createBuffer(1, bufSize, this.ctx.sampleRate);
        const data = buf.getChannelData(0);
        for (let i = 0; i < bufSize; i++) data[i] = Math.random() * 2 - 1;
        const noise = this.ctx.createBufferSource();
        noise.buffer = buf;
        const bp = this.ctx.createBiquadFilter();
        bp.type = 'bandpass'; bp.frequency.value = 2500; bp.Q.value = 1.2;
        const g = this.ctx.createGain();
        g.gain.setValueAtTime(0.7, t);
        g.gain.exponentialRampToValueAtTime(0.001, t + 0.08);
        noise.connect(bp); bp.connect(g); g.connect(this.masterGain);
        noise.start(t); noise.stop(t + 0.08);
    }

    _playTom() {
        if (!this._canTrigger('tom')) return null;
        const t = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        const g = this.ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(200, t);
        osc.frequency.exponentialRampToValueAtTime(80, t + 0.2);
        g.gain.setValueAtTime(0.7, t);
        g.gain.exponentialRampToValueAtTime(0.001, t + 0.25);
        osc.connect(g); g.connect(this.masterGain);
        osc.start(t); osc.stop(t + 0.25);
        return 'tom';
    }

    _playRimshot() {
        if (!this._canTrigger('rimshot')) return null;
        const t = this.ctx.currentTime;
        // High-pitched click
        const osc = this.ctx.createOscillator();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(800, t);
        osc.frequency.exponentialRampToValueAtTime(400, t + 0.04);
        const g = this.ctx.createGain();
        g.gain.setValueAtTime(0.6, t);
        g.gain.exponentialRampToValueAtTime(0.001, t + 0.06);
        // Noise layer
        const bSize = this.ctx.sampleRate * 0.03;
        const buf = this.ctx.createBuffer(1, bSize, this.ctx.sampleRate);
        const d = buf.getChannelData(0);
        for (let i = 0; i < bSize; i++) d[i] = Math.random() * 2 - 1;
        const n = this.ctx.createBufferSource(); n.buffer = buf;
        const ng = this.ctx.createGain();
        ng.gain.setValueAtTime(0.3, t);
        ng.gain.exponentialRampToValueAtTime(0.001, t + 0.03);
        osc.connect(g); g.connect(this.masterGain);
        n.connect(ng); ng.connect(this.masterGain);
        osc.start(t); osc.stop(t + 0.06);
        n.start(t); n.stop(t + 0.03);
        return 'rimshot';
    }

    _playShaker() {
        if (!this._canTrigger('shaker_snd')) return;
        const t = this.ctx.currentTime;
        const bSize = this.ctx.sampleRate * 0.1;
        const buf = this.ctx.createBuffer(1, bSize, this.ctx.sampleRate);
        const d = buf.getChannelData(0);
        for (let i = 0; i < bSize; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / bSize);
        const n = this.ctx.createBufferSource(); n.buffer = buf;
        const hp = this.ctx.createBiquadFilter();
        hp.type = 'highpass'; hp.frequency.value = 6000;
        const g = this.ctx.createGain();
        g.gain.setValueAtTime(0.3, t);
        g.gain.exponentialRampToValueAtTime(0.001, t + 0.1);
        n.connect(hp); hp.connect(g); g.connect(this.masterGain);
        n.start(t); n.stop(t + 0.1);
    }

    _playScratch() {
        if (!this._canTrigger('scratch_snd')) return;
        const t = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(300, t);
        osc.frequency.exponentialRampToValueAtTime(1200, t + 0.05);
        osc.frequency.exponentialRampToValueAtTime(200, t + 0.15);
        const g = this.ctx.createGain();
        g.gain.setValueAtTime(0.25, t);
        g.gain.exponentialRampToValueAtTime(0.001, t + 0.15);
        osc.connect(g); g.connect(this.masterGain);
        osc.start(t); osc.stop(t + 0.15);
    }

    _playFilterSweep() {
        if (!this._canTrigger('filter_sweep_snd')) return;
        const t = this.ctx.currentTime;
        const bSize = this.ctx.sampleRate * 0.5;
        const buf = this.ctx.createBuffer(1, bSize, this.ctx.sampleRate);
        const d = buf.getChannelData(0);
        for (let i = 0; i < bSize; i++) d[i] = Math.random() * 2 - 1;
        const n = this.ctx.createBufferSource(); n.buffer = buf;
        const bp = this.ctx.createBiquadFilter();
        bp.type = 'bandpass'; bp.Q.value = 5;
        bp.frequency.setValueAtTime(200, t);
        bp.frequency.exponentialRampToValueAtTime(4000, t + 0.3);
        bp.frequency.exponentialRampToValueAtTime(200, t + 0.5);
        const g = this.ctx.createGain();
        g.gain.setValueAtTime(0.3, t);
        g.gain.exponentialRampToValueAtTime(0.001, t + 0.5);
        n.connect(bp); bp.connect(g); g.connect(this.masterGain);
        n.start(t); n.stop(t + 0.5);
    }

    _playRiser() {
        if (!this._canTrigger('riser_snd')) return;
        const t = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(200, t);
        osc.frequency.exponentialRampToValueAtTime(2000, t + 0.6);
        const g = this.ctx.createGain();
        g.gain.setValueAtTime(0.001, t);
        g.gain.linearRampToValueAtTime(0.2, t + 0.4);
        g.gain.linearRampToValueAtTime(0.001, t + 0.6);
        osc.connect(g); g.connect(this.masterGain);
        osc.start(t); osc.stop(t + 0.6);
    }

    _playDrop() {
        if (!this._canTrigger('drop_snd')) return;
        const t = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(800, t);
        osc.frequency.exponentialRampToValueAtTime(40, t + 0.5);
        const g = this.ctx.createGain();
        g.gain.setValueAtTime(0.4, t);
        g.gain.exponentialRampToValueAtTime(0.001, t + 0.5);
        osc.connect(g); g.connect(this.masterGain);
        osc.start(t); osc.stop(t + 0.5);
    }

    _canTrigger(id) {
        const now = performance.now();
        const last = this._lastTrigger[id] || 0;
        // Longer cooldown for toggle actions
        const cd = ['toggle_play', 'next_estilo', 'toggle_bass', 'bpm_up', 'bpm_down', 'reverb'].includes(id) ? 800 : this._cooldownMs;
        if (now - last < cd) return false;
        this._lastTrigger[id] = now;
        return true;
    }

    getAnalyserData() {
        if (!this.analyser) return null;
        const data = new Uint8Array(this.analyser.frequencyBinCount);
        this.analyser.getByteFrequencyData(data);
        return data;
    }

    getAnalyserWaveform() {
        if (!this.analyser) return null;
        const data = new Uint8Array(this.analyser.frequencyBinCount);
        this.analyser.getByteTimeDomainData(data);
        return data;
    }

    resume() {
        if (this.ctx && this.ctx.state === 'suspended') {
            this.ctx.resume();
        }
    }

    // === PIANO / TECLADO ===

    // Mapeamento tecla → nota (2 oitavas completas)
    static PIANO_KEYS = {
        // Oitava inferior (C3–B3) — fileira inferior do teclado
        'z': { note: 'C3',  freq: 130.81, black: false },
        's': { note: 'C#3', freq: 138.59, black: true },
        'x': { note: 'D3',  freq: 146.83, black: false },
        'd': { note: 'D#3', freq: 155.56, black: true },
        'c': { note: 'E3',  freq: 164.81, black: false },
        'v': { note: 'F3',  freq: 174.61, black: false },
        'g': { note: 'F#3', freq: 185.00, black: true },
        'b': { note: 'G3',  freq: 196.00, black: false },
        'h': { note: 'G#3', freq: 207.65, black: true },
        'n': { note: 'A3',  freq: 220.00, black: false },
        'j': { note: 'A#3', freq: 233.08, black: true },
        'm': { note: 'B3',  freq: 246.94, black: false },
        // Oitava superior (C4–B4) — fileira superior do teclado
        'q': { note: 'C4',  freq: 261.63, black: false },
        '2': { note: 'C#4', freq: 277.18, black: true },
        'w': { note: 'D4',  freq: 293.66, black: false },
        '3': { note: 'D#4', freq: 311.13, black: true },
        'e': { note: 'E4',  freq: 329.63, black: false },
        'r': { note: 'F4',  freq: 349.23, black: false },
        '5': { note: 'F#4', freq: 369.99, black: true },
        't': { note: 'G4',  freq: 392.00, black: false },
        '6': { note: 'G#4', freq: 415.30, black: true },
        'y': { note: 'A4',  freq: 440.00, black: false },
        '7': { note: 'A#4', freq: 466.16, black: true },
        'u': { note: 'B4',  freq: 493.88, black: false },
        'i': { note: 'C5',  freq: 523.25, black: false },
    };

    // Configurações de timbre do piano por estilo
    static PIANO_TIMBRES = {
        rock:       { type: 'sawtooth', attack: 0.005, decay: 0.1, sustain: 0.3, release: 0.3, filterFreq: 2000 },
        jazz:       { type: 'sine',     attack: 0.01,  decay: 0.15, sustain: 0.5, release: 0.5, filterFreq: 1200 },
        eletronica: { type: 'square',   attack: 0.002, decay: 0.05, sustain: 0.4, release: 0.2, filterFreq: 3000 },
        samba:      { type: 'triangle', attack: 0.008, decay: 0.1,  sustain: 0.35, release: 0.3, filterFreq: 1800 },
        bossanova:  { type: 'sine',     attack: 0.015, decay: 0.2,  sustain: 0.4, release: 0.6, filterFreq: 1000 },
    };

    /**
     * Toca uma nota do piano.
     * @param {string} key - A tecla pressionada (ex: 'q', 'w', 'z')
     * @returns {{ note: string, freq: number }|null}
     */
    playPianoNote(key) {
        if (!this.ctx) return null;
        const k = key.toLowerCase();
        const info = MusicaEngine.PIANO_KEYS[k];
        if (!info) return null;

        const timbre = MusicaEngine.PIANO_TIMBRES[this.estilo] || MusicaEngine.PIANO_TIMBRES.rock;
        const t = this.ctx.currentTime;
        const duration = 1.5;

        // Oscilador principal
        const osc = this.ctx.createOscillator();
        osc.type = timbre.type;
        osc.frequency.setValueAtTime(info.freq, t);

        // Segundo oscilador levemente desafinado para riqueza
        const osc2 = this.ctx.createOscillator();
        osc2.type = timbre.type === 'sine' ? 'triangle' : 'sine';
        osc2.frequency.setValueAtTime(info.freq * 1.002, t);

        // Filtro
        const filter = this.ctx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(timbre.filterFreq, t);
        filter.frequency.exponentialRampToValueAtTime(timbre.filterFreq * 0.3, t + duration);
        filter.Q.value = 1.5;

        // Envelope ADSR
        const gain = this.ctx.createGain();
        gain.gain.setValueAtTime(0, t);
        gain.gain.linearRampToValueAtTime(0.35, t + timbre.attack);
        gain.gain.linearRampToValueAtTime(0.35 * timbre.sustain, t + timbre.attack + timbre.decay);
        gain.gain.setValueAtTime(0.35 * timbre.sustain, t + duration - timbre.release);
        gain.gain.linearRampToValueAtTime(0.001, t + duration);

        const gain2 = this.ctx.createGain();
        gain2.gain.value = 0.12;

        osc.connect(filter);
        osc2.connect(gain2);
        gain2.connect(filter);
        filter.connect(gain);
        gain.connect(this.masterGain);

        osc.start(t);
        osc2.start(t);
        osc.stop(t + duration);
        osc2.stop(t + duration);

        return info;
    }

    /**
     * Retorna info da tecla se é uma tecla de piano válida.
     */
    getPianoKeyInfo(key) {
        return MusicaEngine.PIANO_KEYS[key.toLowerCase()] || null;
    }

    destroy() {
        this._stopBass();
        this._stopMelody();
        if (this.ctx) {
            this.ctx.close();
        }
    }
}
