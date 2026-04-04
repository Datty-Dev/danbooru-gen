#!/usr/bin/env python3
"""Text Overlay Engine — speech bubbles, subtitles, title cards for MangaCut."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")


def load_font(size, bold=True):
    """Load bundled font."""
    path = FONT_BOLD if bold else FONT_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()


def render_speech_bubble(img, text, position="top-right", font_size=28, padding=12):
    """Add a speech bubble to an image.

    Args:
        img: PIL Image
        text: bubble text
        position: top-left, top-right, top-center, bottom-left, bottom-right, bottom-center
        font_size: text font size
        padding: bubble padding

    Returns:
        Modified PIL Image
    """
    frame = img.copy()
    draw = ImageDraw.Draw(frame)
    font = load_font(font_size, bold=True)

    # Calculate text size
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    bubble_w = text_w + padding * 2
    bubble_h = text_h + padding * 2
    margin = 15

    w, h = frame.size

    # Position mapping
    positions = {
        "top-left": (margin, margin),
        "top-right": (w - bubble_w - margin, margin),
        "top-center": ((w - bubble_w) // 2, margin),
        "bottom-left": (margin, h - bubble_h - margin - 20),
        "bottom-right": (w - bubble_w - margin, h - bubble_h - margin - 20),
        "bottom-center": ((w - bubble_w) // 2, h - bubble_h - margin - 20),
    }
    x, y = positions.get(position, positions["top-right"])

    # Draw bubble (rounded rectangle)
    draw.rounded_rectangle(
        [x, y, x + bubble_w, y + bubble_h],
        radius=12,
        fill="white",
        outline="black",
        width=2,
    )

    # Draw tail pointing down toward character
    tail_x = x + bubble_w // 2
    tail_y = y + bubble_h
    draw.polygon(
        [(tail_x - 8, tail_y), (tail_x + 8, tail_y), (tail_x, tail_y + 14)],
        fill="white",
        outline="black",
    )
    # Fix the top edge of the tail (cover the outline)
    draw.line([(tail_x - 8, tail_y), (tail_x + 8, tail_y)], fill="white", width=3)

    # Draw text
    draw.text((x + padding, y + padding - bbox[1]), text, fill="black", font=font)

    return frame


def render_subtitle(img, text, font_size=24, bg_opacity=160, start=None, end=None, progress=None):
    """Add a subtitle bar at the bottom of the frame.

    Args:
        img: PIL Image
        text: subtitle text
        font_size: text font size
        bg_opacity: background bar opacity (0-255)
        start: start time (0-1 of scene duration), None = always show
        end: end time (0-1 of scene duration), None = always show
        progress: current scene progress (0-1)

    Returns:
        Modified PIL Image (or original if outside time range)
    """
    # Check time range
    if progress is not None and start is not None and end is not None:
        if progress < start or progress > end:
            return img

    frame = img.copy()
    w, h = frame.size
    font = load_font(font_size, bold=True)

    # Text size
    bbox = draw = ImageDraw.Draw(frame).textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Background bar
    bar_h = text_h + 20
    bar_y = h - bar_h - 10

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bar_draw = ImageDraw.Draw(overlay)
    bar_draw.rounded_rectangle(
        [20, bar_y, w - 20, bar_y + bar_h],
        radius=8,
        fill=(0, 0, 0, bg_opacity),
    )
    frame = frame.convert("RGBA")
    frame = Image.alpha_composite(frame, overlay)

    # Text
    text_draw = ImageDraw.Draw(frame)
    text_x = (w - text_w) // 2
    text_y = bar_y + 10 - bbox[1]
    text_draw.text((text_x, text_y), text, fill="white", font=font)

    return frame.convert("RGB")


def render_title_card(width, height, text, font_size=72, animation="fade", progress=0.5):
    """Generate a title card frame.

    Args:
        width, height: frame dimensions
        text: title text
        font_size: title font size
        animation: fade, typewriter, none
        progress: animation progress (0-1)

    Returns:
        PIL Image
    """
    font = load_font(font_size, bold=True)

    # Black background
    frame = Image.new("RGB", (width, height), "black")
    draw = ImageDraw.Draw(frame)

    # Calculate text position (centered)
    display_text = text

    if animation == "typewriter":
        # Reveal characters progressively
        char_count = max(1, int(len(text) * progress))
        display_text = text[:char_count]
    elif animation == "fade":
        # Will apply opacity at the end
        pass

    bbox = draw.textbbox((0, 0), display_text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (width - text_w) // 2
    y = (height - text_h) // 2

    draw.text((x, y - bbox[1]), display_text, fill="white", font=font)

    # Fade animation: adjust overall opacity
    if animation == "fade":
        if progress < 0.2:
            opacity = progress / 0.2
        elif progress > 0.8:
            opacity = (1 - progress) / 0.2
        else:
            opacity = 1.0

        black = Image.new("RGB", (width, height), "black")
        frame = Image.blend(black, frame, opacity)

    return frame


def render_text_overlay(img, overlay_config, progress=None):
    """Apply a text overlay to an image based on config.

    Args:
        img: PIL Image
        overlay_config: dict with type, text, position, etc.
        progress: scene progress (0-1) for timed overlays

    Returns:
        Modified PIL Image
    """
    overlay_type = overlay_config.get("type")

    if overlay_type == "speech_bubble":
        return render_speech_bubble(
            img,
            text=overlay_config["text"],
            position=overlay_config.get("position", "top-right"),
            font_size=overlay_config.get("font_size", 28),
        )
    elif overlay_type == "subtitle":
        return render_subtitle(
            img,
            text=overlay_config["text"],
            font_size=overlay_config.get("font_size", 24),
            start=overlay_config.get("start"),
            end=overlay_config.get("end"),
            progress=progress,
        )
    else:
        return img


# Test
if __name__ == "__main__":
    # Create test image
    test = Image.new("RGB", (1080, 1920), (40, 40, 60))
    draw = ImageDraw.Draw(test)
    draw.rectangle([100, 100, 980, 1820], fill=(60, 60, 80), outline="white")

    # Test speech bubble
    bubble = render_speech_bubble(test, "I will get stronger!", position="top-right")
    bubble.save("/tmp/test_bubble.png")
    print("✓ Speech bubble")

    # Test subtitle
    sub = render_subtitle(test, "And so he disappeared into the night.", progress=0.5)
    sub.save("/tmp/test_subtitle.png")
    print("✓ Subtitle")

    # Test title card
    title = render_title_card(1080, 1920, "Chapter 1: The Fall", animation="fade", progress=0.5)
    title.save("/tmp/test_title.png")
    print("✓ Title card")

    print("All text overlays working!")
