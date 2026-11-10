"""Lucent family icons: the crescent + sparkle on dark navy, each add-on with its own colour, emblem and name."""
import math
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = sys.argv[1]
FONT = sys.argv[2]
SS = 4                      # supersampling
N = 1024                    # final size
W = N * SS

ADDONS = {
    #  key          label          accent (main)     accent (deep)     emblem
    "skin":        ("SKIN",        (214, 200, 255), (112, 92, 214),  "layout"),
    "video":       ("VIDEO",       (255, 196, 150), (226, 98, 70),   "play"),
    "subtitles":   ("SUBTITLES",   (150, 236, 222), (32, 160, 150),  "subs"),
    "repository":  ("REPOSITORY",  (160, 206, 255), (52, 112, 214),  "box"),
    "screensaver": ("SCREENSAVER", (190, 190, 255), (82, 82, 190),   "stars"),
}


def s(v):
    return int(round(v * SS))


def background(deep):
    """Dark navy with a soft glow of the add-on's colour from the top right."""
    img = Image.new("RGB", (W, W), (8, 11, 22))
    glow = Image.new("RGB", (W, W), (0, 0, 0))
    d = ImageDraw.Draw(glow)
    d.ellipse([s(380), s(-260), s(1300), s(660)], fill=tuple(int(c * 0.55) for c in deep))
    d.ellipse([s(-300), s(620), s(500), s(1420)], fill=(14, 22, 48))
    glow = glow.filter(ImageFilter.GaussianBlur(s(170)))
    img = Image.blend(img, glow, 0.85)
    # rounded-square card look is left to Kodi; keep the full square
    return img.convert("RGBA")


def crescent(cx, cy, r, cut_dx, cut_dy, cut_r):
    m = Image.new("L", (W, W), 0)
    d = ImageDraw.Draw(m)
    d.ellipse([s(cx - r), s(cy - r), s(cx + r), s(cy + r)], fill=255)
    d.ellipse([s(cx + cut_dx - cut_r), s(cy + cut_dy - cut_r), s(cx + cut_dx + cut_r), s(cy + cut_dy + cut_r)], fill=0)
    return m


def sparkle(d, cx, cy, r, fill, thin=0.18):
    pts = []
    for i in range(8):
        a = math.pi / 4 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * thin
        pts.append((s(cx + rr * math.cos(a)), s(cy + rr * math.sin(a))))
    d.polygon(pts, fill=fill)


def gradient_fill(mask, top, bottom):
    """Colour a mask with a vertical gradient."""
    g = Image.new("RGBA", (1, 256))
    for y in range(256):
        t = y / 255
        g.putpixel((0, y), tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)) + (255,))
    g = g.resize((W, W))
    out = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    out.paste(g, (0, 0), mask)
    return out


def glow_of(mask, colour, radius, strength):
    a = mask.filter(ImageFilter.GaussianBlur(s(radius))).point(lambda v: int(v * strength))
    layer = Image.new("RGBA", (W, W), colour + (0,))
    layer.putalpha(a)
    return layer


def emblem(kind, accent, deep):
    """The add-on's own sign, in the hollow of the crescent (mask, white)."""
    m = Image.new("L", (W, W), 0)
    d = ImageDraw.Draw(m)
    cx, cy = 455, 470
    if kind == "play":
        r = 120
        pts = [(cx - r * 0.55, cy - r), (cx + r * 0.95, cy), (cx - r * 0.55, cy + r)]
        d.polygon([(s(x), s(y)) for x, y in pts], fill=255)
        m = m.filter(ImageFilter.GaussianBlur(s(2)))      # slightly soft corners
        m = m.point(lambda v: 255 if v > 110 else 0)
    elif kind == "subs":
        for i, (w, y) in enumerate(((250, cy - 52), (180, cy + 52))):
            d.rounded_rectangle([s(cx - w / 2), s(y - 26), s(cx + w / 2), s(y + 26)], radius=s(26), fill=255)
    elif kind == "layout":
        x0, y0, x1, y1 = cx - 140, cy - 105, cx + 140, cy + 105
        d.rounded_rectangle([s(x0), s(y0), s(x1), s(y1)], radius=s(30), fill=255)
        d.rounded_rectangle([s(x0 + 26), s(y0 + 26), s(x1 - 26), s(y1 - 26)], radius=s(12), fill=0)
        d.rounded_rectangle([s(x0 + 50), s(y0 + 50), s(x0 + 110), s(y1 - 50)], radius=s(10), fill=255)
        d.rounded_rectangle([s(x0 + 130), s(y0 + 50), s(x1 - 50), s(cy - 8)], radius=s(10), fill=255)
        d.rounded_rectangle([s(x0 + 130), s(cy + 8), s(x1 - 50), s(y1 - 50)], radius=s(10), fill=255)
    elif kind == "box":
        x0, y0, x1, y1 = cx - 130, cy - 70, cx + 130, cy + 120
        d.rounded_rectangle([s(x0), s(y0), s(x1), s(y1)], radius=s(26), fill=255)
        d.rounded_rectangle([s(x0 + 24), s(y0 + 24), s(x1 - 24), s(y1 - 24)], radius=s(10), fill=0)
        d.rectangle([s(cx - 15), s(cy - 150), s(cx + 15), s(cy + 30)], fill=255)
        d.polygon([(s(cx - 62), s(cy - 10)), (s(cx + 62), s(cy - 10)), (s(cx), s(cy + 60))], fill=255)
        d.rectangle([s(cx - 40), s(y0 - 2), s(cx + 40), s(y0 + 26)], fill=0)
        d.rectangle([s(cx - 15), s(y0 - 4), s(cx + 15), s(y0 + 30)], fill=255)
    elif kind == "stars":
        pass
    return place(m, 0.74, 372, 405)


def place(mask, k, tx, ty, ox=455, oy=470):
    """Scale a drawn emblem around (ox, oy) by k and move that point to (tx, ty): it sits free in the hollow."""
    # output (x, y) comes from input ((x - tx) / k + ox, ...)
    a = 1 / k
    return mask.transform((W, W), Image.AFFINE, (a, 0, s(ox) - s(tx) * a, 0, a, s(oy) - s(ty) * a), resample=Image.BICUBIC)


def make(key):
    label, accent, deep, kind = ADDONS[key]
    img = background(deep)
    # the crescent (the Lucent mark), a little smaller and higher than before so the name fits under it
    cx, cy, r = 512, 450, 300
    moon = crescent(cx, cy, r, -118, -92, 262)
    img.alpha_composite(glow_of(moon, accent, 46, 0.55))
    img.alpha_composite(gradient_fill(moon, (250, 248, 255), accent))
    # emblem / sparkle in the hollow
    d = ImageDraw.Draw(img)
    if kind == "stars":
        star = Image.new("L", (W, W), 0)
        sd = ImageDraw.Draw(star)
        sparkle(sd, 370, 420, 88, 255)
        sparkle(sd, 470, 290, 40, 255)
        sparkle(sd, 270, 300, 30, 255)
        img.alpha_composite(glow_of(star, accent, 24, 0.9))
        img.alpha_composite(gradient_fill(star, (255, 255, 255), accent))
    else:
        em = emblem(kind, accent, deep)
        if key == "skin":
            star = Image.new("L", (W, W), 0)
            sparkle(ImageDraw.Draw(star), 385, 410, 105, 255)
            em = star
        img.alpha_composite(glow_of(em, accent, 22, 0.8))
        img.alpha_composite(gradient_fill(em, (255, 255, 255), accent))
    # the name: LUCENT small and wide, the add-on in its colour
    big = ImageFont.truetype(FONT.replace("Bold", "ExtraBold"), s(92 if len(label) <= 9 else 76 if len(label) <= 10 else 70))
    small = ImageFont.truetype(FONT.replace("Bold", "SemiBold"), s(40))
    d = ImageDraw.Draw(img)

    def spaced(text, font, y, fill, track):
        widths = [d.textlength(ch, font=font) for ch in text]
        total = sum(widths) + s(track) * (len(text) - 1)
        x = (W - total) / 2
        for ch, w in zip(text, widths):
            d.text((x, y), ch, font=font, fill=fill)
            x += w + s(track)

    spaced("LUCENT", small, s(810), (205, 210, 230), 14)
    spaced(label, big, s(862), accent, 6)
    img = img.convert("RGB").resize((N, N), Image.LANCZOS)
    img.save(f"{OUT}/{key}.png", optimize=True)
    return img


if __name__ == "__main__":
    tiles = [make(k) for k in ADDONS]
    sheet = Image.new("RGB", (N * len(tiles) + 40 * (len(tiles) - 1), N), (30, 30, 30))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * (N + 40), 0))
    sheet.resize((sheet.width // 2, N // 2), Image.LANCZOS).save(f"{OUT}/overzicht.png")
