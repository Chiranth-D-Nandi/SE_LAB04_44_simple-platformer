import io
import math
import random
import struct
import wave

import pygame

# Sound effects are synthesized in code (no audio files or extra
# dependencies needed). Each effect is built as 16-bit mono WAV data in
# memory and loaded as a pygame Sound.

SAMPLE_RATE = 44100
MASTER_VOLUME = 0.5


def _sweep(start_hz, end_hz, seconds, wave_shape="sine", noise=0.0, seed=0):
    """Samples (-1..1) of a tone gliding from start_hz to end_hz, with a short
    attack and a fade-out so the sound doesn't click."""
    rng = random.Random(seed)
    n = int(SAMPLE_RATE * seconds)
    attack = int(SAMPLE_RATE * 0.005)
    samples, phase = [], 0.0
    for i in range(n):
        t = i / n
        freq = start_hz + (end_hz - start_hz) * t
        phase += 2 * math.pi * freq / SAMPLE_RATE
        value = math.sin(phase)
        if wave_shape == "square":
            value = 1.0 if value >= 0 else -1.0
        if noise:
            value = (1 - noise) * value + noise * rng.uniform(-1, 1)
        envelope = min(1.0, i / attack) if attack else 1.0
        envelope *= (1 - t) ** 1.5
        samples.append(value * envelope)
    return samples


def _to_sound(samples):
    """Convert float samples to a pygame Sound via an in-memory WAV file."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        frames = b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, s)) * MASTER_VOLUME * 32767))
            for s in samples
        )
        wav.writeframes(frames)
    buf.seek(0)
    return pygame.mixer.Sound(file=buf)


def _make_jump():
    # Quick rising "boing".
    return _to_sound(_sweep(280, 640, 0.16))


def _make_goal():
    # Cheerful rising arpeggio: C5, E5, G5, C6.
    samples = []
    for note_hz in (523.25, 659.25, 783.99, 1046.50):
        samples += _sweep(note_hz, note_hz, 0.11)
    return _to_sound(samples)


def _make_death():
    # Falling buzzy tone with a bit of noise.
    return _to_sound(_sweep(420, 70, 0.55, wave_shape="square", noise=0.25, seed=1))


class SoundManager:
    """Loads the game's sound effects. If audio isn't available on this
    machine, every call quietly does nothing so the game still runs."""

    def __init__(self):
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.sounds = {
                "jump": _make_jump(),
                "goal": _make_goal(),
                "death": _make_death(),
            }
        except pygame.error as err:
            print("Sound disabled:", err)
            self.sounds = {}

    def play(self, name):
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()
