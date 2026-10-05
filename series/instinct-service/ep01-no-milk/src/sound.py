"""Sound design + mix for an episode, driven by build/<ep>/timeline.json (48 kHz stereo, exact duration).

Layers: dialogue (TTS lines), room tone, distant wordless murmur and cutlery, fridge hum (louder while the door
is open), UV-lamp hum (while UV is on), soft lounge music (electric piano / upright bass / brushes) that ducks
out in the awkward pauses, and synthesized Foley. Everything is procedural; nothing is downloaded.

usage: python src/sound.py ep01_no_milk   ->  build/<ep>/mix.wav (+ stems/dialogue.wav for verification)
"""
import json
import subprocess
import sys

import numpy as np
import soundfile as sf
from scipy import signal

from common import build_dir, load, save, series_cfg

SR = 48000
rng = np.random.default_rng(90)


def db(x):
    return 10 ** (x / 20)


def ease(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def channel(keys, t, default=0.0):
    """Same hold-then-ease semantics as the animation (vectorised over t)."""
    if not keys:
        return np.full_like(t, default, dtype=float)
    v = np.full_like(t, float(keys[0][1]) if not isinstance(keys[0][1], (list, dict, str)) else default, dtype=float)
    for k in keys:
        kt, kv = k[0], k[1]
        if isinstance(kv, (list, dict, str)):
            continue
        d = k[2] if len(k) > 2 else 0.35
        e = ease((t - (kt - d)) / d) if d > 0 else (t >= kt).astype(float)
        v = v + (kv - v) * e
    return v


def bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def lp(x, hi, order=2):
    return signal.sosfilt(signal.butter(order, hi, btype="low", fs=SR, output="sos"), x)


def hp(x, lo, order=2):
    return signal.sosfilt(signal.butter(order, lo, btype="high", fs=SR, output="sos"), x)


def env(n, a, d, curve=1.0):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-np.maximum(0, t - a) / max(d, 1e-4))
    return e ** curve


def tone(freqs, dur, decays, amps, a=0.002):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for f, dcy, am in zip(freqs, decays, amps):
        y += am * np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * np.exp(-t / dcy)
    return y * np.minimum(1, t / a)


def noise(dur):
    return rng.standard_normal(int(dur * SR))


# ------------------------------------------------------------------ foley
def S(*parts):
    """Sum layers of different lengths."""
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def burst(dur, a, d, f=None):
    y = noise(dur)
    if f:
        y = f(y)
    return y * env(len(y), a, d)


def sfx(name):
    if name == "menu_close":
        return S(burst(0.12, 0.004, 0.03, lambda x: lp(x, 900)) * 0.8, tone([140], 0.12, [0.03], [0.5]))
    if name == "menu_set":
        return S(tone([95, 180], 0.3, [0.06, 0.03], [0.9, 0.3]), burst(0.3, 0.002, 0.02, lambda x: lp(x, 1500)) * 0.6)
    if name == "glass_slide":
        return bp(noise(0.55), 1800, 6500) * np.sin(np.linspace(0, np.pi, int(0.55 * SR))) ** 2 * 0.5
    if name == "glass_set":
        return S(tone([2380, 3910, 5720], 0.6, [0.18, 0.1, 0.06], [0.35, 0.2, 0.1]), tone([120], 0.15, [0.03], [0.6]))
    if name == "fridge_open":
        whoosh = bp(noise(0.6), 300, 2500) * np.sin(np.linspace(0, np.pi, int(0.6 * SR))) * 0.2
        return S(burst(0.35, 0.01, 0.07, lambda x: lp(x, 700)), whoosh)
    if name == "fridge_close":
        return S(tone([70, 130], 0.4, [0.08, 0.05], [1.0, 0.4]), burst(0.4, 0.003, 0.04, lambda x: lp(x, 900)) * 0.7)
    if name == "bottle_clink":
        return tone([1820, 3140, 4620], 0.5, [0.14, 0.08, 0.05], [0.4, 0.25, 0.12])
    if name == "bottle_rattle":
        return tone([930, 2210], 0.25, [0.05, 0.03], [0.3, 0.12])
    if name == "bottle_set":
        return S(tone([110, 1240, 2650], 0.45, [0.04, 0.12, 0.07], [0.8, 0.25, 0.12]), burst(0.2, 0.002, 0.015, lambda x: lp(x, 2000)) * 0.4)
    if name == "notify":
        a = tone([1318.5, 2637], 0.7, [0.25, 0.12], [0.5, 0.1])
        b = tone([1975.5, 3951], 0.9, [0.35, 0.15], [0.5, 0.1])
        return S(a, np.concatenate([np.zeros(int(0.13 * SR)), b]))
    if name == "bowtie_rustle":
        return bp(noise(0.3), 1500, 7000) * np.sin(np.linspace(0, np.pi, int(0.3 * SR))) ** 3 * 0.4
    if name == "lamp_lift":
        return S(tone([420, 1150], 0.18, [0.03, 0.02], [0.5, 0.2]), burst(0.05, 0.001, 0.008, lambda x: hp(x, 2000)) * 0.3)
    if name == "dimmer_click":
        parts = [np.concatenate([np.zeros(int(t0 * SR)), burst(0.02, 0.0005, 0.004, lambda x: hp(x, 2500)) * g])
                 for t0, g in ((0.0, 0.35), (0.07, 0.35), (0.14, 0.35), (0.21, 0.8))]
        return S(*parts)
    if name == "uv_click":
        parts = [np.concatenate([np.zeros(int(t0 * SR)), burst(0.03, 0.0004, 0.005, lambda x: bp(x, 1200, 9000)) * g])
                 for t0, g in ((0.0, 1.0), (0.035, 0.5))]
        return S(*parts, tone([180], 0.12, [0.02], [0.3]))
    if name == "register_chime":
        return tone([1568, 2093, 3136, 4186], 1.6, [0.55, 0.42, 0.25, 0.15], [0.55, 0.35, 0.15, 0.06])
    if name == "tap":
        return S(tone([240, 520], 0.12, [0.025, 0.015], [0.8, 0.3]), burst(0.03, 0.0005, 0.006, lambda x: lp(x, 3000)) * 0.5)
    raise KeyError(name)


def reverb_ir(dur=0.9, damp=3500):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ir = np.stack([lp(rng.standard_normal(n), damp) * np.exp(-t * 6.5) for _ in range(2)], 1)
    ir[: int(0.012 * SR)] = 0
    return ir / np.sqrt((ir ** 2).sum(0))


class Bus:
    def __init__(self, n):
        self.x = np.zeros((n, 2))

    def add(self, t0, mono, gain_db=0.0, pan=0.0):
        i0 = int(round(t0 * SR))
        if i0 >= len(self.x):
            return
        if i0 < 0:
            mono, i0 = mono[-i0:], 0
        n = min(len(mono), len(self.x) - i0)
        g = db(gain_db)
        self.x[i0:i0 + n, 0] += mono[:n] * g * np.cos((pan + 1) * np.pi / 4) * 1.414
        self.x[i0:i0 + n, 1] += mono[:n] * g * np.sin((pan + 1) * np.pi / 4) * 1.414


# ------------------------------------------------------------------ music
def mtof(m):
    return 440 * 2 ** ((m - 69) / 12)


def epiano(m, dur, vel=0.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = mtof(m)
    mod = np.sin(2 * np.pi * f * 1.0 * t) * 1.2 * np.exp(-t * 3)
    y = np.sin(2 * np.pi * f * t + mod) * np.exp(-t * 0.9)
    y += 0.25 * np.sin(2 * np.pi * f * 4.0 * t) * np.exp(-t * 6)
    y *= 1 + 0.12 * np.sin(2 * np.pi * 4.6 * t)
    rel = np.minimum(1, (dur - t) / 0.25)
    return y * vel * np.minimum(1, t / 0.004) * np.clip(rel, 0, 1)


def bass(m, dur, vel=0.8):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = mtof(m)
    y = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t) * np.exp(-t * 4)
    return lp(y * np.exp(-t * 1.8) * np.minimum(1, t / 0.008), 900) * vel


def music(total):
    bpm = 72
    beat = 60 / bpm
    bar = 4 * beat
    prog = [  # F major lounge: Fmaj9 | Dm9 | Gm9 | C13sus
        ([53, 57, 60, 64, 67], 41), ([50, 57, 60, 64, 65], 38),
        ([55, 58, 62, 65, 69], 43), ([52, 58, 62, 65, 69], 36)]
    bus = Bus(int(total * SR))
    t = 0.0
    k = 0
    while t < total:
        chord, root = prog[k % 4]
        # comping: chord on 1 and the "and" of 2, quietly
        for off, vel in ((0.0, 0.32), (1.5 * beat, 0.18)):
            for i, m in enumerate(chord):
                bus.add(t + off + i * 0.012, epiano(m + 12, 2.2 * beat, vel / len(chord) * 2.2), 0, (i - 2) * 0.15)
        # walking-ish bass: root, fifth, approach
        for j, step in enumerate((0, 7, 12, 11 if k % 2 else 6)):
            bus.add(t + j * beat, bass(root + step - 12 if step > 7 else root + step, beat * 0.95, 0.55), 0, -0.05)
        # brushes: swish on 2 and 4, soft taps on the off-beats
        for j in range(4):
            sw = bp(noise(beat * 0.9), 2500, 9000) * np.sin(np.linspace(0, np.pi, int(beat * 0.9 * SR))) ** 2
            bus.add(t + j * beat, sw * (0.08 if j % 2 else 0.05), 0, 0.2)
        t += bar
        k += 1
    return bus.x


# ------------------------------------------------------------------ main
def main(ep):
    cfg = series_cfg()
    bd = build_dir(ep)
    tl = load(bd / "timeline.json")
    dur = tl["duration"]
    N = int(round(dur * SR))
    T = np.arange(N) / SR
    snd = tl["sound"]
    A = tl["acting"]
    amb = snd["ambience"]

    # ---- dialogue (level-matched by active RMS, short room reflection)
    dia = Bus(N)
    for ln in tl["lines"]:
        y, sr = sf.read(ln["wav"], dtype="float64")
        act = y[np.abs(y) > 0.02]
        rms = np.sqrt(np.mean(act ** 2)) if len(act) else 0.1
        y = y * (db(-19) / rms)
        dia.add(ln["start"], y, 0, 0.07 if ln["who"] == "bear" else -0.07)
    ir = reverb_ir(0.5, 4500)
    wet = np.stack([signal.fftconvolve(dia.x.mean(1), ir[:, c])[:N] for c in range(2)], 1)
    dialogue = dia.x + wet * 0.07

    # ---- ducking envelopes (music / ambience)
    duck_m = np.zeros(N)
    duck_a = np.zeros(N)
    for t0, t1, md, ad in snd["duck"]:
        w = ease((T - t0) / 0.35) * (1 - ease((T - t1) / 0.6))
        duck_m = np.minimum(duck_m, w * md)
        duck_a = np.minimum(duck_a, w * ad)
    gm, ga = db(duck_m), db(duck_a)

    # ---- ambience
    room = lp(np.cumsum(rng.standard_normal(N)) * 0.02, 380)
    room = room - lp(room, 25)
    room = room / np.std(room) * db(amb["room_db"])
    walla = np.zeros(N)
    for _ in range(5):  # wordless, distant: formant-band noise with syllable-rate motion
        lo = rng.uniform(250, 500)
        hi = lo * rng.uniform(3, 5)
        am = lp(rng.standard_normal(N), rng.uniform(3, 6))
        am = np.clip(am / np.std(am) * 0.6 + 0.4, 0, None)
        slow = lp(rng.standard_normal(N), 0.15)
        slow = np.clip(slow / np.std(slow) * 0.5 + 0.6, 0.1, None)
        walla += bp(rng.standard_normal(N), lo, hi) * am * slow
    walla = lp(walla, 1800) / np.std(walla) * db(amb["murmur_db"])
    ambience = np.stack([room + walla * 0.9, room * 0.95 + walla], 1)
    cl = Bus(N)
    t = 2.0
    while t < dur - 2:
        quiet = any(t0 - 0.5 < t < t1 + 0.5 for t0, t1, _, _ in snd["duck"])
        if not quiet:
            f0 = rng.uniform(2600, 4200)
            c = tone([f0, f0 * 1.52, f0 * 2.4], 0.4, [0.12, 0.07, 0.04], [0.3, 0.15, 0.08])
            cl.add(t, c, amb["clink_db"] + rng.uniform(-4, 2), rng.uniform(-0.8, 0.8))
        t += rng.uniform(2.5, 6.5)
    rir = reverb_ir(1.2, 2500)
    clw = np.stack([signal.fftconvolve(cl.x.mean(1), rir[:, c])[:N] for c in range(2)], 1)
    ambience = (ambience + cl.x * 0.4 + clw * 0.8) * ga[:, None]

    # ---- fridge hum (constant; louder with the door open) - never ducked: it is the silence
    door = channel(A["props_pose"].get("fridge_door", []), T) / 65.0
    hum = sum(a * np.sin(2 * np.pi * f * T + p) for f, a, p in ((60, 1.0, 0), (120, 0.6, 1), (180, 0.25, 2), (240, 0.15, 3)))
    hum *= 1 + 0.05 * np.sin(2 * np.pi * 0.23 * T)
    hum += bp(rng.standard_normal(N), 180, 700) * 0.35
    hum = hum / np.std(hum) * db(amb["fridge_hum_db"]) * db(amb["fridge_open_boost_db"] * door)
    fridge = np.stack([hum * 0.8, hum * 1.0], 1)

    # ---- UV lamp hum
    uv = channel(A.get("uv", []), T)
    buzz = (np.sign(np.sin(2 * np.pi * 120 * T)) * 0.3 + np.sin(2 * np.pi * 240 * T)) * 0.5 + np.sin(2 * np.pi * 9100 * T) * 0.05
    buzz = lp(buzz, 3000) * uv * db(-47)
    uvh = np.stack([buzz * 1.0, buzz * 0.7], 1)

    # ---- music (ducked; a faint glassy swell under the reveal, no stinger)
    mus = music(dur) * db(snd["music"]["db"])
    mus *= gm[:, None]
    mus *= (1 - ease((T - (dur - 1.4)) / 1.3))[:, None]
    sw = (np.sin(2 * np.pi * 1760 * T) + 0.6 * np.sin(2 * np.pi * 2637 * T)) * ease((T - 73.0) / 1.2) * (1 - ease((T - 76.0) / 2.0))
    shimmer = np.stack([sw, np.roll(sw, 240)], 1) * db(-46) * (1 + 0.2 * np.sin(2 * np.pi * 5 * T))[:, None]

    # ---- foley cues + automatic bear finger taps
    fx = Bus(N)
    for t0, name, g, pan in snd["cues"]:
        fx.add(t0, sfx(name), g, pan)
    for t0, n, iv in A["bear"].get("taps", []):
        for k in range(int(n)):
            fx.add(t0 + (k + 1) * iv, sfx("tap"), -26 + rng.uniform(-1.5, 1.5), 0.25)
    fxw = np.stack([signal.fftconvolve(fx.x.mean(1), rir[:, c])[:N] for c in range(2)], 1)
    foley = fx.x + fxw * 0.18

    mix = dialogue + ambience + fridge + uvh + mus + shimmer + foley
    # fade the very edges to avoid clicks; keep exact length
    edge = int(0.02 * SR)
    mix[:edge] *= np.linspace(0, 1, edge)[:, None]
    mix[-int(0.4 * SR):] *= np.linspace(1, 0, int(0.4 * SR))[:, None]
    out = bd / "mix_raw.wav"
    sf.write(out, mix.astype(np.float32), SR, subtype="FLOAT")
    (bd / "stems").mkdir(exist_ok=True)
    sf.write(bd / "stems" / "dialogue.wav", dialogue.astype(np.float32), SR, subtype="FLOAT")

    # ---- loudness: measure, apply ONE linear gain (no dynamic normalisation that would lift the silences), limit
    target = cfg["audio"]["loudness_lufs"]
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(out), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    js = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    gain = target - float(js["input_i"])
    tp = cfg["audio"]["true_peak_db"]
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out), "-af",
                    f"volume={gain:.2f}dB,alimiter=limit={db(tp):.4f}:attack=2:release=60:level=disabled",
                    "-ar", str(SR), "-c:a", "pcm_s24le", str(bd / "mix.wav")], check=True)
    info = sf.info(bd / "mix.wav")
    save(bd / "mix_report.json", {"input_lufs": float(js["input_i"]), "gain_db": gain, "duration": info.duration})
    print(f"mix ok: {info.duration:.3f}s, measured {float(js['input_i']):.1f} LUFS -> gain {gain:+.1f} dB")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ep01_no_milk")
