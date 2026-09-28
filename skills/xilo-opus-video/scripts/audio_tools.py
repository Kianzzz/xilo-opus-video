#!/usr/bin/env python3
"""Small audio toolkit: synthesize UI/motion sound effects on a timeline, normalize loudness,
and draw waveform/spectrum images so the model can check audio it cannot hear.

  sfx:        audio_tools.py sfx timeline.json audio/sfx.wav
  normalize:  audio_tools.py normalize audio/mix.wav audio/mix_norm.wav      (-14 LUFS, -1 dBTP)
  check:      audio_tools.py check audio/mix_norm.wav --out qa/audio

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


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sp = ap.add_subparsers(dest="cmd", required=True)
p = sp.add_parser("sfx"); p.add_argument("timeline"); p.add_argument("out"); p.set_defaults(fn=cmd_sfx)
p = sp.add_parser("normalize"); p.add_argument("inp"); p.add_argument("out"); p.set_defaults(fn=cmd_normalize)
p = sp.add_parser("check"); p.add_argument("inp"); p.add_argument("--out", required=True); p.set_defaults(fn=cmd_check)
args = ap.parse_args(); args.fn(args)
