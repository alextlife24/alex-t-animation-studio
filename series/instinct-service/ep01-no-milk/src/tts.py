"""Generate every dialogue line with Kokoro (local neural TTS) and measure real durations.

usage: python src/tts.py ep01_no_milk
writes build/<ep>/voice/<line>.wav (48 kHz mono, trimmed) and build/<ep>/voice_manifest.json
Cached by text + voice settings, so re-running after a script edit only regenerates changed lines.
"""
import hashlib
import json
import re
import subprocess
import sys

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from common import MODELS, build_dir, characters, episode_dir, load, save

SR = 48000


def trim(y, sr, thr_db=-45, pad=0.04):
    env = np.abs(y)
    win = int(0.01 * sr)
    env = np.convolve(env, np.ones(win) / win, "same")
    idx = np.where(env > 10 ** (thr_db / 20))[0]
    if not len(idx):
        return y
    a = max(0, idx[0] - int(pad * sr))
    b = min(len(y), idx[-1] + int(pad * sr))
    return y[a:b]


def main(ep):
    from kokoro_onnx import Kokoro
    script = load(episode_dir(ep) / "script.json")
    chars = characters()
    out = build_dir(ep) / "voice"
    out.mkdir(exist_ok=True)
    man_p = build_dir(ep) / "voice_manifest.json"
    manifest = load(man_p) if man_p.exists() else {}
    k = None
    for ln in script["lines"]:
        v = chars[ln["who"]]["voice"]
        key = hashlib.sha1(json.dumps([ln["en"], ln.get("sentence_pause"), v], sort_keys=True).encode()).hexdigest()[:12]
        wav = out / f"{ln['id']}.wav"
        if manifest.get(ln["id"], {}).get("key") == key and wav.exists():
            continue
        if k is None:
            k = Kokoro(str(MODELS / "kokoro-v1.0.onnx"), str(MODELS / "voices-v1.0.bin"))
        style = sum(w * k.get_voice_style(s) for s, w in zip(v["style"], v["weights"]))
        # optional "sentence_pause": speak each sentence separately with a deliberate beat between
        parts = re.split(r"(?<=[.?!])\s+", ln["en"]) if ln.get("sentence_pause") else [ln["en"]]
        chunks = []
        for i, txt in enumerate(parts):
            y, sr = k.create(txt, voice=style, speed=v["speed"], lang=v["lang"])
            chunks.append(trim(resample_poly(y, SR, sr).astype(np.float32), SR))
            if i < len(parts) - 1:
                chunks.append(np.zeros(int(ln["sentence_pause"] * SR), np.float32))
        y = np.concatenate(chunks)
        if v.get("pitch_semitones"):
            raw, shifted = out / f"{ln['id']}_raw.wav", out / f"{ln['id']}_shift.wav"
            sf.write(raw, y, SR)
            ratio = 2 ** (v["pitch_semitones"] / 12)
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af",
                            f"rubberband=pitch={ratio:.5f}:formant=preserved:transients=smooth",
                            str(shifted)], check=True)
            y, _ = sf.read(shifted, dtype="float32")
            raw.unlink()
            shifted.unlink()
        y = trim(y, SR)
        y = y / (np.max(np.abs(y)) + 1e-9) * 0.89
        sf.write(wav, y, SR, subtype="PCM_24")
        manifest[ln["id"]] = {"key": key, "who": ln["who"], "dur": round(len(y) / SR, 3)}
        print(f"{ln['id']} {ln['who']:8s} {len(y) / SR:5.2f}s  {ln['en']}")
    save(man_p, manifest)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ep01_no_milk")
