"""
Gera samples de áudio placeholder para a Música Virtual.
Cada estilo tem bass_loop.wav e melody_loop.wav — synth simples usando numpy + wave.
Substitua por samples reais para melhor qualidade.
"""
import os
import struct
import wave
import math

SAMPLE_RATE = 44100
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "audio")

ESTILOS = {
    "rock": {
        "bass": [82.41, 82.41, 110.00, 98.00],       # E2, E2, A2, G2
        "melody": [329.63, 392.00, 440.00, 392.00, 329.63, 293.66, 329.63, 392.00],
        "bass_wave": "sawtooth",
        "melody_wave": "square",
        "bpm": 120
    },
    "jazz": {
        "bass": [65.41, 73.42, 87.31, 98.00],         # C2, D2, F2, G2
        "melody": [261.63, 329.63, 392.00, 440.00, 493.88, 440.00, 392.00, 329.63],
        "bass_wave": "sine",
        "melody_wave": "sine",
        "bpm": 100
    },
    "eletronica": {
        "bass": [55.00, 55.00, 73.42, 65.41],         # A1, A1, D2, C2
        "melody": [440.00, 523.25, 659.25, 523.25, 440.00, 349.23, 440.00, 523.25],
        "bass_wave": "sawtooth",
        "melody_wave": "sawtooth",
        "bpm": 130
    },
    "samba": {
        "bass": [73.42, 87.31, 98.00, 110.00],        # D2, F2, G2, A2
        "melody": [392.00, 440.00, 493.88, 523.25, 493.88, 440.00, 392.00, 349.23],
        "bass_wave": "sine",
        "melody_wave": "triangle",
        "bpm": 110
    },
    "bossanova": {
        "bass": [65.41, 82.41, 73.42, 87.31],         # C2, E2, D2, F2
        "melody": [261.63, 293.66, 329.63, 392.00, 440.00, 392.00, 329.63, 293.66],
        "bass_wave": "sine",
        "melody_wave": "sine",
        "bpm": 95
    }
}


def generate_wave(freq, duration, sample_rate, wave_type="sine", amplitude=0.4):
    """Gera samples de áudio para uma nota."""
    n_samples = int(sample_rate * duration)
    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        phase = 2 * math.pi * freq * t

        if wave_type == "sine":
            val = math.sin(phase)
        elif wave_type == "square":
            val = 1.0 if math.sin(phase) >= 0 else -1.0
            val *= 0.6  # atenuação para não estourar
        elif wave_type == "sawtooth":
            val = 2.0 * (t * freq - math.floor(0.5 + t * freq))
            val *= 0.6
        elif wave_type == "triangle":
            val = 2.0 * abs(2.0 * (t * freq - math.floor(t * freq + 0.5))) - 1.0
        else:
            val = math.sin(phase)

        # Envelope ADSR simples
        env = 1.0
        attack = 0.02
        release = 0.05
        if t < attack:
            env = t / attack
        elif t > duration - release:
            env = (duration - t) / release

        val = val * amplitude * env
        samples.append(val)

    return samples


def write_wav(filepath, samples, sample_rate=44100):
    """Escreve lista de floats [-1,1] como arquivo WAV 16-bit mono."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with wave.open(filepath, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for s in samples:
            s = max(-1.0, min(1.0, s))
            wf.writeframes(struct.pack('<h', int(s * 32767)))
    print(f"  ✅ {filepath}")


def generate_loop(notes, bpm, wave_type, sample_rate, note_division=1):
    """Gera um loop com as notas no BPM especificado."""
    beat_duration = 60.0 / bpm / note_division
    all_samples = []
    for freq in notes:
        note_samples = generate_wave(freq, beat_duration * 0.9, sample_rate, wave_type, amplitude=0.35)
        # Pequeno silêncio entre notas
        silence = [0.0] * int(sample_rate * beat_duration * 0.1)
        all_samples.extend(note_samples)
        all_samples.extend(silence)
    return all_samples


def main():
    print("🎵 Gerando samples de áudio para Música Virtual...\n")

    for estilo, config in ESTILOS.items():
        print(f"🎶 Estilo: {estilo}")
        estilo_dir = os.path.join(BASE_DIR, estilo)

        # Bass loop
        bass_samples = generate_loop(
            config["bass"], config["bpm"],
            config["bass_wave"], SAMPLE_RATE,
            note_division=1
        )
        write_wav(os.path.join(estilo_dir, "bass_loop.wav"), bass_samples, SAMPLE_RATE)

        # Melody loop
        melody_samples = generate_loop(
            config["melody"], config["bpm"],
            config["melody_wave"], SAMPLE_RATE,
            note_division=2  # colcheias (rhythm mais rápido)
        )
        write_wav(os.path.join(estilo_dir, "melody_loop.wav"), melody_samples, SAMPLE_RATE)

    print(f"\n✅ Todos os samples gerados em: {BASE_DIR}")
    print("💡 Substitua os .wav por samples reais para melhor qualidade!")


if __name__ == "__main__":
    main()
