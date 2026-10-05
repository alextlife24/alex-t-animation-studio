"""2D graphics: register-screen textures (mapped onto the 3D POS), info cards and the end title (overlays).

usage: python src/graphics.py ep01_no_milk  ->  build/<ep>/tex/screen_*.png, build/<ep>/overlay/*.png
"""
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from common import build_dir, episode_dir, load, series_cfg

VENUE = "THE SILVER FIR"


def font(path, size, index=0):
    return ImageFont.truetype(path, size, index=index)


def rounded(draw, box, r, fill, outline=None, width=1):
    draw.rounded_rectangle(box, r, fill=fill, outline=outline, width=width)


def screen_textures(ep, cfg, script):
    F = cfg["fonts"]
    out = build_dir(ep) / "tex"
    out.mkdir(exist_ok=True)
    W, H = 1024, 690
    paths = {}
    for s in script["screens"]:
        im = Image.new("RGB", (W, H), "#0d131c")
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, W, 64), fill="#1a2330")
        d.text((28, 14), VENUE, font=font(F["ui_latin_file"], 30), fill="#c9a45a")
        d.text((W - 130, 16), "21:47", font=font(F["ui_latin_regular_file"], 28), fill="#7f8da0")
        if s["id"] == "idle":
            d.text((48, 120), "BAR · SEAT 2", font=font(F["ui_latin_file"], 54), fill="#e8edf3")
            d.text((48, 200), "ORDER OPEN", font=font(F["ui_latin_regular_file"], 40), fill="#7fb3a0")
            d.line((48, 290, W - 48, 290), fill="#2a3646", width=3)
            d.text((48, 320), "1 ×  Milk, fresh", font=font(F["ui_latin_regular_file"], 44), fill="#c9d3de")
            d.text((W - 230, 320), "PENDING", font=font(F["ui_latin_file"], 34), fill="#c9a45a")
            rounded(d, (48, 560, W - 48, 640), 18, fill="#1d2836")
            d.text((80, 575), "SEND TO BAR", font=font(F["ui_latin_file"], 38), fill="#7f8da0")
        elif s["id"] == "manager":
            rounded(d, (40, 100, W - 40, 640), 26, fill="#1b2433", outline="#c9a45a", width=4)
            d.ellipse((76, 140, 104, 168), fill="#e0533d")
            d.text((122, 128), "NEW MESSAGE", font=font(F["ui_latin_file"], 34), fill="#e0533d")
            d.text((76, 210), "MANAGER:", font=font(F["ui_latin_file"], 66), fill="#f2f4f7")
            d.text((76, 300), "Resolve it on the spot.", font=font(F["ui_latin_file"], 62), fill="#f2f4f7")
            d.text((76, 430), s["zh"], font=font(F["ui_cjk_file"], 46), fill="#aab6c4")
            d.text((76, 560), "Read 21:47", font=font(F["ui_latin_regular_file"], 28), fill="#5d6b7c")
        elif s["id"] == "fee":
            rounded(d, (40, 100, W - 40, 640), 26, fill="#1b2433", outline="#35f2c8", width=4)
            d.text((76, 150), "ADD EXPERIENCE FEE?", font=font(F["ui_latin_file"], 68), fill="#f2f4f7")
            d.text((76, 260), s["zh"], font=font(F["ui_cjk_file"], 50), fill="#aab6c4")
            rounded(d, (76, 440, 470, 580), 22, fill="#35f2c8")
            d.text((200, 470), "YES", font=font(F["ui_latin_file"], 60), fill="#0d131c")
            rounded(d, (W - 470, 440, W - 76, 580), 22, fill="#2a3646")
            d.text((W - 330, 470), "NO", font=font(F["ui_latin_file"], 60), fill="#c9d3de")
        p = out / f"screen_{s['id']}.png"
        im.save(p)
        paths[s["id"]] = p
    return paths


def info_card(card, cfg, out):
    """Small floating fact card, top safe area. Transparent PNG at full frame size."""
    F = cfg["fonts"]
    Wf, Hf = cfg["video"]["width"], cfg["video"]["height"]
    lay = cfg["layout"]
    cw = lay["card_width"]
    f_en = font(F["ui_latin_regular_file"], 40)
    f_zh = font(F["ui_cjk_file"], 48)
    f_lb = font(F["ui_latin_file"], 26)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    w_en = tmp.textlength(card["en"], font=f_en)
    w_zh = tmp.textlength(card["zh"], font=f_zh)
    cw = int(min(cw, max(w_en, w_zh) + 120))
    ch = 210
    x0 = (Wf - cw) // 2
    y0 = lay["card_top"]
    im = Image.new("RGBA", (Wf, Hf), (0, 0, 0, 0))
    sh = Image.new("RGBA", (Wf, Hf), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0, y0 + 10, x0 + cw, y0 + ch + 10), 30, fill=(0, 0, 0, 110))
    sh = sh.filter(ImageFilter.GaussianBlur(18))
    im.alpha_composite(sh)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((x0, y0, x0 + cw, y0 + ch), 30, fill=(18, 23, 31, 228), outline=(201, 164, 90, 255), width=3)
    d.text((x0 + 46, y0 + 26), "FIELD NOTE · 生物筆記", font=font(F["ui_cjk_file"], 26), fill=(201, 164, 90, 255))
    d.text((x0 + 46, y0 + 70), card["zh"], font=f_zh, fill=(244, 246, 248, 255))
    d.text((x0 + 46, y0 + 140), card["en"], font=f_en, fill=(170, 182, 196, 255))
    p = out / f"card_{card['id']}.png"
    im.save(p)
    return p


def end_title(cfg, script, out):
    F = cfg["fonts"]
    Wf, Hf = cfg["video"]["width"], cfg["video"]["height"]
    im = Image.new("RGBA", (Wf, Hf), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = cfg["series"]
    f1 = font(F["ui_cjk_file"], 92)
    f2 = font(F["ui_latin_file"], 50)
    f3 = font(F["ui_cjk_regular_file"], 38)
    y = 300
    for txt, f, col, dy in ((s["zh"], f1, (246, 240, 228, 255), 120), (s["en"].upper(), f2, (201, 164, 90, 255), 90),
                            (f"EP.01  {script['title']['zh']}", f3, (220, 226, 232, 255), 56),
                            (script["title"]["en"], font(F["ui_latin_regular_file"], 34), (170, 182, 196, 255), 0)):
        w = d.textlength(txt, font=f)
        x = (Wf - w) / 2
        # soft shadow for legibility over the scene
        sh = Image.new("RGBA", (Wf, Hf), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((x, y + 4), txt, font=f, fill=(0, 0, 0, 200))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
        d.text((x, y), txt, font=f, fill=col)
        y += dy
    p = out / "end_title.png"
    im.save(p)
    return p


def main(ep):
    cfg = series_cfg()
    script = load(episode_dir(ep) / "script.json")
    screen_textures(ep, cfg, script)
    out = build_dir(ep) / "overlay"
    out.mkdir(exist_ok=True)
    for c in script["cards"]:
        info_card(c, cfg, out)
    end_title(cfg, script, out)
    print("graphics ok")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ep01_no_milk")
