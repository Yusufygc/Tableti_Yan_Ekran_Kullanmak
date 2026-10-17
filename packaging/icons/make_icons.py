"""
TabScreen USB uygulama simgesini üretir (tekrarlanabilir): `python packaging/icons/make_icons.py`.

Tasarım (proje bağlamı): koyu lacivert yuvarlak kare üzerinde yatay duran bir tablet; ekranında dokunma dalgası
(tablet istemcisindeki `touch-ripple` ile aynı motif) ve sağ altta amber "3" rozeti ("3. Ekran"). Küçük boyutlarda
(<= 32 px) ayrıntılar sadeleşir: yalnızca tablet gövdesi, ekran ve dalga okunur kalır.

Çıktılar (bu klasöre): icon_<boyut>.png (16..512) ve app.ico (16, 24, 32, 48, 64, 128, 256 çerçeveleri ayrı çizilir,
büyük resimden küçültülmez). Web istemcisi için `src/ui/client_assets/icon-192.png` da yazılır.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CLIENT_ASSETS = ROOT / "src" / "ui" / "client_assets"

PNG_SIZES = (16, 24, 32, 48, 64, 96, 128, 192, 256, 512)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
SUPERSAMPLE = 4

# Uygulama paletiyle (controller_app.THEME_COLORS ve istemci HUD'ı) uyumlu
BG_TOP = (30, 41, 59)        # #1E293B
BG_BOTTOM = (11, 15, 25)     # #0B0F19
BODY = (226, 232, 240)       # #E2E8F0 tablet gövdesi
SCREEN_TOP = (56, 189, 248)  # #38BDF8 ekran (vurgu rengi)
SCREEN_BOTTOM = (14, 116, 168)
RIPPLE = (248, 250, 252)
BAR = (11, 15, 25)
AMBER = (245, 158, 11)       # #F59E0B rozet
AMBER_TEXT = (11, 15, 25)


def _vertical_gradient(size: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / max(1, size - 1)
        grad.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return grad.resize((size, size))


def _rounded_mask(size: int, radius: int, box: tuple[int, int, int, int] | None = None) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box or (0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def draw_icon(size: int) -> Image.Image:
    """Verilen piksel boyutu için simgeyi çizer (ayrıntı düzeyi boyuta göre seçilir)."""
    s = size * SUPERSAMPLE
    detailed = size >= 48
    mid = size >= 32

    canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    bg = _vertical_gradient(s, BG_TOP, BG_BOTTOM).convert("RGBA")
    canvas.paste(bg, (0, 0), _rounded_mask(s, int(s * 0.22)))

    # Tablet gövdesi (yatay, hafif ortadan yukarı)
    bw, bh = int(s * 0.78), int(s * 0.54)
    bx0, by0 = (s - bw) // 2, int(s * 0.19)
    body_box = (bx0, by0, bx0 + bw, by0 + bh)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(body_box, radius=int(s * 0.07), fill=BODY)

    # Ekran (gradyan)
    margin = int(s * (0.045 if mid else 0.06))
    sx0, sy0, sx1, sy1 = bx0 + margin, by0 + margin, bx0 + bw - margin, by0 + bh - margin
    screen_w, screen_h = sx1 - sx0, sy1 - sy0
    screen = _vertical_gradient(max(screen_w, screen_h), SCREEN_TOP, SCREEN_BOTTOM).crop((0, 0, screen_w, screen_h))
    screen_mask = _rounded_mask(max(screen_w, screen_h), int(s * 0.035)).crop((0, 0, screen_w, screen_h))
    canvas.paste(screen.convert("RGBA"), (sx0, sy0), screen_mask)

    # Yarı saydam şekiller ayrı katmanda çizilip karıştırılır (doğrudan çizim piksellerin alfasını delerdi)
    overlay = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    if detailed:
        # Sade "metin satırları": tablet ekranında içerik olduğunu anlatır
        bar_h = max(2, int(s * 0.018))
        for i, frac in enumerate((0.62, 0.46, 0.54)):
            y = sy0 + int(screen_h * 0.14) + i * int(bar_h * 2.6)
            odraw.rounded_rectangle(
                (sx0 + int(screen_w * 0.07), y, sx0 + int(screen_w * (0.07 + frac * 0.5)), y + bar_h),
                radius=bar_h // 2,
                fill=BAR + (170,),
            )

    # Dokunma dalgası: iki halka + merkez nokta
    cx, cy = sx0 + int(screen_w * (0.62 if detailed else 0.5)), sy0 + int(screen_h * (0.62 if detailed else 0.5))
    r_dot = int(s * (0.05 if mid else 0.07))
    r_ring = int(s * (0.115 if mid else 0.15))
    ring_w = max(2, int(s * (0.018 if mid else 0.03)))
    if detailed:
        r_ring2 = int(r_ring * 1.7)
        odraw.ellipse((cx - r_ring2, cy - r_ring2, cx + r_ring2, cy + r_ring2), outline=RIPPLE + (120,), width=ring_w)
    canvas = Image.alpha_composite(canvas, overlay)
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((cx - r_dot, cy - r_dot, cx + r_dot, cy + r_dot), fill=RIPPLE)
    draw.ellipse((cx - r_ring, cy - r_ring, cx + r_ring, cy + r_ring), outline=RIPPLE, width=ring_w)

    # Tablet altı: ana ekran düğmesi çizgisi + USB kablosu ipucu (yalnızca ayrıntılı boyutlarda)
    if detailed:
        cable_w = int(s * 0.10)
        cable_x0 = (s - cable_w) // 2
        draw.rounded_rectangle(
            (cable_x0, by0 + bh - int(s * 0.005), cable_x0 + cable_w, by0 + bh + int(s * 0.075)),
            radius=int(s * 0.02),
            fill=(148, 163, 184),
        )
        draw.line(
            (s // 2, by0 + bh + int(s * 0.07), s // 2, int(s * 0.9)),
            fill=(148, 163, 184),
            width=max(2, int(s * 0.022)),
        )

    # "3" rozeti (3. Ekran): sağ alt
    badge_r = int(s * (0.19 if detailed else (0.23 if mid else 0.27)))
    bcx, bcy = int(s * (0.76 if detailed else 0.74)), int(s * (0.77 if detailed else 0.74))
    draw.ellipse((bcx - badge_r, bcy - badge_r, bcx + badge_r, bcy + badge_r), fill=AMBER, outline=BG_BOTTOM, width=max(2, int(s * 0.02)))
    font_path = Path(r"C:\Windows\Fonts\segoeuib.ttf")
    font = ImageFont.truetype(str(font_path), int(badge_r * 1.45)) if font_path.is_file() else ImageFont.load_default()
    draw.text((bcx, bcy), "3", font=font, fill=AMBER_TEXT, anchor="mm")

    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    frames: dict[int, Image.Image] = {}
    for size in sorted(set(PNG_SIZES) | set(ICO_SIZES)):
        frames[size] = draw_icon(size)

    for size in PNG_SIZES:
        frames[size].save(HERE / f"icon_{size}.png", optimize=True)

    ico_frames = [frames[size] for size in ICO_SIZES]
    ico_frames[-1].save(
        HERE / "app.ico",
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
        append_images=ico_frames[:-1],
    )

    CLIENT_ASSETS.mkdir(parents=True, exist_ok=True)
    frames[192].save(CLIENT_ASSETS / "icon-192.png", optimize=True)
    print("Simgeler üretildi:", ", ".join(f"{s}px" for s in PNG_SIZES), "+ app.ico", ICO_SIZES)


if __name__ == "__main__":
    main()
