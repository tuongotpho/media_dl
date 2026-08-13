"""Tao icon cho YTDLP Studio.

Thiet ke: o vuong bo goc, gradient xanh -> tim theo dung bang mau cua app.
Ben trong la mui ten tai xuong co dau hinh tam giac (vua doc la nut play,
vua doc la mui ten download), dat tren mot vach day.

Chay:  python tools/make_icon.py
Xuat:  assets/icon.ico (nhieu kich thuoc) + assets/icon.png (256px)
"""
import os

from PIL import Image, ImageDraw

# Bang mau lay tu app/static/style.css
BLUE = (59, 130, 246)    # --accent-blue  #3b82f6
PURPLE = (139, 92, 246)  # --accent-purple #8b5cf6
PINK = (236, 72, 153)    # --accent-pink  #ec4899

SIZE = 1024
RADIUS = 232
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "assets")


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def make_gradient(size):
    """Gradient cheo: xanh (goc tren trai) -> tim -> hong nhat (goc duoi phai).

    Ve o do phan giai thap roi phong to, muot hon va nhanh hon nhieu
    so voi viec duyet tung pixel o 1024x1024.
    """
    small = 64
    grad = Image.new("RGB", (small, small))
    px = grad.load()
    for y in range(small):
        for x in range(small):
            t = (x + y) / (2 * (small - 1))
            if t < 0.65:
                color = lerp(BLUE, PURPLE, t / 0.65)
            else:
                color = lerp(PURPLE, PINK, (t - 0.65) / 0.35 * 0.55)
            px[x, y] = color
    return grad.resize((size, size), Image.LANCZOS)


def make_icon():
    gradient = make_gradient(SIZE)

    # Mat na bo goc
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, SIZE - 1, SIZE - 1], radius=RADIUS, fill=255
    )

    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    icon.paste(gradient, (0, 0), mask)

    # Lop sang nhe tu tren xuong cho co chieu sau.
    # Dung dai mo dan chu khong dung hinh chu nhat bo goc: hinh chu nhat
    # se de lai duong vien cong lo ro o giua icon.
    fade = Image.new("L", (1, SIZE))
    fade_px = fade.load()
    for y in range(SIZE):
        t = y / (SIZE * 0.62)
        fade_px[0, y] = max(0, round(30 * (1 - t))) if t < 1 else 0
    sheen_alpha = fade.resize((SIZE, SIZE))
    sheen_alpha = Image.composite(sheen_alpha, Image.new("L", (SIZE, SIZE), 0), mask)

    sheen = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    sheen.putalpha(sheen_alpha)
    icon = Image.alpha_composite(icon, sheen)

    draw = ImageDraw.Draw(icon)
    cx = SIZE // 2
    white = (255, 255, 255, 255)

    # Than mui ten
    draw.rounded_rectangle([cx - 62, 236, cx + 62, 548], radius=40, fill=white)
    # Dau mui ten kiem nut play
    draw.polygon([(cx - 232, 505), (cx + 232, 505), (cx, 792)], fill=white)
    # Vach day
    draw.rounded_rectangle([cx - 232, 838, cx + 232, 898], radius=30, fill=white)

    os.makedirs(OUT_DIR, exist_ok=True)

    png_path = os.path.join(OUT_DIR, "icon.png")
    icon.resize((256, 256), Image.LANCZOS).save(png_path)

    ico_path = os.path.join(OUT_DIR, "icon.ico")
    icon.save(ico_path, sizes=[(16, 16), (24, 24), (32, 32),
                               (48, 48), (64, 64), (128, 128), (256, 256)])

    # Anh xem thu cac kich thuoc nho, de kiem tra icon con ro khong
    preview = Image.new("RGBA", (16 + 24 + 32 + 48 + 64 + 60, 80), (20, 24, 36, 255))
    x = 10
    for s in (16, 24, 32, 48, 64):
        preview.paste(icon.resize((s, s), Image.LANCZOS), (x, (80 - s) // 2))
        x += s + 10
    preview.save(os.path.join(OUT_DIR, "icon-preview.png"))

    print(f"Da tao: {ico_path}")
    print(f"Da tao: {png_path}")
    print(f"Xem thu kich thuoc nho: {os.path.join(OUT_DIR, 'icon-preview.png')}")


if __name__ == "__main__":
    make_icon()
