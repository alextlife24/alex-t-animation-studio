"""Acceptance checks on the delivered MP4 (and the build inputs behind it).

usage: python src/verify.py ep01_no_milk [path/to/final.mp4]
Writes build/<ep>/verify/report.json + contact sheets; exits non-zero if a hard check fails.
"""
import difflib
import json
import os
import re
import subprocess
import sys

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

from common import ROOT, build_dir, episode_dir, load, save, series_cfg

WHISPER_PY = os.environ.get("WHISPER_PYTHON", r"C:\Users\alex\AppData\Local\Programs\Python\Python311\python.exe")
# characters that only exist in Simplified Chinese and commonly slip into subtitles
SIMPLIFIED = set("这个们为说时会对发经现进动应间问题来没还过实后东车门见长马鸟鱼鸭兽业务级体验费让论设计谁读写钱银"
                 "给决区网样当总头张专传将层历两单与从众优传华双变块报夺够学宝实属岁带帮广应开张强录忆总愿态"
                 "战户执扩扫护抢担择换据摆数断无旧显术机杀权条来极构标树样桥检楼欢残毕气汉汤沟泪洁浅测济浑"
                 "灭灯灵热爱牵独猎环现电画畅疗盖盘码确礼祸离种积称稳穷窃竞笔节荣药莱获营虑虽补装觉觅规视"
                 "览证识评译试详语误说请读调谈谢贝负贡贫购贸费资赏赔趋跃践车轨转轮软轻较辆辉边达迁过运还这进远")


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe(mp4):
    r = run(["ffprobe", "-v", "error", "-count_frames", "-show_entries",
             "stream=codec_type,codec_name,profile,width,height,r_frame_rate,avg_frame_rate,nb_read_frames,pix_fmt,sample_rate,channels,duration"
             ":format=duration,size", "-of", "json", mp4])
    return json.loads(r.stdout)


def f0(y, sr):
    fr = int(0.04 * sr)
    out = []
    for i in range(0, len(y) - fr, fr // 2):
        x = y[i:i + fr]
        if np.sqrt((x ** 2).mean()) < 0.02:
            continue
        x = x - x.mean()
        ac = np.correlate(x, x, "full")[fr - 1:]
        lo, hi = int(sr / 350), int(sr / 55)
        lag = lo + np.argmax(ac[lo:hi])
        if ac[lag] > 0.3 * ac[0]:
            out.append(sr / lag)
    return float(np.median(out)) if out else 0.0


def norm(s):
    return re.sub(r"[^a-z ]", "", s.lower().replace("-", " ")).split()


def main(ep, mp4=None):
    cfg = series_cfg()
    bd = build_dir(ep)
    ed = episode_dir(ep)
    vd = bd / "verify"
    vd.mkdir(exist_ok=True)
    tl = load(bd / "timeline.json")
    mp4 = mp4 or str(ROOT / "output" / f"{ep}.mp4")
    rep = {"file": mp4, "checks": [], "warnings": []}

    def check(name, ok, detail=""):
        rep["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")

    # ---------------- container / streams
    p = probe(mp4)
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    a = next((s for s in p["streams"] if s["codec_type"] == "audio"), None)
    W, H, fps, N = cfg["video"]["width"], cfg["video"]["height"], cfg["video"]["fps"], tl["frames"]
    check("video H.264", v["codec_name"] == "h264", f"{v['codec_name']} {v.get('profile')} {v.get('pix_fmt')}")
    check("resolution 1080x1920", (v["width"], v["height"]) == (W, H), f"{v['width']}x{v['height']}")
    check("30 fps constant", v["r_frame_rate"] == f"{fps}/1" and v["avg_frame_rate"] == f"{fps}/1", f"{v['r_frame_rate']} avg {v['avg_frame_rate']}")
    check("exactly 2700 frames", int(v["nb_read_frames"]) == N, f"{v['nb_read_frames']} frames")
    check("video duration 90.000 s", abs(float(v["duration"]) - 90.0) < 0.001, v["duration"])
    check("audio AAC", a is not None and a["codec_name"] == "aac", f"{a and a['codec_name']} {a and a['sample_rate']} Hz {a and a['channels']} ch")
    check("audio duration ~90 s", a is not None and abs(float(a["duration"]) - 90.0) < 0.05, a and a["duration"])
    check("container duration ~90 s", abs(float(p["format"]["duration"]) - 90.0) < 0.05, p["format"]["duration"])

    # decode whole file once (catches corrupt packets)
    r = run(["ffmpeg", "-v", "error", "-i", mp4, "-f", "null", "-"])
    check("decodes without errors", r.returncode == 0 and not r.stderr.strip(), r.stderr.strip()[:200])

    # ---------------- audio content
    wav = vd / "final_audio.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", mp4, "-vn", "-ac", "1", "-ar", "16000", str(wav)])
    y, sr = sf.read(wav, dtype="float32")
    lu = run(["ffmpeg", "-hide_banner", "-i", mp4, "-vn", "-af", "loudnorm=print_format=json", "-f", "null", "-"]).stderr
    js = json.loads(lu[lu.rindex("{"):lu.rindex("}") + 1])
    check("loudness about -16 LUFS", abs(float(js["input_i"]) + 16) < 1.5, f"{js['input_i']} LUFS, TP {js['input_tp']} dBTP")
    check("true peak <= -1 dBTP", float(js["input_tp"]) <= -1.0, js["input_tp"])

    def rms_db(t0, t1):
        seg = y[int(t0 * sr):int(t1 * sr)]
        return float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9))
    lines = tl["lines"]
    sil = [(lines[i]["end"] + 0.3, lines[i + 1]["start"] - 0.3) for i, ln in enumerate(lines[:-1]) if ln["id"] == "L09"]
    if sil:
        s0, s1 = sil[0]
        speech = np.mean([rms_db(l["start"], l["end"]) for l in lines])
        quiet = rms_db(s0, s1)
        check("dead-silence beat is quiet (fridge hum only)", speech - quiet > 18, f"speech {speech:.1f} dB vs silence {quiet:.1f} dB ({s0:.1f}-{s1:.1f}s)")

    # ASR on the delivered audio
    asr_p = vd / "asr.json"
    r = run([WHISPER_PY, str(ROOT / "src" / "asr_check.py"), str(wav), str(asr_p)])
    if r.returncode != 0:
        check("speech recognition ran", False, r.stderr[-300:])
    else:
        words = [w for s in load(asr_p) for w in s["words"]]
        missing = []
        for ln in lines:
            ws = [w for w in words if ln["start"] - 0.5 <= (w["s"] + w["e"]) / 2 <= ln["end"] + 0.5]
            heard = " ".join(norm(" ".join(w["w"] for w in ws)))
            want = " ".join(norm(ln["en"]))
            ratio = difflib.SequenceMatcher(None, heard, want).ratio()
            ok = ratio >= 0.75
            if not ok:
                missing.append(f"{ln['id']}: heard '{heard}' want '{want}' ({ratio:.2f})")
            rep.setdefault("asr", []).append({"id": ln["id"], "heard": heard, "ratio": round(ratio, 2)})
        check("all 19 lines heard complete at their times (Whisper)", not missing, "; ".join(missing))
        # anything spoken outside dialogue windows = stray/duplicated speech
        stray = [w["w"] for w in words if not any(l["start"] - 0.6 <= (w["s"] + w["e"]) / 2 <= l["end"] + 0.6 for l in lines)]
        check("no speech outside scripted lines", len(stray) <= 1, " ".join(stray))

    # dialogue integrity from the stems/lines
    ov = [f"{a['id']}/{b['id']}" for a, b in zip(lines, lines[1:]) if b["start"] < a["end"]]
    check("no overlapping lines", not ov, ",".join(ov))
    clipped = []
    for ln in lines:
        yy, ss = sf.read(ln["wav"], dtype="float32")
        if np.abs(yy[-int(0.03 * ss):]).max() > 0.05 or np.abs(yy[:int(0.01 * ss)]).max() > 0.05:
            clipped.append(ln["id"])
    check("no truncated line audio (clean head/tail)", not clipped, ",".join(clipped))
    pitches = {}
    for ln in lines:
        yy, ss = sf.read(ln["wav"], dtype="float32")
        pitches.setdefault(ln["who"], []).append(f0(yy, ss))
    pb, pp = np.array(pitches["bear"]), np.array(pitches["patrick"])
    check("voices never swap (every Bear line lower than every Patrick line)", pb.max() < pp.min(),
          f"bear f0 {pb.min():.0f}-{pb.max():.0f} Hz, patrick f0 {pp.min():.0f}-{pp.max():.0f} Hz")
    check("only two speaking characters", set(l["who"] for l in lines) == {"bear", "patrick"}, str(sorted(set(l["who"] for l in lines))))

    # ---------------- subtitles
    ass = (ed / "subtitles.zh-Hant.ass").read_text(encoding="utf-8-sig")
    events = [l.split(",", 9)[9] for l in ass.splitlines() if l.startswith("Dialogue:")]
    texts = [re.sub(r"\{[^}]*\}", "", e) for e in events]
    expected = [l["zh"] for l in lines]
    check("subtitle text matches script exactly", texts == expected, "")
    simp = sorted({c for t in texts for c in t if c in SIMPLIFIED})
    big5 = sorted({c for t in texts for c in t if not _big5(c)})
    check("no Simplified-only characters", not simp and not big5, f"simplified {simp} non-Big5 {big5}")
    font = ImageFont.truetype(cfg["fonts"]["ui_cjk_file"], cfg["layout"]["subtitle_font_size"])
    widest = max(font.getlength(t) for t in texts)
    check("subtitles fit on one line inside safe margins", widest <= W - 2 * 90, f"widest {widest:.0f}px of {W - 180}px")
    check("max two subtitle lines", all(t.count("\\N") <= 1 for t in texts), "")

    # ---------------- visual contact sheets
    sheet(mp4, vd / "contact_every3s.jpg", [i * 3 + 1.5 for i in range(30)])
    sheet(mp4, vd / "contact_keymoments.jpg", [1.0, 7.2, 9.6, 11.9, 19.5, 37.5, 43.5, 48.5, 64.3, 72.3, 74.2, 76.6, 79.3, 81.5, 86.4, 89.6])
    save(vd / "report.json", rep)
    bad = [c for c in rep["checks"] if not c["ok"]]
    print(f"\n{len(rep['checks']) - len(bad)}/{len(rep['checks'])} checks passed")
    return 1 if bad else 0


def _big5(c):
    try:
        c.encode("big5")
        return True
    except UnicodeEncodeError:
        return False


def sheet(mp4, out, times, cols=6, w=270):
    h = int(w * 16 / 9)
    ims = []
    tmp = out.parent / "_f.png"
    for t in times:
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", mp4, "-frames:v", "1", "-vf", f"scale={w}:{h}", str(tmp)])
        im = Image.open(tmp).convert("RGB")
        ImageDraw.Draw(im).text((6, 6), f"{t:.1f}s", fill=(255, 255, 0))
        ims.append(im)
    rows = (len(ims) + cols - 1) // cols
    S = Image.new("RGB", (cols * w, rows * h))
    for i, im in enumerate(ims):
        S.paste(im, ((i % cols) * w, (i // cols) * h))
    S.save(out, quality=88)
    tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "ep01_no_milk", sys.argv[2] if len(sys.argv) > 2 else None))
