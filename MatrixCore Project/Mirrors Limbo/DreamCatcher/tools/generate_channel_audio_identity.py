from __future__ import annotations
from pathlib import Path
import json, math, wave
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets' / 'audio' / 'tv_channels'
CFG = ROOT / 'data' / 'tv_channel_audio.json'
SR = 22050
DUR = 8.0
N = int(SR * DUR)
t = np.arange(N, dtype=np.float64) / SR


def midi(n):
    return 440.0 * (2.0 ** ((n - 69) / 12.0))

def osc(freq, amp=1.0, phase=0.0, kind='sine'):
    x = 2*np.pi*freq*t + phase
    if kind == 'sine': return amp*np.sin(x)
    if kind == 'square': return amp*np.sign(np.sin(x))
    if kind == 'triangle': return amp*(2/np.pi)*np.arcsin(np.sin(x))
    if kind == 'saw': return amp*(2*((freq*t + phase/(2*np.pi)) % 1.0)-1.0)
    raise ValueError(kind)

def env_event(start, length, curve=5.0):
    e = np.zeros(N)
    a = max(0, int(start*SR)); b = min(N, int((start+length)*SR))
    if b <= a: return e
    u = np.linspace(0,1,b-a,endpoint=False)
    # quick attack, exponential-ish decay
    e[a:b] = np.minimum(1,u*25) * np.exp(-curve*u)
    return e

def tone_event(start, length, freq, amp=.3, kind='sine', curve=3.0):
    return osc(freq, amp=amp, kind=kind) * env_event(start,length,curve)

def kick(start, amp=.6):
    e=env_event(start,.35,curve=7)
    ph=2*np.pi*(58*t + 24*(1-np.exp(-8*np.maximum(0,t-start))))
    return amp*np.sin(ph)*e

def noise_event(rng, start, length, amp=.25, curve=5):
    raw=rng.normal(0,1,N)
    # simple highpass-ish difference for hiss/snare
    raw=np.concatenate(([0.0], np.diff(raw)))
    return amp*raw*env_event(start,length,curve)

def low_noise(rng, amp=.15):
    raw=rng.normal(0,1,N)
    # low-pass by moving average
    k=180
    kernel=np.ones(k)/k
    return amp*np.convolve(raw,kernel,mode='same')

def tiled_noise(rng, period=.5, amp=.1):
    m=max(16,int(period*SR))
    tile=rng.normal(0,1,m)
    y=np.resize(tile,N)
    return amp*y

def seq(notes, step=.5, amp=.18, kind='triangle', octave_shift=0, sustain=.38):
    y=np.zeros(N)
    for i,n in enumerate(notes):
        if n is None: continue
        st=i*step
        if st>=DUR: break
        y += tone_event(st,min(sustain,step),midi(n+octave_shift),amp,kind,curve=2.4)
    return y

def pulse_train(freq=2.0, amp=.2, duty=.15):
    p=(t*freq)%1.0
    return amp*(p<duty).astype(float)

def siren(f0=420,f1=720,rate=.3,amp=.22):
    f=(f0+f1)/2 + (f1-f0)/2*np.sin(2*np.pi*rate*t)
    phase=2*np.pi*np.cumsum(f)/SR
    return amp*np.sin(phase)

def normalize_loop(y, peak=.82):
    # DC remove, soft clip, boundary crossfade
    y=y-np.mean(y)
    mx=np.max(np.abs(y)) or 1
    y=y*(peak/mx)
    y=np.tanh(y*1.15)/np.tanh(1.15)
    fade=int(.20*SR)
    # blend final fade toward first fade to suppress loop clicks
    a=np.linspace(0,1,fade,endpoint=False)
    y[-fade:] = y[-fade:]*(1-a) + y[:fade]*a
    y[-1]=y[0]
    return np.clip(y,-1,1)

def write_wav(path,y):
    path.parent.mkdir(parents=True,exist_ok=True)
    pcm=(y*32767).astype('<i2')
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())

def build(cid):
    seed=sum((i+1)*ord(c) for i,c in enumerate(cid)) + 7919
    rng=np.random.default_rng(seed)
    hum=osc(50, .035)+osc(100,.018)
    y=np.zeros(N)
    if cid=='security':
        y=hum + osc(82,.07) + tiled_noise(rng,.25,.018)
        for st in [0.4,2.4,4.4,6.4]: y+=tone_event(st,.16,980,.16,'sine',5)+tone_event(st+.18,.10,1220,.09,'sine',6)
    elif cid=='news':
        y=hum*.5 + seq([60,64,67,72,67,64,62,67,69,74,69,67,60,64,67,72],.5,.11,'triangle')
        for st in np.arange(.25,8,.5): y+=tone_event(st,.04,1800,.035,'square',8)
    elif cid=='cartoon':
        y=seq([72,76,79,84,79,76,74,79,81,84,88,84,79,76,74,72],.5,.15,'square')
        for st in np.arange(0,8,1): y+=tone_event(st,.08,140,.18,'sine',7)
    elif cid=='archive':
        y=hum + osc(110,.07)+osc(165,.035)+tiled_noise(rng,1.0,.012)
        for st in [1,3,5,7]: y+=tone_event(st,.5,440,.07,'sine',2)
    elif cid=='combat':
        y=osc(55,.10)+seq([48,48,51,48,55,53,51,48]*2,.5,.08,'saw')
        for st in np.arange(0,8,.5): y+=kick(st,.28)
        for st in np.arange(.25,8,.5): y+=noise_event(rng,st,.12,.035,10)
    elif cid=='dance':
        y=seq([45,45,48,45,50,48,43,43]*2,.5,.12,'saw')
        y+=seq([69,72,76,72,67,72,74,79]*2,.5,.07,'square',sustain=.18)
        for st in np.arange(0,8,.5): y+=kick(st,.32)
        for st in np.arange(.25,8,.5): y+=noise_event(rng,st,.08,.025,12)
    elif cid=='dream':
        y=osc(midi(48),.055)+osc(midi(55),.045)+osc(midi(60),.035)
        y*=0.7+0.3*np.sin(2*np.pi*.18*t)
        y+=seq([72,None,74,None,79,None,76,None,72,None,67,None,69,None,71,None],.5,.07,'sine',sustain=.9)
        y+=low_noise(rng,.02)
    elif cid=='emergency':
        y=siren(520,860,.25,.16)+hum*.4
        for st in np.arange(0,8,1): y+=tone_event(st,.12,1400,.17,'square',7)+tone_event(st+.18,.12,1400,.17,'square',7)
    elif cid=='kaiju':
        y=osc(34,.18)+osc(51,.09)+low_noise(rng,.05)
        for st in [0.7,2.6,4.6,6.6]: y+=kick(st,.52)+noise_event(rng,st,.8,.065,1.8)
    elif cid=='league':
        y=seq([60,64,67,72,67,64,65,69,72,77,72,69,67,71,74,79],.5,.11,'triangle')
        y+=low_noise(rng,.035)
        for st in [1.75,3.75,5.75,7.75]: y+=tone_event(st,.08,1900,.09,'square',8)
    elif cid=='mix':
        y=seq([60,67,63,70,58,65,61,68]*2,.5,.065,'saw') + tiled_noise(rng,.125,.04)
        for st,f in zip(np.arange(.2,8,.7),[330,880,440,1320,550,1760,660,990,770,1440,500,1200]): y+=tone_event(float(st),.09,float(f),.08,'square',9)
    elif cid=='noisefight':
        y=tiled_noise(rng,.25,.08)+osc(46,.08)
        for i,st in enumerate(np.arange(0,8,.25)):
            if i%2==0: y+=noise_event(rng,float(st),.10,.07,8)
            else: y+=tone_event(float(st),.07,90+(i%5)*37,.08,'square',10)
    elif cid=='pirate':
        # original 6/8-ish modal motif, not based on an existing tune
        y=seq([57,60,64,65,64,60,55,59,62,64,62,59,57,60,64,67],.5,.12,'triangle')
        for st in np.arange(0,8,1.5): y+=kick(float(st),.18)
        y+=low_noise(rng,.018)
    elif cid=='racing':
        # engine-like harmonic stack with cyclic rev
        f=72+38*(0.5+0.5*np.sin(2*np.pi*.25*t))
        ph=2*np.pi*np.cumsum(f)/SR
        y=.12*np.sin(ph)+.06*np.sin(2*ph)+.035*np.sin(3*ph)+tiled_noise(rng,.04,.015)
        for st in [0.5,1.0,1.5,4.5,5.0,5.5]: y+=tone_event(st,.12,950,.10,'square',8)
    elif cid=='ritual':
        y=osc(55,.10)+osc(82.5,.06)+osc(110,.04)
        y*=.75+.25*np.sin(2*np.pi*.125*t)
        for st in [0,2,4,6]: y+=tone_event(st,1.2,220,.09,'sine',1.3)
        for st in [1.75,5.75]: y+=tone_event(st,.9,1320,.08,'sine',3)
    elif cid=='shop':
        y=seq([60,64,67,72,64,67,71,74,65,69,72,76,67,71,74,79],.5,.10,'triangle')
        for st in [1.9,3.9,5.9,7.9]: y+=tone_event(st,.12,1568,.09,'sine',7)+tone_event(st+.12,.18,2093,.07,'sine',5)
    elif cid=='sportcast':
        y=hum*.35+seq([55,62,67,62,57,64,69,64]*2,.5,.07,'triangle')+low_noise(rng,.04)
        for st in np.arange(0,8,2): y+=noise_event(rng,float(st),.35,.045,2)
    elif cid=='sports':
        y=low_noise(rng,.06)+osc(65,.045)
        for st in np.arange(0,8,1): y+=kick(float(st),.20)
        for st in [1.2,3.6,6.2]: y+=tone_event(st,.18,2200,.12,'sine',5)
    elif cid=='static':
        y=tiled_noise(rng,.5,.18)+osc(60,.025)+osc(120,.015)
    elif cid=='surveil':
        y=hum+osc(73,.045)+tiled_noise(rng,.5,.012)
        for st in np.arange(.6,8,1.2): y+=tone_event(float(st),.08,820+(int(st*10)%3)*110,.08,'sine',8)
    elif cid=='teletext':
        y=hum*.3
        freqs=[1200,1600,2100,900,1800,1350,2400,1050]
        for i,st in enumerate(np.arange(0,8,.125)): y+=tone_event(float(st),.06,freqs[i%len(freqs)],.045,'square',9)
    elif cid=='tunnel':
        y=osc(42,.14)+low_noise(rng,.055)
        for st in [0,2,4,6]: y+=tone_event(st,1.5,84,.08,'sine',1.5)
        for st in [1,3,5,7]: y+=noise_event(rng,st,.7,.025,2)
    elif cid=='weather':
        y=seq([60,None,64,None,67,None,69,None,65,None,62,None,64,None,67,None],.5,.055,'sine',sustain=1.1)
        y+=tiled_noise(rng,.25,.025)+low_noise(rng,.018)
    elif cid=='wilderness':
        y=low_noise(rng,.07)+osc(32,.025)
        chirps=[(0.8,1800),(1.0,2200),(2.7,1500),(3.0,1950),(5.1,2100),(5.35,2600),(7.1,1700)]
        for st,f in chirps: y+=tone_event(st,.10,f,.06,'sine',5)+tone_event(st+.10,.08,f*1.12,.04,'sine',6)
    elif cid=='wrestling':
        y=seq([40,40,43,45,40,47,45,43]*2,.5,.11,'square')+low_noise(rng,.04)
        for st in np.arange(0,8,1): y+=kick(float(st),.28)
        for st in [0,4]: y+=tone_event(st+.05,.8,740,.10,'sine',4)+tone_event(st+.15,.7,980,.08,'sine',4)
    else:
        y=hum
    return normalize_loop(y)

VOLUMES={
 'security':.10,'news':.11,'cartoon':.10,'archive':.09,'combat':.11,'dance':.11,
 'dream':.10,'emergency':.09,'kaiju':.09,'league':.10,'mix':.09,'noisefight':.08,
 'pirate':.10,'racing':.10,'ritual':.09,'shop':.10,'sportcast':.10,'sports':.10,
 'static':.07,'surveil':.09,'teletext':.07,'tunnel':.09,'weather':.09,'wilderness':.09,'wrestling':.10,
}

cfg=json.loads(CFG.read_text())
for entry in cfg['channels']:
    cid=entry['id']
    y=build(cid)
    write_wav(OUT/f'{cid}.wav',y)
    entry['placeholder']=True
    entry['placeholder_kind']='procedural_channel_identity'
    entry['volume']=VOLUMES.get(cid,.10)
    entry['duration_seconds']=DUR
    entry['sample_rate']=SR
cfg['schema_version']=2
cfg['scope']='TV channel audio identity authority (procedural placeholders until original recordings are recovered)'
cfg['default_volume']=.10
cfg['replacement_rule']='Each channel has a distinct seamless WAV identity loop. These are original procedural placeholders, not recovered historic music; replace one-for-one by channel id when original recordings are recovered.'
CFG.write_text(json.dumps(cfg,indent=2)+"\n")
print(f'generated {len(cfg["channels"])} channel loops at {SR} Hz, {DUR:.1f}s each')
