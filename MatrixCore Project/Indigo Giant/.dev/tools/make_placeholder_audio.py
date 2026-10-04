"""Generate the placeholder sound set for The Indigo Giant (Pass 40).

    python .dev/tools/make_placeholder_audio.py            # writes audio/sfx/*.wav and audio/music/*.wav
    python .dev/tools/make_placeholder_audio.py --force    # overwrite files that already exist

Everything is synthesised (numpy + scipy), mono, 22.05 kHz, 16-bit WAV — no third-party
sound content.  Existing files are NOT overwritten unless --force is given, so your own
replacements are safe.  The game itself does not need this script (or scipy) to run.
"""
from __future__ import annotations

import argparse
import wave
from pathlib import Path

import numpy as np
from scipy import signal

SR = 22050
ROOT = Path(__file__).resolve().parents[2] / 'audio'
RNG = np.random.default_rng(40)


# ------------------------------------------------------------------ helpers
def t_axis(seconds):
    return np.arange(int(seconds * SR)) / SR


def noise(seconds):
    return RNG.standard_normal(int(seconds * SR))


def lowpass(x, hz, order=2):
    b, a = signal.butter(order, hz / (SR / 2), 'low')
    return signal.lfilter(b, a, x)


def highpass(x, hz, order=2):
    b, a = signal.butter(order, hz / (SR / 2), 'high')
    return signal.lfilter(b, a, x)


def bandpass(x, lo, hi, order=2):
    b, a = signal.butter(order, [lo / (SR / 2), hi / (SR / 2)], 'band')
    return signal.lfilter(b, a, x)


def env(n, attack, decay, sustain=0.0, hold=0.0):
    """Attack/hold/exponential decay envelope over n samples (times in seconds)."""
    t = np.arange(n) / SR
    e = np.where(t < attack, t / max(attack, 1e-6), 1.0)
    after = np.clip(t - attack - hold, 0, None)
    e = e * np.where(t < attack + hold, 1.0, sustain + (1 - sustain) * np.exp(-after / max(decay, 1e-6)))
    return e


def sweep_sine(f0, f1, seconds, curve=1.0):
    t = t_axis(seconds)
    k = (t / seconds) ** curve
    f = f0 + (f1 - f0) * k
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def saw(freq_array):
    phase = np.cumsum(freq_array) / SR
    return 2.0 * (phase - np.floor(phase + 0.5))


def fade_edges(x, fin=0.004, fout=0.02):
    n_in, n_out = int(fin * SR), int(fout * SR)
    x = x.copy()
    if n_in:
        x[:n_in] *= np.linspace(0, 1, n_in)
    if n_out:
        x[-n_out:] *= np.linspace(1, 0, n_out)
    return x


def normalize(x, peak=0.8):
    m = np.max(np.abs(x)) or 1.0
    return x * (peak / m)


def reverb(x, seconds=1.2, mix=0.3):
    """Cheap diffuse tail: noise impulse response with exponential decay."""
    ir = noise(seconds) * np.exp(-np.arange(int(seconds * SR)) / (SR * seconds / 5))
    ir = lowpass(ir, 1600, order=4)
    wet = signal.fftconvolve(x, ir)[: len(x) + len(ir)]
    dry = np.concatenate([x, np.zeros(len(wet) - len(x))])
    return dry + normalize(wet, np.max(np.abs(x)) * mix)


def loopable(x, xfade=1.0):
    """Crossfade the tail into the head so the file loops seamlessly."""
    n = int(xfade * SR)
    head, body, tail = x[:n], x[n:-n], x[-n:]
    ramp = np.linspace(0, 1, n)
    return np.concatenate([tail * (1 - ramp) + head * ramp, body])


def write(rel, x, peak=0.8, force=False):
    path = ROOT / rel
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.int16(np.clip(normalize(x, peak), -1, 1) * 32767)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return True


# ------------------------------------------------------------------ sounds
def thump(freq0, freq1, seconds, drive=1.5):
    body = sweep_sine(freq0, freq1, seconds, 0.4) * env(int(seconds * SR), 0.004, seconds * 0.22)
    return np.tanh(body * drive)


def sand(seconds, lo=1200, hi=6000, decay=0.08):
    return bandpass(noise(seconds), lo, hi) * env(int(seconds * SR), 0.003, decay)


def footstep_human(i):
    s = 0.22
    x = sand(s, 1500 + 300 * i, 6500, 0.05) * 0.8 + thump(140 + 10 * i, 90, s, 1.0) * 0.35
    return fade_edges(x)


def footstep_giant(i, red=False):
    s = 1.6
    base = 32 if red else 40
    x = thump(base + 6 * i, base * 0.6, s, 2.6 if red else 2.0)
    rumble = lowpass(noise(s), 90) * env(int(s * SR), 0.01, 0.45) * 3.0
    spray = sand(s, 900, 4500, 0.35) * 0.25
    y = x + rumble + spray
    return fade_edges(reverb(y, 0.9, 0.18))


def land(big):
    if big:
        return footstep_giant(0) * 1.3
    s = 0.35
    return fade_edges(thump(110, 70, s, 1.4) * 0.6 + sand(s, 1000, 5000, 0.12))


def kneel_giant():
    a = footstep_giant(1)
    b = footstep_giant(2)
    gap = np.zeros(int(0.35 * SR))
    return np.concatenate([a, gap]) + np.concatenate([gap, b]) * 0.8


def stand_giant():
    s = 1.4
    swell = lowpass(noise(s), 120) * np.sin(np.linspace(0, np.pi, int(s * SR))) * 2.0
    return fade_edges(swell + sand(s, 800, 3000, 0.9) * 0.15)


def roar(f0, f1, seconds, formants, breath=0.25, drive=2.2, vibrato=5.0, rough=0.0):
    t = t_axis(seconds)
    f = f0 + (f1 - f0) * np.sin(np.pi * np.clip(t / seconds, 0, 1) * 0.5)
    f = f * (1 + 0.03 * np.sin(2 * np.pi * vibrato * t)) * (1 + rough * lowpass(noise(seconds), 30) * 0.2)
    src = saw(f) + breath * noise(seconds)
    out = np.zeros_like(src)
    for lo, hi, gain in formants:
        out += bandpass(src, lo, hi) * gain
    e = np.minimum(1.0, t / 0.25) * np.minimum(1.0, (seconds - t) / 0.6)
    return fade_edges(np.tanh(out * e * drive))


def roar_red_hunt():
    return reverb(roar(62, 95, 2.4, [(90, 400, 1.0), (500, 900, 0.7), (1200, 2200, 0.35)], rough=1.0), 1.4, 0.3)


def roar_red_scared():
    return reverb(roar(150, 80, 1.6, [(150, 600, 1.0), (800, 1600, 0.6)], breath=0.4, vibrato=9.0), 1.0, 0.25)


def roar_red_ko():
    return reverb(roar(90, 45, 2.8, [(60, 300, 1.0), (400, 800, 0.5)], breath=0.35, vibrato=3.0), 1.6, 0.3)


def roar_red_return():
    r = roar(58, 88, 3.2, [(70, 350, 1.0), (450, 850, 0.6)], rough=1.2)
    return reverb(lowpass(r, 700), 2.5, 0.55)       # distant: dull and washed


def roar_red_heave(i):
    return fade_edges(roar(85 + 10 * i, 70, 0.7, [(80, 400, 1.0), (600, 1100, 0.5)], breath=0.5, drive=2.8))


def call_indigo():
    s = 3.0
    t = t_axis(s)
    f = 52 * (1 + 0.012 * np.sin(2 * np.pi * 0.7 * t))
    x = (np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.6 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)
         + 0.3 * np.sin(2 * np.pi * np.cumsum(f * 3.02) / SR) + 0.12 * bandpass(saw(f * 2), 200, 900))
    e = np.sin(np.pi * np.clip(t / s, 0, 1)) ** 0.8
    return reverb(np.tanh(1.4 * x * e), 2.0, 0.35)


def hum_indigo_sense():
    s = 1.8
    t = t_axis(s)
    x = np.sin(2 * np.pi * 70 * t) * 0.8 + np.sin(2 * np.pi * 1760 * t) * 0.08 * (0.5 + 0.5 * np.sin(2 * np.pi * 6 * t))
    return reverb(x * np.sin(np.pi * t / s) ** 1.5, 1.2, 0.3)


def chime(freqs, seconds=0.9, step=0.12, decay=0.35):
    out = np.zeros(int((seconds + step * len(freqs)) * SR))
    for k, f in enumerate(freqs):
        t = t_axis(seconds)
        tone = fade_edges((np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2.01 * t)) * env(len(t), 0.005, decay),
                          0.004, 0.08)
        start = int(k * step * SR)
        out[start:start + len(tone)] += tone
    return fade_edges(reverb(out, 0.8, 0.2))


def whoosh(seconds=0.5, lo=300, hi=2500):
    x = bandpass(noise(seconds), lo, hi)
    return fade_edges(x * np.sin(np.pi * t_axis(seconds) / seconds) ** 2)


def whistle():
    s = 1.0
    t = t_axis(s)
    f = np.where(t < 0.35, 1300 + 500 * (t / 0.35), 1800 - 350 * np.clip((t - 0.45) / 0.4, 0, 1))
    f = f * (1 + 0.012 * np.sin(2 * np.pi * 6 * t))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.05 * bandpass(noise(s), 1000, 3000)
    dip = 1.0 - 0.7 * np.exp(-((t - 0.40) / 0.03) ** 2)      # the breath between the two notes
    e = np.minimum(1, t / 0.04) * dip * np.minimum(1, (s - t) / 0.1)
    return reverb(x * e, 1.2, 0.25)


def punch_hit():
    s = 0.7
    return fade_edges(reverb(thump(90, 45, s, 3.0) + bandpass(noise(s), 200, 1500) * env(int(s * SR), 0.002, 0.06), 0.8, 0.2))


def branch_smash():
    s = 0.7
    x = np.zeros(int(s * SR))
    for k in range(9):
        start = int(RNG.uniform(0, 0.4) * SR)
        c = highpass(noise(0.05), 1500) * env(int(0.05 * SR), 0.001, 0.012)
        x[start:start + len(c)] += c * RNG.uniform(0.4, 1.0)
    return fade_edges(x + thump(180, 120, s, 1.0) * 0.2)


def dig():
    s = 0.9
    x = np.zeros(int(s * SR))
    for k in range(3):
        start = int(k * 0.26 * SR)
        c = sand(0.22, 700, 4000, 0.07)
        x[start:start + len(c)] += c
    return fade_edges(x)


def eat():
    s = 0.8
    x = np.zeros(int(s * SR))
    for k in range(4):
        start = int((0.05 + k * 0.17) * SR)
        c = bandpass(noise(0.08), 800, 3500) * env(int(0.08 * SR), 0.002, 0.025)
        x[start:start + len(c)] += c
    return fade_edges(x)


def hollow(seconds, ring=320):
    t = t_axis(seconds)
    x = bandpass(noise(seconds), 200, 1800) * np.sin(np.pi * t / seconds) ** 2
    res = np.sin(2 * np.pi * ring * t) * env(len(t), 0.02, 0.3) * 0.3
    return fade_edges(reverb(x + res, 0.6, 0.35))


def shell_creak():
    s = 1.4
    t = t_axis(s)
    grind = bandpass(noise(s), 150, 900) * (0.5 + 0.5 * np.sin(2 * np.pi * 7 * t) ** 2)
    squeal = np.sin(2 * np.pi * np.cumsum(420 + 60 * np.sin(2 * np.pi * 1.3 * t)) / SR) * 0.12
    return fade_edges((grind + squeal) * np.sin(np.pi * t / s))


def shell_flip():
    clatter = np.concatenate([hollow(0.6, 260), np.zeros(int(0.8 * SR))])
    slam = np.concatenate([np.zeros(int(0.5 * SR)), thump(120, 60, 0.9, 2.0)])
    n = min(len(clatter), len(slam))
    return fade_edges(reverb(clatter[:n] + slam[:n], 1.0, 0.3))


def patch():
    s = 1.0
    x = np.zeros(int(s * SR))
    for k in range(4):
        start = int((0.1 + k * 0.2) * SR)
        c = (np.sin(2 * np.pi * 900 * t_axis(0.06)) + bandpass(noise(0.06), 1500, 5000)) * env(int(0.06 * SR), 0.001, 0.015)
        x[start:start + len(c)] += c
    return fade_edges(x)


def landmark_study():
    s = 3.2
    t = t_axis(s)
    x = np.zeros_like(t)
    for f, g in ((392, 1.0), (392 * 2.76, 0.5), (392 * 5.4, 0.25), (587, 0.6)):
        x += np.sin(2 * np.pi * f * t) * g * np.exp(-t / (0.9 if f < 600 else 0.4))
    return fade_edges(reverb(x, 2.0, 0.35))


def heartbeat():
    s = 1.0
    x = np.zeros(int(s * SR))
    for start, g in ((0.0, 1.0), (0.22, 0.7)):
        b = thump(60, 40, 0.2, 1.5) * g
        i = int(start * SR)
        x[i:i + len(b)] += b
    return lowpass(x, 200)


def human_hurt():
    return fade_edges(roar(260, 180, 0.35, [(300, 900, 1.0), (1200, 2500, 0.5)], breath=0.6, drive=1.5))


def human_down():
    return reverb(fade_edges(roar(220, 120, 0.8, [(250, 800, 1.0), (1000, 2000, 0.4)], breath=0.7, drive=1.2)), 1.2, 0.3)


def amb_wind():
    s = 16.0
    t = t_axis(s)
    x = lowpass(noise(s), 500) * (0.55 + 0.45 * np.sin(2 * np.pi * t / 8.0) ** 2)
    x += bandpass(noise(s), 1500, 4000) * 0.08 * (0.5 + 0.5 * np.sin(2 * np.pi * t / 5.3))
    return loopable(x, 2.0)


def amb_heat():
    s = 8.0
    t = t_axis(s)
    x = sum(np.sin(2 * np.pi * f * t) * 0.2 for f in (2200, 2213, 3300))
    x = x * (0.6 + 0.4 * np.sin(2 * np.pi * t / 4.0)) + highpass(noise(s), 5000) * 0.05
    return loopable(x, 1.0)


# ------------------------------------------------------------------ music
def pad(chords, beat, bars_per_chord=1, bright=1200, overlap=0.35):
    """Slow detuned pad; chords overlap-add with raised-cosine windows (no gaps, no clicks)."""
    d = beat * 4 * bars_per_chord
    hop = d * (1 - overlap)
    total = int((hop * (len(chords) - 1) + d) * SR)
    out = np.zeros(total)
    t = t_axis(d)
    window = np.sin(np.pi * np.arange(len(t)) / len(t)) ** 2
    for k, chord in enumerate(chords):
        tone = np.zeros_like(t)
        for f in chord:
            for det in (0.997, 1.0, 1.004):
                tone += saw(np.full_like(t, f * det)) * 0.15 + np.sin(2 * np.pi * f * det * t) * 0.2
        start = int(k * hop * SR)
        seg = lowpass(tone, bright) * window
        out[start:start + len(seg)] += seg[: total - start]
    return out


def music_ambient(variant):
    beat = 1.2
    if variant == 1:     # D dorian-ish, open fifths
        chords = [(73.4, 110, 146.8, 220), (65.4, 98, 130.8, 196), (58.3, 87.3, 116.5, 174.6), (65.4, 98, 146.8, 220)]
    else:                # F lydian drift
        chords = [(87.3, 130.8, 174.6, 246.9), (98, 146.8, 196, 246.9), (82.4, 123.5, 164.8, 246.9), (87.3, 130.8, 220, 261.6)]
    x = pad(chords * 2, beat, 1, bright=900)
    bell = np.zeros_like(x)
    for k in range(10):                   # sparse high bells
        start = RNG.uniform(1, len(x) / SR - 3)
        f = RNG.choice([440, 587.3, 659.3, 880])
        i = int(start * SR)
        seg = np.sin(2 * np.pi * f * t_axis(2.5)) * np.exp(-t_axis(2.5) / 0.8) * 0.25
        bell[i:i + len(seg)] += seg[: len(bell) - i]
    return reverb(x + bell, 3.0, 0.4)


def music_battle():
    bpm = 100
    beat = 60 / bpm
    bars = 8
    n = int(bars * 4 * beat * SR)
    x = np.zeros(n)
    kick = thump(70, 40, 0.5, 2.5)
    tom = thump(140, 90, 0.35, 1.8) * 0.6
    for b in range(bars * 4):
        i = int(b * beat * SR)
        x[i:i + len(kick)] += kick[: n - i]
        if b % 4 in (1, 3):
            j = int((b + 0.5) * beat * SR)
            x[j:j + len(tom)] += tom[: n - j]
    drone = saw(np.full(n, 55.0)) * 0.25 + saw(np.full(n, 82.4)) * 0.15
    x = x + lowpass(drone, 400) * (0.6 + 0.4 * np.sin(2 * np.pi * np.arange(n) / SR / (beat * 8)))
    return loopable(x, 0.5)


def stinger(kind):
    if kind == 'landmark':
        bell = landmark_study()
        chord = pad([(146.8, 220, 293.7)], 1.0, 1, bright=1500)
        n = min(len(bell), len(chord))
        return bell[:n] * 0.6 + chord[:n] * 0.5
    if kind == 'red_return':
        s = 4.0
        t = t_axis(s)
        horn = lowpass(saw(np.full_like(t, 46.2)) + saw(np.full_like(t, 49)), 500) * np.sin(np.pi * t / s)
        return reverb(horn, 2.0, 0.4)
    # ko: settling chord
    return reverb(pad([(98, 146.8, 196, 293.7)], 0.8, 1, bright=1400), 2.0, 0.4)


# ------------------------------------------------------------------ Pass 54: the newer moments
def indigo_shake():
    """A small hand patting a great stone hand: soft thumps and a low murmur."""
    x = np.zeros(int(0.7 * SR))
    for start, g in ((0.0, 1.0), (0.18, 0.7), (0.34, 0.5)):
        b = thump(180, 120, 0.12, 1.2) * g
        i = int(start * SR)
        x[i:i + len(b)] += b
    hum = np.sin(2 * np.pi * 70 * t_axis(0.7)) * env(int(0.7 * SR), 0.2, 0.4) * 0.3
    return fade_edges(x + hum)


def indigo_wake():
    """A deep breath in, rising, then the weight shifting as it gets up."""
    s = 2.4
    t = t_axis(s)
    breath = bandpass(noise(s), 150, 900) * np.sin(np.pi * t / s) ** 2 * 0.6
    tone = np.sin(2 * np.pi * (55 + 25 * t / s) * t) * np.sin(np.pi * t / s) * 0.5
    return reverb(fade_edges(_mix(breath + tone, stand_giant() * 0.8)), 1.5, 0.3)


def giant_fall():
    """Twenty metres of giant meeting the sand."""
    body = thump(55, 28, 1.6, 2.4)
    burst = sand(1.2, 400, 3000, decay=0.4) * 0.6
    return reverb(fade_edges(_mix(body, burst, land(True) * 0.5)), 1.8, 0.35)


def red_poisoned():
    """A gulp, and a long shudder in the throat."""
    gulp = eat() * 0.8
    shudder = roar(90, 60, 1.4, [(150, 600, 1.0), (700, 1400, 0.3)], breath=0.5, drive=1.4, vibrato=11.0, rough=0.4)
    return fade_edges(_mix(gulp, np.concatenate([np.zeros(int(0.35 * SR)), shudder * 0.7])))


def tower_climb():
    """Wind at the top of the tower, and a far bell."""
    return fade_edges(_mix(whoosh(2.2, 200, 1600) * 0.8, chime([293.7, 440.0], 2.0, 0.4, 0.8) * 0.4))


def legend_found():
    """Something very old and very large: a low bell that does not stop."""
    s = 5.0
    t = t_axis(s)
    x = np.zeros_like(t)
    for f, g, d in ((98, 1.0, 2.5), (98 * 2.76, 0.4, 1.4), (146.8, 0.6, 2.0), (196, 0.3, 1.2)):
        x += np.sin(2 * np.pi * f * t) * g * np.exp(-t / d)
    return reverb(fade_edges(x), 3.0, 0.45)


def well_drink():
    """Cupped hands of cold water, echoing up from far below."""
    return reverb(fade_edges(_mix(eat() * 0.7, hollow(1.2, 180) * 0.6)), 2.2, 0.5)


def lore_read():
    """Pass 61: an old etching lighting up under your hand: a glassy shimmer and a soft low tone."""
    s = 2.2
    t = t_axis(s)
    shimmer = chime([1318.5, 1760.0, 2093.0, 1567.9], 1.4, 0.09, 0.5) * 0.5
    low = np.sin(2 * np.pi * 110 * t) * np.sin(np.pi * t / s) ** 2 * 0.35
    return reverb(fade_edges(_mix(shimmer, low)), 1.6, 0.4)


def gleebs_arrive():
    """Pass 61: the sky opening - a long rising swell, a bright chord and a crackle of light."""
    s = 7.0
    t = t_axis(s)
    rise = np.sin(2 * np.pi * np.cumsum(60 + 160 * (t / s) ** 2) / SR) * np.minimum(1, t / 3.0) * 0.5
    chord = sum(np.sin(2 * np.pi * f * t) * g for f, g in ((220, 0.5), (277.2, 0.35), (329.6, 0.35), (440, 0.25),
                                                           (659.3, 0.12)))
    chord = chord * np.clip((t - 2.2) / 1.5, 0, 1) * np.exp(-np.clip(t - 4.0, 0, None) / 2.0)
    crackle = highpass(noise(s), 3000) * (RNG.random(len(t)) < 0.004) * 1.5 * np.clip((t - 2.4) / 0.4, 0, 1)
    air = bandpass(noise(s), 800, 5000) * np.sin(np.pi * t / s) ** 2 * 0.12
    return reverb(fade_edges(_mix(rise, chord, crackle, air), 0.2, 0.8), 3.0, 0.45)


def gleebs_voice():
    """Pass 61: a few soft warbling syllables - Gleebs speaking through the light."""
    s = 1.3
    x = np.zeros(int(s * SR))
    for k, (f0, f1, start, d) in enumerate(((520, 640, 0.0, 0.22), (700, 560, 0.26, 0.2), (600, 820, 0.5, 0.28),
                                             (760, 660, 0.84, 0.3))):
        tt = t_axis(d)
        f = f0 + (f1 - f0) * tt / d
        f = f * (1 + 0.03 * np.sin(2 * np.pi * 14 * tt))
        syl = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.25 * np.sin(2 * np.pi * np.cumsum(f * 2.0) / SR)
        syl *= np.sin(np.pi * tt / d) ** 1.5
        i = int(start * SR)
        x[i:i + len(syl)] += syl[: len(x) - i]
    return reverb(fade_edges(x), 1.2, 0.35)


def gleebs_depart():
    """Pass 61: rising up the beam - a swell that climbs and climbs, then a bell that fades out."""
    s = 10.0
    t = t_axis(s)
    climb = sum(np.sin(2 * np.pi * np.cumsum(f * (1 + 1.5 * (t / 9.0) ** 2)) / SR) * g
                for f, g in ((110, 0.4), (164.8, 0.3), (220, 0.25)))
    climb = climb * np.minimum(1, t / 2.0) * np.clip((9.0 - t) / 2.0, 0, 1)
    bell = np.zeros_like(t)
    i = int(8.2 * SR)
    tb = np.arange(len(t) - i) / SR
    bell[i:] = (np.sin(2 * np.pi * 880 * tb) + 0.4 * np.sin(2 * np.pi * 1320 * tb)) * np.exp(-tb / 0.9) * 0.4
    return reverb(fade_edges(_mix(climb, bell), 0.3, 1.0), 3.5, 0.5)


def _mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[: len(p)] += p
    return out


# ------------------------------------------------------------------ catalogue
def build(force=False):
    jobs = {}
    for i in range(4):
        jobs[f'sfx/footstep_human_{i + 1:02d}.wav'] = lambda i=i: footstep_human(i)
    for i in range(3):
        jobs[f'sfx/footstep_giant_{i + 1:02d}.wav'] = lambda i=i: footstep_giant(i)
        jobs[f'sfx/footstep_red_{i + 1:02d}.wav'] = lambda i=i: footstep_giant(i, red=True)
    jobs.update({
        'sfx/land_human_01.wav': lambda: land(False),
        'sfx/land_giant_01.wav': lambda: land(True),
        'sfx/kneel_giant_01.wav': kneel_giant,
        'sfx/stand_giant_01.wav': stand_giant,
        'sfx/stomp_red_01.wav': lambda: footstep_giant(0, red=True) * 1.4,
        'sfx/roar_red_hunt_01.wav': roar_red_hunt,
        'sfx/roar_red_scared_01.wav': roar_red_scared,
        'sfx/roar_red_ko_01.wav': roar_red_ko,
        'sfx/roar_red_return_01.wav': roar_red_return,
        'sfx/roar_red_heave_01.wav': lambda: roar_red_heave(0),
        'sfx/roar_red_heave_02.wav': lambda: roar_red_heave(1),
        'sfx/call_indigo_01.wav': call_indigo,
        'sfx/hum_indigo_sense_01.wav': hum_indigo_sense,
        'sfx/gesture_come_01.wav': lambda: chime([523.3, 659.3]),
        'sfx/gesture_stay_01.wav': lambda: chime([392.0], 1.0),
        'sfx/gesture_shade_01.wav': lambda: _mix(whoosh(0.8, 400, 3000) * 0.7, chime([587.3], 0.8) * 0.4),
        'sfx/gesture_lift_01.wav': lambda: chime([392.0, 523.3, 659.3]),
        'sfx/gesture_goto_01.wav': lambda: chime([659.3, 523.3], 0.6),
        'sfx/whistle_01.wav': whistle,
        'sfx/punch_swing_01.wav': lambda: whoosh(0.45, 150, 1200),
        'sfx/punch_hit_01.wav': punch_hit,
        'sfx/branch_smash_01.wav': branch_smash,
        'sfx/dig_01.wav': dig,
        'sfx/eat_01.wav': eat,
        'sfx/shell_enter_01.wav': lambda: hollow(0.7, 340),
        'sfx/shell_exit_01.wav': lambda: hollow(0.6, 300),
        'sfx/shell_creak_01.wav': shell_creak,
        'sfx/shell_flip_01.wav': shell_flip,
        'sfx/shell_lift_01.wav': lambda: _mix(hollow(0.9, 220), stand_giant() * 0.3),
        'sfx/shell_place_01.wav': lambda: _mix(thump(110, 60, 0.8, 1.8), hollow(0.8, 260) * 0.5),
        'sfx/patch_01.wav': patch,
        'sfx/landmark_study_01.wav': landmark_study,
        'sfx/heartbeat_01.wav': heartbeat,
        'sfx/human_hurt_01.wav': human_hurt,
        'sfx/human_down_01.wav': human_down,
        'sfx/amb_wind_01.wav': amb_wind,
        'sfx/amb_heat_01.wav': amb_heat,
        'sfx/indigo_shake_01.wav': indigo_shake,
        'sfx/indigo_wake_01.wav': indigo_wake,
        'sfx/giant_fall_01.wav': giant_fall,
        'sfx/red_poisoned_01.wav': red_poisoned,
        'sfx/tower_climb_01.wav': tower_climb,
        'sfx/legend_found_01.wav': legend_found,
        'sfx/well_drink_01.wav': well_drink,
        'sfx/lore_read_01.wav': lore_read,                  # Pass 61
        'sfx/gleebs_arrive_01.wav': gleebs_arrive,
        'sfx/gleebs_voice_01.wav': gleebs_voice,
        'sfx/gleebs_depart_01.wav': gleebs_depart,
        'music/ambient_01.wav': lambda: music_ambient(1),
        'music/ambient_02.wav': lambda: music_ambient(2),
        'music/battle_01.wav': music_battle,
        'music/stinger_landmark.wav': lambda: stinger('landmark'),
        'music/stinger_red_return.wav': lambda: stinger('red_return'),
        'music/stinger_ko.wav': lambda: stinger('ko'),
    })
    written = 0
    for rel, fn in jobs.items():
        if (ROOT / rel).exists() and not force:
            continue
        peak = 0.5 if rel.startswith('music/') else (0.35 if 'amb_' in rel else 0.8)
        written += write(rel, fn(), peak=peak, force=force)
    return written, len(jobs)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()
    w, n = build(args.force)
    print(f'wrote {w} of {n} placeholder files into {ROOT}')
