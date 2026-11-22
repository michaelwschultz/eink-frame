"""Generates a 3-color (white/black/red) fallback card when the backend is unreachable."""

from datetime import datetime
import os
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont

EPD_WIDTH = 800
EPD_HEIGHT = 480

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
PURE_RED = (255, 0, 0)

BOLD_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)

REGULAR_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "DejaVuSans.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


def _load_font(size, bold=False):
    """Load the best available TrueType font, falling back to Pillow's default."""
    candidates = BOLD_FONT_CANDIDATES if bold else REGULAR_FONT_CANDIDATES
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _draw_offline_cloud_icon(image, center_x, center_y):
    """Draw a crisp pure-red disconnected-cloud icon centered at (center_x, center_y)."""
    scale = 2
    box_w, box_h = 220 * scale, 160 * scale
    layer = Image.new("RGB", (box_w, box_h), WHITE)
    draw = ImageDraw.Draw(layer)
    cx, cy = box_w // 2, box_h // 2 + 8 * scale
    inset = 10 * scale

    # Cloud silhouette built from circles + flat base aligned at cy + 46
    lobes = (
        (cx - 72 * scale, cy - 14 * scale, cx - 12 * scale, cy + 46 * scale),
        (cx - 46 * scale, cy - 54 * scale, cx + 38 * scale, cy + 30 * scale),
        (cx + 12 * scale, cy - 18 * scale, cx + 76 * scale, cy + 46 * scale),
    )
    for box in lobes:
        draw.ellipse(box, fill=PURE_RED)
    draw.rectangle(
        (cx - 42 * scale, cy - 2 * scale, cx + 44 * scale, cy + 46 * scale),
        fill=PURE_RED,
    )

    # White inner cutout to make it a bold outline-style cloud
    for x0, y0, x1, y1 in lobes:
        draw.ellipse((x0 + inset, y0 + inset, x1 - inset, y1 - inset), fill=WHITE)
    draw.rectangle(
        (cx - 42 * scale, cy - 2 * scale, cx + 44 * scale, cy + 46 * scale - inset),
        fill=WHITE,
    )

    # Diagonal slash: wide white knockout + crisp pure-red bar with rounded caps
    slash = [(cx - 66 * scale, cy - 58 * scale), (cx + 66 * scale, cy + 54 * scale)]
    draw.line(slash, fill=WHITE, width=22 * scale)
    draw.line(slash, fill=PURE_RED, width=10 * scale)
    for px, py in slash:
        draw.ellipse(
            (px - 5 * scale, py - 5 * scale, px + 5 * scale, py + 5 * scale),
            fill=PURE_RED,
        )

    icon = layer.resize((box_w // scale, box_h // scale), Image.Resampling.LANCZOS)
    image.paste(icon, (center_x - icon.width // 2, center_y - icon.height // 2))


def _draw_centered_text(draw, y_pos, text, font, fill=BLACK):
    """Draw horizontally centered text at y_pos and return its bottom y coordinate."""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x_pos = (EPD_WIDTH - text_w) // 2 - bbox[0]
    draw.text((x_pos, y_pos - bbox[1]), text, font=font, fill=fill)
    return y_pos + text_h


def _quantize_for_eink(image):
    """Snap anti-aliased edge pixels strictly to pure white, pure black, or pure red."""
    pixels = image.load()
    for x in range(image.width):
        for y in range(image.height):
            r, g, b = pixels[x, y]
            if (r - g) >= 80 and (r - b) >= 80:
                pixels[x, y] = PURE_RED
            elif (r + g + b) < 420:
                pixels[x, y] = BLACK
            else:
                pixels[x, y] = WHITE


def render_error_card(output_path, backend_url="https://eink.schultz.co", detail=None):
    """Render an 800x480 'Unable to connect to server' card and save it to output_path."""
    image = Image.new("RGB", (EPD_WIDTH, EPD_HEIGHT), WHITE)
    draw = ImageDraw.Draw(image)

    # Clean inset border
    draw.rectangle((24, 24, EPD_WIDTH - 25, EPD_HEIGHT - 25), outline=BLACK, width=2)

    # Pure red disconnected-cloud icon centered in the upper-middle area
    _draw_offline_cloud_icon(image, EPD_WIDTH // 2, 168)

    # Headline and subtitle in pure black
    host = urlparse(backend_url).netloc or backend_url
    next_y = _draw_centered_text(
        draw, 276, "Unable to connect to server", _load_font(38, bold=True)
    )
    _draw_centered_text(draw, next_y + 18, detail or f"Could not reach {host}", _load_font(20))

    # Subtle divider and retry note at the bottom
    rule_y = EPD_HEIGHT - 84
    draw.line([(120, rule_y), (EPD_WIDTH - 120, rule_y)], fill=BLACK, width=1)
    timestamp = datetime.now().strftime("%b %d, %H:%M")
    _draw_centered_text(
        draw,
        rule_y + 20,
        f"Will retry on next refresh  |  Last attempt {timestamp}",
        _load_font(17),
    )

    _quantize_for_eink(image)

    if os.path.dirname(output_path):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
    image.save(output_path, format="PNG")
    return output_path


if __name__ == "__main__":
    path = render_error_card(os.path.join("images", "fetched-image.png"))
    print(f"Saved error card to {path}")
