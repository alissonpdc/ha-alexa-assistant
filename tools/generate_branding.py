#!/usr/bin/env python3
"""Generate official branding icons and logos for Alexa Assistant."""
import math
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def create_icon_image(size: int = 2048) -> Image.Image:
    """Create supersampled 2048x2048 icon image."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = 120
    radius = 420

    # 1. Background squircle with vertical gradient
    bg_mask = Image.new("L", (size, size), 0)
    bg_mask_draw = ImageDraw.Draw(bg_mask)
    bg_mask_draw.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=radius,
        fill=255,
    )

    # Gradient background: Deep space navy (#0B132B to #1C2541)
    gradient = Image.new("RGBA", (size, size))
    grad_draw = ImageDraw.Draw(gradient)
    for y in range(size):
        ratio = y / size
        r = int(11 * (1 - ratio) + 28 * ratio)
        g = int(19 * (1 - ratio) + 37 * ratio)
        b = int(43 * (1 - ratio) + 65 * ratio)
        grad_draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    img.paste(gradient, (0, 0), bg_mask)

    # 2. Glowing inner ambient light (radial glow in upper center)
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cx, cy = size // 2, int(size * 0.45)
    for rad in range(600, 50, -15):
        alpha = int((1.0 - (rad / 600)) * 60)
        glow_draw.ellipse(
            [cx - rad, cy - rad, cx + rad, cy + rad],
            fill=(0, 202, 255, alpha),
        )
    img.alpha_composite(glow)

    # 3. Squircle accent border (subtle glowing stroke)
    border_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    border_draw = ImageDraw.Draw(border_img)
    border_draw.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=radius,
        outline=(0, 202, 255, 120),
        width=12,
    )
    img.alpha_composite(border_img)

    # 4. Draw outer Alexa Ring
    # Center = cx, cy = 1024, 1024
    center_x, center_y = size // 2, size // 2
    ring_radius = 580
    ring_width = 88

    ring_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ring_draw = ImageDraw.Draw(ring_img)

    # Draw glow underneath the ring
    for g_rad in range(ring_width + 60, ring_width, -10):
        g_alpha = int((1.0 - (g_rad - ring_width) / 60) * 80)
        ring_draw.ellipse(
            [
                center_x - (ring_radius + g_rad // 2),
                center_y - (ring_radius + g_rad // 2),
                center_x + (ring_radius + g_rad // 2),
                center_y + (ring_radius + g_rad // 2),
            ],
            outline=(0, 229, 255, g_alpha),
            width=g_rad,
        )

    # Main Alexa Cyan gradient ring (#00C6FF to #0072FF)
    ring_draw.ellipse(
        [
            center_x - ring_radius,
            center_y - ring_radius,
            center_x + ring_radius,
            center_y + ring_radius,
        ],
        outline=(0, 210, 255, 255),
        width=ring_width,
    )

    # Inner bright ring highlight
    ring_draw.ellipse(
        [
            center_x - ring_radius,
            center_y - ring_radius,
            center_x + ring_radius,
            center_y + ring_radius,
        ],
        outline=(220, 250, 255, 220),
        width=14,
    )

    img.alpha_composite(ring_img)

    # 5. Draw Home Assistant House Silhouette in center
    house_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(house_img)

    # House Roof: Triangle + Chimney
    roof_top = (center_x, center_y - 340)
    roof_left = (center_x - 320, center_y - 60)
    roof_right = (center_x + 320, center_y - 60)

    # Roof Stroke
    h_draw.polygon(
        [roof_top, roof_right, roof_left],
        fill=(255, 255, 255, 240),
    )

    # Chimney
    h_draw.rectangle(
        [center_x + 160, center_y - 280, center_x + 230, center_y - 140],
        fill=(255, 255, 255, 240),
    )

    # House Body (Cutout or walls)
    body_left = center_x - 240
    body_right = center_x + 240
    body_top = center_y - 60
    body_bottom = center_y + 320
    h_draw.rounded_rectangle(
        [body_left, body_top, body_right, body_bottom],
        radius=30,
        fill=(255, 255, 255, 240),
    )

    # Cutout inside of house so it's a sleek frame
    inner_pad = 52
    h_draw.rounded_rectangle(
        [body_left + inner_pad, body_top + inner_pad, body_right - inner_pad, body_bottom - 20],
        radius=20,
        fill=(13, 22, 40, 255),
    )

    # Inner roof cutout
    h_draw.polygon(
        [
            (center_x, center_y - 250),
            (center_x + 230, body_top + inner_pad),
            (center_x - 230, body_top + inner_pad),
        ],
        fill=(13, 22, 40, 255),
    )

    img.alpha_composite(house_img)

    # 6. Soundwave / Voice Frequency Equalizer Bars in center of house
    wave_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    w_draw = ImageDraw.Draw(wave_img)

    # 5 bars centered around center_x, center_y + 80
    bar_w = 34
    bar_gap = 26
    bar_heights = [120, 220, 310, 220, 120]
    total_w = len(bar_heights) * bar_w + (len(bar_heights) - 1) * bar_gap
    start_x = center_x - total_w // 2
    wave_cy = center_y + 90

    for i, bh in enumerate(bar_heights):
        bx = start_x + i * (bar_w + bar_gap)
        by1 = wave_cy - bh // 2
        by2 = wave_cy + bh // 2

        # Glow for bar
        w_draw.rounded_rectangle(
            [bx - 8, by1 - 8, bx + bar_w + 8, by2 + 8],
            radius=24,
            fill=(0, 210, 255, 90),
        )
        # Bar fill with cyan gradient
        w_draw.rounded_rectangle(
            [bx, by1, bx + bar_w, by2],
            radius=17,
            fill=(0, 235, 255, 255),
        )

    img.alpha_composite(wave_img)

    return img


def create_logo_image(icon_img_512: Image.Image) -> Image.Image:
    """Create wide 1024x512 logo image with icon on left and text on right."""
    logo = Image.new("RGBA", (1024, 512), (13, 22, 40, 0))
    draw = ImageDraw.Draw(logo)

    # Paste resized icon on the left
    icon_resized = icon_img_512.resize((360, 360), Image.Resampling.LANCZOS)
    logo.paste(icon_resized, (60, 76), icon_resized)

    # Text positioning
    tx = 460
    # Try finding system font
    font_large = None
    font_sub = None
    for font_path in [
        "/System/Library/Fonts/SFPro-Bold.ttf",
        "/System/Library/Fonts/SFCompact-Bold.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]:
        if os.path.exists(font_path):
            try:
                font_large = ImageFont.truetype(font_path, 72)
                font_sub = ImageFont.truetype(font_path, 28)
                break
            except Exception:
                pass

    if font_large is None:
        font_large = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    # Draw "Alexa"
    draw.text((tx, 150), "Alexa", font=font_large, fill=(255, 255, 255, 255))
    # Draw "Assistant"
    draw.text((tx, 235), "Assistant", font=font_large, fill=(0, 202, 255, 255))
    # Draw Subtitle / Slogan
    draw.text(
        (tx, 325),
        "Home Assistant Integration",
        font=font_sub,
        fill=(148, 163, 184, 255),
    )

    return logo


def main() -> None:
    repo_root = Path(__file__).parent.parent
    brand_dir = repo_root / "custom_components" / "alexa_assistant" / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)

    print("Generating supersampled icon (2048x2048)...")
    icon_2048 = create_icon_image(2048)

    print("Downscaling to 1024x1024 (icon@2x.png)...")
    icon_1024 = icon_2048.resize((1024, 1024), Image.Resampling.LANCZOS)

    print("Downscaling to 512x512 (icon.png)...")
    icon_512 = icon_2048.resize((512, 512), Image.Resampling.LANCZOS)

    # Save to custom_components/alexa_assistant/brand/
    icon_512.save(brand_dir / "icon.png", "PNG", optimize=True)
    icon_1024.save(brand_dir / "icon@2x.png", "PNG", optimize=True)
    print(f"Saved: {brand_dir / 'icon.png'}")
    print(f"Saved: {brand_dir / 'icon@2x.png'}")

    # Save to repo root
    icon_512.save(repo_root / "icon.png", "PNG", optimize=True)
    icon_1024.save(repo_root / "icon@2x.png", "PNG", optimize=True)
    print(f"Saved: {repo_root / 'icon.png'}")

    print("Generating logo (1024x512)...")
    logo = create_logo_image(icon_512)
    logo.save(brand_dir / "logo.png", "PNG", optimize=True)
    logo.save(repo_root / "logo.png", "PNG", optimize=True)
    print(f"Saved: {brand_dir / 'logo.png'}")
    print(f"Saved: {repo_root / 'logo.png'}")


if __name__ == "__main__":
    main()
