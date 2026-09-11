# -*- coding: utf-8 -*-
"""Lich dang bai fanpage 30 ngay: sinh anh card, hen gio qua Graph API.

    python tools/schedule_posts.py cards            # sinh 30 anh vao assets/social/cards/
    python tools/schedule_posts.py plan             # in lich, khong dang gi
    python tools/schedule_posts.py schedule         # hen gio TAT CA bai chua hen
    python tools/schedule_posts.py schedule --day 5 # chi mot bai
    python tools/schedule_posts.py status           # bai nao da hen, gio nao
    python tools/schedule_posts.py cancel --day 5   # xoa bai da hen

Facebook tu dang khi den gio; may nay khong can bat. Token het han cung
khong anh huong den bai da hen. Trang thai luu o content/scheduled.json de
chay lai khong hen trung.
"""
import argparse
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import fb_page  # noqa: E402

POSTS_FILE = os.path.join(ROOT, "content", "posts.json")
STATE_FILE = os.path.join(ROOT, "content", "scheduled.json")
CARD_DIR = os.path.join(ROOT, "assets", "social", "cards")
VN = timezone(timedelta(hours=7))


def load_posts():
    with io.open(POSTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_state():
    if not os.path.isfile(STATE_FILE):
        return {}
    with io.open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with io.open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def publish_at(cfg, day: int) -> datetime:
    d = datetime.strptime(cfg["start_date"], "%Y-%m-%d") + timedelta(days=day - 1)
    h, m = map(int, cfg["post_time"].split(":"))
    return d.replace(hour=h, minute=m, tzinfo=VN)


def card_path(day: int) -> str:
    return os.path.join(CARD_DIR, "day-%02d.jpg" % day)


# ===================== ANH CARD =====================

def make_cards(cfg, only_day=None):
    """Card 1200x630 cung phong cach og-image: logo, loai bai, tieu de lon, URL."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont, ImageFilter

    W, H = 1200, 630
    CX = W // 2
    BG, BLUE, PURPLE, PINK = (11, 15, 25), (59, 130, 246), (139, 92, 246), (236, 72, 153)
    WHITE, GREY = (248, 250, 252), (148, 163, 184)
    F = "C:/Windows/Fonts/"

    def font(n, s):
        return ImageFont.truetype(F + n, s)

    def background(seed):
        rng = np.random.default_rng(seed)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        img = np.zeros((H, W, 3), np.float32)
        img[:] = np.array(BG, np.float32)

        def blob(cx, cy, r, color, k):
            d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
            return (np.clip(1 - (d / r) ** 2, 0, 1) ** 2 * k)[..., None] * np.array(color, np.float32)

        # Vi tri blob doi nhe theo ngay de 30 card khong giong het nhau
        img += blob(120 + rng.integers(0, 200), 80 + rng.integers(0, 120), 480, BLUE, 0.6)
        img += blob(1000 + rng.integers(0, 150), 480 + rng.integers(0, 120), 500, PURPLE, 0.55)
        img += blob(1050 + rng.integers(0, 120), 60 + rng.integers(0, 80), 340, PINK, 0.38)
        d = np.sqrt(((xx - CX) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        img *= np.clip(1 - 0.42 * np.clip(d - 0.4, 0, None), 0.4, 1)[..., None]
        band = np.clip(1 - ((yy - 330) / 260.0) ** 2, 0, 1) ** 1.5
        img *= (1 - 0.30 * band)[..., None]
        base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")
        grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        g = ImageDraw.Draw(grid)
        for i in range(-H, W + H, 44):
            g.line([(i, 0), (i + H, H)], fill=(255, 255, 255, 7), width=1)
        return Image.alpha_composite(base, grid)

    def wrap(d, text, fnt, max_w):
        words, lines, cur = text.split(), [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if d.textlength(t, font=fnt) <= max_w:
                cur = t
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def text_mask(text, fnt, cx, cy):
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).text((cx, cy), text, font=fnt, fill=255, anchor="mm")
        return m

    def shadow(canvas, mask):
        sh = mask.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 170 / 255))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        layer.paste((0, 0, 0, 255), (0, 0), sh)
        canvas.alpha_composite(layer.transform((W, H), Image.AFFINE, (1, 0, 0, 0, 1, -5)))

    grad_row = np.stack([np.interp(np.arange(W), [0, W / 2, W - 1], [c[i] for c in (BLUE, PURPLE, PINK)])
                         for i in range(3)], axis=1)
    grad_img = Image.fromarray(np.tile(grad_row, (H, 1, 1)).astype(np.uint8)).convert("RGBA")

    os.makedirs(CARD_DIR, exist_ok=True)
    icon = Image.open(os.path.join(ROOT, "assets", "icon.png")).convert("RGBA").resize((56, 56), Image.LANCZOS)
    f_word, f_kind, f_url = font("seguibl.ttf", 24), font("seguisb.ttf", 20), font("segoeuib.ttf", 22)

    for p in cfg["posts"]:
        day = p["day"]
        if only_day and day != only_day:
            continue
        canvas = background(day)
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)

        # Logo + wordmark, goc tren trai
        ov.alpha_composite(icon, (72, 60))
        d.text((144, 88), "MEDIA DOWNLOAD STUDIO", font=f_word, fill=WHITE + (255,), anchor="lm")
        # Loai bai + so ngay, goc tren phai
        label = "%s  •  Ngày %d/30" % (p["kind"].upper(), day)
        lw = d.textlength(label, font=f_kind)
        d.rounded_rectangle([W - 72 - lw - 32, 68, W - 72, 108], radius=20,
                            fill=(255, 255, 255, 16), outline=(255, 255, 255, 46), width=2)
        d.text((W - 72 - 16, 88), label, font=f_kind, fill=(203, 213, 225, 255), anchor="rm")
        canvas.alpha_composite(ov)

        # Tieu de lon, tu xuong dong, co giam khi qua dai
        size = 64
        while True:
            f_h = font("seguibl.ttf", size)
            lines = wrap(d, p["card"], f_h, 1000)
            if len(lines) <= 3 or size <= 44:
                break
            size -= 4
        lh = int(size * 1.22)
        y0 = 330 - lh * (len(lines) - 1) / 2
        for i, line in enumerate(lines):
            y = y0 + i * lh
            m = text_mask(line, f_h, CX, y)
            shadow(canvas, m)
            if i == len(lines) - 1 and len(lines) > 1:
                g = grad_img.copy()
                g.putalpha(m)
                glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                glow.paste((139, 92, 246, 120), (0, 0), m)
                canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(20)))
                canvas.alpha_composite(g)
            else:
                layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                layer.paste(WHITE + (255,), (0, 0), m)
                canvas.alpha_composite(layer)

        # URL duoi cung
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        url = "media-download-free.web.app"
        uw = d.textlength(url, font=f_url)
        d.rounded_rectangle([CX - uw / 2 - 26, 532, CX + uw / 2 + 26, 576], radius=22,
                            fill=(255, 255, 255, 20), outline=(139, 92, 246, 140), width=2)
        d.text((CX, 554), url, font=f_url, fill=WHITE + (255,), anchor="mm")
        canvas.alpha_composite(ov)

        out = card_path(day)
        canvas.convert("RGB").save(out, "JPEG", quality=86, optimize=True, progressive=True)
        print("  day-%02d.jpg  %3d KB  %s" % (day, os.path.getsize(out) // 1024, p["card"]))


# ===================== HEN GIO =====================

def schedule(cfg, only_day=None, dry=False):
    page_id, token = fb_page.load_config()
    state = load_state()
    now = datetime.now(VN)
    for p in cfg["posts"]:
        day = p["day"]
        key = str(day)
        if only_day and day != only_day:
            continue
        if key in state and state[key].get("post_id"):
            print("  ngay %2d: da hen roi (%s), bo qua" % (day, state[key]["post_id"]))
            continue
        when = publish_at(cfg, day)
        if when < now + timedelta(minutes=11):
            print("  ngay %2d: %s da qua hoac qua gan (Facebook can >= 10 phut), bo qua" % (day, when.strftime("%d/%m %H:%M")))
            continue
        img = card_path(day)
        if not os.path.isfile(img):
            print("  ngay %2d: thieu anh %s — chay 'cards' truoc" % (day, os.path.basename(img)))
            continue
        msg = p["body"].strip() + "\n\n👉 Tải miễn phí: https://media-download-free.web.app/\n\n" + cfg["tags"]
        if dry:
            print("  ngay %2d: %s  %-40s (%d ky tu)" % (day, when.strftime("%a %d/%m %H:%M"), p["card"][:40], len(msg)))
            continue

        photo = fb_page.call("%s/photos" % page_id, token, data={"published": "false"}, files={"source": img})
        res = fb_page.call("%s/feed" % page_id, token, data={
            "message": msg,
            "attached_media[0]": json.dumps({"media_fbid": photo["id"]}),
            "published": "false",
            "scheduled_publish_time": str(int(when.timestamp())),
        })
        state[key] = {"post_id": res.get("id"), "photo_id": photo["id"],
                      "scheduled_for": when.isoformat(), "card": p["card"]}
        save_state(state)
        print("  ngay %2d: HEN %s  ->  %s" % (day, when.strftime("%a %d/%m %H:%M"), res.get("id")))


def status(cfg):
    page_id, token = fb_page.load_config()
    state = load_state()
    print("%-5s %-16s %-10s %s" % ("NGAY", "GIO DANG", "TRANG THAI", "TIEU DE"))
    for p in cfg["posts"]:
        s = state.get(str(p["day"]))
        when = publish_at(cfg, p["day"]).strftime("%a %d/%m %H:%M")
        if not s:
            print("%-5d %-16s %-10s %s" % (p["day"], when, "chua hen", p["card"]))
            continue
        try:
            r = fb_page.call(s["post_id"], token, params={"fields": "is_published,scheduled_publish_time"})
            st = "DA DANG" if r.get("is_published") else "da hen"
        except SystemExit:
            st = "MAT?"
        print("%-5d %-16s %-10s %s" % (p["day"], when, st, p["card"]))


def cancel(cfg, day):
    page_id, token = fb_page.load_config()
    state = load_state()
    s = state.get(str(day))
    if not s:
        print("ngay %d chua hen" % day)
        return
    fb_page.call(s["post_id"], token, method="DELETE")
    del state[str(day)]
    save_state(state)
    print("da xoa bai ngay %d (%s)" % (day, s["post_id"]))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("cards").add_argument("--day", type=int)
    sub.add_parser("plan")
    sub.add_parser("schedule").add_argument("--day", type=int)
    sub.add_parser("status")
    sub.add_parser("cancel").add_argument("--day", type=int, required=True)
    a = ap.parse_args()
    cfg = load_posts()
    if a.cmd == "cards":
        make_cards(cfg, a.day)
    elif a.cmd == "plan":
        schedule(cfg, dry=True)
    elif a.cmd == "schedule":
        schedule(cfg, a.day)
    elif a.cmd == "status":
        status(cfg)
    elif a.cmd == "cancel":
        cancel(cfg, a.day)


if __name__ == "__main__":
    main()
