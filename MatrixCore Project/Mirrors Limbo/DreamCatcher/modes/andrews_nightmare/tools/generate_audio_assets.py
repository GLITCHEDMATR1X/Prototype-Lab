from __future__ import annotations

import math
import wave
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MUSIC = ROOT / 'assets' / 'audio' / 'music'
SFX = ROOT / 'assets' / 'audio' / 'sfx'
SR = 32000

MUSIC.mkdir(parents=True, exist_ok=True)
SFX.mkdir(parents=True, exist_ok=True)


def qfreq(freq: float, duration: float) -> float:
    return max(1.0, round(freq * duration) / duration)


def sine(t, freq, duration, phase=0.0, amp=1.0, pm=None):
    f = qfreq(freq, duration)
    ph = 2*np.pi*f*t + phase
    if pm is not None:
        ph = ph + pm
    return amp*np.sin(ph)


def periodic_noise(n: int, duration: float, rng: np.random.Generator, low_hz: float, high_hz: float, tilt: float = 1.0):
    # Random-phase spectral noise represented entirely by DFT bins.  This makes
    # the buffer itself periodic and therefore safe for native setLoop(True).
    freqs = np.fft.rfftfreq(n, 1/SR)
    band = (freqs >= low_hz) & (freqs <= high_hz)
    mag = np.zeros_like(freqs)
    safe = np.maximum(freqs, 1.0)
    mag[band] = 1.0 / np.power(safe[band], tilt)
    # soften both band edges
    if low_hz > 0:
        mag *= np.clip((freqs - low_hz) / max(8.0, low_hz*0.3), 0, 1)
    mag *= np.clip((high_hz - freqs) / max(40.0, high_hz*0.12), 0, 1)
    phase = rng.uniform(0, 2*np.pi, len(freqs))
    spec = mag * np.exp(1j*phase)
    spec[0] = 0
    if n % 2 == 0:
        spec[-1] = spec[-1].real
    x = np.fft.irfft(spec, n=n)
    x -= x.mean()
    sd = x.std() or 1.0
    return x / sd


def softclip(x, drive=1.2):
    return np.tanh(x*drive) / np.tanh(drive)


def normalize_stereo(x, peak=0.62):
    x = np.asarray(x, dtype=np.float64)
    m = float(np.max(np.abs(x))) or 1.0
    x = x * (peak / m)
    return x


def write_wav(path: Path, stereo: np.ndarray, sr=SR):
    stereo = np.asarray(stereo)
    if stereo.ndim == 1:
        stereo = stereo[:, None]
    if stereo.shape[1] == 1:
        stereo = np.repeat(stereo, 2, axis=1)
    pcm = np.clip(stereo, -1, 1)
    pcm = (pcm * 32767.0).astype('<i2')
    with wave.open(str(path), 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def loop_timeline(duration):
    n = int(round(duration * SR))
    t = np.arange(n) / SR
    return n, t


def loop_intercept_hum(path: Path, duration=36.0, seed=14101):
    n,t = loop_timeline(duration); rng=np.random.default_rng(seed)
    lfo = 0.21*np.sin(2*np.pi*(3/duration)*t) + 0.08*np.sin(2*np.pi*(7/duration)*t+1.1)
    left = (sine(t, 42.0, duration, amp=.42, pm=lfo) + sine(t, 63.5, duration, phase=.8, amp=.22, pm=.5*lfo)
            + sine(t, 127.0, duration, phase=2.1, amp=.075) + sine(t, 251.0, duration, phase=.3, amp=.028))
    right = (sine(t, 42.0, duration, phase=.04, amp=.42, pm=lfo*1.03) + sine(t, 64.2, duration, phase=.92, amp=.20, pm=.48*lfo)
             + sine(t, 128.0, duration, phase=2.0, amp=.068) + sine(t, 247.0, duration, phase=.6, amp=.032))
    breath=(.52+.48*np.sin(2*np.pi*(2/duration)*t-1.2)**2)
    airL=periodic_noise(n,duration,rng,90,1700,tilt=.65)*.035*breath
    airR=periodic_noise(n,duration,rng,100,1800,tilt=.62)*.033*breath
    out=np.column_stack([left+airL,right+airR])
    write_wav(path, normalize_stereo(softclip(out,.95),.53))


def loop_empty_carrier(path: Path, duration=40.0, seed=14102):
    n,t=loop_timeline(duration); rng=np.random.default_rng(seed)
    airL=periodic_noise(n,duration,rng,160,2800,tilt=.45)
    airR=periodic_noise(n,duration,rng,180,2600,tilt=.48)
    gate=.35+.65*(.5+.5*np.sin(2*np.pi*(3/duration)*t+1.5))**3
    low=sine(t, 37.5, duration, amp=.18)+sine(t, 75, duration, phase=.7, amp=.065)
    carrier=sine(t, 931, duration, phase=2.0, amp=.018)*(0.25+0.75*(.5+.5*np.sin(2*np.pi*(5/duration)*t))**8)
    left=low+airL*.050*gate+carrier
    right=low*.95+airR*.052*gate+sine(t, 923, duration, phase=1.7, amp=.017)*(0.25+0.75*(.5+.5*np.sin(2*np.pi*(5/duration)*t+.3))**8)
    write_wav(path, normalize_stereo(softclip(np.column_stack([left,right]),1.0),.50))


def loop_sleep_channel(path: Path, duration=42.0, seed=14103):
    n,t=loop_timeline(duration); rng=np.random.default_rng(seed)
    wob=.26*np.sin(2*np.pi*(4/duration)*t)+.11*np.sin(2*np.pi*(9/duration)*t+.4)
    chordL=sine(t,48,duration,amp=.30,pm=wob)+sine(t,71.3,duration,phase=.8,amp=.19,pm=-.33*wob)+sine(t,95.8,duration,phase=2.4,amp=.11)
    chordR=sine(t,48,duration,phase=.05,amp=.29,pm=wob*1.08)+sine(t,72.1,duration,phase=.95,amp=.18,pm=-.30*wob)+sine(t,96.4,duration,phase=2.25,amp=.10)
    hissL=periodic_noise(n,duration,rng,450,3500,.3)*.025
    hissR=periodic_noise(n,duration,rng,420,3300,.3)*.027
    breathe=.25+.75*(.5+.5*np.sin(2*np.pi*(2/duration)*t-1.1))**2
    write_wav(path, normalize_stereo(softclip(np.column_stack([chordL+hissL*breathe,chordR+hissR*breathe]),1.05),.55))


def loop_green_static(path: Path, duration=38.0, seed=14104):
    n,t=loop_timeline(duration); rng=np.random.default_rng(seed)
    crackL=periodic_noise(n,duration,rng,700,6200,.1)
    crackR=periodic_noise(n,duration,rng,650,5900,.1)
    mod=(.16+.84*(.5+.5*np.sin(2*np.pi*(11/duration)*t+.5))**7)
    hum=sine(t,53,duration,amp=.20)+sine(t,106,duration,phase=1.2,amp=.055)
    ringL=sine(t,1367,duration,phase=.5,amp=.022)*(0.2+0.8*(.5+.5*np.sin(2*np.pi*(3/duration)*t))**10)
    ringR=sine(t,1391,duration,phase=.2,amp=.020)*(0.2+0.8*(.5+.5*np.sin(2*np.pi*(3/duration)*t+.2))**10)
    left=hum+crackL*.034*mod+ringL
    right=hum*.96+crackR*.033*mod+ringR
    write_wav(path, normalize_stereo(softclip(np.column_stack([left,right]),1.1),.48))


def loop_false_room(path: Path, duration=44.0, seed=14105):
    n,t=loop_timeline(duration); rng=np.random.default_rng(seed)
    mech=sine(t,59.5,duration,amp=.25)+sine(t,119,duration,phase=.4,amp=.07)+sine(t,178.5,duration,phase=1.0,amp=.025)
    drift=.5+.5*np.sin(2*np.pi*(5/duration)*t-.8)
    airyL=periodic_noise(n,duration,rng,70,1000,.75)*.045*(.2+.8*drift)
    airyR=periodic_noise(n,duration,rng,75,1100,.72)*.043*(.2+.8*np.roll(drift,int(.15*SR)))
    distant=sine(t,406,duration,phase=1.8,amp=.019)*(0.05+0.95*(.5+.5*np.sin(2*np.pi*(2/duration)*t))**12)
    write_wav(path, normalize_stereo(softclip(np.column_stack([mech+airyL+distant,mech*.97+airyR+distant*.8]),.95),.50))


def loop_dreamcatcher_core(path: Path, duration=48.0, seed=14106):
    n,t=loop_timeline(duration); rng=np.random.default_rng(seed)
    lfo=np.sin(2*np.pi*(3/duration)*t)
    low=sine(t,31.25,duration,amp=.30,pm=.14*lfo)+sine(t,62.5,duration,phase=.5,amp=.14)
    midL=sine(t,187.5,duration,phase=1.2,amp=.045)+sine(t,281.25,duration,phase=2.2,amp=.022)
    midR=sine(t,184.9,duration,phase=1.0,amp=.043)+sine(t,286.0,duration,phase=2.4,amp=.021)
    airL=periodic_noise(n,duration,rng,110,2400,.55)*.032
    airR=periodic_noise(n,duration,rng,120,2500,.52)*.034
    pulse=(.15+.85*(.5+.5*np.sin(2*np.pi*(4/duration)*t-1.0))**6)
    out=np.column_stack([low+midL+airL*pulse, low*.98+midR+airR*pulse])
    write_wav(path, normalize_stereo(softclip(out,1.0),.52))


def sfx_timeline(duration):
    n=int(duration*SR); t=np.arange(n)/SR; return n,t


def env_exp(t, tau, attack=.005):
    a=np.minimum(1.0, t/max(attack,1e-4)); return a*np.exp(-t/max(tau,1e-4))


def write_sfx(name, duration, fn, peak=.68, seed=0):
    n,t=sfx_timeline(duration); rng=np.random.default_rng(seed)
    x=fn(t,rng)
    if x.ndim==1: x=np.column_stack([x,x])
    # short fade at absolute tail to prevent click on stop
    m=min(len(x),int(.025*SR))
    if m>1: x[-m:]*=np.linspace(1,0,m)[:,None]
    write_wav(SFX/name, normalize_stereo(softclip(x,1.05),peak))


def f_stabilizer(t,rng):
    e=env_exp(t,.75,.01)
    rise=np.sin(2*np.pi*(220*t+190*t*t))*e*.55 + np.sin(2*np.pi*660*t)*env_exp(t,.42,.005)*.16
    sub=np.sin(2*np.pi*55*t)*env_exp(t,.55,.01)*.20
    return np.column_stack([rise+sub, np.roll(rise,int(.004*SR))*.96+sub])

def f_sleeper(t,rng):
    e=np.exp(-t/.9); wob=np.sin(2*np.pi*7.4*t)*(.12+.18*np.clip(t/1.6,0,1))
    phase=2*np.pi*(74*t-18*t*t)+wob
    low=np.sin(phase)*e*.55
    noise=rng.normal(0,1,len(t)); noise=np.convolve(noise,np.ones(15)/15,mode='same')*np.exp(-t/.45)*.16
    return np.column_stack([low+noise, low*.96-np.roll(noise,37)*.8])

def f_collapse(t,rng):
    sweep=np.sin(2*np.pi*(95*t-17*t*t))*env_exp(t,1.25,.01)*.52
    sub=np.sin(2*np.pi*34*t)*env_exp(t,1.55,.02)*.30
    noise=rng.normal(0,1,len(t)); noise=np.convolve(noise,np.ones(7)/7,mode='same')*env_exp(t,.55,.002)*.14
    return np.column_stack([sweep+sub+noise, sweep*.94+sub-np.roll(noise,71)*.75])

def f_null_layer(t,rng):
    e=np.exp(-t/.65)
    tone=np.sin(2*np.pi*(520*t-150*t*t))*e*.34 + np.sin(2*np.pi*130*t)*np.exp(-t/1.1)*.20
    air=rng.normal(0,1,len(t)); air=np.convolve(air,np.ones(25)/25,mode='same')*np.exp(-t/.28)*.10
    return np.column_stack([tone+air, np.roll(tone,11)*.96-air*.7])

def f_null_exit(t,rng):
    click=np.sin(2*np.pi*920*t)*env_exp(t,.035,.001)*.30
    release=np.sin(2*np.pi*(150*t-35*t*t))*env_exp(t,.75,.002)*.42
    return np.column_stack([click+release, np.roll(click,9)+release*.96])

def f_gleebs(t,rng):
    chirp=np.sin(2*np.pi*(1450*t+830*t*t))*env_exp(t,.24,.003)*.19
    chirp+=np.sin(2*np.pi*(2200*t+300*t*t))*env_exp(t,.18,.001)*.09
    low=np.sin(2*np.pi*92*t)*env_exp(t,.38,.005)*.08
    return np.column_stack([chirp+low, np.roll(chirp,31)*.87+low])

def f_seam(t,rng):
    # slow swell into a short glassy lock
    swell=(1-np.exp(-t/.18))*np.exp(-t/1.1)
    x=np.sin(2*np.pi*(178*t+80*t*t))*swell*.25 + np.sin(2*np.pi*713*t)*env_exp(t,.6,.12)*.08
    return np.column_stack([x, np.roll(x,23)*.97])

def f_false(t,rng):
    air=rng.normal(0,1,len(t)); air=np.convolve(air,np.ones(18)/18,mode='same')*env_exp(t,.23,.002)*.14
    fall=np.sin(2*np.pi*(440*t-140*t*t))*env_exp(t,.33,.002)*.19
    return np.column_stack([air+fall, -np.roll(air,19)*.75+fall*.9])

def f_recovered(t,rng):
    e=env_exp(t,.58,.005)
    x=np.sin(2*np.pi*164*t)*e*.28+np.sin(2*np.pi*328*t)*env_exp(t,.32,.004)*.12
    th=np.sin(2*np.pi*48*t)*env_exp(t,.5,.005)*.13
    return np.column_stack([x+th,np.roll(x,14)*.95+th])

def f_relay(t,rng):
    e=env_exp(t,.48,.003)
    x=np.sin(2*np.pi*294*t)*e*.20+np.sin(2*np.pi*588*t)*env_exp(t,.22,.002)*.08
    return np.column_stack([x,np.roll(x,18)*.94])

def f_resonance(t,rng):
    dur=max(float(t[-1]) if len(t) else 1.85, .001)
    env=(np.sin(np.pi*np.clip(t/max(dur,.001),0,1))**1.15)*np.exp(-.20*t)
    base=.26*np.sin(2*np.pi*73*t)+.16*np.sin(2*np.pi*109.5*t+.7)
    beat=.10*np.sin(2*np.pi*(146+4*np.sin(2*np.pi*1.7*t))*t+1.1)
    chirp=np.sin(2*np.pi*(420*t+.5*(560/max(dur,.001))*t*t))*.075*(.25+.75*np.clip(t/.7,0,1))
    flutter=.055*np.sin(2*np.pi*7.2*t)*np.sin(2*np.pi*292*t+.35)
    pulse=np.exp(-((t-1.08)/.11)**2)*.11*np.sin(2*np.pi*54*t)
    mono=(base+beat+chirp+flutter)*env+pulse
    left=mono+.025*np.sin(2*np.pi*487*t+.2)*env
    right=mono+.025*np.sin(2*np.pi*487*t+1.0)*env
    return np.column_stack([left,right])

loops=[
 ('01_intercept_hum.wav', loop_intercept_hum),
 ('02_empty_carrier.wav', loop_empty_carrier),
 ('03_sleep_channel.wav', loop_sleep_channel),
 ('04_green_static.wav', loop_green_static),
 ('05_false_room.wav', loop_false_room),
 ('06_dreamcatcher_core.wav', loop_dreamcatcher_core),
]
for name,fn in loops:
    print('GENERATE', name); fn(MUSIC/name)

write_sfx('stabilizer.wav',1.35,f_stabilizer,.64,201)
write_sfx('sleeper_disturb.wav',2.15,f_sleeper,.69,202)
write_sfx('instance_collapse.wav',2.65,f_collapse,.72,203)
write_sfx('null_layer.wav',1.75,f_null_layer,.62,204)
write_sfx('null_exit.wav',1.35,f_null_exit,.62,205)
write_sfx('gleebs_trace.wav',.82,f_gleebs,.50,206)
write_sfx('memory_seam.wav',1.25,f_seam,.52,207)
write_sfx('false_sleeper_resolve.wav',.90,f_false,.48,208)
write_sfx('room_recovered.wav',1.10,f_recovered,.54,209)
write_sfx('relay_online.wav',.72,f_relay,.47,210)
write_sfx('sleeper_resonance.wav',1.85,f_resonance,.55,211)
print('DONE')
