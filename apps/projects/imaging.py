from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageOps

THUMB_SIZE = (400, 400)
PREVIEW_SIZE = (1600, 1600)


def load_rgb(fileobj):
    img = Image.open(fileobj)
    img = ImageOps.exif_transpose(img)  # respect camera/export rotation
    return img.convert("RGB")           # JPEG output needs RGB (no alpha)


def make_thumbnail(img, size=THUMB_SIZE):
    thumb = img.copy()
    thumb.thumbnail(size, Image.Resampling.LANCZOS)  # keeps aspect ratio, never upscales
    return thumb


def add_watermark(img, text):
    base = img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default(size=max(16, base.width // 30))  # needs Pillow 10.1+
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = right - left, bottom - top
    step_x, step_y = text_w * 2, text_h * 5
    for row, y in enumerate(range(0, base.height, step_y)):
        start_x = -text_w if row % 2 else 0  # stagger every other row
        for x in range(start_x, base.width, step_x):
            draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 90))      # shadow
            draw.text((x, y), text, font=font, fill=(255, 255, 255, 120))        # text
    return Image.alpha_composite(base, overlay).convert("RGB")


def make_preview(img, text, size=PREVIEW_SIZE):
    preview = img.copy()
    preview.thumbnail(size, Image.Resampling.LANCZOS)
    return add_watermark(preview, text)


def to_jpeg_bytes(img, quality=85):
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()