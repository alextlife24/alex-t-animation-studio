"""Viewer-facing diagram of a weak electric field (EP02): faint flat rings spreading from the hidden prey and a thin
dashed bearing line toward the bill tip. Drawn in 2D over the picture from the projected positions that
build/<ep>/track.json records during the bake - it is an explanatory overlay, not light in the scene.

usage: python src/signal_overlay.py ep02_eyes_closed  ->  build/<ep>/signal/s_%04d.png (only the overlay window)
"""
import math
import sys

from PIL import Image, ImageDraw, ImageFilter

from common import build_dir, episode_dir, load, series_cfg


def main(ep):
    cfg = series_cfg()
    script = load(episode_dir(ep) / "script.json")
    sig = script.get("signal")
    if not sig:
        return None
    bd = build_dir(ep)
    track = load(bd / "track.json")
    fps = cfg["video"]["fps"]
    W, H = cfg["video"]["width"], cfg["video"]["height"]
    out = bd / "signal"
    out.mkdir(exist_ok=True)
    for p in out.glob("s_*.png"):
        p.unlink()
    t0, t1 = sig["t"]
    f0, f1 = int(round(t0 * fps)), int(round(t1 * fps))
    col = tuple(sig.get("color", [190, 240, 255]))
    for f in range(f0, f1):
        t = f / fps
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        src, dst = track[f].get(sig["from"]), track[f].get(sig["to"])
        # global fade in/out so the diagram never pops
        g = min(1.0, (t - t0) / 0.5, (t1 - t) / 0.5)
        if src and dst and g > 0:
            d = ImageDraw.Draw(im)
            sx, sy = src[0], src[1]
            # expanding rings, one every 0.55 s, each fading as it grows
            for k in range(6):
                age = (t - t0) - k * 0.55
                if age < 0:
                    continue
                x = (age % 1.65) / 1.65
                r = 30 + 260 * x
                a = int(150 * g * (1 - x) ** 1.4)
                if a > 4:
                    d.ellipse((sx - r, sy - r * 0.62, sx + r, sy + r * 0.62), outline=col + (a,), width=4)
            # dashed bearing line from the prey to the bill tip, dashes drift toward the bill
            dx, dy = dst[0] - sx, dst[1] - sy
            L = math.hypot(dx, dy)
            if L > 1:
                ux, uy = dx / L, dy / L
                ph = ((t - t0) * 90) % 36
                s = 40 + ph
                while s < L - 30:
                    e = min(s + 18, L - 30)
                    d.line((sx + ux * s, sy + uy * s, sx + ux * e, sy + uy * e), fill=col + (int(170 * g),), width=5)
                    s += 36
                d.ellipse((dst[0] - 9, dst[1] - 9, dst[0] + 9, dst[1] + 9), outline=col + (int(190 * g),), width=4)
            im = Image.alpha_composite(im.filter(ImageFilter.GaussianBlur(3)), im)
        im.save(out / f"s_{f - f0:04d}.png")
    return f0


if __name__ == "__main__":
    print("signal frames from", main(sys.argv[1] if len(sys.argv) > 1 else "ep02_eyes_closed"))
