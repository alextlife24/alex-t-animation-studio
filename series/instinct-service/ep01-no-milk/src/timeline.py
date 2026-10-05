"""Resolve the episode into ONE master timeline (build/<ep>/timeline.json) used by Blender, audio and compositing.

- Places each line at its scripted start, using the real voice duration from the TTS manifest.
- Resolves time expressions anywhere in shots/acting/sound: 12.5, "L03.end+0.4", "L08.start-0.2", "C1.t0".
- Validates: no overlapping dialogue, every line ends inside its beat window, total length exact.
- Derives per-frame mouth curves from the real audio envelope (lip sync) and writes .srt + .ass subtitles.

usage: python src/timeline.py ep01_no_milk
"""
import re
import sys

import numpy as np
import soundfile as sf

from common import build_dir, episode_dir, load, save, series_cfg

EXPR = re.compile(r"^\s*([A-Z]\d+)\.(start|end|t0|t1)\s*(?:([+-])\s*([\d.]+))?\s*$")


class Ctx:
    def __init__(self, lines, cards):
        self.anchor = {}
        for ln in lines:
            self.anchor[(ln["id"], "start")] = ln["start"]
            self.anchor[(ln["id"], "end")] = ln["end"]
        for c in cards:
            self.anchor[(c["id"], "t0")] = c["t"][0]
            self.anchor[(c["id"], "t1")] = c["t"][1]

    def t(self, x):
        if isinstance(x, (int, float)):
            return float(x)
        m = EXPR.match(x)
        if not m:
            raise ValueError(f"bad time expression: {x!r}")
        base = self.anchor[(m.group(1), m.group(2))]
        off = float(m.group(4) or 0) * (-1 if m.group(3) == "-" else 1)
        return round(base + off, 4)


def resolve_keys(keys, ctx):
    """[[t, value, (dur)], ...] -> times resolved, sorted."""
    out = []
    for k in keys:
        k = [ctx.t(x) if (i == 0 or (isinstance(x, str) and EXPR.match(x))) else x for i, x in enumerate(k)]
        out.append(k)
    return sorted(out, key=lambda k: k[0])


def resolve_tree(node, ctx):
    """Acting/sound files: any list whose first element looks like a time gets resolved."""
    if isinstance(node, dict):
        return {k: resolve_tree(v, ctx) for k, v in node.items()}
    if isinstance(node, list):
        if node and all(isinstance(k, list) and k and (isinstance(k[0], (int, float)) or (isinstance(k[0], str) and EXPR.match(k[0])))
                        for k in node):
            return resolve_keys(node, ctx)
        return [resolve_tree(v, ctx) for v in node]
    return node


def mouth_curve(wav, fps, n_frames, start):
    y, sr = sf.read(wav, dtype="float32")
    hop = sr / fps
    out = np.zeros(n_frames)
    f0 = int(round(start * fps))
    nf = int(np.ceil(len(y) / hop))
    raw = np.zeros(nf)
    for i in range(nf):
        a = int(i * hop - hop * 0.5)
        b = int(i * hop + hop * 1.0)
        seg = y[max(0, a):max(0, b)]
        rms = np.sqrt(np.mean(seg ** 2)) if len(seg) else 0
        db = 20 * np.log10(rms + 1e-6)
        raw[i] = np.clip((db + 42) / 26, 0, 1) ** 0.9
    # attack fast, release a bit slower, then drop tiny values so the bill rests closed between words
    sm = np.zeros(nf)
    v = 0
    for i, r in enumerate(raw):
        v = r if r > v else v * 0.55 + r * 0.45
        sm[i] = v
    sm[sm < 0.08] = 0
    for i in range(nf):
        j = f0 + i
        if 0 <= j < n_frames:
            out[j] = max(out[j], sm[i])
    return out


def ass_time(t):
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def subtitles(lines, cfg, ep_dir):
    L = cfg["layout"]
    subs = []
    for i, ln in enumerate(lines):
        a = ln["start"] - 0.06
        b = max(ln["end"] + 0.4, a + 1.1)
        if i + 1 < len(lines):
            b = min(b, lines[i + 1]["start"] - 0.08)
        subs.append((a, b, ln["zh"]))
    with open(ep_dir / "subtitles.zh-Hant.srt", "w", encoding="utf-8") as f:
        for i, (a, b, t) in enumerate(subs, 1):
            f.write(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{t}\n\n")
    W, H = cfg["video"]["width"], cfg["video"]["height"]
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{cfg['fonts']['subtitle']},{L['subtitle_font_size']},&H00FFFFFF,&H00FFFFFF,&H00141414,&H96000000,-1,0,0,0,100,100,1,0,1,3.2,1.6,2,90,90,{L['subtitle_margin_bottom']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with open(ep_dir / "subtitles.zh-Hant.ass", "w", encoding="utf-8-sig") as f:
        f.write(hdr)
        for a, b, t in subs:
            f.write(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Sub,,0,0,0,,{{\\fad(90,120)}}{t}\n")
    return subs


def main(ep):
    cfg = series_cfg()
    fps = cfg["video"]["fps"]
    ed = episode_dir(ep)
    bd = build_dir(ep)
    script = load(ed / "script.json")
    man = load(bd / "voice_manifest.json")
    dur = script["duration_s"]
    n = int(round(dur * fps))
    beats = {b["id"]: b for b in script["beats"]}

    lines = []
    for ln in script["lines"]:
        d = man[ln["id"]]["dur"]
        lines.append(dict(ln, start=ln["at"], end=round(ln["at"] + d, 3), dur=d, wav=str(bd / "voice" / f"{ln['id']}.wav")))
    problems = []
    for a, b in zip(lines, lines[1:]):
        if b["start"] < a["end"] + 0.25:
            problems.append(f"{a['id']} ends {a['end']:.2f} but {b['id']} starts {b['start']:.2f} (need >= 0.25 s gap)")
    for ln in lines:
        t0, t1 = beats[ln["beat"]]["t"]
        if not (t0 <= ln["start"] and ln["end"] <= t1 + 1e-6):
            problems.append(f"{ln['id']} [{ln['start']:.2f}-{ln['end']:.2f}] outside beat {ln['beat']} {t0}-{t1}")
    if problems:
        print("TIMELINE PROBLEMS:\n  " + "\n  ".join(problems))
        sys.exit(1)

    ctx = Ctx(lines, script["cards"])
    mouth = {"patrick": np.zeros(n), "bear": np.zeros(n)}
    for ln in lines:
        mouth[ln["who"]] = np.maximum(mouth[ln["who"]], mouth_curve(ln["wav"], fps, n, ln["start"]))

    tl = dict(
        episode=ep, fps=fps, frames=n, duration=dur,
        lines=lines,
        mouth={k: [round(float(x), 3) for x in v] for k, v in mouth.items()},
        cards=script["cards"], end_title=script["end_title"],
        shots=resolve_keys(load(ed / "shots.json")["shots"], ctx),
        acting=resolve_tree(load(ed / "acting.json"), ctx),
        sound=resolve_tree(load(ed / "sound.json"), ctx),
    )
    subs = subtitles(lines, cfg, ed)
    save(bd / "timeline.json", tl)
    talk = sum(l["dur"] for l in lines)
    print(f"timeline ok: {n} frames @ {fps} fps, {len(lines)} lines, {talk:.1f}s of dialogue, {len(tl['shots'])} shots, {len(subs)} subtitles")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ep01_no_milk")
