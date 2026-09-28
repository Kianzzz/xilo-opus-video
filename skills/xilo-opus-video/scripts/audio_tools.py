#!/usr/bin/env python3
"""Small audio toolkit: synthesize UI/motion sound effects on a timeline, normalize loudness,
and draw waveform/spectrum images so the model can check audio it cannot hear.

  sfx:        audio_tools.py sfx timeline.json audio/sfx.wav
  normalize:  audio_tools.py normalize audio/mix.wav audio/mix_norm.wav      (-14 LUFS, -1 dBTP)
  check:      audio_tools.py check audio/mix_norm.wav --out qa/audio
  beats:      audio_tools.py beats music.mp3 > audio/beats.json     (measure a supplied track)

beats.json: {"bpm": 120.0, "beats": [...], "downbeats": [...], "hits": [...]}
  beats = where state changes go, downbeats = where the big moments go, hits = where SFX go.
  Uses librosa when installed, otherwise a numpy-only tracker (fine for steady-tempo music).

timeline.json:
  {"duration": 12, "bpm": 120, "beat": "kick",            # optional soft pulse on every beat
   "events": [{"t": 1.0, "sound": "click"}, {"t": 2.0, "sound": "success", "gain": 0.8},
              {"t": 3.5, "sound": "whoosh"}, {"t": 4.0, "sound": "pop"}, {"t": 6.0, "sound": "impact"}]}
sounds: click, pop, success, whoosh, impact, tick, kick, riser
Music itself is better written per project (see references/craft-rules.md); this covers the effects layer.
"""
import argparse, json, re, subprocess, sys, wave

import numpy as np

SR = 48000


def env(n, attack=0.002, decay=0.1):
    x = np.arange(n) / SR
    return np.minimum(1, x / max(attack, 1e-4)) * np.exp(-x / decay)


def tone(freqs, length, decay, attack=0.003):
    n = int(length * SR); x = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * f * x) for f in freqs) / len(freqs) * env(n, attack, decay)


def noise(length, seed=1):
    return np.random.default_rng(seed).standard_normal(int(length * SR))


def sweep(f0, f1, length):
    n = int(length * SR); f = np.geomspace(f0, f1, n)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def lowpass(sig, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR); out = np.zeros_like(sig); y = 0.0
    for i, s in enumerate(sig):
        y = (1 - a) * s + a * y; out[i] = y
    return out


SOUNDS = {
    "click": lambda: noise(0.04) * env(int(0.04 * SR), 0.0005, 0.005) * 0.6 + tone([2400], 0.04, 0.008) * 0.6,
    "tick": lambda: tone([3200], 0.03, 0.006),
    "pop": lambda: np.concatenate([tone([880], 0.06, 0.03), tone([1175, 1760], 0.4, 0.12)]),
    "success": lambda: np.concatenate([tone([1318.5], 0.09, 0.06), tone([1318.5, 1975.5], 0.5, 0.15)]),
    "whoosh": lambda: lowpass(noise(0.45, 7), 2500) * np.hanning(int(0.45 * SR)) * 2.2,
    "impact": lambda: sweep(160, 38, 0.6) * env(int(0.6 * SR), 0.001, 0.18) + lowpass(noise(0.6, 3), 900) * env(int(0.6 * SR), 0.001, 0.05),
    "kick": lambda: sweep(140, 45, 0.35) * env(int(0.35 * SR), 0.001, 0.12),
    "riser": lambda: sweep(200, 1800, 1.2) * np.linspace(0, 1, int(1.2 * SR)) ** 2 * 0.5 + lowpass(noise(1.2, 5), 4000) * np.linspace(0, 1, int(1.2 * SR)) ** 2 * 0.4,
}


def write_wav(path, sig):
    peak = np.abs(sig).max() or 1
    sig = sig / peak * 0.89
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((sig * 32767).astype(np.int16).tobytes())


def cmd_sfx(a):
    spec = json.load(open(a.timeline))
    out = np.zeros(int(spec["duration"] * SR) + SR)
    if spec.get("beat"):
        for t in np.arange(0, spec["duration"], 60 / spec.get("bpm", 120)):
            s = SOUNDS[spec["beat"]](); i = int(t * SR); out[i:i + len(s)] += s[:len(out) - i] * 0.3
    for ev in spec["events"]:
        if ev["sound"] not in SOUNDS:
            sys.exit(f"unknown sound {ev['sound']}; choose from {', '.join(SOUNDS)}")
        s = SOUNDS[ev["sound"]]()
        i = int(ev["t"] * SR); n = min(len(s), len(out) - i)
        out[i:i + n] += s[:n] * ev.get("gain", 0.7)
    write_wav(a.out, out[: int(spec["duration"] * SR)])
    print(f"{a.out}: {len(spec['events'])} events, {spec['duration']}s")


def cmd_normalize(a):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.inp, "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-ar", str(SR), a.out])
    sys.exit(r.returncode)


def cmd_check(a):
    st = subprocess.run(["ffmpeg", "-hide_banner", "-i", a.inp, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    summary = st[st.rfind("Summary:"):]
    lufs = re.search(r"I:\s+(-?[\d.]+) LUFS", summary); peak = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.inp, "-filter_complex", "showwavespic=s=1600x300:split_channels=0", "-frames:v", "1", f"{a.out}-wave.png"])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.inp, "-lavfi", "showspectrumpic=s=1600x500:legend=1", f"{a.out}-spectrum.png"])
    print(f"integrated loudness: {lufs.group(1) if lufs else '?'} LUFS (target -14)   true peak: {peak.group(1) if peak else '?'} dBFS (keep below -1)")
    print(f"images: {a.out}-wave.png, {a.out}-spectrum.png  (look for clipping, silence gaps, low-frequency rumble)")


def load_mono(path, sr=22050):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32), sr


def beats_numpy(y, sr):
    hop, n_fft = 256, 1024
    frames = 1 + (len(y) - n_fft) // hop
    win = np.hanning(n_fft)
    spec = np.abs(np.fft.rfft(np.stack([y[i * hop:i * hop + n_fft] * win for i in range(frames)]), axis=1))
    flux = np.maximum(0, np.diff(np.log1p(spec), axis=0)).sum(axis=1)
    onset = np.concatenate([[0], flux]); onset = (onset - onset.mean()) / (onset.std() + 1e-9)
    fps = sr / hop
    # tempo: autocorrelation of the onset envelope, 60-180 BPM, mild preference around 120,
    # refined to a fractional period so the grid does not drift over long tracks
    ac = np.correlate(onset, onset, mode="full")[len(onset) - 1:]
    lags = np.arange(int(fps * 60 / 180), int(fps * 60 / 60) + 1)
    score = ac[lags] * np.exp(-0.5 * (np.log2(60 * fps / lags / 120) / 0.9) ** 2)
    i = int(np.argmax(score)); period = float(lags[i])
    if 0 < i < len(score) - 1:
        l, c, r = score[i - 1], score[i], score[i + 1]
        period += 0.5 * (l - r) / (l - 2 * c + r) if (l - 2 * c + r) != 0 else 0
    n = len(onset)
    grid = lambda o: [int(round(o + k * period)) for k in range(int((n - o) / period) + 1) if round(o + k * period) < n]
    phase = max(range(int(period)), key=lambda o: onset[grid(o)].sum())
    # track: predict the next beat from the previous one, snap to a strong onset nearby
    beats, t, w = [], float(phase), max(2, int(period * 0.12))
    while t < n:
        c = int(round(t)); lo, hi = max(0, c - w), min(n, c + w + 1)
        j = lo + int(np.argmax(onset[lo:hi]))
        pos = j if onset[j] > 0.5 else c
        beats.append(pos); t = pos + period
    lag = n_fft / 2 / sr                       # frame index -> time at the window centre
    beat_t = np.array(beats) / fps + lag
    down0 = max(range(4), key=lambda k: onset[beats[k::4]].sum()) if len(beats) >= 4 else 0
    peaks = [i for i in range(1, n - 1) if onset[i] > 2 and onset[i] >= onset[i - 1] and onset[i] >= onset[i + 1]]
    hits, last = [], -10**9
    for i in peaks:
        if i - last > fps * 0.1: hits.append(i / fps + lag); last = i
    return 60 * fps / period, beat_t.tolist(), beat_t[down0::4].tolist(), hits


def cmd_beats(a):
    try:
        import librosa
        y, sr = librosa.load(a.inp, sr=None, mono=True)
        tempo, fr = librosa.beat.beat_track(y=y, sr=sr, units="frames")
        beats = librosa.frames_to_time(fr, sr=sr).tolist()
        env_ = librosa.onset.onset_strength(y=y, sr=sr)
        pk = librosa.util.peak_pick(env_, pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.5, wait=10)
        bpm, downs, hits = float(np.atleast_1d(tempo)[0]), beats[::4], librosa.frames_to_time(pk, sr=sr).tolist()
    except ImportError:
        y, sr = load_mono(a.inp)
        bpm, beats, downs, hits = beats_numpy(y, sr)
    r = lambda xs: [round(x, 3) for x in xs]
    json.dump({"bpm": round(bpm, 2), "beats": r(beats), "downbeats": r(downs), "hits": r(hits)}, sys.stdout, indent=1)
    print(f"\nbpm {bpm:.1f}, {len(beats)} beats, {len(hits)} hits", file=sys.stderr)


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sp = ap.add_subparsers(dest="cmd", required=True)
p = sp.add_parser("sfx"); p.add_argument("timeline"); p.add_argument("out"); p.set_defaults(fn=cmd_sfx)
p = sp.add_parser("normalize"); p.add_argument("inp"); p.add_argument("out"); p.set_defaults(fn=cmd_normalize)
p = sp.add_parser("check"); p.add_argument("inp"); p.add_argument("--out", required=True); p.set_defaults(fn=cmd_check)
p = sp.add_parser("beats"); p.add_argument("inp"); p.set_defaults(fn=cmd_beats)
args = ap.parse_args(); args.fn(args)
