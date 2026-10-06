"""Final assembly: rendered frames + soft bloom + info cards + end title + burned-in Traditional Chinese subtitles
+ mix -> H.264/AAC MP4, exactly duration*fps frames.

usage: python src/compose.py ep01_no_milk [--preview]   ->  output/<ep>.mp4
--preview fills missing frames with the nearest rendered one so the cut can be checked before rendering ends.
"""
import os
import shutil
import subprocess
import sys

from common import ROOT, build_dir, episode_dir, load, series_cfg


def main(ep, preview=False, frames_dir="frames"):
    cfg = series_cfg()
    bd = build_dir(ep)
    ed = episode_dir(ep)
    tl = load(bd / "timeline.json")
    script = load(ed / "script.json")
    fps, n, dur = tl["fps"], tl["frames"], tl["duration"]
    W, H = cfg["video"]["width"], cfg["video"]["height"]
    frames = bd / frames_dir
    missing = [f for f in range(n) if not (frames / f"f_{f:04d}.png").exists()]
    inputs = ["-framerate", str(fps), "-start_number", "0", "-i", str(frames / "f_%04d.png")]
    if missing:
        if not preview:
            sys.exit(f"{len(missing)} frames missing (first {missing[0]}); finish rendering or use --preview")
        import bisect
        have = [f for f in range(n) if (frames / f"f_{f:04d}.png").exists()]
        lst = bd / "preview_frames.ffconcat"
        with open(lst, "w", encoding="utf-8") as fh:
            fh.write("ffconcat version 1.0\n")
            for f in range(n):
                j = have[min(bisect.bisect_left(have, f), len(have) - 1)]
                path = (frames / f"f_{j:04d}.png").as_posix()
                fh.write(f"file '{path}'\nduration {1 / fps:.6f}\n")
        inputs = ["-f", "concat", "-safe", "0", "-i", str(lst)]
    ov = bd / "overlay"
    out = ROOT / "output" / (f"{ep}_preview.mp4" if preview else f"{ep}.mp4")
    if frames_dir != "frames":
        out = ROOT / "output" / f"{ep}_{frames_dir}.mp4"
    out.parent.mkdir(exist_ok=True)

    chains = [f"[0:v]fps={fps},scale={W}:{H}:flags=bicubic,format=gbrp,split[base][hi]",
              # soft bloom: only bright practicals (bulbs, screen, fluorescence) bleed a little
              "[hi]colorlevels=rimin=0.62:gimin=0.62:bimin=0.62,gblur=sigma=22[glow]",
              "[base][glow]blend=all_mode=screen:all_opacity=0.32,format=yuv420p[v0]"]
    last = "v0"
    k = 1
    for c in tl["cards"]:
        t0, t1 = c["t"]
        inputs += ["-loop", "1", "-framerate", str(fps), "-t", str(dur), "-i", str(ov / f"card_{c['id']}.png")]
        chains.append(f"[{k}:v]format=rgba,fade=t=in:st={t0}:d=0.3:alpha=1,fade=t=out:st={t1 - 0.35}:d=0.35:alpha=1[c{k}]")
        chains.append(f"[{last}][c{k}]overlay=0:0:enable='between(t,{t0},{t1})'[v{k}]")
        last = f"v{k}"
        k += 1
    if script.get("signal"):
        # electroreception diagram: 2D overlay frames generated from the baked track (see signal_overlay.py)
        import signal_overlay
        sf0 = signal_overlay.main(ep)
        st0, st1 = script["signal"]["t"]
        inputs += ["-framerate", str(fps), "-start_number", "0", "-itsoffset", f"{sf0 / fps:.6f}", "-i", str(bd / "signal" / "s_%04d.png")]
        chains.append(f"[{k}:v]format=rgba[c{k}]")
        chains.append(f"[{last}][c{k}]overlay=0:0:eof_action=pass:enable='between(t,{st0},{st1})'[v{k}]")
        last = f"v{k}"
        k += 1
    t0, t1 = tl["end_title"]["t"]
    inputs += ["-loop", "1", "-framerate", str(fps), "-t", str(dur), "-i", str(ov / "end_title.png")]
    chains.append(f"[{k}:v]format=rgba,fade=t=in:st={t0}:d=0.6:alpha=1[c{k}]")
    chains.append(f"[{last}][c{k}]overlay=0:0:enable='gte(t,{t0})'[v{k}]")
    last = f"v{k}"
    k += 1
    # subtitles last, so they always sit on top; relative path avoids Windows drive-letter escaping in filters
    chains.append(f"[{last}]subtitles=subtitles.zh-Hant.ass:fontsdir=fonts_link,format=yuv420p[vout]")
    inputs += ["-i", str(bd / "mix.wav")]
    fonts = ed / "fonts_link"
    if not fonts.exists():
        fonts.mkdir()
        for name in ("msjh.ttc", "msjhbd.ttc"):
            shutil.copy(os.path.join(r"C:\Windows\Fonts", name), fonts / name)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning", *inputs,
           "-filter_complex", ";".join(chains), "-map", "[vout]", "-map", f"{k}:a",
           "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-r", str(fps), "-fps_mode", "cfr", "-frames:v", str(n),
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{dur:.3f}",
           "-movflags", "+faststart", str(out)]
    print("encoding", out)
    subprocess.run(cmd, check=True, cwd=ed)
    print("done", out)


if __name__ == "__main__":
    fd = sys.argv[sys.argv.index("--frames") + 1] if "--frames" in sys.argv else "frames"
    main(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "ep01_no_milk", "--preview" in sys.argv, fd)
